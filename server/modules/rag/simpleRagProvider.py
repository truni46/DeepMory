from __future__ import annotations

import os
import uuid
from typing import Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from config.logger import logger
from modules.llm.embeddingProvider import embeddingService
from modules.rag.documentParser import ParsedPage, documentParserService
from modules.rag.repository import Document, SearchResult


def _chunkPages(pages: List[ParsedPage], chunkSize: int = 800, overlap: int = 100) -> List[dict]:
    if overlap >= chunkSize:
        raise ValueError(f"_chunkPages: overlap ({overlap}) must be less than chunkSize ({chunkSize})")

    # Build flat text and record where each page starts so chunks can span boundaries
    fullText = ""
    pageBoundaries: List[tuple] = []  # (startChar, pageNumber)
    for page in pages:
        if not page.text.strip():
            continue
        pageBoundaries.append((len(fullText), page.pageNumber))
        fullText += page.text + "\n"

    if not fullText.strip():
        return []

    def _pageAt(pos: int) -> int:
        pageNum = pageBoundaries[0][1] if pageBoundaries else 1
        for startChar, num in pageBoundaries:
            if pos >= startChar:
                pageNum = num
            else:
                break
        return pageNum

    chunks = []
    chunkIndex = 0
    start = 0
    while start < len(fullText):
        chunkText = fullText[start:start + chunkSize]
        if chunkText.strip():
            chunks.append({
                "text": chunkText,
                "pageNumber": _pageAt(start),
                "chunkIndex": chunkIndex,
            })
            chunkIndex += 1
        start += chunkSize - overlap
    return chunks


class SimpleRagProvider:
    """Direct Qdrant + embedding RAG — no external graph dependencies."""

    def __init__(self):
        self._url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self._apiKey = os.getenv("QDRANT_API_KEY") or None
        self._client: Optional[AsyncQdrantClient] = None

    async def _getClient(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(url=self._url, api_key=self._apiKey)
        return self._client

    def _collectionName(self, namespace: str) -> str:
        return f"simple_rag_{namespace}"

    async def _ensureCollection(self, name: str) -> None:
        client = await self._getClient()
        collections = await client.get_collections()
        existing = {c.name for c in collections.collections}
        if name not in existing:
            await client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=embeddingService.dimension,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"SimpleRagProvider: created collection '{name}'")

    async def index(self, filePath: str, projectId: str, documentId: str, userId: str, filename: Optional[str] = None) -> int:
        try:
            pages = documentParserService.parse(filePath)
            if not pages:
                logger.warning(f"SimpleRagProvider: no content extracted from '{filePath}'")
                return 0
            chunks = _chunkPages(pages)
            if not chunks:
                logger.warning(f"SimpleRagProvider.index: no chunks produced from '{filePath}' for document {documentId}")
                return 0
            texts = [c["text"] for c in chunks]
            vectors = await embeddingService.embedBatch(texts)
            collName = self._collectionName(f"project_{projectId}")
            await self._ensureCollection(collName)
            client = await self._getClient()
            filename = filename or os.path.basename(filePath)
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectors[i],
                    payload={
                        "documentId": documentId,
                        "userId": userId,
                        "filename": filename,
                        "filePath": filePath,
                        "pageNumber": chunks[i]["pageNumber"],
                        "chunkIndex": chunks[i]["chunkIndex"],
                        "text": chunks[i]["text"],
                    },
                )
                for i in range(len(chunks))
            ]
            await client.upsert(collection_name=collName, points=points)
            logger.info(f"SimpleRagProvider: indexed {len(points)} chunks for document {documentId}")
            return len(points)
        except Exception as e:
            logger.error(f"SimpleRagProvider.index failed for document {documentId}: {e}")
            raise

    async def deleteDocumentChunks(self, projectId: str, documentId: str) -> None:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"project_{projectId}")
            await client.delete(
                collection_name=collName,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="documentId", match=MatchValue(value=documentId))]
                    )
                ),
            )
            logger.info(f"SimpleRagProvider: deleted chunks for document {documentId}")
        except Exception as e:
            logger.error(f"SimpleRagProvider.deleteDocumentChunks failed for document {documentId}: {e}")

    async def searchContext(
        self, query: str, projectId: str, limit: int = 5, **kwargs
    ) -> List[SearchResult]:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"project_{projectId}")
            queryVector = await embeddingService.embed(query)
            response = await client.query_points(
                collection_name=collName,
                query=queryVector,
                limit=limit,
                with_payload=True,
            )
            return [
                SearchResult(
                    document=Document(
                        id=r.payload.get("documentId", str(uuid.uuid4())),
                        content=r.payload.get("text", ""),
                        metadata={
                            "documentId": r.payload.get("documentId"),
                            "chunkIndex": r.payload.get("chunkIndex"),
                            "filename": r.payload.get("filename"),
                            "pageNumber": r.payload.get("pageNumber"),
                        },
                    ),
                    score=r.score,
                )
                for r in response.points
                if r.payload.get("text")
            ]
        except Exception as e:
            logger.warning(f"SimpleRagProvider.searchContext failed for project {projectId}: {e}")
            return []

    async def searchContextByDocumentIds(
        self, query: str, namespace: str, documentIds: List[str], limit: int = 5
    ) -> List[SearchResult]:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"project_{namespace}")
            queryVector = await embeddingService.embed(query)
            response = await client.query_points(
                collection_name=collName,
                query=queryVector,
                limit=limit,
                with_payload=True,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="documentId",
                            match=MatchAny(any=documentIds),
                        )
                    ]
                ),
            )
            return [
                SearchResult(
                    document=Document(
                        id=r.payload.get("documentId", str(uuid.uuid4())),
                        content=r.payload.get("text", ""),
                        metadata={
                            "documentId": r.payload.get("documentId"),
                            "chunkIndex": r.payload.get("chunkIndex"),
                            "filename": r.payload.get("filename"),
                            "pageNumber": r.payload.get("pageNumber"),
                        },
                    ),
                    score=r.score,
                )
                for r in response.points
                if r.payload.get("text")
            ]
        except Exception as e:
            logger.warning(f"SimpleRagProvider.searchContextByDocumentIds failed for namespace {namespace}: {e}")
            return []

    async def upsertMemoryVector(
        self, userId: str, memoryId: str, content: str, metadata: Optional[Dict] = None
    ) -> None:
        try:
            collName = self._collectionName(f"user_{userId}")
            await self._ensureCollection(collName)
            client = await self._getClient()
            vector = await embeddingService.embed(content)
            await client.upsert(
                collection_name=collName,
                points=[
                    PointStruct(
                        id=memoryId,
                        vector=vector,
                        payload={"text": content, **(metadata or {})},
                    )
                ],
            )
        except Exception as e:
            logger.error(f"SimpleRagProvider.upsertMemoryVector failed for user {userId}: {e}")

    async def searchMemoryVectors(
        self, userId: str, query: str, limit: int = 5, threshold: float = 0.65
    ) -> List[SearchResult]:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"user_{userId}")
            queryVector = await embeddingService.embed(query)
            response = await client.query_points(
                collection_name=collName,
                query=queryVector,
                limit=limit,
                with_payload=True,
                score_threshold=threshold,
            )
            return [
                SearchResult(
                    document=Document(
                        id=str(r.id),
                        content=r.payload.get("text", ""),
                        metadata={},
                    ),
                    score=r.score,
                )
                for r in response.points
                if r.payload.get("text")
            ]
        except Exception as e:
            logger.warning(f"SimpleRagProvider.searchMemoryVectors failed for user {userId}: {e}")
            return []

    async def deleteMemoryVector(self, userId: str, memoryId: str) -> None:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"user_{userId}")
            await client.delete(
                collection_name=collName,
                points_selector=PointIdsList(points=[memoryId]),
            )
        except Exception as e:
            logger.error(f"SimpleRagProvider.deleteMemoryVector failed memoryId={memoryId}: {e}")

    async def upsertDocumentIndex(
        self, userId: str, documentId: str, filename: str, summary: str
    ) -> None:
        try:
            collName = self._collectionName(f"docIndex_{userId}")
            await self._ensureCollection(collName)
            client = await self._getClient()
            vector = await embeddingService.embed(summary)
            await client.upsert(
                collection_name=collName,
                points=[
                    PointStruct(
                        id=str(uuid.UUID(str(documentId))),
                        vector=vector,
                        payload={
                            "documentId": documentId,
                            "filename": filename,
                            "userId": userId,
                        },
                    )
                ],
            )
            logger.info(f"SimpleRagProvider: upserted doc index for document {documentId}")
        except Exception as e:
            logger.error(f"SimpleRagProvider.upsertDocumentIndex failed for document {documentId}: {e}")

    async def searchDocumentIndex(
        self, userId: str, query: str, limit: int = 10, threshold: float = 0.6
    ) -> List[Dict]:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"docIndex_{userId}")
            queryVector = await embeddingService.embed(query)
            response = await client.query_points(
                collection_name=collName,
                query=queryVector,
                limit=limit,
                with_payload=True,
                score_threshold=threshold,
            )
            return [
                {
                    "documentId": r.payload.get("documentId"),
                    "filename": r.payload.get("filename"),
                    "score": r.score,
                }
                for r in response.points
                if r.payload.get("documentId")
            ]
        except Exception as e:
            logger.debug(f"SimpleRagProvider.searchDocumentIndex failed for user {userId}: {e}")
            return []

    async def deleteDocumentIndex(self, userId: str, documentId: str) -> None:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"docIndex_{userId}")
            await client.delete(
                collection_name=collName,
                points_selector=PointIdsList(points=[str(uuid.UUID(str(documentId)))]),
            )
            logger.info(f"SimpleRagProvider: deleted doc index for document {documentId}")
        except Exception as e:
            logger.error(f"SimpleRagProvider.deleteDocumentIndex failed for document {documentId}: {e}")


simpleRagProvider = SimpleRagProvider()
