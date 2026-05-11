# Auto RAG Detection + Inline DocRef Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tự động phát hiện tài liệu liên quan đến câu hỏi của user và inject context vào prompt mà không cần client truyền `documentIds`; đồng thời yêu cầu LLM tự chèn `<docref>` inline khi trích dẫn tài liệu.

**Architecture:** Sau khi document được indexed xong và summary được tạo, embed summary đó vào Qdrant collection `doc_index_{userId}`. Khi user gửi message, tìm kiếm collection này để xác định tài liệu liên quan (score ≥ 0.6), rồi chạy chunk-level RAG trên các tài liệu đó. System prompt được bổ sung danh sách tài liệu và instruction để LLM tự tạo `<docref>` tag inline.

**Tech Stack:** Python asyncpg, Qdrant AsyncQdrantClient, FastAPI, tiktoken, React + streamingService.js

---

## File Map

| File | Action | Trách nhiệm |
|------|--------|-------------|
| `server/modules/rag/simpleRagProvider.py` | Modify | Thêm `upsertDocumentIndex`, `searchDocumentIndex`, `deleteDocumentIndex` |
| `server/modules/rag/ragService.py` | Modify | Expose 3 method mới qua facade + `LightRagAdapter` stub |
| `server/modules/knowledge/service.py` | Modify | Gọi `upsertDocumentIndex` sau khi summary xong; gọi `deleteDocumentIndex` khi xóa doc |
| `server/modules/message/service.py` | Modify | Thêm bước auto-detect + build docref instruction trong system prompt |

---

## Task 1: Thêm document-index methods vào `SimpleRagProvider`

**Files:**
- Modify: `server/modules/rag/simpleRagProvider.py`

Ba method mới sử dụng collection `doc_index_{userId}`:
- `upsertDocumentIndex(userId, documentId, filename, summary)` — embed summary, lưu vào Qdrant
- `searchDocumentIndex(userId, query, limit, threshold)` → `List[dict]` với `documentId`, `filename`, `score`
- `deleteDocumentIndex(userId, documentId)` — xóa điểm khỏi collection

- [ ] **Step 1: Thêm 3 methods vào cuối class `SimpleRagProvider` (trước dòng cuối `simpleRagProvider = SimpleRagProvider()`)**

Mở `server/modules/rag/simpleRagProvider.py`, thêm sau method `deleteMemoryVector` (dòng 269), trước dòng cuối:

```python
    async def upsertDocumentIndex(
        self, userId: str, documentId: str, filename: str, summary: str
    ) -> None:
        try:
            collName = self._collectionName(f"doc_index_{userId}")
            await self._ensureCollection(collName)
            client = await self._getClient()
            vector = await embeddingService.embed(summary)
            await client.upsert(
                collection_name=collName,
                points=[
                    PointStruct(
                        id=documentId,
                        vector=vector,
                        payload={
                            "documentId": documentId,
                            "filename": filename,
                            "userId": userId,
                        },
                    )
                ],
            )
            logger.info(f"SimpleRagProvider: upserted doc index for document {documentId}")
        except Exception as e:
            logger.error(f"SimpleRagProvider.upsertDocumentIndex failed for document {documentId}: {e}")

    async def searchDocumentIndex(
        self, userId: str, query: str, limit: int = 10, threshold: float = 0.6
    ) -> List[Dict]:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"doc_index_{userId}")
            queryVector = await embeddingService.embed(query)
            results = await client.search(
                collection_name=collName,
                query_vector=queryVector,
                limit=limit,
                with_payload=True,
                score_threshold=threshold,
            )
            return [
                {
                    "documentId": r.payload.get("documentId"),
                    "filename": r.payload.get("filename"),
                    "score": r.score,
                }
                for r in results
                if r.payload.get("documentId")
            ]
        except Exception as e:
            logger.warning(f"SimpleRagProvider.searchDocumentIndex failed for user {userId}: {e}")
            return []

    async def deleteDocumentIndex(self, userId: str, documentId: str) -> None:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"doc_index_{userId}")
            await client.delete(
                collection_name=collName,
                points_selector=PointIdsList(points=[documentId]),
            )
            logger.info(f"SimpleRagProvider: deleted doc index for document {documentId}")
        except Exception as e:
            logger.error(f"SimpleRagProvider.deleteDocumentIndex failed for document {documentId}: {e}")
```

- [ ] **Step 2: Kiểm tra cú pháp**

```bash
cd server && python -c "from modules.rag.simpleRagProvider import simpleRagProvider; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/modules/rag/simpleRagProvider.py
git commit -m "feat(rag): add document-level index methods to SimpleRagProvider"
```

---

## Task 2: Expose methods mới qua `RagService` facade

**Files:**
- Modify: `server/modules/rag/ragService.py`

- [ ] **Step 1: Thêm stub vào `LightRagAdapter` (sau method `deleteMemoryVector`, trước class `RagService`)**

Thêm vào cuối class `LightRagAdapter` (dòng ~127, trước `class RagService`):

```python
    async def upsertDocumentIndex(
        self, userId: str, documentId: str, filename: str, summary: str
    ) -> None:
        logger.debug("LightRagAdapter.upsertDocumentIndex: not supported, skipping")

    async def searchDocumentIndex(
        self, userId: str, query: str, limit: int = 10, threshold: float = 0.6
    ) -> List[Dict]:
        return []

    async def deleteDocumentIndex(self, userId: str, documentId: str) -> None:
        logger.debug("LightRagAdapter.deleteDocumentIndex: not supported, skipping")
```

- [ ] **Step 2: Thêm 3 method vào class `RagService` (sau `deleteMemoryVector`)**

```python
    async def upsertDocumentIndex(
        self, userId: str, documentId: str, filename: str, summary: str
    ) -> None:
        return await self._provider.upsertDocumentIndex(userId, documentId, filename, summary)

    async def searchDocumentIndex(
        self, userId: str, query: str, limit: int = 10, threshold: float = 0.6
    ) -> List[Dict]:
        return await self._provider.searchDocumentIndex(userId, query, limit=limit, threshold=threshold)

    async def deleteDocumentIndex(self, userId: str, documentId: str) -> None:
        return await self._provider.deleteDocumentIndex(userId, documentId)
```

- [ ] **Step 3: Kiểm tra cú pháp**

```bash
cd server && python -c "from modules.rag.ragService import ragService; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/modules/rag/ragService.py
git commit -m "feat(rag): expose document-index methods via RagService facade"
```

---

## Task 3: Upsert doc index sau khi summary được tạo

**Files:**
- Modify: `server/modules/knowledge/service.py`

Sau khi `_generateSummary` lưu summary thành công, gọi `ragService.upsertDocumentIndex` để index document-level vector. Đồng thời, khi xóa document, gọi `deleteDocumentIndex`.

- [ ] **Step 1: Sửa `_generateSummary` — thêm upsert sau khi lưu summary**

Tìm đoạn trong `_generateSummary` (dòng ~162):
```python
            await documentRepository.updateSummary(
                documentId, "completed", summary=response
            )
            logger.info(f"_generateSummary completed for {documentId}")
```

Thay bằng:
```python
            await documentRepository.updateSummary(
                documentId, "completed", summary=response
            )
            logger.info(f"_generateSummary completed for {documentId}")
            doc = await documentRepository.getById(documentId)
            if doc:
                asyncio.create_task(
                    ragService.upsertDocumentIndex(
                        userId=doc.get("userId", ""),
                        documentId=documentId,
                        filename=doc.get("filename", ""),
                        summary=response,
                    )
                )
```

- [ ] **Step 2: Sửa `deleteDocument` — thêm deleteDocumentIndex**

Tìm đoạn trong `deleteDocument` (dòng ~258):
```python
        try:
            await ragService.deleteDocumentChunks(ownerId, documentId)
        except Exception as e:
            logger.error(f"deleteDocument RAG cleanup failed for {documentId}: {e}")
        return True
```

Thay bằng:
```python
        try:
            await ragService.deleteDocumentChunks(ownerId, documentId)
        except Exception as e:
            logger.error(f"deleteDocument RAG cleanup failed for {documentId}: {e}")
        try:
            doc = await documentRepository.getById(documentId)
            docUserId = doc.get("userId", userId) if doc else userId
            await ragService.deleteDocumentIndex(docUserId, documentId)
        except Exception as e:
            logger.error(f"deleteDocument doc-index cleanup failed for {documentId}: {e}")
        return True
```

**Lưu ý:** `deleteDocument` được gọi sau khi record đã bị xóa khỏi DB, nên cần fetch trước khi delete. Kiểm tra lại thứ tự trong method gốc — nếu `documentRepository.delete` xóa trước, thì ta cần fetch userId từ kết quả trả về của delete, không phải từ getById. Xem thực tế:

```python
        result = await documentRepository.delete(documentId, userId)
        if result is None:
            return False
        filePath, ownerId = result
```

`documentRepository.delete` trả về `(filePath, ownerId)` — không có `userId`. Vậy dùng tham số `userId` truyền vào hàm là đủ:

```python
        try:
            await ragService.deleteDocumentIndex(userId, documentId)
        except Exception as e:
            logger.error(f"deleteDocument doc-index cleanup failed for {documentId}: {e}")
        return True
```

- [ ] **Step 3: Kiểm tra cú pháp**

```bash
cd server && python -c "from modules.knowledge.service import documentService; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/modules/knowledge/service.py
git commit -m "feat(knowledge): upsert/delete document-level Qdrant index on summary complete and doc delete"
```

---

## Task 4: Auto-detect tài liệu liên quan trong `MessageService`

**Files:**
- Modify: `server/modules/message/service.py`

Thêm bước tự động phát hiện tài liệu liên quan khi client **không** truyền `documentIds`. Kết quả được dùng để:
1. Chạy chunk-level RAG trên các tài liệu phát hiện được
2. Build danh sách tài liệu cho instruction `<docref>`

- [ ] **Step 1: Thêm bước auto-detect vào `processMessageFlow`**

Tìm đoạn sau dòng khởi tạo `documentContext = ""` (dòng ~87 trong service.py):

```python
        documentContext = ""
        if documentIds:
            try:
                documentContext, documentSources = await documentService.searchDocumentContext(
                    documentIds, userId, content
                )
            except Exception as e:
                logger.warning(f"processMessageFlow: searchDocumentContext failed for userId {userId}: {e}")
```

Thay bằng:

```python
        documentContext = ""
        autoDetectedDocs: List[Dict] = []

        if documentIds:
            try:
                documentContext, documentSources = await documentService.searchDocumentContext(
                    documentIds, userId, content
                )
            except Exception as e:
                logger.warning(f"processMessageFlow: searchDocumentContext failed for userId {userId}: {e}")
        else:
            try:
                autoDetectedDocs = await ragService.searchDocumentIndex(userId, content, limit=5, threshold=0.6)
                if autoDetectedDocs:
                    detectedIds = [d["documentId"] for d in autoDetectedDocs]
                    logger.info(f"[AutoRAG] Detected {len(detectedIds)} relevant docs for user {userId}: {[d['filename'] for d in autoDetectedDocs]}")
                    documentContext, documentSources = await documentService.searchDocumentContext(
                        detectedIds, userId, content
                    )
            except Exception as e:
                logger.warning(f"processMessageFlow: auto-detect documents failed for userId {userId}: {e}")
```

- [ ] **Step 2: Kiểm tra cú pháp**

```bash
cd server && python -c "from modules.message.service import messageService; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/modules/message/service.py
git commit -m "feat(message): auto-detect relevant documents via doc-index semantic search"
```

---

## Task 5: Thêm `<docref>` instruction vào system prompt

**Files:**
- Modify: `server/modules/message/service.py`

Khi có `ragContext` hoặc `documentContext`, thêm vào system prompt:
1. Danh sách tài liệu hiện có (từ `ragSources + documentSources + autoDetectedDocs`)
2. Instruction để LLM dùng `<docref>` khi trích dẫn

- [ ] **Step 1: Thêm helper function `_buildDocrefInstruction` vào class `MessageService`**

Thêm static method sau `buildUsageDict` (dòng ~50):

```python
    @staticmethod
    def _buildDocrefInstruction(sources: List[Dict]) -> str:
        if not sources:
            return ""
        seen = set()
        unique = []
        for s in sources:
            key = s.get("filename", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(s)
        if not unique:
            return ""
        lines = []
        for s in unique:
            docId = s.get("documentId", "")
            filename = s.get("filename", "")
            entry = f'- file="{filename}"' + (f' docId="{docId}"' if docId else "")
            lines.append(entry)
        docList = "\n".join(lines)
        return (
            "\n\nWhen your answer references content from a document listed below, "
            "cite it inline using this XML tag:\n"
            '  <docref file="filename" docId="id" page="N">cited text</docref>\n'
            "Use page attribute only when you know the page number from the context. "
            "Available documents:\n"
            f"{docList}"
        )
```

- [ ] **Step 2: Sửa phần build `systemPrompt` — gọi `_buildDocrefInstruction`**

Tìm đoạn (dòng ~99):
```python
        systemPrompt = "You are a helpful AI assistant."
        if ragContext:
            systemPrompt += f"\n\nRelevant Context:\n{ragContext}"
        if documentContext:
            systemPrompt += f"\n\nDocument Context:\n{documentContext}"
        if memoryText:
            systemPrompt += f"\n\nKnown about this user:\n{memoryText}"
```

Thay bằng:

```python
        systemPrompt = "You are a helpful AI assistant."
        if ragContext:
            systemPrompt += f"\n\nRelevant Context:\n{ragContext}"
        if documentContext:
            systemPrompt += f"\n\nDocument Context:\n{documentContext}"
        if memoryText:
            systemPrompt += f"\n\nKnown about this user:\n{memoryText}"

        allDocMeta = [
            {"filename": s.get("filename"), "documentId": s.get("documentId")}
            for s in (ragSources + documentSources)
            if s.get("filename")
        ]
        for d in autoDetectedDocs:
            if d.get("filename") not in {m.get("filename") for m in allDocMeta}:
                allDocMeta.append({"filename": d.get("filename"), "documentId": d.get("documentId")})

        docrefInstruction = self._buildDocrefInstruction(allDocMeta)
        if docrefInstruction:
            systemPrompt += docrefInstruction
```

**Lưu ý:** `ragSources` hiện chỉ có `filename` và `pageNumber`, không có `documentId`. Cần sửa phần build `ragSources` để bao gồm `documentId`:

Tìm đoạn (dòng ~76):
```python
                ragSources = [
                    {
                        "filename": r.document.metadata.get("filename"),
                        "pageNumber": r.document.metadata.get("pageNumber"),
                    }
                    for r in results
                    if r.document.metadata.get("filename")
                ]
```

Thay bằng:
```python
                ragSources = [
                    {
                        "filename": r.document.metadata.get("filename"),
                        "pageNumber": r.document.metadata.get("pageNumber"),
                        "documentId": r.document.metadata.get("documentId"),
                    }
                    for r in results
                    if r.document.metadata.get("filename")
                ]
```

Tương tự `documentSources` trong `searchDocumentContext` — đã có `filename` và `pageNumber`. Sửa trong `knowledge/service.py` dòng ~219:
```python
                sources = [
                    {
                        "filename": r.document.metadata.get("filename"),
                        "pageNumber": r.document.metadata.get("pageNumber"),
                        "documentId": r.document.metadata.get("documentId"),
                    }
                    for r in results
                ]
```

Và fallback dòng ~237:
```python
                        sources.append({
                            "filename": doc.get("filename"),
                            "pageNumber": None,
                            "documentId": docId,
                        })
```

- [ ] **Step 3: Kiểm tra cú pháp toàn bộ**

```bash
cd server && python -c "
from modules.rag.simpleRagProvider import simpleRagProvider
from modules.rag.ragService import ragService
from modules.knowledge.service import documentService
from modules.message.service import messageService
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 4: Commit**

```bash
git add server/modules/message/service.py server/modules/knowledge/service.py
git commit -m "feat(message): inject docref instruction + document metadata into system prompt"
```

---

## Task 6: Backfill doc index cho tài liệu đã tồn tại

Documents đã upload trước khi có tính năng này không có entry trong `doc_index_{userId}`. Cần chạy một lần backfill.

**Files:**
- Create: `server/scripts/backfillDocIndex.py`

- [ ] **Step 1: Tạo script backfill**

```python
"""One-time script: backfill doc_index for all existing documents that have a summary."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=str(Path(__file__).parent.parent / ".env"))

from config.database import db
from modules.rag.ragService import ragService


async def backfill():
    await db.connect()
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, "userId", filename, summary
               FROM documents
               WHERE summary IS NOT NULL AND summary != ''
               ORDER BY "createdAt" ASC"""
        )
    print(f"Found {len(rows)} documents with summaries to backfill")
    for row in rows:
        try:
            await ragService.upsertDocumentIndex(
                userId=str(row["userId"]),
                documentId=str(row["id"]),
                filename=row["filename"],
                summary=row["summary"],
            )
            print(f"  OK: {row['filename']} ({row['id']})")
        except Exception as e:
            print(f"  FAIL: {row['filename']} ({row['id']}): {e}")
    await db.disconnect()
    print("Backfill complete.")


asyncio.run(backfill())
```

- [ ] **Step 2: Chạy backfill**

```bash
cd server
.venv\Scripts\activate   # Windows
python scripts/backfillDocIndex.py
```

Expected output:
```
Found N documents with summaries to backfill
  OK: document1.pdf (uuid...)
  OK: report.docx (uuid...)
Backfill complete.
```

- [ ] **Step 3: Commit**

```bash
git add server/scripts/backfillDocIndex.py
git commit -m "chore(scripts): add one-time backfill script for doc-index"
```

---

## Self-Review

### Spec Coverage

| Yêu cầu | Task |
|---------|------|
| Tự động phát hiện tài liệu liên quan | Task 1 (Qdrant index) + Task 3 (upsert on summary) + Task 4 (auto-detect in flow) |
| Không cần client truyền documentIds | Task 4 (`else` branch trong processMessageFlow) |
| LLM chèn `<docref>` inline | Task 5 (instruction trong system prompt) |
| Tài liệu cũ được index | Task 6 (backfill script) |
| Xóa document dọn dẹp index | Task 3 (deleteDocumentIndex trong deleteDocument) |
| documentId có trong sources | Task 5 (sửa ragSources + documentSources) |

### Potential Issues

1. **`autoDetectedDocs` chưa được khai báo khi `documentIds` được truyền** — trong Task 4, `autoDetectedDocs` chỉ được set trong `else` branch. Trong `if documentIds` branch, cần khởi tạo `autoDetectedDocs = []` ở đầu (đã được làm trong Task 4 Step 1: `autoDetectedDocs: List[Dict] = []`).

2. **LightRagAdapter stubs** — không raise exception, chỉ log debug và return `[]` — đúng hành vi graceful degradation.

3. **Score threshold 0.6** — có thể điều chỉnh qua env var nếu cần (`DOC_INDEX_THRESHOLD`). Không thêm vào plan này vì YAGNI.
