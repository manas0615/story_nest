from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ForumCategory(Base):
    __tablename__ = 'forum_categories'

    category_id = Column(Integer, primary_key=True)
    name = Column(String(120), unique=True, nullable=False)
    slug = Column(String(140), unique=True, nullable=False)
    description = Column(Text)
    sort_order = Column(Integer, nullable=False, default=0)
    is_admin_only = Column(Boolean, nullable=False, default=False)
    is_locked = Column(Boolean, nullable=False, default=False)
    created_by = Column(Integer, ForeignKey('users.user_id'))
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    threads = relationship('ForumThread', back_populates='category', cascade='all, delete-orphan')


class ForumThread(Base):
    __tablename__ = 'forum_threads'

    thread_id = Column(Integer, primary_key=True)
    category_id = Column(Integer, ForeignKey('forum_categories.category_id', ondelete='CASCADE'), nullable=False)
    author_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    title = Column(String(220), nullable=False)
    is_pinned = Column(Boolean, nullable=False, default=False)
    is_locked = Column(Boolean, nullable=False, default=False)
    view_count = Column(Integer, nullable=False, default=0)
    reply_count = Column(Integer, nullable=False, default=0)
    last_post_at = Column(DateTime, server_default=func.current_timestamp())
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    category = relationship('ForumCategory', back_populates='threads')
    posts = relationship('ForumPost', back_populates='thread', cascade='all, delete-orphan')


class ForumPost(Base):
    __tablename__ = 'forum_posts'

    post_id = Column(Integer, primary_key=True)
    thread_id = Column(Integer, ForeignKey('forum_threads.thread_id', ondelete='CASCADE'), nullable=False)
    author_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime)
    deleted_by = Column(Integer, ForeignKey('users.user_id'))
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(
        DateTime,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp()
    )

    thread = relationship('ForumThread', back_populates='posts')
