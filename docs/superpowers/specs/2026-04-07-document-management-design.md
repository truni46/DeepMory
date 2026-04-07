# Document Management Module — Design Spec

**Date:** 2026-04-07
**Status:** Approved

## Overview

Rewrite the `knowledge/` module to support full document management with multi-file upload, progress tracking, AI-generated summaries, and a document detail viewer. The module handles both personal documents (user-owned) and shared library documents (department/organization-owned) via a single `scope` field — access control (RBAC) is deferred to a later sprint.

---

## Data Model

### Table: `documents`

```sql
id              UUID        PRIMARY KEY DEFAULT gen_random_uuid()
userId          UUID        NOT NULL REFERENCES users(id)
scope           VARCHAR(20) NOT NULL DEFAULT 'personal'   -- personal | department | organization
ownerId         UUID        NOT NULL                      -- userId | deptId | orgId
ownerType       VARCHAR(20) NOT NULL DEFAULT 'user'       -- user | department | organization

filename        VARCHAR(255) NOT NULL   -- original display name
storedFilename  VARCHAR(255) NOT NULL   -- uuid-prefixed filename on disk
filePath        VARCHAR(500) NOT NULL
fileType        VARCHAR(50)             -- pdf | docx | txt | xlsx
fileSize        BIGINT                  -- bytes
contentHash     VARCHAR(64)             -- SHA-256, used for duplicate detection

embeddingStatus VARCHAR(20) NOT NULL DEFAULT 'pending'    -- pending | processing | completed | failed
embeddingError  TEXT
chunkCount      INT
pageCount       INT

summary         TEXT                    -- AI-generated document summary
summaryStatus   VARCHAR(20) NOT NULL DEFAULT 'pending'    -- pending | processing | completed | failed

description     TEXT                    -- user-entered (reserved for future CRUD)
tags            TEXT[]

createdAt       TIMESTAMPTZ NOT NULL DEFAULT now()
updatedAt       TIMESTAMPTZ NOT NULL DEFAULT now()
metadata        JSONB
```

**Notes:**
- `storedFilename` is separate from `filename` to avoid collisions when multiple users upload files with the same name.
- `contentHash` allows detecting duplicate file content before re-indexing.
- `summary` and `summaryStatus` are populated after embedding completes, not at upload time.
- `description` and `tags` are reserved for a future user-editable CRUD flow.

---

## Backend Design

### Module: `server/modules/knowledge/`

```
knowledge/
├── router.py       -- FastAPI routes
├── service.py      -- Business logic, pipeline orchestration
└── repository.py   -- PostgreSQL + JSON fallback CRUD
```

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/knowledge/documents/upload` | Upload multiple files (multipart/form-data), returns list of created documents |
| `GET` | `/knowledge/documents` | List documents, filterable by `scope` |
| `GET` | `/knowledge/documents/:id` | Get single document detail |
| `GET` | `/knowledge/documents/:id/file` | Serve file binary (auth-protected) |
| `DELETE` | `/knowledge/documents/:id` | Delete document + file on disk + RAG chunks |
| `PATCH` | `/knowledge/documents/:id` | Update `description` / `tags` (reserved) |

### Async Processing Pipeline

```
POST /upload
  → validate file type + size
  → compute contentHash (SHA-256)
  → save file to disk as {uuid}_{originalFilename}
  → insert DB record (embeddingStatus: 'pending', summaryStatus: 'pending')
  → return document to client immediately

asyncio.create_task(_processDocument(documentId))
  → set embeddingStatus: 'processing'
  → ragService.index(filePath, documentId, userId)
  → extract pageCount from file metadata
  → set embeddingStatus: 'completed', chunkCount: N, pageCount: N
  → asyncio.create_task(_generateSummary(documentId))
      → set summaryStatus: 'processing'
      → retrieve first N chunks from RAG store
      → call LLM with summarization prompt
      → set summaryStatus: 'completed', summary: "<text>"

On any error:
  → set embeddingStatus / summaryStatus: 'failed', embeddingError: str(e)
  → logger.error with documentId context
```

**Supported file types:** `.pdf`, `.txt`, `.md`, `.docx`, `.doc`, `.xlsx`, `.xls`

**Duplicate detection:** If `contentHash` matches an existing document for the same user, skip re-indexing and reuse existing RAG chunks.

---

## Frontend Design

### File Structure

```
src/pages/
  DocumentsPage.jsx              -- page layout, state management

src/components/
  DocumentUploadZone.jsx         -- drag & drop, multi-file, per-file progress bars
  DocumentTable.jsx              -- table listing documents

src/components/ui/
  DocumentCard.jsx               -- single document row/card (reusable)
  DocumentDetailModal.jsx        -- split-panel modal: PDF viewer + metadata (reusable)
  DocumentStatusBadge.jsx        -- status badge for embedding/summary status (reusable)
  PDFViewer.jsx                  -- PDF renderer via react-pdf (reusable)

src/services/
  documentService.js             -- rewritten: upload (with progress), list, detail, delete
```

### Component Responsibilities

**`DocumentUploadZone`**
- Drag & drop or click-to-browse, accepts multiple files
- Per-file progress bar using `XMLHttpRequest.onprogress`
- Max 3 concurrent uploads (queue remainder)
- On all uploads complete → callback to refresh `DocumentTable`

**`DocumentTable`**
- Renders list of `DocumentCard` rows
- Polls `GET /knowledge/documents` every 3 seconds while any document has `embeddingStatus: 'processing'`
- Stops polling when all documents reach `completed` or `failed`

**`DocumentCard`**
- Displays: file type icon, filename, fileSize, createdAt, `DocumentStatusBadge`
- "View" button → opens `DocumentDetailModal`
- Delete button with confirmation

**`DocumentDetailModal`**
- Left panel: `PDFViewer` (fetches auth-protected `/documents/:id/file`)
  - Non-PDF files: show download link instead of viewer
- Right panel:
  - Filename, pageCount, uploadedAt
  - `DocumentStatusBadge` for summaryStatus
  - "About this document" section: summary text or loading skeleton while `summaryStatus: 'processing'`

**`DocumentStatusBadge`**
- Props: `status` (`pending | processing | completed | failed`), optional `type` (`embedding | summary`)
- Color coding: pending=gray, processing=blue+spinner, completed=green, failed=red

**`PDFViewer`**
- Uses `react-pdf` (`pdfjs-dist`)
- Props: `fileUrl`, `authToken`
- Fetches with Authorization header (not a plain `<iframe>`)
- Shows page navigation controls

### Upload Progress State Shape

```js
// Per-file upload state in DocumentUploadZone
{
  id: string,          // local uuid
  file: File,
  progress: number,    // 0–100
  status: 'queued' | 'uploading' | 'done' | 'error',
  documentId: string | null,
  errorMessage: string | null
}
```

---

## Scope Deferred

- Access control / RBAC (who can see `department` or `organization` scope documents)
- Edit document metadata (description, tags) — fields exist in DB but UI not implemented
- Library page (`/library`) — same components, different `scope` filter

---

## Dependencies

- `react-pdf` / `pdfjs-dist` — PDF rendering in browser
- Existing: `ragService`, `llmProvider`, `asyncpg`, `asyncio`
