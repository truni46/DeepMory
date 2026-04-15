# RAG Pipeline Complete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the RAG indexing and retrieval pipeline — page-aware chunking with source metadata, hybrid document search, and `__SOURCES__` SSE marker for frontend citation display.

**Architecture:** A new `documentParser.py` handles file-to-page extraction (PDF via `pymupdf4llm`, others via existing libs). `simpleRagProvider.py` gains page-aware chunking that stores `filename`/`pageNumber` in Qdrant payloads and a new `searchContextByDocumentIds` method. The message service collects sources from both search paths and yields them as a `__SOURCES__` SSE marker after the response.

**Tech Stack:** Python, Qdrant (`qdrant-client`), `pymupdf4llm`, `python-docx`, `openpyxl`, `pytest`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `server/modules/rag/documentParser.py` | **Create** | Parse any file type → `List[ParsedPage]` |
| `server/modules/rag/simpleRagProvider.py` | **Modify** | Page-aware indexing; extended metadata; `searchContextByDocumentIds` |
| `server/modules/rag/ragService.py` | **Modify** | Expose `searchContextByDocumentIds` on public facade |
| `server/modules/knowledge/service.py` | **Modify** | Fix real `chunkCount`; replace `getDocumentContext` with `searchDocumentContext` |
| `server/modules/message/service.py` | **Modify** | Use `searchDocumentContext`; collect + yield `__SOURCES__` marker |
| `server/tests/rag/test_documentParser.py` | **Create** | Unit tests for parser |
| `server/tests/rag/test_simpleRagProvider.py` | **Create** | Unit tests for chunking logic |
| `server/tests/knowledge/test_service.py` | **Modify** | Tests for `searchDocumentContext` |

---

## Task 1: Install `pymupdf4llm`

**Files:**
- Run: install in project venv

- [ ] **Step 1: Activate venv and install**

```bash
cd server
.venv\Scripts\activate
pip install pymupdf4llm
```

Expected output: `Successfully installed pymupdf4llm-...`

- [ ] **Step 2: Verify import works**

```bash
python -c "import pymupdf4llm; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: install pymupdf4llm for page-aware PDF parsing"
```

---

## Task 2: Create `documentParser.py`

**Files:**
- Create: `server/modules/rag/documentParser.py`
- Create: `server/tests/rag/__init__.py`
- Create: `server/tests/rag/test_documentParser.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/rag/__init__.py` (empty).

Create `server/tests/rag/test_documentParser.py`:

```python
# server/tests/rag/test_documentParser.py
import os
import tempfile
import pytest


def test_parsedPage_has_text_and_pageNumber():
    from modules.rag.documentParser import ParsedPage
    p = ParsedPage(text="hello", pageNumber=1)
    assert p.text == "hello"
    assert p.pageNumber == 1


def test_parsedPage_pageNumber_can_be_none():
    from modules.rag.documentParser import ParsedPage
    p = ParsedPage(text="hello", pageNumber=None)
    assert p.pageNumber is None


def test_textParser_reads_plain_file():
    from modules.rag.documentParser import TextParser
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("line one\nline two")
        path = f.name
    try:
        pages = TextParser().parse(path)
        assert len(pages) == 1
        assert "line one" in pages[0].text
        assert pages[0].pageNumber is None
    finally:
        os.unlink(path)


def test_textParser_empty_file_returns_empty():
    from modules.rag.documentParser import TextParser
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("   ")
        path = f.name
    try:
        pages = TextParser().parse(path)
        assert pages == []
    finally:
        os.unlink(path)


def test_documentParserService_dispatches_txt():
    from modules.rag.documentParser import documentParserService, TextParser
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("content")
        path = f.name
    try:
        pages = documentParserService.parse(path)
        assert len(pages) == 1
    finally:
        os.unlink(path)


def test_documentParserService_dispatches_md():
    from modules.rag.documentParser import documentParserService
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# Heading\ncontent")
        path = f.name
    try:
        pages = documentParserService.parse(path)
        assert len(pages) == 1
        assert "content" in pages[0].text
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server
python -m pytest tests/rag/test_documentParser.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` (file doesn't exist yet)

- [ ] **Step 3: Create `documentParser.py`**

Create `server/modules/rag/documentParser.py`:

```python
# server/modules/rag/documentParser.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional

from config.logger import logger


@dataclass
class ParsedPage:
    text: str
    pageNumber: Optional[int]


class PdfParser:
    def parse(self, filePath: str) -> List[ParsedPage]:
        try:
            import pymupdf4llm
            chunks = pymupdf4llm.to_markdown(filePath, page_chunks=True)
            pages = []
            for chunk in chunks:
                text = chunk.get("text", "")
                pageNum = chunk.get("metadata", {}).get("page", 0) + 1
                if text.strip():
                    pages.append(ParsedPage(text=text, pageNumber=pageNum))
            return pages
        except Exception as e:
            logger.error(f"PdfParser.parse failed for '{filePath}': {e}")
            return []


class DocxParser:
    def parse(self, filePath: str) -> List[ParsedPage]:
        try:
            import docx
            doc = docx.Document(filePath)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return [ParsedPage(text=text, pageNumber=None)] if text.strip() else []
        except Exception as e:
            logger.error(f"DocxParser.parse failed for '{filePath}': {e}")
            return []


class XlsxParser:
    def parse(self, filePath: str) -> List[ParsedPage]:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(filePath, read_only=True, data_only=True)
            pages = []
            for sheetName in wb.sheetnames:
                ws = wb[sheetName]
                rows = []
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c) if c is not None else "" for c in row]
                    rows.append(" | ".join(cells))
                text = "\n".join(r for r in rows if r.strip())
                if text.strip():
                    pages.append(ParsedPage(text=text, pageNumber=None))
            return pages
        except Exception as e:
            logger.error(f"XlsxParser.parse failed for '{filePath}': {e}")
            return []


class TextParser:
    def parse(self, filePath: str) -> List[ParsedPage]:
        try:
            with open(filePath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            return [ParsedPage(text=text, pageNumber=None)] if text.strip() else []
        except Exception as e:
            logger.error(f"TextParser.parse failed for '{filePath}': {e}")
            return []


class DocumentParserService:
    def __init__(self):
        self._parsers = {
            ".pdf": PdfParser(),
            ".docx": DocxParser(),
            ".doc": DocxParser(),
            ".xlsx": XlsxParser(),
            ".xls": XlsxParser(),
        }
        self._default = TextParser()

    def parse(self, filePath: str) -> List[ParsedPage]:
        ext = os.path.splitext(filePath)[1].lower()
        parser = self._parsers.get(ext, self._default)
        return parser.parse(filePath)


documentParserService = DocumentParserService()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd server
python -m pytest tests/rag/test_documentParser.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/modules/rag/documentParser.py server/tests/rag/
git commit -m "feat(rag): add documentParser with page-aware PDF/DOCX/XLSX/text support"
```

---

## Task 3: Update `simpleRagProvider.py` — page-aware indexing + extended metadata

**Files:**
- Modify: `server/modules/rag/simpleRagProvider.py`
- Create: `server/tests/rag/test_simpleRagProvider.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/rag/test_simpleRagProvider.py`:

```python
# server/tests/rag/test_simpleRagProvider.py
import pytest
from modules.rag.documentParser import ParsedPage


def test_chunkPages_basic_split():
    from modules.rag.simpleRagProvider import _chunkPages
    pages = [ParsedPage(text="a" * 1000, pageNumber=1)]
    chunks = _chunkPages(pages, chunkSize=300, overlap=50)
    assert len(chunks) > 1
    assert all(c["pageNumber"] == 1 for c in chunks)


def test_chunkPages_preserves_pageNumber_none():
    from modules.rag.simpleRagProvider import _chunkPages
    pages = [ParsedPage(text="hello world", pageNumber=None)]
    chunks = _chunkPages(pages, chunkSize=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0]["pageNumber"] is None


def test_chunkPages_assigns_sequential_chunkIndex():
    from modules.rag.simpleRagProvider import _chunkPages
    pages = [
        ParsedPage(text="a" * 500, pageNumber=1),
        ParsedPage(text="b" * 500, pageNumber=2),
    ]
    chunks = _chunkPages(pages, chunkSize=300, overlap=50)
    indices = [c["chunkIndex"] for c in chunks]
    assert indices == list(range(len(chunks)))


def test_chunkPages_skips_empty_pages():
    from modules.rag.simpleRagProvider import _chunkPages
    pages = [
        ParsedPage(text="   ", pageNumber=1),
        ParsedPage(text="real content", pageNumber=2),
    ]
    chunks = _chunkPages(pages, chunkSize=800, overlap=100)
    assert len(chunks) == 1
    assert chunks[0]["pageNumber"] == 2


def test_chunkPages_empty_input_returns_empty():
    from modules.rag.simpleRagProvider import _chunkPages
    assert _chunkPages([]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server
python -m pytest tests/rag/test_simpleRagProvider.py -v
```

Expected: `ImportError: cannot import name '_chunkPages'`

- [ ] **Step 3: Replace `_readFile` and `_chunkText` with page-aware versions in `simpleRagProvider.py`**

Remove the `_readFile` function entirely (lines 24–41) and replace `_chunkText` (lines 43–51) with:

```python
from modules.rag.documentParser import ParsedPage, documentParserService


def _chunkPages(pages: List[ParsedPage], chunkSize: int = 800, overlap: int = 100) -> List[dict]:
    chunks = []
    chunkIndex = 0
    for page in pages:
        text = page.text
        if not text.strip():
            continue
        start = 0
        while start < len(text):
            chunkText = text[start:start + chunkSize]
            if chunkText.strip():
                chunks.append({
                    "text": chunkText,
                    "pageNumber": page.pageNumber,
                    "chunkIndex": chunkIndex,
                })
                chunkIndex += 1
            start += chunkSize - overlap
    return chunks
```

Also add `MatchAny` to the qdrant imports at the top:

```python
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchAny,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)
```

- [ ] **Step 4: Update the `index` method**

Replace the `index` method body (starting at line 84) with:

```python
    async def index(self, filePath: str, projectId: str, documentId: str, userId: str) -> int:
        try:
            pages = documentParserService.parse(filePath)
            if not pages:
                logger.warning(f"SimpleRagProvider: no content extracted from '{filePath}'")
                return 0
            chunks = _chunkPages(pages)
            if not chunks:
                return 0
            texts = [c["text"] for c in chunks]
            vectors = await embeddingService.embedBatch(texts)
            collName = self._collectionName(f"project_{projectId}")
            await self._ensureCollection(collName)
            client = await self._getClient()
            filename = os.path.basename(filePath)
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectors[i],
                    payload={
                        "documentId": documentId,
                        "userId": userId,
                        "filename": filename,
                        "filePath": filePath,
                        "pageNumber": chunks[i]["pageNumber"],
                        "chunkIndex": chunks[i]["chunkIndex"],
                        "text": chunks[i]["text"],
                    },
                )
                for i in range(len(chunks))
            ]
            await client.upsert(collection_name=collName, points=points)
            logger.info(f"SimpleRagProvider: indexed {len(points)} chunks for document {documentId}")
            return len(points)
        except Exception as e:
            logger.error(f"SimpleRagProvider.index failed for document {documentId}: {e}")
            raise
```

- [ ] **Step 5: Update `searchContext` to return `filename` and `pageNumber` in metadata**

Replace the return list comprehension inside `searchContext` (the `return [...]` block):

```python
            return [
                SearchResult(
                    document=Document(
                        id=r.payload.get("documentId", str(uuid.uuid4())),
                        content=r.payload.get("text", ""),
                        metadata={
                            "documentId": r.payload.get("documentId"),
                            "chunkIndex": r.payload.get("chunkIndex"),
                            "filename": r.payload.get("filename"),
                            "pageNumber": r.payload.get("pageNumber"),
                        },
                    ),
                    score=r.score,
                )
                for r in results
                if r.payload.get("text")
            ]
```

- [ ] **Step 6: Add `searchContextByDocumentIds` method to `SimpleRagProvider`**

Add this method after `searchContext`:

```python
    async def searchContextByDocumentIds(
        self, query: str, namespace: str, documentIds: List[str], limit: int = 5
    ) -> List[SearchResult]:
        try:
            client = await self._getClient()
            collName = self._collectionName(f"project_{namespace}")
            queryVector = await embeddingService.embed(query)
            results = await client.search(
                collection_name=collName,
                query_vector=queryVector,
                limit=limit,
                with_payload=True,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key="documentId",
                            match=MatchAny(any=documentIds),
                        )
                    ]
                ),
            )
            return [
                SearchResult(
                    document=Document(
                        id=r.payload.get("documentId", str(uuid.uuid4())),
                        content=r.payload.get("text", ""),
                        metadata={
                            "documentId": r.payload.get("documentId"),
                            "chunkIndex": r.payload.get("chunkIndex"),
                            "filename": r.payload.get("filename"),
                            "pageNumber": r.payload.get("pageNumber"),
                        },
                    ),
                    score=r.score,
                )
                for r in results
                if r.payload.get("text")
            ]
        except Exception as e:
            logger.warning(f"SimpleRagProvider.searchContextByDocumentIds failed for namespace {namespace}: {e}")
            return []
```

- [ ] **Step 7: Run tests**

```bash
cd server
python -m pytest tests/rag/test_simpleRagProvider.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 8: Commit**

```bash
git add server/modules/rag/simpleRagProvider.py server/tests/rag/test_simpleRagProvider.py
git commit -m "feat(rag): page-aware chunking with filename/page metadata; add searchContextByDocumentIds"
```

---

## Task 4: Expose `searchContextByDocumentIds` on `ragService.py` facade

**Files:**
- Modify: `server/modules/rag/ragService.py`

- [ ] **Step 1: Add stub to `LightRagAdapter`**

In `ragService.py`, add this method to `LightRagAdapter` after `searchContext`:

```python
    async def searchContextByDocumentIds(
        self, query: str, namespace: str, documentIds: List[str], limit: int = 5
    ) -> List[SearchResult]:
        # LightRAG does not support per-document filtering; return empty so caller falls back to full-text
        logger.warning("LightRagAdapter.searchContextByDocumentIds not supported — caller will use full-text fallback")
        return []
```

- [ ] **Step 2: Add method to `RagService` facade**

In `RagService`, add after `searchContext`:

```python
    async def searchContextByDocumentIds(
        self, query: str, namespace: str, documentIds: List[str], limit: int = 5
    ) -> List[SearchResult]:
        return await self._provider.searchContextByDocumentIds(
            query=query, namespace=namespace, documentIds=documentIds, limit=limit
        )
```

- [ ] **Step 3: Commit**

```bash
git add server/modules/rag/ragService.py
git commit -m "feat(rag): expose searchContextByDocumentIds on RagService facade"
```

---

## Task 5: Update `knowledge/service.py` — fix `chunkCount` + replace `getDocumentContext`

**Files:**
- Modify: `server/modules/knowledge/service.py`
- Modify: `server/tests/knowledge/test_service.py`

- [ ] **Step 1: Write failing tests**

Add to `server/tests/knowledge/test_service.py`:

```python
def test_chunkCount_placeholder():
    # Verifies the old hardcoded value is gone.
    # The actual count update is integration-tested; this confirms the constant is removed.
    import inspect
    from modules.knowledge import service
    source = inspect.getsource(service._processDocument if hasattr(service, '_processDocument') else service.DocumentService._processDocument)
    assert "chunkCount=1" not in source, "chunkCount must not be hardcoded to 1"


def test_searchDocumentContext_returns_tuple():
    # Smoke test: function exists and returns (str, list)
    import asyncio
    from unittest.mock import AsyncMock, patch, MagicMock
    from modules.knowledge.service import documentService

    mockDoc = {
        "id": "doc1",
        "userId": "user1",
        "ownerId": "user1",
        "filename": "test.pdf",
        "filePath": "/fake/path.pdf",
    }
    mockResults = []  # empty results → triggers fallback

    with patch("modules.knowledge.service.documentRepository.getById", new=AsyncMock(return_value=mockDoc)), \
         patch("modules.knowledge.service.ragService.searchContextByDocumentIds", new=AsyncMock(return_value=mockResults)), \
         patch("modules.knowledge.service.documentService.getDocument", new=AsyncMock(return_value=mockDoc)), \
         patch("modules.knowledge.service._readTextContent", return_value="some text"):
        result = asyncio.get_event_loop().run_until_complete(
            documentService.searchDocumentContext(["doc1"], "user1", "query")
        )

    contextText, sources = result
    assert isinstance(contextText, str)
    assert isinstance(sources, list)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd server
python -m pytest tests/knowledge/test_service.py -v
```

Expected: `test_chunkCount_placeholder` fails (hardcoded 1 still exists), `test_searchDocumentContext_returns_tuple` fails (function not found)

- [ ] **Step 3: Fix `chunkCount` in `_processDocument`**

In `service.py`, find `_processDocument` and change:

```python
# OLD
await documentRepository.updateEmbedding(
    documentId, "completed", chunkCount=1, pageCount=pageCount
)
```

to:

```python
# NEW
chunkCount = await ragService.index(filePath, ownerId, documentId, userId)
pageCount = _extractPageCount(filePath)
await documentRepository.updateEmbedding(
    documentId, "completed", chunkCount=chunkCount, pageCount=pageCount
)
```

Also remove the old `await ragService.index(...)` call that was before this block — it is now merged into the line above.

The updated `_processDocument` method should look like:

```python
    async def _processDocument(
        self, documentId: str, filePath: str, ownerId: str, userId: str
    ) -> None:
        try:
            await documentRepository.updateEmbedding(documentId, "processing")
            chunkCount = await ragService.index(filePath, ownerId, documentId, userId)
            pageCount = _extractPageCount(filePath)
            await documentRepository.updateEmbedding(
                documentId, "completed", chunkCount=chunkCount, pageCount=pageCount
            )
            logger.info(f"_processDocument completed for {documentId}")
            asyncio.create_task(self._generateSummary(documentId, filePath))
        except Exception as e:
            logger.error(f"_processDocument failed for {documentId}: {e}")
            await documentRepository.updateEmbedding(
                documentId, "failed", errorMsg=str(e)
            )
```

- [ ] **Step 4: Add `searchDocumentContext` method**

Add `documentRepository` import at the top of `service.py` — it is already imported via `from modules.knowledge.repository import documentRepository`.

Add this method to `DocumentService` class, replacing `getDocumentContext`:

```python
    async def searchDocumentContext(
        self, documentIds: List[str], userId: str, query: str
    ) -> tuple:
        """Returns (contextText, sources) using hybrid search (vector + full-text fallback)."""
        try:
            firstDoc = await documentRepository.getById(documentIds[0])
            namespace = firstDoc.get("ownerId", userId) if firstDoc else userId

            results = await ragService.searchContextByDocumentIds(
                query=query, namespace=namespace, documentIds=documentIds, limit=5
            )
            maxScore = max((r.score for r in results), default=0.0)

            if results and maxScore >= 0.5:
                contextText = "\n\n".join(r.document.content for r in results)
                sources = [
                    {
                        "filename": r.document.metadata.get("filename"),
                        "pageNumber": r.document.metadata.get("pageNumber"),
                    }
                    for r in results
                ]
                return contextText, sources

            # Fallback: full-text read
            parts = []
            sources = []
            for docId in documentIds:
                try:
                    doc = await self.getDocument(docId, userId)
                    if not doc:
                        continue
                    text = _readTextContent(doc["filePath"], maxChars=8000)
                    if text.strip():
                        parts.append(f"--- Document: {doc.get('filename', docId)} ---\n{text}")
                        sources.append({"filename": doc.get("filename"), "pageNumber": None})
                except Exception as e:
                    logger.error(f"searchDocumentContext fallback failed for {docId}: {e}")
            return "\n\n".join(parts), sources
        except Exception as e:
            logger.error(f"searchDocumentContext failed: {e}")
            return "", []
```

Keep the old `getDocumentContext` method in place for now (do not delete) — it may be called from other places. It will be removed in a follow-up.

- [ ] **Step 5: Run tests**

```bash
cd server
python -m pytest tests/knowledge/test_service.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/modules/knowledge/service.py server/tests/knowledge/test_service.py
git commit -m "feat(knowledge): fix real chunkCount; add searchDocumentContext with hybrid fallback"
```

---

## Task 6: Update `message/service.py` — yield `__SOURCES__` SSE marker

**Files:**
- Modify: `server/modules/message/service.py`

- [ ] **Step 1: Replace `getDocumentContext` call with `searchDocumentContext`**

In `processMessageFlow`, find:

```python
        documentContext = ""
        if documentIds:
            try:
                documentContext = await documentService.getDocumentContext(documentIds, userId)
            except Exception as e:
                logger.warning(f"processMessageFlow: getDocumentContext failed for userId {userId}: {e}")
```

Replace with:

```python
        documentContext = ""
        documentSources: list = []
        if documentIds:
            try:
                documentContext, documentSources = await documentService.searchDocumentContext(
                    documentIds, userId, content
                )
            except Exception as e:
                logger.warning(f"processMessageFlow: searchDocumentContext failed for userId {userId}: {e}")
```

- [ ] **Step 2: Collect sources from projectId RAG results**

Find the `ragContext` block:

```python
        ragContext = ""
        if projectId:
            try:
                results = await ragService.searchContext(content, projectId, limit=5)
                ragContext = "\n\n".join(r.document.content for r in results)
            except Exception as e:
                logger.warning(f"RAG search failed for project {projectId}: {e}")
```

Replace with:

```python
        ragContext = ""
        ragSources: list = []
        if projectId:
            try:
                results = await ragService.searchContext(content, projectId, limit=5)
                ragContext = "\n\n".join(r.document.content for r in results)
                ragSources = [
                    {
                        "filename": r.document.metadata.get("filename"),
                        "pageNumber": r.document.metadata.get("pageNumber"),
                    }
                    for r in results
                    if r.document.metadata.get("filename")
                ]
            except Exception as e:
                logger.warning(f"RAG search failed for project {projectId}: {e}")
```

- [ ] **Step 3: Yield `__SOURCES__` marker after `__QUOTA__`**

Find this block near the end of `processMessageFlow`:

```python
        quotaStatus = await quotaService.getStatus(userId, conversationId)
        yield f"\n__QUOTA__{json.dumps(quotaStatus)}__QUOTA__"
```

Replace with:

```python
        quotaStatus = await quotaService.getStatus(userId, conversationId)
        yield f"\n__QUOTA__{json.dumps(quotaStatus)}__QUOTA__"

        allSources = [s for s in (ragSources + documentSources) if s.get("filename")]
        if allSources:
            yield f"\n__SOURCES__{json.dumps(allSources)}__SOURCES__"
```

- [ ] **Step 4: Initialize `ragSources` and `documentSources` at the top of `processMessageFlow`**

After `userMsg = await messageRepository.create(...)`, add these two lines so they are always defined even when `projectId` or `documentIds` is `None`:

```python
        ragSources: list = []
        documentSources: list = []
```

Place them just before the `logger.info("[Step 3] Building context...")` line.

- [ ] **Step 5: Commit**

```bash
git add server/modules/message/service.py
git commit -m "feat(message): use searchDocumentContext; yield __SOURCES__ SSE marker with citation data"
```

---

## Task 7: Verify end-to-end with a real file upload

**Files:** (no code changes, manual verification)

- [ ] **Step 1: Start the backend**

```bash
cd server
uvicorn main:app --reload --port 3000
```

- [ ] **Step 2: Upload a test PDF and check logs**

Upload any text-based PDF via `POST /knowledge/documents/upload`. Watch logs for:

```
SimpleRagProvider: indexed N chunks for document <id>
_processDocument completed for <id>
```

`N` must be > 1 and the `chunkCount` field in the database/JSON should match `N`.

- [ ] **Step 3: Send a chat message and check SSE output**

Send a message that is relevant to the uploaded document. In the SSE stream, after the response text, verify:

```
__SOURCES__[{"filename": "yourfile.pdf", "pageNumber": 3}]__SOURCES__
```

appears in the stream.

- [ ] **Step 4: Run all project tests**

```bash
cd server
python -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test: verify RAG pipeline end-to-end — page-aware indexing and source citations"
```
