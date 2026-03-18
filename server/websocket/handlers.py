import socketio
from modules.message.service import messageService
from modules.memory.historyService import historyService
from config.logger import logger
from datetime import datetime

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
        conversationId = data.get('conversationId')
        
        logger.chat(f"WebSocket message received from {sid}: conversation={conversationId}")
        
        validation = messageService.validateMessage(message)
        if not validation['valid']:
            await sio.emit('error', {'message': '; '.join(validation['errors'])}, room=sid)
            return
        
        await sio.emit('typing', {'isTyping': True}, room=sid)
        
        history = await historyService.getChatHistory(conversationId)
        await historyService.saveMessage(conversationId, 'user', message)
        
        response = await messageService.generateAiResponse(message, history)
        await historyService.saveMessage(conversationId, 'assistant', response)
        
        await sio.emit('typing', {'isTyping': False}, room=sid)
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
        conversationId = data.get('conversationId')
        
        logger.chat(f"WebSocket streaming message received from {sid}: conversation={conversationId}")
        
        validation = messageService.validateMessage(message)
        if not validation['valid']:
            await sio.emit('error', {'message': '; '.join(validation['errors'])}, room=sid)
            return
        
        await sio.emit('typing', {'isTyping': True}, room=sid)
        
        history = await historyService.getChatHistory(conversationId)
        await historyService.saveMessage(conversationId, 'user', message)
        
        fullResponse = ""
        async for chunk in messageService.generateStreamingResponse(message, history, conversationId=conversationId):
            fullResponse += chunk
            await sio.emit('messageChunk', {'chunk': chunk}, room=sid)
        
        await historyService.saveMessage(conversationId, 'assistant', fullResponse)
        
        await sio.emit('messageComplete', {
            'fullResponse': fullResponse,
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
    isTyping = data.get('isTyping', False)
    await sio.emit('userTyping', {
        'socketId': sid,
        'isTyping': isTyping
    }, skip_sid=sid)
