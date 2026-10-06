"""Environment configuration for the Brief API."""

import logging
import os
from dataclasses import dataclass

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Paid generations per person per UTC day. A brief now costs about a dollar.
DEFAULT_DAILY_LIMIT = 10
# Written by the admin portal, shared between instances on EFS.
DEFAULT_ADMINS_FILE = "/var/www/briefgen/data/admins.json"
# In production data/ is a symlink to EFS, shared by both instances.
DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


@dataclass(frozen=True)
class Settings:
    anthropic_key: str
    tavily_key: str
    daily_limit: int
    admins_file: str
    usage_dir: str


def _daily_limit() -> int:
    """BRIEF_DAILY_LIMIT as a positive whole number, or the default.

    A typo in the environment must not stop the API from starting, so anything
    unusable is logged and ignored rather than raised.
    """
    raw = os.environ.get("BRIEF_DAILY_LIMIT", "").strip()
    if not raw:
        return DEFAULT_DAILY_LIMIT
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value < 1:
        logger.warning("BRIEF_DAILY_LIMIT=%r is not a positive whole number; using %d.", raw, DEFAULT_DAILY_LIMIT)
        return DEFAULT_DAILY_LIMIT
    return value


def load_settings() -> Settings:
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    return Settings(
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        tavily_key=os.environ.get("TAVILY_API_KEY", ""),
        daily_limit=_daily_limit(),
        admins_file=os.environ.get("BRIEF_ADMINS_FILE", DEFAULT_ADMINS_FILE),
        usage_dir=os.environ.get("BRIEF_DATA_DIR", DEFAULT_DATA_DIR),
    )
