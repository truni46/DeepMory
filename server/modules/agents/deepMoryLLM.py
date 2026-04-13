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
    """Convert a LangChain message to an OpenAI-compatible dict, preserving tool call fields."""
    roleMap = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
    d = {"role": roleMap.get(message.type, message.type), "content": str(message.content)}
    if hasattr(message, "tool_calls") and message.tool_calls:
        rawExtras = message.additional_kwargs.get("tool_call_extras", {})
        tcList = []
        for tc in message.tool_calls:
            entry = {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
            extra = rawExtras.get(tc["id"])
            if extra:
                entry["extra_content"] = extra
            tcList.append(entry)
        d["tool_calls"] = tcList
    if hasattr(message, "tool_call_id") and message.tool_call_id:
        d["tool_call_id"] = message.tool_call_id
    return d


def _cleanSchemaProps(propDef: dict) -> dict:
    """Flatten anyOf/nullable patterns and strip fields unsupported by Gemini."""
    cleaned = {}
    if "anyOf" in propDef:
        for option in propDef["anyOf"]:
            if option.get("type") != "null":
                cleaned["type"] = option.get("type", "string")
                if "items" in option:
                    cleaned["items"] = _cleanSchemaProps(option["items"])
                break
        if "type" not in cleaned:
            cleaned["type"] = "string"
    elif "type" in propDef:
        cleaned["type"] = propDef["type"]
    else:
        cleaned["type"] = "string"
    if "items" in propDef and "items" not in cleaned:
        cleaned["items"] = _cleanSchemaProps(propDef["items"])
    if "description" in propDef:
        cleaned["description"] = propDef["description"]
    if "enum" in propDef:
        cleaned["enum"] = propDef["enum"]
    if propDef.get("type") == "object" and "properties" in propDef:
        cleaned["properties"] = {k: _cleanSchemaProps(v) for k, v in propDef["properties"].items()}
    return cleaned


def _toolToOpenAI(tool: BaseTool) -> dict:
    """Convert a LangChain BaseTool to OpenAI function schema, cleaned for Gemini compatibility."""
    schema = tool.args_schema.model_json_schema() if tool.args_schema else {"type": "object", "properties": {}}
    cleanedParams = {"type": "object", "properties": {}}
    for propName, propDef in schema.get("properties", {}).items():
        cleanedParams["properties"][propName] = _cleanSchemaProps(propDef)
    required = schema.get("required")
    if required:
        cleanedParams["required"] = required
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": cleanedParams,
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
            toolCalls = []
            toolCallExtras = {}
            if hasattr(result, "tool_calls") and result.tool_calls:
                for tc in result.tool_calls:
                    tcId = tc.id or ""
                    toolCalls.append(ToolCall(
                        name=tc.function.name,
                        args=json.loads(tc.function.arguments or "{}"),
                        id=tcId,
                    ))
                    extra = getattr(tc, "extra_content", None)
                    if extra:
                        toolCallExtras[tcId] = extra if isinstance(extra, dict) else {"google": extra}
            content = result.content or ""
            additionalKwargs = {}
            if toolCallExtras:
                additionalKwargs["tool_call_extras"] = toolCallExtras
            aiMsg = AIMessage(content=content, tool_calls=toolCalls, additional_kwargs=additionalKwargs)
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
            # async for chunk in llmProvider.streamResponse(dicts):
                # yield ChatGenerationChunk(message=AIMessage(content=chunk))
        except Exception as e:
            logger.error(f"DeepMoryLLM._astream failed: {e}")
            raise


deepMoryLLM = DeepMoryLLM()
