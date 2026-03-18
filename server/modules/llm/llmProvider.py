from typing import List, Dict, AsyncGenerator, Optional
from typing import Protocol
import os
from openai import AsyncOpenAI
from config.logger import logger

class LLMProvider(Protocol):
    async def generateResponse(self, messages: List[Dict], stream: bool = False) -> str | AsyncGenerator[str, None]:
        ...
    
    @property
    def modelName(self) -> str:
        ...


class BaseOpenAIProvider:
    def __init__(self, apiKey: str, baseUrl: str, model: str):
        self.client = AsyncOpenAI(api_key=apiKey, base_url=baseUrl)
        self.model = model

    async def generateResponse(self, messages: List[Dict], stream: bool = False):
        try:
            if stream:
                return self.streamResponse(messages)
            else:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.7
                )
                return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Provider ({self.model}) error: {e}")
            return f"Error from LLM provider: {str(e)}"

    async def streamResponse(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                if chunk.choices:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
        except Exception as e:
            logger.error(f"LLM Streaming error ({self.model}): {e}")
            yield f"Error streaming response: {str(e)}"
            
    @property
    def modelName(self) -> str:
        return self.model

class OllamaProvider(BaseOpenAIProvider):
    def __init__(self, baseUrl: str = None, model: str = None):
        baseUrl = baseUrl or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        model = model or os.getenv("LLM_MODEL", "qwen3:8b") 
        super().__init__(apiKey="ollama", baseUrl=baseUrl, model=model)

class OpenAIProvider(BaseOpenAIProvider):
    def __init__(self, apiKey: str = None, model: str = None):
        apiKey = apiKey or os.getenv("OPENAI_API_KEY")
        model = model or os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        super().__init__(apiKey=apiKey or "dummy", baseUrl="https://api.openai.com/v1", model=model)

class GeminiProvider(BaseOpenAIProvider):
    def __init__(self, apiKey: str = None, model: str = None):
        apiKey = apiKey or os.getenv("GEMINI_API_KEY")
        baseUrl = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = model or os.getenv("LLM_MODEL", "gemini-2.5-pro-preview-03-25")
        super().__init__(apiKey=apiKey or "dummy", baseUrl=baseUrl, model=model)

class VLLMProvider(BaseOpenAIProvider):
    def __init__(self, baseUrl: str = None, apiKey: str = None, model: str = None):
        baseUrl = baseUrl or os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        model = model or os.getenv("LLM_MODEL", "llama-2-7b") 
        apiKey = apiKey or os.getenv("VLLM_API_KEY", "EMPTY") 
        super().__init__(apiKey=apiKey, baseUrl=baseUrl, model=model)

class MockProvider:
    def __init__(self):
        self.model = "mock-model"
        
    async def generateResponse(self, messages: List[Dict], stream: bool = False):
        mockText = "This is a mock response. Please configure a valid LLM_PROVIDER in settings."
        if stream:
            async def generator():
                for word in mockText.split():
                    import asyncio
                    yield word + " "
                    await asyncio.sleep(0.05)
            return generator()
        return mockText

    @property
    def modelName(self) -> str:
        return self.model


class LLMInferenceService:
    def __init__(self):
        self.providerName = os.getenv("LLM_PROVIDER", "gemini").lower()
        self.provider = self.getProvider()
        logger.info(f"LLM Service initialized with provider: {self.providerName} (Model: {self.provider.modelName})")

    def getProvider(self):
        try:
            if self.providerName == "openai":
                return OpenAIProvider()
            elif self.providerName == "gemini":
                return GeminiProvider()
            elif self.providerName == "ollama":
                return OllamaProvider()
            elif self.providerName == "vllm":
                return VLLMProvider()
            else:
                logger.warning(f"Unknown provider '{self.providerName}', falling back to Mock.")
                return MockProvider()
        except Exception as e:
            logger.error(f"Failed to initialize provider {self.providerName}: {e}")
            return MockProvider()

    @property
    def model(self) -> str:
        return self.provider.modelName

    async def generateResponse(self, messages: List[Dict], stream: bool = False):
        """Generate response from LLM"""
        return await self.provider.generateResponse(messages, stream)
        
    async def streamResponse(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        streamGen = await self.generateResponse(messages, stream=True)
        async for chunk in streamGen:
             yield chunk

    # Backward compat alias
    async def _stream_response(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        async for chunk in self.streamResponse(messages):
            yield chunk

llm_provider = LLMInferenceService()
