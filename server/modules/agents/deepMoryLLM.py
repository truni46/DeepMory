from __future__ import annotations

from typing import Any, AsyncIterator, Iterator, List, Optional

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from config.logger import logger
from modules.llm.llmProvider import llmProvider


def _toDict(message: BaseMessage) -> dict:
    roleMap = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
    return {"role": roleMap.get(message.type, message.type), "content": str(message.content)}


class DeepMoryLLM(BaseChatModel):
    """LangChain BaseChatModel adapter wrapping the existing llmProvider singleton."""

    @property
    def _llm_type(self) -> str:
        return "deepmory"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("Use async _agenerate instead.")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Non-streaming — used by the Supervisor node."""
        try:
            dicts = [_toDict(m) for m in messages]
            result = await llmProvider.generateResponse(dicts, stream=False)
            if not isinstance(result, str):
                chunks = []
                async for chunk in result:
                    chunks.append(chunk)
                result = "".join(chunks)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=result))])
        except Exception as e:
            logger.error(f"DeepMoryLLM._agenerate failed: {e}")
            raise

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Streaming — used by sub-agent nodes."""
        try:
            dicts = [_toDict(m) for m in messages]
            async for chunk in llmProvider.streamResponse(dicts):
                yield ChatGenerationChunk(message=AIMessage(content=chunk))
        except Exception as e:
            logger.error(f"DeepMoryLLM._astream failed: {e}")
            raise


deepMoryLLM = DeepMoryLLM()
