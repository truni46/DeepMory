"""
Long-term memory orchestrator.
SQL ops go through memoryRepository; vector ops go through ragService (cross-module).
"""
from __future__ import annotations

import os
from typing import List

from config.logger import logger
from modules.memory.longTerm.extractionService import extractionService
from modules.memory.longTerm.repository import memoryRepository


class MemRAG:

    async def processConversationTurn(
        self,
        userId: str,
        conversationId: str,
        userMessage: str,
        assistantResponse: str,
    ) -> None:
        """
        Background task: extract facts → SQL write → vector upsert.
        Safe to fail silently — never blocks the chat response.
        """
        if os.getenv("MEMORY_EXTRACTION_ENABLED", "true").lower() != "true":
            return

        from modules.rag.ragService import ragService

        try:
            existing = await memoryRepository.getByUser(userId, limit=30)
            existingContent = [m["content"] for m in existing]

            newFacts = await extractionService.extractFacts(
                userMessage, assistantResponse, existingContent
            )

            for fact in newFacts:
                record = await memoryRepository.create(
                    userId=userId,
                    content=fact,
                    metadata={"conversationId": conversationId},
                )
                await ragService.upsertMemoryVector(
                    userId=userId,
                    memoryId=record["id"],
                    content=fact,
                    metadata={"conversationId": conversationId},
                )
                logger.info(f"Stored new memory for user {userId}: {fact[:60]}")

        except Exception as e:
            logger.error(f"Memory extraction failed for user {userId}: {e}")

    async def retrieveRelevantMemories(
        self,
        userId: str,
        query: str,
        limit: int = 5,
        threshold: float = 0.65,
    ) -> List[str]:
        """
        Vector similarity search over user's memories, filtered by relevance threshold.
        Only memories with similarity score >= threshold are returned, so off-topic
        memories never leak into the system prompt.
        """
        from modules.rag.ragService import ragService

        results = await ragService.searchMemoryVectors(userId, query, limit, threshold=threshold)
        if results:
            logger.info(
                f"[Memory] {len(results)} relevant memories for user {userId} "
                f"(top score: {results[0].score:.3f}, threshold: {threshold})"
            )
        else:
            logger.info(f"[Memory] no memories passed threshold {threshold} for user {userId}")
        return [r.document.content for r in results]

    async def deleteMemory(self, userId: str, memoryId: str) -> bool:
        from modules.rag.ragService import ragService

        success = await memoryRepository.delete(memoryId, userId)
        if success:
            await ragService.deleteMemoryVector(userId, memoryId)
        return success


memRAG = MemRAG()
