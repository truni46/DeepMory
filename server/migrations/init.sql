-- DeepMory - Consolidated Database Initialization
-- Auto-runs on first container startup via init-db.sh

BEGIN;

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Utility function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW."updatedAt" = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100),
    "fullName" VARCHAR(255),
    "passwordHash" VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    preferences JSONB DEFAULT '{}',
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now()
);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "userId" UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    config JSONB DEFAULT '{}',
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now()
);

-- Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "projectId" UUID REFERENCES projects(id) ON DELETE SET NULL,
    "userId" UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Messages
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "conversationId" UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    model VARCHAR(100),
    "parentId" UUID REFERENCES messages(id),
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Documents (RAG)
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "projectId" UUID REFERENCES projects(id) ON DELETE CASCADE,
    "userId" UUID REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    "filePath" VARCHAR(1024) NOT NULL,
    "fileType" VARCHAR(50),
    "fileSize" BIGINT,
    "contentHash" VARCHAR(64),
    "embeddingStatus" VARCHAR(50) DEFAULT 'pending',
    scope VARCHAR(20) NOT NULL DEFAULT 'personal',
    "ownerId" UUID NOT NULL,
    "ownerType" VARCHAR(20) NOT NULL DEFAULT 'user',
    "storedFilename" VARCHAR(255) NOT NULL,
    "embeddingError" TEXT,
    "chunkCount" INT,
    "pageCount" INT,
    summary TEXT,
    "summaryStatus" VARCHAR(20) NOT NULL DEFAULT 'pending',
    description TEXT,
    tags TEXT[],
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Memories
CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "userId" UUID REFERENCES users(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    context JSONB,
    "importanceScore" FLOAT DEFAULT 1.0,
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "lastAccessedAt" TIMESTAMPTZ DEFAULT now()
);

-- MCP Servers
CREATE TABLE IF NOT EXISTS "mcpServers" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    "userId" UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    url VARCHAR(2048) NOT NULL,
    config JSONB DEFAULT '{}',
    "isActive" BOOLEAN DEFAULT TRUE,
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now()
);

-- Settings
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(255) PRIMARY KEY,
    value JSONB NOT NULL,
    "updatedAt" TIMESTAMPTZ DEFAULT now()
);

-- Conversation Summaries (short-term memory)
CREATE TABLE IF NOT EXISTS "conversationSummaries" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "conversationId" UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    "tokenCount" INTEGER DEFAULT 0,
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now(),
    UNIQUE("conversationId")
);

-- Agent Tasks
CREATE TABLE IF NOT EXISTS "agentTasks" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    "conversationId" UUID REFERENCES conversations(id) ON DELETE SET NULL,
    "projectId" UUID REFERENCES projects(id) ON DELETE SET NULL,
    goal TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','completed','failed','partial_failure','cancelled')),
    "errorMessage" TEXT,
    "finalReport" TEXT,
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now()
);

-- Agent Runs
CREATE TABLE IF NOT EXISTS "agentRuns" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "taskId" UUID NOT NULL REFERENCES "agentTasks"(id) ON DELETE CASCADE,
    "agentType" VARCHAR(64) NOT NULL,
    "iterationNum" INTEGER NOT NULL,
    input JSONB,
    output JSONB,
    status VARCHAR(32) NOT NULL,
    "durationMs" INTEGER,
    "createdAt" TIMESTAMPTZ DEFAULT now()
);

-- Agent Memories
CREATE TABLE IF NOT EXISTS "agentMemories" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "agentType" VARCHAR(64) NOT NULL,
    "userId" UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    "taskId" UUID REFERENCES "agentTasks"(id) ON DELETE SET NULL,
    "memoryType" VARCHAR(16) NOT NULL
        CHECK ("memoryType" IN ('episodic','semantic','procedural')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    "vectorId" VARCHAR(128),
    "createdAt" TIMESTAMPTZ DEFAULT now()
);

-- Agent Memory History
CREATE TABLE IF NOT EXISTS "agentMemoryHistory" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "memoryId" UUID NOT NULL REFERENCES "agentMemories"(id) ON DELETE CASCADE,
    "oldMemory" TEXT,
    "newMemory" TEXT,
    event VARCHAR(16) NOT NULL CHECK (event IN ('ADD', 'UPDATE', 'DELETE')),
    "createdAt" TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations("createdAt" DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_metadata ON conversations USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages("conversationId");
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages("createdAt");
CREATE INDEX IF NOT EXISTS idx_messages_content_search ON messages USING GIN(to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS idx_memories_userid ON memories("userId");
CREATE INDEX IF NOT EXISTS idx_agent_tasks_user ON "agentTasks"("userId");
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON "agentTasks"(status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_task ON "agentRuns"("taskId");
CREATE INDEX IF NOT EXISTS idx_agent_memories_user_type ON "agentMemories"("userId", "agentType", "memoryType");
CREATE INDEX IF NOT EXISTS idx_agent_memory_history_memory_id ON "agentMemoryHistory"("memoryId");

-- Triggers
DROP TRIGGER IF EXISTS trg_conversations_updated_at ON conversations;
CREATE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_settings_updated_at ON settings;
CREATE TRIGGER trg_settings_updated_at
    BEFORE UPDATE ON settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_agent_tasks_updated_at ON "agentTasks";
CREATE TRIGGER trg_agent_tasks_updated_at
    BEFORE UPDATE ON "agentTasks"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Default settings
INSERT INTO settings (key, value) VALUES
    ('communication_mode', '"streaming"'::jsonb),
    ('theme', '"dark-green"'::jsonb),
    ('show_timestamps', 'true'::jsonb),
    ('ai_response_speed', '"medium"'::jsonb)
ON CONFLICT (key) DO NOTHING;

COMMIT;
