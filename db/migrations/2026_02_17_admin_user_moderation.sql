-- Add moderation states for user lifecycle: active, suspended, banned.
ALTER TABLE users
ADD COLUMN IF NOT EXISTS moderation_status VARCHAR(20) NOT NULL DEFAULT 'active';

-- Backfill old blocked users into banned status.
UPDATE users
SET moderation_status = 'banned'
WHERE is_blocked = TRUE
  AND moderation_status = 'active';

-- Keep database-level status integrity.
ALTER TABLE users
DROP CONSTRAINT IF EXISTS users_moderation_status_check;

ALTER TABLE users
ADD CONSTRAINT users_moderation_status_check
CHECK (moderation_status IN ('active', 'suspended', 'banned'));

CREATE INDEX IF NOT EXISTS idx_users_moderation_status ON users(moderation_status);
