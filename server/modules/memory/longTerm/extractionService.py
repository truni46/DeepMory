"""
Extraction service — uses LLM to extract durable facts from a conversation turn.
"""
from __future__ import annotations

import json
from typing import List, Optional

from config.logger import logger
from common.prompts import FACT_EXTRACTION_SYSTEM, factExtractionUserPrompt


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
            {"role": "system", "content": FACT_EXTRACTION_SYSTEM},
            {"role": "user", "content": factExtractionUserPrompt(userMsg, assistantMsg, existing)},
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
