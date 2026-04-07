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
