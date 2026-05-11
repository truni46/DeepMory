from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict
from modules.message.service import messageService
from modules.agents.service import agentService
from modules.llm.llmProvider import llmProvider
from modules.quota.service import quotaService
from common.deps import getCurrentUser
from common.prompts import CLASSIFY_SYSTEM
from schemas import MessageRequest
from config.logger import logger
import json

router = APIRouter(prefix="/messages", tags=["Messages"])

CLASSIFY_PROMPT = [{"role": "system", "content": CLASSIFY_SYSTEM}]


async def classifyMessage(message: str) -> str:
    try:
        prompt = CLASSIFY_PROMPT + [{"role": "user", "content": message}]
        logger.info(f"[Step 1] Analyzing user request intent: '{message[:50]}...'")
        result = await llmProvider.provider.generateResponse(prompt, stream=False)
        # Handle tuple return from updated provider
        if isinstance(result, tuple):
            result = result[0]
        classification = result.strip().upper() if isinstance(result, str) else "CHAT"
        if "AGENT" in classification:
            logger.info("[Step 2] Intent -> [AGENT]: Delegating to Agent workflow.")
            return "AGENT"
        logger.info("[Step 2] Intent -> [CHAT]: Processing via standard LLM stream.")
        return "CHAT"
    except Exception as e:
        logger.warning(f"classifyMessage failed, defaulting to CHAT: {e}")
        return "CHAT"


@router.get("/{conversationId}")
async def getConversationHistory(conversationId: str, user: Dict = Depends(getCurrentUser)):
    return await messageService.getHistory(conversationId)

@router.post("/chat/completions")
async def sendMessageStream(data: MessageRequest, user: Dict = Depends(getCurrentUser)):
    try:
        if data.message.startswith("/"):
            task = await agentService.runFromCommand(
                userId=str(user["id"]),
                conversationId=data.conversationId,
                command=data.message,
            )
            async def slashEventGenerator():
                yield f"data: {json.dumps({'agentTask': True, 'taskId': task.get('id')})}\n\n"
            return StreamingResponse(
                slashEventGenerator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        validation = messageService.validateMessage(data.message)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail={"errors": validation['errors']})

        quotaCheck = await quotaService.checkQuota(str(user["id"]), data.conversationId)
        if not quotaCheck["allowed"]:
            async def blockedGenerator():
                yield f"data: {json.dumps({'quotaExceeded': True, 'quota': quotaCheck})}\n\n"
            return StreamingResponse(
                blockedGenerator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        # If documents are attached, always use RAG — skip agent classification
        if data.documentIds and len(data.documentIds) > 0:
            logger.info(f"[Step 2] documentIds present → forcing CHAT/RAG path.")
            route = "CHAT"
        else:
            route = await classifyMessage(data.message)

        if route == "AGENT":
            logger.info(f"[Step 3] Dispatching Agent Task for: '{data.message[:30]}...'")
            task = await agentService.createTask(
                userId=str(user["id"]),
                goal=data.message,
                conversationId=data.conversationId,
                projectId=data.projectId,
            )
            async def agentEventGenerator():
                yield f"data: {json.dumps({'agentTask': True, 'taskId': task.get('id')})}\n\n"
            return StreamingResponse(
                agentEventGenerator(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        async def eventGenerator():
            fullResponse = ""
            sources = []
            try:
                async for chunk in messageService.processMessageFlow(
                    str(user['id']),
                    data.conversationId,
                    data.message,
                    data.projectId,
                    data.documentIds,
                ):
                    if "__TITLE__" in chunk:
                        start = chunk.index("__TITLE__") + len("__TITLE__")
                        end = chunk.index("__TITLE__", start)
                        yield f"data: {json.dumps({'title': chunk[start:end]})}\n\n"
                    elif "__SOURCES__" in chunk:
                        start = chunk.index("__SOURCES__") + len("__SOURCES__")
                        end = chunk.index("__SOURCES__", start)
                        try:
                            sources = json.loads(chunk[start:end])
                        except Exception:
                            pass
                    elif "__QUOTA__" in chunk:
                        start = chunk.index("__QUOTA__") + len("__QUOTA__")
                        end = chunk.index("__QUOTA__", start)
                        quotaJson = chunk[start:end]
                        cleanChunk = chunk[:chunk.index("\n__QUOTA__")] if "\n__QUOTA__" in chunk else ""
                        if cleanChunk:
                            fullResponse += cleanChunk
                            yield f"data: {json.dumps({'chunk': cleanChunk})}\n\n"
                        yield f"data: {json.dumps({'done': True, 'fullResponse': fullResponse, 'quota': json.loads(quotaJson), 'sources': sources})}\n\n"
                    else:
                        fullResponse += chunk
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            eventGenerator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
    except Exception as e:
        logger.error(f"Error streaming message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
