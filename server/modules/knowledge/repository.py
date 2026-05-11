# server/modules/knowledge/repository.py
from typing import Dict, List, Optional, Tuple
import uuid
from datetime import datetime, timezone

from config.database import db


class DocumentRepository:

    async def create(
        self,
        userId: str,
        filename: str,
        storedFilename: str,
        filePath: str,
        fileType: str,
        fileSize: int,
        contentHash: str,
        scope: str = 'personal',
        ownerId: str = None,
        ownerType: str = 'user',
    ) -> Dict:
        docId = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        ownerIdVal = ownerId or userId
        record = {
            "id": docId,
            "userId": userId,
            "scope": scope,
            "ownerId": ownerIdVal,
            "ownerType": ownerType,
            "filename": filename,
            "storedFilename": storedFilename,
            "filePath": filePath,
            "fileType": fileType,
            "fileSize": fileSize,
            "contentHash": contentHash,
            "embeddingStatus": "pending",
            "summaryStatus": "pending",
            "createdAt": now.isoformat(),
            "updatedAt": now.isoformat(),
        }

        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO documents (
                        id, "userId", scope, "ownerId", "ownerType",
                        filename, "storedFilename", "filePath", "fileType", "fileSize", "contentHash",
                        "embeddingStatus", "summaryStatus", "createdAt", "updatedAt"
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'pending','pending',$12,$13)
                    RETURNING *""",
                    docId, userId, scope, ownerIdVal, ownerType,
                    filename, storedFilename, filePath, fileType, fileSize, contentHash,
                    now, now,
                )
                return dict(row)
        else:
            data = db.read_json("documents")
            data[docId] = record
            db.write_json("documents", data)
            return record

    async def getByUser(self, userId: str, scope: str = None) -> List[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                if scope:
                    rows = await conn.fetch(
                        """SELECT * FROM documents WHERE "userId" = $1 AND scope = $2
                           ORDER BY "createdAt" DESC""",
                        userId, scope,
                    )
                else:
                    rows = await conn.fetch(
                        """SELECT * FROM documents WHERE "userId" = $1
                           ORDER BY "createdAt" DESC""",
                        userId,
                    )
                return [dict(r) for r in rows]
        else:
            data = db.read_json("documents")
            docs = [d for d in data.values() if str(d.get("userId")) == str(userId)]
            if scope:
                docs = [d for d in docs if d.get("scope") == scope]
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

    async def updateEmbedding(
        self,
        documentId: str,
        status: str,
        chunkCount: int = None,
        pageCount: int = None,
        errorMsg: str = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE documents SET
                        "embeddingStatus" = $1,
                        "chunkCount" = COALESCE($2, "chunkCount"),
                        "pageCount" = COALESCE($3, "pageCount"),
                        "embeddingError" = $4,
                        "updatedAt" = $5
                    WHERE id = $6""",
                    status, chunkCount, pageCount, errorMsg, now, documentId,
                )
        else:
            data = db.read_json("documents")
            if documentId in data:
                data[documentId]["embeddingStatus"] = status
                if chunkCount is not None:
                    data[documentId]["chunkCount"] = chunkCount
                if pageCount is not None:
                    data[documentId]["pageCount"] = pageCount
                if errorMsg is not None:
                    data[documentId]["embeddingError"] = errorMsg
                data[documentId]["updatedAt"] = now.isoformat()
                db.write_json("documents", data)

    async def updateSummary(
        self,
        documentId: str,
        status: str,
        summary: str = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE documents SET
                        "summaryStatus" = $1,
                        summary = COALESCE($2, summary),
                        "updatedAt" = $3
                    WHERE id = $4""",
                    status, summary, now, documentId,
                )
        else:
            data = db.read_json("documents")
            if documentId in data:
                data[documentId]["summaryStatus"] = status
                if summary is not None:
                    data[documentId]["summary"] = summary
                data[documentId]["updatedAt"] = now.isoformat()
                db.write_json("documents", data)

    async def updateOcr(
        self,
        documentId: str,
        ocrStatus: str,
        ocrFilePath: str = None,
        isScanned: bool = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE documents SET
                        "ocrStatus" = $1,
                        "ocrFilePath" = COALESCE($2, "ocrFilePath"),
                        "isScanned" = COALESCE($3, "isScanned"),
                        "updatedAt" = $4
                    WHERE id = $5""",
                    ocrStatus, ocrFilePath, isScanned, now, documentId,
                )
        else:
            data = db.read_json("documents")
            if documentId in data:
                data[documentId]["ocrStatus"] = ocrStatus
                if ocrFilePath is not None:
                    data[documentId]["ocrFilePath"] = ocrFilePath
                if isScanned is not None:
                    data[documentId]["isScanned"] = isScanned
                data[documentId]["updatedAt"] = now.isoformat()
                db.write_json("documents", data)

    async def updateFilePath(
        self, documentId: str, filePath: str, fileType: str = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """UPDATE documents SET
                        "filePath" = $1,
                        "fileType" = COALESCE($2, "fileType"),
                        "updatedAt" = $3
                    WHERE id = $4""",
                    filePath, fileType, now, documentId,
                )
        else:
            data = db.read_json("documents")
            if documentId in data:
                data[documentId]["filePath"] = filePath
                if fileType:
                    data[documentId]["fileType"] = fileType
                data[documentId]["updatedAt"] = now.isoformat()
                db.write_json("documents", data)

    async def update(self, documentId: str, userId: str, fields: Dict) -> Optional[Dict]:
        ALLOWED = {"filename", "scope", "ownerId", "ownerType"}
        safe = {k: v for k, v in fields.items() if k in ALLOWED and v is not None}
        if not safe:
            return await self.getById(documentId)
        now = datetime.now(timezone.utc)
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                setClauses = ", ".join(f'"{k}" = ${i+2}' for i, k in enumerate(safe))
                values = list(safe.values())
                row = await conn.fetchrow(
                    f"""UPDATE documents SET {setClauses}, "updatedAt" = ${len(values)+2}
                        WHERE id = $1 AND "userId" = ${len(values)+3}
                        RETURNING *""",
                    documentId, *values, now, userId,
                )
                return dict(row) if row else None
        else:
            data = db.read_json("documents")
            doc = data.get(documentId)
            if not doc or str(doc.get("userId")) != str(userId):
                return None
            doc.update(safe)
            doc["updatedAt"] = now.isoformat()
            db.write_json("documents", data)
            return doc

    async def getByHashAndOwner(self, contentHash: str, ownerId: str) -> Optional[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT * FROM documents WHERE "contentHash" = $1 AND "ownerId" = $2
                       ORDER BY "createdAt" DESC LIMIT 1""",
                    contentHash, ownerId,
                )
                return dict(row) if row else None
        else:
            data = db.read_json("documents")
            matches = [
                d for d in data.values()
                if d.get("contentHash") == contentHash and str(d.get("ownerId")) == str(ownerId)
            ]
            if not matches:
                return None
            matches.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            return matches[0]

    async def delete(self, documentId: str, userId: str) -> Optional[Tuple[str, str]]:
        """Returns (filePath, ownerId) if deleted, None if not found/unauthorized."""
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT "filePath", "ownerId" FROM documents
                       WHERE id = $1 AND "userId" = $2""",
                    documentId, userId,
                )
                if not row:
                    return None
                await conn.execute(
                    """DELETE FROM documents WHERE id = $1 AND "userId" = $2""",
                    documentId, userId,
                )
                return row["filePath"], str(row["ownerId"])
        else:
            data = db.read_json("documents")
            doc = data.get(documentId)
            if not doc or str(doc.get("userId")) != str(userId):
                return None
            del data[documentId]
            db.write_json("documents", data)
            return doc.get("filePath"), doc.get("ownerId")


documentRepository = DocumentRepository()
