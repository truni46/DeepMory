"""
Short-term memory orchestrator — public entry point for Conv memory.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from config.logger import logger
from modules.memory.shortTerm.contextWindowManager import contextWindowManager
from modules.memory.shortTerm.repository import convMemoryRepository
from modules.memory.shortTerm.summaryService import summaryService


class ConvRAG:

    async def addTurn(self, conversationId: str, role: str, content: str) -> None:
        """
        Append one message to the context window.
        Triggers summarization and window trim when the token threshold is exceeded.
        """
        window = await convMemoryRepository.appendToWindow(
            conversationId, {"role": role, "content": content}
        )

        if contextWindowManager.shouldSummarize(window):
            await self._summarizeAndTrim(conversationId, window)

    async def getContextWindow(self, conversationId: str) -> List[Dict]:
        """
        Returns the messages list ready to be prepended to the LLM messages array.
        Includes an optional summary prefix message if a summary exists.
        """
        window = await convMemoryRepository.getWindow(conversationId)
        summary = await convMemoryRepository.getSummary(conversationId)
        return contextWindowManager.buildWindow(window, summary)

    async def clearConversation(self, conversationId: str) -> None:
        await convMemoryRepository.clearWindow(conversationId)
        await convMemoryRepository.clearSummary(conversationId)

    async def _summarizeAndTrim(self, conversationId: str, window: List[Dict]) -> None:
        try:
            existingSummary = await convMemoryRepository.getSummary(conversationId)
            newSummary = await summaryService.summarize(existingSummary, window)
            tokenCount = contextWindowManager.countTokens(newSummary)
            await convMemoryRepository.upsertSummary(conversationId, newSummary, tokenCount)

            # Keep only the last windowSize turns after summarizing
            trimmed = window[-contextWindowManager.windowSize:]
            await convMemoryRepository.setWindow(conversationId, trimmed)
        except Exception as e:
            logger.error(f"Failed to summarize conversation {conversationId}: {e}")


convRAG = ConvRAG()
