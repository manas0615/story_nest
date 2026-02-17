-- PL/pgSQL Functions for Story Nest

-- Function to calculate average rating for a story
CREATE OR REPLACE FUNCTION calculate_average_rating(p_story_id INT)
RETURNS NUMERIC AS $$
DECLARE
    avg_rating NUMERIC;
BEGIN
    SELECT COALESCE(AVG(rating), 0) INTO avg_rating
    FROM ratings
    WHERE story_id = p_story_id;
    
    RETURN ROUND(avg_rating, 2);
END;
$$ LANGUAGE plpgsql;

-- Stored Procedure to publish a story
CREATE OR REPLACE FUNCTION publish_story(p_story_id INT, p_author_id INT)
RETURNS BOOLEAN AS $$
DECLARE
    chapter_count INT;
    story_exists BOOLEAN;
BEGIN
    -- Check if story exists and belongs to author
    SELECT EXISTS(
        SELECT 1 FROM stories 
        WHERE story_id = p_story_id AND author_id = p_author_id
    ) INTO story_exists;
    
    IF NOT story_exists THEN
        RAISE EXCEPTION 'Story not found or unauthorized';
    END IF;
    
    -- Check if story has at least one chapter
    SELECT COUNT(*) INTO chapter_count
    FROM chapters
    WHERE story_id = p_story_id;
    
    IF chapter_count = 0 THEN
        RAISE EXCEPTION 'Cannot publish story without chapters';
    END IF;
    
    -- Publish the story
    UPDATE stories
    SET is_published = TRUE,
        published_at = CURRENT_TIMESTAMP
    WHERE story_id = p_story_id;
    
    -- Create notification for author
    INSERT INTO notifications (user_id, message)
    VALUES (p_author_id, 'Your story has been published successfully!');
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Function to create notification for new chapter comment
CREATE OR REPLACE FUNCTION notify_author_on_chapter_comment()
RETURNS TRIGGER AS $$
DECLARE
    author_id INT;
    commenter_name VARCHAR(100);
    story_title VARCHAR(255);
BEGIN
    -- Get author_id and story title
    SELECT s.author_id, s.title INTO author_id, story_title
    FROM stories s
    WHERE s.story_id = NEW.story_id;
    
    -- Get commenter username
    SELECT username INTO commenter_name
    FROM users
    WHERE user_id = NEW.user_id;
    
    -- Avoid self-notification if the author comments on their own chapter.
    IF author_id <> NEW.user_id THEN
        INSERT INTO notifications (user_id, message)
        VALUES (author_id, commenter_name || ' commented on your story "' || story_title || '"');
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to create notification for new rating
CREATE OR REPLACE FUNCTION notify_author_on_rating()
RETURNS TRIGGER AS $$
DECLARE
    author_id INT;
    rater_name VARCHAR(100);
    story_title VARCHAR(255);
BEGIN
    -- Get author_id and story title
    SELECT s.author_id, s.title INTO author_id, story_title
    FROM stories s
    WHERE s.story_id = NEW.story_id;
    
    -- Get rater username
    SELECT username INTO rater_name
    FROM users
    WHERE user_id = NEW.user_id;
    
    -- Create notification
    INSERT INTO notifications (user_id, message)
    VALUES (author_id, rater_name || ' rated your story "' || story_title || '" with ' || NEW.rating || ' stars');
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to get story statistics
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
