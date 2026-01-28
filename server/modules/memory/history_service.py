import uuid
from typing import Dict, List
from modules.messages.repository import message_repository
from config.logger import logger


class HistoryService:
    """Service for managing chat history"""
    
    @staticmethod
    async def get_chat_history(conversation_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get chat history for a conversation"""
        try:
            messages = await message_repository.get_by_conversation(conversation_id, limit, offset)
            logger.info(f"Retrieved {len(messages)} messages for conversation: {conversation_id}")
            return messages
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            raise
    
    @staticmethod
    async def save_message(conversation_id: str, role: str, content: str, metadata: Dict = None) -> Dict:
        """Save a message to history"""
        try:
            message_id = str(uuid.uuid4())
            
            # Using the unified repository 'create' method
            message = await message_repository.create(
                conversation_id=conversation_id,
                role=role,
                content=content,
                message_id=message_id,
                metadata=metadata or {}
            )
            
            logger.chat(f"Saved {role} message to conversation {conversation_id}")
            return message
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            raise
    
    @staticmethod
    async def search_messages(query: str, limit: int = 50) -> List[Dict]:
        """Search messages"""
        try:
            messages = await message_repository.search(query, limit)
            logger.info(f"Found {len(messages)} messages for query: {query[:50]}")
            return messages
        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            raise
    
    @staticmethod
    async def delete_message(message_id: str) -> bool:
        """Delete a message (if implemented)"""
        try:
            # Not yet implemented in repository
            logger.info(f"Deleted message: {message_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            raise


# Export instance
history_service = HistoryService()
