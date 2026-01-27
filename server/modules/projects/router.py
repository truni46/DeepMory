from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Dict
from modules.projects.service import project_service
from modules.knowledge.service import document_service
from common.deps import get_current_user
from schemas import ProjectCreate
from config.logger import logger

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("", status_code=201)
async def create_project(project: ProjectCreate, user: Dict = Depends(get_current_user)):
    try:
        new_project = await project_service.create_project(str(user['id']), project.name, project.description, project.config)
        return new_project
    except Exception as e:
        logger.error(f"Create project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")

@router.get("")
async def get_projects(user: Dict = Depends(get_current_user)):
    return await project_service.get_projects(str(user['id']))

@router.post("/{project_id}/documents")
async def upload_document(
    project_id: str, 
    file: UploadFile = File(...), 
    user: Dict = Depends(get_current_user)
):
    try:
        doc = await document_service.upload_document(str(user['id']), project_id, file, file.filename)
        return doc
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@router.get("/{project_id}/documents")
async def get_project_documents(project_id: str, user: Dict = Depends(get_current_user)):
    return await document_service.get_documents(project_id)
