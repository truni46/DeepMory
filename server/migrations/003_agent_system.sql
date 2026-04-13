-- Migration 003: agent system tables

CREATE TABLE IF NOT EXISTS "agentTasks" (
    "id"             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId"         UUID NOT NULL REFERENCES users("id") ON DELETE CASCADE,
    "conversationId" UUID REFERENCES conversations("id") ON DELETE SET NULL,
    "projectId"      UUID REFERENCES projects("id") ON DELETE SET NULL,
    "goal"           TEXT NOT NULL,
    "status"         VARCHAR(32) NOT NULL DEFAULT 'running'
                         CHECK ("status" IN ('running','completed','failed','partial_failure','cancelled')),
    "errorMessage"   TEXT,
    "finalReport"    TEXT,
    "createdAt"      TIMESTAMPTZ DEFAULT now(),
    "updatedAt"      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "agentRuns" (
    "id"           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "taskId"       UUID NOT NULL REFERENCES "agentTasks"("id") ON DELETE CASCADE,
    "agentType"    VARCHAR(64) NOT NULL,
    "iterationNum" INTEGER NOT NULL,
    "input"        JSONB,
    "output"       JSONB,
    "status"       VARCHAR(32) NOT NULL,
    "durationMs"   INTEGER,
    "createdAt"    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "agentMemories" (
    "id"         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "agentType"  VARCHAR(64) NOT NULL,
    "userId"     UUID NOT NULL REFERENCES users("id") ON DELETE CASCADE,
    "taskId"     UUID REFERENCES "agentTasks"("id") ON DELETE SET NULL,
    "memoryType" VARCHAR(16) NOT NULL
                     CHECK ("memoryType" IN ('episodic','semantic','procedural')),
    "content"    TEXT NOT NULL,
    "metadata"   JSONB DEFAULT '{}',
    "vectorId"   VARCHAR(128),
    "createdAt"  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_user   ON "agentTasks"("userId");
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON "agentTasks"("status");
CREATE INDEX IF NOT EXISTS idx_agent_runs_task    ON "agentRuns"("taskId");
CREATE INDEX IF NOT EXISTS idx_agent_memories_user_type
    ON "agentMemories"("userId", "agentType", "memoryType");

CREATE OR REPLACE FUNCTION update_agent_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW."updatedAt" = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_tasks_updated_at ON "agentTasks";
CREATE TRIGGER trg_agent_tasks_updated_at
    BEFORE UPDATE ON "agentTasks"
    FOR EACH ROW EXECUTE FUNCTION update_agent_tasks_updated_at();
