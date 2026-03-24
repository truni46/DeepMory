"""
Text splitter — splits Document content into overlapping chunks.
Token-aware when tiktoken is available; character-based fallback.
"""
from __future__ import annotations

import os
import uuid
from typing import List

from config.logger import logger
from modules.rag.repository import Document


class TextSplitter:
    def __init__(
        self,
        chunkSize: int = None,
        chunkOverlap: int = None,
    ):
        self.chunkSize = chunkSize or int(os.getenv("CHUNK_SIZE", 512))
        self.chunkOverlap = chunkOverlap or int(os.getenv("CHUNK_OVERLAP", 50))
        self._encoder = None

    def _getEncoder(self):
        if self._encoder is None:
            try:
                import tiktoken
                self._encoder = tiktoken.get_encoding("cl100k_base")
            except ImportError:
                self._encoder = False  # character fallback
        return self._encoder

    def _tokenLen(self, text: str) -> int:
        enc = self._getEncoder()
        if enc:
            return len(enc.encode(text))
        return len(text) // 4  # ~4 chars per token approximation

    def split(self, document: Document) -> List[Document]:
        text = document.content
        if not text.strip():
            return []

        chunks = self._splitRecursive(text, self.chunkSize, self.chunkOverlap)
        result = []
        for i, chunk in enumerate(chunks):
            result.append(Document(
                id=str(uuid.uuid4()),
                content=chunk,
                projectId=document.projectId,
                userId=document.userId,
                source=document.source,
                chunkIndex=i,
                metadata={**document.metadata, "parentId": document.id},
            ))
        return result

    def _splitRecursive(self, text: str, chunkSize: int, overlap: int) -> List[str]:
        """Split by paragraphs first, then by sentences, then by characters."""
        separators = ["\n\n", "\n", ". ", " ", ""]

        for sep in separators:
            if sep and sep in text:
                parts = text.split(sep)
                chunks = []
                current = ""
                for part in parts:
                    candidate = current + (sep if current else "") + part
                    if self._tokenLen(candidate) <= chunkSize:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        # carry overlap from tail of current into next chunk
                        overlap_text = self._tail(current, overlap)
                        current = overlap_text + (sep if overlap_text else "") + part
                if current:
                    chunks.append(current)
                if len(chunks) > 1:
                    return chunks

        # Final fallback: hard character split
        return self._hardSplit(text, chunkSize, overlap)

    def _hardSplit(self, text: str, chunkSize: int, overlap: int) -> List[str]:
        enc = self._getEncoder()
        if enc:
            tokens = enc.encode(text)
            step = chunkSize - overlap
            chunks = []
            for start in range(0, len(tokens), step):
                chunk_tokens = tokens[start: start + chunkSize]
                chunks.append(enc.decode(chunk_tokens))
            return chunks

        # character fallback
        step = chunkSize * 4 - overlap * 4
        size = chunkSize * 4
        return [text[i: i + size] for i in range(0, len(text), step)]

    def _tail(self, text: str, numTokens: int) -> str:
        enc = self._getEncoder()
        if enc:
            tokens = enc.encode(text)
            return enc.decode(tokens[-numTokens:]) if len(tokens) > numTokens else text
        chars = numTokens * 4
        return text[-chars:] if len(text) > chars else text


textSplitter = TextSplitter()
