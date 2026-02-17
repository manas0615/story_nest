BEGIN;

CREATE TABLE IF NOT EXISTS story_reviews (
    review_id SERIAL PRIMARY KEY,
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(180) NOT NULL,
    body TEXT NOT NULL,
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(story_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_story_reviews_story_created
ON story_reviews(story_id, created_at DESC);

COMMIT;
