from typing import Dict, List, AsyncGenerator, Optional
import asyncio
import json
from datetime import datetime
import uuid

from modules.message.repository import messageRepository
from modules.llm.llmProvider import llmProvider
from modules.memory.service import memoryFacade
from modules.rag.ragService import ragService
from modules.settings.service import settingsService
from modules.conversations.service import conversationService
from config.logger import logger


class MessageService:
    """Service for handling chat processing and AI response generation"""

    @staticmethod
    def validateMessage(message: str) -> Dict:
        errors = []
        if not message or not message.strip():
            errors.append("Message cannot be empty")
        if len(message) > 5000:
            errors.append("Message too long (max 5000 characters)")
        return {"valid": len(errors) == 0, "errors": errors}

    async def getHistory(self, conversationId: str, limit: int = 100) -> List[Dict]:
        return await messageRepository.getByConversation(conversationId, limit)

    async def processMessageFlow(
        self,
        userId: str,
        conversationId: str,
        content: str,
        projectId: str = None,
    ) -> AsyncGenerator[str, None]:
        """
        Full message processing flow:
        1. Save user message
        2. Build context (Conv window + RAG + Mem)
        3. Stream LLM response
        4. Save assistant response
        5. Background: update short-term window + extract long-term memories
        """
        userMsg = await messageRepository.create(conversationId, "user", content)

        logger.info("[Step 3] Building context (Conversation History, RAG, Memory)")
        contextWindow = await memoryFacade.getContextWindow(conversationId)

        ragContext = ""
        if projectId:
            try:
                results = await ragService.searchContext(content, projectId, limit=5)
                ragContext = "\n\n".join(r.document.content for r in results)
            except Exception as e:
                logger.warning(f"RAG search failed for project {projectId}: {e}")

        memoryTexts = await memoryFacade.retrieveRelevantMemories(userId, content, limit=5)
        memoryText = "\n".join(f"- {m}" for m in memoryTexts)

        systemPrompt = "You are a helpful AI assistant."
        if ragContext:
            systemPrompt += f"\n\nRelevant Context:\n{ragContext}"
        if memoryText:
            systemPrompt += f"\n\nKnown about this user:\n{memoryText}"

        messages = [{"role": "system", "content": systemPrompt}] + contextWindow + [{"role": "user", "content": content}]
        logger.info(f"[Step 4] Starting streaming response (Model: {llmProvider.model})")

        fullResponse = ""
        try:
            async for chunk in llmProvider._stream_response(messages):
                fullResponse += chunk
                yield chunk
        except Exception as e:
            logger.error(f"LLM Error — userId: {userId}, conversationId: {conversationId}, error: {e}")
            errorMsg = "Xin lỗi, hiện tại hệ thống AI đang gặp sự cố kết nối hoặc phản hồi. Vui lòng thử lại sau."
            if not fullResponse:
                fullResponse = errorMsg
                yield errorMsg
            else:
                fullResponse += f"\n\n[{errorMsg}]"
                yield f"\n\n[{errorMsg}]"
                
        logger.info("[Step 5] Stream complete. Executing background tasks (Persistence & Summary)")
        await messageRepository.create(
            conversationId, "assistant", fullResponse,
            model=llmProvider.model, parentId=userMsg["id"],
        )

        asyncio.create_task(memoryFacade.addTurn(conversationId, "user", content))
        asyncio.create_task(memoryFacade.addTurn(conversationId, "assistant", fullResponse))

        asyncio.create_task(
            memoryFacade.processConversationTurn(userId, conversationId, content, fullResponse)
        )

        if len(contextWindow) <= 1:
            asyncio.create_task(
                self.generateConversationTitle(conversationId, userId, content, fullResponse)
            )

    async def processMessage(self, message: str, conversationId: str, history: List[Dict]) -> Dict:
        fullResponse = ""
        async for chunk in self.processMessageFlow("00000000-0000-0000-0000-000000000000", conversationId, message):
            fullResponse += chunk
        return {
            "id": str(uuid.uuid4()),
            "aiResponse": fullResponse,
            "timestamp": datetime.now().isoformat(),
            "metadata": {},
        }

    async def generateStreamingResponse(
        self, message: str, history: List[Dict], conversationId: str = None
    ) -> AsyncGenerator[str, None]:
        cid = conversationId
        if not cid and history:
            cid = history[0].get("conversationId", "unknown")
        if not cid:
            cid = "unknownConversation"
        async for chunk in self.processMessageFlow("00000000-0000-0000-0000-000000000000", cid, message):
            yield chunk

    async def generateAIResponse(self, message: str, history: List[Dict]) -> str:
        fullResponse = ""
        cid = "unknownConversation"
        if history:
            cid = history[0].get("conversationId", "unknownConversation")
        async for chunk in self.processMessageFlow("00000000-0000-0000-0000-000000000000", cid, message):
            fullResponse += chunk
        return fullResponse

    async def generateConversationTitle(
        self, conversationId: str, userId: str, userMessage: str, aiResponse: str
    ):
        try:
            logger.info(f"Generating title for conversation {conversationId}")
            prompt = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates short, concise titles for conversations. Max 6 words. No quotes. No prefixes like 'Title:'.",
                },
                {
                    "role": "user",
                    "content": f"User: {userMessage[:500]}\nAI: {aiResponse[:500]}\n\nGenerate a title for this conversation:",
                },
            ]
            title = ""
            async for chunk in llmProvider._stream_response(prompt):
                title += chunk
            title = title.strip().strip('"')
            if title:
                logger.info(f"Generated title: {title}")
                await conversationService.updateConversation(conversationId, userId, {"title": title})
        except Exception as e:
            logger.error(f"Error generating conversation title: {e}")


messageService = MessageService()
