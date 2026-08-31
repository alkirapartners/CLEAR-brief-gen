"""Tests for the single-call generation contract. No live API calls."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import generate

BRIEF = "# ALKIRA OPPORTUNITY BRIEF\n## Acme\n"


def _message(text, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=200,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=None,
        ),
    )


def _run(message):
    """Drive generate_brief with a stubbed Anthropic client and research layer."""
    client = MagicMock()
    stream = MagicMock()
    stream.__enter__.return_value.get_final_message.return_value = message
    client.messages.stream.return_value = stream

    with patch("generate.Anthropic", return_value=client), patch(
        "generate.research.research",
        return_value=SimpleNamespace(sources=[], payload="[1] src"),
    ):
        brief = generate.generate_brief(
            "fake-anthropic", "fake-tavily", "Acme", lambda phase: None
        )
    return brief, client


def test_returns_brief_when_output_follows_the_contract():
    brief, _ = _run(_message(BRIEF))
    assert brief == BRIEF


def test_leading_whitespace_before_the_marker_is_tolerated():
    brief, _ = _run(_message("\n\n" + BRIEF))
    assert brief.strip().startswith(generate.BRIEF_MARKER)


def test_raises_when_output_does_not_start_with_the_contract_marker():
    """Narration or a refusal parses to score 0 and renders as a broken brief."""
    narrated = "Sure! Here is the brief you asked for:\n\n" + BRIEF
    with pytest.raises(RuntimeError) as exc:
        _run(_message(narrated))
    assert "contract" in str(exc.value)
    assert "Sure!" in str(exc.value)  # the actual prefix, for diagnosis
    assert "end_turn" in str(exc.value)  # the stop_reason


def test_raises_on_truncated_output():
    with pytest.raises(RuntimeError, match="truncated"):
        _run(_message(BRIEF, stop_reason="max_tokens"))


def test_raises_on_empty_output():
    with pytest.raises(RuntimeError, match="empty output"):
        _run(_message("   "))


def test_research_error_propagates_uncaught():
    """An uncited brief must never be produced; ResearchError must reach the caller."""
    with patch("generate.Anthropic", return_value=MagicMock()), patch(
        "generate.research.research",
        side_effect=generate.research.ResearchError("no results"),
    ):
        with pytest.raises(generate.research.ResearchError):
            generate.generate_brief(
                "fake-anthropic", "fake-tavily", "Acme", lambda phase: None
            )


def test_system_block_requests_a_one_hour_cache_ttl():
    """The default 5-minute TTL would make caching a net cost increase here."""
    _, client = _run(_message(BRIEF))
    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["system"][0]["cache_control"] == {
        "type": "ephemeral",
        "ttl": "1h",
    }


def test_generation_params_are_unchanged():
    _, client = _run(_message(BRIEF))
    kwargs = client.messages.stream.call_args.kwargs
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["max_tokens"] == 16000
    assert kwargs["thinking"] == {"type": "adaptive"}
    assert kwargs["output_config"] == {"effort": "medium"}
    assert "budget_tokens" not in kwargs
    # No assistant prefill: exactly one user turn.
    assert [m["role"] for m in kwargs["messages"]] == ["user"]


def test_cache_metrics_log_as_zero_not_none(caplog):
    """cache_read is the metric used to confirm prompt caching in production."""
    with caplog.at_level("INFO", logger="generate"):
        _run(_message(BRIEF))
    assert "cache_read=0 cache_write=0" in caplog.text
