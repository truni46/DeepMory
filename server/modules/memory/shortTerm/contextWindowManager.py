"""
Context window manager — token-aware sliding window over conversation messages.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional


class ContextWindowManager:

    def __init__(self, maxTokens: int = None, windowSize: int = None):
        self.maxTokens = maxTokens or int(os.getenv("CONV_SUMMARY_THRESHOLD", 4000))
        self.windowSize = windowSize or int(os.getenv("CONV_WINDOW_SIZE", 10))
        self._encoder = None

    def _getEncoder(self):
        if self._encoder is None:
            try:
                import tiktoken
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                self._encoder = False
        return self._encoder

    def countTokens(self, text: str) -> int:
        enc = self._getEncoder()
        if enc:
            return len(enc.encode(text))
        return len(text) // 4

    def totalTokens(self, messages: List[Dict]) -> int:
        return sum(self.countTokens(m.get("content", "")) for m in messages)

    def shouldSummarize(self, messages: List[Dict]) -> bool:
        return self.totalTokens(messages) > self.maxTokens

    def buildWindow(
        self,
        messages: List[Dict],
        summary: Optional[str] = None,
    ) -> List[Dict]:
        """
        Returns the messages list to prepend to the LLM messages array.
        If a summary exists it is injected as the first system message.
        Only the most recent messages fitting within the token budget are kept.
        """
        budget = self.maxTokens
        result: List[Dict] = []

        summaryMsg: Optional[Dict] = None
        if summary:
            summaryMsg = {
                "role": "system",
                "content": f"Summary of earlier conversation:\n{summary}",
            }
            budget -= self.countTokens(summaryMsg["content"])

        # Walk backwards and collect messages until budget is exhausted
        selected: List[Dict] = []
        for msg in reversed(messages):
            tokens = self.countTokens(msg.get("content", ""))
            if budget - tokens < 0:
                break
            selected.append(msg)
            budget -= tokens

        selected.reverse()

        if summaryMsg:
            result.append(summaryMsg)
        result.extend(selected)
        return result


contextWindowManager = ContextWindowManager()
