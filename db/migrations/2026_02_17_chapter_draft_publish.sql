BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'chapter_status') THEN
        CREATE TYPE chapter_status AS ENUM ('draft', 'published');
    END IF;
END $$;

ALTER TABLE chapters
    ADD COLUMN IF NOT EXISTS status chapter_status;

ALTER TABLE chapters
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMP NULL;

UPDATE chapters c
SET
    status = CASE
        WHEN s.is_published = TRUE THEN 'published'::chapter_status
        ELSE 'draft'::chapter_status
    END,
    published_at = CASE
        WHEN s.is_published = TRUE THEN COALESCE(s.published_at, c.created_at)
        ELSE NULL
    END
FROM stories s
WHERE c.story_id = s.story_id
  AND c.status IS NULL;

ALTER TABLE chapters
    ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE chapters
    ALTER COLUMN status SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chapters_story_status
    ON chapters(story_id, status);

COMMIT;
