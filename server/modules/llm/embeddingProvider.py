from __future__ import annotations

import os
from typing import List, Protocol

import httpx
from openai import AsyncOpenAI

from config.logger import logger


class EmbeddingProvider(Protocol):
    """Abstract interface every embedding backend must satisfy."""

    async def embed(self, texts: List[str]) -> List[List[float]]:
        ...

    @property
    def dimension(self) -> int:
        ...

    @property
    def modelName(self) -> str:
        ...


class OllamaEmbeddingProvider:
    """Calls Ollama /api/embed endpoint (supports bge-m3, nomic-embed-text, etc.)."""

    def __init__(self, baseUrl: str = None, model: str = None, dim: int = 1024):
        self._baseUrl = (baseUrl or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._model = model or os.getenv("EMBEDDING_MODEL", "bge-m3")
        self._dim = dim

    async def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._baseUrl}/api/embed",
                    json={"model": self._model, "input": texts},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("embeddings", [])
        except Exception as e:
            logger.error(f"OllamaEmbeddingProvider.embed failed model={self._model}: {e}")
            raise

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def modelName(self) -> str:
        return self._model


class OpenAIEmbeddingProvider:
    """Uses official OpenAI embeddings API."""

    def __init__(self, apiKey: str = None, model: str = None, dim: int = 1536):
        apiKey = apiKey or os.getenv("OPENAI_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self._client = AsyncOpenAI(api_key=apiKey)
        self._model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self._dim = dim

    async def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = await self._client.embeddings.create(model=self._model, input=texts)
            return [item.embedding for item in resp.data]
        except Exception as e:
            logger.error(f"OpenAIEmbeddingProvider.embed failed model={self._model}: {e}")
            raise

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def modelName(self) -> str:
        return self._model


class GenericOpenAIEmbeddingProvider:
    """OpenAI-compatible endpoint with custom base_url (vLLM, LM Studio, etc.)."""

    def __init__(self, baseUrl: str = None, apiKey: str = None, model: str = None, dim: int = 1024):
        baseUrl = baseUrl or os.getenv("EMBEDDING_BASE_URL", "http://localhost:8000/v1")
        apiKey = apiKey or os.getenv("EMBEDDING_API_KEY", "EMPTY")
        self._client = AsyncOpenAI(api_key=apiKey, base_url=baseUrl)
        self._model = model or os.getenv("EMBEDDING_MODEL", "bge-m3")
        self._dim = dim

    async def embed(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = await self._client.embeddings.create(model=self._model, input=texts)
            return [item.embedding for item in resp.data]
        except Exception as e:
            logger.error(f"GenericOpenAIEmbeddingProvider.embed failed model={self._model}: {e}")
            raise

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def modelName(self) -> str:
        return self._model


class EmbeddingService:
    """ServiceWrapper — reads env, builds provider, exposes convenience methods."""

    def __init__(self):
        self.providerName = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()
        self._dim = int(os.getenv("EMBEDDING_DIM", "1024"))
        self._provider = self._getProvider()
        logger.info(f"EmbeddingService initialized: provider={self.providerName} model={self._provider.modelName} dim={self._dim}")

    def _getProvider(self) -> EmbeddingProvider:
        try:
            if self.providerName == "ollama":
                return OllamaEmbeddingProvider(dim=self._dim)
            elif self.providerName == "openai":
                return OpenAIEmbeddingProvider(dim=self._dim)
            elif self.providerName == "generic":
                return GenericOpenAIEmbeddingProvider(dim=self._dim)
            else:
                logger.warning(f"Unknown embedding provider '{self.providerName}', falling back to Ollama")
                return OllamaEmbeddingProvider(dim=self._dim)
        except Exception as e:
            logger.error(f"Failed to init embedding provider {self.providerName}: {e}")
            return OllamaEmbeddingProvider(dim=self._dim)

    @property
    def dimension(self) -> int:
        return self._dim

    async def embed(self, text: str) -> List[float]:
        """Embed a single text, returns vector."""
        results = await self._provider.embed([text])
        if results and len(results) > 0:
            return results[0]
        return [0.0] * self._dim

    async def embedBatch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in one call."""
        if not texts:
            return []
        return await self._provider.embed(texts)


embeddingService = EmbeddingService()
