"""
RAG Repository — types + vector store access layer.

Acts the same role as message/repository.py for PostgreSQL:
all vector store reads/writes flow through RagRepository only.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config.logger import logger


# ---------------------------------------------------------------------------
# Types / models
# ---------------------------------------------------------------------------

class SearchMode(str, Enum):
    SEMANTIC = "semantic"
    BM25 = "bm25"
    HYBRID = "hybrid"
    HYDE = "hyde"
    MULTIQUERY = "multiquery"
    MMR = "mmr"


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    projectId: Optional[str] = None
    userId: Optional[str] = None
    source: Optional[str] = None
    chunkIndex: Optional[int] = None


class VectorPoint(BaseModel):
    id: str
    vector: List[float]
    payload: Dict[str, Any] = Field(default_factory=dict)


class SearchResult(BaseModel):
    document: Document
    score: float


# ---------------------------------------------------------------------------
# Access layer
# ---------------------------------------------------------------------------

class RagRepository:
    """
    Vector store access layer. All cross-module callers (memory, knowledge)
    read/write through this class only — never directly touching vectorstore.py.
    """

    def __init__(self, store, embedder):
        self._store = store
        self._embedder = embedder

    @property
    def embedder(self):
        return self._embedder

    @property
    def store(self):
        return self._store

    # ---- Collection helpers ------------------------------------------------

    @staticmethod
    def projectCollection(projectId: str) -> str:
        return f"project_{projectId}_docs"

    @staticmethod
    def userMemoryCollection(userId: str) -> str:
        return f"user_{userId}_memories"

    async def ensureCollection(self, collection: str) -> None:
        await self._store.ensureCollection(collection, self._embedder.dim)

    # ---- Write ---------------------------------------------------------------

    async def upsertDocuments(self, collection: str, documents: List[Document]) -> None:
        """Embed and upsert a batch of documents into the vector store."""
        if not documents:
            return

        await self.ensureCollection(collection)

        texts = [doc.content for doc in documents]
        vectors = await self._embedder.embed(texts)

        points = []
        for doc, vector in zip(documents, vectors):
            payload = {
                "content": doc.content,
                "documentId": doc.id,
                "projectId": doc.projectId,
                "userId": doc.userId,
                "source": doc.source,
                "chunkIndex": doc.chunkIndex,
                **doc.metadata,
            }
            points.append({"id": doc.id, "vector": vector, "payload": payload})

        await self._store.upsert(collection, points)

    async def upsertPoint(self, collection: str, point: VectorPoint) -> None:
        """Upsert a single pre-computed VectorPoint (used by long-term memory)."""
        await self.ensureCollection(collection)
        await self._store.upsert(collection, [point.model_dump()])

    # ---- Read ----------------------------------------------------------------

    async def searchByVector(
        self,
        collection: str,
        queryVector: List[float],
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        raw = await self._store.search(collection, queryVector, limit, filter)
        return [self._toSearchResult(r) for r in raw]

    async def searchByText(
        self,
        collection: str,
        query: str,
        limit: int = 5,
        filter: Optional[Dict] = None,
    ) -> List[SearchResult]:
        queryVector = await self._embedder.embedQuery(query)
        return await self.searchByVector(collection, queryVector, limit, filter)

    # ---- Delete --------------------------------------------------------------

    async def deleteDocuments(self, collection: str, ids: List[str]) -> None:
        await self._store.delete(collection, ids)

    # ---- Internal ------------------------------------------------------------

    @staticmethod
    def _toSearchResult(raw: Dict) -> SearchResult:
        payload = raw.get("payload", {})
        doc = Document(
            id=raw.get("id", str(uuid.uuid4())),
            content=payload.get("content", ""),
            projectId=payload.get("projectId"),
            userId=payload.get("userId"),
            source=payload.get("source"),
            chunkIndex=payload.get("chunkIndex"),
            metadata={
                k: v for k, v in payload.items()
                if k not in {"content", "projectId", "userId", "source", "chunkIndex", "documentId"}
            },
        )
        return SearchResult(document=doc, score=raw.get("score", 0.0))


# ---------------------------------------------------------------------------
# Module-level singleton (wired at import time)
# ---------------------------------------------------------------------------

from modules.rag.vectorstore import vectorStore
from modules.rag.embedding import embeddingService

ragRepository = RagRepository(store=vectorStore, embedder=embeddingService)
