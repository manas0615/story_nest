-- StoryNest migration: unified users + discovery/follow/comment enhancements
-- Run this on existing databases after backups.

BEGIN;

-- 1) Unified users: behavior-based author flag.
ALTER TABLE users
ADD COLUMN IF NOT EXISTS is_author BOOLEAN DEFAULT FALSE;

-- Allow role_id to be optional for normal users while preserving admin role usage.
ALTER TABLE users
ALTER COLUMN role_id DROP NOT NULL;

-- 2) Follow/favorite table used for discovery sorting and story engagement.
CREATE TABLE IF NOT EXISTS story_follows (
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (story_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_story_follows_story ON story_follows(story_id);
CREATE INDEX IF NOT EXISTS idx_story_follows_user ON story_follows(user_id);

-- 3) Chapter-level comments with optional author replies.
CREATE TABLE IF NOT EXISTS chapter_comments (
    comment_id SERIAL PRIMARY KEY,
    chapter_id INT NOT NULL REFERENCES chapters(chapter_id) ON DELETE CASCADE,
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id),
    parent_comment_id INT REFERENCES chapter_comments(comment_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chapter_comments_chapter ON chapter_comments(chapter_id);
CREATE INDEX IF NOT EXISTS idx_chapter_comments_story ON chapter_comments(story_id);
CREATE INDEX IF NOT EXISTS idx_chapter_comments_parent ON chapter_comments(parent_comment_id);

-- 4) Functions and trigger updates for chapter comment notifications and stats.
CREATE OR REPLACE FUNCTION notify_author_on_chapter_comment()
RETURNS TRIGGER AS $$
DECLARE
    author_id INT;
    commenter_name VARCHAR(100);
    story_title VARCHAR(255);
BEGIN
    SELECT s.author_id, s.title INTO author_id, story_title
    FROM stories s
    WHERE s.story_id = NEW.story_id;

    SELECT username INTO commenter_name
    FROM users
    WHERE user_id = NEW.user_id;

    IF author_id <> NEW.user_id THEN
        INSERT INTO notifications (user_id, message)
        VALUES (author_id, commenter_name || ' commented on your story "' || story_title || '"');
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_story_stats(p_story_id INT)
RETURNS TABLE (
    total_views INT,
    total_ratings BIGINT,
    average_rating NUMERIC,
    total_comments BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.view_count,
        COUNT(DISTINCT r.rating_id),
        calculate_average_rating(p_story_id),
        COUNT(DISTINCT c.comment_id)
    FROM stories s
    LEFT JOIN ratings r ON s.story_id = r.story_id
    LEFT JOIN chapter_comments c ON s.story_id = c.story_id
    WHERE s.story_id = p_story_id
    GROUP BY s.story_id, s.view_count;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_comment_notification ON comments;
DROP TRIGGER IF EXISTS trigger_comment_notification ON chapter_comments;

CREATE TRIGGER trigger_comment_notification
AFTER INSERT ON chapter_comments
FOR EACH ROW
EXECUTE FUNCTION notify_author_on_chapter_comment();

COMMIT;
