from fastapi import APIRouter, HTTPException, Depends
from typing import Dict
from modules.conversations.service import conversation_service
from common.deps import get_current_user
from schemas import ConversationCreate, ConversationUpdate

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("")
async def get_conversations(user: Dict = Depends(get_current_user)):
    return await conversation_service.get_user_conversations(str(user['id']))

@router.post("", status_code=201)
async def create_conversation(data: ConversationCreate, user: Dict = Depends(get_current_user)):
    return await conversation_service.create_conversation(str(user['id']), data.title, data.project_id)

@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str, user: Dict = Depends(get_current_user)):
    conv = await conversation_service.get_conversation(conversation_id, str(user['id']))
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv

@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: str, 
    data: ConversationUpdate, 
    user: Dict = Depends(get_current_user)
):
    updates = data.dict(exclude_unset=True)
    updated_conv = await conversation_service.update_conversation(conversation_id, str(user['id']), updates)
    
    if not updated_conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return updated_conv

@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, user: Dict = Depends(get_current_user)):
    success = await conversation_service.delete_conversation(conversation_id, str(user['id']))
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return None
