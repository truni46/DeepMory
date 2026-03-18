from typing import Dict, List, Optional
from modules.conversations.repository import conversationRepository
from config.logger import logger

class ConversationService:
    """Service for managing conversations"""
    
    async def getConversations(self, userId: str) -> List[Dict]:
        """Get all conversations for a user"""
        return await conversationRepository.getByUser(userId)
    
    async def getConversation(self, conversationId: str, userId: str) -> Optional[Dict]:
        """Get conversation by ID"""
        return await conversationRepository.getById(conversationId, userId)
    
    async def createConversation(self, userId: str, title: str = None, projectId: str = None) -> Dict:
        """Create new conversation"""
        return await conversationRepository.create(userId, title, projectId)

    async def updateConversation(self, conversationId: str, userId: str, updates: Dict) -> Optional[Dict]:
        """Update conversation fields"""
        validUpdates = {k: v for k, v in updates.items() if v is not None}
        if not validUpdates:
            return await self.getConversation(conversationId, userId)
            
        return await conversationRepository.update(conversationId, userId, validUpdates)

    async def deleteConversation(self, conversationId: str, userId: str) -> bool:
        """Delete a conversation"""
        return await conversationRepository.delete(conversationId, userId)

conversationService = ConversationService()
