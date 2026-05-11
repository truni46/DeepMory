# OCR Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an OCR module that detects scanned/image-based PDFs and extracts text using pluggable OCR engines, saving the result as a separate file and using it for RAG indexing.

**Architecture:** Single-File Provider Pattern (`ocrProvider.py`) with three providers — TesseractOCR, PaddleOCR, PaddleOCR-VL. A scan detection function checks if any PDF page lacks extractable text; if so, the entire document is OCR'd. The OCR text file is saved to `server/data/uploads/ocr/{documentId}_ocr.txt` and referenced via new DB fields. The existing indexing pipeline consumes the OCR file instead of the original when available.

**Tech Stack:** PyMuPDF (fitz) for scan detection, pytesseract + pdf2image for Tesseract, paddleocr for PaddleOCR/PaddleOCR-VL, Pillow for image handling.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `server/migrations/007_ocr_fields.sql` | Add OCR columns to `documents` table |
| Create | `server/modules/ocr/ocrProvider.py` | OCR providers + service (Single-File Provider Pattern) |
| Modify | `server/modules/knowledge/repository.py` | Add `updateOcr()` method |
| Modify | `server/modules/knowledge/service.py` | Integrate OCR detection + processing into document pipeline |

---

### Task 1: Database Migration

**Files:**
- Create: `server/migrations/007_ocr_fields.sql`

- [ ] **Step 1: Create migration file**

```sql
ALTER TABLE documents
  ADD COLUMN IF NOT EXISTS "ocrFilePath" VARCHAR(1024),
  ADD COLUMN IF NOT EXISTS "ocrStatus" VARCHAR(20),
  ADD COLUMN IF NOT EXISTS "isScanned" BOOLEAN DEFAULT FALSE;
```

`ocrStatus` values: `NULL` (not applicable / not checked), `"processing"`, `"completed"`, `"failed"`.
`isScanned` is `TRUE` when any page lacked extractable text.
`ocrFilePath` points to the OCR text file when `ocrStatus = "completed"`.

- [ ] **Step 2: Commit**

```bash
git add server/migrations/007_ocr_fields.sql
git commit -m "feat(ocr): add ocrFilePath, ocrStatus, isScanned columns to documents"
```

---

### Task 2: Repository — `updateOcr` Method

**Files:**
- Modify: `server/modules/knowledge/repository.py`

- [ ] **Step 1: Add `updateOcr` method to `DocumentRepository`**

Add this method after the existing `updateSummary` method (after line 158):

```python
async def updateOcr(
    self,
    documentId: str,
    ocrStatus: str,
    ocrFilePath: str = None,
    isScanned: bool = None,
) -> None:
    now = datetime.now(timezone.utc)
    if db.useDatabase and db.pool:
        async with db.pool.acquire() as conn:
            await conn.execute(
                """UPDATE documents SET
                    "ocrStatus" = $1,
                    "ocrFilePath" = COALESCE($2, "ocrFilePath"),
                    "isScanned" = COALESCE($3, "isScanned"),
                    "updatedAt" = $4
                WHERE id = $5""",
                ocrStatus, ocrFilePath, isScanned, now, documentId,
            )
    else:
        data = db.read_json("documents")
        if documentId in data:
            data[documentId]["ocrStatus"] = ocrStatus
            if ocrFilePath is not None:
                data[documentId]["ocrFilePath"] = ocrFilePath
            if isScanned is not None:
                data[documentId]["isScanned"] = isScanned
            data[documentId]["updatedAt"] = now.isoformat()
            db.write_json("documents", data)
```

- [ ] **Step 2: Commit**

```bash
git add server/modules/knowledge/repository.py
git commit -m "feat(ocr): add updateOcr method to DocumentRepository"
```

---

### Task 3: OCR Provider Module

**Files:**
- Create: `server/modules/ocr/ocrProvider.py`

This follows the **Single-File Provider Pattern** identical to `embeddingProvider.py`:
`Protocol → ConcreteProviderA → ConcreteProviderB → ConcreteProviderC → ServiceWrapper → singleton`

- [ ] **Step 1: Create the provider file**

```python
# server/modules/ocr/ocrProvider.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Protocol

from config.logger import logger


@dataclass
class OcrPage:
    text: str
    pageNumber: int
    confidence: Optional[float] = None


class OcrProvider(Protocol):
    def ocrImages(self, imagePaths: List[str], lang: str) -> List[OcrPage]:
        ...

    @property
    def providerName(self) -> str:
        ...


class TesseractOcrProvider:
    def __init__(self, cmd: str = None):
        import pytesseract
        if cmd or os.getenv("TESSERACT_CMD"):
            pytesseract.pytesseract.tesseract_cmd = cmd or os.getenv("TESSERACT_CMD")
        self._pytesseract = pytesseract

    def _mapLang(self, lang: str) -> str:
        mapping = {"vie": "vie", "eng": "eng", "vi": "vie", "en": "eng"}
        parts = [p.strip() for p in lang.replace(",", "+").split("+")]
        mapped = [mapping.get(p, p) for p in parts]
        return "+".join(mapped)

    def ocrImages(self, imagePaths: List[str], lang: str) -> List[OcrPage]:
        from PIL import Image
        tessLang = self._mapLang(lang)
        results: List[OcrPage] = []
        for i, imgPath in enumerate(imagePaths):
            try:
                img = Image.open(imgPath)
                data = self._pytesseract.image_to_data(img, lang=tessLang, output_type=self._pytesseract.Output.DICT)
                text = self._pytesseract.image_to_string(img, lang=tessLang)
                confs = [int(c) for c in data["conf"] if int(c) > 0]
                avgConf = sum(confs) / len(confs) if confs else 0.0
                results.append(OcrPage(text=text.strip(), pageNumber=i + 1, confidence=round(avgConf, 2)))
            except Exception as e:
                logger.error(f"TesseractOcrProvider.ocrImages failed on page {i + 1}: {e}")
                results.append(OcrPage(text="", pageNumber=i + 1, confidence=0.0))
        return results

    @property
    def providerName(self) -> str:
        return "tesseract"


class PaddleOcrProvider:
    def __init__(self, useCls: bool = False, useStructure: bool = False):
        self._useCls = useCls
        self._useStructure = useStructure
        self._engine = None

    def _getEngine(self, lang: str):
        if self._engine is None:
            from paddleocr import PaddleOCR
            paddleLang = self._mapLang(lang)
            self._engine = PaddleOCR(
                use_angle_cls=self._useCls,
                lang=paddleLang,
                show_log=False,
            )
        return self._engine

    def _mapLang(self, lang: str) -> str:
        parts = [p.strip() for p in lang.replace(",", "+").split("+")]
        mapping = {"vie": "vi", "eng": "en", "vi": "vi", "en": "en"}
        for p in parts:
            if mapping.get(p, p) == "vi":
                return "vi"
        return "en"

    def ocrImages(self, imagePaths: List[str], lang: str) -> List[OcrPage]:
        engine = self._getEngine(lang)
        results: List[OcrPage] = []
        for i, imgPath in enumerate(imagePaths):
            try:
                ocrResult = engine.ocr(imgPath, cls=self._useCls)
                lines = []
                confs = []
                if ocrResult and ocrResult[0]:
                    for line in ocrResult[0]:
                        text = line[1][0]
                        conf = line[1][1]
                        lines.append(text)
                        confs.append(conf)
                avgConf = sum(confs) / len(confs) if confs else 0.0
                results.append(OcrPage(
                    text="\n".join(lines),
                    pageNumber=i + 1,
                    confidence=round(avgConf * 100, 2),
                ))
            except Exception as e:
                logger.error(f"PaddleOcrProvider.ocrImages failed on page {i + 1}: {e}")
                results.append(OcrPage(text="", pageNumber=i + 1, confidence=0.0))
        return results

    @property
    def providerName(self) -> str:
        return "paddle"


class PaddleVLOcrProvider(PaddleOcrProvider):
    """PaddleOCR with angle classification and layout-aware structure analysis."""

    def __init__(self):
        super().__init__(useCls=True, useStructure=True)

    def _getEngine(self, lang: str):
        if self._engine is None:
            from paddleocr import PaddleOCR
            paddleLang = self._mapLang(lang)
            self._engine = PaddleOCR(
                use_angle_cls=True,
                lang=paddleLang,
                show_log=False,
                ocr_version="PP-OCRv4",
            )
        return self._engine

    @property
    def providerName(self) -> str:
        return "paddle-vl"


def _pdfToImages(pdfPath: str, outputDir: str) -> List[str]:
    """Convert each PDF page to a PNG image using PyMuPDF. Returns list of image paths."""
    import fitz
    doc = fitz.open(pdfPath)
    imagePaths: List[str] = []
    for pageNum in range(len(doc)):
        page = doc[pageNum]
        pix = page.get_pixmap(dpi=300)
        imgPath = os.path.join(outputDir, f"page_{pageNum + 1}.png")
        pix.save(imgPath)
        imagePaths.append(imgPath)
    doc.close()
    return imagePaths


def needsOcr(filePath: str) -> bool:
    """Return True if the document has any page without extractable text."""
    ext = os.path.splitext(filePath)[1].lower()
    imageExts = {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}
    if ext in imageExts:
        return True
    if ext != ".pdf":
        return False
    try:
        import fitz
        doc = fitz.open(filePath)
        for page in doc:
            text = page.get_text().strip()
            if not text:
                doc.close()
                return True
        doc.close()
        return False
    except Exception as e:
        logger.error(f"needsOcr check failed for {filePath}: {e}")
        return False


class OCRService:
    """ServiceWrapper — reads env, builds provider, exposes convenience methods."""

    def __init__(self):
        self._providerName = os.getenv("OCR_PROVIDER", "tesseract").lower()
        self._lang = os.getenv("OCR_LANG", "vie+eng")
        self._provider: Optional[OcrProvider] = None
        logger.info(f"OCRService initialized: provider={self._providerName} lang={self._lang}")

    def _getProvider(self) -> OcrProvider:
        if self._provider is None:
            try:
                if self._providerName == "tesseract":
                    self._provider = TesseractOcrProvider()
                elif self._providerName == "paddle":
                    self._provider = PaddleOcrProvider()
                elif self._providerName == "paddle-vl":
                    self._provider = PaddleVLOcrProvider()
                else:
                    logger.warning(f"Unknown OCR provider '{self._providerName}', falling back to Tesseract")
                    self._provider = TesseractOcrProvider()
            except Exception as e:
                logger.error(f"Failed to init OCR provider {self._providerName}: {e}")
                raise
        return self._provider

    def ocrFile(self, filePath: str, lang: str = None) -> List[OcrPage]:
        """OCR a PDF or image file. Returns list of OcrPage with text per page."""
        import tempfile
        lang = lang or self._lang
        ext = os.path.splitext(filePath)[1].lower()
        provider = self._getProvider()

        if ext == ".pdf":
            with tempfile.TemporaryDirectory() as tmpDir:
                imagePaths = _pdfToImages(filePath, tmpDir)
                return provider.ocrImages(imagePaths, lang)
        else:
            return provider.ocrImages([filePath], lang)

    def saveOcrText(self, pages: List[OcrPage], outputPath: str) -> str:
        """Save OCR results to a text file. Returns the output path."""
        os.makedirs(os.path.dirname(outputPath), exist_ok=True)
        with open(outputPath, "w", encoding="utf-8") as f:
            for page in pages:
                if page.text:
                    f.write(page.text)
                    f.write("\n\n")
        return outputPath

    @property
    def providerName(self) -> str:
        return self._getProvider().providerName


ocrService = OCRService()
```

- [ ] **Step 2: Create `__init__.py`**

Create an empty `server/modules/ocr/__init__.py` file (if the project uses `__init__.py` for modules — check first).

- [ ] **Step 3: Commit**

```bash
git add server/modules/ocr/
git commit -m "feat(ocr): add OCR provider module with Tesseract, PaddleOCR, PaddleOCR-VL"
```

---

### Task 4: Integrate OCR into Document Processing Pipeline

**Files:**
- Modify: `server/modules/knowledge/service.py`

This is the core integration. The `_processDocument` method is modified to:
1. Check if document needs OCR via `needsOcr()`
2. If yes — run OCR, save text file, update DB
3. Pass the OCR file path (instead of original) to `ragService.index()`
4. Use OCR text for summary generation too

- [ ] **Step 1: Add imports and OCR directory constant**

At the top of `server/modules/knowledge/service.py`, add after existing imports (line 13):

```python
from modules.ocr.ocrProvider import ocrService, needsOcr
```

Add after the `UPLOAD_DIR` setup (after line 16):

```python
OCR_DIR = Path(__file__).parent.parent.parent / "data" / "uploads" / "ocr"
OCR_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Replace `_processDocument` method**

Replace the entire `_processDocument` method (lines 128–144) with:

```python
async def _processDocument(
    self, documentId: str, filePath: str, ownerId: str, userId: str, filename: Optional[str] = None
) -> None:
    try:
        await documentRepository.updateEmbedding(documentId, "processing")

        indexPath = filePath
        if needsOcr(filePath):
            try:
                await documentRepository.updateOcr(documentId, "processing", isScanned=True)
                ocrPages = ocrService.ocrFile(filePath)
                ocrFilePath = str(OCR_DIR / f"{documentId}_ocr.txt")
                ocrService.saveOcrText(ocrPages, ocrFilePath)
                await documentRepository.updateOcr(documentId, "completed", ocrFilePath=ocrFilePath)
                indexPath = ocrFilePath
                logger.info(f"OCR completed for {documentId}: {len(ocrPages)} pages")
            except Exception as e:
                logger.error(f"OCR failed for {documentId}: {e}")
                await documentRepository.updateOcr(documentId, "failed")

        chunkCount = await ragService.index(indexPath, ownerId, documentId, userId, filename=filename)
        pageCount = _extractPageCount(filePath)
        await documentRepository.updateEmbedding(
            documentId, "completed", chunkCount=chunkCount, pageCount=pageCount
        )
        logger.info(f"_processDocument completed for {documentId}")
        asyncio.create_task(self._generateSummary(documentId, filePath, indexPath))
    except Exception as e:
        logger.error(f"_processDocument failed for {documentId}: {e}")
        await documentRepository.updateEmbedding(
            documentId, "failed", errorMsg=str(e)
        )
```

Note: `_generateSummary` now receives `indexPath` as a third argument so it can read OCR text for better summaries.

- [ ] **Step 3: Update `_generateSummary` signature and body**

Replace the `_generateSummary` method (lines 146–178) with:

```python
async def _generateSummary(self, documentId: str, filePath: str, indexPath: str = None) -> None:
    try:
        await documentRepository.updateSummary(documentId, "processing")
        text = _readTextContent(indexPath or filePath)
        if not text.strip():
            await documentRepository.updateSummary(documentId, "failed")
            return
        messages = [
            {"role": "system", "content": DOCUMENT_SUMMARY_SYSTEM},
            {"role": "user", "content": documentSummaryUserPrompt(text)},
        ]
        response = await llmProvider.generateResponse(messages, stream=False)
        await documentRepository.updateSummary(
            documentId, "completed", summary=response
        )
        logger.info(f"_generateSummary completed for {documentId}")
        doc = await documentRepository.getById(documentId)
        if doc:
            docUserId = doc.get("userId") or ""
            if docUserId:
                asyncio.create_task(
                    ragService.upsertDocumentIndex(
                        userId=docUserId,
                        documentId=documentId,
                        filename=doc.get("filename", ""),
                        summary=response,
                    )
                )
            else:
                logger.warning(f"_generateSummary: skipping upsertDocumentIndex for {documentId} — missing userId")
    except Exception as e:
        logger.error(f"_generateSummary failed for {documentId}: {e}")
        await documentRepository.updateSummary(documentId, "failed")
```

- [ ] **Step 4: Update `getDocumentContext` to prefer OCR text**

Replace `getDocumentContext` method (lines 195–212) — change the `_readTextContent` call to use `ocrFilePath` when available:

```python
async def getDocumentContext(self, documentIds: List[str], userId: str) -> str:
    parts = []
    for docId in documentIds:
        try:
            doc = await self.getDocument(docId, userId)
            if not doc:
                logger.warning(f"getDocumentContext: document {docId} not found or unauthorized for user {userId}")
                continue
            readPath = doc.get("ocrFilePath") or doc.get("filePath", "")
            if not readPath:
                logger.warning(f"getDocumentContext: no filePath for document {docId}")
                continue
            text = _readTextContent(readPath, maxChars=8000)
            if text.strip():
                parts.append(f"--- Document: {doc.get('filename', docId)} ---\n{text}")
        except Exception as e:
            logger.error(f"getDocumentContext failed for document {docId}: {e}")
    return "\n\n".join(parts)
```

- [ ] **Step 5: Update `searchDocumentContext` fallback to prefer OCR text**

In `searchDocumentContext` (lines 214–264), change the fallback branch (line 255) from `doc["filePath"]` to prefer OCR:

Change:
```python
text = _readTextContent(doc["filePath"], maxChars=8000)
```
To:
```python
readPath = doc.get("ocrFilePath") or doc["filePath"]
text = _readTextContent(readPath, maxChars=8000)
```

- [ ] **Step 6: Update `deleteDocument` to clean up OCR file**

In the `deleteDocument` method (lines 266–285), after the original file deletion (after line 274), add OCR file cleanup:

```python
ocrPath = str(OCR_DIR / f"{documentId}_ocr.txt")
try:
    if os.path.exists(ocrPath):
        os.remove(ocrPath)
except Exception as e:
    logger.error(f"deleteDocument OCR file removal failed for {documentId}: {e}")
```

- [ ] **Step 7: Commit**

```bash
git add server/modules/knowledge/service.py
git commit -m "feat(ocr): integrate OCR detection and processing into document pipeline"
```

---

### Task 5: Install Dependencies

- [ ] **Step 1: Install Python packages**

```bash
# Activate venv first
.venv\Scripts\activate

pip install pytesseract pdf2image Pillow paddleocr paddlepaddle
```

Note on system dependencies:
- **Tesseract binary**: Install via `choco install tesseract` (Windows), `apt install tesseract-ocr tesseract-ocr-vie` (Linux), `brew install tesseract` (Mac)
- **Poppler** (for pdf2image): `choco install poppler` (Windows), `apt install poppler-utils` (Linux)
- **PyMuPDF** (`fitz`): Already installed as a dependency of `pymupdf4llm`

- [ ] **Step 2: Add to requirements if a requirements file exists**

Check for `requirements.txt` or `pyproject.toml` and add:
```
pytesseract
pdf2image
Pillow
paddleocr
paddlepaddle
```

- [ ] **Step 3: Run the migration**

```bash
# If using PostgreSQL:
psql -U deepmory -d deepmory_db -f server/migrations/007_ocr_fields.sql
```

- [ ] **Step 4: Commit dependency changes**

```bash
git add requirements.txt  # or pyproject.toml
git commit -m "chore: add OCR dependencies (pytesseract, paddleocr, pdf2image)"
```

---

### Task 6: Smoke Test

- [ ] **Step 1: Start the backend**

```bash
cd server && python main.py
```

Verify in logs: `OCRService initialized: provider=tesseract lang=vie+eng`

- [ ] **Step 2: Upload a scanned PDF via API or UI**

Upload a PDF with at least one scanned (image-only) page. Verify in logs:
- `OCR completed for {documentId}: N pages`
- `_processDocument completed for {documentId}`
- OCR text file exists at `server/data/uploads/ocr/{documentId}_ocr.txt`

- [ ] **Step 3: Verify indexing used OCR text**

Search the document via RAG. The search results should return text extracted by OCR, not empty content.

- [ ] **Step 4: Verify DB fields**

```sql
SELECT id, filename, "isScanned", "ocrStatus", "ocrFilePath" FROM documents WHERE "isScanned" = TRUE;
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_PROVIDER` | `tesseract` | OCR engine: `tesseract`, `paddle`, `paddle-vl` |
| `OCR_LANG` | `vie+eng` | Languages for OCR (mapped per provider) |
| `TESSERACT_CMD` | _(system default)_ | Path to Tesseract binary (optional, for non-standard installs) |
