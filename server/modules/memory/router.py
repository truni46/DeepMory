from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from common.deps import getCurrentUser
from modules.memory.longTerm.repository import memoryRepository
from config.logger import logger

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryUpdateRequest(BaseModel):
    content: str


class MemorySettingsRequest(BaseModel):
    enabled: bool


@router.get("")
async def getMemories(currentUser: dict = Depends(getCurrentUser)):
    """Get all memories for the current user."""
    userId = str(currentUser["id"])
    memories = await memoryRepository.getByUser(userId, limit=200)
    return [
        {
            "id": m["id"],
            "content": m["content"],
            "createdAt": m.get("createdAt"),
        }
        for m in memories
    ]


@router.patch("/{memoryId}")
async def updateMemory(
    memoryId: str,
    body: MemoryUpdateRequest,
    currentUser: dict = Depends(getCurrentUser),
):
    """Update a memory's content (both SQL and vector)."""
    userId = str(currentUser["id"])
    from modules.memory.longTerm.repository import memoryRepository
    from modules.rag.ragService import ragService

    # Update SQL record
    existing = await memoryRepository.getById(memoryId)
    if not existing or str(existing.get("userId")) != userId:
        raise HTTPException(status_code=404, detail="Memory not found")

    from config.database import db
    if db.useDatabase and db.pool:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE memories SET content = $1 WHERE id = $2 AND "userId" = $3""",
                body.content, memoryId, userId,
            )
    else:
        import json
        data = db.read_json("memories")
        if memoryId in data:
            data[memoryId]["content"] = body.content
            db.write_json("memories", data)

    # Update vector
    try:
        await ragService.deleteMemoryVector(userId, memoryId)
        await ragService.upsertMemoryVector(userId, memoryId, body.content)
    except Exception as e:
        logger.warning(f"Failed to update memory vector for {memoryId}: {e}")

    return {"status": "success", "id": memoryId}


@router.delete("/{memoryId}")
async def deleteMemory(
    memoryId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    """Delete a memory (SQL + vector)."""
    userId = str(currentUser["id"])
    from modules.memory.service import memoryFacade

    success = await memoryFacade.deleteMemory(userId, memoryId)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "success"}


@router.get("/settings")
async def getMemorySettings(currentUser: dict = Depends(getCurrentUser)):
    """Get memory collection toggle state for this user."""
    import os
    enabled = os.getenv("MEMORY_EXTRACTION_ENABLED", "true").lower() == "true"
    return {"enabled": enabled}


@router.put("/settings")
async def updateMemorySettings(
    body: MemorySettingsRequest,
    currentUser: dict = Depends(getCurrentUser),
):
    """
    Toggle memory extraction on/off.
    In production this would be per-user in DB; for now we use env var as default.
    """
    import os
    os.environ["MEMORY_EXTRACTION_ENABLED"] = str(body.enabled).lower()
    return {"status": "success", "enabled": body.enabled}
