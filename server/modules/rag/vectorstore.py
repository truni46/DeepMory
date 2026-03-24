from typing import List, Dict, Optional, Any
from typing import Protocol
import os
import json
from config.logger import logger


class VectorStoreProvider(Protocol):
    async def upsert(self, collection: str, points: List[Dict]) -> None: ...
    async def search(self, collection: str, vector: List[float], limit: int, filter: Optional[Dict]) -> List[Dict]: ...
    async def delete(self, collection: str, ids: List[str]) -> None: ...
    async def createCollection(self, collection: str, dim: int) -> None: ...
    async def collectionExists(self, collection: str) -> bool: ...


# ---------------------------------------------------------------------------
# Qdrant
# ---------------------------------------------------------------------------

class QdrantProvider:
    def __init__(self, url: str = None, apiKey: str = None):
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.apiKey = apiKey or os.getenv("QDRANT_API_KEY") or None
        self._client = None

    async def _getClient(self):
        if not self._client:
            from qdrant_client import AsyncQdrantClient
            self._client = AsyncQdrantClient(url=self.url, api_key=self.apiKey)
        return self._client

    async def createCollection(self, collection: str, dim: int) -> None:
        from qdrant_client.models import Distance, VectorParams
        client = await self._getClient()
        await client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        logger.info(f"Qdrant: created collection '{collection}' dim={dim}")

    async def collectionExists(self, collection: str) -> bool:
        client = await self._getClient()
        try:
            await client.get_collection(collection)
            return True
        except Exception:
            return False

    async def upsert(self, collection: str, points: List[Dict]) -> None:
        from qdrant_client.models import PointStruct
        client = await self._getClient()
        qdrant_points = [
            PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {}))
            for p in points
        ]
        await client.upsert(collection_name=collection, points=qdrant_points)

    async def search(
        self,
        collection: str,
        vector: List[float],
        limit: int,
        filter: Optional[Dict] = None,
    ) -> List[Dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = await self._getClient()

        qdrant_filter = None
        if filter:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = await client.search(
            collection_name=collection,
            query_vector=vector,
            limit=limit,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        return [{"id": str(r.id), "score": r.score, "payload": r.payload} for r in results]

    async def delete(self, collection: str, ids: List[str]) -> None:
        from qdrant_client.models import PointIdsList
        client = await self._getClient()
        await client.delete(collection_name=collection, points_selector=PointIdsList(points=ids))


# ---------------------------------------------------------------------------
# PgVector
# ---------------------------------------------------------------------------

class PgVectorProvider:
    """Uses the existing asyncpg pool from config.database. Stores vectors in vector_points table."""

    async def createCollection(self, collection: str, dim: int) -> None:
        from config.database import db
        if not (db.useDatabase and db.pool):
            return
        async with db.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS vector_points (
                    id TEXT NOT NULL,
                    collection TEXT NOT NULL,
                    vector vector({dim}),
                    payload JSONB DEFAULT '{{}}',
                    "createdAt" TIMESTAMPTZ DEFAULT now(),
                    PRIMARY KEY (collection, id)
                )
            """)
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_vp_collection ON vector_points(collection)"
            )
        logger.info(f"PgVector: ensured collection '{collection}' dim={dim}")

    async def collectionExists(self, collection: str) -> bool:
        from config.database import db
        if not (db.useDatabase and db.pool):
            return False
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM vector_points WHERE collection = $1 LIMIT 1", collection
            )
            return row is not None

    async def upsert(self, collection: str, points: List[Dict]) -> None:
        from config.database import db
        if not (db.useDatabase and db.pool):
            return
        async with db.pool.acquire() as conn:
            for p in points:
                await conn.execute(
                    """INSERT INTO vector_points (id, collection, vector, payload)
                       VALUES ($1, $2, $3::vector, $4)
                       ON CONFLICT (collection, id) DO UPDATE
                       SET vector = EXCLUDED.vector, payload = EXCLUDED.payload""",
                    p["id"],
                    collection,
                    str(p["vector"]),
                    json.dumps(p.get("payload", {})),
                )

    async def search(
        self,
        collection: str,
        vector: List[float],
        limit: int,
        filter: Optional[Dict] = None,
    ) -> List[Dict]:
        from config.database import db
        if not (db.useDatabase and db.pool):
            return []
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, payload, 1 - (vector <=> $1::vector) AS score
                   FROM vector_points
                   WHERE collection = $2
                   ORDER BY vector <=> $1::vector
                   LIMIT $3""",
                str(vector),
                collection,
                limit,
            )
            return [{"id": r["id"], "score": float(r["score"]), "payload": r["payload"]} for r in rows]

    async def delete(self, collection: str, ids: List[str]) -> None:
        from config.database import db
        if not (db.useDatabase and db.pool):
            return
        async with db.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM vector_points WHERE collection = $1 AND id = ANY($2)",
                collection,
                ids,
            )


# ---------------------------------------------------------------------------
# Milvus
# ---------------------------------------------------------------------------

class MilvusProvider:
    def __init__(self, uri: str = None, token: str = None):
        self.uri = uri or os.getenv("MILVUS_URI", "http://localhost:19530")
        self.token = token or os.getenv("MILVUS_TOKEN", "")
        self._connected = False

    def _connect(self):
        if not self._connected:
            from pymilvus import connections
            connections.connect(uri=self.uri, token=self.token)
            self._connected = True

    async def createCollection(self, collection: str, dim: int) -> None:
        import asyncio
        from pymilvus import CollectionSchema, FieldSchema, DataType, Collection, utility
        self._connect()

        def _create():
            if utility.has_collection(collection):
                return
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=128),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="payload", dtype=DataType.VARCHAR, max_length=65535),
            ]
            schema = CollectionSchema(fields=fields)
            col = Collection(name=collection, schema=schema)
            col.create_index("vector", {"metric_type": "COSINE", "index_type": "HNSW", "params": {"M": 8, "efConstruction": 64}})

        await asyncio.get_event_loop().run_in_executor(None, _create)
        logger.info(f"Milvus: ensured collection '{collection}' dim={dim}")

    async def collectionExists(self, collection: str) -> bool:
        import asyncio
        from pymilvus import utility
        self._connect()
        return await asyncio.get_event_loop().run_in_executor(None, utility.has_collection, collection)

    async def upsert(self, collection: str, points: List[Dict]) -> None:
        import asyncio
        import json as json_lib
        from pymilvus import Collection
        self._connect()

        def _upsert():
            col = Collection(collection)
            ids = [p["id"] for p in points]
            vectors = [p["vector"] for p in points]
            payloads = [json_lib.dumps(p.get("payload", {})) for p in points]
            col.upsert([ids, vectors, payloads])
            col.flush()

        await asyncio.get_event_loop().run_in_executor(None, _upsert)

    async def search(
        self,
        collection: str,
        vector: List[float],
        limit: int,
        filter: Optional[Dict] = None,
    ) -> List[Dict]:
        import asyncio
        import json as json_lib
        from pymilvus import Collection
        self._connect()

        def _search():
            col = Collection(collection)
            col.load()
            results = col.search(
                data=[vector],
                anns_field="vector",
                param={"metric_type": "COSINE", "params": {"ef": 64}},
                limit=limit,
                output_fields=["payload"],
            )
            out = []
            for hit in results[0]:
                out.append({
                    "id": hit.id,
                    "score": hit.score,
                    "payload": json_lib.loads(hit.entity.get("payload", "{}")),
                })
            return out

        return await asyncio.get_event_loop().run_in_executor(None, _search)

    async def delete(self, collection: str, ids: List[str]) -> None:
        import asyncio
        from pymilvus import Collection
        self._connect()

        def _delete():
            col = Collection(collection)
            id_list = ", ".join(f'"{i}"' for i in ids)
            col.delete(f"id in [{id_list}]")

        await asyncio.get_event_loop().run_in_executor(None, _delete)


# ---------------------------------------------------------------------------
# Service wrapper + singleton
# ---------------------------------------------------------------------------

class VectorStoreService:
    def __init__(self):
        self.providerName = os.getenv("VECTOR_STORE_TYPE", "qdrant").lower()
        self.provider = self._buildProvider()
        logger.info(f"VectorStore initialized: {self.providerName}")

    def _buildProvider(self):
        try:
            if self.providerName == "qdrant":
                return QdrantProvider()
            elif self.providerName == "pgvector":
                return PgVectorProvider()
            elif self.providerName == "milvus":
                return MilvusProvider()
            else:
                logger.warning(f"Unknown VECTOR_STORE_TYPE '{self.providerName}', falling back to pgvector.")
                return PgVectorProvider()
        except Exception as e:
            logger.error(f"Failed to initialize vector store '{self.providerName}': {e}")
            return PgVectorProvider()

    async def ensureCollection(self, collection: str, dim: int) -> None:
        if not await self.provider.collectionExists(collection):
            await self.provider.createCollection(collection, dim)

    async def upsert(self, collection: str, points: List[Dict]) -> None:
        await self.provider.upsert(collection, points)

    async def search(
        self,
        collection: str,
        vector: List[float],
        limit: int,
        filter: Optional[Dict] = None,
    ) -> List[Dict]:
        return await self.provider.search(collection, vector, limit, filter)

    async def delete(self, collection: str, ids: List[str]) -> None:
        await self.provider.delete(collection, ids)


vectorStore = VectorStoreService()
