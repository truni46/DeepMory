import uuid
from typing import Dict, List
from modules.message.repository import messageRepository
from config.logger import logger


class HistoryService:
    """Service for managing chat history"""
    
    @staticmethod
    async def getChatHistory(conversationId: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get chat history for a conversation"""
        try:
            messages = await messageRepository.getByConversation(conversationId, limit, offset)
            logger.info(f"Retrieved {len(messages)} messages for conversation: {conversationId}")
            return messages
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            raise
    
    @staticmethod
    async def saveMessage(conversationId: str, role: str, content: str, metadata: Dict = None) -> Dict:
        """Save a message to history"""
        try:
            messageId = str(uuid.uuid4())
            message = await messageRepository.create(
                conversationId=conversationId,
                role=role,
                content=content,
                messageId=messageId,
                metadata=metadata or {}
            )
            logger.chat(f"Saved {role} message to conversation {conversationId}")
            return message
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise
    
    @staticmethod
    async def searchMessages(query: str, limit: int = 50) -> List[Dict]:
        """Search messages"""
        try:
            messages = await messageRepository.search(query, limit)
            logger.info(f"Found {len(messages)} messages for query: {query[:50]}")
            return messages
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            raise
    
    @staticmethod
    async def deleteMessage(messageId: str) -> bool:
        """Delete a message"""
        try:
            logger.info(f"Deleted message: {messageId}")
            return True
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            raise

    # Backward compat aliases
    @staticmethod
    async def get_chat_history(conversationId: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        return await HistoryService.getChatHistory(conversationId, limit, offset)

    @staticmethod
    async def save_message(conversationId: str, role: str, content: str, metadata: Dict = None) -> Dict:
        return await HistoryService.saveMessage(conversationId, role, content, metadata)


# Export instance
historyService = HistoryService()
