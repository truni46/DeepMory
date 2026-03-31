from __future__ import annotations

import json
from typing import Any, AsyncIterator, List, Optional, Sequence

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolCall
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import BaseTool

from config.logger import logger
from modules.llm.llmProvider import llmProvider


def _toDict(message: BaseMessage) -> dict:
    roleMap = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
    return {"role": roleMap.get(message.type, message.type), "content": str(message.content)}


def _toolToOpenAI(tool: BaseTool) -> dict:
    """Convert a LangChain BaseTool to OpenAI function schema."""
    schema = tool.args_schema.model_json_schema() if tool.args_schema else {"type": "object", "properties": {}}
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


class DeepMoryLLM(BaseChatModel):
    """LangChain BaseChatModel adapter wrapping the existing llmProvider singleton."""

    @property
    def _llm_type(self) -> str:
        return "deepmory"

    def bind_tools(self, tools: Sequence[BaseTool], **kwargs: Any) -> "DeepMoryLLM":
        """Bind tools as OpenAI-compatible function schemas."""
        toolSchemas = [_toolToOpenAI(t) for t in tools]
        return self.bind(tools=toolSchemas, **kwargs)

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
        """Non-streaming — used by Supervisor and sub-agent nodes."""
        try:
            dicts = [_toDict(m) for m in messages]
            tools = kwargs.get("tools")
            result = await llmProvider.generateResponse(dicts, stream=False, tools=tools)
            if result is None or isinstance(result, str):
                content = result or ""
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])
            # result is a message object with tool_calls
            toolCalls = []
            if hasattr(result, "tool_calls") and result.tool_calls:
                for tc in result.tool_calls:
                    toolCalls.append(ToolCall(
                        name=tc.function.name,
                        args=json.loads(tc.function.arguments or "{}"),
                        id=tc.id or "",
                    ))
            content = result.content or ""
            aiMsg = AIMessage(content=content, tool_calls=toolCalls)
            return ChatResult(generations=[ChatGeneration(message=aiMsg)])
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
