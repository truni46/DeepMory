"""
Summary service — uses LLM to produce a rolling summary when the context window is full.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from config.logger import logger
from common.prompts import CONV_SUMMARY_SYSTEM, convSummaryUserPrompt


class SummaryService:

    def __init__(self, llm):
        self._llm = llm

    async def summarize(
        self,
        existingSummary: Optional[str],
        newTurns: List[Dict],
    ) -> str:
        """
        Produces a new summary that incorporates both the previous summary
        (if any) and the recent conversation turns.
        """
        prompt = self._buildPrompt(existingSummary, newTurns)
        try:
            return await self._llm.generateResponse(prompt)
        except Exception as e:
            logger.error(f"Summarization LLM call failed: {e}")
            # Graceful degradation: return old summary or empty string
            return existingSummary or ""

    @staticmethod
    def _buildPrompt(existingSummary: Optional[str], turns: List[Dict]) -> List[Dict]:
        turns_text = "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in turns
        )

        return [
            {"role": "system", "content": CONV_SUMMARY_SYSTEM},
            {"role": "user", "content": convSummaryUserPrompt(existingSummary, turns_text)},
        ]


def _buildSummaryService() -> SummaryService:
    from modules.llm.llmProvider import llmProvider
    return SummaryService(llmProvider)


summaryService = _buildSummaryService()
