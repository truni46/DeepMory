from typing import List, Dict, AsyncGenerator, Optional, Protocol
import os
from openai import AsyncOpenAI
from config.logger import logger

class LLMProvider(Protocol):
    async def generate_response(self, messages: List[Dict], stream: bool = False) -> str | AsyncGenerator[str, None]:
        ...
    
    @property
    def model_name(self) -> str:
        ...


# -------------------------------------------------------------
# Base & Concrete Providers
# -------------------------------------------------------------

class BaseOpenAIProvider:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def generate_response(self, messages: List[Dict], stream: bool = False):
        try:
            if stream:
                return self._stream_response(messages)
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

    async def _stream_response(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
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
    def model_name(self) -> str:
        return self.model

class OllamaProvider(BaseOpenAIProvider):
    def __init__(self, base_url: str = None, model: str = None):
        base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        model = model or os.getenv("LLM_MODEL", "qwen3:8b") 
        # API key is ignored by Ollama but required by client
        super().__init__(api_key="ollama", base_url=base_url, model=model)

class OpenAIProvider(BaseOpenAIProvider):
    def __init__(self, api_key: str = None, model: str = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            pass # Relaxed check for dynamic instantiation; will fail at call time if missing
        model = model or os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        super().__init__(api_key=api_key or "dummy", base_url="https://api.openai.com/v1", model=model)

class GeminiProvider(BaseOpenAIProvider):
    def __init__(self, api_key: str = None, model: str = None):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = model or "gemini-2.5-flash"
        super().__init__(api_key=api_key or "dummy", base_url=base_url, model=model)

class VLLMProvider(BaseOpenAIProvider):
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        base_url = base_url or os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        model = model or os.getenv("LLM_MODEL", "llama-2-7b") 
        api_key = api_key or os.getenv("VLLM_API_KEY", "EMPTY") 
        super().__init__(api_key=api_key, base_url=base_url, model=model)

class MockProvider:
    def __init__(self):
        self.model = "mock-model"
        
    async def generate_response(self, messages: List[Dict], stream: bool = False):
        mock_text = "This is a mock response. Please configure a valid LLM_PROVIDER in settings."
        if stream:
            async def generator():
                for word in mock_text.split():
                    import asyncio
                    yield word + " "
                    await asyncio.sleep(0.05)
            return generator()
        return mock_text

    @property
    def model_name(self) -> str:
        return self.model


# -------------------------------------------------------------
# LLM Service (Static Config)
# -------------------------------------------------------------
class LLMInferenceService:
    def __init__(self):
        self.provider_name = os.getenv("LLM_PROVIDER", "ollama").lower()
        self.provider = self._get_provider()
        logger.info(f"LLM Service initialized with provider: {self.provider_name} (Model: {self.provider.model_name})")

    def _get_provider(self):
        try:
            if self.provider_name == "openai":
                return OpenAIProvider()
            elif self.provider_name == "gemini":
                return GeminiProvider()
            elif self.provider_name == "ollama":
                return OllamaProvider()
            elif self.provider_name == "vllm":
                return VLLMProvider()
            else:
                logger.warning(f"Unknown provider '{self.provider_name}', falling back to Mock.")
                return MockProvider()
        except Exception as e:
            logger.error(f"Failed to initialize provider {self.provider_name}: {e}")
            return MockProvider()

    @property
    def model(self) -> str:
        return self.provider.model_name

    async def generate_response(self, messages: List[Dict], stream: bool = False):
        """Generate response from LLM"""
        return await self.provider.generate_response(messages, stream)
        
    # Compat helper for internal usage if needed
    async def _stream_response(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        stream_gen = await self.generate_response(messages, stream=True)
        async for chunk in stream_gen:
             yield chunk

llm_provider = LLMInferenceService()
