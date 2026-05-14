from __future__ import annotations

import asyncio
import os
import time
from typing import List, Protocol

import httpx
from openai import AsyncOpenAI

from config.logger import logger

_ollamaSemaphore = asyncio.Semaphore(int(os.getenv("OLLAMA_MAX_CONCURRENT", "1")))
_OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_EMBED_TIMEOUT", "300"))


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
        raw = baseUrl or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self._baseUrl = raw.rstrip("/").removesuffix("/v1")
        self._model = model or os.getenv("EMBEDDING_MODEL", "bge-m3")
        self._dim = dim

    async def embed(self, texts: List[str]) -> List[List[float]]:
        waitStart = time.perf_counter()
        async with _ollamaSemaphore:
            waitSec = time.perf_counter() - waitStart
            if waitSec > 1.0:
                logger.info(f"OllamaEmbeddingProvider.embed semaphore wait={waitSec:.1f}s texts={len(texts)}")
            return await self._doEmbed(texts)

    async def _doEmbed(self, texts: List[str]) -> List[List[float]]:
        charCount = sum(len(t) for t in texts)
        logger.info(f"OllamaEmbeddingProvider._doEmbed start texts={len(texts)} chars={charCount} model={self._model} timeout={_OLLAMA_TIMEOUT}s")
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_OLLAMA_TIMEOUT) as client:
                logger.info(f"OllamaEmbeddingProvider._doEmbed sending POST to {self._baseUrl}/api/embed")
                resp = await client.post(
                    f"{self._baseUrl}/api/embed",
                    json={"model": self._model, "input": texts, "keep_alive": "10m"},
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings", [])
                elapsed = time.perf_counter() - t0
                logger.info(f"OllamaEmbeddingProvider._doEmbed done texts={len(texts)} elapsed={elapsed:.2f}s")
                return embeddings
        except Exception as e:
            elapsed = time.perf_counter() - t0
            logger.error(f"OllamaEmbeddingProvider._doEmbed failed after {elapsed:.2f}s model={self._model}: {type(e).__name__}: {e}")
            raise

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def modelName(self) -> str:
        return self._model


class FastEmbedProvider:
    """In-process ONNX embedding via fastembed — no HTTP, no Ollama, fastest option on CPU.

    Recommended models (set via EMBEDDING_MODEL env):
      BAAI/bge-m3                              1024 dim  multilingual, drop-in for Ollama bge-m3
      nomic-ai/nomic-embed-text-v1.5           768 dim  multilingual, faster
      BAAI/bge-small-en-v1.5                   384 dim  fastest, English-only

    First run downloads the ONNX model from HuggingFace Hub into the fastembed
    cache dir (FASTEMBED_CACHE_DIR env, default ~/.cache/fastembed). Mount a
    Docker volume there so the download survives container rebuilds.

    NOTE: switching model changes the vector dimension — existing Qdrant collections
    must be deleted and re-indexed if you change EMBEDDING_DIM.
    """

    def __init__(self, model: str = None, dim: int = 1024):
        self._modelName = model or os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self._dim = dim
        self._model = None

    def _getModel(self):
        if self._model is None:
            from fastembed import TextEmbedding
            logger.info(f"FastEmbedProvider: loading model '{self._modelName}'")
            self._model = TextEmbedding(model_name=self._modelName)
            logger.info(f"FastEmbedProvider: model loaded")
        return self._model

    async def embed(self, texts: List[str]) -> List[List[float]]:
        t0 = time.perf_counter()
        try:
            loop = asyncio.get_event_loop()
            model = self._getModel()
            vectors = await loop.run_in_executor(None, lambda: [v.tolist() for v in model.embed(texts)])
            elapsed = time.perf_counter() - t0
            logger.info(f"FastEmbedProvider.embed done texts={len(texts)} elapsed={elapsed:.2f}s")
            return vectors
        except Exception as e:
            elapsed = time.perf_counter() - t0
            logger.error(f"FastEmbedProvider.embed failed after {elapsed:.2f}s: {type(e).__name__}: {e}")
            raise

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def modelName(self) -> str:
        return self._modelName


class HuggingFaceEmbeddingProvider:
    """HuggingFace Inference API — runs bge-m3 on HF's GPU servers, free tier available.

    Get a free token at https://huggingface.co/settings/tokens
    Set HF_TOKEN env var.

    Free tier: rate-limited but sufficient for moderate usage.
    """

    _BASE = "https://api-inference.huggingface.co/models"

    def __init__(self, model: str = None, dim: int = 1024):
        self._model = model or os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self._dim = dim
        self._token = os.getenv("HF_TOKEN", "")
        if not self._token:
            logger.warning("HuggingFaceEmbeddingProvider: HF_TOKEN not set — requests will be rate-limited")

    async def embed(self, texts: List[str]) -> List[List[float]]:
        url = f"{self._BASE}/{self._model}"
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        charCount = sum(len(t) for t in texts)
        logger.info(f"HuggingFaceEmbeddingProvider.embed start texts={len(texts)} chars={charCount} model={self._model}")
        t0 = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, headers=headers, json={"inputs": texts})

                if resp.status_code == 503:
                    # Model is loading on HF servers — wait and retry once
                    estimatedTime = resp.json().get("estimated_time", 20)
                    logger.info(f"HuggingFaceEmbeddingProvider: model loading, waiting {estimatedTime:.0f}s")
                    await asyncio.sleep(min(estimatedTime, 30))
                    resp = await client.post(url, headers=headers, json={"inputs": texts})

                resp.raise_for_status()
                data = resp.json()
                elapsed = time.perf_counter() - t0
                logger.info(f"HuggingFaceEmbeddingProvider.embed done texts={len(texts)} elapsed={elapsed:.2f}s")
                return data
        except Exception as e:
            elapsed = time.perf_counter() - t0
            logger.error(f"HuggingFaceEmbeddingProvider.embed failed after {elapsed:.2f}s: {type(e).__name__}: {e}")
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
            logger.error(f"OpenAIEmbeddingProvider.embed failed model={self._model}: {type(e).__name__}: {e}")
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
            logger.error(f"GenericOpenAIEmbeddingProvider.embed failed model={self._model}: {type(e).__name__}: {e}")
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
            elif self.providerName == "fastembed":
                return FastEmbedProvider(dim=self._dim)
            elif self.providerName == "huggingface":
                return HuggingFaceEmbeddingProvider(dim=self._dim)
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

    async def embedBatch(self, texts: List[str], batchSize: int = int(os.getenv("OLLAMA_EMBED_BATCH_SIZE", "8"))) -> List[List[float]]:
        """Embed multiple texts, splitting into batches to avoid large payloads."""
        if not texts:
            return []
        totalBatches = (len(texts) + batchSize - 1) // batchSize
        logger.info(f"EmbeddingService.embedBatch start total={len(texts)} texts batchSize={batchSize} batches={totalBatches}")
        t0 = time.perf_counter()
        results = []
        for i in range(0, len(texts), batchSize):
            batch = texts[i:i + batchSize]
            batchNum = i // batchSize + 1
            logger.info(f"EmbeddingService.embedBatch batch {batchNum}/{totalBatches} size={len(batch)}")
            vectors = await self._provider.embed(batch)
            results.extend(vectors)
        elapsed = time.perf_counter() - t0
        logger.info(f"EmbeddingService.embedBatch done total={len(texts)} elapsed={elapsed:.2f}s avg={(elapsed/totalBatches):.2f}s/batch")
        return results


embeddingService = EmbeddingService()
