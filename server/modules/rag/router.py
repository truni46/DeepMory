from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from config.logger import logger
from common.deps import getCurrentUser
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
    currentUser: dict = Depends(getCurrentUser),
):
    """Search a project's knowledge collection via LightRAG."""
    try:
        results = await ragService.searchContext(
            body.query, body.projectId, body.limit, body.rerank,
            mode=body.mode.value if body.mode else None,
        )
        return [
            {"id": r.document.id, "content": r.document.content, "score": r.score, "metadata": r.document.metadata}
            for r in results
        ]
    except Exception as e:
        logger.error(f"Endpoint /rag/search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/search")
async def searchMemory(
    body: MemorySearchRequest,
    currentUser: dict = Depends(getCurrentUser),
):
    """Search the current user's long-term memory via LightRAG."""
    try:
        userId = str(currentUser["id"])
        results = await ragService.searchMemoryVectors(userId, body.query, body.limit)
        return [
            {"id": r.document.id, "content": r.document.content, "score": r.score}
            for r in results
        ]
    except Exception as e:
        logger.error(f"Endpoint /rag/memory/search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{projectId}/{documentId}")
async def deleteDocumentChunks(
    projectId: str,
    documentId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    """Remove all data for a document from its project's LightRAG instance."""
    try:
        await ragService.deleteDocumentChunks(projectId, documentId)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Endpoint /rag/documents delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
