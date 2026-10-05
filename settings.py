"""Environment configuration for the Brief API."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_DAILY_LIMIT = 50
# Written by the admin portal, shared between instances on EFS.
DEFAULT_ADMINS_FILE = "/var/www/briefgen/data/admins.json"


@dataclass(frozen=True)
class Settings:
    anthropic_key: str
    tavily_key: str
    daily_limit: int
    admins_file: str


def load_settings() -> Settings:
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    return Settings(
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        tavily_key=os.environ.get("TAVILY_API_KEY", ""),
        daily_limit=int(os.environ.get("BRIEF_DAILY_LIMIT", DEFAULT_DAILY_LIMIT)),
        admins_file=os.environ.get("BRIEF_ADMINS_FILE", DEFAULT_ADMINS_FILE),
    )
