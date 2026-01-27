from typing import Dict, List, Optional
from modules.conversations.repository import conversation_repository
from config.logger import logger

class ConversationService:
    """Service for managing conversations"""
    
    async def get_user_conversations(self, user_id: str) -> List[Dict]:
        """Get all conversations for a user"""
        return await conversation_repository.get_by_user(user_id)
    
    async def get_conversation(self, conversation_id: str, user_id: str) -> Optional[Dict]:
        """Get conversation by ID"""
        return await conversation_repository.get_by_id(conversation_id, user_id)
    
    async def create_conversation(self, user_id: str, title: str = None, project_id: str = None) -> Dict:
        """Create new conversation"""
        return await conversation_repository.create(user_id, title, project_id)

    async def update_conversation(self, conversation_id: str, user_id: str, updates: Dict) -> Optional[Dict]:
        """Update conversation fields"""
        # Filter valid updates
        valid_updates = {k: v for k, v in updates.items() if v is not None}
        if not valid_updates:
            return await self.get_conversation(conversation_id, user_id)
            
        return await conversation_repository.update(conversation_id, user_id, valid_updates)

    async def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation"""
        return await conversation_repository.delete(conversation_id, user_id)

    # Legacy method support (optional, or remove if fully breaking)
    async def get_all_conversations(self) -> List[Dict]:
        # This implies getting ALL conversations for ALL users, likely not what we want anymore. 
        # But for backward compat with existing routes (which didn't have auth yet), we might leave a placeholder or error.
        # Assuming we will update routes to use auth.
        pass

conversation_service = ConversationService()
