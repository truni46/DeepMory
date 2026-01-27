from typing import List, Dict, Optional
import os
import shutil
from pathlib import Path
from config.database import db
from config.logger import logger

UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class DocumentService:
    
    async def upload_document(self, user_id: str, file_obj, filename: str, project_id: Optional[str] = None) -> Dict:
        """Save uploaded file and create record"""
        # Save file to disk
        file_ext = os.path.splitext(filename)[1]
        stored_filename = f"{user_id}_{filename}"
        if project_id:
             stored_filename = f"{user_id}_{project_id}_{filename}"
             
        file_path = UPLOAD_DIR / stored_filename
        
        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file_obj.file, buffer)
        finally:
            file_obj.file.close()
            
        # Create DB record
        if not db.pool:
            raise Exception("Database not connected")
            
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO documents (project_id, user_id, filename, file_path, file_type, embedding_status) 
                   VALUES ($1, $2, $3, $4, $5, 'pending') 
                   RETURNING *""",
                project_id, user_id, filename, str(file_path), file_ext
            )
            return dict(row)

    async def get_documents(self, project_id: str) -> List[Dict]:
        """Get documents for a project"""
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM documents WHERE project_id = $1 ORDER BY created_at DESC", project_id)
            return [dict(row) for row in rows]
            
    async def get_user_documents(self, user_id: str) -> List[Dict]:
        """Get all documents for a user"""
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM documents WHERE user_id = $1 ORDER BY created_at DESC", user_id)
            return [dict(row) for row in rows]

    async def delete_document(self, user_id: str, document_id: str) -> bool:
        """Delete a document by ID and user_id"""
        if not db.pool:
            return False
            
        async with db.pool.acquire() as conn:
            # First get the file path to delete from disk
            row = await conn.fetchrow("SELECT file_path FROM documents WHERE id = $1 AND user_id = $2", document_id, user_id)
            if not row:
                return False
                
            file_path = row['file_path']
            
            # Delete from DB
            await conn.execute("DELETE FROM documents WHERE id = $1 AND user_id = $2", document_id, user_id)
            
            # Delete from disk
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to delete file {file_path}: {e}")
                
            return True

document_service = DocumentService()
