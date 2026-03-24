from typing import List
from typing import Protocol
import os
from config.logger import logger


class EmbeddingProvider(Protocol):
    async def embed(self, texts: List[str]) -> List[List[float]]: ...
    async def embedQuery(self, text: str) -> List[float]: ...

    @property
    def dim(self) -> int: ...


class OpenAIEmbeddingProvider:
    def __init__(self, apiKey: str = None, model: str = None):
        self.apiKey = apiKey or os.getenv("OPENAI_EMBEDDING_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self._dim = int(os.getenv("EMBEDDING_DIM", 1536))
        self._client = None

    def _getClient(self):
        if not self._client:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.apiKey or "dummy")
        return self._client

    async def embed(self, texts: List[str]) -> List[List[float]]:
        client = self._getClient()
        response = await client.embeddings.create(model=self.model, input=texts)
        return [item.embedding for item in response.data]

    async def embedQuery(self, text: str) -> List[float]:
        results = await self.embed([text])
        return results[0]

    @property
    def dim(self) -> int:
        return self._dim


class BedrockEmbeddingProvider:
    def __init__(self, region: str = None, model: str = None):
        self.region = region or os.getenv("BEDROCK_REGION", "us-east-1")
        self.model = model or os.getenv("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")
        self._dim = int(os.getenv("EMBEDDING_DIM", 1024))
        self._client = None

    def _getClient(self):
        if not self._client:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=self.region)
        return self._client

    async def embed(self, texts: List[str]) -> List[List[float]]:
        import asyncio
        import json
        client = self._getClient()
        results = []
        for text in texts:
            body = json.dumps({"inputText": text})
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda b=body: client.invoke_model(modelId=self.model, body=b)
            )
            data = json.loads(response["body"].read())
            results.append(data["embedding"])
        return results

    async def embedQuery(self, text: str) -> List[float]:
        results = await self.embed([text])
        return results[0]

    @property
    def dim(self) -> int:
        return self._dim


class LocalEmbeddingProvider:
    """Fallback — no external API key required (sentence-transformers)."""

    def __init__(self, model: str = None):
        self.modelName = model or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self._model = None
        self._dim = 384

    def _getModel(self):
        if not self._model:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.modelName)
            self._dim = self._model.get_sentence_embedding_dimension()
        return self._model

    async def embed(self, texts: List[str]) -> List[List[float]]:
        import asyncio
        model = self._getModel()
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: model.encode(texts).tolist()
        )

    async def embedQuery(self, text: str) -> List[float]:
        results = await self.embed([text])
        return results[0]

    @property
    def dim(self) -> int:
        return self._dim


class EmbeddingService:
    def __init__(self):
        self.providerName = os.getenv("EMBEDDING_PROVIDER", "openai").lower()
        self.provider = self._buildProvider()
        logger.info(f"Embedding service initialized: {self.providerName}")

    def _buildProvider(self):
        try:
            if self.providerName == "openai":
                return OpenAIEmbeddingProvider()
            elif self.providerName == "bedrock":
                return BedrockEmbeddingProvider()
            elif self.providerName == "local":
                return LocalEmbeddingProvider()
            else:
                logger.warning(f"Unknown EMBEDDING_PROVIDER '{self.providerName}', falling back to local.")
                return LocalEmbeddingProvider()
        except Exception as e:
            logger.error(f"Failed to initialize embedding provider '{self.providerName}': {e}")
            return LocalEmbeddingProvider()

    async def embed(self, texts: List[str]) -> List[List[float]]:
        return await self.provider.embed(texts)

    async def embedQuery(self, text: str) -> List[float]:
        return await self.provider.embedQuery(text)

    @property
    def dim(self) -> int:
        return self.provider.dim


embeddingService = EmbeddingService()
