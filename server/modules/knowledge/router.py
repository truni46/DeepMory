from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
from common.deps import get_current_user
from modules.knowledge.service import documentService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.post("/upload")
async def uploadDocument(
    file: UploadFile = File(...),
    projectId: Optional[str] = None,
    currentUser: dict = Depends(get_current_user)
):
    try:
        doc = await documentService.uploadDocument(
            userId=str(currentUser['id']),
            fileObj=file,
            filename=file.filename,
            projectId=projectId,
        )
        return doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents")
async def getDocuments(
    currentUser: dict = Depends(get_current_user)
):
    try:
        return await documentService.getUserDocuments(userId=str(currentUser["id"]))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{documentId}")
async def deleteDocument(
    documentId: str,
    currentUser: dict = Depends(get_current_user)
):
    try:
        success = await documentService.deleteDocument(
            userId=str(currentUser['id']),
            documentId=documentId
        )
        if not success:
            raise HTTPException(status_code=404, detail="Document not found or unauthorized")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
