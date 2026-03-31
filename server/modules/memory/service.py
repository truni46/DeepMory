"""
Memory facade — single import point for message/service.py.
Delegates to shortTerm (Conv) and longTerm (Mem) sub-modules.
"""
from __future__ import annotations

from typing import Dict, List

from modules.memory.shortTerm.convRAG import convRAG
from modules.memory.longTerm.memRAG import memRAG


class MemoryFacade:

    async def addTurn(self, conversationId: str, role: str, content: str) -> None:
        """Append one message turn to the conversation context window."""
        await convRAG.addTurn(conversationId, role, content)

    async def getContextWindow(self, conversationId: str) -> List[Dict]:
        """
        Return the managed context window (with optional summary prefix)
        ready to be concatenated with the system prompt in the LLM messages array.
        """
        return await convRAG.getContextWindow(conversationId)

    async def clearConversation(self, conversationId: str) -> None:
        """Wipe both Redis window and summary for a conversation."""
        await convRAG.clearConversation(conversationId)

    async def retrieveRelevantMemories(
        self,
        userId: str,
        query: str,
        limit: int = 5,
    ) -> List[str]:
        """
        Vector similarity search over user's long-term memories.
        Returns plain text strings for injection into the system prompt.
        """
        return await memRAG.retrieveRelevantMemories(userId, query, limit)

    async def processConversationTurn(
        self,
        userId: str,
        conversationId: str,
        userMessage: str,
        assistantResponse: str,
    ) -> None:
        """
        Background task: extract facts from the exchange and persist them
        in both the memories table and the user's vector collection.
        """
        await memRAG.processConversationTurn(
            userId, conversationId, userMessage, assistantResponse
        )

    async def deleteMemory(self, userId: str, memoryId: str) -> bool:
        return await memRAG.deleteMemory(userId, memoryId)


memoryFacade = MemoryFacade()
