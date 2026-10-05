"""Who is calling, according to the header nginx sets."""

import json

from fastapi import Header, HTTPException

_ALKIRA_DOMAINS = ("alkira.net", "alkira.com")


async def require_email(x_auth_email: str | None = Header(default=None)) -> str:
    """Trust the X-Auth-Email header set by nginx.

    The API binds to 127.0.0.1 only. nginx replaces any client-supplied
    X-Auth-Email with the auth service's answer, so receiving the header
    here is proof of a valid session.
    """
    email = (x_auth_email or "").strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=401, detail="Not signed in")
    return email


def _aliases(email: str) -> set[str]:
    """alkira.net and alkira.com name the same person, as in the auth service."""
    local, _, domain = email.partition("@")
    if domain in _ALKIRA_DOMAINS:
        return {f"{local}@{d}" for d in _ALKIRA_DOMAINS}
    return {email}


def is_admin(email: str, admins_file: str) -> bool:
    try:
        with open(admins_file, encoding="utf-8") as handle:
            admins = json.load(handle)
    except (OSError, ValueError):
        return False
    if not isinstance(admins, list):
        return False
    known: set[str] = set()
    for entry in admins:
        if isinstance(entry, str):
            known |= _aliases(entry.strip().lower())
    return email.strip().lower() in known
