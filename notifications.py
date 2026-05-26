"""
Slack notification dispatch for brief generation events.

Reads SLACK_WEBHOOK_URL from env vars first, then st.secrets.
All public functions catch their own exceptions and return a safe
default so a notification failure never affects the calling code.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

import streamlit as st

logger = logging.getLogger(__name__)


def _slack_webhook_url() -> str:
    """Read SLACK_WEBHOOK_URL from env, then st.secrets. Returns '' if unset."""
    val = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not val:
        try:
            val = st.secrets.get("SLACK_WEBHOOK_URL", "")
        except FileNotFoundError:
            val = ""
    return val


def _post(url: str, payload: dict, timeout: float = 5.0) -> None:
    """POST a JSON payload. Raises on network error or non-2xx response."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.status >= 300:
            raise urllib.error.HTTPError(
                url, resp.status, f"Slack returned {resp.status}", resp.headers, None
            )


def _format_message(email: str, company: str, score: int) -> str:
    """Return the Slack-formatted notification text for a brief generation."""
    # Alkira Fit Score is a 1-5 scale (see README).
    if score >= 5:
        emoji = ":large_green_circle:"
    elif score >= 3:
        emoji = ":large_yellow_circle:"
    else:
        emoji = ":red_circle:"

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        f"{emoji} *New Alkira brief generated*\n"
        f"*Company:* {company}\n"
        f"*Score:* {score}\n"
        f"*By:* {email}\n"
        f"*At:* {now_utc}"
    )


def notify_brief_generated(email: str, company: str, score: int) -> bool:
    """
    Post a brief-generation notification to Slack.

    Returns True on a successful POST, False on any failure (missing
    webhook, network error, non-2xx response). Never raises.
    """
    url = _slack_webhook_url()
    if not url:
        logger.warning("SLACK_WEBHOOK_URL not configured. Skipping notification.")
        return False

    payload = {"text": _format_message(email, company, score)}

    try:
        _post(url, payload)
        return True
    except Exception as exc:
        logger.error(
            "Slack notification failed for %s / %s: %s", email, company, exc
        )
        return False
