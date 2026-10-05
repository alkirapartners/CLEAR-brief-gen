import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from brief_service import BriefService
from usage_ledger import UsageLedger
from errors import GenerationInFlight
from tests.api_fakes import (
    AUTH, OTHER, SAMPLE_BRIEF, TEST_SETTINGS, FakeRepo, events, fake_generator, make_client,
)
from tests.brief_fixtures import stored

GEN = "/api/brief/briefs"


def _named(name):
    return {"name": name, "legal_name": "", "ticker": "", "website": "", "identity_note": ""}


# Research another person finished, in the format that may be shared.
SHARED = stored(company=_named("TestCo Holdings"))


def _post(client, company="TestCo", language="en", headers=AUTH):
    return client.post(GEN, json={"company": company, "language": language}, headers=headers)


def test_generate_streams_phases_then_done_and_saves_once():
    repo = FakeRepo()
    resp = _post(make_client(repo))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert resp.headers["x-accel-buffering"] == "no"
    # no-transform stops any proxy in between from compressing, and so buffering, the stream.
    assert "no-transform" in resp.headers["cache-control"]
    got = events(resp)
    assert [e.get("phase") for e in got[:-1]] == ["init", "research", "analyze", "compose"]
    assert got[-1]["type"] == "done" and got[-1]["reusedFrom"] is None
    assert len(repo.rows) == 1
    saved = repo.rows[0]
    assert saved["id"] == got[-1]["briefId"]
    assert saved["email"] == "partner@example.com"
    assert saved["company"] == "TestCo Holdings"  # from the brief header, not the typed name
    assert saved["score"] == 4


def test_generate_requires_auth():
    assert make_client().post(GEN, json={"company": "TestCo"}).status_code == 401


@pytest.mark.parametrize("body", [
    {"company": "   "},
    {"company": "x" * 101},
    {"company": "TestCo", "language": "fr"},
    {"language": "en"},
])
def test_generate_rejects_bad_input(body):
    calls = []
    def generator(*args, **kwargs):
        calls.append(args)
        return SAMPLE_BRIEF
    resp = make_client(generator=generator).post(GEN, json=body, headers=AUTH)
    assert resp.status_code == 422
    assert resp.json()["success"] is False
    assert calls == []


def test_generate_rejects_a_non_json_body():
    resp = make_client().post(
        GEN, content='{"company": "TestCo"}', headers={**AUTH, "Content-Type": "text/plain"},
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("typed", [
    "https://evil.example/facts", "Acme, see evil.example/page", "www.acme.com", "Acme <b>x</b>",
], ids=["url", "path", "www", "markup"])
def test_a_web_address_typed_as_the_company_is_refused_before_anything_is_spent(typed):
    calls = []
    def generator(*args, **kwargs):
        calls.append(args)
        return SAMPLE_BRIEF
    client = _limited(FakeRepo(), 1, generator=generator)

    refused = _post(client, company=typed)

    assert refused.status_code == 400
    assert refused.json()["error"] == "Enter a company name, not a web address."
    assert calls == []
    assert events(_post(client, company="Acme"))[-1]["type"] == "done"  # the day's one slot was not spent


def test_a_company_named_like_a_website_is_still_researched():
    seen = []
    def generator(api_key, tavily_key, company, status_callback, **kwargs):
        seen.append(company)
        return SAMPLE_BRIEF
    _post(make_client(generator=generator), company="Booking.com")
    assert seen == ["Booking.com"]


def test_generate_flattens_control_characters():
    seen = []
    def generator(api_key, tavily_key, company, status_callback, **kwargs):
        seen.append(company)
        return SAMPLE_BRIEF
    _post(make_client(generator=generator), company="  Test\nCo\t Holdings\x00 ")
    assert seen == ["Test Co Holdings"]


def test_recent_research_is_reused_without_calling_the_model():
    original = "2026-10-01T09:00:00+00:00"
    repo = FakeRepo()
    repo.seed("someone@else.com", company="TestCo Holdings", brief_md=SHARED, created_at=original)
    calls = []
    def generator(*args, **kwargs):
        calls.append(args)
        return SAMPLE_BRIEF
    got = events(_post(make_client(repo, generator=generator), company="testco holdings"))
    assert calls == []
    assert got == [{"type": "done", "briefId": got[0]["briefId"], "reusedFrom": original}]
    mine = repo.get_user_briefs("partner@example.com")
    assert len(mine) == 1 and mine[0]["created_at"] == original  # copy keeps the research date


def test_a_brief_in_the_other_language_is_not_reused():
    repo = FakeRepo()
    repo.seed("someone@else.com", company="TestCo Holdings", brief_md=SHARED)  # English
    seen = []
    def generator(api_key, tavily_key, company, status_callback, language="en", **kwargs):
        seen.append(language)
        return SAMPLE_BRIEF
    got = events(_post(make_client(repo, generator=generator), company="TestCo Holdings", language="es"))
    assert seen == ["es"]
    assert got[-1]["reusedFrom"] is None


def test_guard_is_released_after_failure():
    attempts = []
    def generator(api_key, tavily_key, company, status_callback, **kwargs):
        attempts.append(company)
        if len(attempts) == 1:
            raise RuntimeError("tavily exploded at /var/www/briefgen")
        return SAMPLE_BRIEF
    repo = FakeRepo()
    client = make_client(repo, generator=generator)
    first = events(_post(client))
    assert first[-1]["type"] == "error"
    assert "tavily" not in first[-1]["message"] and "/var/www" not in first[-1]["message"]
    assert repo.rows == []
    assert events(_post(client))[-1]["type"] == "done"


def test_second_generation_while_in_flight_is_rejected(tmp_path):
    service = BriefService(FakeRepo(), fake_generator, TEST_SETTINGS, UsageLedger(str(tmp_path)))
    work = service.start_generate("partner@example.com", "TestCo", "en")
    with pytest.raises(GenerationInFlight):
        service.start_generate("partner@example.com", "Other Co", "en")
    service.start_generate("someone@else.com", "Other Co", "en")  # other users are unaffected
    work(lambda phase: None)
    service.start_generate("partner@example.com", "Other Co", "en")  # released after it ran


def test_in_flight_maps_to_409():
    client = make_client()
    client.app.state.service._guard.acquire("partner@example.com")
    resp = _post(client)
    assert resp.status_code == 409
    assert resp.json()["success"] is False


def _limited(repo, limit, **kwargs):
    return make_client(repo, settings=replace(TEST_SETTINGS, daily_limit=limit), **kwargs)


def _delete(client, brief_id):
    return client.delete(f"{GEN}/{brief_id}", headers=AUTH)


def test_the_daily_limit_blocks_once_reached():
    client = _limited(FakeRepo(), 2)
    assert events(_post(client, company="One Co"))[-1]["type"] == "done"
    assert events(_post(client, company="Two Co"))[-1]["type"] == "done"

    blocked = _post(client, company="Three Co")

    assert blocked.status_code == 429
    assert "2" in blocked.json()["error"]


def test_deleting_a_brief_does_not_give_the_generation_back():
    repo = FakeRepo()
    client = _limited(repo, 2)
    for company in ("One Co", "Two Co"):
        done = events(_post(client, company=company))[-1]
        assert _delete(client, done["briefId"]).status_code == 200
    assert repo.rows == []

    assert _post(client, company="Three Co").status_code == 429


def test_updating_a_brief_counts_as_a_generation():
    repo = FakeRepo()
    client = _limited(repo, 2)
    first = events(_post(client, company="One Co"))[-1]
    second = events(_refresh(client, first["briefId"]))[-1]
    assert second["type"] == "done"

    blocked = _refresh(client, second["briefId"])

    assert blocked.status_code == 429
    assert [row["id"] for row in repo.rows] == [second["briefId"]]  # the brief is untouched


def test_a_generation_that_fails_after_starting_still_counts():
    def broken(*args, **kwargs):
        raise RuntimeError("the model call was paid for, then failed")
    client = _limited(FakeRepo(), 1, generator=broken)
    assert events(_post(client))[-1]["type"] == "error"

    assert _post(client).status_code == 429


def test_reused_research_is_free_and_never_blocked():
    repo = FakeRepo()
    repo.seed("someone@else.com", company="Shared Co", brief_md=stored(company=_named("Shared Co")))
    client = _limited(repo, 1)
    assert events(_post(client, company="Shared Co"))[-1]["type"] == "done"  # free
    assert events(_post(client, company="Fresh Co"))[-1]["type"] == "done"   # the one paid generation

    assert _post(client, company="Another Fresh Co").status_code == 429
    assert events(_post(client, company="Shared Co"))[-1]["type"] == "done"  # still free


def test_each_person_has_their_own_limit():
    client = _limited(FakeRepo(), 1)
    assert events(_post(client, company="One Co"))[-1]["type"] == "done"

    assert events(_post(client, company="Two Co", headers=OTHER))[-1]["type"] == "done"


def test_the_limit_resets_at_midnight_utc():
    now = {"value": datetime(2026, 10, 5, 23, 59, tzinfo=timezone.utc)}
    client = _limited(FakeRepo(), 1, clock=lambda: now["value"])
    assert events(_post(client, company="One Co"))[-1]["type"] == "done"
    assert _post(client, company="Two Co").status_code == 429

    now["value"] = datetime(2026, 10, 6, 0, 1, tzinfo=timezone.utc)

    assert events(_post(client, company="Two Co"))[-1]["type"] == "done"


def test_generation_is_refused_when_usage_cannot_be_read(tmp_path):
    """If the cap cannot be checked it must not be skipped."""
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory")
    calls = []
    def generator(*args, **kwargs):
        calls.append(args)
        return SAMPLE_BRIEF
    client = make_client(generator=generator, ledger=UsageLedger(str(blocker)))

    resp = _post(client)

    assert resp.status_code == 503
    assert calls == []
    assert events(_post(make_client()))[-1]["type"] == "done"  # and the guard was released


def test_missing_keys_disable_generation_with_503():
    client = make_client(settings=replace(TEST_SETTINGS, anthropic_key=""))
    assert _post(client).status_code == 503


def test_save_is_retried_once():
    repo = FakeRepo()
    repo.save_failures = 1
    assert events(_post(make_client(repo)))[-1]["type"] == "done"
    assert len(repo.rows) == 1


def test_save_failure_reports_error_event():
    repo = FakeRepo()
    repo.save_failures = 2
    got = events(_post(make_client(repo)))
    assert got[-1]["type"] == "error"
    assert "could not be saved" in got[-1]["message"]
    assert repo.rows == []


def test_heartbeat_reaches_the_client():
    def slow(api_key, tavily_key, company, status_callback, **kwargs):
        time.sleep(0.25)
        return SAMPLE_BRIEF
    resp = _post(make_client(generator=slow, heartbeat_seconds=0.05))
    assert ": ping" in resp.text
    assert events(resp)[-1]["type"] == "done"


# ── Refresh (Update Brief) ───────────────────────────────────────

def _refresh(client, brief_id, body=None, headers=AUTH):
    return client.post(f"{GEN}/{brief_id}/refresh", json=body or {}, headers=headers)


def test_refresh_replaces_the_brief_and_always_researches():
    repo = FakeRepo()
    old = repo.seed("partner@example.com", created_at="2026-10-04T00:00:00+00:00")
    calls = []
    def generator(api_key, tavily_key, company, status_callback, language="en", **kwargs):
        calls.append((company, language))
        return SAMPLE_BRIEF
    got = events(_refresh(make_client(repo, generator=generator), old["id"]))
    assert calls == [("TestCo Holdings", "en")]
    assert got[-1]["type"] == "done" and got[-1]["reusedFrom"] is None
    mine = repo.get_user_briefs("partner@example.com")
    assert [b["id"] for b in mine] == [got[-1]["briefId"]]
    assert got[-1]["briefId"] != old["id"]


def test_refresh_of_someone_elses_brief_is_404():
    repo = FakeRepo()
    old = repo.seed("partner@example.com")
    assert _refresh(make_client(repo), old["id"], headers=OTHER).status_code == 404
    assert len(repo.rows) == 1


def test_failed_refresh_keeps_the_old_brief():
    repo = FakeRepo()
    old = repo.seed("partner@example.com")
    def broken(*args, **kwargs):
        raise RuntimeError("boom")
    got = events(_refresh(make_client(repo, generator=broken), old["id"]))
    assert got[-1]["type"] == "error"
    assert [r["id"] for r in repo.rows] == [old["id"]]


def test_refresh_can_switch_language():
    repo = FakeRepo()
    old = repo.seed("partner@example.com")
    seen = []
    def generator(api_key, tavily_key, company, status_callback, language="en", **kwargs):
        seen.append(language)
        return SAMPLE_BRIEF
    _refresh(make_client(repo, generator=generator), old["id"], body={"language": "es"})
    assert seen == ["es"]


def test_refresh_still_succeeds_when_the_old_copy_cannot_be_removed():
    repo = FakeRepo()
    old = repo.seed("partner@example.com")
    repo.delete_brief = lambda brief_id, email: False
    got = events(_refresh(make_client(repo), old["id"]))
    assert got[-1]["type"] == "done"
    assert len(repo.rows) == 2  # the new brief is saved; the old one is left in place


def test_refresh_is_refused_while_a_generation_is_running():
    repo = FakeRepo()
    old = repo.seed("partner@example.com")
    client = make_client(repo)
    client.app.state.service._guard.acquire("partner@example.com")

    assert _refresh(client, old["id"]).status_code == 409


@pytest.mark.parametrize("scenario", ["not_found", "not_configured", "at_limit"])
def test_a_refused_refresh_does_not_leave_the_user_locked(scenario):
    """Every way a refresh can be turned away must release the in-flight guard."""
    repo = FakeRepo()
    old = repo.seed("partner@example.com")
    settings = TEST_SETTINGS
    target = old["id"]
    if scenario == "not_found":
        target = "00000000-0000-4000-8000-000000000000"
    elif scenario == "not_configured":
        settings = replace(TEST_SETTINGS, tavily_key="")
    client = make_client(repo, settings=replace(settings, daily_limit=1))
    if scenario == "at_limit":
        assert events(_post(client, company="Uses The Limit"))[-1]["type"] == "done"

    refused = _refresh(client, target)

    assert refused.status_code in (404, 429, 503)
    assert client.app.state.service._guard.acquire("partner@example.com") is True


def test_a_refresh_that_cannot_be_saved_keeps_the_old_brief():
    repo = FakeRepo()
    old = repo.seed("partner@example.com")
    repo.save_failures = 2

    got = events(_refresh(make_client(repo), old["id"]))

    assert got[-1]["type"] == "error"
    assert "could not be saved" in got[-1]["message"]
    assert [row["id"] for row in repo.rows] == [old["id"]]


def test_refresh_researches_the_stored_name_cleaned_up():
    """The stored name was written by the model, so it is cleaned like typed input."""
    repo = FakeRepo()
    old = repo.seed("partner@example.com", company="Acme\nCorp\x00  " + "x" * 300)
    seen = []
    def generator(api_key, tavily_key, company, status_callback, **kwargs):
        seen.append(company)
        return SAMPLE_BRIEF

    _refresh(make_client(repo, generator=generator), old["id"])

    assert len(seen) == 1
    assert seen[0].startswith("Acme Corp x")
    assert len(seen[0]) <= 100 and "\n" not in seen[0] and "\x00" not in seen[0]


def test_reuse_does_not_duplicate_research_the_partner_already_has():
    original = "2026-10-01T09:00:00+00:00"
    repo = FakeRepo()
    repo.seed("someone@else.com", company="TestCo Holdings", brief_md=SHARED, created_at=original)
    client = make_client(repo)
    first = events(_post(client, company="TestCo Holdings"))[-1]

    second = events(_post(client, company="TestCo Holdings"))[-1]

    assert second == {"type": "done", "briefId": first["briefId"], "reusedFrom": original}
    assert len(repo.get_user_briefs("partner@example.com")) == 1


def test_asking_again_for_my_own_recent_brief_opens_it_instead_of_copying_it():
    repo = FakeRepo()
    mine = repo.seed(
        "partner@example.com", company="TestCo Holdings", brief_md=SHARED,
        created_at="2026-10-02T09:00:00+00:00",
    )
    calls = []
    def generator(*args, **kwargs):
        calls.append(args)
        return SAMPLE_BRIEF

    got = events(_post(make_client(repo, generator=generator), company="TestCo Holdings"))

    assert calls == []
    assert got[-1]["briefId"] == mine["id"]
    assert len(repo.rows) == 1


def test_a_brief_with_no_usable_company_name_cannot_be_refreshed():
    repo = FakeRepo()
    old = repo.seed("partner@example.com", company="  \n ")
    client = make_client(repo)

    refused = _refresh(client, old["id"])

    assert refused.status_code == 400
    assert "no company name" in refused.json()["error"]
    assert client.app.state.service._guard.acquire("partner@example.com") is True


def test_a_stored_name_that_is_a_web_address_cannot_be_refreshed():
    repo = FakeRepo()
    old = repo.seed("partner@example.com", company="Acme, see https://evil.example/facts")
    client = make_client(repo)

    refused = _refresh(client, old["id"])

    assert refused.status_code == 400
    assert "no company name" in refused.json()["error"]
    assert client.app.state.service._guard.acquire("partner@example.com") is True


def test_a_job_that_cannot_be_started_does_not_leave_the_user_locked(monkeypatch):
    """If the worker thread cannot start, nothing will ever release the guard but us."""
    import server

    def cannot_start(*args, **kwargs):
        raise RuntimeError("can't start new thread")
    monkeypatch.setattr(server, "stream_job", cannot_start)
    client = make_client()
    client_quiet = TestClient(client.app, raise_server_exceptions=False)

    failed = client_quiet.post(GEN, json={"company": "TestCo"}, headers=AUTH)

    assert failed.status_code == 500
    assert "can't start" not in failed.text
    assert client.app.state.service._guard.acquire("partner@example.com") is True
