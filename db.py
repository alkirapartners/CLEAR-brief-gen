"""
Supabase persistence layer for brief history.

Every public function catches exceptions and returns a safe default
(empty list, None, or False) so the app never crashes on DB issues.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)

# Module-level client cache
_client = None
_client_failed = False


def _secret(key: str) -> str:
    """Read from env vars first, then st.secrets."""
    val = os.environ.get(key, "")
    if not val:
        try:
            val = st.secrets.get(key, "")
        except FileNotFoundError:
            pass
    return val


def _get_client():
    """Return a cached Supabase client, or None if unavailable."""
    global _client, _client_failed

    if _client is not None:
        return _client
    if _client_failed:
        return None

    url = _secret("SUPABASE_URL")
    key = _secret("SUPABASE_KEY")

    if not url or not key:
        logger.warning("SUPABASE_URL or SUPABASE_KEY not configured. Running without persistence.")
        _client_failed = True
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except Exception as exc:
        logger.error("Failed to create Supabase client: %s", exc)
        _client_failed = True
        return None


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _escape_like(value: str) -> str:
    """Escape LIKE/ILIKE metacharacters so user input can't act as a wildcard.

    Backslash must be escaped first so it doesn't double-escape the
    characters escaped after it.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_user_briefs(email: str) -> list[dict]:
    """Fetch all briefs for the given email, newest first."""
    client = _get_client()
    if client is None:
        return []

    try:
        result = (
            client.table("briefs")
            .select("id, email, company, score, brief_md, created_at")
            .eq("email", _normalize_email(email))
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("Failed to fetch briefs for %s: %s", email, exc)
        return []


def save_brief(
    email: str,
    company: str,
    score: int,
    brief_md: str,
) -> Optional[dict]:
    """Insert a new brief. Returns the inserted record or None on failure."""
    client = _get_client()
    if client is None:
        return None

    try:
        result = (
            client.table("briefs")
            .insert({
                "email": _normalize_email(email),
                "company": company,
                "score": score,
                "brief_md": brief_md,
            })
            .execute()
        )
        rows = result.data or []
        saved = rows[0] if rows else None
    except Exception as exc:
        logger.error("Failed to save brief for %s / %s: %s", email, company, exc)
        return None

    if saved is not None:
        try:
            import notifications
            notifications.notify_brief_generated(email, company, score)
        except Exception as exc:
            logger.error(
                "Notification dispatch failed for %s / %s: %s", email, company, exc
            )

    return saved


def delete_brief(brief_id: str) -> bool:
    """Delete a brief by UUID. Returns True on success."""
    client = _get_client()
    if client is None:
        return False

    try:
        client.table("briefs").delete().eq("id", brief_id).execute()
        return True
    except Exception as exc:
        logger.error("Failed to delete brief %s: %s", brief_id, exc)
        return False


def replace_brief(
    old_brief_id: str,
    email: str,
    company: str,
    score: int,
    brief_md: str,
) -> Optional[dict]:
    """Delete old brief and save a new one. Returns the new record or None."""
    if old_brief_id:
        delete_brief(old_brief_id)
    return save_brief(email, company, score, brief_md)


def is_available() -> bool:
    """Check if the database is configured and reachable."""
    return _get_client() is not None


def find_recent_brief_by_company(
    company: str,
    max_age_days: int = 7,
) -> Optional[dict]:
    """Most recent brief for this company across all users, or None.

    Unlike get_user_briefs this deliberately ignores email: if any partner
    briefed the company this week, reuse that research.
    """
    client = _get_client()
    if client is None:
        return None

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=max_age_days)
    ).isoformat()

    try:
        result = (
            client.table("briefs")
            .select("id, email, company, score, brief_md, created_at")
            .ilike("company", _escape_like(company.strip()))
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.error("Failed company-cache lookup for %s: %s", company, exc)
        return None
