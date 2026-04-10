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
