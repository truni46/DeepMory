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
    def __init__(self, APIKey: str, baseUrl: str, model: str):
        self.client = AsyncOpenAI(api_key=APIKey, base_url=baseUrl)
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
            raise e

    async def streamResponse(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True
            )
            async for chunk in stream:
                print(f"Chunk: {chunk}")
                if chunk.choices:
                    content = chunk.choices[0].delta.content
                    if content:
                        import asyncio
                        step = 4
                        for i in range(0, len(content), step):
                            yield content[i:i+step]
                            await asyncio.sleep(0.02)
        except Exception as e:
            logger.error(f"LLM Streaming error ({self.model}): {e}")
            raise e
            
    @property
    def modelName(self) -> str:
        return self.model

class OllamaProvider(BaseOpenAIProvider):
    def __init__(self, baseUrl: str = None, model: str = None):
        baseUrl = baseUrl or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        model = model or os.getenv("LLM_MODEL", "kamekichi128/qwen3-4b-instruct-2507") 
        super().__init__(APIKey="ollama", baseUrl=baseUrl, model=model)

class OpenAIProvider(BaseOpenAIProvider):
    def __init__(self, APIKey: str = None, model: str = None):
        APIKey = APIKey or os.getenv("OPENAI_API_KEY")
        model = model or os.getenv("LLM_MODEL", "gpt-3.5-turbo")
        super().__init__(APIKey=APIKey or "dummy", baseUrl="https://api.openai.com/v1", model=model)

class GeminiProvider(BaseOpenAIProvider):
    def __init__(self, APIKey: str = None, model: str = None):
        APIKey = APIKey or os.getenv("GEMINI_API_KEY")
        baseUrl = "https://generativelanguage.googleapis.com/v1beta/openai/"
        model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        super().__init__(APIKey=APIKey or "dummy", baseUrl=baseUrl, model=model)

class GeminiNativeProvider:
    def __init__(self, APIKey: str = None, model: str = None):
        self.api_key = APIKey or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "gemini-2.5-flash")
        
    @property
    def modelName(self) -> str:
        return self.model

    def _convert_messages(self, messages: List[Dict]) -> Dict:
        payload = {"contents": [], "generationConfig": {"temperature": 0.7}}
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                payload["systemInstruction"] = {"parts": [{"text": content}]}
            else:
                gemini_role = "model" if role == "assistant" else "user"
                # Gemini doesn't allow multiple adjacent identical roles easily, but we trust the format for now
                payload["contents"].append({"role": gemini_role, "parts": [{"text": content}]})
        return payload

    async def generateResponse(self, messages: List[Dict], stream: bool = False):
        try:
            if stream:
                return self.streamResponse(messages)
            
            import httpx
            payload = self._convert_messages(messages)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=60.0)
                if resp.status_code != 200:
                    raise Exception(f"Gemini API error ({resp.status_code}): {resp.text}")
                
                data = resp.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
                return ""
        except Exception as e:
            logger.error(f"LLM Provider ({self.model}) error: {e}")
            raise e

    async def streamResponse(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        import httpx
        import json
        payload = self._convert_messages(messages)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?key={self.api_key}&alt=sse"
        
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise Exception(f"Gemini API stream error ({response.status_code}): {error_text.decode('utf-8')}")
                        
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data = json.loads(data_str)
                                if "candidates" in data and len(data["candidates"]) > 0:
                                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                                    if parts:
                                        content = parts[0].get("text", "")
                                        if content:
                                            # Yield content immediately without manual delay to avoid UI freeze/glitches 
                                            yield content
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            logger.error(f"LLM Streaming error ({self.model}): {e}")
            raise e

class VLLMProvider(BaseOpenAIProvider):
    def __init__(self, baseUrl: str = None, APIKey: str = None, model: str = None):
        baseUrl = baseUrl or os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
        model = model or os.getenv("LLM_MODEL", "llama-2-7b") 
        APIKey = APIKey or os.getenv("VLLM_API_KEY", "EMPTY") 
        super().__init__(APIKey=APIKey, baseUrl=baseUrl, model=model)

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
            elif self.providerName == "gemini_native":
                return GeminiNativeProvider()
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

llmProvider = LLMInferenceService()
