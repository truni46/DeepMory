"""
RAG public facade — powered by LightRAG.

This is the ONLY file that memory, knowledge, and message modules import from.
The public API is identical to the previous custom implementation.
"""
from __future__ import annotations

import os
import uuid
from typing import Dict, List, Optional

from config.logger import logger
from lightrag import QueryParam
from modules.rag.lightragProvider import lightragProvider
from modules.rag.repository import Document, SearchResult

def _readFile(filePath: str) -> str:
    """Read file content as text. Supports TXT, MD, HTML directly. PDF/DOCX via extractors."""
    ext = os.path.splitext(filePath)[1].lower()
    try:
        if ext == ".pdf":
            import pypdf
            reader = pypdf.PdfReader(filePath)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        elif ext == ".docx":
            import docx
            doc = docx.Document(filePath)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        else:
            with open(filePath, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as e:
        logger.error(f"Failed to read file '{filePath}': {e}")
        return ""


def _toSearchResults(lightragResponse: str) -> List[SearchResult]:
    """
    Convert LightRAG's string response into List[SearchResult].
    LightRAG returns a single text answer (not individual chunks),
    so we wrap it as one SearchResult.
    """
    if not lightragResponse or not lightragResponse.strip():
        return []
    return [
        SearchResult(
            document=Document(
                id=str(uuid.uuid4()),
                content=lightragResponse.strip(),
                metadata={"source": "lightrag"},
            ),
            score=1.0,
        )
    ]


class RagService:


    async def index(
        self,
        filePath: str,
        projectId: str,
        documentId: str,
        userId: str,
    ) -> int:
        """
        Read file → insert into project's LightRAG instance.
        LightRAG handles chunking, entity extraction, and graph building.
        Returns 1 on success (LightRAG manages chunks internally).
        """
        try:
            content = _readFile(filePath)
            if not content.strip():
                logger.warning(f"No content extracted from '{filePath}'")
                return 0

            instance = await lightragProvider.getInstance(f"project_{projectId}")
            await instance.ainsert(
                content,
                ids=[documentId],
                file_paths=[filePath],
            )
            logger.info(f"LightRAG indexed document {documentId} for project {projectId}")
            return 1
        except Exception as e:
            logger.error(f"LightRAG index failed for document {documentId}: {e}")
            raise

    async def deleteDocumentChunks(self, projectId: str, documentId: str) -> None:
        """Remove all data for a document from its project's LightRAG instance."""
        try:
            instance = await lightragProvider.getInstance(f"project_{projectId}")
            await instance.adelete_by_doc_id(documentId)
            logger.info(f"LightRAG deleted document {documentId} from project {projectId}")
        except Exception as e:
            logger.error(f"LightRAG delete failed for document {documentId}: {e}")
            raise

    async def searchContext(
        self,
        query: str,
        projectId: str,
        limit: int = 5,
        rerank: bool = False,
        mode: str = None,
    ) -> List[SearchResult]:
        """
        Query a project's knowledge graph + vectors.
        Modes: naive (vector only), local (entity graph), global (summary), hybrid (all).
        """
        try:
            instance = await lightragProvider.getInstance(f"project_{projectId}")
            queryMode = mode or os.getenv("LIGHTRAG_QUERY_MODE", "hybrid")
            result = await instance.aquery(
                query,
                param=QueryParam(mode=queryMode, top_k=limit),
            )
            return _toSearchResults(result)
        except Exception as e:
            logger.warning(f"LightRAG search failed for project {projectId}: {e}")
            return []

    async def upsertMemoryVector(
        self,
        userId: str,
        memoryId: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Insert a user-memory fact into the user's LightRAG instance."""
        try:
            instance = await lightragProvider.getInstance(f"user_{userId}")
            await instance.ainsert(content, ids=[memoryId])
        except Exception as e:
            logger.error(f"LightRAG memory upsert failed for user {userId}: {e}")

    async def searchMemoryVectors(
        self,
        userId: str,
        query: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        """Search over a user's long-term memories via LightRAG."""
        try:
            instance = await lightragProvider.getInstance(f"user_{userId}")
            result = await instance.aquery(
                query,
                param=QueryParam(mode="hybrid", top_k=limit),
            )
            return _toSearchResults(result)
        except Exception as e:
            logger.warning(f"LightRAG memory search failed for user {userId}: {e}")
            return []

    async def deleteMemoryVector(self, userId: str, memoryId: str) -> None:
        """Remove a single memory from the user's LightRAG instance."""
        try:
            instance = await lightragProvider.getInstance(f"user_{userId}")
            await instance.adelete_by_doc_id(memoryId)
        except Exception as e:
            logger.error(f"LightRAG memory delete failed for user {userId}: {e}")


ragService = RagService()
