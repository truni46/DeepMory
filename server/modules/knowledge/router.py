# server/modules/knowledge/router.py
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from common.deps import getCurrentUser
from config.logger import logger
from modules.knowledge.service import documentService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents/upload")
async def uploadDocuments(
    files: List[UploadFile] = File(...),
    scope: str = Query(default="personal"),
    ownerId: Optional[str] = Query(default=None),
    ownerType: str = Query(default="user"),
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        userId = str(currentUser["id"])
        results = await documentService.uploadDocuments(
            userId=userId,
            files=files,
            scope=scope,
            ownerId=ownerId or userId,
            ownerType=ownerType,
        )
        return results
    except Exception as e:
        logger.error(f"POST /knowledge/documents/upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def getDocuments(
    scope: Optional[str] = Query(default=None),
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        return await documentService.getDocuments(
            userId=str(currentUser["id"]), scope=scope
        )
    except Exception as e:
        logger.error(f"GET /knowledge/documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{documentId}/file")
async def serveDocumentFile(
    documentId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        doc = await documentService.getDocument(documentId, str(currentUser["id"]))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        filePath = doc["filePath"]
        if not os.path.exists(filePath):
            raise HTTPException(status_code=404, detail="File not found on disk")
        return FileResponse(
            path=filePath,
            filename=doc["filename"],
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /knowledge/documents/{documentId}/file failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{documentId}")
async def getDocument(
    documentId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        doc = await documentService.getDocument(documentId, str(currentUser["id"]))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /knowledge/documents/{documentId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{documentId}")
async def deleteDocument(
    documentId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        success = await documentService.deleteDocument(
            userId=str(currentUser["id"]),
            documentId=documentId,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE /knowledge/documents/{documentId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/documents/{documentId}")
async def updateDocument(
    documentId: str,
    payload: dict,
    currentUser: dict = Depends(getCurrentUser),
):
    raise HTTPException(status_code=501, detail="Not implemented")
