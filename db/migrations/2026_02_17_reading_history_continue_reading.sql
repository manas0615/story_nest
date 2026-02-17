BEGIN;

CREATE TABLE IF NOT EXISTS reading_history (
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    last_chapter_id INT NOT NULL REFERENCES chapters(chapter_id) ON DELETE CASCADE,
    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, story_id)
);

CREATE INDEX IF NOT EXISTS idx_reading_history_user_last_read
ON reading_history(user_id, last_read_at DESC);

COMMIT;
