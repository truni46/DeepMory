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
