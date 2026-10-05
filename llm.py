"""How this app calls Claude: the model, the shared request settings, the cost.

Research and writing both go through here, so the model, the thinking mode,
the cache lifetime and the refusal fallback are set in one place.
"""

from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

MODEL = "claude-sonnet-5-5"
# No single request runs for minutes: research is many short turns and the
# writer streams. This bounds a stalled connection, not the length of a run.
REQUEST_TIMEOUT_SECONDS = 300
# Briefs arrive minutes apart, so the system prefix is cached for an hour.
CACHE_TTL = "1h"
# If the model declines a request, the API retries it on Anthropic's
# recommended substitute inside the same call. Set to False to turn it off.
USE_REFUSAL_FALLBACK = True
REFUSAL_FALLBACK_BETA = "server-side-fallback-2026-07-01"

TOKENS_PER_MILLION = 1_000_000
# US dollars per million tokens for Claude Sonnet 5.5.
PRICE_INPUT = 2.00
PRICE_OUTPUT = 10.00
PRICE_CACHE_WRITE_5M = 2.50
PRICE_CACHE_WRITE_1H = 4.00
PRICE_CACHE_READ = 0.20
# Tavily: pay-as-you-go price, an advanced search, an advanced page read.
TAVILY_PRICE_PER_CREDIT = 0.008
TAVILY_CREDITS_PER_SEARCH = 2.0
TAVILY_CREDITS_PER_PAGE = 0.4


@dataclass(frozen=True)
class Usage:
    """Tokens billed across one or more requests."""

    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_5m_tokens: int = 0
    cache_write_1h_tokens: int = 0


def make_client(api_key: str, timeout_seconds: float = REQUEST_TIMEOUT_SECONDS) -> Anthropic:
    return Anthropic(api_key=api_key, timeout=timeout_seconds)


def request_settings(system_text: str, max_tokens: int) -> dict[str, Any]:
    """Keyword arguments every request shares. The caller adds the rest.

    The system text is the cached prefix: it must be byte-identical between
    briefs, so nothing about one brief may ever be put in it.
    """
    settings: dict[str, Any] = {
        "model": MODEL,
        "max_tokens": max_tokens,
        "thinking": {"type": "adaptive"},
        "system": [{
            "type": "text",
            "text": system_text,
            "cache_control": {"type": "ephemeral", "ttl": CACHE_TTL},
        }],
    }
    if USE_REFUSAL_FALLBACK:
        settings.update(betas=[REFUSAL_FALLBACK_BETA], fallbacks="default")
    return settings


def refusal(message: Any) -> str | None:
    """Why the model declined, or None when it did not."""
    if getattr(message, "stop_reason", None) != "refusal":
        return None
    details = getattr(message, "stop_details", None)
    return str(getattr(details, "category", None) or "unspecified")


def _count(raw: Any, name: str) -> int:
    return int(getattr(raw, name, 0) or 0)


def add_usage(total: Usage, raw: Any) -> Usage:
    """``total`` plus one response's ``usage`` object."""
    written = _count(raw, "cache_creation_input_tokens")
    breakdown = getattr(raw, "cache_creation", None)
    five_minute = _count(breakdown, "ephemeral_5m_input_tokens")
    one_hour = _count(breakdown, "ephemeral_1h_input_tokens")
    if five_minute + one_hour == 0:
        one_hour = written  # no breakdown given: count it at the dearer rate
    return Usage(
        requests=total.requests + 1,
        input_tokens=total.input_tokens + _count(raw, "input_tokens"),
        output_tokens=total.output_tokens + _count(raw, "output_tokens"),
        cache_read_tokens=total.cache_read_tokens + _count(raw, "cache_read_input_tokens"),
        cache_write_5m_tokens=total.cache_write_5m_tokens + five_minute,
        cache_write_1h_tokens=total.cache_write_1h_tokens + one_hour,
    )


def combine(first: Usage, second: Usage) -> Usage:
    return Usage(
        requests=first.requests + second.requests,
        input_tokens=first.input_tokens + second.input_tokens,
        output_tokens=first.output_tokens + second.output_tokens,
        cache_read_tokens=first.cache_read_tokens + second.cache_read_tokens,
        cache_write_5m_tokens=first.cache_write_5m_tokens + second.cache_write_5m_tokens,
        cache_write_1h_tokens=first.cache_write_1h_tokens + second.cache_write_1h_tokens,
    )


def token_cost(usage: Usage) -> float:
    """Estimated US dollars for the tokens in ``usage``."""
    dollars = (
        usage.input_tokens * PRICE_INPUT
        + usage.output_tokens * PRICE_OUTPUT
        + usage.cache_read_tokens * PRICE_CACHE_READ
        + usage.cache_write_5m_tokens * PRICE_CACHE_WRITE_5M
        + usage.cache_write_1h_tokens * PRICE_CACHE_WRITE_1H
    )
    return dollars / TOKENS_PER_MILLION


def web_cost(searches: int, pages_opened: int) -> float:
    """Estimated US dollars for the Tavily calls of one brief."""
    credits = searches * TAVILY_CREDITS_PER_SEARCH + pages_opened * TAVILY_CREDITS_PER_PAGE
    return credits * TAVILY_PRICE_PER_CREDIT
