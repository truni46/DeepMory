"""
RAG Repository — shared types consumed by memory, knowledge, and message modules.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SearchMode(str, Enum):
    """LightRAG query modes."""
    NAIVE = "naive"      # basic vector similarity search
    LOCAL = "local"      # entity-focused graph search
    GLOBAL = "global"    # summary-based graph traversal
    HYBRID = "hybrid"    # combined — recommended


class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    projectId: Optional[str] = None
    userId: Optional[str] = None
    source: Optional[str] = None
    chunkIndex: Optional[int] = None


class SearchResult(BaseModel):
    document: Document
    score: float
