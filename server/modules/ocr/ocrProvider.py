from __future__ import annotations

import os
from dataclasses import dataclass
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
    def __init__(self, useCls: bool = False):
        self._useCls = useCls
        self._engine = None

    def _getEngine(self, lang: str):
        if self._engine is None:
            from paddleocr import PaddleOCR
            paddleLang = self._mapLang(lang)
            self._engine = PaddleOCR(
                use_angle_cls=self._useCls,
                lang=paddleLang,
                use_gpu=False,
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
                lines: List[str] = []
                confs: List[float] = []
                if ocrResult and ocrResult[0]:
                    for line in ocrResult[0]:
                        lines.append(line[1][0])
                        confs.append(line[1][1])
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
    """PaddleOCR with angle classification for layout-aware recognition."""

    def __init__(self):
        super().__init__(useCls=True)

    def _getEngine(self, lang: str):
        if self._engine is None:
            from paddleocr import PaddleOCR
            paddleLang = self._mapLang(lang)
            self._engine = PaddleOCR(
                use_angle_cls=True,
                lang=paddleLang,
                use_gpu=False,
                show_log=False,
            )
        return self._engine

    @property
    def providerName(self) -> str:
        return "paddle-vl"


class PaddleVLCloudOcrProvider:
    """PaddleOCR-VL via Baidu AI Studio official API (layout-parsing endpoint).

    Get API_URL and ACCESS_TOKEN from https://aistudio.baidu.com/paddleocr/task
    (click "API" button next to the PaddleOCR-VL / PaddleOCR-VL-1.5 model).

    Env vars:
      PADDLEOCR_VL_API_URL       — full endpoint URL, e.g. https://xxxxxx.aistudio-app.com/layout-parsing (required)
      PADDLEOCR_VL_ACCESS_TOKEN  — access token from https://aistudio.baidu.com/index/accessToken (required)
      PADDLEOCR_VL_TIMEOUT       — request timeout in seconds, default 180
      PADDLEOCR_VL_PRETTIFY      — prettifyMarkdown, default true

    Backwards-compatible aliases (still honored):
      PADDLEOCR_VL_API_KEY  → PADDLEOCR_VL_ACCESS_TOKEN
      PADDLEOCR_VL_BASE_URL → PADDLEOCR_VL_API_URL
    """

    def __init__(self):
        self._apiUrl = os.getenv("PADDLEOCR_VL_API_URL") or os.getenv("PADDLEOCR_VL_BASE_URL", "")
        self._token = os.getenv("PADDLEOCR_VL_ACCESS_TOKEN") or os.getenv("PADDLEOCR_VL_API_KEY", "")
        self._timeout = float(os.getenv("PADDLEOCR_VL_TIMEOUT", "180"))
        self._prettify = os.getenv("PADDLEOCR_VL_PRETTIFY", "true").lower() == "true"
        if not self._apiUrl or not self._token:
            logger.warning(
                "PaddleVLCloudOcrProvider: missing PADDLEOCR_VL_API_URL or PADDLEOCR_VL_ACCESS_TOKEN; "
                "calls will fail until configured"
            )

    def _encodeFile(self, filePath: str) -> str:
        import base64
        with open(filePath, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    def _callApi(self, filePath: str, fileType: int) -> dict:
        import httpx
        headers = {
            "Authorization": f"token {self._token}",
            "Content-Type": "application/json",
        }
        payload = {
            "file": self._encodeFile(filePath),
            "fileType": fileType,
            "prettifyMarkdown": self._prettify,
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(self._apiUrl, json=payload, headers=headers)
            resp.raise_for_status()
            body = resp.json()
        if body.get("errorCode", 0) != 0:
            raise RuntimeError(f"PaddleOCR-VL API error {body.get('errorCode')}: {body.get('errorMsg')}")
        return body.get("result", {})

    def _extractPages(self, result: dict) -> List[OcrPage]:
        parsed = result.get("layoutParsingResults", []) or []
        pages: List[OcrPage] = []
        for i, item in enumerate(parsed):
            md = (item or {}).get("markdown") or {}
            text = md.get("text", "") if isinstance(md, dict) else ""
            pages.append(OcrPage(text=(text or "").strip(), pageNumber=i + 1, confidence=None))
        return pages

    def ocrImages(self, imagePaths: List[str], lang: str) -> List[OcrPage]:
        results: List[OcrPage] = []
        for i, imgPath in enumerate(imagePaths):
            try:
                result = self._callApi(imgPath, fileType=1)
                pages = self._extractPages(result)
                text = "\n\n".join(p.text for p in pages if p.text)
                results.append(OcrPage(text=text, pageNumber=i + 1, confidence=None))
            except Exception as e:
                logger.error(f"PaddleVLCloudOcrProvider.ocrImages failed on page {i + 1}: {e}")
                results.append(OcrPage(text="", pageNumber=i + 1, confidence=0.0))
        return results

    def ocrPdf(self, pdfPath: str) -> List[OcrPage]:
        """Send the whole PDF in one request (server-side layout parses all pages)."""
        try:
            result = self._callApi(pdfPath, fileType=0)
            return self._extractPages(result)
        except Exception as e:
            logger.error(f"PaddleVLCloudOcrProvider.ocrPdf failed: {e}")
            return []

    @property
    def providerName(self) -> str:
        return "paddle-vl-cloud"


class VisionLLMOcrProvider:
    """OCR via Vision LLM API (Gemini or OpenAI). Set OCR_VISION_MODEL env to override model."""

    _PROMPT = (
        "Extract all text from this document image exactly as it appears. "
        "Preserve line breaks and paragraph structure. "
        "Return only the extracted text, no commentary."
    )

    def __init__(self):
        self._backend = os.getenv("OCR_VISION_BACKEND", "gemini").lower()
        self._model = os.getenv("OCR_VISION_MODEL", "")

    def _encodeImage(self, imagePath: str) -> tuple[str, str]:
        import base64, mimetypes
        mime = mimetypes.guess_type(imagePath)[0] or "image/png"
        with open(imagePath, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")
        return mime, data

    def _ocrWithGemini(self, imagePath: str) -> str:
        import base64
        from google import genai
        from google.genai import types
        model = self._model or "gemini-2.0-flash"
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        mime, data = self._encodeImage(imagePath)
        response = client.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=base64.b64decode(data), mime_type=mime),
                self._PROMPT,
            ],
        )
        return response.text or ""

    def _ocrWithOpenAI(self, imagePath: str) -> str:
        from openai import OpenAI
        model = self._model or "gpt-4o-mini"
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        mime, data = self._encodeImage(imagePath)
        response = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
                    {"type": "text", "text": self._PROMPT},
                ],
            }],
            max_tokens=4096,
        )
        return response.choices[0].message.content or ""

    def ocrImages(self, imagePaths: List[str], lang: str) -> List[OcrPage]:
        results: List[OcrPage] = []
        for i, imgPath in enumerate(imagePaths):
            try:
                if self._backend == "openai":
                    text = self._ocrWithOpenAI(imgPath)
                else:
                    text = self._ocrWithGemini(imgPath)
                results.append(OcrPage(text=text.strip(), pageNumber=i + 1, confidence=None))
            except Exception as e:
                logger.error(f"VisionLLMOcrProvider.ocrImages failed on page {i + 1}: {e}")
                results.append(OcrPage(text="", pageNumber=i + 1, confidence=0.0))
        return results

    @property
    def providerName(self) -> str:
        return f"vision-{self._backend}"


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
        self._providerName = os.getenv("OCR_PROVIDER", "paddle").lower()
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
                    hasToken = os.getenv("PADDLEOCR_VL_ACCESS_TOKEN") or os.getenv("PADDLEOCR_VL_API_KEY")
                    hasUrl = os.getenv("PADDLEOCR_VL_API_URL") or os.getenv("PADDLEOCR_VL_BASE_URL")
                    if hasToken and hasUrl:
                        logger.info("paddle-vl: routing to AI Studio cloud API")
                        self._provider = PaddleVLCloudOcrProvider()
                    else:
                        self._provider = PaddleVLOcrProvider()
                elif self._providerName in ("paddle-vl-cloud", "paddleocr-vl", "paddleocr-vl-cloud"):
                    self._provider = PaddleVLCloudOcrProvider()
                elif self._providerName in ("vision", "vision-gemini", "vision-openai"):
                    self._provider = VisionLLMOcrProvider()
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
            if hasattr(provider, "ocrPdf"):
                pages = provider.ocrPdf(filePath)
                if pages:
                    return pages
                logger.warning("provider.ocrPdf returned no pages; falling back to per-page image OCR")
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
