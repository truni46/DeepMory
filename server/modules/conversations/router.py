from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from modules.conversations.service import conversationService
from common.deps import getCurrentUser
from schemas import ConversationCreate, ConversationUpdate

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("")
async def getConversations(user: Dict = Depends(getCurrentUser)):
    return await conversationService.getConversations(str(user['id']))

@router.post("", status_code=201)
async def createConversation(data: ConversationCreate, user: Dict = Depends(getCurrentUser)):
    return await conversationService.createConversation(str(user['id']), data.title, data.projectId)

@router.get("/{conversationId}")
async def getConversation(conversationId: str, user: Dict = Depends(getCurrentUser)):
    conv = await conversationService.getConversation(conversationId, str(user['id']))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.patch("/{conversationId}")
async def updateConversation(
    conversationId: str, 
    data: ConversationUpdate, 
    user: Dict = Depends(getCurrentUser)
):
    updates = data.dict(exclude_unset=True)
    updatedConv = await conversationService.updateConversation(conversationId, str(user['id']), updates)
    if not updatedConv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return updatedConv

@router.delete("/{conversationId}", status_code=204)
async def deleteConversation(conversationId: str, user: Dict = Depends(getCurrentUser)):
    success = await conversationService.deleteConversation(conversationId, str(user['id']))
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None
