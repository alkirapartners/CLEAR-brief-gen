"""Tests for prompt construction and prompt-cache stability."""

import hashlib
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import prompts

REPO_ROOT = Path(__file__).resolve().parent.parent

# One distinctive marker per file in prompts.SKILL_FILES, hand-picked by reading
# each file and confirming (via grep) it appears nowhere else under skills/.
_SKILL_FILE_MARKERS: dict[str, str] = {
    "alkira-brief-template/SKILL.md": "THE BRIEF MUST FIT ON TWO PRINTED PAGES.",
    "alkira-customer/SKILL.md": "Channel Account Manager Edition",
    "alkira-customer/references/case-studies.md": (
        "Nemertes Research Case Studies by Industry"
    ),
    "alkira-customer/references/objection-handling.md": (
        "We're happy with what we have"
    ),
    "alkira-customer/references/pricing.md": "20Large (20L)",
    "stop-slop/SKILL.md": "Eliminate predictable AI writing patterns from prose.",
    "stop-slop/references/phrases.md": "Throat-Clearing Openers",
    "stop-slop/references/structures.md": "Binary Contrasts",
}


def test_system_prefix_is_byte_stable_within_process():
    """cache_clear forces a fresh build; construction must still be deterministic.

    This catches construction-order nondeterminism (e.g. a switch from the
    hardcoded SKILL_FILES tuple to os.listdir()/glob(), which returns files in
    arbitrary filesystem order) that a plain double-call can't catch, since
    @lru_cache would just return the same cached object both times.
    """
    first = prompts.build_system_prefix()
    prompts.build_system_prefix.cache_clear()
    second = prompts.build_system_prefix()
    assert first == second


def test_system_prefix_is_byte_stable_across_processes():
    """Build the prefix in a fresh subprocess and compare its hash to ours.

    PYTHONHASHSEED-based ordering (e.g. iterating a set or dict keyed by
    strings) is stable within a single process but can vary between processes,
    so a same-process check alone would miss it. A crashing subprocess must
    fail this test loudly rather than silently comparing empty strings.
    """
    script = (
        "import hashlib, prompts; "
        "print(hashlib.sha256("
        "prompts.build_system_prefix().encode('utf-8')"
        ").hexdigest())"
    )
    clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONHASHSEED"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=clean_env,
    )
    assert result.returncode == 0, (
        f"subprocess crashed (exit {result.returncode}): {result.stderr}"
    )
    subprocess_digest = result.stdout.strip()
    in_process_digest = hashlib.sha256(
        prompts.build_system_prefix().encode("utf-8")
    ).hexdigest()
    assert subprocess_digest == in_process_digest


def test_system_prefix_inlines_all_skill_files():
    """Every file in SKILL_FILES must leave a distinctive trace in the prefix.

    A length-only check would still pass if a whole file (e.g. pricing.md)
    were silently dropped from SKILL_FILES, since the remaining seven files
    already clear 30,000 characters on their own.
    """
    assert set(_SKILL_FILE_MARKERS) == set(prompts.SKILL_FILES)
    prefix = prompts.build_system_prefix()
    for relative_path, marker in _SKILL_FILE_MARKERS.items():
        assert marker in prefix, f"missing marker for {relative_path}"
    assert len(prefix) > 30_000                   # all skills present, not just one


def test_system_prefix_contains_no_volatile_content():
    """A date in the prefix invalidates the cache on every month boundary."""
    prefix = prompts.build_system_prefix()
    for year in ("2025", "2026", "2027"):
        assert year not in prefix


def test_system_prefix_states_the_output_contract():
    assert "# ALKIRA OPPORTUNITY BRIEF" in prompts.build_system_prefix()


def test_system_prefix_mandates_heading_format_the_parsers_require():
    """app.py:extract_section matches ONLY '##'/'###' headings by exact text.

    Live generation (Mary Kay, Chevron) emitted these as **bold** instead,
    which app.py's regex-based extractors silently treat as a missing
    section — Infrastructure Snapshot, Signals & Timing, Three Alkira Entry
    Points, and Conversation Starters all rendered as 0 characters. The
    parsers and their fixtures are a frozen regression gate (test_parsers.py)
    and skills/ must never be edited, so the fix has to make _INSTRUCTIONS
    state the required literal heading text unambiguously. This test pins
    that down so a future edit to _INSTRUCTIONS can't silently drop the
    format rules and reintroduce empty sections.
    """
    prefix = prompts.build_system_prefix()
    required_headings = (
        "## Infrastructure Snapshot",
        "## Signals & Timing",
        "## Three Alkira Entry Points",
        "## Conversation Starters",
        "## References",
    )
    for heading in required_headings:
        assert heading in prefix, f"missing required heading directive: {heading}"

    # The ampersand form is mandated explicitly, not just used in the heading
    # list above — "and" must never be presented as an acceptable substitute.
    assert 'Do not write "and"' in prefix

    # Entry-point subheadings must be required to carry a leading number.
    assert "**1. Title**" in prefix
    assert "**2. Title**" in prefix
    assert "**3. Title**" in prefix


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
