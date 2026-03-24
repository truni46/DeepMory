-- Migration 002: memory and RAG infrastructure

-- Short-term memory: one summary row per conversation
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "conversationId" UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    summary         TEXT NOT NULL,
    "tokenCount"    INTEGER DEFAULT 0,
    "createdAt"     TIMESTAMPTZ DEFAULT now(),
    "updatedAt"     TIMESTAMPTZ DEFAULT now(),
    UNIQUE("conversationId")
);

-- Long-term memory: index on userId for fast per-user lookups
CREATE INDEX IF NOT EXISTS idx_memories_userid ON memories("userId");

-- --------------------------------------------------------------------------
-- pgvector tables (only used when VECTOR_STORE_TYPE=pgvector)
-- Safe to run even when pgvector extension is not installed;
-- the extension creation will simply fail and can be skipped.
-- --------------------------------------------------------------------------

-- Enable pgvector extension (requires PostgreSQL pgvector plugin)
-- CREATE EXTENSION IF NOT EXISTS vector;

-- Generic vector store table used by PgVectorProvider
-- CREATE TABLE IF NOT EXISTS vector_points (
--     id          TEXT NOT NULL,
--     collection  TEXT NOT NULL,
--     vector      vector(1536),
--     payload     JSONB DEFAULT '{}',
--     "createdAt" TIMESTAMPTZ DEFAULT now(),
--     PRIMARY KEY (collection, id)
-- );
--
-- CREATE INDEX IF NOT EXISTS idx_vector_points_collection
--     ON vector_points(collection);
--
-- CREATE INDEX IF NOT EXISTS idx_vector_points_hnsw
--     ON vector_points USING hnsw (vector vector_cosine_ops);
