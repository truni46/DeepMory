import asyncio
import random
from typing import AsyncGenerator, Dict, List
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
        
        if len(message.strip()) < 1:
            errors.append("Message must contain at least 1 character")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    @staticmethod
    async def generate_ai_response(message: str, conversation_history: List[Dict]) -> str:
        """
        Generate AI response (mock implementation)
        Replace this with actual AI API call (e.g., OpenAI, Anthropic, etc.)
        """
        # Simulate processing time
        await asyncio.sleep(0.5)
        
        # Mock responses based on keywords
        message_lower = message.lower()
        
        if 'hello' in message_lower or 'hi' in message_lower:
            responses = [
                "Hello! How can I help you today?",
                "Hi there! What would you like to learn about?",
                "Hey! I'm here to assist you with your questions."
            ]
        elif 'how are you' in message_lower:
            responses = [
                "I'm doing great, thank you! I'm here to help you learn. What would you like to explore?",
                "I'm functioning well! How can I assist you today?"
            ]
        elif 'thank' in message_lower:
            responses = [
                "You're welcome! Feel free to ask if you have more questions.",
                "Happy to help! Is there anything else you'd like to know?"
            ]
        elif '?' in message:
            responses = [
                f"That's a great question about '{message[:50]}...' Let me help you understand this better. " +
                "This is a complex topic that requires careful consideration. " +
                "The key points to understand are...",
                f"Regarding your question, I can provide some insights. " +
                "Based on my knowledge, the answer involves several factors...",
            ]
        else:
            responses = [
                f"I understand you're asking about: {message[:100]}. " +
                "That's an interesting topic! Let me explain it in detail. " +
                "There are several important aspects to consider...",
                f"Thank you for sharing that. Based on what you've said, " +
                "I can provide some helpful information and guidance.",
            ]
        
        response = random.choice(responses)
        logger.chat(f"Generated AI response for message: {message[:50]}...")
        
        return response
    
    @staticmethod
    async def generate_streaming_response(message: str, conversation_history: List[Dict]) -> AsyncGenerator[str, None]:
        """
        Generate AI response as a stream of chunks
        This simulates streaming like ChatGPT
        """
        full_response = await MessageService.generate_ai_response(message, conversation_history)
        
        # Stream response word by word with slight delay
        words = full_response.split()
        for i, word in enumerate(words):
            chunk = word if i == 0 else f" {word}"
            yield chunk
            # Simulate realistic typing speed
            await asyncio.sleep(random.uniform(0.03, 0.08))
    
    @staticmethod
    async def process_message(message: str, conversation_id: str, conversation_history: List[Dict]) -> Dict:
        """Process message and return complete response"""
        logger.info(f"Processing message for conversation: {conversation_id}")
        
        ai_response = await MessageService.generate_ai_response(message, conversation_history)
        
        from datetime import datetime
        import uuid
        
        return {
            'id': str(uuid.uuid4()),
            'aiResponse': ai_response,
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'conversation_id': conversation_id,
                'message_length': len(message),
                'response_length': len(ai_response)
            }
        }


# Export instance
message_service = MessageService()
