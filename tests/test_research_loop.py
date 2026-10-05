"""The research loop: follow leads, stay inside the budget, never return nothing."""

from datetime import date
from types import SimpleNamespace

import pytest

import llm
import prompts
import research_loop
import research_tools as tools
from errors import UserFacingError
from research_loop import ResearchError
from tests.llm_fakes import FakeClient, reply, text, thinking, timed_out, tool_use, usage
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
        clock=clock or Clock(), today=TODAY,
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
        _run([SEARCH, failure])
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
    result, client, _ = _run([READ, RECORD, timed_out()])
    assert result.stopped_by == "model_failed"
    assert len(result.sources) == 1
    assert result.usage.requests == 2  # the failed request billed nothing


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

@pytest.mark.parametrize("elapsed, timeout, retries", [
    (0, 90, 1),      # early: the usual limit and one retry
    (100, 70, 1),    # both attempts end by the hard deadline
    (120, 60, 1),
    (121, 60, 0),    # late: one attempt, long enough to record what was read
    (239, 60, 0),
])
def test_a_turn_is_given_a_time_limit_that_ends_the_run_on_time(elapsed, timeout, retries):
    assert research_loop.turn_limits(elapsed) == (timeout, retries)


def test_no_turn_can_end_later_than_the_research_ceiling():
    for elapsed in range(0, research_loop.HARD_DEADLINE_SECONDS):
        timeout, retries = research_loop.turn_limits(elapsed)
        assert elapsed + timeout * (retries + 1) <= research_loop.RESEARCH_CEILING_SECONDS


def test_every_research_request_is_sent_with_its_own_time_limit():
    clock = Clock()

    def tick(request_number):
        clock.now += 70  # each request takes 70 seconds

    _, client, _ = _run(clock=clock, on_request=tick)
    assert client.options == [
        {"timeout": 90, "max_retries": 1},
        {"timeout": 85, "max_retries": 1},
        {"timeout": 60, "max_retries": 0},
        {"timeout": 60, "max_retries": 0},
    ]


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


def test_the_spending_ceiling_is_far_below_what_an_unchecked_run_could_cost():
    assert 1.0 <= research_loop.MAX_RESEARCH_COST_DOLLARS <= 2.0


def test_ordinary_research_is_nowhere_near_the_ceiling():
    result, _, _ = _run()
    assert research_loop.research_cost(result.usage, tools.Ledger(searches=1, pages=(None,))) < 0.05
    assert result.stopped_by == "finished"
