from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict
from modules.messages.service import message_service
from common.deps import get_current_user
from schemas import MessageRequest
from config.logger import logger
import json

router = APIRouter(prefix="/messages", tags=["Messages"])

@router.get("/{conversation_id}")
async def get_conversation_history(conversation_id: str, user: Dict = Depends(get_current_user)):
    # Optional: Verify conversation ownership
    return await message_service.get_history(conversation_id)

@router.post("/stream")
async def send_message_stream(data: MessageRequest, user: Dict = Depends(get_current_user)):
    try:
        # Validate message
        validation = message_service.validate_message(data.message)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail={"errors": validation['errors']})
        
        async def event_generator():
            full_response = ""
            try:
                # Stream usage
                async for chunk in message_service.process_message_flow(
                    str(user['id']), 
                    data.conversationId, 
                    data.message, 
                    data.projectId
                ):
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
                yield f"data: {json.dumps({'done': True, 'fullResponse': full_response})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        logger.error(f"Error streaming message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
