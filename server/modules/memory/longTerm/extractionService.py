"""
Extraction service — uses LLM to extract durable facts from a conversation turn.
"""
from __future__ import annotations

import json
from typing import List, Optional

from config.logger import logger


class ExtractionService:

    def __init__(self, llm):
        self._llm = llm

    async def extractFacts(
        self,
        userMessage: str,
        assistantResponse: str,
        existingFacts: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Returns 0-3 new fact strings worth storing as long-term memories.
        Returns empty list if nothing meaningful is found.
        """
        prompt = self._buildPrompt(userMessage, assistantResponse, existingFacts or [])
        try:
            raw = await self._llm.generateResponse(prompt)
            return self._parseFacts(raw)
        except Exception as e:
            logger.error(f"Fact extraction failed: {e}")
            return []

    @staticmethod
    def _buildPrompt(
        userMsg: str,
        assistantMsg: str,
        existing: List[str],
    ) -> List[dict]:
        existing_str = "\n".join(f"- {f}" for f in existing) if existing else "None"
        return [
            {
                "role": "system",
                "content": (
                    "You extract durable personal facts about the user from conversations. "
                    "Facts must be genuinely useful for future personalization "
                    "(preferences, goals, background, constraints). "
                    "Return a valid JSON array of strings. "
                    "Return [] if nothing is worth remembering. "
                    "Do not duplicate facts already in the existing list."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Existing facts:\n{existing_str}\n\n"
                    f"User: {userMsg[:800]}\n"
                    f"Assistant: {assistantMsg[:800]}\n\n"
                    "Extract 0-3 new facts as a JSON array:"
                ),
            },
        ]

    @staticmethod
    def _parseFacts(raw: str) -> List[str]:
        raw = raw.strip()
        # Find the JSON array in the response
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            return []
        try:
            facts = json.loads(raw[start: end + 1])
            return [f for f in facts if isinstance(f, str) and f.strip()]
        except json.JSONDecodeError:
            return []


def _buildExtractionService() -> ExtractionService:
    from modules.llm.llmProvider import llmProvider
    return ExtractionService(llmProvider)


extractionService = _buildExtractionService()
