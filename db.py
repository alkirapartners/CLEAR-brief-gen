"""
Supabase persistence layer for brief history.

Every public function catches exceptions and returns a safe default
(empty list, None, or False) so the app never crashes on DB issues.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# How many recent rows the reuse lookup reads before picking the exact company.
CACHE_CANDIDATES = 5

# Module-level client cache
_client = None
_client_failed = False


def _secret(key: str) -> str:
    """Read configuration from the environment."""
    return os.environ.get(key, "")


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
    created_at: Optional[str] = None,
) -> Optional[dict]:
    """Insert a new brief. Returns the inserted record or None on failure.

    ``created_at`` is normally left to the column default. Pass it only when
    copying an existing brief (the repeat-company cache), so the copy keeps the
    ORIGINAL research timestamp. Without that, each cache hit would write a row
    dated today, the next lookup would match the copy, and both the 7-day
    window and the "reused research" date would drift indefinitely.
    """
    client = _get_client()
    if client is None:
        return None

    payload = {
        "email": _normalize_email(email),
        "company": company,
        "score": score,
        "brief_md": brief_md,
    }
    if created_at:
        payload["created_at"] = created_at

    try:
        result = (
            client.table("briefs")
            .insert(payload)
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


def get_brief(brief_id: str, email: str) -> Optional[dict]:
    """One brief by id, only if it belongs to this email. None otherwise."""
    client = _get_client()
    if client is None:
        return None

    try:
        result = (
            client.table("briefs")
            .select("id, email, company, score, brief_md, created_at")
            .eq("id", brief_id)
            .eq("email", _normalize_email(email))
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.error("Failed to fetch brief %s: %s", brief_id, exc)
        return None


def delete_brief(brief_id: str, email: str) -> bool:
    """Delete a brief by UUID if it belongs to this email.

    Returns True only when a row was removed, so a caller can tell "deleted"
    from "not yours or not there".
    """
    client = _get_client()
    if client is None:
        return False

    try:
        result = (
            client.table("briefs")
            .delete()
            .eq("id", brief_id)
            .eq("email", _normalize_email(email))
            .execute()
        )
        return bool(result.data)
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
        delete_brief(old_brief_id, email)
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
            .limit(CACHE_CANDIDATES)
            .execute()
        )
    except Exception as exc:
        logger.error("Failed company-cache lookup for %s: %s", company, exc)
        return None

    # PostgREST reads * as a wildcard in ilike, and the pattern cannot escape
    # it. Only a row for exactly this company may be reused: reuse copies the
    # brief into the caller's account.
    wanted = company.strip().casefold()
    for row in result.data or []:
        if (row.get("company") or "").strip().casefold() == wanted:
            return row
    return None
