from typing import List, Dict, Optional
import os
import shutil
from pathlib import Path
from config.database import db
from config.logger import logger

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class DocumentService:
    
    async def upload_document(self, userId: str, fileObj, filename: str, projectId: Optional[str] = None) -> Dict:
        """Save uploaded file and create record"""
        fileExt = os.path.splitext(filename)[1]
        storedFilename = f"{userId}_{filename}"
        if projectId:
             storedFilename = f"{userId}_{projectId}_{filename}"
             
        filePath = UPLOAD_DIR / storedFilename
        
        try:
            with open(filePath, "wb") as buffer:
                shutil.copyfileobj(fileObj.file, buffer)
        finally:
            fileObj.file.close()
            
        if not db.pool:
            raise Exception("Database not connected")
            
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO documents ("projectId", "userId", filename, "filePath", "fileType", "embeddingStatus") 
                   VALUES ($1, $2, $3, $4, $5, 'pending') 
                   RETURNING *""",
                projectId, userId, filename, str(filePath), fileExt
            )
            return dict(row)

    async def get_documents(self, projectId: str) -> List[Dict]:
        """Get documents for a project"""
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM documents WHERE "projectId" = $1 ORDER BY "createdAt" DESC""",
                projectId
            )
            return [dict(row) for row in rows]
            
    async def get_user_documents(self, userId: str) -> List[Dict]:
        """Get all documents for a user"""
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM documents WHERE "userId" = $1 ORDER BY "createdAt" DESC""",
                userId
            )
            return [dict(row) for row in rows]

    async def delete_document(self, userId: str, documentId: str) -> bool:
        """Delete a document by ID and userId"""
        if not db.pool:
            return False
            
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT "filePath" FROM documents WHERE id = $1 AND "userId" = $2""",
                documentId, userId
            )
            if not row:
                return False
                
            filePath = row['filePath']
            
            await conn.execute(
                """DELETE FROM documents WHERE id = $1 AND "userId" = $2""",
                documentId, userId
            )
            
            try:
                if os.path.exists(filePath):
                    os.remove(filePath)
            except Exception as e:
                logger.error(f"Failed to delete file {filePath}: {e}")
                
            return True

documentService = DocumentService()
