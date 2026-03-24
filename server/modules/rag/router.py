from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional

from common.deps import get_current_user
from modules.rag.ragService import ragService
from modules.rag.repository import SearchMode

router = APIRouter(prefix="/rag", tags=["rag"])


class SearchRequest(BaseModel):
    query: str
    projectId: str
    limit: int = 5
    mode: Optional[SearchMode] = None
    rerank: bool = False


class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 5


@router.post("/search")
async def searchKnowledge(
    body: SearchRequest,
    currentUser: dict = Depends(get_current_user),
):
    """Search a project's knowledge collection."""
    try:
        results = await ragService.searchContext(
            body.query, body.projectId, body.limit, body.rerank
        )
        return [
            {"id": r.document.id, "content": r.document.content, "score": r.score, "metadata": r.document.metadata}
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/search")
async def searchMemory(
    body: MemorySearchRequest,
    currentUser: dict = Depends(get_current_user),
):
    """Search the current user's long-term memory vectors."""
    try:
        userId = str(currentUser["id"])
        results = await ragService.searchMemoryVectors(userId, body.query, body.limit)
        return [
            {"id": r.document.id, "content": r.document.content, "score": r.score}
            for r in results
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{projectId}/{documentId}")
async def deleteDocumentChunks(
    projectId: str,
    documentId: str,
    currentUser: dict = Depends(get_current_user),
):
    """Remove all vector chunks for a document from its project collection."""
    try:
        await ragService.deleteDocumentChunks(projectId, documentId)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
