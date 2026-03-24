"""
Indexing pipeline — orchestrates: load → split → upsert.
Called by ragService.index() after a file is saved to disk.
"""
from __future__ import annotations

from typing import Dict, Optional

from config.logger import logger
from modules.rag.pipeline.documentLoader import documentLoader
from modules.rag.pipeline.textSplitter import textSplitter
from modules.rag.repository import ragRepository


class IndexingService:

    async def indexFile(
        self,
        filePath: str,
        collection: str,
        metadata: Optional[Dict] = None,
    ) -> int:
        """
        Load file → split into chunks → embed and upsert to vector store.
        Returns the number of chunks indexed.
        """
        meta = metadata or {}

        raw_docs = await documentLoader.loadFromPath(filePath, meta)
        if not raw_docs:
            logger.warning(f"No content extracted from '{filePath}'")
            return 0

        chunks = []
        for doc in raw_docs:
            chunks.extend(textSplitter.split(doc))

        if not chunks:
            logger.warning(f"No chunks produced from '{filePath}'")
            return 0

        await ragRepository.upsertDocuments(collection, chunks)
        logger.info(f"Indexed {len(chunks)} chunks from '{filePath}' into '{collection}'")
        return len(chunks)

    async def deleteDocument(self, collection: str, documentId: str) -> None:
        """
        Delete all vector points belonging to a specific documentId.
        Uses a filter on payload.documentId when the backend supports it;
        falls back to a scan-based deletion via the repository.
        """
        # For Qdrant we can filter by payload; for pgvector we query by payload field
        try:
            from modules.rag.vectorstore import vectorStore
            from config.database import db

            if vectorStore.providerName == "pgvector" and db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT id FROM vector_points WHERE collection = $1 AND payload->>'documentId' = $2",
                        collection,
                        documentId,
                    )
                    ids = [r["id"] for r in rows]
            elif vectorStore.providerName == "qdrant":
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                client = await vectorStore.provider._getClient()
                result = await client.scroll(
                    collection_name=collection,
                    scroll_filter=Filter(
                        must=[FieldCondition(key="documentId", match=MatchValue(value=documentId))]
                    ),
                    limit=10000,
                    with_payload=False,
                )
                ids = [str(p.id) for p in result[0]]
            else:
                logger.warning(f"deleteDocument: unsupported backend '{vectorStore.providerName}'")
                return

            if ids:
                await ragRepository.deleteDocuments(collection, ids)
                logger.info(f"Deleted {len(ids)} chunks for document {documentId} from '{collection}'")
        except Exception as e:
            logger.error(f"Failed to delete document chunks for {documentId}: {e}")


indexingService = IndexingService()
