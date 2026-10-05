"""Saving, reusing and refreshing work for both stored formats."""

import pytest

import research_loop
import stored_brief
from tests.api_fakes import AUTH, SAMPLE_BRIEF, FakeRepo, events, make_client
from tests.brief_fixtures import SAMPLE_JSON_BRIEF, stored

GEN = "/api/brief/briefs"
SPANISH_LEGACY = "# ALKIRA OPPORTUNITY BRIEF\n*[Agosto 2026]*\n\n## Cemex\n\n**Alkira Fit Score: 3 / 5**\n"


def _json_generator(text=SAMPLE_JSON_BRIEF):
    seen = []

    def generator(api_key, tavily_key, company, status_callback, language="en", **kwargs):
        seen.append((company, language))
        for phase in ("init", "research", "analyze", "compose", "done"):
            status_callback(phase)
        return text

    generator.seen = seen
    return generator


def _post(client, company="Northwind", language="en"):
    return client.post(GEN, json={"company": company, "language": language}, headers=AUTH)


# ── Reading either format ────────────────────────────────────────

def test_a_json_brief_gives_its_own_score_company_and_language():
    assert stored_brief.score_and_company(SAMPLE_JSON_BRIEF) == (5, "Northwind Energy")
    assert stored_brief.language_of(SAMPLE_JSON_BRIEF) == "en"
    assert stored_brief.language_of(stored(language="es")) == "es"


def test_a_legacy_brief_is_still_read_by_the_parsers():
    assert stored_brief.score_and_company(SAMPLE_BRIEF) == (4, "TestCo Holdings")
    assert stored_brief.language_of(SAMPLE_BRIEF) == "en"
    assert stored_brief.language_of(SPANISH_LEGACY) == "es"


def test_a_json_brief_is_stored_as_written_and_legacy_text_is_cleaned():
    assert stored_brief.normalise("\n " + SAMPLE_JSON_BRIEF + "\n") == SAMPLE_JSON_BRIEF
    assert stored_brief.normalise("Sure!\n\n" + SAMPLE_BRIEF) == SAMPLE_BRIEF


def test_a_spanish_month_inside_an_english_json_brief_does_not_make_it_spanish():
    fit = {"score": 4, "verdict": "The Agosto 2026 filing confirms it.", "lead": "Call the CIO."}
    assert stored_brief.language_of(stored(fit=fit)) == "en"


def test_a_damaged_document_reads_as_an_empty_legacy_brief():
    assert stored_brief.score_and_company('{"format": 2}') == (0, "")
    assert stored_brief.language_of(None) == "en"


# ── What may be handed to another person ─────────────────────────

def _stopped(stopped_by):
    return stored(research={"searches": 9, "pages": 4, "seconds": 240, "stopped_by": stopped_by})


@pytest.mark.parametrize("stopped_by", ["finished", "budget"])
def test_research_that_ran_its_course_is_reusable(stopped_by):
    assert stored_brief.is_reusable(_stopped(stopped_by))


@pytest.mark.parametrize(
    "stopped_by", ["deadline", "turn_cap", "truncated", "a-reason-added-later", ""],
    ids=["deadline", "turn_cap", "truncated", "unknown", "blank"],
)
def test_research_that_stopped_early_is_not_reusable(stopped_by):
    assert not stored_brief.is_reusable(_stopped(stopped_by))


@pytest.mark.parametrize(
    "text", [SAMPLE_BRIEF, SPANISH_LEGACY, '{"format": 2}', "", None],
    ids=["legacy", "spanish-legacy", "damaged", "empty", "missing"],
)
def test_a_legacy_or_damaged_brief_is_never_reusable(text):
    assert not stored_brief.is_reusable(text)


def test_the_reusable_reasons_are_the_ones_the_research_loop_uses():
    assert stored_brief.COMPLETE_RESEARCH == {research_loop.FINISHED, research_loop.BUDGET_SPENT}
    assert not stored_brief.COMPLETE_RESEARCH & set(research_loop.EARLY_STOPS)


# ── Through the API ──────────────────────────────────────────────

def test_a_generated_json_brief_is_saved_with_its_score_and_resolved_name():
    repo = FakeRepo()
    got = events(_post(make_client(repo, generator=_json_generator())))
    assert got[-1]["type"] == "done"
    (row,) = repo.rows
    assert row["brief_md"] == SAMPLE_JSON_BRIEF
    assert row["score"] == 5
    assert row["company"] == "Northwind Energy"  # the resolved name, not the typed one


def test_a_json_brief_with_no_company_name_is_saved_under_the_typed_name():
    company = {"name": " ", "legal_name": "", "ticker": "", "website": "", "identity_note": ""}
    repo = FakeRepo()
    events(_post(make_client(repo, generator=_json_generator(stored(company=company))), company="Typed Co"))
    assert repo.rows[0]["company"] == "Typed Co"


def test_recent_json_research_is_reused_without_calling_the_generator():
    repo = FakeRepo()
    repo.seed("someone@else.com", company="Northwind Energy", brief_md=SAMPLE_JSON_BRIEF, score=5)
    generator = _json_generator()
    got = events(_post(make_client(repo, generator=generator), company="northwind energy"))
    assert generator.seen == []
    assert got[-1]["reusedFrom"] is not None
    mine = repo.get_user_briefs("partner@example.com")
    assert len(mine) == 1 and mine[0]["brief_md"] == SAMPLE_JSON_BRIEF and mine[0]["score"] == 5


def test_a_json_brief_in_the_other_language_is_not_reused():
    repo = FakeRepo()
    repo.seed("someone@else.com", company="Northwind Energy", brief_md=stored(language="es"), score=5)
    generator = _json_generator()
    got = events(_post(make_client(repo, generator=generator), company="Northwind Energy"))
    assert generator.seen == [("Northwind Energy", "en")]
    assert got[-1]["reusedFrom"] is None


def test_refreshing_a_spanish_json_brief_stays_spanish():
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Northwind Energy", brief_md=stored(language="es"), score=5)
    generator = _json_generator(stored(language="es"))
    client = make_client(repo, generator=generator)
    got = events(client.post(f"{GEN}/{row['id']}/refresh", json={}, headers=AUTH))
    assert got[-1]["type"] == "done"
    assert generator.seen == [("Northwind Energy", "es")]


@pytest.mark.parametrize(
    "weak", [SAMPLE_BRIEF, _stopped("deadline"), _stopped("turn_cap"), _stopped("truncated")],
    ids=["legacy", "deadline", "turn_cap", "truncated"],
)
def test_a_legacy_or_early_stopped_brief_is_researched_again_instead_of_shared(weak):
    repo = FakeRepo()
    repo.seed("someone@else.com", company="Northwind Energy", brief_md=weak)
    generator = _json_generator()
    got = events(_post(make_client(repo, generator=generator), company="Northwind Energy"))
    assert generator.seen == [("Northwind Energy", "en")]
    assert got[-1]["reusedFrom"] is None
