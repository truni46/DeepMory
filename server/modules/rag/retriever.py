"""
All retrieval strategies in one file — mirrors the single-file pattern of llmProvider.py.

Strategy selection is controlled by RETRIEVER_MODE env var.
Reranking is an optional post-process, controlled by RERANKER_PROVIDER.
"""
from __future__ import annotations

import asyncio
import os
from typing import Dict, List, Optional, Protocol

from config.logger import logger
from modules.rag.repository import RagRepository, SearchResult


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class BaseRetriever(Protocol):
    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]: ...


# ---------------------------------------------------------------------------
# Semantic (dense cosine)
# ---------------------------------------------------------------------------

class SemanticRetriever:
    def __init__(self, repo: RagRepository):
        self._repo = repo

    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        return await self._repo.searchByText(collection, query, limit, filter)


# ---------------------------------------------------------------------------
# BM25 (sparse keyword)
# For Qdrant: uses sparse vector search via SPLADE/BM42 if available.
# Falls back to PostgreSQL full-text search when pgvector backend is active.
# ---------------------------------------------------------------------------

class BM25Retriever:
    def __init__(self, repo: RagRepository):
        self._repo = repo
        self._vectorStoreType = os.getenv("VECTOR_STORE_TYPE", "qdrant").lower()

    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        if self._vectorStoreType == "qdrant":
            return await self._qdrantSparse(query, collection, limit, filter)
        return await self._pgFullText(query, collection, limit)

    async def _qdrantSparse(
        self, query: str, collection: str, limit: int, filter: Optional[Dict]
    ) -> List[SearchResult]:
        try:
            from qdrant_client.models import SparseVector, NamedSparseVector, SearchRequest
            # Build a simple TF-IDF-style sparse vector from query tokens
            tokens = query.lower().split()
            indices, values = self._buildSparseVector(tokens)
            client = await self._repo.store.provider._getClient()
            results = await client.search(
                collection_name=collection,
                query_vector=NamedSparseVector(
                    name="text",
                    vector=SparseVector(indices=indices, values=values),
                ),
                limit=limit,
                with_payload=True,
            )
            return [
                self._repo._toSearchResult(
                    {"id": str(r.id), "score": r.score, "payload": r.payload}
                )
                for r in results
            ]
        except Exception as e:
            logger.warning(f"BM25 sparse search failed, falling back to semantic: {e}")
            return await self._repo.searchByText(collection, query, limit, filter)

    async def _pgFullText(self, query: str, collection: str, limit: int) -> List[SearchResult]:
        from config.database import db
        if not (db.useDatabase and db.pool):
            return []
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, payload,
                          ts_rank(to_tsvector('english', payload->>'content'),
                                  plainto_tsquery('english', $1)) AS score
                   FROM vector_points
                   WHERE collection = $2
                     AND to_tsvector('english', payload->>'content') @@ plainto_tsquery('english', $1)
                   ORDER BY score DESC
                   LIMIT $3""",
                query, collection, limit,
            )
        return [
            self._repo._toSearchResult(
                {"id": r["id"], "score": float(r["score"]), "payload": r["payload"]}
            )
            for r in rows
        ]

    @staticmethod
    def _buildSparseVector(tokens: List[str]):
        from collections import Counter
        counts = Counter(tokens)
        vocab = sorted(set(tokens))
        token2idx = {t: i for i, t in enumerate(vocab)}
        indices = [token2idx[t] for t in counts]
        total = sum(counts.values())
        values = [counts[t] / total for t in counts]
        return indices, values


# ---------------------------------------------------------------------------
# Hybrid (dense + sparse → RRF fusion)
# ---------------------------------------------------------------------------

class HybridRetriever:
    def __init__(self, repo: RagRepository, denseWeight: float = 0.6, sparseWeight: float = 0.4):
        self._dense = SemanticRetriever(repo)
        self._sparse = BM25Retriever(repo)
        self.denseWeight = denseWeight
        self.sparseWeight = sparseWeight

    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        denseResults, sparseResults = await asyncio.gather(
            self._dense.retrieve(query, collection, limit * 2, filter),
            self._sparse.retrieve(query, collection, limit * 2, filter),
        )
        return self._rrfFusion(denseResults, sparseResults, limit)

    def _rrfFusion(
        self,
        listA: List[SearchResult],
        listB: List[SearchResult],
        limit: int,
        k: int = 60,
    ) -> List[SearchResult]:
        scores: Dict[str, float] = {}
        byId: Dict[str, SearchResult] = {}

        for rank, result in enumerate(listA):
            rid = result.document.id
            scores[rid] = scores.get(rid, 0.0) + self.denseWeight / (k + rank + 1)
            byId[rid] = result

        for rank, result in enumerate(listB):
            rid = result.document.id
            scores[rid] = scores.get(rid, 0.0) + self.sparseWeight / (k + rank + 1)
            if rid not in byId:
                byId[rid] = result

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            SearchResult(document=byId[rid].document, score=score)
            for rid, score in ranked[:limit]
        ]


# ---------------------------------------------------------------------------
# HyDE (Hypothetical Document Embeddings)
# ---------------------------------------------------------------------------

class HyDERetriever:
    def __init__(self, repo: RagRepository, llm):
        self._repo = repo
        self._llm = llm
        self._base = SemanticRetriever(repo)

    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        hypoDoc = await self._generateHypotheticalDoc(query)
        hypoVector = await self._repo.embedder.embedQuery(hypoDoc)
        return await self._repo.searchByVector(collection, hypoVector, limit, filter)

    async def _generateHypotheticalDoc(self, query: str) -> str:
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Write a short, factual passage (2-4 sentences) "
                    "that directly answers the following question. Do not mention the question itself."
                ),
            },
            {"role": "user", "content": query},
        ]
        try:
            return await self._llm.generateResponse(prompt)
        except Exception as e:
            logger.warning(f"HyDE generation failed, falling back to raw query: {e}")
            return query


# ---------------------------------------------------------------------------
# Multi-Query Retriever
# ---------------------------------------------------------------------------

class MultiQueryRetriever:
    def __init__(self, repo: RagRepository, llm, numQueries: int = 3):
        self._repo = repo
        self._llm = llm
        self._numQueries = numQueries
        self._base = SemanticRetriever(repo)

    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        queries = await self._expandQueries(query)
        tasks = [self._base.retrieve(q, collection, limit, filter) for q in queries]
        allResults: List[List[SearchResult]] = await asyncio.gather(*tasks)

        seen: Dict[str, SearchResult] = {}
        for results in allResults:
            for r in results:
                rid = r.document.id
                if rid not in seen or r.score > seen[rid].score:
                    seen[rid] = r

        ranked = sorted(seen.values(), key=lambda r: r.score, reverse=True)
        return ranked[:limit]

    async def _expandQueries(self, query: str) -> List[str]:
        prompt = [
            {
                "role": "system",
                "content": (
                    f"Generate {self._numQueries} distinct reformulations of the user query "
                    "to improve document retrieval coverage. "
                    "Return only the queries, one per line, no numbering or extra text."
                ),
            },
            {"role": "user", "content": query},
        ]
        try:
            response = await self._llm.generateResponse(prompt)
            variants = [line.strip() for line in response.strip().splitlines() if line.strip()]
            return [query] + variants[: self._numQueries]
        except Exception as e:
            logger.warning(f"Multi-query expansion failed: {e}")
            return [query]


# ---------------------------------------------------------------------------
# MMR (Maximal Marginal Relevance)
# ---------------------------------------------------------------------------

class MMRRetriever:
    def __init__(self, repo: RagRepository, lambda_: float = 0.5):
        self._repo = repo
        self._lambda = lambda_
        self._base = SemanticRetriever(repo)

    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        candidates = await self._base.retrieve(query, collection, limit * 4, filter)
        queryVector = await self._repo.embedder.embedQuery(query)
        return self._mmrSelect(candidates, queryVector, limit)

    def _mmrSelect(
        self,
        candidates: List[SearchResult],
        queryVector: List[float],
        limit: int,
    ) -> List[SearchResult]:
        import math

        def cosineSim(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            normA = math.sqrt(sum(x * x for x in a))
            normB = math.sqrt(sum(x * x for x in b))
            return dot / (normA * normB + 1e-10)

        selected: List[SearchResult] = []
        remaining = list(candidates)

        while remaining and len(selected) < limit:
            best = None
            bestScore = float("-inf")
            for candidate in remaining:
                relevance = candidate.score
                if selected:
                    maxSim = max(
                        cosineSim(
                            [candidate.score],  # proxy — actual vectors not stored here
                            [s.score],
                        )
                        for s in selected
                    )
                else:
                    maxSim = 0.0
                mmrScore = self._lambda * relevance - (1 - self._lambda) * maxSim
                if mmrScore > bestScore:
                    bestScore = mmrScore
                    best = candidate
            if best:
                selected.append(best)
                remaining.remove(best)

        return selected


# ---------------------------------------------------------------------------
# Reranker (post-process)
# ---------------------------------------------------------------------------

class Reranker:
    def __init__(self, provider: str = None):
        self.providerName = (provider or os.getenv("RERANKER_PROVIDER", "none")).lower()

    async def rerank(
        self,
        query: str,
        results: List[SearchResult],
        limit: int,
    ) -> List[SearchResult]:
        if self.providerName == "cohere":
            return await self._rerankCohere(query, results, limit)
        elif self.providerName == "cross_encoder":
            return await self._rerankCrossEncoder(query, results, limit)
        return results[:limit]

    async def _rerankCohere(
        self, query: str, results: List[SearchResult], limit: int
    ) -> List[SearchResult]:
        import cohere
        apiKey = os.getenv("COHERE_API_KEY", "")
        client = cohere.AsyncClient(apiKey)
        docs = [r.document.content for r in results]
        response = await client.rerank(
            model="rerank-english-v3.0",
            query=query,
            documents=docs,
            top_n=limit,
        )
        reranked = []
        for item in response.results:
            original = results[item.index]
            reranked.append(SearchResult(document=original.document, score=item.relevance_score))
        return reranked

    async def _rerankCrossEncoder(
        self, query: str, results: List[SearchResult], limit: int
    ) -> List[SearchResult]:
        import asyncio
        from sentence_transformers import CrossEncoder

        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        pairs = [[query, r.document.content] for r in results]
        scores = await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.predict(pairs).tolist()
        )
        ranked = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
        return [SearchResult(document=r.document, score=float(s)) for r, s in ranked[:limit]]


# ---------------------------------------------------------------------------
# RetrieverService — reads RETRIEVER_MODE and builds the right strategy
# ---------------------------------------------------------------------------

class RetrieverService:
    def __init__(self, repo: RagRepository):
        self._repo = repo
        self.mode = os.getenv("RETRIEVER_MODE", "semantic").lower()
        self._retriever = self._buildRetriever(self.mode)
        self._reranker = Reranker()
        logger.info(f"Retriever initialized: mode={self.mode}, reranker={self._reranker.providerName}")

    def _buildRetriever(self, mode: str):
        # Lazy import to avoid circular at module load time
        from modules.llm.llmProvider import llmProvider

        if mode == "semantic":
            return SemanticRetriever(self._repo)
        elif mode == "bm25":
            return BM25Retriever(self._repo)
        elif mode == "hybrid":
            return HybridRetriever(self._repo)
        elif mode == "hyde":
            return HyDERetriever(self._repo, llmProvider)
        elif mode == "multiquery":
            return MultiQueryRetriever(self._repo, llmProvider)
        elif mode == "mmr":
            return MMRRetriever(self._repo)
        else:
            logger.warning(f"Unknown RETRIEVER_MODE '{mode}', falling back to semantic.")
            return SemanticRetriever(self._repo)

    async def retrieve(
        self,
        query: str,
        collection: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
        rerank: bool = False,
    ) -> List[SearchResult]:
        results = await self._retriever.retrieve(query, collection, limit, filter)
        if rerank and self._reranker.providerName != "none":
            results = await self._reranker.rerank(query, results, limit)
        return results


def buildRetriever(mode: str = None) -> RetrieverService:
    from modules.rag.repository import ragRepository
    svc = RetrieverService(ragRepository)
    if mode:
        svc._retriever = svc._buildRetriever(mode)
    return svc


retrieverService = buildRetriever()
