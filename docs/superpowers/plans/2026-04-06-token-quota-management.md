# Token Quota Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add token-based quota management with Redis real-time tracking, LLM usage extraction, and a collapsible frontend widget.

**Architecture:** Hybrid Redis+DB approach — Redis counters for real-time quota checks (session 2h TTL, weekly 7d TTL), DB message metadata for audit/rebuild. LLM providers return usage data alongside content; tiktoken fallback with explicit logging.

**Tech Stack:** Python FastAPI, Redis (async), asyncpg, tiktoken, React + Tailwind CSS

---

### File Structure

**New files:**
- `server/config/quota.py` — env-based quota config singleton
- `server/modules/quota/repository.py` — Redis operations + DB rebuild
- `server/modules/quota/service.py` — quota check/increment/status logic
- `server/modules/quota/router.py` — GET /quota/status endpoint
- `src/components/ui/QuotaWidget.jsx` — collapsible quota display widget

**Modified files:**
- `server/modules/llm/llmProvider.py` — extract usage from API responses
- `server/modules/message/service.py` — integrate usage extraction + quota calls
- `server/modules/message/router.py` — add quota check + SSE quota event
- `server/modules/message/repository.py` — store extended usage metadata
- `server/apiRouter.py` — register quota router
- `src/services/streamingService.js` — handle quota SSE events
- `src/pages/ChatPage.jsx` — add QuotaWidget + quota state + block UI
- `src/components/ChatInput.jsx` — accept quotaBlocked prop

---

### Task 1: Quota Config (`server/config/quota.py`)

**Files:**
- Create: `server/config/quota.py`

- [ ] **Step 1: Create quota config module**

```python
import os

class QuotaConfig:
    def __init__(self):
        self.sessionLimit = int(os.getenv("TOKEN_SESSION_LIMIT", 500000))
        self.sessionDuration = int(os.getenv("TOKEN_SESSION_DURATION", 7200))
        self.weeklyLimit = int(os.getenv("TOKEN_WEEKLY_LIMIT", 5000000))
        self.warningThreshold = float(os.getenv("TOKEN_WARNING_THRESHOLD", 0.9))

quotaConfig = QuotaConfig()
```

- [ ] **Step 2: Commit**

```bash
git add server/config/quota.py
git commit -m "feat(quota): add env-based quota config"
```

---

### Task 2: Quota Repository (`server/modules/quota/repository.py`)

**Files:**
- Create: `server/modules/quota/repository.py`

- [ ] **Step 1: Create quota repository with Redis ops + DB rebuild**

```python
from datetime import datetime, timedelta
from typing import Optional
from config.logger import logger
from config.database import db
from common.cacheService import cacheService
from config.quota import quotaConfig


def getWeekStart() -> str:
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


class QuotaRepository:

    def _sessionKey(self, userId: str, conversationId: str) -> str:
        return f"quota:session:{userId}:{conversationId}"

    def _weeklyKey(self, userId: str) -> str:
        return f"quota:weekly:{userId}:{getWeekStart()}"

    async def getSessionUsage(self, userId: str, conversationId: str) -> Optional[int]:
        if not cacheService.redis:
            return None
        try:
            val = await cacheService.redis.get(self._sessionKey(userId, conversationId))
            return int(val) if val is not None else None
        except Exception as e:
            logger.error(f"getSessionUsage failed: {e}")
            return None

    async def getWeeklyUsage(self, userId: str) -> Optional[int]:
        if not cacheService.redis:
            return None
        try:
            val = await cacheService.redis.get(self._weeklyKey(userId))
            return int(val) if val is not None else None
        except Exception as e:
            logger.error(f"getWeeklyUsage failed: {e}")
            return None

    async def incrementUsage(self, userId: str, conversationId: str, tokens: int):
        if not cacheService.redis:
            logger.warning("Redis unavailable, skipping quota increment")
            return
        try:
            sessionKey = self._sessionKey(userId, conversationId)
            weeklyKey = self._weeklyKey(userId)

            pipe = cacheService.redis.pipeline()
            pipe.incrby(sessionKey, tokens)
            pipe.expire(sessionKey, quotaConfig.sessionDuration)
            pipe.incrby(weeklyKey, tokens)
            pipe.expire(weeklyKey, 7 * 24 * 3600)
            await pipe.execute()
        except Exception as e:
            logger.error(f"incrementUsage failed for user {userId}: {e}")

    async def rebuildSessionFromDb(self, userId: str, conversationId: str) -> int:
        total = 0
        try:
            if db.useDatabase and db.pool:
                cutoff = datetime.now() - timedelta(seconds=quotaConfig.sessionDuration)
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT COALESCE(SUM((metadata->>'tokens')::int), 0) as total
                           FROM messages
                           WHERE "conversationId" = $1 AND "createdAt" >= $2""",
                        conversationId, cutoff
                    )
                    total = row["total"] if row else 0

            if cacheService.redis and total > 0:
                key = self._sessionKey(userId, conversationId)
                await cacheService.redis.set(key, total, ex=quotaConfig.sessionDuration)
                logger.info(f"Rebuilt session quota for user {userId}: {total} tokens")
        except Exception as e:
            logger.error(f"rebuildSessionFromDb failed for user {userId}: {e}")
        return total

    async def rebuildWeeklyFromDb(self, userId: str) -> int:
        total = 0
        try:
            if db.useDatabase and db.pool:
                weekStart = getWeekStart()
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT COALESCE(SUM((metadata->>'tokens')::int), 0) as total
                           FROM messages m
                           JOIN conversations c ON m."conversationId" = c.id
                           WHERE c."userId" = $1 AND m."createdAt" >= $2::date""",
                        userId, weekStart
                    )
                    total = row["total"] if row else 0

            if cacheService.redis and total > 0:
                key = self._weeklyKey(userId)
                await cacheService.redis.set(key, total, ex=7 * 24 * 3600)
                logger.info(f"Rebuilt weekly quota for user {userId}: {total} tokens")
        except Exception as e:
            logger.error(f"rebuildWeeklyFromDb failed for user {userId}: {e}")
        return total

    async def getSessionTTL(self, userId: str, conversationId: str) -> int:
        if not cacheService.redis:
            return quotaConfig.sessionDuration
        try:
            ttl = await cacheService.redis.ttl(self._sessionKey(userId, conversationId))
            return max(ttl, 0)
        except Exception as e:
            logger.error(f"getSessionTTL failed: {e}")
            return 0


quotaRepository = QuotaRepository()
```

- [ ] **Step 2: Commit**

```bash
git add server/modules/quota/repository.py
git commit -m "feat(quota): add quota repository with Redis ops and DB rebuild"
```

---

### Task 3: Quota Service (`server/modules/quota/service.py`)

**Files:**
- Create: `server/modules/quota/service.py`

- [ ] **Step 1: Create quota service**

```python
from typing import Dict
from config.quota import quotaConfig
from config.logger import logger
from modules.quota.repository import quotaRepository, getWeekStart


class QuotaService:

    async def checkQuota(self, userId: str, conversationId: str) -> Dict:
        sessionUsed = await quotaRepository.getSessionUsage(userId, conversationId)
        if sessionUsed is None:
            sessionUsed = await quotaRepository.rebuildSessionFromDb(userId, conversationId)

        weeklyUsed = await quotaRepository.getWeeklyUsage(userId)
        if weeklyUsed is None:
            weeklyUsed = await quotaRepository.rebuildWeeklyFromDb(userId)

        sessionPercent = sessionUsed / quotaConfig.sessionLimit if quotaConfig.sessionLimit > 0 else 0
        weeklyPercent = weeklyUsed / quotaConfig.weeklyLimit if quotaConfig.weeklyLimit > 0 else 0

        maxPercent = max(sessionPercent, weeklyPercent)
        allowed = maxPercent < 1.0
        warning = maxPercent >= quotaConfig.warningThreshold and maxPercent < 1.0

        sessionTTL = await quotaRepository.getSessionTTL(userId, conversationId)

        return {
            "allowed": allowed,
            "warning": warning,
            "session": {
                "used": sessionUsed,
                "limit": quotaConfig.sessionLimit,
                "percent": round(sessionPercent, 4),
                "remainingSeconds": sessionTTL,
            },
            "weekly": {
                "used": weeklyUsed,
                "limit": quotaConfig.weeklyLimit,
                "percent": round(weeklyPercent, 4),
                "resetDay": getWeekStart(),
            },
        }

    async def incrementUsage(self, userId: str, conversationId: str, tokens: int):
        if tokens <= 0:
            return
        await quotaRepository.incrementUsage(userId, conversationId, tokens)
        logger.info(f"Quota incremented for user {userId}: +{tokens} tokens")

    async def getStatus(self, userId: str, conversationId: str) -> Dict:
        return await self.checkQuota(userId, conversationId)


quotaService = QuotaService()
```

- [ ] **Step 2: Commit**

```bash
git add server/modules/quota/service.py
git commit -m "feat(quota): add quota service with check, increment, status"
```

---

### Task 4: Quota Router (`server/modules/quota/router.py`)

**Files:**
- Create: `server/modules/quota/router.py`
- Modify: `server/apiRouter.py:1-22`

- [ ] **Step 1: Create quota router**

```python
from fastapi import APIRouter, Depends, Query
from typing import Dict
from common.deps import getCurrentUser
from modules.quota.service import quotaService
from config.logger import logger

router = APIRouter(prefix="/quota", tags=["Quota"])


@router.get("/status")
async def getQuotaStatus(
    conversationId: str = Query(default=""),
    user: Dict = Depends(getCurrentUser),
):
    try:
        status = await quotaService.getStatus(str(user["id"]), conversationId)
        return status
    except Exception as e:
        logger.error(f"getQuotaStatus failed: {e}")
        raise
```

- [ ] **Step 2: Register quota router in apiRouter.py**

Add these two lines to `server/apiRouter.py`:

```python
from modules.quota.router import router as quotaRouter
```

And at the bottom with the other `include_router` calls:

```python
router.include_router(quotaRouter)
```

- [ ] **Step 3: Commit**

```bash
git add server/modules/quota/router.py server/apiRouter.py
git commit -m "feat(quota): add quota REST endpoint and register router"
```

---

### Task 5: LLM Provider — Extract Usage Data (`server/modules/llm/llmProvider.py`)

**Files:**
- Modify: `server/modules/llm/llmProvider.py`

- [ ] **Step 1: Add usage extraction to `BaseOpenAIProvider.generateResponse()`**

Replace lines 21-37 of `llmProvider.py` (the `generateResponse` method in `BaseOpenAIProvider`):

```python
    async def generateResponse(self, messages: List[Dict], stream: bool = False, tools: Optional[List[Dict]] = None):
        try:
            if stream:
                return self.streamResponse(messages)
            else:
                kwargs = {"model": self.model, "messages": messages, "temperature": 0.7}
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                response = await self.client.chat.completions.create(**kwargs)
                msg = response.choices[0].message

                usageDict = None
                if hasattr(response, "usage") and response.usage:
                    usageDict = {
                        "promptTokens": response.usage.prompt_tokens or 0,
                        "completionTokens": response.usage.completion_tokens or 0,
                        "totalTokens": (response.usage.prompt_tokens or 0) + (response.usage.completion_tokens or 0),
                        "source": "api_usage",
                    }

                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    return msg, usageDict
                return msg.content, usageDict
        except Exception as e:
            logger.error(f"LLM Provider ({self.model}) error: {e}")
            raise e
```

- [ ] **Step 2: Add usage extraction to `BaseOpenAIProvider.streamResponse()`**

Replace lines 39-58 (the `streamResponse` method):

```python
    async def streamResponse(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            usageDict = None
            async for chunk in stream:
                if chunk.choices:
                    content = chunk.choices[0].delta.content
                    if content:
                        import asyncio
                        step = 4
                        for i in range(0, len(content), step):
                            yield content[i:i+step]
                            await asyncio.sleep(0.01)
                if hasattr(chunk, "usage") and chunk.usage:
                    usageDict = {
                        "promptTokens": chunk.usage.prompt_tokens or 0,
                        "completionTokens": chunk.usage.completion_tokens or 0,
                        "totalTokens": (chunk.usage.prompt_tokens or 0) + (chunk.usage.completion_tokens or 0),
                        "source": "api_usage",
                    }
            if usageDict:
                yield f"\n__USAGE__{json.dumps(usageDict)}__USAGE__"
        except Exception as e:
            logger.error(f"LLM Streaming error ({self.model}): {e}")
            raise e
```

- [ ] **Step 3: Add usage extraction to `GeminiNativeProvider.generateResponse()`**

Replace lines 105-127 (the non-stream `generateResponse` in `GeminiNativeProvider`):

```python
    async def generateResponse(self, messages: List[Dict], stream: bool = False):
        try:
            if stream:
                return self.streamResponse(messages)

            import httpx
            payload = self._convert_messages(messages)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=60.0)
                if resp.status_code != 200:
                    raise Exception(f"Gemini API error ({resp.status_code}): {resp.text}")

                data = resp.json()
                usageDict = None
                usageMeta = data.get("usageMetadata")
                if usageMeta:
                    usageDict = {
                        "promptTokens": usageMeta.get("promptTokenCount", 0),
                        "completionTokens": usageMeta.get("candidatesTokenCount", 0),
                        "totalTokens": usageMeta.get("totalTokenCount", 0),
                        "source": "api_usage",
                    }

                content = ""
                if "candidates" in data and len(data["candidates"]) > 0:
                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                    if parts:
                        content = parts[0].get("text", "")
                return content, usageDict
        except Exception as e:
            logger.error(f"LLM Provider ({self.model}) error: {e}")
            raise e
```

- [ ] **Step 4: Add usage extraction to `GeminiNativeProvider.streamResponse()`**

Replace lines 129-158 (the `streamResponse` in `GeminiNativeProvider`):

```python
    async def streamResponse(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        import httpx
        import json
        payload = self._convert_messages(messages)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?key={self.api_key}&alt=sse"

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", url, json=payload, timeout=60.0) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise Exception(f"Gemini API stream error ({response.status_code}): {error_text.decode('utf-8')}")

                    usageDict = None
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data = json.loads(data_str)
                                if "candidates" in data and len(data["candidates"]) > 0:
                                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                                    if parts:
                                        content = parts[0].get("text", "")
                                        if content:
                                            yield content
                                usageMeta = data.get("usageMetadata")
                                if usageMeta and usageMeta.get("totalTokenCount"):
                                    usageDict = {
                                        "promptTokens": usageMeta.get("promptTokenCount", 0),
                                        "completionTokens": usageMeta.get("candidatesTokenCount", 0),
                                        "totalTokens": usageMeta.get("totalTokenCount", 0),
                                        "source": "api_usage",
                                    }
                            except json.JSONDecodeError:
                                pass
                    if usageDict:
                        yield f"\n__USAGE__{json.dumps(usageDict)}__USAGE__"
        except Exception as e:
            logger.error(f"LLM Streaming error ({self.model}): {e}")
            raise e
```

- [ ] **Step 5: Update `MockProvider.generateResponse()` to return tuple**

Replace lines 171-180:

```python
    async def generateResponse(self, messages: List[Dict], stream: bool = False):
        mockText = "This is a mock response. Please configure a valid LLM_PROVIDER in settings."
        if stream:
            async def generator():
                for word in mockText.split():
                    import asyncio
                    yield word + " "
                    await asyncio.sleep(0.05)
            return generator()
        return mockText, None
```

- [ ] **Step 6: Add `json` import at top of file**

Add `import json` to the imports at the top of `llmProvider.py` (line 1-5 area).

- [ ] **Step 7: Commit**

```bash
git add server/modules/llm/llmProvider.py
git commit -m "feat(quota): extract usage data from LLM provider responses"
```

---

### Task 6: Message Service — Usage Extraction + Quota Integration (`server/modules/message/service.py`)

**Files:**
- Modify: `server/modules/message/service.py`

- [ ] **Step 1: Add imports and usage parsing helper**

Add to the imports section (after line 13):

```python
from modules.quota.service import quotaService
from modules.memory.shortTerm.contextWindowManager import contextWindowManager
```

Add a helper method to the `MessageService` class (after the `validateMessage` method, line 26):

```python
    @staticmethod
    def parseUsageFromStream(chunk: str):
        if "__USAGE__" in chunk:
            import json
            start = chunk.index("__USAGE__") + len("__USAGE__")
            end = chunk.index("__USAGE__", start)
            usageJson = chunk[start:end]
            cleanChunk = chunk[:chunk.index("\n__USAGE__")] if "\n__USAGE__" in chunk else ""
            return cleanChunk, json.loads(usageJson)
        return chunk, None

    @staticmethod
    def buildUsageDict(content: str, model: str) -> dict:
        tokens = contextWindowManager.countTokens(content)
        logger.warning(f"[TOKEN_SOURCE: tiktoken_fallback] Provider {model} did not return usage data, counting via tiktoken")
        return {
            "promptTokens": 0,
            "completionTokens": tokens,
            "totalTokens": tokens,
            "source": "tiktoken_fallback",
        }
```

- [ ] **Step 2: Update `processMessageFlow` to capture usage and integrate quota**

Replace the `processMessageFlow` method (lines 31-102):

```python
    async def processMessageFlow(
        self,
        userId: str,
        conversationId: str,
        content: str,
        projectId: str = None,
    ) -> AsyncGenerator[str, None]:
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

        fullResponse = ""
        usageDict = None
        try:
            async for chunk in llmProvider._stream_response(messages):
                cleanChunk, chunkUsage = self.parseUsageFromStream(chunk)
                if chunkUsage:
                    usageDict = chunkUsage
                if cleanChunk:
                    fullResponse += cleanChunk
                    yield cleanChunk
        except Exception as e:
            logger.error(f"LLM Error — userId: {userId}, conversationId: {conversationId}, error: {e}")
            errorMsg = "Xin lỗi, hiện tại hệ thống AI đang gặp sự cố kết nối hoặc phản hồi. Vui lòng thử lại sau."
            if not fullResponse:
                fullResponse = errorMsg
                yield errorMsg
            else:
                fullResponse += f"\n\n[{errorMsg}]"
                yield f"\n\n[{errorMsg}]"

        if usageDict:
            logger.info(f"[TOKEN_SOURCE: api_usage] {llmProvider.model}: prompt={usageDict['promptTokens']}, completion={usageDict['completionTokens']}")
        else:
            usageDict = self.buildUsageDict(fullResponse, llmProvider.model)

        metadata = {"usage": usageDict, "tokens": usageDict.get("completionTokens", 0)}

        logger.info("[Step 5] Stream complete. Executing background tasks (Persistence & Summary)")
        await messageRepository.create(
            conversationId, "assistant", fullResponse,
            model=llmProvider.model, parentId=userMsg["id"],
            metadata=metadata,
        )

        await quotaService.incrementUsage(userId, conversationId, usageDict.get("totalTokens", 0))

        quotaStatus = await quotaService.getStatus(userId, conversationId)
        yield f"\n__QUOTA__{json.dumps(quotaStatus)}__QUOTA__"

        asyncio.create_task(memoryFacade.addTurn(conversationId, "user", content))
        asyncio.create_task(memoryFacade.addTurn(conversationId, "assistant", fullResponse))

        asyncio.create_task(
            memoryFacade.processConversationTurn(userId, conversationId, content, fullResponse)
        )

        if len(contextWindow) <= 1:
            asyncio.create_task(
                self.generateConversationTitle(conversationId, userId, content, fullResponse)
            )
```

- [ ] **Step 3: Commit**

```bash
git add server/modules/message/service.py
git commit -m "feat(quota): integrate usage extraction and quota tracking in message flow"
```

---

### Task 7: Message Router — Quota Check + SSE Quota Event (`server/modules/message/router.py`)

**Files:**
- Modify: `server/modules/message/router.py`

- [ ] **Step 1: Add quota import and update `sendMessageStream`**

Add import at top (after line 9):

```python
from modules.quota.service import quotaService
```

Replace the `sendMessageStream` function (lines 49-115) — add quota check before LLM call and parse quota event from stream:

```python
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
            try:
                async for chunk in messageService.processMessageFlow(
                    str(user['id']),
                    data.conversationId,
                    data.message,
                    data.projectId
                ):
                    if "__QUOTA__" in chunk:
                        start = chunk.index("__QUOTA__") + len("__QUOTA__")
                        end = chunk.index("__QUOTA__", start)
                        quotaJson = chunk[start:end]
                        cleanChunk = chunk[:chunk.index("\n__QUOTA__")] if "\n__QUOTA__" in chunk else ""
                        if cleanChunk:
                            fullResponse += cleanChunk
                            yield f"data: {json.dumps({'chunk': cleanChunk})}\n\n"
                        yield f"data: {json.dumps({'done': True, 'fullResponse': fullResponse, 'quota': json.loads(quotaJson)})}\n\n"
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
```

- [ ] **Step 2: Commit**

```bash
git add server/modules/message/router.py
git commit -m "feat(quota): add quota check and SSE quota event in message router"
```

---

### Task 8: Register Quota Router (`server/apiRouter.py`)

**Files:**
- Modify: `server/apiRouter.py`

- [ ] **Step 1: Add quota router import and registration**

Add import line after line 10:

```python
from modules.quota.router import router as quotaRouter
```

Add registration after line 22:

```python
router.include_router(quotaRouter)
```

- [ ] **Step 2: Commit**

```bash
git add server/apiRouter.py
git commit -m "feat(quota): register quota router in API"
```

---

### Task 9: Frontend StreamingService — Handle Quota Events (`src/services/streamingService.js`)

**Files:**
- Modify: `src/services/streamingService.js`

- [ ] **Step 1: Add `onQuota` callback and `quotaExceeded` handling**

Replace the `sendMessage` method signature and SSE parsing logic. The new method:

```javascript
    async sendMessage(message, conversationId, onChunk, onComplete, onError, onAgentTask, onQuota) {
        try {
            const token = localStorage.getItem('accessToken');
            const headers = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`${API_BASE_URL}/messages/chat/completions`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ message, conversationId }),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();

                if (done) {
                    break;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));

                            if (data.quotaExceeded && onQuota) {
                                onQuota(data.quota, true);
                                return;
                            }

                            if (data.agentTask && onAgentTask) {
                                onAgentTask(data.taskId);
                                return;
                            }

                            if (data.error) {
                                onError(new Error(data.error));
                                return;
                            }

                            if (data.chunk) {
                                onChunk(data.chunk);
                            }

                            if (data.done) {
                                if (data.quota && onQuota) {
                                    onQuota(data.quota, false);
                                }
                                onComplete(data.fullResponse);
                                return;
                            }
                        } catch (err) {
                            console.error('Error parsing SSE data:', err);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Streaming error:', error);
            onError(error);
        }
    }
```

- [ ] **Step 2: Commit**

```bash
git add src/services/streamingService.js
git commit -m "feat(quota): handle quota events in streaming service"
```

---

### Task 10: QuotaWidget Component (`src/components/ui/QuotaWidget.jsx`)

**Files:**
- Create: `src/components/ui/QuotaWidget.jsx`

- [ ] **Step 1: Create QuotaWidget component**

```jsx
import { useState, useRef, useEffect } from 'react';

function formatTokens(n) {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`;
    return String(n);
}

function formatTime(seconds) {
    if (seconds <= 0) return '0m';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

function getColor(percent) {
    if (percent >= 0.9) return { bg: 'bg-red-500', text: 'text-red-600', ring: 'ring-red-400' };
    if (percent >= 0.7) return { bg: 'bg-yellow-500', text: 'text-yellow-600', ring: 'ring-yellow-400' };
    return { bg: 'bg-green-500', text: 'text-green-600', ring: 'ring-green-400' };
}

function ProgressBar({ label, used, limit, percent, extra }) {
    const color = getColor(percent);
    return (
        <div className="mb-3 last:mb-0">
            <div className="flex justify-between text-xs mb-1">
                <span className="font-medium text-text-primary">{label}</span>
                <span className={`font-semibold ${color.text}`}>
                    {formatTokens(used)} / {formatTokens(limit)}
                </span>
            </div>
            <div className="w-full h-2 bg-bg-secondary rounded-full overflow-hidden">
                <div
                    className={`h-full rounded-full transition-all duration-500 ${color.bg}`}
                    style={{ width: `${Math.min(percent * 100, 100)}%` }}
                />
            </div>
            {extra && (
                <div className="text-[10px] text-text-muted mt-0.5">{extra}</div>
            )}
        </div>
    );
}

export default function QuotaWidget({ quota, warning }) {
    const [expanded, setExpanded] = useState(false);
    const panelRef = useRef(null);

    useEffect(() => {
        if (warning && quota) setExpanded(true);
    }, [warning]);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (panelRef.current && !panelRef.current.contains(e.target)) {
                setExpanded(false);
            }
        };
        if (expanded) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [expanded]);

    if (!quota) return null;

    const maxPercent = Math.max(quota.session?.percent || 0, quota.weekly?.percent || 0);
    const color = getColor(maxPercent);
    const isBlocked = !quota.allowed;

    return (
        <div className="fixed bottom-24 right-6 z-50" ref={panelRef}>
            {expanded && (
                <div className="mb-2 bg-white border border-border rounded-xl shadow-xl p-4 w-72 animate-in fade-in slide-in-from-bottom-2 duration-200">
                    <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-semibold text-text-primary">Token Usage</h4>
                        {isBlocked && (
                            <span className="text-[10px] font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
                                QUOTA EXCEEDED
                            </span>
                        )}
                    </div>
                    <ProgressBar
                        label="Session"
                        used={quota.session?.used || 0}
                        limit={quota.session?.limit || 1}
                        percent={quota.session?.percent || 0}
                        extra={`${formatTime(quota.session?.remainingSeconds || 0)} remaining`}
                    />
                    <ProgressBar
                        label="Weekly"
                        used={quota.weekly?.used || 0}
                        limit={quota.weekly?.limit || 1}
                        percent={quota.weekly?.percent || 0}
                        extra={`Resets ${quota.weekly?.resetDay || 'Mon'}`}
                    />
                </div>
            )}

            <button
                onClick={() => setExpanded(!expanded)}
                className={`ml-auto flex items-center justify-center w-10 h-10 rounded-full shadow-lg border-2 border-white transition-all duration-300 ${color.bg} ${warning ? 'animate-pulse' : ''} hover:scale-110`}
                title="Token quota"
            >
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
            </button>
        </div>
    );
}
```

- [ ] **Step 2: Commit**

```bash
git add src/components/ui/QuotaWidget.jsx
git commit -m "feat(quota): add collapsible QuotaWidget component"
```

---

### Task 11: ChatPage — Integrate QuotaWidget + Block UI (`src/pages/ChatPage.jsx`)

**Files:**
- Modify: `src/pages/ChatPage.jsx`
- Modify: `src/components/ChatInput.jsx`

- [ ] **Step 1: Add quota state and fetch to ChatPage**

Add import at top of `ChatPage.jsx` (after line 12):

```javascript
import QuotaWidget from '../components/ui/QuotaWidget';
import apiService from '../services/apiService';
```

Add quota state after line 30 (after `calledAgent` state):

```javascript
    const [quotaStatus, setQuotaStatus] = useState(null);
    const [quotaWarning, setQuotaWarning] = useState(false);
    const [quotaBlocked, setQuotaBlocked] = useState(false);
```

Add effect to fetch quota on mount/conversation change (after the `activeConversationId` useEffect, around line 66):

```javascript
    useEffect(() => {
        const fetchQuota = async () => {
            try {
                const status = await apiService.get(`/quota/status?conversationId=${activeConversationId || ''}`);
                setQuotaStatus(status);
                setQuotaBlocked(!status.allowed);
                setQuotaWarning(status.warning);
            } catch (error) {
                logger.error('Error fetching quota:', error);
            }
        };
        fetchQuota();
    }, [activeConversationId]);
```

- [ ] **Step 2: Add onQuota callback in handleSendMessage**

In the `handleSendMessage` function, add an `onQuota` handler to the `streamingService.sendMessage` call. Replace lines 265-291:

```javascript
            await streamingService.sendMessage(
                messageText,
                currentId,
                (chunk) => setStreamingMessage(prev => prev + chunk),
                (fullResponse) => {
                    const aiMessage = {
                        role: 'assistant',
                        content: fullResponse,
                        createdAt: new Date().toISOString()
                    };
                    setMessages(prev => [...prev, aiMessage]);
                    setStreamingMessage('');
                    setIsTyping(false);

                    if (currentId) {
                        setTimeout(() => loadConversations(), 2500);
                    }
                },
                (error) => {
                    logger.error('Stream error:', error);
                    setIsTyping(false);
                    setStreamingMessage('');
                },
                (taskId) => {
                    handleAgentTask(taskId, currentId);
                },
                (quota, exceeded) => {
                    setQuotaStatus(quota);
                    setQuotaWarning(quota.warning);
                    setQuotaBlocked(!quota.allowed);
                    if (exceeded) {
                        setIsTyping(false);
                    }
                }
            );
```

- [ ] **Step 3: Add QuotaWidget and blocked overlay to JSX**

In the return JSX, add before the closing `</div>` (before line 366):

```jsx
            <QuotaWidget quota={quotaStatus} warning={quotaWarning} />
```

Update the ChatInput line (line 364) to pass `quotaBlocked`:

```jsx
            <ChatInput onSend={handleSendMessage} disabled={isTyping || quotaBlocked} quotaBlocked={quotaBlocked} />
```

- [ ] **Step 4: Update ChatInput to show blocked message**

In `src/components/ChatInput.jsx`, update the component signature (line 39):

```jsx
export default function ChatInput({ onSend, disabled = false, quotaBlocked = false }) {
```

Add a blocked overlay inside the component return, after the `data-placeholder` div and before the send button (after line 202):

```jsx
                    {quotaBlocked && (
                        <div className="absolute inset-0 flex items-center justify-center bg-white/80 rounded-3xl z-10">
                            <span className="text-sm text-red-600 font-medium">
                                Quota exceeded. Please wait for reset.
                            </span>
                        </div>
                    )}
```

Update the wrapper div (line 170) to add `relative`:

```jsx
                <div className="relative flex items-end space-x-2 bg-white border border-border rounded-3xl shadow-lg p-2 transition-shadow hover:shadow-xl">
```

- [ ] **Step 5: Commit**

```bash
git add src/pages/ChatPage.jsx src/components/ChatInput.jsx
git commit -m "feat(quota): integrate QuotaWidget and block UI in ChatPage"
```

---

### Task 12: Add Environment Variables to `.env.example`

**Files:**
- Modify: `server/.env.example` (or `.env.example` at root)

- [ ] **Step 1: Add quota env vars**

Add this section to the `.env.example` file:

```env
# Token Quota
TOKEN_SESSION_LIMIT=500000
TOKEN_SESSION_DURATION=7200
TOKEN_WEEKLY_LIMIT=5000000
TOKEN_WARNING_THRESHOLD=0.9
```

- [ ] **Step 2: Commit**

```bash
git add server/.env.example
git commit -m "feat(quota): add token quota env vars to .env.example"
```

---

### Task 13: End-to-End Verification

- [ ] **Step 1: Start backend and verify quota endpoint**

```bash
cd server && source ../.venv/Scripts/activate && python main.py
```

Test the quota endpoint:
```bash
curl -H "Authorization: Bearer <token>" "http://localhost:3000/api/v1/quota/status?conversationId=test"
```

Expected: JSON with `allowed`, `session`, `weekly`, `warning` fields.

- [ ] **Step 2: Send a chat message and verify quota SSE event**

Send a message via the frontend. Check:
- Stream response includes quota data in the `done` event
- QuotaWidget appears at bottom-right
- Clicking widget shows session + weekly progress bars
- Console logs show `[TOKEN_SOURCE: api_usage]` or `[TOKEN_SOURCE: tiktoken_fallback]`

- [ ] **Step 3: Verify quota enforcement**

Set `TOKEN_SESSION_LIMIT=100` temporarily in `.env` and restart server. Send a message. After the limit is reached:
- Next message should return `quotaExceeded: true`
- ChatInput should be disabled with "Quota exceeded" overlay
- QuotaWidget should auto-expand with red progress bars

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(quota): token quota management system complete"
```
