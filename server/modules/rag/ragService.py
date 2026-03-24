"""
RAG public facade.

This is the ONLY file that memory, knowledge, and message modules import from.
They never import vectorstore, retriever, embedding, or repository directly.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from config.logger import logger
from modules.rag.repository import Document, SearchResult, VectorPoint, ragRepository
from modules.rag.retriever import retrieverService


class RagService:

    # ------------------------------------------------------------------
    # Called by knowledge/service.py
    # ------------------------------------------------------------------

    async def index(
        self,
        filePath: str,
        projectId: str,
        documentId: str,
        userId: str,
    ) -> int:
        """
        Index a file into the project's vector collection.
        Returns the number of chunks indexed.
        """
        from modules.rag.pipeline.indexingService import indexingService

        collection = ragRepository.projectCollection(projectId)
        metadata = {"documentId": documentId, "projectId": projectId, "userId": userId}
        count = await indexingService.indexFile(filePath, collection, metadata)
        logger.info(f"RAG indexed {count} chunks for document {documentId} in collection '{collection}'")
        return count

    async def deleteDocumentChunks(self, projectId: str, documentId: str) -> None:
        """Remove all vector chunks belonging to a document from its project collection."""
        from modules.rag.pipeline.indexingService import indexingService

        collection = ragRepository.projectCollection(projectId)
        await indexingService.deleteDocument(collection, documentId)
        logger.info(f"RAG deleted chunks for document {documentId} from collection '{collection}'")

    # ------------------------------------------------------------------
    # Called by message/service.py  (RAG context for chat)
    # ------------------------------------------------------------------

    async def searchContext(
        self,
        query: str,
        projectId: str,
        limit: int = 5,
        rerank: bool = False,
    ) -> List[SearchResult]:
        """Semantic/hybrid search over a project's knowledge collection."""
        collection = ragRepository.projectCollection(projectId)
        return await retrieverService.retrieve(query, collection, limit, rerank=rerank)

    # ------------------------------------------------------------------
    # Called by memory/longTerm/memRAG.py
    # ------------------------------------------------------------------

    async def upsertMemoryVector(
        self,
        userId: str,
        memoryId: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Upsert a single user-memory fact into the user's memory collection."""
        collection = ragRepository.userMemoryCollection(userId)
        await ragRepository.ensureCollection(collection)
        vector = await ragRepository.embedder.embedQuery(content)
        point = VectorPoint(
            id=memoryId,
            vector=vector,
            payload={"content": content, "userId": userId, **(metadata or {})},
        )
        await ragRepository.upsertPoint(collection, point)

    async def searchMemoryVectors(
        self,
        userId: str,
        query: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        """Vector similarity search over a user's long-term memories."""
        collection = ragRepository.userMemoryCollection(userId)
        try:
            return await ragRepository.searchByText(collection, query, limit)
        except Exception as e:
            logger.warning(f"Memory vector search failed for user {userId}: {e}")
            return []

    async def deleteMemoryVector(self, userId: str, memoryId: str) -> None:
        """Remove a single memory vector from the user's memory collection."""
        collection = ragRepository.userMemoryCollection(userId)
        await ragRepository.deleteDocuments(collection, [memoryId])


ragService = RagService()
