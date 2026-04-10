# server/tests/knowledge/test_service.py
import hashlib
import pytest


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
    assert len(result) == 64


def test_computeHash_same_content_gives_same_hash():
    from modules.knowledge.service import _computeHash
    assert _computeHash(b"test") == _computeHash(b"test")


def test_chunkCount_not_hardcoded():
    import inspect
    from modules.knowledge import service as svc
    source = inspect.getsource(svc.DocumentService._processDocument)
    assert "chunkCount=1" not in source, "chunkCount must not be hardcoded to 1"


def test_searchDocumentContext_returns_tuple():
    import asyncio
    from unittest.mock import AsyncMock, patch
    from modules.knowledge.service import documentService

    mockDoc = {
        "id": "doc1",
        "userId": "user1",
        "ownerId": "user1",
        "filename": "test.pdf",
        "filePath": "/fake/path.pdf",
    }

    with patch("modules.knowledge.service.documentRepository.getById", new=AsyncMock(return_value=mockDoc)), \
         patch("modules.knowledge.service.ragService.searchContextByDocumentIds", new=AsyncMock(return_value=[])), \
         patch("modules.knowledge.service.documentService.getDocument", new=AsyncMock(return_value=mockDoc)), \
         patch("modules.knowledge.service._readTextContent", return_value="some text"):
        result = asyncio.get_event_loop().run_until_complete(
            documentService.searchDocumentContext(["doc1"], "user1", "query")
        )

    contextText, sources = result
    assert isinstance(contextText, str)
    assert isinstance(sources, list)


def test_searchDocumentContext_uses_vector_when_score_high():
    import asyncio
    from unittest.mock import AsyncMock, patch, MagicMock
    from modules.knowledge.service import documentService
    from modules.rag.repository import SearchResult, Document

    mockDoc = {
        "id": "doc1",
        "userId": "user1",
        "ownerId": "user1",
        "filename": "test.pdf",
        "filePath": "/fake/path.pdf",
    }
    mockResult = SearchResult(
        document=Document(
            id="doc1",
            content="chunk text",
            metadata={"filename": "test.pdf", "pageNumber": 2},
        ),
        score=0.9,
    )

    with patch("modules.knowledge.service.documentRepository.getById", new=AsyncMock(return_value=mockDoc)), \
         patch("modules.knowledge.service.ragService.searchContextByDocumentIds", new=AsyncMock(return_value=[mockResult])):
        contextText, sources = asyncio.get_event_loop().run_until_complete(
            documentService.searchDocumentContext(["doc1"], "user1", "query")
        )

    assert "chunk text" in contextText
    assert sources[0]["filename"] == "test.pdf"
    assert sources[0]["pageNumber"] == 2
