"""The research loop: follow leads, stay inside the budget, never return nothing."""

from datetime import date
from types import SimpleNamespace

import pytest

import llm
import prompts
import research_floor
import research_loop
import research_tools as tools
from errors import UserFacingError
from research_loop import ResearchError
from tests.llm_fakes import (
    FakeClient, bad_request, overloaded, reply, text, thinking, timed_out, tool_use, usage,
)
from tests.test_research_tools import JOB, FakeWeb

TODAY = date(2026, 10, 5)
FACT = {
    "fact": "Runs ExpressRoute and a Virtual WAN hub-and-spoke.", "category": "cloud",
    "quote": "ExpressRoute, Virtual WAN hub-and-spoke, BGP",
    "source_url": JOB, "source_title": "Senior Network Engineer", "source_date": "2026-09-23",
}
SEARCH = reply(thinking(), tool_use("s1", "web_search", {"query": "acme careers network", "site": "", "recent_news": False}))
READ = reply(tool_use("r1", "read_page", {"url": JOB, "find": ""}))
RECORD = reply(tool_use("e1", "record_evidence", {"items": [FACT]}))
FOUND_SOMETHING = [SEARCH, READ, RECORD]
DONE = reply(text("Research complete."))


@pytest.fixture(autouse=True)
def no_floor(monkeypatch):
    """These tests script a few turns. The floor has its own tests at the end."""
    monkeypatch.setattr(research_floor, "MAX_NUDGES", 0)


class Clock:
    """A clock the test moves by hand."""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def _run(turns=FOUND_SOMETHING, then=None, web=None, clock=None, on_request=None, company="Acme"):
    client = FakeClient(turns, then=then, on_request=on_request)
    phases = []
    result = research_loop.research(
        company, phases.append, client, web if web is not None else FakeWeb(),
        clock=clock or Clock(), today=TODAY, sleep=lambda _seconds: None,
    )
    return result, client, phases


# ── The happy path ───────────────────────────────────────────────

def test_evidence_recorded_from_an_opened_page_comes_back_as_a_numbered_source():
    result, client, phases = _run()
    (source,) = result.sources
    assert (source.n, source.url, source.title, source.date) == (1, JOB, "Senior Network Engineer", "2026-09-23")
    assert source.facts[0].fact.startswith("Runs ExpressRoute")
    assert (result.searches, result.page_reads, result.pages_opened) == (1, 1, 1)
    assert result.stopped_by == "finished"
    assert phases == ["research"]
    assert len(client.requests) == 4  # three tool turns, then the model says it is done


def test_every_request_is_a_cached_tool_request_to_sonnet_5_5():
    _, client, _ = _run()
    for request in client.requests:
        assert request["model"] == "claude-sonnet-5-5"
        assert request["thinking"] == {"type": "adaptive"}
        assert request["output_config"] == {"effort": "medium"}
        assert request["tools"] == list(tools.TOOLS)
        assert request["cache_control"] == {"type": "ephemeral"}
        assert request["system"][0]["text"] == prompts.build_research_prefix()
        assert request["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
        assert "tool_choice" not in request  # forcing a tool is rejected by this model


def test_the_conversation_only_ever_grows():
    """Earlier turns are replayed unchanged, or the cache and the model's own notes are lost."""
    _, client, _ = _run()
    sent = [request["messages"] for request in client.requests]
    for earlier, later in zip(sent, sent[1:]):
        assert later[: len(earlier)] == earlier
        assert [m["role"] for m in later[len(earlier):]] == ["assistant", "user"]
    assert sent[1][1]["content"] is SEARCH.content  # the reply goes back whole, thinking included
    assert sent[1][2]["content"][0]["tool_use_id"] == "s1"


def test_the_company_and_the_fence_are_in_the_first_message_never_in_the_system_prefix():
    _, client, _ = _run(company="Zebra Holdings")
    opening = client.requests[0]["messages"][0]["content"]
    assert "Today's date: 2026-10-05" in opening
    assert "Budget: 25 searches, 20 page reads, about 4 minutes." in opening
    assert "Zebra Holdings" not in client.requests[0]["system"][0]["text"]
    fence = opening.split("<web-")[1].split(">")[0]
    assert f"<name-{fence}>Zebra Holdings</name-{fence}>" in opening
    tool_result = client.requests[1]["messages"][2]["content"][0]["content"]
    assert f"<web-{fence}>" in tool_result


def test_the_fence_changes_from_one_run_to_the_next():
    first = _run()[1].requests[0]["messages"][0]["content"]
    second = _run()[1].requests[0]["messages"][0]["content"]
    assert first != second


def test_tokens_are_added_up_across_turns():
    turns = [
        reply(tool_use("r1", "read_page", {"url": JOB, "find": ""}), used=usage(100, 10, cache_read=5000)),
        reply(tool_use("e1", "record_evidence", {"items": [FACT]}), used=usage(200, 30, cache_write=700)),
    ]
    result, _, _ = _run(turns, then=reply(text("Done."), used=usage(1, 1)))
    assert result.usage == llm.Usage(
        requests=3, input_tokens=301, output_tokens=41, cache_read_tokens=5000, cache_write_1h_tokens=700,
    )


def test_the_result_says_how_many_facts_were_kept_and_how_many_refused():
    invented = {**FACT, "quote": "We operate 14 data centers on a Cisco ACI fabric"}
    both = reply(tool_use("e1", "record_evidence", {"items": [FACT, invented]}))
    result, _, _ = _run([READ, both])
    assert (result.facts_kept, result.facts_refused) == (1, 1)


def test_a_page_on_the_company_s_own_domain_is_first_hand_and_the_same_page_for_another_company_is_not():
    own, _, _ = _run(company="Acme")  # the fake posting is on careers.acme-northwind.example
    other, _, _ = _run(company="Zenith Holdings")
    assert own.sources[0].source_type == "first_hand" and other.sources[0].source_type == "second_hand"


def test_an_undated_open_posting_on_the_company_s_careers_site_is_dated_the_day_of_the_research():
    undated = {**FACT, "source_date": ""}
    result, _, _ = _run([READ, reply(tool_use("e1", "record_evidence", {"items": [undated]}))], company="Acme")
    (source,) = result.sources
    assert (source.date, source.open_posting, source.source_type) == ("2026-10-05", True, "first_hand")
    other, _, _ = _run([READ, reply(tool_use("e1", "record_evidence", {"items": [undated]}))], company="Zenith Holdings")
    assert (other.sources[0].date, other.sources[0].open_posting) == ("", False)


# ── Research that finds nothing is an error, never a brief ───────

def test_no_recorded_evidence_is_an_error():
    with pytest.raises(ResearchError) as raised:
        _run([SEARCH], company="Asdfgh")
    assert "nothing citable for 'Asdfgh'" in raised.value.detail


def test_finding_nothing_is_an_error_a_partner_can_be_shown():
    with pytest.raises(research_loop.NothingCitable) as raised:
        _run([SEARCH], company="Asdfgh")
    assert isinstance(raised.value, UserFacingError) and isinstance(raised.value, ResearchError)
    assert str(raised.value) == research_loop.NOTHING_CITABLE_MESSAGE
    assert "searches=1" in raised.value.detail and "'Asdfgh'" in raised.value.detail


def test_a_failing_service_is_not_reported_as_an_unknown_company():
    with pytest.raises(ResearchError) as raised:
        _run([_five_searches()], web=FakeWeb(fail=True))
    assert not isinstance(raised.value, research_loop.NothingCitable)


def test_evidence_only_from_pages_that_were_never_opened_is_an_error():
    with pytest.raises(research_loop.NothingCitable):
        _run([SEARCH, RECORD])  # recorded from the search summary, page never read


def test_a_refusal_is_an_error_that_names_the_category():
    declined = reply(text("I can't help with that."), stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"))
    with pytest.raises(ResearchError, match="declined to research 'Acme' \\(cyber\\)"):
        _run([READ, RECORD, declined])


def _five_searches():
    return reply(*[tool_use(f"s{i}", "web_search", {"query": f"q{i}", "site": "", "recent_news": False}) for i in range(5)])


def test_a_web_service_that_keeps_failing_is_an_error():
    with pytest.raises(ResearchError, match="kept failing"):
        _run([_five_searches()], web=FakeWeb(fail=True))


def test_a_model_request_that_fails_with_nothing_gathered_is_an_error():
    failure = timed_out()
    with pytest.raises(ResearchError, match="request to the model failed while researching 'Acme'") as raised:
        _run([SEARCH, timed_out(), failure])  # the first attempt and its one retry
    assert raised.value.__cause__ is failure


# ── A late failure keeps what was already gathered ───────────────

def test_a_web_service_that_fails_late_keeps_the_evidence_already_recorded():
    web = FakeWeb()

    def break_the_web(request_number):
        web.fail = request_number >= 3

    result, client, _ = _run([READ, RECORD, _five_searches()], web=web, on_request=break_the_web)
    assert result.stopped_by == "web_failed"
    assert len(result.sources) == 1
    assert len(client.requests) == 3  # no further turn is spent on a web that is down


def test_a_model_request_that_fails_late_keeps_the_evidence_already_recorded():
    result, client, _ = _run([READ, RECORD, timed_out(), timed_out()])
    assert result.stopped_by == "model_failed"
    assert len(result.sources) == 1
    assert result.usage.requests == 2  # the failed requests billed nothing
    assert len(client.requests) == 4  # tried once more, then stopped


# ── Budgets and the clock ────────────────────────────────────────

def test_at_the_hard_deadline_no_new_turn_starts_and_what_was_gathered_is_kept():
    clock = Clock()

    def tick(request_number):
        if request_number == 3:  # the third request takes the run past four minutes
            clock.now += research_loop.HARD_DEADLINE_SECONDS

    keep_searching = reply(tool_use("sx", "web_search", {"query": "more", "site": "", "recent_news": False}))
    result, client, _ = _run([READ, RECORD], then=keep_searching, clock=clock, on_request=tick)
    assert result.stopped_by == "deadline"
    assert len(result.sources) == 1
    assert len(client.requests) == 3
    assert result.seconds >= research_loop.HARD_DEADLINE_SECONDS


def test_a_deadline_with_nothing_gathered_is_an_error():
    clock = Clock()

    def tick(_request_number):
        clock.now += research_loop.HARD_DEADLINE_SECONDS

    with pytest.raises(ResearchError) as raised:
        _run([SEARCH], then=SEARCH, clock=clock, on_request=tick)
    assert "stopped by deadline" in raised.value.detail


def test_after_the_soft_deadline_the_web_is_closed_but_evidence_is_still_recorded():
    clock = Clock()

    def tick(request_number):
        if request_number == 2:
            clock.now += research_loop.SOFT_DEADLINE_SECONDS + 1

    late = reply(
        tool_use("s2", "web_search", {"query": "one more", "site": "", "recent_news": False}),
        tool_use("e1", "record_evidence", {"items": [FACT]}),
    )
    web = FakeWeb()
    result, client, _ = _run([READ, late], web=web, clock=clock, on_request=tick)
    assert web.searches == []  # the late search never reached the web
    assert len(result.sources) == 1  # the evidence sent with it was kept
    refused = client.requests[2]["messages"][-1]["content"][0]
    assert refused["is_error"] is True and refused["content"].startswith(tools.TIME_UP)


def test_a_model_that_never_stops_is_stopped_at_the_turn_limit():
    again = reply(tool_use("sx", "web_search", {"query": "again", "site": "", "recent_news": False}))
    result, client, _ = _run([READ, RECORD], then=again)
    assert result.stopped_by == "turn_cap"
    assert len(client.requests) == research_loop.MAX_TURNS
    assert result.searches == tools.MAX_SEARCHES  # the budget held even though the model kept asking


def test_spending_the_whole_budget_is_reported_as_budget_not_as_finished():
    searches = [
        reply(*[tool_use(f"s{b}-{i}", "web_search", {"query": f"q{b}{i}", "site": "", "recent_news": False}) for i in range(5)])
        for b in range(5)
    ]
    result, _, _ = _run([READ, RECORD, *searches])
    assert result.searches == tools.MAX_SEARCHES and result.stopped_by == "budget"


def test_a_cut_off_reply_ends_research_without_running_its_tool_calls():
    cut = reply(tool_use("r9", "read_page", {"url": "https://example.com/other", "find": ""}), stop_reason="max_tokens")
    web = FakeWeb()
    result, _, _ = _run([READ, RECORD, cut], web=web)
    assert result.stopped_by == "truncated"
    assert [urls for urls, _ in web.extracts] == [[JOB]]


def test_only_abnormal_stops_are_worded_for_the_writer():
    assert set(research_loop.EARLY_STOPS) == {
        "deadline", "turn_cap", "truncated", "web_failed", "model_failed", "cost_cap",
    }
    assert "finished" not in research_loop.EARLY_STOPS and "budget" not in research_loop.EARLY_STOPS


# ── No single request can outrun the clock ───────────────────────

@pytest.mark.parametrize("elapsed, timeout", [
    (0, 90), (150, 90), (210, 90), (230, 70), (239, 61), (280, 20), (281, None), (300, None),
])
def test_an_attempt_is_given_only_the_time_left_before_the_ceiling(elapsed, timeout):
    assert research_loop.attempt_timeout(elapsed) == timeout


def _stalling(clock, turns, start_at=0.0):
    """Run research against a model whose every request takes all the time it is allowed."""
    clock.now += start_at
    holder = {}

    def stall(_request_number):
        clock.now += holder["client"].options[-1]["timeout"]

    client = FakeClient(turns, then=timed_out(), on_request=stall)
    holder["client"] = client
    started = clock.now - start_at

    def pause(seconds):
        clock.now += seconds

    try:
        research_loop.research("Acme", lambda _phase: None, client, FakeWeb(), clock=clock, today=TODAY, sleep=pause)
    except ResearchError:
        pass
    return clock.now - started, client


@pytest.mark.parametrize("turns", [[], [READ, RECORD], [SEARCH, READ, RECORD, SEARCH]], ids=["at-once", "late", "later"])
def test_research_never_runs_past_its_ceiling_however_the_model_stalls(turns):
    elapsed, client = _stalling(Clock(), [timed_out() if not turns else turns[0], *turns[1:]])
    assert elapsed <= research_loop.RESEARCH_CEILING_SECONDS
    assert all(options["max_retries"] == 0 for options in client.options)  # the SDK never sleeps on our behalf


def test_a_busy_api_s_long_retry_after_is_not_obeyed():
    """The SDK would sleep for the ten minutes the header asks for. The loop pauses two seconds."""
    clock = Clock()
    pauses = []

    def pause(seconds):
        pauses.append(seconds)
        clock.now += seconds

    client = FakeClient([READ, RECORD, overloaded(retry_after="600"), DONE])
    result = research_loop.research("Acme", lambda _phase: None, client, FakeWeb(), clock=clock, today=TODAY, sleep=pause)
    assert pauses == [research_loop.RETRY_PAUSE_SECONDS]
    assert result.stopped_by == "finished" and len(client.requests) == 4


def test_a_request_the_api_rejects_outright_is_not_tried_again():
    result, client, _ = _run([READ, RECORD, bad_request()])
    assert result.stopped_by == "model_failed" and len(client.requests) == 3


def test_every_research_request_is_sent_with_its_own_time_limit_and_no_sdk_retries():
    _, client, _ = _run()
    assert client.options[0] == {"timeout": 90, "max_retries": 0}
    assert len(client.options) == len(client.requests)


def test_pages_read_just_before_the_web_closes_are_still_recorded():
    """A read issued at the last moment is over in time for the turn that records it."""
    clock, web = Clock(), FakeWeb()

    def tick(request_number):
        if request_number == 1:  # the reply asking for the page arrives a second before the web closes
            clock.now += research_loop.SOFT_DEADLINE_SECONDS - 1

    def slow_web(timeout):
        clock.now += timeout  # the page takes as long as it is allowed

    web.on_call = slow_web
    result, client, _ = _run([READ, RECORD], web=web, clock=clock, on_request=tick)
    assert web.extracts[0][1]["timeout"] <= tools.TAVILY_TIMEOUT_SECONDS
    assert len(result.sources) == 1 and result.stopped_by == "finished"
    assert result.seconds < research_loop.HARD_DEADLINE_SECONDS


# ── A ceiling on what one brief's research may cost ──────────────

def _costly(call_id):
    """A turn that bills about 36 cents: a long conversation re-read and a long reply."""
    return reply(
        tool_use(call_id, "web_search", {"query": call_id, "site": "", "recent_news": False}),
        used=usage(input_tokens=100_000, output_tokens=16_000),
    )


def test_research_stops_at_the_spending_ceiling_and_keeps_what_it_gathered():
    turns = [READ, RECORD, *[_costly(f"c{i}") for i in range(30)]]
    result, client, _ = _run(turns)
    assert result.stopped_by == "cost_cap"
    assert len(result.sources) == 1
    spent = llm.token_cost(result.usage) + llm.web_cost(result.searches, result.pages_opened)
    one_turn = llm.token_cost(llm.add_usage(llm.Usage(), _costly("x").usage))
    assert research_loop.MAX_RESEARCH_COST_DOLLARS <= spent < research_loop.MAX_RESEARCH_COST_DOLLARS + one_turn
    assert len(client.requests) < 10


def test_the_spending_ceiling_stops_a_run_at_a_fraction_of_what_it_would_have_cost():
    """Unchecked, a model that never stops bills every one of its turns."""
    turns = [READ, RECORD, *[_costly(f"c{i}") for i in range(research_loop.MAX_TURNS)]]
    result, _, _ = _run(turns)
    unchecked = research_loop.MAX_TURNS * llm.token_cost(llm.add_usage(llm.Usage(), _costly("x").usage))
    assert llm.token_cost(result.usage) < unchecked / 4


def test_ordinary_research_is_nowhere_near_the_ceiling():
    result, _, _ = _run()
    assert research_loop.research_cost(result.usage, tools.Ledger(searches=1, pages=(None,))) < 0.05
    assert result.stopped_by == "finished"


# ── The model may not stop until the floor is covered ────────────

def _aimed(call_id, query, site=""):
    return reply(tool_use(call_id, "web_search", {"query": query, "site": site, "recent_news": False}))


def test_a_model_that_stops_early_is_sent_back_with_what_is_still_open(monkeypatch):
    monkeypatch.setattr(research_floor, "MAX_NUDGES", 2)
    result, client, _ = _run([READ, RECORD, DONE, _aimed("s9", "acme 10-K annual report", "sec.gov"), DONE])
    sent_back = client.requests[3]["messages"][-1]
    assert sent_back["role"] == "user" and client.requests[3]["messages"][-2]["content"] is DONE.content
    told = sent_back["content"]
    assert told.startswith("The research is not finished.")
    assert "- Latest annual filing:" in told and "- Careers site and job postings:" in told
    assert "Budget left: 25 searches, 19 page reads." in told
    second = client.requests[5]["messages"][-1]["content"]
    assert "- Latest annual filing:" not in second  # it was tried in between
    assert result.stopped_by == "finished"
    assert len(client.requests) == 6  # sent back twice, then let go


def test_what_was_never_covered_is_reported_with_the_result(monkeypatch):
    monkeypatch.setattr(research_floor, "MAX_NUDGES", 1)
    result, _, _ = _run([READ, RECORD, DONE, DONE])
    assert "latest annual filing" in result.not_covered and "careers site and job postings" in result.not_covered


def test_a_model_that_covered_the_floor_is_let_go_at_once(monkeypatch):
    monkeypatch.setattr(research_floor, "MAX_NUDGES", 2)
    monkeypatch.setattr(research_floor, "MIN_SEARCHES", 2)
    monkeypatch.setattr(research_floor, "MIN_PAGES_OPENED", 1)
    turns = [
        _aimed("s1", "acme careers network engineer SD-WAN firewall data center AWS ExpressRoute", "myworkdayjobs.com"),
        _aimed("s2", "acme 10-K annual report", "sec.gov"),
        _aimed("s3", "acme acquisition announced"),
        READ, RECORD, DONE,
    ]
    result, client, _ = _run(turns)
    assert len(client.requests) == 6 and result.not_covered == ()


def test_nobody_is_sent_back_once_the_web_is_closed_or_the_searches_are_spent(monkeypatch):
    monkeypatch.setattr(research_floor, "MAX_NUDGES", 2)
    clock = Clock()

    def tick(request_number):
        if request_number == 3:
            clock.now += research_loop.SOFT_DEADLINE_SECONDS

    _, client, _ = _run([READ, RECORD, DONE], clock=clock, on_request=tick)
    assert len(client.requests) == 3
    searches = [
        reply(*[tool_use(f"s{b}-{i}", "web_search", {"query": f"q{b}{i}", "site": "", "recent_news": False}) for i in range(5)])
        for b in range(5)
    ]
    _, client, _ = _run([READ, RECORD, *searches, DONE])
    assert len(client.requests) == 8


def test_the_instructions_name_the_floor_the_code_enforces():
    prefix = prompts.build_research_prefix()
    assert "**Cover the checklist before you stop.**" in prefix
    assert f"at least {research_floor.MIN_SEARCHES} searches" in prefix
    assert f"at least {research_floor.MIN_PAGES_OPENED} pages" in prefix
    assert "`recent_news`" in prefix and "revenue, employees" in prefix
    assert "myworkdayjobs.com" in prefix
