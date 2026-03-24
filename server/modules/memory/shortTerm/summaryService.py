"""
Summary service — uses LLM to produce a rolling summary when the context window is full.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from config.logger import logger


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

        if existingSummary:
            user_content = (
                f"Previous summary:\n{existingSummary}\n\n"
                f"New conversation turns:\n{turns_text}\n\n"
                "Update the summary to incorporate the new turns. "
                "Keep it concise (3-5 sentences). Preserve key facts."
            )
        else:
            user_content = (
                f"Conversation:\n{turns_text}\n\n"
                "Summarize the key points of this conversation in 3-5 sentences "
                "so the context can be continued in future turns."
            )

        return [
            {
                "role": "system",
                "content": "You are a helpful assistant that summarizes conversations concisely.",
            },
            {"role": "user", "content": user_content},
        ]


def _buildSummaryService() -> SummaryService:
    from modules.llm.llmProvider import llmProvider
    return SummaryService(llmProvider)


summaryService = _buildSummaryService()
