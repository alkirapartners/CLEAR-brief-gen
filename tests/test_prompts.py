"""Tests for prompt construction and prompt-cache stability."""

from datetime import date

import prompts


def test_system_prefix_is_byte_stable_across_builds():
    """Any drift silently destroys the prompt cache and the cost savings."""
    assert prompts.build_system_prefix() == prompts.build_system_prefix()


def test_system_prefix_inlines_all_skill_files():
    prefix = prompts.build_system_prefix()
    assert "Alkira Fit Score" in prefix          # alkira-brief-template
    assert len(prefix) > 30_000                   # all skills present, not just one


def test_system_prefix_contains_no_volatile_content():
    """A date in the prefix invalidates the cache on every month boundary."""
    prefix = prompts.build_system_prefix()
    for year in ("2025", "2026", "2027"):
        assert year not in prefix


def test_system_prefix_states_the_output_contract():
    assert "# ALKIRA OPPORTUNITY BRIEF" in prompts.build_system_prefix()


def test_user_message_carries_company_payload_and_date():
    msg = prompts.build_user_message(
        "Acme Corp", "[1] Source\nURL: https://a.com", date(2026, 8, 31)
    )
    assert "Acme Corp" in msg
    assert "August 2026" in msg
    assert "https://a.com" in msg


def test_user_message_instructs_citation_by_number():
    msg = prompts.build_user_message("Acme", "[1] x", date(2026, 8, 31))
    assert "[1]" in msg
