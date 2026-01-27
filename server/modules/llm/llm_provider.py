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
            logger.error(f"LLM Provider error: {e}")
            return f"Error from LLM provider: {str(e)}"

    async def _stream_response(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"LLM Streaming error: {e}")
            yield f"Error streaming response: {str(e)}"
            
    @property
    def model_name(self) -> str:
        return self.model

class OllamaProvider(BaseOpenAIProvider):
    def __init__(self):
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        model = os.getenv("LLM_MODEL", "mistral") # Default to mistral for Ollama
        # Api key is required by client but ignored by Ollama
        super().__init__(api_key="ollama", base_url=base_url, model=model)

class OpenAIProvider(BaseOpenAIProvider):
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI Provider")
        model = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        super().__init__(api_key=api_key, base_url="https://api.openai.com/v1", model=model)

class GeminiProvider(BaseOpenAIProvider):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
             raise ValueError("GEMINI_API_KEY is required for Gemini Provider")
        # Google Gemini via OpenAI Compat endpoint
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = os.getenv("LLM_MODEL", "gemini-pro")
        super().__init__(api_key=api_key, base_url=base_url, model=model)

class VLLMProvider(BaseOpenAIProvider):
    def __init__(self):
        base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        model = os.getenv("LLM_MODEL", "llama-2-7b") 
        # API key might be optional or required depending on vLLM cleanup
        api_key = os.getenv("VLLM_API_KEY", "EMPTY") 
        super().__init__(api_key=api_key, base_url=base_url, model=model)

class MockProvider:
    def __init__(self):
        self.model = "mock-model"
        
    async def generate_response(self, messages: List[Dict], stream: bool = False):
        mock_text = "This is a mock response. Please configure a valid LLM_PROVIDER (ollama, openai, gemini)."
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
