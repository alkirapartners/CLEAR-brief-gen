"""Tests for prefilling the company field from a ``?company=`` link.

Account Radar's "Generate brief" button links here with the company name in
the query string. The name must land in the search box without starting a
brief on its own: a brief costs money, so the partner still clicks Generate.
"""

import pytest

from briefparse import MAX_COMPANY_PREFILL_CHARS, clean_company_prefill

# ── Sanitising the query value ───────────────────────────────────


def test_clean_company_prefill_trims_surrounding_whitespace():
    assert clean_company_prefill("  Sysco Corporation  ") == "Sysco Corporation"


def test_clean_company_prefill_flattens_newlines_and_tabs_to_single_spaces():
    assert clean_company_prefill("Koch\n\tIndustries") == "Koch Industries"


def test_clean_company_prefill_drops_control_characters():
    assert clean_company_prefill("Acme\x00\x1b Corp") == "Acme Corp"


@pytest.mark.parametrize("raw", [None, "", "   ", "\n\t"])
def test_clean_company_prefill_returns_empty_for_missing_or_blank(raw):
    assert clean_company_prefill(raw) == ""


def test_clean_company_prefill_accepts_a_name_at_the_length_limit():
    name = "x" * MAX_COMPANY_PREFILL_CHARS
    assert clean_company_prefill(name) == name


def test_clean_company_prefill_ignores_an_overlong_value():
    assert clean_company_prefill("x" * (MAX_COMPANY_PREFILL_CHARS + 1)) == ""
