from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
from pydantic import BaseModel
import time
import json

from services.message_service import message_service
from services.conversation_service import conversation_service
from services.history_service import history_service
from services.settings_service import settings_service
from services.export_service import export_service
from config.database import db
from config.logger import logger

router = APIRouter(prefix="/api")


# ============ Request Models ============

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    metadata: Optional[dict] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    metadata: Optional[dict] = None


class MessageRequest(BaseModel):
    message: str
    conversationId: str


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 50


# ============ Middleware for API Logging ============

@router.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=False)
async def log_requests(request: Request, path_name: str):
    """Middleware to log all API requests"""
    start_time = time.time()
    
    # This won't actually handle requests, just log them
    # The actual endpoint handlers below will process requests
    
    return None


# ============ Health & Status ============

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    import psutil
    return {
        "status": "ok",
        "timestamp": time.time(),
        "uptime": time.time()  # Replace with actual uptime tracking
    }


@router.get("/db-status")
async def database_status():
    """Database connection status"""
    try:
        is_connected = await db.check_connection()
        return {
            "database": "connected" if is_connected else "disconnected",
            "type": "PostgreSQL" if db.use_database else "JSON File",
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Conversations ============

@router.get("/conversations")
async def get_conversations():
    """Get all conversations"""
    try:
        conversations = await conversation_service.get_all_conversations()
        return conversations
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")


@router.post("/conversations", status_code=201)
async def create_conversation(data: ConversationCreate):
    """Create new conversation"""
    try:
        conversation = await conversation_service.create_conversation(
            title=data.title,
            metadata=data.metadata
        )
        return conversation
    except Exception as e:
        logger.error(f"Error creating conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation by ID"""
    try:
        conversation = await conversation_service.get_conversation_by_id(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversation")


@router.put("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, data: ConversationUpdate):
    """Update conversation"""
    try:
        updates = {}
        if data.title is not None:
            updates['title'] = data.title
        if data.metadata is not None:
            updates['metadata'] = data.metadata
        
        conversation = await conversation_service.update_conversation(conversation_id, updates)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to update conversation")


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete conversation"""
    try:
        success = await conversation_service.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")


# ============ Messages ============

@router.post("/messages")
async def send_message(data: MessageRequest):
    """Send message (non-streaming)"""
    try:
        # Validate message
        validation = message_service.validate_message(data.message)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail={"errors": validation['errors']})
        
        # Get conversation history
        history = await history_service.get_chat_history(data.conversationId)
        
        # Process message
        result = await message_service.process_message(data.message, data.conversationId, history)
        
        # Save messages
        await history_service.save_message(data.conversationId, 'user', data.message)
        await history_service.save_message(
            data.conversationId, 
            'assistant', 
            result['aiResponse'],
            result['metadata']
        )
        
        return {
            "response": result['aiResponse'],
            "messageId": result['id'],
            "timestamp": result['timestamp']
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages/stream")
async def send_message_stream(data: MessageRequest):
    """Send message with Server-Sent Events streaming"""
    try:
        # Validate message
        validation = message_service.validate_message(data.message)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail={"errors": validation['errors']})
        
        # Get conversation history
        history = await history_service.get_chat_history(data.conversationId)
        
        # Save user message
        await history_service.save_message(data.conversationId, 'user', data.message)
        
        # Stream response
        async def event_generator():
            full_response = ""
            try:
                async for chunk in message_service.generate_streaming_response(data.message, history):
                    full_response += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                
                # Save assistant message
                await history_service.save_message(data.conversationId, 'assistant', full_response)
                
                # Send completion event
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ History ============

@router.get("/history/{conversation_id}")
async def get_history(conversation_id: str, limit: int = 100, offset: int = 0):
    """Get chat history for a conversation"""
    try:
        messages = await history_service.get_chat_history(conversation_id, limit, offset)
        return messages
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch history")


@router.post("/history/search")
async def search_history(data: SearchRequest):
    """Search messages"""
    try:
        messages = await history_service.search_messages(data.query, data.limit)
        return messages
    except Exception as e:
        logger.error(f"Error searching messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to search messages")


@router.delete("/history/messages/{message_id}")
async def delete_message(message_id: str):
    """Delete a message"""
    try:
        success = await history_service.delete_message(message_id)
        if success:
            return {"message": "Message deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Message not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting message: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete message")


# ============ Settings ============

@router.get("/settings")
async def get_settings():
    """Get all settings"""
    try:
        settings = await settings_service.get_all_settings()
        return settings
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch settings")


@router.put("/settings")
async def update_settings(updates: dict):
    """Update settings"""
    try:
        settings = await settings_service.update_settings(updates)
        return settings
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update settings")


@router.post("/settings/reset")
async def reset_settings():
    """Reset settings to defaults"""
    try:
        settings = await settings_service.reset_settings()
        return settings
    except Exception as e:
        logger.error(f"Error resetting settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset settings")


# ============ Export ============

@router.get("/export/{conversation_id}")
async def export_conversation(conversation_id: str, format: str = "json"):
    """Export conversation"""
    try:
        if format == "txt":
            data = await export_service.export_as_text(conversation_id)
            return StreamingResponse(
                iter([data]),
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=conversation-{conversation_id}.txt"}
            )
        elif format == "md":
            data = await export_service.export_as_markdown(conversation_id)
            return StreamingResponse(
                iter([data]),
                media_type="text/markdown",
                headers={"Content-Disposition": f"attachment; filename=conversation-{conversation_id}.md"}
            )
        else:  # json
            data = await export_service.export_as_json(conversation_id)
            return JSONResponse(
                content=data,
                headers={"Content-Disposition": f"attachment; filename=conversation-{conversation_id}.json"}
            )
    except Exception as e:
        logger.error(f"Error exporting conversation: {e}")
        raise HTTPException(status_code=500, detail="Failed to export conversation")


@router.get("/export/all")
async def export_all_conversations(format: str = "json"):
    """Export all conversations"""
    try:
        data = await export_service.export_all_conversations(format)
        
        if format == "txt":
            filename = "all-conversations.txt"
            media_type = "text/plain"
        elif format == "md":
            filename = "all-conversations.md"
            media_type = "text/markdown"
        else:
            filename = "all-conversations.json"
            media_type = "application/json"
            if isinstance(data, (list, dict)):
                data = json.dumps(data, indent=2)
        
        return StreamingResponse(
            iter([data if isinstance(data, str) else json.dumps(data, indent=2)]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        logger.error(f"Error exporting all conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to export conversations")
