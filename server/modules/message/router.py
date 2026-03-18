from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict
from modules.message.service import messageService
from common.deps import get_current_user
from schemas import MessageRequest
from config.logger import logger
import json

router = APIRouter(prefix="/messages", tags=["Messages"])

@router.get("/{conversationId}")
async def getConversationHistory(conversationId: str, user: Dict = Depends(get_current_user)):
    return await messageService.getHistory(conversationId)

@router.post("/chat/completions")
async def sendMessageStream(data: MessageRequest, user: Dict = Depends(get_current_user)):
    try:
        validation = messageService.validateMessage(data.message)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail={"errors": validation['errors']})
        
        async def eventGenerator():
            fullResponse = ""
            try:
                async for chunk in messageService.processMessageFlow(
                    str(user['id']), 
                    data.conversationId, 
                    data.message, 
                    data.projectId
                ):
                    fullResponse += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
                yield f"data: {json.dumps({'done': True, 'fullResponse': fullResponse})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            eventGenerator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        logger.error(f"Error streaming message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
