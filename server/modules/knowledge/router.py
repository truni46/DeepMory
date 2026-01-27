from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
from typing import List, Optional
from common.deps import get_current_user
from modules.knowledge.service import document_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    project_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    try:
        doc = await document_service.upload_document(
            user_id=str(current_user['id']),
            project_id=project_id,
            file_obj=file,
            filename=file.filename
        )
        return doc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents")
async def get_documents(
    current_user: dict = Depends(get_current_user)
):
    try:
        return await document_service.get_user_documents(user_id=str(current_user['id']))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        success = await document_service.delete_document(
            user_id=str(current_user['id']),
            document_id=document_id
        )
        if not success:
            raise HTTPException(status_code=404, detail="Document not found or unauthorized")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
