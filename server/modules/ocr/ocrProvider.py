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
    """PaddleOCR with angle classification and PP-OCRv4 for layout-aware recognition."""

    def __init__(self):
        super().__init__(useCls=True)

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
