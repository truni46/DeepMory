from __future__ import annotations

from langchain_core.messages import BaseMessage


def extractLastAIContent(messages: list) -> str:
    """Extract content from the last AIMessage in a message list."""
    for msg in reversed(messages):
        if getattr(msg, "type", None) == "ai" and msg.content:
            return msg.content
    return ""


def extractConversationContext(messages: list[BaseMessage], maxMessages: int = 20) -> list[BaseMessage]:
    """Extract original conversation messages (human/ai only, no tool messages).

    Filters out tool-related messages from the react agent loop
    to preserve the actual conversation context for sub-agents.
    """
    conversationMessages = []
    for msg in messages:
        msgType = getattr(msg, "type", "")
        if msgType in ("human", "ai") and not _isToolRelated(msg):
            conversationMessages.append(msg)
    if len(conversationMessages) > maxMessages:
        return conversationMessages[:maxMessages]
    return conversationMessages


def _isToolRelated(msg: BaseMessage) -> bool:
    """Check if an AI message is a tool call (not a real conversation message)."""
    if getattr(msg, "type", "") == "ai":
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            return True
    return False
