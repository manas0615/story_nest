-- Story Nest Database Schema

-- Drop existing tables if they exist
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS reports CASCADE;
DROP TABLE IF EXISTS story_follows CASCADE;
DROP TABLE IF EXISTS reading_history CASCADE;
DROP TABLE IF EXISTS reading_list CASCADE;
DROP TABLE IF EXISTS story_reviews CASCADE;
DROP TABLE IF EXISTS chapter_comments CASCADE;
DROP TABLE IF EXISTS ratings CASCADE;
DROP TABLE IF EXISTS story_tags CASCADE;
DROP TABLE IF EXISTS tags CASCADE;
DROP TABLE IF EXISTS chapters CASCADE;
DROP TABLE IF EXISTS stories CASCADE;
DROP TABLE IF EXISTS genres CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS roles CASCADE;
DROP TYPE IF EXISTS chapter_status CASCADE;

CREATE TYPE chapter_status AS ENUM ('draft', 'published');

-- Roles Table
CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) UNIQUE NOT NULL
);

-- Users Table
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    bio TEXT,
    avatar_url VARCHAR(255),
    role_id INT REFERENCES roles(role_id),
    is_author BOOLEAN DEFAULT FALSE,
    is_blocked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Genres Table
CREATE TABLE genres (
    genre_id SERIAL PRIMARY KEY,
    genre_name VARCHAR(100) UNIQUE NOT NULL
);

-- Stories Table
CREATE TABLE stories (
    story_id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    author_id INT NOT NULL REFERENCES users(user_id),
    genre_id INT NOT NULL REFERENCES genres(genre_id),
    cover_image VARCHAR(255),
    is_published BOOLEAN DEFAULT FALSE,
    view_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);

-- Chapters Table
CREATE TABLE chapters (
    chapter_id SERIAL PRIMARY KEY,
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    chapter_number INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    status chapter_status NOT NULL DEFAULT 'draft',
    published_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(story_id, chapter_number)
);

-- Tags Table
CREATE TABLE tags (
    tag_id SERIAL PRIMARY KEY,
    tag_name VARCHAR(50) UNIQUE NOT NULL
);

-- Story Tags (Many-to-Many)
CREATE TABLE story_tags (
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    tag_id INT NOT NULL REFERENCES tags(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (story_id, tag_id)
);

-- Ratings Table
CREATE TABLE ratings (
    rating_id SERIAL PRIMARY KEY,
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id),
    rating INT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(story_id, user_id)
);

-- Story Reviews Table
CREATE TABLE story_reviews (
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

-- Chapter Comments Table
CREATE TABLE chapter_comments (
    comment_id SERIAL PRIMARY KEY,
    chapter_id INT NOT NULL REFERENCES chapters(chapter_id) ON DELETE CASCADE,
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id),
    parent_comment_id INT REFERENCES chapter_comments(comment_id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Story Follow/Favorite Table
CREATE TABLE story_follows (
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (story_id, user_id)
);

-- Reading List Table
CREATE TABLE reading_list (
    user_id INT NOT NULL REFERENCES users(user_id),
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, story_id)
);

-- Reading History Table
CREATE TABLE reading_history (
    user_id INT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    story_id INT NOT NULL REFERENCES stories(story_id) ON DELETE CASCADE,
    last_chapter_id INT NOT NULL REFERENCES chapters(chapter_id) ON DELETE CASCADE,
    last_read_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, story_id)
);

-- Notifications Table
CREATE TABLE notifications (
    notification_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(user_id),
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reports Table
CREATE TABLE reports (
    report_id SERIAL PRIMARY KEY,
    story_id INT NOT NULL REFERENCES stories(story_id),
    reported_by INT NOT NULL REFERENCES users(user_id),
    reason TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert Default Roles
INSERT INTO roles (role_name) VALUES ('admin');

-- Insert Default Genres
INSERT INTO genres (genre_name) VALUES 
    ('Fantasy'),
    ('Science Fiction'),
    ('Romance'),
    ('Mystery'),
    ('Horror'),
    ('Adventure'),
    ('Drama'),
    ('Comedy');

-- Create Indexes for Performance
CREATE INDEX idx_stories_author ON stories(author_id);
CREATE INDEX idx_stories_genre ON stories(genre_id);
CREATE INDEX idx_stories_published ON stories(is_published);
CREATE INDEX idx_chapters_story ON chapters(story_id);
CREATE INDEX idx_chapters_story_status ON chapters(story_id, status);
CREATE INDEX idx_ratings_story ON ratings(story_id);
CREATE INDEX idx_story_reviews_story_created ON story_reviews(story_id, created_at DESC);
CREATE INDEX idx_story_follows_story ON story_follows(story_id);
CREATE INDEX idx_story_follows_user ON story_follows(user_id);
CREATE INDEX idx_reading_history_user_last_read ON reading_history(user_id, last_read_at DESC);
CREATE INDEX idx_chapter_comments_chapter ON chapter_comments(chapter_id);
CREATE INDEX idx_chapter_comments_story ON chapter_comments(story_id);
CREATE INDEX idx_chapter_comments_parent ON chapter_comments(parent_comment_id);
CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_notifications_user_is_read ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_user_created ON notifications(user_id, created_at DESC);
