from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Dict
from modules.projects.service import projectService
from modules.knowledge.service import documentService
from common.deps import get_current_user
from schemas import ProjectCreate
from config.logger import logger

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("", status_code=201)
async def createProject(project: ProjectCreate, user: Dict = Depends(get_current_user)):
    try:
        newProject = await projectService.createProject(str(user['id']), project.name, project.description, project.config)
        return newProject
    except Exception as e:
        logger.error(f"Create project error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create project")

@router.get("")
async def getProjects(user: Dict = Depends(get_current_user)):
    return await projectService.getProjects(str(user['id']))

@router.post("/{projectId}/documents")
async def uploadDocument(
    projectId: str, 
    file: UploadFile = File(...), 
    user: Dict = Depends(get_current_user)
):
    try:
        doc = await documentService.uploadDocument(str(user['id']), file, file.filename, projectId)
        return doc
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@router.get("/{projectId}/documents")
async def getProjectDocuments(projectId: str, user: Dict = Depends(get_current_user)):
    return await documentService.getDocuments(projectId)
