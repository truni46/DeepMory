-- Migration Script: snake_case -> camelCase (PostgreSQL)
-- Chạy script này để rename columns trong database đang tồn tại
-- QUAN TRỌNG: Backup database trước khi chạy!

BEGIN;

-- ============================================================
-- Table: users
-- ============================================================
ALTER TABLE users RENAME COLUMN full_name TO "fullName";
ALTER TABLE users RENAME COLUMN password_hash TO "passwordHash";
ALTER TABLE users RENAME COLUMN created_at TO "createdAt";
ALTER TABLE users RENAME COLUMN updated_at TO "updatedAt";

-- ============================================================
-- Table: projects
-- ============================================================
ALTER TABLE projects RENAME COLUMN user_id TO "userId";
ALTER TABLE projects RENAME COLUMN created_at TO "createdAt";
ALTER TABLE projects RENAME COLUMN updated_at TO "updatedAt";

-- ============================================================
-- Table: conversations
-- ============================================================
ALTER TABLE conversations RENAME COLUMN user_id TO "userId";
ALTER TABLE conversations RENAME COLUMN project_id TO "projectId";
ALTER TABLE conversations RENAME COLUMN created_at TO "createdAt";
ALTER TABLE conversations RENAME COLUMN updated_at TO "updatedAt";

-- ============================================================
-- Table: messages
-- ============================================================
ALTER TABLE messages RENAME COLUMN conversation_id TO "conversationId";
ALTER TABLE messages RENAME COLUMN parent_id TO "parentId";
ALTER TABLE messages RENAME COLUMN created_at TO "createdAt";

-- ============================================================
-- Table: documents
-- ============================================================
ALTER TABLE documents RENAME COLUMN user_id TO "userId";
ALTER TABLE documents RENAME COLUMN project_id TO "projectId";
ALTER TABLE documents RENAME COLUMN file_path TO "filePath";
ALTER TABLE documents RENAME COLUMN file_type TO "fileType";
ALTER TABLE documents RENAME COLUMN file_size TO "fileSize";
ALTER TABLE documents RENAME COLUMN content_hash TO "contentHash";
ALTER TABLE documents RENAME COLUMN embedding_status TO "embeddingStatus";
ALTER TABLE documents RENAME COLUMN created_at TO "createdAt";
ALTER TABLE documents RENAME COLUMN updated_at TO "updatedAt";

-- ============================================================
-- Table: memories
-- ============================================================
ALTER TABLE memories RENAME COLUMN user_id TO "userId";
ALTER TABLE memories RENAME COLUMN importance_score TO "importanceScore";
ALTER TABLE memories RENAME COLUMN created_at TO "createdAt";
ALTER TABLE memories RENAME COLUMN last_accessed_at TO "lastAccessedAt";

-- ============================================================
-- Table: mcp_servers
-- ============================================================
ALTER TABLE mcp_servers RENAME COLUMN user_id TO "userId";
ALTER TABLE mcp_servers RENAME COLUMN is_active TO "isActive";
ALTER TABLE mcp_servers RENAME COLUMN created_at TO "createdAt";
ALTER TABLE mcp_servers RENAME COLUMN updated_at TO "updatedAt";

-- ============================================================
-- Table: settings
-- ============================================================
ALTER TABLE settings RENAME COLUMN updated_at TO "updatedAt";

COMMIT;
