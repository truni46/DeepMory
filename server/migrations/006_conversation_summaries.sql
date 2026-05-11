CREATE TABLE IF NOT EXISTS "conversationSummaries" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "conversationId" UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    "tokenCount" INTEGER DEFAULT 0,
    "createdAt" TIMESTAMPTZ DEFAULT now(),
    "updatedAt" TIMESTAMPTZ DEFAULT now(),
    UNIQUE("conversationId")
);
