import uuid
from datetime import datetime
from typing import Dict, List, Optional
from config.database import db
from config.logger import logger


class ConversationService:
    """Service for managing conversations"""
    
    @staticmethod
    async def get_all_conversations() -> List[Dict]:
        """Get all conversations"""
        try:
            conversations = await db.get_all_conversations()
            logger.info(f"Retrieved {len(conversations)} conversations")
            return conversations
        except Exception as e:
            logger.error(f"Error getting conversations: {e}")
            raise
    
    @staticmethod
    async def get_conversation_by_id(conversation_id: str) -> Optional[Dict]:
        """Get conversation by ID"""
        try:
            conversation = await db.get_conversation_by_id(conversation_id)
            if conversation:
                logger.info(f"Retrieved conversation: {conversation_id}")
            else:
                logger.warning(f"Conversation not found: {conversation_id}")
            return conversation
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {e}")
            raise
    
    @staticmethod
    async def create_conversation(title: str = None, metadata: Dict = None) -> Dict:
        """Create new conversation"""
        try:
            conversation_id = str(uuid.uuid4())
            
            if not title:
                title = f"New Chat - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            
            conversation = await db.create_conversation(
                conversation_id=conversation_id,
                title=title,
                metadata=metadata or {}
            )
            
            logger.info(f"Created conversation: {conversation_id} - {title}")
            return conversation
        except Exception as e:
            logger.error(f"Error creating conversation: {e}")
            raise
    
    @staticmethod
    async def update_conversation(conversation_id: str, updates: Dict) -> Optional[Dict]:
        """Update conversation"""
        try:
            conversation = await db.update_conversation(conversation_id, updates)
            
            if conversation:
                logger.info(f"Updated conversation: {conversation_id}")
            else:
                logger.warning(f"Conversation not found for update: {conversation_id}")
            
            return conversation
        except Exception as e:
            logger.error(f"Error updating conversation {conversation_id}: {e}")
            raise
    
    @staticmethod
    async def delete_conversation(conversation_id: str) -> bool:
        """Delete conversation"""
        try:
            success = await db.delete_conversation(conversation_id)
            
            if success:
                logger.info(f"Deleted conversation: {conversation_id}")
            else:
                logger.warning(f"Conversation not found for deletion: {conversation_id}")
            
            return success
        except Exception as e:
            logger.error(f"Error deleting conversation {conversation_id}: {e}")
            raise


# Export instance
conversation_service = ConversationService()
