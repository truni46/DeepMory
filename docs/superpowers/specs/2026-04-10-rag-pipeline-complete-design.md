# RAG Pipeline Complete Design

**Date:** 2026-04-10
**Status:** Approved

---

## Problem Statement

The current document indexing and retrieval pipeline has several gaps:

1. **Chunk metadata missing** — Qdrant payloads store only `documentId`, `chunkIndex`, `text`; no `filename` or `pageNumber`, making source attribution impossible.
2. **`getDocumentContext` bypasses vector search** — when the user attaches specific documents to a chat, the code reads the raw file (up to 8000 chars) instead of doing semantic search.
3. **`chunkCount` hardcoded to 1** — never reflects the actual number of indexed chunks.
4. **No page-aware chunking** — text is split by character count with no respect for page or section boundaries.
5. **No source citation in UI** — the frontend has no way to show "Source: file.pdf, page 3" because the data never reaches it.

---

## Goals

- Upload → Markdown parse → page-aware chunk → embed → Qdrant (with filename + pageNumber metadata)
- Chat retrieval returns top-k chunks annotated with source info
- Sources delivered to frontend via SSE marker (like existing `__QUOTA__`)
- `documentIds` path uses hybrid search: vector first, full-text fallback if score low

---

## Architecture

### New File: `server/modules/rag/documentParser.py`

Single-file provider pattern (per project conventions). Handles document-to-page extraction:

```
Protocol: DocumentParser
  parse(filePath: str) -> List[ParsedPage]

ParsedPage:
  text: str          # Markdown text for this page/section
  pageNumber: int | None  # Real page number for PDF; None for others

PdfParser       → pymupdf4llm, page-by-page Markdown
DocxParser      → python-docx, paragraphs grouped into sections
XlsxParser      → openpyxl, sheet rows as Markdown tables
TextParser      → raw read, no page info

documentParserService = DocumentParserService()  # singleton, picks by ext
```

**Fidelity note:** `pymupdf4llm` handles text-based PDFs well (~85-95% accuracy). Multi-column PDFs may have ordering issues but semantic content is preserved — sufficient for RAG use cases.

### Modified: `server/modules/rag/simpleRagProvider.py`

**`_readFile` replaced by `_parseDocument`** — calls `documentParserService.parse()`.

**`_chunkText` replaced by `_chunkPages`** — receives `List[ParsedPage]`, chunks each page's text using heading/paragraph boundaries with overlap, propagates `pageNumber`.

**Qdrant payload per chunk:**
```json
{
  "documentId": "...",
  "userId": "...",
  "filename": "report.pdf",
  "filePath": "/data/uploads/abc_report.pdf",
  "pageNumber": 3,
  "chunkIndex": 7,
  "text": "..."
}
```

**`searchContext` return value** — `SearchResult.document.metadata` extended:
```json
{
  "documentId": "...",
  "chunkIndex": 7,
  "filename": "report.pdf",
  "pageNumber": 3
}
```

**New method: `searchContextByDocumentIds`** — vector search with `must` filter on a list of `documentId` values. Returns same `List[SearchResult]`.

### Modified: `server/modules/knowledge/service.py`

**`_processDocument`** — pass actual chunk count returned by `ragService.index()` to `updateEmbedding(chunkCount=N)`.

**`getDocumentContext` replaced by `searchDocumentContext`:**

```
searchDocumentContext(documentIds, userId, query) -> (contextText, sources)

Algorithm:
  1. Call ragService.searchContextByDocumentIds(query, documentIds, limit=5)
  2. If max score >= 0.5:
       contextText = join chunk texts
       sources = [{filename, pageNumber, score}, ...]
  3. Else (fallback):
       contextText = _readTextContent(filePath, maxChars=8000) per doc
       sources = [{filename, pageNumber=None}]
  4. Return (contextText, sources)
```

### Modified: `server/modules/message/service.py`

**`processMessageFlow`:**

- Replace `documentService.getDocumentContext(documentIds, userId)` with `documentService.searchDocumentContext(documentIds, userId, content)` — receives both `documentContext` and `documentSources`.
- After stream completes, collect all sources (from both `projectId` RAG results and `documentSources`), yield:

```
\n__SOURCES__[{"filename":"x.pdf","page":3},{"filename":"y.pdf","page":null}]__SOURCES__
```

Frontend parses this marker the same way it parses `__QUOTA__`.

---

## Data Flow: Chat with Documents

```
User types message
    │
    ▼
embed(message) → query vector
    │
    ├─[projectId]─ Qdrant search in project namespace → top-k chunks
    │
    └─[documentIds]─ Qdrant search filtered by documentId list
            │
            ├── max score ≥ 0.5 → use vector chunks
            └── max score < 0.5 → fallback: read raw file text
    │
    ▼
Build system prompt:
  "Relevant Context:\n{chunk texts}"
    │
    ▼
LLM stream → yield text chunks to client
    │
    ▼
yield \n__SOURCES__[...]__SOURCES__
    │
    ▼
Frontend displays:
  AI answer
  ─────────────────────
  Nguồn: report.pdf, trang 3 | contract.pdf, trang 7
```

---

## Files Changed

| File | Change |
|------|--------|
| `server/modules/rag/documentParser.py` | **New** — PDF/DOCX/XLSX/text → `List[ParsedPage]` |
| `server/modules/rag/simpleRagProvider.py` | Replace `_readFile`/`_chunkText` with page-aware versions; extend payload + metadata; add `searchContextByDocumentIds` |
| `server/modules/rag/ragService.py` | Expose `searchContextByDocumentIds` on facade |
| `server/modules/knowledge/service.py` | Fix `chunkCount`; replace `getDocumentContext` with `searchDocumentContext` |
| `server/modules/message/service.py` | Use `searchDocumentContext`; collect and yield `__SOURCES__` marker |

---

## Dependencies

```bash
pip install pymupdf4llm  # PDF → Markdown (page-aware)
```

`openpyxl` and `python-docx` are already in the project.

---

## Out of Scope

- OCR for scanned PDFs
- LightRAG provider (changes only affect `SimpleRagProvider`)
- Frontend rendering of `__SOURCES__` marker (separate UI task)
- Re-indexing existing documents (existing chunks lack new metadata; new uploads will have it)
