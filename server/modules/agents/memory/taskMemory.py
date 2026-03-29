from __future__ import annotations

import os
from typing import Any, AsyncIterator, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

from common.cacheService import cacheService
from config.logger import logger

_TTL = int(os.getenv("AGENT_CHECKPOINT_TTL", str(24 * 3600)))


class RedisCheckpointer(BaseCheckpointSaver):
    """LangGraph checkpoint saver backed by cacheService (Redis)."""

    @staticmethod
    def _latestKey(threadId: str) -> str:
        return f"agent:checkpoint:{threadId}:latest"

    @staticmethod
    def _stepKey(threadId: str, checkpointId: str) -> str:
        return f"agent:checkpoint:{threadId}:{checkpointId}"

    @staticmethod
    def _messagesKey(taskId: str) -> str:
        return f"agent:task:{taskId}:messages"

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        raise NotImplementedError("Use async aget_tuple")

    def list(self, config: Optional[RunnableConfig], **kwargs: Any):
        raise NotImplementedError("Use async alist")

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        raise NotImplementedError("Use async aput")

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        try:
            threadId = config["configurable"].get("thread_id", "unknown")
            data = await cacheService.get(self._latestKey(threadId))
            if not data or not isinstance(data, dict):
                return None
            return CheckpointTuple(
                config=config,
                checkpoint=data,
                metadata={},
                parent_config=None,
                pending_writes=None,
            )
        except Exception as e:
            logger.error(
                f"RedisCheckpointer.aget_tuple failed threadId={config.get('configurable', {}).get('thread_id')}: {e}"
            )
            return None

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        try:
            threadId = config["configurable"].get("thread_id", "unknown")
            checkpointId = checkpoint.get("id", "step") if isinstance(checkpoint, dict) else str(id(checkpoint))
            payload = checkpoint if isinstance(checkpoint, dict) else dict(checkpoint)
            await cacheService.set(self._latestKey(threadId), payload, expire=_TTL)
            await cacheService.set(self._stepKey(threadId, str(checkpointId)), payload, expire=_TTL)
            return config
        except Exception as e:
            logger.error(
                f"RedisCheckpointer.aput failed threadId={config.get('configurable', {}).get('thread_id')}: {e}"
            )
            return config

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        try:
            if config is None:
                return
            threadId = config["configurable"].get("thread_id", "unknown")
            data = await cacheService.get(self._latestKey(threadId))
            if data and isinstance(data, dict):
                yield CheckpointTuple(
                    config=config,
                    checkpoint=data,
                    metadata={},
                    parent_config=None,
                    pending_writes=None,
                )
        except Exception as e:
            logger.error(
                f"RedisCheckpointer.alist failed threadId={config.get('configurable', {}).get('thread_id') if config else 'None'}: {e}"
            )

    async def writeMessages(self, taskId: str, messages: list) -> None:
        """Write message list to Redis for sub-agent convenience reads."""
        try:
            serialized = [{"type": m.__class__.__name__, "content": str(m.content)} for m in messages]
            await cacheService.set(self._messagesKey(taskId), serialized, expire=_TTL)
        except Exception as e:
            logger.error(f"RedisCheckpointer.writeMessages failed taskId={taskId}: {e}")

    async def readMessages(self, taskId: str) -> list:
        """Read cached message list (convenience, not authoritative checkpoint)."""
        try:
            return await cacheService.get(self._messagesKey(taskId)) or []
        except Exception as e:
            logger.error(f"RedisCheckpointer.readMessages failed taskId={taskId}: {e}")
            return []


taskMemory = RedisCheckpointer()
