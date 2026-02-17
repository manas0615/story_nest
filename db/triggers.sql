-- Triggers for Story Nest

-- Trigger to increment view count when story is viewed
CREATE OR REPLACE FUNCTION increment_view_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE stories 
    SET view_count = view_count + 1
    WHERE story_id = NEW.story_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: This trigger will be activated when a view record is inserted
-- For simplicity, we'll track views through a separate mechanism in the application

-- Trigger for comment notifications
CREATE TRIGGER trigger_comment_notification
AFTER INSERT ON chapter_comments
FOR EACH ROW
EXECUTE FUNCTION notify_author_on_chapter_comment();

-- Trigger for rating notifications
CREATE TRIGGER trigger_rating_notification
AFTER INSERT ON ratings
FOR EACH ROW
EXECUTE FUNCTION notify_author_on_rating();
