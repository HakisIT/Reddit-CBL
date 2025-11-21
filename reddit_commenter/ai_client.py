"""AI client for generating Jade-styled comments."""
import random
from typing import Optional


# Template-based comment generation (stub for future AI integration)
_COMMENT_TEMPLATES = [
    "Love this. Stuff like this is why I keep my kit ready 😂",
    "This is exactly the kind of thing I needed to see today. Thanks for sharing!",
    "Solid post. Always appreciate seeing real-world examples like this.",
    "Can't wait to try this out myself. Great find!",
    "This is why I love this community. Practical and helpful.",
    "Bookmarking this for later. Really useful stuff here.",
    "Nice! This is the kind of content that keeps me coming back.",
    "Appreciate the share. Always learning something new here.",
]


async def generate_jade_comment(
    subreddit: str,
    title: str,
    url: str,
) -> str:
    """
    Generate a Jade-styled comment for a Reddit post.
    
    This is currently a stub implementation using templates.
    In the future, this will be replaced with actual AI backend calls.
    
    Args:
        subreddit: The subreddit name (e.g., "Bushcraft").
        title: The post title.
        url: The post URL.
        
    Returns:
        A comment string in Jade's style.
    """
    # For now, use a simple template-based approach
    base_comment = random.choice(_COMMENT_TEMPLATES)
    
    # Optionally add subreddit reference
    if random.random() < 0.3:  # 30% chance
        base_comment += f" (r/{subreddit})"
    
    return base_comment

