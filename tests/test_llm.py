"""Shared Claude request settings and the cost estimate."""

from types import SimpleNamespace

import pytest

import llm
from llm import Usage


def test_every_request_uses_sonnet_5_5_with_adaptive_thinking():
    settings = llm.request_settings("PREFIX", 16000)
    assert settings["model"] == "claude-sonnet-5-5"
    assert settings["max_tokens"] == 16000
    assert settings["thinking"] == {"type": "adaptive"}
    assert "budget_tokens" not in str(settings) and "temperature" not in settings


def test_the_system_prefix_is_cached_for_an_hour():
    (block,) = llm.request_settings("PREFIX", 100)["system"]
    assert block == {"type": "text", "text": "PREFIX", "cache_control": {"type": "ephemeral", "ttl": "1h"}}


def test_a_declined_request_is_retried_by_the_api_on_its_default_substitute():
    settings = llm.request_settings("PREFIX", 100)
    assert settings["fallbacks"] == "default"
    assert settings["betas"] == ["server-side-fallback-2026-07-01"]


def test_the_fallback_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(llm, "USE_REFUSAL_FALLBACK", False)
    settings = llm.request_settings("PREFIX", 100)
    assert "fallbacks" not in settings and "betas" not in settings


def test_the_client_timeout_covers_a_long_run():
    assert llm.REQUEST_TIMEOUT_SECONDS >= 240


def test_a_refusal_is_reported_with_its_category():
    declined = SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"))
    assert llm.refusal(declined) == "cyber"
    assert llm.refusal(SimpleNamespace(stop_reason="refusal", stop_details=None)) == "unspecified"
    assert llm.refusal(SimpleNamespace(stop_reason="end_turn", stop_details=None)) is None


def test_usage_adds_up_and_treats_missing_fields_as_zero():
    first = SimpleNamespace(
        input_tokens=100, output_tokens=50, cache_read_input_tokens=None,
        cache_creation_input_tokens=None, cache_creation=None,
    )
    second = SimpleNamespace(
        input_tokens=10, output_tokens=5, cache_read_input_tokens=4000,
        cache_creation_input_tokens=900,
        cache_creation=SimpleNamespace(ephemeral_5m_input_tokens=600, ephemeral_1h_input_tokens=300),
    )
    total = llm.add_usage(llm.add_usage(Usage(), first), second)
    assert total == Usage(
        requests=2, input_tokens=110, output_tokens=55, cache_read_tokens=4000,
        cache_write_5m_tokens=600, cache_write_1h_tokens=300,
    )


def test_cache_writes_without_a_breakdown_are_counted_at_the_dearer_rate():
    raw = SimpleNamespace(input_tokens=0, output_tokens=0, cache_creation_input_tokens=1000)
    assert llm.add_usage(Usage(), raw).cache_write_1h_tokens == 1000


def test_two_usages_combine():
    total = llm.combine(Usage(requests=3, input_tokens=5), Usage(requests=1, output_tokens=7))
    assert total == Usage(requests=4, input_tokens=5, output_tokens=7)


def test_token_cost_uses_the_published_prices():
    usage = Usage(
        input_tokens=1_000_000, output_tokens=1_000_000, cache_read_tokens=1_000_000,
        cache_write_5m_tokens=1_000_000, cache_write_1h_tokens=1_000_000,
    )
    assert llm.token_cost(usage) == pytest.approx(2.00 + 10.00 + 0.20 + 2.50 + 4.00)
    assert llm.token_cost(Usage()) == 0


def test_web_cost_counts_searches_and_opened_pages():
    assert llm.web_credits(25, 20) == pytest.approx(25 * 2 + 20 * 0.4)
    assert llm.web_cost(25, 20) == pytest.approx((25 * 2 + 20 * 0.4) * 0.008)
