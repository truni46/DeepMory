from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from common.deps import getCurrentUser
from config.logger import logger
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.repository import agentRepository
from modules.agents.service import agentService

router = APIRouter(prefix="/agents", tags=["agents"])


class CreateTaskRequest(BaseModel):
    goal: str
    conversationId: Optional[str] = None
    projectId: Optional[str] = None


@router.post("/tasks")
async def createTask(body: CreateTaskRequest, currentUser=Depends(getCurrentUser)):
    try:
        task = await agentService.createTask(
            userId=str(currentUser["id"]),
            goal=body.goal,
            conversationId=body.conversationId,
            projectId=body.projectId,
        )
        return task
    except Exception as e:
        logger.error(f"POST /agents/tasks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def listTasks(currentUser=Depends(getCurrentUser)):
    try:
        return await agentService.listTasks(userId=str(currentUser["id"]))
    except Exception as e:
        logger.error(f"GET /agents/tasks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{taskId}")
async def getTask(taskId: str, currentUser=Depends(getCurrentUser)):
    try:
        task = await agentService.getTask(taskId, str(currentUser["id"]))
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /agents/tasks/{taskId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{taskId}")
async def cancelTask(taskId: str, currentUser=Depends(getCurrentUser)):
    try:
        success = await agentService.cancelTask(taskId, str(currentUser["id"]))
        return {"cancelled": success}
    except Exception as e:
        logger.error(f"DELETE /agents/tasks/{taskId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{taskId}/stream")
async def streamTask(taskId: str, currentUser=Depends(getCurrentUser)):
    try:
        return StreamingResponse(
            agentService.streamTask(taskId, str(currentUser["id"])),
            media_type="text/event-stream",
        )
    except Exception as e:
        logger.error(f"GET /agents/tasks/{taskId}/stream failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories")
async def listMemories(currentUser=Depends(getCurrentUser)):
    try:
        return await agentRepository.listMemories(str(currentUser["id"]))
    except Exception as e:
        logger.error(f"GET /agents/memories failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memories/{memoryId}")
async def deleteMemory(memoryId: str, currentUser=Depends(getCurrentUser)):
    try:
        success = await agentRepository.deleteMemory(memoryId, str(currentUser["id"]))
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE /agents/memories/{memoryId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
