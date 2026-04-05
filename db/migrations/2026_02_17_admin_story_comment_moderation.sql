-- Story moderation states for admin hide/soft-remove flows.
ALTER TABLE stories
ADD COLUMN IF NOT EXISTS moderation_status VARCHAR(20) NOT NULL DEFAULT 'active';

UPDATE stories
SET moderation_status = 'active'
WHERE moderation_status IS NULL;

ALTER TABLE stories
DROP CONSTRAINT IF EXISTS stories_moderation_status_check;

ALTER TABLE stories
ADD CONSTRAINT stories_moderation_status_check
CHECK (moderation_status IN ('active', 'hidden', 'removed'));

CREATE INDEX IF NOT EXISTS idx_stories_moderation_status ON stories(moderation_status);

-- Comment visibility for moderation.
ALTER TABLE chapter_comments
ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN DEFAULT FALSE;

UPDATE chapter_comments
SET is_hidden = FALSE
WHERE is_hidden IS NULL;

CREATE INDEX IF NOT EXISTS idx_chapter_comments_hidden ON chapter_comments(is_hidden);
