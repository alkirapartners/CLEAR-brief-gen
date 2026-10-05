"""Tests for prefilling the company field from a ``?company=`` link.

Account Radar's "Generate brief" button links here with the company name in
the query string. The name must land in the search box without starting a
brief on its own: a brief costs money, so the partner still clicks Generate.
"""

from unittest.mock import patch

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


# ── UI wiring (headless Streamlit) ───────────────────────────────

GENERATE_BUTTON = "FormSubmitter:brief_form-Generate"


def _run_app(
    monkeypatch,
    query: dict[str, str],
    click_generate: bool = False,
    saved_briefs: list[dict] | None = None,
):
    """Run the real app headlessly with the given query string.

    Every outbound call is stubbed: no API calls, no database writes.
    ``saved_briefs`` stands in for the partner's stored brief history.
    """
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    monkeypatch.setenv("TAVILY_API_KEY", "dummy")

    generated: list[str] = []

    def fake_generate(
        api_key, tavily_key, company, status_callback,
        timeout_seconds=180, language="en",
    ):
        generated.append(company)
        return "# ALKIRA OPPORTUNITY BRIEF\n\n## " + company + "\n"

    at = AppTest.from_file("app.py", default_timeout=60)
    at.query_params["auth_email"] = "tester@example.com"
    for key, value in query.items():
        at.query_params[key] = value

    saved = {"id": "x", "created_at": "2026-08-31T12:00:00Z"}
    with patch("generate.generate_brief", fake_generate), patch(
        "db.save_brief", return_value=saved
    ), patch("db.find_recent_brief_by_company", return_value=None), patch(
        "db.get_user_briefs", return_value=saved_briefs or []
    ):
        at.run()
        if click_generate:
            # AppTest models segmented_control as a multi-select button group
            # and cannot serialise its scalar default, so set it explicitly.
            at.button_group[0].set_value(["en"])
            at.button(key=GENERATE_BUTTON).click().run()

    return at, generated


def test_company_link_prefills_the_search_box(monkeypatch):
    at, _ = _run_app(monkeypatch, {"company": "Sysco Corporation", "domain": "sysco.com"})

    assert not at.exception
    assert at.text_input[0].value == "Sysco Corporation"


def test_company_link_does_not_start_a_brief_by_itself(monkeypatch):
    at, generated = _run_app(monkeypatch, {"company": "Sysco Corporation"})

    assert not at.exception
    assert generated == []


def test_prefilled_company_is_what_generate_submits(monkeypatch):
    at, generated = _run_app(
        monkeypatch, {"company": "Sysco Corporation"}, click_generate=True
    )

    assert not at.exception
    assert generated == ["Sysco Corporation"]


def test_company_link_is_consumed_so_a_refresh_does_not_prefill_again(monkeypatch):
    at, _ = _run_app(monkeypatch, {"company": "Sysco Corporation", "domain": "sysco.com"})

    assert "company" not in at.query_params
    assert "domain" not in at.query_params


def test_search_box_starts_empty_without_a_company_link(monkeypatch):
    at, _ = _run_app(monkeypatch, {})

    assert not at.exception
    assert at.text_input[0].value == ""


def test_overlong_company_link_leaves_the_search_box_empty(monkeypatch):
    at, _ = _run_app(monkeypatch, {"company": "x" * (MAX_COMPANY_PREFILL_CHARS + 1)})

    assert not at.exception
    assert at.text_input[0].value == ""
    assert "company" not in at.query_params


# ── A linked name must not become markup later ───────────────────
#
# The search box is safe for any text, but a submitted name is stored and
# shown again on the dashboard. A link can now supply that name, so the
# dashboard card must treat it as text.

def test_dashboard_card_shows_a_stored_company_name_as_text_not_markup(monkeypatch):
    hostile = "<img src=//evil.example/p.gif>"
    stored = [{
        "id": "b1", "company": hostile, "score": 4,
        "brief_md": "# ALKIRA OPPORTUNITY BRIEF\n", "created_at": "2026-08-31T12:00:00Z",
    }]

    at, _ = _run_app(monkeypatch, {}, saved_briefs=stored)

    assert not at.exception
    card = next(m.value for m in at.markdown if 'class="dash-company"' in m.value)
    assert hostile not in card
    assert "&lt;img src=//evil.example/p.gif&gt;" in card
