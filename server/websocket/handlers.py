import socketio
from modules.messages.service import message_service
from modules.memory.history_service import history_service
from config.logger import logger

# Create Socket.IO server
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=False,
    engineio_logger=False
)


@sio.event
async def connect(sid, environ):
    """Handle client connection"""
    logger.info(f"Client connected via WebSocket: {sid}")
    await sio.emit('connected', {
        'message': 'Connected to AI Tutor server',
        'socketId': sid,
        'timestamp': str(datetime.now())
    }, room=sid)


@sio.event
async def disconnect(sid):
    """Handle client disconnection"""
    logger.info(f"Client disconnected: {sid}")


@sio.event
async def sendMessage(sid, data):
    """Handle incoming message from client"""
    try:
        message = data.get('message')
        conversation_id = data.get('conversationId')
        
        logger.chat(f"WebSocket message received from {sid}: conversation={conversation_id}")
        
        # Validate message
        validation = message_service.validate_message(message)
        if not validation['valid']:
            await sio.emit('error', {'message': '; '.join(validation['errors'])}, room=sid)
            return
        
        # Send typing indicator
        await sio.emit('typing', {'isTyping': True}, room=sid)
        
        # Get conversation history
        history = await history_service.get_chat_history(conversation_id)
        
        # Save user message
        await history_service.save_message(conversation_id, 'user', message)
        
        # Generate AI response
        response = await message_service.generate_ai_response(message, history)
        
        # Save assistant message
        await history_service.save_message(conversation_id, 'assistant', response)
        
        # Stop typing indicator
        await sio.emit('typing', {'isTyping': False}, room=sid)
        
        # Send response
        from datetime import datetime
        await sio.emit('receiveMessage', {
            'role': 'assistant',
            'content': response,
            'timestamp': str(datetime.now())
        }, room=sid)
        
    except Exception as e:
        logger.error(f"WebSocket message error: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)
        await sio.emit('typing', {'isTyping': False}, room=sid)


@sio.event
async def sendMessageStreaming(sid, data):
    """Handle streaming message request"""
    try:
        message = data.get('message')
        conversation_id = data.get('conversationId')
        
        logger.chat(f"WebSocket streaming message received from {sid}: conversation={conversation_id}")
        
        # Validate message
        validation = message_service.validate_message(message)
        if not validation['valid']:
            await sio.emit('error', {'message': '; '.join(validation['errors'])}, room=sid)
            return
        
        # Send typing indicator
        await sio.emit('typing', {'isTyping': True}, room=sid)
        
        # Get conversation history
        history = await history_service.get_chat_history(conversation_id)
        
        # Save user message
        await history_service.save_message(conversation_id, 'user', message)
        
        # Stream response
        full_response = ""
        async for chunk in message_service.generate_streaming_response(message, history):
            full_response += chunk
            await sio.emit('messageChunk', {'chunk': chunk}, room=sid)
        
        # Save assistant message
        await history_service.save_message(conversation_id, 'assistant', full_response)
        
        # Send completion
        from datetime import datetime
        await sio.emit('messageComplete', {
            'fullResponse': full_response,
            'timestamp': str(datetime.now())
        }, room=sid)
        
        await sio.emit('typing', {'isTyping': False}, room=sid)
        
    except Exception as e:
        logger.error(f"WebSocket streaming error: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)
        await sio.emit('typing', {'isTyping': False}, room=sid)


@sio.event
async def typing(sid, data):
    """Handle user typing indicator"""
    is_typing = data.get('isTyping', False)
    await sio.emit('userTyping', {
        'socketId': sid,
        'isTyping': is_typing
    }, skip_sid=sid)


# Import datetime for timestamps
from datetime import datetime
