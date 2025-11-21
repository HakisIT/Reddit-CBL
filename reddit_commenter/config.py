"""Configuration management for the Reddit commenter."""
import os
import warnings
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of reddit_commenter/)
_project_root = Path(__file__).parent.parent
_env_path = _project_root / ".env"
load_dotenv(_env_path)


@dataclass
class DBConfig:
    """Database configuration."""
    host: str
    port: int
    name: str
    user: str
    password: str


@dataclass
class CommenterConfig:
    """Commenter behavior configuration."""
    max_comments_per_run: int
    min_delay_sec: int
    max_delay_sec: int
    post_max_age_hours: int


def get_db_config() -> DBConfig:
    """
    Load database configuration from environment variables.
    
    Returns:
        DBConfig: Database configuration object.
        
    Raises:
        RuntimeError: If required DB config variables are missing.
    """
    host = os.getenv("DB_HOST", "")
    port_str = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "")
    user = os.getenv("DB_USER", "")
    password = os.getenv("DB_PASSWORD", "")
    
    # Validate required fields
    missing = []
    if not host:
        missing.append("DB_HOST")
    if not name:
        missing.append("DB_NAME")
    if not user:
        missing.append("DB_USER")
    if not password:
        missing.append("DB_PASSWORD")
    
    if missing:
        raise RuntimeError(
            f"Missing required DB config environment variables: {', '.join(missing)}"
        )
    
    try:
        port = int(port_str)
    except ValueError:
        warnings.warn(f"Invalid DB_PORT value '{port_str}', using default 5432")
        port = 5432
    
    return DBConfig(
        host=host,
        port=port,
        name=name,
        user=user,
        password=password,
    )


def get_commenter_config() -> CommenterConfig:
    """
    Load commenter configuration from environment variables.
    
    Returns:
        CommenterConfig: Commenter configuration object with defaults for missing values.
    """
    max_comments = int(os.getenv("MAX_COMMENTS_PER_RUN", "10"))
    min_delay = int(os.getenv("MIN_DELAY_BETWEEN_COMMENTS_SEC", "180"))
    max_delay = int(os.getenv("MAX_DELAY_BETWEEN_COMMENTS_SEC", "420"))
    post_max_age = int(os.getenv("POST_MAX_AGE_HOURS", "24"))
    
    # Warn if using defaults
    if not os.getenv("MAX_COMMENTS_PER_RUN"):
        warnings.warn("MAX_COMMENTS_PER_RUN not set, using default: 10")
    if not os.getenv("MIN_DELAY_BETWEEN_COMMENTS_SEC"):
        warnings.warn("MIN_DELAY_BETWEEN_COMMENTS_SEC not set, using default: 180")
    if not os.getenv("MAX_DELAY_BETWEEN_COMMENTS_SEC"):
        warnings.warn("MAX_DELAY_BETWEEN_COMMENTS_SEC not set, using default: 420")
    if not os.getenv("POST_MAX_AGE_HOURS"):
        warnings.warn("POST_MAX_AGE_HOURS not set, using default: 24")
    
    return CommenterConfig(
        max_comments_per_run=max_comments,
        min_delay_sec=min_delay,
        max_delay_sec=max_delay,
        post_max_age_hours=post_max_age,
    )

