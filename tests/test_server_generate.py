import threading
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from brief_service import BriefService
from errors import GenerationInFlight
from tests.api_fakes import (
    AUTH, OTHER, SAMPLE_BRIEF, TEST_SETTINGS, FakeRepo, events, fake_generator, make_client,
)

GEN = "/api/brief/briefs"


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
    repo.seed("someone@else.com", company="TestCo Holdings", created_at=original)
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
    repo.seed("someone@else.com", company="TestCo Holdings")  # English
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


def test_second_generation_while_in_flight_is_rejected():
    service = BriefService(FakeRepo(), fake_generator, TEST_SETTINGS)
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


def test_daily_limit_blocks_new_research_but_not_reuse():
    today = datetime.now(timezone.utc).isoformat()
    repo = FakeRepo()
    repo.seed("partner@example.com", company="Already Done", created_at=today)
    repo.seed("someone@else.com", company="Shared Co", created_at=today)
    client = make_client(repo, settings=replace(TEST_SETTINGS, daily_limit=1))
    blocked = _post(client, company="Brand New Co")
    assert blocked.status_code == 429
    assert "1" in blocked.json()["error"]
    assert events(_post(client, company="Shared Co"))[-1]["type"] == "done"


def test_yesterdays_briefs_do_not_count_toward_today():
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1, minutes=1)).isoformat()
    repo = FakeRepo()
    repo.seed("partner@example.com", company="Old", created_at=yesterday)
    client = make_client(repo, settings=replace(TEST_SETTINGS, daily_limit=1))
    assert events(_post(client, company="Brand New Co"))[-1]["type"] == "done"


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
