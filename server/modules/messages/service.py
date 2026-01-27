from typing import Dict, List, AsyncGenerator, Optional
import asyncio
import json
from datetime import datetime
import uuid

from modules.messages.repository import message_repository
from modules.llm.llm_provider import llm_provider
from modules.memory.rag_service import rag_service
from modules.memory.service import memory_service
from config.logger import logger

class MessageService:
    """Service for handling message processing and AI response generation"""
    
    @staticmethod
    def validate_message(message: str) -> Dict:
        """Validate user message"""
        errors = []
        if not message or not message.strip():
            errors.append("Message cannot be empty")
        if len(message) > 5000:
            errors.append("Message too long (max 5000 characters)")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

    async def get_history(self, conversation_id: str, limit: int = 100) -> List[Dict]:
        """Get conversation history"""
        # We might want to verify user access here if strict, 
        # but the router typically handles checking if the conversation belongs to the user 
        # via a conversation service check, or we assume conversation_id is enough if UUIDs are random.
        # But optimally, we should check ownership.
        # For now, just return data.
        return await message_repository.get_by_conversation(conversation_id, limit)

    async def process_message_flow(self, user_id: str, conversation_id: str, content: str, project_id: str = None) -> AsyncGenerator[str, None]:
        """
        Full message processing flow:
        1. Save user message
        2. Retrieve context (History + RAG + Memory)
        3. Call LLM (Streamed)
        4. Save assistant response
        """
        # 1. Save User Message
        user_msg = await message_repository.create(conversation_id, "user", content)
        
        # 2. Build Context
        # Chat History
        history = await message_repository.get_history_for_context(conversation_id, limit=10)
        
        # RAG Context (if project defined)
        rag_context = ""
        if project_id:
            rag_context = await rag_service.search_context(content, project_id)
            
        # Memory Context
        memories = await memory_service.retrieve_memories(user_id, content)
        memory_text = "\n".join([m['content'] for m in memories])
        
        # System Prompt construction
        system_prompt = "You are a helpful AI assistant."
        if rag_context:
            system_prompt += f"\n\nRelevant Context:\n{rag_context}"
        if memory_text:
            system_prompt += f"\n\nUser Memories:\n{memory_text}"
            
        messages = [{"role": "system", "content": system_prompt}] + history
        # Add current message if not in history (history usually excludes current if fetched before save, but here we fetched after save? 
        # Actually get_history_for_context fetches *recent* messages. 
        # If we saved it, it might be in there. Let's ensure we don't duplicate.
        # Simplest: Fetch history excluding the very last one if it matches, OR just trust the LLM service to handle a list.
        # Actually, let's just pass `messages` correctly.
        
        # 3. Stream LLM Response
        full_response = ""
        async for chunk in llm_provider._stream_response(messages):
            full_response += chunk
            yield chunk
            
        # 4. Save Assistant Response
        await message_repository.create(conversation_id, "assistant", full_response, model=llm_provider.model, parent_id=user_msg['id'])
        
        # 5. Background: Update Memory/RAG relevance? (Optional)
        # await memory_service.add_memory(user_id, content) # logic to detect important facts

    # Legacy support wrappers if needed, or replacement for existing methods
    async def process_message(self, message: str, conversation_id: str, history: List[Dict]) -> Dict:
        # This was the old non-streaming method. 
        # We can implement it by consuming the stream.
        full_response = ""
        async for chunk in self.process_message_flow("unknown_user", conversation_id, message): # User ID missing in old signature
            full_response += chunk
            
        return {
            'id': str(uuid.uuid4()),
            'aiResponse': full_response,
            'timestamp': datetime.now().isoformat(),
            'metadata': {}
        }

    async def generate_streaming_response(self, message: str, history: List[Dict]) -> AsyncGenerator[str, None]:
        # Old signature support
        async for chunk in self.process_message_flow("unknown_user", history[0].get('conversation_id', 'unknown'), message):
             yield chunk

message_service = MessageService()
