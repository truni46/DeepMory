-- Migration 004: agent memory history

CREATE TABLE IF NOT EXISTS "agentMemoryHistory" (
    "id"         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "memoryId"   UUID NOT NULL REFERENCES "agentMemories"("id") ON DELETE CASCADE,
    "oldMemory"  TEXT,
    "newMemory"  TEXT,
    "event"      VARCHAR(16) NOT NULL CHECK ("event" IN ('ADD', 'UPDATE', 'DELETE')),
    "createdAt"  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_history_memory_id ON "agentMemoryHistory"("memoryId");
