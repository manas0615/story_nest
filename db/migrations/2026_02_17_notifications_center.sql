BEGIN;

CREATE TABLE IF NOT EXISTS notifications (
    notification_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_notifications_user
ON notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_notifications_user_is_read
ON notifications(user_id, is_read);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created
ON notifications(user_id, created_at DESC);

COMMIT;
