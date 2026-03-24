import asyncio
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from config.logger import logger
from modules.knowledge.repository import documentRepository
from modules.rag.ragService import ragService

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class DocumentService:

    async def uploadDocument(
        self,
        userId: str,
        fileObj,
        filename: str,
        projectId: Optional[str] = None,
    ) -> Dict:
        """Save file to disk, create DB record, trigger async indexing."""
        fileExt = os.path.splitext(filename)[1]
        storedName = f"{userId}_{projectId}_{filename}" if projectId else f"{userId}_{filename}"
        filePath = UPLOAD_DIR / storedName

        try:
            with open(filePath, "wb") as buf:
                shutil.copyfileobj(fileObj.file, buf)
        finally:
            fileObj.file.close()

        record = await documentRepository.create(
            userId=userId,
            filename=filename,
            filePath=str(filePath),
            fileType=fileExt,
            projectId=projectId,
        )

        if projectId:
            asyncio.create_task(
                self._indexDocument(record["id"], str(filePath), projectId, userId)
            )

        return record

    async def _indexDocument(
        self, documentId: str, filePath: str, projectId: str, userId: str
    ) -> None:
        try:
            await documentRepository.updateStatus(documentId, "processing")
            chunksIndexed = await ragService.index(filePath, projectId, documentId, userId)
            await documentRepository.updateStatus(documentId, "completed")
            logger.info(f"Indexed {chunksIndexed} chunks for document {documentId}")
        except Exception as e:
            logger.error(f"Indexing failed for document {documentId}: {e}")
            await documentRepository.updateStatus(documentId, "failed")

    async def getUserDocuments(self, userId: str) -> List[Dict]:
        return await documentRepository.getByUser(userId)

    async def getProjectDocuments(self, projectId: str) -> List[Dict]:
        return await documentRepository.getByProject(projectId)

    async def deleteDocument(self, userId: str, documentId: str) -> bool:
        result = await documentRepository.delete(documentId, userId)
        if result is None:
            return False

        filePath, projectId = result

        try:
            if filePath and os.path.exists(filePath):
                os.remove(filePath)
        except Exception as e:
            logger.error(f"Failed to delete file '{filePath}': {e}")

        if projectId:
            try:
                await ragService.deleteDocumentChunks(projectId, documentId)
            except Exception as e:
                logger.error(f"Failed to delete vector chunks for document {documentId}: {e}")

        return True


documentService = DocumentService()
