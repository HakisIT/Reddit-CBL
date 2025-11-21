"""Database operations for the Reddit commenter."""
from typing import List

import asyncpg

from .config import DBConfig


async def create_pool(db_config: DBConfig) -> asyncpg.Pool:
    """
    Create an asyncpg connection pool.
    
    Args:
        db_config: Database configuration.
        
    Returns:
        asyncpg.Pool: Connection pool instance.
    """
    return await asyncpg.create_pool(
        host=db_config.host,
        port=db_config.port,
        database=db_config.name,
        user=db_config.user,
        password=db_config.password,
        min_size=1,
        max_size=5,
    )


async def fetch_next_posts_to_comment(
    pool: asyncpg.Pool,
    limit: int,
    post_max_age_hours: int,
) -> List[asyncpg.Record]:
    """
    Fetch posts that need to be commented on.
    
    Selects posts that:
    - Have commented = FALSE
    - Were created within the last post_max_age_hours
    - Ordered by seen_at DESC (most recently seen first)
    
    Args:
        pool: Database connection pool.
        limit: Maximum number of posts to fetch.
        post_max_age_hours: Maximum age of posts in hours.
        
    Returns:
        List of post records.
    """
    query = """
        SELECT 
            id,
            subreddit,
            post_id,
            post_url,
            title,
            score,
            created_at,
            seen_at,
            commented
        FROM reddit_posts
        WHERE 
            commented = FALSE
            AND created_at > NOW() - INTERVAL '1 hour' * $1
        ORDER BY seen_at DESC
        LIMIT $2;
    """


    
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, post_max_age_hours, limit)
        return list(rows)


async def mark_commented(pool: asyncpg.Pool, row_id: int) -> None:
    """
    Mark a post as successfully commented.
    """
    query = """
        UPDATE reddit_posts
        SET commented = TRUE
        WHERE id = $1;
    """
    
    async with pool.acquire() as conn:
        await conn.execute(query, row_id)


async def mark_failed(pool: asyncpg.Pool, row_id: int, error_message: str) -> None:
    """
    Mark a post as failed.
    
    Currently we don't store error details because the table
    has no 'last_error' column – we just ensure commented stays FALSE.
    """
    query = """
        UPDATE reddit_posts
        SET commented = FALSE
        WHERE id = $1;
    """
    async with pool.acquire() as conn:
        await conn.execute(query, row_id)
