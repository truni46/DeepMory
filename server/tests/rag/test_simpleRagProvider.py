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
