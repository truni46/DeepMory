"""
LightRAG provider — manages LightRAG instances per project/user namespace.

Each namespace (project_{id} or user_{id}) gets its own LightRAG instance
with isolated working_dir, graph, and vector storage.
"""
from __future__ import annotations

import os
from functools import partial
from typing import Dict

from config.logger import logger

from lightrag import LightRAG, QueryParam
from lightrag.llm.openai import openai_complete_if_cache, openai_embed
from lightrag.utils import EmbeddingFunc


# ---------------------------------------------------------------------------
# LLM provider mapping — maps LLM_PROVIDER env to OpenAI-compatible base_url
# ---------------------------------------------------------------------------

_LLM_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "ollama": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    "vllm": os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1"),
}


def _getBaseUrl() -> str:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    return _LLM_BASE_URLS.get(provider, _LLM_BASE_URLS["gemini"])


def _getApiKey() -> str:
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "openai":
        return os.getenv("OPENAI_API_KEY", "")
    elif provider == "gemini" or provider == "gemini_native":
        return os.getenv("GEMINI_API_KEY", "")
    elif provider == "ollama":
        return "ollama"
    elif provider == "vllm":
        return os.getenv("VLLM_API_KEY", "EMPTY")
    return os.getenv("OPENAI_API_KEY", "")


# ---------------------------------------------------------------------------
# LLM function for LightRAG
# ---------------------------------------------------------------------------

async def _llmFunc(
    prompt,
    system_prompt=None,
    history_messages=None,
    keyword_extraction=False,
    **kwargs,
) -> str:
    """LLM function compatible with LightRAG's expected signature."""
    try:
        return await openai_complete_if_cache(
            model=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
            prompt=prompt,
            system_prompt=system_prompt,
            history_messages=history_messages or [],
            api_key=_getApiKey(),
            base_url=_getBaseUrl(),
            **kwargs,
        )
    except Exception as e:
        logger.error(f"LightRAG LLM call failed: {e}")
        raise


# ---------------------------------------------------------------------------
# Embedding function for LightRAG
# ---------------------------------------------------------------------------

def _buildEmbeddingFunc() -> EmbeddingFunc:
    embeddingProvider = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
    embeddingModel = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    embeddingDim = int(os.getenv("EMBEDDING_DIM", 1536))
    apiKey = os.getenv("OPENAI_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY", "")

    if embeddingProvider == "openai":
        return EmbeddingFunc(
            embedding_dim=embeddingDim,
            max_token_size=8192,
            func=partial(
                openai_embed,
                model=embeddingModel,
                api_key=apiKey,
            ),
        )
    elif embeddingProvider == "ollama":
        from lightrag.llm.ollama import ollama_embed
        return EmbeddingFunc(
            embedding_dim=embeddingDim,
            max_token_size=8192,
            func=partial(
                ollama_embed,
                embed_model=embeddingModel,
                host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ),
        )
    else:
        # Fallback to OpenAI-compatible embedding
        return EmbeddingFunc(
            embedding_dim=embeddingDim,
            max_token_size=8192,
            func=partial(
                openai_embed,
                model=embeddingModel,
                api_key=apiKey,
                base_url=_getBaseUrl(),
            ),
        )


# ---------------------------------------------------------------------------
# Provider class — manages per-namespace LightRAG instances
# ---------------------------------------------------------------------------

class LightRAGProvider:
    """
    Factory for LightRAG instances.
    One instance per namespace (project_id or user_id).
    Instances are lazily created and cached.
    """

    def __init__(self):
        self._instances: Dict[str, LightRAG] = {}
        self._storageDir = os.getenv("LIGHTRAG_STORAGE_DIR", "./rag_storage")
        self._embeddingFunc = _buildEmbeddingFunc()

    async def getInstance(self, namespace: str) -> LightRAG:
        """Get or create a LightRAG instance for a namespace."""
        if namespace not in self._instances:
            try:
                workingDir = os.path.join(self._storageDir, namespace)
                os.makedirs(workingDir, exist_ok=True)

                instance = LightRAG(
                    working_dir=workingDir,
                    llm_model_func=_llmFunc,
                    llm_model_name=os.getenv("LLM_MODEL", "gemini-2.5-flash"),
                    embedding_func=self._embeddingFunc,
                    # Storage backends
                    kv_storage="JsonKVStorage",
                    vector_storage="QdrantVectorDBStorage",
                    graph_storage="Neo4JStorage",
                    # Qdrant config
                    vector_db_storage_cls_kwargs={
                        "url": os.getenv("QDRANT_URL", "http://localhost:6333"),
                        "api_key": os.getenv("QDRANT_API_KEY") or None,
                    },
                    # Neo4j config
                    graph_storage_cls_kwargs={
                        "url": os.getenv("NEO4J_URL", "bolt://localhost:7687"),
                        "username": os.getenv("NEO4J_USER", "neo4j"),
                        "password": os.getenv("NEO4J_PASSWORD", "password"),
                    },
                    # Chunking
                    chunk_token_size=int(os.getenv("LIGHTRAG_CHUNK_SIZE", 1200)),
                    chunk_overlap_token_size=int(os.getenv("LIGHTRAG_CHUNK_OVERLAP", 100)),
                )
                await instance.initialize_storages()
                self._instances[namespace] = instance
                logger.info(f"LightRAG instance created for namespace: {namespace}")
            except Exception as e:
                logger.error(f"Failed to create LightRAG instance for '{namespace}': {e}")
                raise

        return self._instances[namespace]

    async def removeInstance(self, namespace: str) -> None:
        """Finalize and remove a cached instance."""
        if namespace in self._instances:
            try:
                await self._instances[namespace].finalize_storages()
            except Exception as e:
                logger.warning(f"Error finalizing LightRAG instance '{namespace}': {e}")
            del self._instances[namespace]

    async def shutdown(self) -> None:
        """Finalize all cached instances. Call on app shutdown."""
        for ns in list(self._instances.keys()):
            await self.removeInstance(ns)
        logger.info("All LightRAG instances finalized")


lightragProvider = LightRAGProvider()
