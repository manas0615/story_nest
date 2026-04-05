-- Community/Forum core schema.

CREATE TABLE IF NOT EXISTS forum_categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(120) UNIQUE NOT NULL,
    slug VARCHAR(140) UNIQUE NOT NULL,
    description TEXT,
    sort_order INT NOT NULL DEFAULT 0,
    is_admin_only BOOLEAN NOT NULL DEFAULT FALSE,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INT REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS forum_threads (
    thread_id SERIAL PRIMARY KEY,
    category_id INT NOT NULL REFERENCES forum_categories(category_id) ON DELETE CASCADE,
    author_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(220) NOT NULL,
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    is_locked BOOLEAN NOT NULL DEFAULT FALSE,
    view_count INT NOT NULL DEFAULT 0,
    reply_count INT NOT NULL DEFAULT 0,
    last_post_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS forum_posts (
    post_id SERIAL PRIMARY KEY,
    thread_id INT NOT NULL REFERENCES forum_threads(thread_id) ON DELETE CASCADE,
    author_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    deleted_by INT NULL REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_forum_categories_admin_sort
    ON forum_categories(is_admin_only, sort_order, category_id);

CREATE INDEX IF NOT EXISTS idx_forum_threads_category_pinned_last
    ON forum_threads(category_id, is_pinned DESC, last_post_at DESC, thread_id DESC);

CREATE INDEX IF NOT EXISTS idx_forum_threads_author
    ON forum_threads(author_id);

CREATE INDEX IF NOT EXISTS idx_forum_posts_thread_created
    ON forum_posts(thread_id, created_at ASC, post_id ASC);

CREATE INDEX IF NOT EXISTS idx_forum_posts_author
    ON forum_posts(author_id);

CREATE INDEX IF NOT EXISTS idx_forum_posts_deleted
    ON forum_posts(is_deleted);
