# Document Management Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox ('- [ ]') syntax for tracking.

**Goal:** Rewrite the 'knowledge/' module with multi-file upload + progress, async embedding pipeline, AI-generated summaries, and a document detail modal with PDF viewer.

**Architecture:** Full rewrite of 'server/modules/knowledge/' (router, service, repository) with a DB migration to extend the 'documents' table. Frontend replaces 'DocumentsPage.jsx' with a component tree: 'DocumentUploadZone' → 'DocumentTable' → 'DocumentCard' → 'DocumentDetailModal' + 'PDFViewer'.

**Tech Stack:** FastAPI, asyncpg, asyncio, pypdf, react-pdf (pdfjs-dist), React, Tailwind CSS, XMLHttpRequest (upload progress), pytest, pytest-asyncio

---

## File Map

**Create:**
- 'server/migrations/002_documents_update.sql' — ALTER TABLE to add new columns
- 'server/tests/__init__.py' — pytest package root
- 'server/tests/knowledge/__init__.py'
- 'server/tests/knowledge/test_service.py' — unit tests for pure utility functions
- 'src/components/ui/DocumentStatusBadge.jsx' — reusable status badge
- 'src/components/ui/PDFViewer.jsx' — react-pdf based PDF renderer
- 'src/components/ui/DocumentCard.jsx' — single document table row
- 'src/components/ui/DocumentDetailModal.jsx' — split-panel detail modal
- 'src/components/DocumentUploadZone.jsx' — drag & drop multi-upload with progress
- 'src/components/DocumentTable.jsx' — table with polling

**Rewrite:**
- 'server/modules/knowledge/repository.py' — full CRUD for new schema
- 'server/modules/knowledge/service.py' — upload pipeline + summary generation
- 'server/modules/knowledge/router.py' — new endpoints incl. file serve
- 'src/services/documentService.js' — XHR upload with progress + new API methods
- 'src/pages/DocumentsPage.jsx' — page layout wiring components together

---

## Task 1: DB Migration

**Files:**
- Create: 'server/migrations/002_documents_update.sql'

- [ ] **Step 1: Write the migration SQL**

'''sql
-- server/migrations/002_documents_update.sql

ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS scope VARCHAR(20) NOT NULL DEFAULT 'personal',
  ADD COLUMN IF NOT EXISTS "ownerId" UUID,
  ADD COLUMN IF NOT EXISTS "ownerType" VARCHAR(20) NOT NULL DEFAULT 'user',
  ADD COLUMN IF NOT EXISTS "storedFilename" VARCHAR(255),
  ADD COLUMN IF NOT EXISTS "embeddingError" TEXT,
  ADD COLUMN IF NOT EXISTS "chunkCount" INT,
  ADD COLUMN IF NOT EXISTS "pageCount" INT,
  ADD COLUMN IF NOT EXISTS summary TEXT,
  ADD COLUMN IF NOT EXISTS "summaryStatus" VARCHAR(20) NOT NULL DEFAULT 'pending',
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS tags TEXT[];

UPDATE documents SET "ownerId" = "userId" WHERE "ownerId" IS NULL;
ALTER TABLE documents ALTER COLUMN "ownerId" SET NOT NULL;

UPDATE documents SET "storedFilename" = filename WHERE "storedFilename" IS NULL;
ALTER TABLE documents ALTER COLUMN "storedFilename" SET NOT NULL;
'''

- [ ] **Step 2: Run the migration**

'''bash
# From project root, with DB running
psql -U $DB_USER -d $DB_NAME -f server/migrations/002_documents_update.sql
'''

Expected: 'ALTER TABLE', 'UPDATE X', 'ALTER TABLE' (×2) — no errors.

- [ ] **Step 3: Verify columns exist**

'''bash
psql -U $DB_USER -d $DB_NAME -c "\d documents"
'''

Expected: columns 'scope', 'ownerId', 'ownerType', 'storedFilename', 'embeddingError', 'chunkCount', 'pageCount', 'summary', 'summaryStatus', 'description', 'tags' all present.

- [ ] **Step 4: Commit**

'''bash
git add server/migrations/002_documents_update.sql
git commit -m "feat(knowledge): add migration for extended documents schema"
'''

---

## Task 2: Rewrite repository.py

**Files:**
- Modify: 'server/modules/knowledge/repository.py'

- [ ] **Step 1: Replace the file with the new implementation**

'''python
# server/modules/knowledge/repository.py
from typing import Dict, List, Optional, Tuple
import uuid
from datetime import datetime, timezone

from config.database import db


class DocumentRepository:

    async def create(
        self,
        userId: str,
        filename: str,
        storedFilename: str,
        filePath: str,
        fileType: str,
        fileSize: int,
        contentHash: str,
        scope: str = 'personal',
        ownerId: str = None,
        ownerType: str = 'user',
    ) -> Dict:
        docId = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        ownerIdVal = ownerId or userId
        record = {
            "id": docId,
            "userId": userId,
            "scope": scope,
            "ownerId": ownerIdVal,
            "ownerType": ownerType,
            "filename": filename,
            "storedFilename": storedFilename,
            "filePath": filePath,
            "fileType": fileType,
            "fileSize": fileSize,
            "contentHash": contentHash,
            "embeddingStatus": "pending",
            "summaryStatus": "pending",
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
        }

        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO documents (
                        id, "userId", scope, "ownerId", "ownerType",
                        filename, "storedFilename", "filePath", "fileType", "fileSize", "contentHash",
                        "embeddingStatus", "summaryStatus", "createdAt", "updatedAt"
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'pending','pending',$12,$13)
                    RETURNING *""",
                    docId, userId, scope, ownerIdVal, ownerType,
                    filename, storedFilename, filePath, fileType, fileSize, contentHash,
                    now, now,
                )
                return dict(row)
        else:
            data = db.read_json("documents")
            data[docId] = record
            db.write_json("documents", data)
            return record

    async def getByUser(self, userId: str, scope: str = None) -> List[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                if scope:
                    rows = await conn.fetch(
                        """SELECT * FROM documents WHERE "userId" = $1 AND scope = $2
                           ORDER BY "createdAt" DESC""",
                        userId, scope,
                    )
                else:
                    rows = await conn.fetch(
                        """SELECT * FROM documents WHERE "userId" = $1
                           ORDER BY "createdAt" DESC""",
                        userId,
                    )
                return [dict(r) for r in rows]
        else:
            data = db.read_json("documents")
            docs = [d for d in data.values() if str(d.get("userId")) == str(userId)]
            if scope:
                docs = [d for d in docs if d.get("scope") == scope]
            docs.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            return docs

    async def getById(self, documentId: str) -> Optional[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM documents WHERE id = $1", documentId
                )
                return dict(row) if row else None
        else:
            data = db.read_json("documents")
            return data.get(documentId)

    async def updateEmbedding(
        self,
        documentId: str,
        status: str,
        chunkCount: int = None,
        pageCount: int = None,
        errorMsg: str = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE documents SET
                        "embeddingStatus" = $1,
                        "chunkCount" = COALESCE($2, "chunkCount"),
                        "pageCount" = COALESCE($3, "pageCount"),
                        "embeddingError" = $4,
                        "updatedAt" = $5
                    WHERE id = $6""",
                    status, chunkCount, pageCount, errorMsg, now, documentId,
                )
        else:
            data = db.read_json("documents")
            if documentId in data:
                data[documentId]["embeddingStatus"] = status
                if chunkCount is not None:
                    data[documentId]["chunkCount"] = chunkCount
                if pageCount is not None:
                    data[documentId]["pageCount"] = pageCount
                if errorMsg is not None:
                    data[documentId]["embeddingError"] = errorMsg
                data[documentId]["updatedAt"] = now.isoformat()
                db.write_json("documents", data)

    async def updateSummary(
        self,
        documentId: str,
        status: str,
        summary: str = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE documents SET
                        "summaryStatus" = $1,
                        summary = COALESCE($2, summary),
                        "updatedAt" = $3
                    WHERE id = $4""",
                    status, summary, now, documentId,
                )
        else:
            data = db.read_json("documents")
            if documentId in data:
                data[documentId]["summaryStatus"] = status
                if summary is not None:
                    data[documentId]["summary"] = summary
                data[documentId]["updatedAt"] = now.isoformat()
                db.write_json("documents", data)

    async def delete(self, documentId: str, userId: str) -> Optional[Tuple[str, str]]:
        """Returns (filePath, ownerId) if deleted, None if not found/unauthorized."""
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT "filePath", "ownerId" FROM documents
                       WHERE id = $1 AND "userId" = $2""",
                    documentId, userId,
                )
                if not row:
                    return None
                await conn.execute(
                    """DELETE FROM documents WHERE id = $1 AND "userId" = $2""",
                    documentId, userId,
                )
                return row["filePath"], str(row["ownerId"])
        else:
            data = db.read_json("documents")
            doc = data.get(documentId)
            if not doc or str(doc.get("userId")) != str(userId):
                return None
            del data[documentId]
            db.write_json("documents", data)
            return doc.get("filePath"), doc.get("ownerId")


documentRepository = DocumentRepository()
'''

- [ ] **Step 2: Commit**

'''bash
git add server/modules/knowledge/repository.py
git commit -m "feat(knowledge): rewrite repository with extended schema support"
'''

---

## Task 3: Set up pytest + write tests for service utilities

**Files:**
- Create: 'server/tests/__init__.py'
- Create: 'server/tests/knowledge/__init__.py'
- Create: 'server/tests/knowledge/test_service.py'

- [ ] **Step 1: Install test dependencies**

'''bash
# Activate venv first
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

pip install pytest pytest-asyncio
'''

- [ ] **Step 2: Create pytest package files**

'''bash
# Create empty __init__.py files
touch server/tests/__init__.py
touch server/tests/knowledge/__init__.py
'''

- [ ] **Step 3: Write failing tests for '_computeHash' and '_extractPageCount'**

'''python
# server/tests/knowledge/test_service.py
import hashlib
import pytest

# We test the pure utility functions directly by importing them.
# These functions have no DB or network deps, so no mocking needed.

def test_computeHash_returns_sha256_hex():
    from modules.knowledge.service import _computeHash
    content = b"hello world"
    expected = hashlib.sha256(content).hexdigest()
    assert _computeHash(content) == expected

def test_computeHash_different_content_gives_different_hash():
    from modules.knowledge.service import _computeHash
    assert _computeHash(b"aaa") != _computeHash(b"bbb")

def test_computeHash_empty_bytes():
    from modules.knowledge.service import _computeHash
    result = _computeHash(b"")
    assert len(result) == 64  # SHA-256 hex is always 64 chars

def test_computeHash_same_content_gives_same_hash():
    from modules.knowledge.service import _computeHash
    assert _computeHash(b"test") == _computeHash(b"test")
'''

- [ ] **Step 4: Run tests — expect ImportError (module not written yet)**

'''bash
cd server && python -m pytest tests/knowledge/test_service.py -v
'''

Expected: 'ImportError' or 'ModuleNotFoundError' — the functions don't exist yet. This is the failing-test step.

- [ ] **Step 5: Commit failing tests**

'''bash
git add server/tests/
git commit -m "test(knowledge): add failing tests for service utility functions"
'''

---

## Task 4: Rewrite service.py

**Files:**
- Modify: 'server/modules/knowledge/service.py'

- [ ] **Step 1: Replace the file with the new implementation**

'''python
# server/modules/knowledge/service.py
import asyncio
import hashlib
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from config.logger import logger
from modules.knowledge.repository import documentRepository
from modules.rag.ragService import ragService
from modules.llm.llmProvider import llmProvider

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {".pdf", ".txt", ".md", ".docx", ".doc", ".xlsx", ".xls"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
SUMMARY_MAX_CHARS = 4000


def _computeHash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _extractPageCount(filePath: str) -> int:
    ext = os.path.splitext(filePath)[1].lower()
    try:
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(filePath)
            return len(reader.pages)
        elif ext in (".docx", ".doc"):
            import docx
            doc = docx.Document(filePath)
            paragraphs = [p for p in doc.paragraphs if p.text.strip()]
            return max(len(paragraphs) // 25, 1)
    except Exception as e:
        logger.warning(f"_extractPageCount failed for {filePath}: {e}")
    return 0


def _readTextContent(filePath: str, maxChars: int = SUMMARY_MAX_CHARS) -> str:
    ext = os.path.splitext(filePath)[1].lower()
    try:
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(filePath)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext in (".docx", ".doc"):
            import docx
            doc = docx.Document(filePath)
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            with open(filePath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        return text[:maxChars]
    except Exception as e:
        logger.warning(f"_readTextContent failed for {filePath}: {e}")
        return ""


class DocumentService:

    async def uploadDocuments(
        self,
        userId: str,
        files: List,
        scope: str = "personal",
        ownerId: str = None,
        ownerType: str = "user",
    ) -> List[Dict]:
        results = []
        for fileObj in files:
            try:
                doc = await self._uploadOne(
                    userId, fileObj, scope, ownerId or userId, ownerType
                )
                results.append(doc)
            except Exception as e:
                logger.error(f"uploadDocuments failed for {fileObj.filename}: {e}")
                results.append({"error": str(e), "filename": fileObj.filename})
        return results

    async def _uploadOne(
        self,
        userId: str,
        fileObj,
        scope: str,
        ownerId: str,
        ownerType: str,
    ) -> Dict:
        filename = fileObj.filename
        fileExt = os.path.splitext(filename)[1].lower()
        if fileExt not in ALLOWED_TYPES:
            raise ValueError(f"File type '{fileExt}' not allowed")

        content = await fileObj.read()
        if len(content) > MAX_FILE_SIZE:
            raise ValueError("File exceeds 50 MB limit")

        contentHash = _computeHash(content)
        storedFilename = f"{uuid.uuid4().hex}_{filename}"
        filePath = UPLOAD_DIR / storedFilename

        with open(filePath, "wb") as f:
            f.write(content)

        record = await documentRepository.create(
            userId=userId,
            filename=filename,
            storedFilename=storedFilename,
            filePath=str(filePath),
            fileType=fileExt.lstrip("."),
            fileSize=len(content),
            contentHash=contentHash,
            scope=scope,
            ownerId=ownerId,
            ownerType=ownerType,
        )

        asyncio.create_task(
            self._processDocument(record["id"], str(filePath), ownerId, userId)
        )
        return record

    async def _processDocument(
        self, documentId: str, filePath: str, ownerId: str, userId: str
    ) -> None:
        try:
            await documentRepository.updateEmbedding(documentId, "processing")
            await ragService.index(filePath, ownerId, documentId, userId)
            pageCount = _extractPageCount(filePath)
            await documentRepository.updateEmbedding(
                documentId, "completed", chunkCount=1, pageCount=pageCount
            )
            logger.info(f"_processDocument completed for {documentId}")
            asyncio.create_task(self._generateSummary(documentId, filePath))
        except Exception as e:
            logger.error(f"_processDocument failed for {documentId}: {e}")
            await documentRepository.updateEmbedding(
                documentId, "failed", errorMsg=str(e)
            )

    async def _generateSummary(self, documentId: str, filePath: str) -> None:
        try:
            await documentRepository.updateSummary(documentId, "processing")
            text = _readTextContent(filePath)
            if not text.strip():
                await documentRepository.updateSummary(documentId, "failed")
                return
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes documents concisely.",
                },
                {
                    "role": "user",
                    "content": f"Summarize the following document in 3-5 sentences:\n\n{text}",
                },
            ]
            response, _ = await llmProvider.generateResponse(messages, stream=False)
            await documentRepository.updateSummary(
                documentId, "completed", summary=response
            )
            logger.info(f"_generateSummary completed for {documentId}")
        except Exception as e:
            logger.error(f"_generateSummary failed for {documentId}: {e}")
            await documentRepository.updateSummary(documentId, "failed")

    async def getDocuments(
        self, userId: str, scope: Optional[str] = None
    ) -> List[Dict]:
        return await documentRepository.getByUser(userId, scope)

    async def getDocument(self, documentId: str, userId: str) -> Optional[Dict]:
        doc = await documentRepository.getById(documentId)
        if not doc or str(doc.get("userId")) != str(userId):
            return None
        return doc

    async def deleteDocument(self, userId: str, documentId: str) -> bool:
        result = await documentRepository.delete(documentId, userId)
        if result is None:
            return False
        filePath, ownerId = result
        try:
            if filePath and os.path.exists(filePath):
                os.remove(filePath)
        except Exception as e:
            logger.error(f"deleteDocument file removal failed for {documentId}: {e}")
        try:
            await ragService.deleteDocumentChunks(ownerId, documentId)
        except Exception as e:
            logger.error(f"deleteDocument RAG cleanup failed for {documentId}: {e}")
        return True


documentService = DocumentService()
'''

- [ ] **Step 2: Run the tests — should pass now**

'''bash
cd server && python -m pytest tests/knowledge/test_service.py -v
'''

Expected output:
'''
PASSED tests/knowledge/test_service.py::test_computeHash_returns_sha256_hex
PASSED tests/knowledge/test_service.py::test_computeHash_different_content_gives_different_hash
PASSED tests/knowledge/test_service.py::test_computeHash_empty_bytes
PASSED tests/knowledge/test_service.py::test_computeHash_same_content_gives_same_hash
4 passed
'''

- [ ] **Step 3: Commit**

'''bash
git add server/modules/knowledge/service.py
git commit -m "feat(knowledge): rewrite service with multi-upload, embedding pipeline, AI summary"
'''

---

## Task 5: Rewrite router.py

**Files:**
- Modify: 'server/modules/knowledge/router.py'

- [ ] **Step 1: Replace the file**

'''python
# server/modules/knowledge/router.py
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from common.deps import getCurrentUser
from config.logger import logger
from modules.knowledge.service import documentService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/documents/upload")
async def uploadDocuments(
    files: List[UploadFile] = File(...),
    scope: str = Query(default="personal"),
    ownerId: Optional[str] = Query(default=None),
    ownerType: str = Query(default="user"),
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        userId = str(currentUser["id"])
        results = await documentService.uploadDocuments(
            userId=userId,
            files=files,
            scope=scope,
            ownerId=ownerId or userId,
            ownerType=ownerType,
        )
        return results
    except Exception as e:
        logger.error(f"POST /knowledge/documents/upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def getDocuments(
    scope: Optional[str] = Query(default=None),
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        return await documentService.getDocuments(
            userId=str(currentUser["id"]), scope=scope
        )
    except Exception as e:
        logger.error(f"GET /knowledge/documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{documentId}/file")
async def serveDocumentFile(
    documentId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        doc = await documentService.getDocument(documentId, str(currentUser["id"]))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        filePath = doc["filePath"]
        if not os.path.exists(filePath):
            raise HTTPException(status_code=404, detail="File not found on disk")
        return FileResponse(
            path=filePath,
            filename=doc["filename"],
            media_type="application/octet-stream",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /knowledge/documents/{documentId}/file failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{documentId}")
async def getDocument(
    documentId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        doc = await documentService.getDocument(documentId, str(currentUser["id"]))
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /knowledge/documents/{documentId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{documentId}")
async def deleteDocument(
    documentId: str,
    currentUser: dict = Depends(getCurrentUser),
):
    try:
        success = await documentService.deleteDocument(
            userId=str(currentUser["id"]),
            documentId=documentId,
        )
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE /knowledge/documents/{documentId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/documents/{documentId}")
async def updateDocument(
    documentId: str,
    payload: dict,
    currentUser: dict = Depends(getCurrentUser),
):
    raise HTTPException(status_code=501, detail="Not implemented")
'''

- [ ] **Step 2: Restart the backend and smoke test**

'''bash
# In server/ directory, start the server
uvicorn main:app --reload --port 3000
'''

Then in another terminal:
'''bash
# Get a JWT token first, then:
curl -X GET http://localhost:3000/api/v1/knowledge/documents \
  -H "Authorization: Bearer <your_token>"
'''

Expected: '[]' (empty array) — no errors, 200 OK.

- [ ] **Step 3: Commit**

'''bash
git add server/modules/knowledge/router.py
git commit -m "feat(knowledge): rewrite router with multi-upload, file serve, and detail endpoints"
'''

---

## Task 6: Install react-pdf + rewrite documentService.js

**Files:**
- Modify: 'src/services/documentService.js'

- [ ] **Step 1: Install react-pdf**

'''bash
npm install react-pdf
'''

Expected: 'added N packages' — no peer-dep errors.

- [ ] **Step 2: Replace documentService.js**

'''javascript
// src/services/documentService.js
import apiService from './apiService';

class DocumentService {
    uploadDocuments(files, onProgress, scope = 'personal') {
        return new Promise((resolve, reject) => {
            const formData = new FormData();
            files.forEach(file => formData.append('files', file));

            const xhr = new XMLHttpRequest();
            const token = localStorage.getItem('token');

            xhr.upload.onprogress = (event) => {
                if (event.lengthComputable && onProgress) {
                    onProgress(Math.round((event.loaded / event.total) * 100));
                }
            };

            xhr.onload = () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        resolve(JSON.parse(xhr.responseText));
                    } catch {
                        resolve([]);
                    }
                } else {
                    reject(new Error(xhr.responseText || 'Upload failed'));
                }
            };

            xhr.onerror = () => reject(new Error('Network error during upload'));

            const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:3000/api/v1';
            xhr.open('POST', '${baseUrl}/knowledge/documents/upload?scope=${scope}');
            xhr.setRequestHeader('Authorization', 'Bearer ${token}');
            xhr.send(formData);
        });
    }

    async getDocuments(scope = null) {
        const params = scope ? '?scope=${scope}' : '';
        return apiService.get('/knowledge/documents${params}');
    }

    async getDocument(documentId) {
        return apiService.get('/knowledge/documents/${documentId}');
    }

    async getDocumentFileUrl(documentId) {
        const token = localStorage.getItem('token');
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:3000/api/v1';
        const response = await fetch(
            '${baseUrl}/knowledge/documents/${documentId}/file',
            { headers: { Authorization: 'Bearer ${token}' } }
        );
        if (!response.ok) throw new Error('Failed to fetch file');
        const blob = await response.blob();
        return URL.createObjectURL(blob);
    }

    async deleteDocument(documentId) {
        return apiService.delete('/knowledge/documents/${documentId}');
    }
}

export default new DocumentService();
'''

- [ ] **Step 3: Commit**

'''bash
git add src/services/documentService.js package.json package-lock.json
git commit -m "feat(knowledge): rewrite documentService with XHR progress upload and file URL support"
'''

---

## Task 7: Create DocumentStatusBadge.jsx

**Files:**
- Create: 'src/components/ui/DocumentStatusBadge.jsx'

- [ ] **Step 1: Create the component**

'''jsx
// src/components/ui/DocumentStatusBadge.jsx
export default function DocumentStatusBadge({ status }) {
    const config = {
        pending:    { label: 'Pending',    className: 'bg-gray-100 text-gray-600' },
        processing: { label: 'Processing', className: 'bg-blue-100 text-blue-600', spinner: true },
        completed:  { label: 'Completed',  className: 'bg-green-100 text-green-700' },
        failed:     { label: 'Failed',     className: 'bg-red-100 text-red-600' },
    };
    const { label, className, spinner } = config[status] || config.pending;

    return (
        <span className={'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${className}'}>
            {spinner && (
                <span className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
            )}
            {label}
        </span>
    );
}
'''

- [ ] **Step 2: Commit**

'''bash
git add src/components/ui/DocumentStatusBadge.jsx
git commit -m "feat(knowledge): add DocumentStatusBadge reusable component"
'''

---

## Task 8: Create PDFViewer.jsx

**Files:**
- Create: 'src/components/ui/PDFViewer.jsx'

- [ ] **Step 1: Create the component**

'''jsx
// src/components/ui/PDFViewer.jsx
import { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
    'pdfjs-dist/build/pdf.worker.min.mjs',
    import.meta.url,
).toString();

export default function PDFViewer({ fileUrl }) {
    const [numPages, setNumPages] = useState(null);
    const [currentPage, setCurrentPage] = useState(1);

    function onDocumentLoadSuccess({ numPages }) {
        setNumPages(numPages);
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-gray-100">
            <div className="flex-1 overflow-y-auto flex justify-center p-4">
                <Document
                    file={fileUrl}
                    onLoadSuccess={onDocumentLoadSuccess}
                    loading={
                        <p className="text-sm text-gray-500 mt-8">Loading document...</p>
                    }
                    error={
                        <p className="text-sm text-red-500 mt-8">Failed to load PDF.</p>
                    }
                >
                    <Page pageNumber={currentPage} width={560} />
                </Document>
            </div>

            {numPages && (
                <div className="flex items-center justify-center gap-4 py-3 border-t border-gray-200 bg-white text-sm">
                    <button
                        onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                        disabled={currentPage <= 1}
                        className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100 transition-colors"
                    >
                        ←
                    </button>
                    <span className="text-text-secondary">
                        {currentPage} / {numPages}
                    </span>
                    <button
                        onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
                        disabled={currentPage >= numPages}
                        className="px-3 py-1 rounded border border-gray-300 disabled:opacity-40 hover:bg-gray-100 transition-colors"
                    >
                        →
                    </button>
                </div>
            )}
        </div>
    );
}
'''

- [ ] **Step 2: Commit**

'''bash
git add src/components/ui/PDFViewer.jsx
git commit -m "feat(knowledge): add PDFViewer component with react-pdf"
'''

---

## Task 9: Create DocumentCard.jsx

**Files:**
- Create: 'src/components/ui/DocumentCard.jsx'

- [ ] **Step 1: Create the component**

'''jsx
// src/components/ui/DocumentCard.jsx
import { FiTrash2, FiEye } from 'react-icons/fi';
import DocumentStatusBadge from './DocumentStatusBadge';

const FILE_ICONS = {
    pdf:  '📄',
    docx: '📝',
    doc:  '📝',
    xlsx: '📊',
    xls:  '📊',
    txt:  '📃',
    md:   '📃',
};

function formatFileSize(bytes) {
    if (!bytes) return '—';
    if (bytes < 1024) return '${bytes} B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toFixed(1)} KB';
    return '${(bytes / (1024 * 1024)).toFixed(1)} MB';
}

export default function DocumentCard({ document, onView, onDelete }) {
    const icon = FILE_ICONS[document.fileType] || '📄';
    const date = new Date(document.createdAt).toLocaleDateString('en-GB', {
        day: '2-digit', month: 'short', year: 'numeric',
    });

    return (
        <tr className="hover:bg-gray-50 transition-colors border-b border-border-color last:border-0">
            <td className="px-6 py-4">
                <div className="flex items-center gap-3">
                    <span className="text-lg">{icon}</span>
                    <span
                        className="font-medium text-sm truncate max-w-xs"
                        title={document.filename}
                    >
                        {document.filename}
                    </span>
                </div>
            </td>
            <td className="px-6 py-4 text-sm text-text-secondary uppercase">
                {document.fileType || '—'}
            </td>
            <td className="px-6 py-4 text-sm text-text-secondary">
                {formatFileSize(document.fileSize)}
            </td>
            <td className="px-6 py-4">
                <DocumentStatusBadge status={document.embeddingStatus} />
            </td>
            <td className="px-6 py-4 text-sm text-text-secondary">{date}</td>
            <td className="px-6 py-4">
                <div className="flex items-center justify-end gap-2">
                    <button
                        onClick={() => onView(document)}
                        className="p-2 text-gray-400 hover:text-primary transition-colors rounded hover:bg-primary/10"
                        title="View details"
                    >
                        <FiEye size={16} />
                    </button>
                    <button
                        onClick={() => onDelete(document.id)}
                        className="p-2 text-gray-400 hover:text-red-500 transition-colors rounded hover:bg-red-50"
                        title="Delete"
                    >
                        <FiTrash2 size={16} />
                    </button>
                </div>
            </td>
        </tr>
    );
}
'''

- [ ] **Step 2: Commit**

'''bash
git add src/components/ui/DocumentCard.jsx
git commit -m "feat(knowledge): add DocumentCard table row component"
'''

---

## Task 10: Create DocumentDetailModal.jsx

**Files:**
- Create: 'src/components/ui/DocumentDetailModal.jsx'

- [ ] **Step 1: Create the component**

'''jsx
// src/components/ui/DocumentDetailModal.jsx
import { useState, useEffect } from 'react';
import { FiX, FiFileText, FiCalendar, FiBookOpen, FiDownload } from 'react-icons/fi';
import documentService from '../../services/documentService';
import PDFViewer from './PDFViewer';
import DocumentStatusBadge from './DocumentStatusBadge';

function formatDate(dateStr) {
    return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short', day: 'numeric', year: 'numeric',
    });
}

export default function DocumentDetailModal({ document, onClose }) {
    const [fileUrl, setFileUrl] = useState(null);
    const [fileError, setFileError] = useState(null);
    const isPdf = document.fileType === 'pdf';

    useEffect(() => {
        let objectUrl = null;
        documentService.getDocumentFileUrl(document.id)
            .then(url => {
                objectUrl = url;
                setFileUrl(url);
            })
            .catch(() => setFileError('Could not load file preview.'));

        return () => {
            if (objectUrl) URL.revokeObjectURL(objectUrl);
        };
    }, [document.id]);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
            <div className="bg-white rounded-xl shadow-2xl w-[90vw] max-w-5xl h-[85vh] flex flex-col overflow-hidden">
                <div className="flex items-center justify-between px-6 py-4 border-b border-border-color">
                    <h2 className="text-lg font-semibold">Document Preview</h2>
                    <button
                        onClick={onClose}
                        className="p-2 rounded hover:bg-gray-100 transition-colors"
                    >
                        <FiX size={20} />
                    </button>
                </div>

                <div className="flex flex-1 overflow-hidden">
                    {/* Left: file viewer */}
                    <div className="flex-1 border-r border-border-color overflow-hidden">
                        {isPdf && fileUrl ? (
                            <PDFViewer fileUrl={fileUrl} />
                        ) : fileError ? (
                            <div className="flex items-center justify-center h-full text-sm text-red-500">
                                {fileError}
                            </div>
                        ) : !fileUrl ? (
                            <div className="flex items-center justify-center h-full text-sm text-gray-400">
                                Loading document...
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full gap-4">
                                <FiFileText size={48} className="text-gray-300" />
                                <p className="text-sm text-gray-500">
                                    Preview not available for this file type.
                                </p>
                                <a
                                    href={fileUrl}
                                    download={document.filename}
                                    className="px-4 py-2 bg-primary text-white rounded-lg text-sm flex items-center gap-2 hover:bg-primary-dark transition-colors"
                                >
                                    <FiDownload size={16} />
                                    Download
                                </a>
                            </div>
                        )}
                    </div>

                    {/* Right: metadata */}
                    <div className="w-80 flex-shrink-0 overflow-y-auto p-6 space-y-6">
                        <h3 className="text-lg font-semibold break-words">
                            {document.filename}
                        </h3>

                        <div className="space-y-3 text-sm text-text-secondary">
                            {document.pageCount > 0 && (
                                <div className="flex items-center gap-2">
                                    <FiBookOpen size={16} />
                                    <span>
                                        Total pages:{' '}
                                        <strong className="text-text-primary">
                                            {document.pageCount}
                                        </strong>
                                    </span>
                                </div>
                            )}
                            <div className="flex items-center gap-2">
                                <FiCalendar size={16} />
                                <span>
                                    Uploaded on:{' '}
                                    <strong className="text-text-primary">
                                        {formatDate(document.createdAt)}
                                    </strong>
                                </span>
                            </div>
                        </div>

                        <div>
                            <div className="flex items-center justify-between mb-3">
                                <h4 className="font-semibold text-sm">About this document</h4>
                                <DocumentStatusBadge status={document.summaryStatus} />
                            </div>

                            {document.summaryStatus === 'completed' && document.summary ? (
                                <p className="text-sm text-text-secondary leading-relaxed">
                                    {document.summary}
                                </p>
                            ) : document.summaryStatus === 'processing' ||
                              document.summaryStatus === 'pending' ? (
                                <div className="space-y-2">
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-full" />
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-4/5" />
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-3/4" />
                                    <div className="h-3 bg-gray-200 rounded animate-pulse w-2/3" />
                                </div>
                            ) : (
                                <p className="text-sm text-red-400">
                                    Summary generation failed.
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
'''

- [ ] **Step 2: Commit**

'''bash
git add src/components/ui/DocumentDetailModal.jsx
git commit -m "feat(knowledge): add DocumentDetailModal with PDF viewer and AI summary panel"
'''

---

## Task 11: Create DocumentUploadZone.jsx

**Files:**
- Create: 'src/components/DocumentUploadZone.jsx'

- [ ] **Step 1: Create the component**

'''jsx
// src/components/DocumentUploadZone.jsx
import { useState, useRef, useCallback } from 'react';
import { FiUploadCloud, FiCheck, FiAlertCircle } from 'react-icons/fi';
import documentService from '../services/documentService';

const ACCEPTED = '.pdf,.txt,.md,.docx,.doc,.xlsx,.xls';
const MAX_CONCURRENT = 3;

function FileProgressItem({ item }) {
    return (
        <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
                <span className="truncate max-w-xs text-text-secondary" title={item.file.name}>
                    {item.file.name}
                </span>
                <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                    {item.status === 'done' && <FiCheck size={14} className="text-green-600" />}
                    {item.status === 'error' && <FiAlertCircle size={14} className="text-red-500" />}
                    <span className="text-text-secondary">
                        {item.status === 'error' ? item.errorMessage : '${item.progress}%'}
                    </span>
                </div>
            </div>
            <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                <div
                    className={'h-full rounded-full transition-all duration-200 ${
                        item.status === 'error'
                            ? 'bg-red-400'
                            : item.status === 'done'
                            ? 'bg-green-500'
                            : 'bg-primary'
                    }'}
                    style={{ width: '${item.progress}%' }}
                />
            </div>
        </div>
    );
}

export default function DocumentUploadZone({ onUploadComplete }) {
    const [dragOver, setDragOver] = useState(false);
    const [uploadItems, setUploadItems] = useState([]);
    const inputRef = useRef(null);

    const updateItem = useCallback((id, patch) => {
        setUploadItems(prev => prev.map(i => (i.id === id ? { ...i, ...patch } : i)));
    }, []);

    const uploadFile = useCallback(
        async item => {
            updateItem(item.id, { status: 'uploading', progress: 0 });
            try {
                const results = await documentService.uploadDocuments(
                    [item.file],
                    progress => updateItem(item.id, { progress }),
                );
                updateItem(item.id, {
                    status: 'done',
                    progress: 100,
                    documentId: results[0]?.id || null,
                });
            } catch (err) {
                updateItem(item.id, {
                    status: 'error',
                    errorMessage: err.message || 'Upload failed',
                });
            }
        },
        [updateItem],
    );

    const processQueue = useCallback(
        async items => {
            for (let i = 0; i < items.length; i += MAX_CONCURRENT) {
                await Promise.all(items.slice(i, i + MAX_CONCURRENT).map(uploadFile));
            }
            if (onUploadComplete) onUploadComplete();
        },
        [uploadFile, onUploadComplete],
    );

    const handleFiles = useCallback(
        files => {
            const newItems = Array.from(files).map(file => ({
                id: Math.random().toString(36).slice(2),
                file,
                progress: 0,
                status: 'queued',
                documentId: null,
                errorMessage: null,
            }));
            setUploadItems(prev => [...prev, ...newItems]);
            processQueue(newItems);
        },
        [processQueue],
    );

    const onDrop = useCallback(
        e => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
        },
        [handleFiles],
    );

    return (
        <div className="bg-white rounded-xl border border-border-color p-6 space-y-4">
            <h2 className="text-lg font-semibold">Upload Document</h2>

            <div
                onDragOver={e => {
                    e.preventDefault();
                    setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                onClick={() => inputRef.current?.click()}
                className={'border-2 border-dashed rounded-xl p-10 flex flex-col items-center gap-3 cursor-pointer transition-colors ${
                    dragOver
                        ? 'border-primary bg-primary/5'
                        : 'border-gray-300 hover:border-primary/50'
                }'}
            >
                <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
                    <FiUploadCloud size={22} className="text-gray-500" />
                </div>
                <p className="font-medium text-sm">Select Documents</p>
                <p className="text-xs text-text-secondary">
                    Drag & drop PDF files here, or click to browse
                </p>
                <input
                    ref={inputRef}
                    type="file"
                    className="hidden"
                    multiple
                    accept={ACCEPTED}
                    onChange={e => handleFiles(e.target.files)}
                />
            </div>

            {uploadItems.length > 0 && (
                <div className="space-y-3 pt-2">
                    {uploadItems.map(item => (
                        <FileProgressItem key={item.id} item={item} />
                    ))}
                </div>
            )}
        </div>
    );
}
'''

- [ ] **Step 2: Commit**

'''bash
git add src/components/DocumentUploadZone.jsx
git commit -m "feat(knowledge): add DocumentUploadZone with drag-drop and per-file progress bars"
'''

---

## Task 12: Create DocumentTable.jsx

**Files:**
- Create: 'src/components/DocumentTable.jsx'

- [ ] **Step 1: Create the component**

'''jsx
// src/components/DocumentTable.jsx
import { useState, useEffect, useRef } from 'react';
import { FiRefreshCw } from 'react-icons/fi';
import DocumentCard from './ui/DocumentCard';
import DocumentDetailModal from './ui/DocumentDetailModal';
import documentService from '../services/documentService';

const POLL_INTERVAL_MS = 3000;

function hasProcessingDocs(docs) {
    return docs.some(
        d => d.embeddingStatus === 'processing' || d.embeddingStatus === 'pending',
    );
}

export default function DocumentTable({ refreshTrigger }) {
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [selectedDoc, setSelectedDoc] = useState(null);
    const pollingRef = useRef(null);

    const fetchDocuments = async () => {
        try {
            const docs = await documentService.getDocuments();
            setDocuments(docs);
        } catch (err) {
            console.error('fetchDocuments failed:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        setLoading(true);
        fetchDocuments();
    }, [refreshTrigger]);

    useEffect(() => {
        if (!hasProcessingDocs(documents)) return;

        pollingRef.current = setInterval(async () => {
            try {
                const docs = await documentService.getDocuments();
                setDocuments(docs);
                if (!hasProcessingDocs(docs)) {
                    clearInterval(pollingRef.current);
                }
            } catch (err) {
                console.error('Polling failed:', err);
            }
        }, POLL_INTERVAL_MS);

        return () => clearInterval(pollingRef.current);
    }, [documents]);

    const handleDelete = async documentId => {
        if (!window.confirm('Delete this document?')) return;
        try {
            await documentService.deleteDocument(documentId);
            setDocuments(prev => prev.filter(d => d.id !== documentId));
        } catch (err) {
            console.error('Delete failed:', err);
        }
    };

    return (
        <>
            <div className="bg-white rounded-xl border border-border-color overflow-hidden">
                <div className="px-6 py-4 border-b border-border-color bg-gray-50 flex justify-between items-center">
                    <h2 className="text-lg font-semibold">My Documents</h2>
                    <div className="flex items-center gap-3">
                        <span className="text-sm text-text-secondary">
                            {documents.length} document{documents.length !== 1 ? 's' : ''}
                        </span>
                        <button
                            onClick={fetchDocuments}
                            className="p-1.5 text-text-secondary hover:text-primary transition-colors"
                            title="Refresh"
                        >
                            <FiRefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                        </button>
                    </div>
                </div>

                {loading ? (
                    <div className="p-12 text-center text-sm text-text-secondary">
                        Loading...
                    </div>
                ) : documents.length === 0 ? (
                    <div className="p-12 text-center text-sm text-text-secondary">
                        No documents uploaded yet.
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <table className="w-full text-left">
                            <thead className="bg-gray-50 text-text-secondary text-xs font-medium uppercase tracking-wide">
                                <tr>
                                    <th className="px-6 py-3">Name</th>
                                    <th className="px-6 py-3">Type</th>
                                    <th className="px-6 py-3">Size</th>
                                    <th className="px-6 py-3">Status</th>
                                    <th className="px-6 py-3">Uploaded</th>
                                    <th className="px-6 py-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {documents.map(doc => (
                                    <DocumentCard
                                        key={doc.id}
                                        document={doc}
                                        onView={setSelectedDoc}
                                        onDelete={handleDelete}
                                    />
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {selectedDoc && (
                <DocumentDetailModal
                    document={selectedDoc}
                    onClose={() => setSelectedDoc(null)}
                />
            )}
        </>
    );
}
'''

- [ ] **Step 2: Commit**

'''bash
git add src/components/DocumentTable.jsx
git commit -m "feat(knowledge): add DocumentTable with status polling and detail modal trigger"
'''

---

## Task 13: Rewrite DocumentsPage.jsx

**Files:**
- Modify: 'src/pages/DocumentsPage.jsx'

- [ ] **Step 1: Replace the file**

'''jsx
// src/pages/DocumentsPage.jsx
import { useState } from 'react';
import DocumentUploadZone from '../components/DocumentUploadZone';
import DocumentTable from '../components/DocumentTable';

export default function DocumentsPage() {
    const [refreshTrigger, setRefreshTrigger] = useState(0);

    return (
        <div className="flex-1 flex flex-col h-full overflow-hidden">
            <header className="px-6 py-4 border-b border-border-color bg-white shadow-sm">
                <h1 className="text-2xl font-bold text-primary">My Documents</h1>
            </header>

            <main className="flex-1 overflow-y-auto p-8">
                <div className="max-w-5xl mx-auto space-y-8">
                    <DocumentUploadZone
                        onUploadComplete={() => setRefreshTrigger(t => t + 1)}
                    />
                    <DocumentTable refreshTrigger={refreshTrigger} />
                </div>
            </main>
        </div>
    );
}
'''

- [ ] **Step 2: Start the dev server and verify the page loads**

'''bash
npm run dev
'''

Open 'http://localhost:5173/documents' — expect:
- Upload zone with drag & drop area
- Empty documents table
- No console errors

- [ ] **Step 3: Upload a PDF and verify**

1. Drag a PDF onto the upload zone
2. Progress bar shows 0 → 100%
3. Table refreshes and shows the document with 'embeddingStatus: pending' → 'processing' → 'completed'
4. Click "View" — modal opens with PDF viewer on the left and metadata on the right
5. After a few seconds, the "About this document" section shows the AI summary

- [ ] **Step 4: Commit**

'''bash
git add src/pages/DocumentsPage.jsx
git commit -m "feat(knowledge): rewrite DocumentsPage wiring upload zone and table together"
'''
