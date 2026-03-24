from typing import Dict, List, Optional, Tuple
import uuid
import json
from datetime import datetime

from config.database import db


class DocumentRepository:

    async def create(
        self,
        userId: str,
        filename: str,
        filePath: str,
        fileType: str,
        projectId: Optional[str] = None,
    ) -> Dict:
        docId = str(uuid.uuid4())
        now = datetime.now()
        record = {
            "id": docId,
            "userId": userId,
            "projectId": projectId,
            "filename": filename,
            "filePath": filePath,
            "fileType": fileType,
            "embeddingStatus": "pending",
            "createdAt": now.isoformat(),
        }

        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO documents (id, "userId", "projectId", filename, "filePath", "fileType", "embeddingStatus", "createdAt")
                       VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7)
                       RETURNING *""",
                    docId, userId, projectId, filename, filePath, fileType, now,
                )
                return dict(row)
        else:
            data = db.read_json("documents")
            data[docId] = record
            db.write_json("documents", data)
            return record

    async def getByUser(self, userId: str) -> List[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM documents WHERE "userId" = $1 ORDER BY "createdAt" DESC""",
                    userId,
                )
                return [dict(r) for r in rows]
        else:
            data = db.read_json("documents")
            docs = [d for d in data.values() if str(d.get("userId")) == str(userId)]
            docs.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            return docs

    async def getByProject(self, projectId: str) -> List[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM documents WHERE "projectId" = $1 ORDER BY "createdAt" DESC""",
                    projectId,
                )
                return [dict(r) for r in rows]
        else:
            data = db.read_json("documents")
            docs = [d for d in data.values() if str(d.get("projectId")) == str(projectId)]
            docs.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            return docs

    async def getById(self, documentId: str) -> Optional[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM documents WHERE id = $1", documentId
                )
                return dict(row) if row else None
        else:
            data = db.read_json("documents")
            return data.get(documentId)

    async def updateStatus(self, documentId: str, status: str) -> None:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE documents SET "embeddingStatus" = $1 WHERE id = $2""",
                    status, documentId,
                )
        else:
            data = db.read_json("documents")
            if documentId in data:
                data[documentId]["embeddingStatus"] = status
                db.write_json("documents", data)

    async def delete(self, documentId: str, userId: str) -> Optional[Tuple[str, Optional[str]]]:
        """
        Delete document record. Returns (filePath, projectId) if deleted, None if not found.
        """
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT "filePath", "projectId" FROM documents WHERE id = $1 AND "userId" = $2""",
                    documentId, userId,
                )
                if not row:
                    return None
                await conn.execute(
                    """DELETE FROM documents WHERE id = $1 AND "userId" = $2""",
                    documentId, userId,
                )
                return row["filePath"], row["projectId"]
        else:
            data = db.read_json("documents")
            doc = data.get(documentId)
            if not doc or str(doc.get("userId")) != str(userId):
                return None
            del data[documentId]
            db.write_json("documents", data)
            return doc.get("filePath"), doc.get("projectId")


documentRepository = DocumentRepository()
