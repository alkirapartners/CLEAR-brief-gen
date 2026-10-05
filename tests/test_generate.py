"""Research, then judge and write: the generation contract. No live API calls."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

import brief_doc
import generate
import llm
import prompts
import research_floor
import research_loop
from errors import GENERIC_ERROR
from dataclasses import replace

from tests.api_fakes import AUTH, TEST_SETTINGS, FakeRepo, events, make_client
from tests.brief_fixtures import writer_output
from tests.llm_fakes import FakeClient, reply, text, thinking, timed_out
from tests.test_research_loop import FOUND_SOMETHING, Clock
from tests.test_research_tools import JOB, FakeWeb

TODAY = date(2026, 10, 5)


@pytest.fixture(autouse=True)
def no_floor(monkeypatch):
    """The fake research is three turns long. The floor is tested with the research loop."""
    monkeypatch.setattr(research_floor, "MAX_NUDGES", 0)


def _output(**changes):
    """A writer output that cites only source 1, the one page the fake research opens."""
    output = writer_output()
    output["angles"] = output["angles"][:1]
    output["fit"] = {**output["fit"], "score": 4}
    output["snapshot"]["plant_networks"] = {"text": "", "sources": []}
    output["people"] = output["people"][:1]
    output.update(changes)
    return output


def _written(output=None, **kwargs):
    return reply(thinking(), text(json.dumps(output if output is not None else _output())), **kwargs)


def _generate(writer=None, turns=FOUND_SOMETHING, language="en", company="Northwind", client=None, clock=None):
    client = client or FakeClient(list(turns), writer=writer or _written())
    phases = []
    result = generate.generate_detailed(
        "anthropic-key", "tavily-key", company, phases.append,
        language=language, client=client, web=FakeWeb(), today=TODAY,
        **({"clock": clock} if clock is not None else {}),
    )
    return result, client, phases


# ── The writer cannot outrun the clock ───────────────────────────

def test_the_writer_request_has_a_stall_limit_and_one_retry():
    _, client, _ = _generate()
    assert client.options[-1] == {
        "timeout": generate.WRITER_STALL_SECONDS, "max_retries": generate.WRITER_RETRIES,
    }
    assert generate.WRITER_RETRIES == 1


def test_a_writer_that_runs_past_its_deadline_is_stopped_and_its_stream_closed():
    clock = Clock()

    def slow():
        clock.now += generate.WRITER_DEADLINE_SECONDS  # every event takes the whole allowance

    client = FakeClient(list(FOUND_SOMETHING), writer=_written(), on_writer_event=slow)
    with pytest.raises(RuntimeError, match="Writing the brief for 'Northwind' ran past"):
        _generate(client=client, clock=clock)
    assert client.stream.closed


def test_the_writer_is_told_what_the_research_never_got_to():
    _, client, _ = _generate()
    content = client.writer_requests[0]["messages"][0]["content"]
    assert "The research did not get to: " in content and "latest annual filing" in content
    assert content.index("did not get to") < content.index("The evidence follows.")


# ── What comes back ──────────────────────────────────────────────

def test_the_brief_is_a_stored_json_document():
    result, _, _ = _generate()
    doc = brief_doc.load(result.stored)
    assert doc is not None and doc == result.doc
    assert doc["format"] == 2 and doc["language"] == "en" and doc["generated"] == "2026-10-05"
    assert doc["company"]["name"] == "Northwind Energy" and doc["fit"]["score"] == 4
    assert [(r["n"], r["url"]) for r in doc["references"]] == [(1, JOB)]
    assert doc["research"] == {"searches": 1, "pages": 1, "seconds": 0, "stopped_by": "finished"}


def test_the_five_phases_are_reported_once_each_in_order():
    _, _, phases = _generate()
    assert phases == ["init", "research", "analyze", "compose", "done"]


def test_compose_is_still_reported_when_the_reply_has_no_thinking_block():
    _, _, phases = _generate(writer=reply(text(json.dumps(_output()))))
    assert phases == ["init", "research", "analyze", "compose", "done"]


def test_the_api_entry_point_returns_only_the_stored_text(monkeypatch):
    client = FakeClient(list(FOUND_SOMETHING), writer=_written())
    built = []
    monkeypatch.setattr(llm, "make_client", lambda key, timeout: built.append((key, timeout)) or client)
    monkeypatch.setattr(generate, "TavilyClient", lambda api_key: FakeWeb())
    stored = generate.generate_brief("anthropic-key", "tavily-key", "Northwind", lambda phase: None)
    assert brief_doc.load(stored)["company"]["name"] == "Northwind Energy"
    assert built == [("anthropic-key", llm.REQUEST_TIMEOUT_SECONDS)]


# ── The judge-and-write request ──────────────────────────────────

def test_the_writer_request_is_one_cached_structured_call_with_no_tools():
    _, client, _ = _generate()
    (request,) = client.writer_requests
    assert request["model"] == "claude-sonnet-5-5"
    assert request["max_tokens"] == 16000
    assert request["thinking"] == {"type": "adaptive"}
    assert request["output_config"] == {
        "effort": "medium",
        "format": {"type": "json_schema", "schema": brief_doc.WRITER_SCHEMA},
    }
    assert request["system"] == [{
        "type": "text", "text": prompts.build_writer_prefix(),
        "cache_control": {"type": "ephemeral", "ttl": "1h"},
    }]
    assert "tools" not in request and "tool_choice" not in request
    assert [m["role"] for m in request["messages"]] == ["user"]  # no assistant prefill


def test_the_writer_sees_the_fenced_evidence_and_nothing_else_about_the_web():
    _, client, _ = _generate(company="Northwind")
    content = client.writer_requests[0]["messages"][0]["content"]
    fence = content.split("<source-")[1].split(">")[0]
    assert f"<name-{fence}>Northwind</name-{fence}>" in content  # one random tag fences the name and the evidence
    assert "[1] Senior Network Engineer" in content and f"URL: {JOB}" in content
    assert "- [cloud] Runs ExpressRoute and a Virtual WAN hub-and-spoke." in content
    assert content.count("<source-") == 2  # the header and the one source
    assert "Senior Network Engineer. ExpressRoute, Virtual WAN hub-and-spoke, BGP." not in content  # no raw page text


def test_language_goes_in_the_message_and_the_document_never_in_the_cached_prefix():
    english, english_client, _ = _generate(language="en")
    spanish, spanish_client, _ = _generate(language="es")
    assert spanish_client.writer_requests[0]["system"] == english_client.writer_requests[0]["system"]
    assert "Output Language: Spanish" in spanish_client.writer_requests[0]["messages"][0]["content"]
    assert "Spanish" not in english_client.writer_requests[0]["messages"][0]["content"]
    assert spanish.doc["language"] == "es" and english.doc["language"] == "en"
    # Research is always English: the research requests are the same in both.
    assert spanish_client.requests[0]["system"] == english_client.requests[0]["system"]


def test_the_writer_is_told_when_research_was_cut_short(monkeypatch):
    real = research_loop.research

    def cut_short(*args, **kwargs):
        found = real(*args, **kwargs)
        return research_loop.ResearchResult(
            found.sources, found.searches, found.page_reads, found.pages_opened,
            found.seconds, research_loop.DEADLINE, found.usage,
        )

    monkeypatch.setattr(research_loop, "research", cut_short)
    result, client, _ = _generate()
    assert "its time ran out" in client.writer_requests[0]["messages"][0]["content"]
    assert result.doc["research"]["stopped_by"] == "deadline"


# ── The code enforces the rules on whatever the model wrote ──────

def test_an_angle_citing_a_page_that_was_never_opened_is_removed_and_the_score_capped():
    result, _, _ = _generate(writer=_written(writer_output()))  # cites sources 1 and 2; only 1 exists
    assert [angle["title"] for angle in result.doc["angles"]] == ["Hand-built Azure network"]
    assert result.doc["fit"]["score"] == 4  # a 5 needs two evidenced angles
    assert result.doc["snapshot"]["plant_networks"] == {"text": "", "sources": []}
    assert [ref["url"] for ref in result.doc["references"]] == [JOB]


def test_the_customer_name_is_taken_from_the_knowledge_base():
    output = _output()
    output["angles"][0]["story"] = {"id": "michaels", "customer": "Somebody Else", "result": "Three weeks."}
    result, _, _ = _generate(writer=_written(output))
    story = result.doc["angles"][0]["story"]
    assert story["customer"] == "Michaels" and "1,400 stores" in story["result"]


# ── Failures: an error, never a broken or uncited brief ──────────

def test_text_that_is_not_the_document_is_an_error_that_shows_what_came_back():
    with pytest.raises(RuntimeError) as exc:
        _generate(writer=reply(text("Sure! Here is the brief you asked for.")))
    assert "contract" in str(exc.value) and "Sure!" in str(exc.value) and "end_turn" in str(exc.value)


def test_json_that_does_not_match_the_schema_is_an_error():
    with pytest.raises(RuntimeError, match="contract"):
        _generate(writer=reply(text(json.dumps({"company": "Northwind"}))))


def test_a_truncated_reply_is_an_error():
    with pytest.raises(RuntimeError, match="truncated"):
        _generate(writer=_written(stop_reason="max_tokens"))


def test_an_empty_reply_is_an_error():
    with pytest.raises(RuntimeError, match="empty output"):
        _generate(writer=reply(thinking(), text("   ")))


def test_a_declined_reply_is_an_error_that_names_the_category():
    declined = reply(text(""), stop_reason="refusal", stop_details=SimpleNamespace(category="general_harms"))
    with pytest.raises(RuntimeError, match="declined to write the brief for 'Northwind' \\(general_harms\\)"):
        _generate(writer=declined)


def test_research_that_finds_nothing_is_an_error_and_the_writer_is_never_called():
    client = FakeClient([], writer=_written())
    with pytest.raises(research_loop.ResearchError):
        generate.generate_detailed(
            "k", "t", "Asdfgh", lambda phase: None, client=client, web=FakeWeb(), today=TODAY,
        )
    assert client.writer_requests == []


def test_a_missing_tavily_key_is_an_error_before_any_call():
    with pytest.raises(research_loop.ResearchError, match="TAVILY_API_KEY"):
        generate.generate_detailed("k", "", "Acme", lambda phase: None, client=FakeClient())


# ── Cost ─────────────────────────────────────────────────────────

def test_usage_covers_research_and_writing_and_is_priced(caplog):
    with caplog.at_level("INFO", logger="generate"):
        result, client, _ = _generate()
    assert result.usage.requests == len(client.requests) + 1
    assert result.cost == pytest.approx(
        llm.token_cost(result.usage) + llm.web_cost(result.research.searches, result.research.pages_opened)
    )
    assert result.cost > 0 and result.seconds >= 0
    assert "cache_read=0 cache_write=0" in caplog.text  # the line used to confirm caching in production


# ── Through the API, end to end ──────────────────────────────────

def _api_generator(turns):
    """The real generator, with the model and the web replaced by fakes."""

    def generator(api_key, tavily_key, company, status_callback, language="en", **kwargs):
        client = FakeClient(list(turns), writer=_written())
        return generate.generate_detailed(
            api_key, tavily_key, company, status_callback, language=language,
            client=client, web=FakeWeb(), today=TODAY,
        ).stored

    return generator


def test_a_generated_brief_is_saved_then_served_in_both_shapes_and_as_a_pdf():
    """The path a partner takes: generate, open the brief, download the PDF."""
    repo = FakeRepo()
    api = make_client(repo, generator=_api_generator(FOUND_SOMETHING))
    got = events(api.post("/api/brief/briefs", json={"company": "Northwind", "language": "en"}, headers=AUTH))
    assert [event.get("phase") for event in got[:-1]] == ["init", "research", "analyze", "compose"]
    assert got[-1]["type"] == "done"

    (row,) = repo.rows
    assert (row["company"], row["score"]) == ("Northwind", 4)  # filed under the typed name

    data = api.get(f"/api/brief/briefs/{got[-1]['briefId']}", headers=AUTH).json()["data"]
    assert data["format"] == 2 and data["score"] == 4
    assert [point["heading"] for point in data["entryPoints"]] == ["Hand-built Azure network"]
    assert data["referencesMd"] == f"[1] Senior Network Engineer — {JOB}"
    assert data["doc"]["references"][0]["url"] == JOB

    listed = api.get("/api/brief/briefs", headers=AUTH).json()["data"]
    assert listed[0]["snippet"].startswith("Strong fit")
    assert listed[0]["company"] == data["company"] == "Northwind Energy"  # shown under the resolved name

    download = api.get(f"/api/brief/briefs/{got[-1]['briefId']}/pdf", headers=AUTH)
    assert download.status_code == 200 and download.content.startswith(b"%PDF-")


def test_research_that_finds_nothing_reaches_the_partner_as_an_error_and_saves_nothing():
    repo = FakeRepo()
    api = make_client(repo, generator=_api_generator([]))
    got = events(api.post("/api/brief/briefs", json={"company": "Asdfgh", "language": "en"}, headers=AUTH))
    assert got[-1] == {"type": "error", "message": research_loop.NOTHING_CITABLE_MESSAGE}
    assert "Check the spelling" in got[-1]["message"] and "Asdfgh" not in got[-1]["message"]
    assert repo.rows == []


def test_research_that_finds_nothing_still_uses_the_day_s_slot():
    """The research was paid for. Giving the slot back would make such runs unlimited."""
    api = make_client(FakeRepo(), generator=_api_generator([]), settings=replace(TEST_SETTINGS, daily_limit=1))
    events(api.post("/api/brief/briefs", json={"company": "Asdfgh", "language": "en"}, headers=AUTH))
    again = api.post("/api/brief/briefs", json={"company": "Asdfgh", "language": "en"}, headers=AUTH)
    assert again.status_code == 429


def test_a_service_failure_during_research_is_not_blamed_on_the_company_name():
    api = make_client(FakeRepo(), generator=_api_generator([timed_out()]))
    got = events(api.post("/api/brief/briefs", json={"company": "Acme", "language": "en"}, headers=AUTH))
    assert got[-1] == {"type": "error", "message": GENERIC_ERROR}
