"""Research a company by letting the model follow leads, inside a budget.

One conversation with Claude. Each turn the model asks to search, to open
pages or to record evidence. ``research_tools`` runs those calls and
enforces the search and page budgets. This module enforces the clock and
decides when research is over. The result is the evidence recorded from
pages that were opened. With none, research has failed and no brief is
written. A failure late in a run ends the research but keeps what was
already gathered, so a brief that was nearly paid for is still written.
"""

import logging
import time
from dataclasses import dataclass, replace
from datetime import date
from typing import Any, Callable

import anthropic

import llm
import prompts
import research_floor
from errors import UserFacingError
from evidence import Source, build_sources, new_fence
from research_tools import (
    MAX_PAGES, MAX_SEARCHES, TAVILY_TIMEOUT_SECONDS, TOOLS, Ledger, ToolCall, WebClient,
    budget_line, open_items, run_calls,
)

logger = logging.getLogger(__name__)

MAX_TOKENS = 16000
EFFORT = "medium"
# After the soft deadline no search or page read is started: the model is
# told to record what it has. After the hard deadline no model turn is
# started: the brief is written with what was gathered.
SOFT_DEADLINE_SECONDS = 200
HARD_DEADLINE_SECONDS = 240
BUDGET_MINUTES = HARD_DEADLINE_SECONDS // 60
# A web call started just before the soft deadline is over by this point,
# which leaves a model turn before the hard deadline to record what it returned.
WEB_DEADLINE_SECONDS = SOFT_DEADLINE_SECONDS + TAVILY_TIMEOUT_SECONDS
# One request to the model gets this long at most, and never longer than
# the time left before the ceiling. A failed request is tried once more when
# there is still room for an attempt. The SDK's own retries are off, because
# they sleep for as long as a Retry-After header asks.
TURN_TIMEOUT_SECONDS = 90
TURN_RETRIES = 1
RETRY_PAUSE_SECONDS = llm.RETRY_PAUSE_SECONDS
MIN_ATTEMPT_SECONDS = 20
LAST_TURN_TIMEOUT_SECONDS = 60
# Research cannot run longer than this, whatever the model or the web does:
# no turn starts after the hard deadline, and no attempt may outlast this.
RESEARCH_CEILING_SECONDS = HARD_DEADLINE_SECONDS + LAST_TURN_TIMEOUT_SECONDS
MAX_TURNS = 40
MAX_FAILURES_IN_A_ROW = 5
# What one brief's research may cost, tokens and web calls together. A normal
# run costs well under a dollar. Checked before every turn, so a run can pass
# it by one turn at most; the writer then works with what was gathered.
MAX_RESEARCH_COST_DOLLARS = 1.50

FINISHED = "finished"
BUDGET_SPENT = "budget"
DEADLINE = "deadline"
TURN_CAP = "turn_cap"
TRUNCATED = "truncated"
WEB_FAILED = "web_failed"
MODEL_FAILED = "model_failed"
COST_CAP = "cost_cap"
# Stops the writer is told about, with the words it is told in.
EARLY_STOPS: dict[str, str] = {
    DEADLINE: "its time ran out",
    TURN_CAP: "it reached its turn limit",
    TRUNCATED: "a reply was cut off",
    WEB_FAILED: "the web search service kept failing",
    MODEL_FAILED: "a request to the model failed",
    COST_CAP: "it reached its spending limit",
}
# What the log says when one of these stops leaves nothing to cite.
_FAILURES: dict[str, str] = {
    WEB_FAILED: "The web search service kept failing while researching {company!r}.",
    MODEL_FAILED: "A request to the model failed while researching {company!r}, before anything citable was gathered.",
}

Clock = Callable[[], float]


NOTHING_CITABLE_MESSAGE = (
    "The research found nothing it could cite for that name. Check the spelling, or add "
    "what sets the company apart, such as its country or its ticker, then try again. "
    "This attempt counts toward today's limit."
)


class ResearchError(RuntimeError):
    """Research failed. A brief is never written without cited evidence."""


class NothingCitable(UserFacingError, ResearchError):
    """Research ran, and no page it opened gave a usable fact.

    The message is safe to show a partner. ``detail`` is for the log.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(NOTHING_CITABLE_MESSAGE)
        self.detail = detail


@dataclass(frozen=True)
class ResearchResult:
    sources: tuple[Source, ...]
    searches: int
    page_reads: int
    pages_opened: int
    seconds: float
    stopped_by: str
    usage: llm.Usage
    # What the research floor asked for and the run never got to, by name.
    not_covered: tuple[str, ...] = ()
    facts_kept: int = 0
    # Facts recorded without an opened page behind them, or without a quote on it.
    facts_refused: int = 0


@dataclass(frozen=True)
class _Run:
    """Where a research run stands between turns."""

    messages: tuple[dict[str, Any], ...]
    ledger: Ledger = Ledger()
    usage: llm.Usage = llm.Usage()
    nudges: int = 0


def research_cost(usage: llm.Usage, ledger: Ledger) -> float:
    """Estimated US dollars spent on this research so far."""
    return llm.token_cost(usage) + llm.web_cost(ledger.searches, len(ledger.pages))


def _stop_before_turn(elapsed: float, usage: llm.Usage, ledger: Ledger) -> str | None:
    """Why no further model turn may start, or None when one may."""
    if elapsed >= HARD_DEADLINE_SECONDS:
        return DEADLINE
    if research_cost(usage, ledger) >= MAX_RESEARCH_COST_DOLLARS:
        return COST_CAP
    return None


def attempt_timeout(elapsed: float) -> float | None:
    """Seconds one request may take so it ends by the ceiling, or None when there is no room."""
    room = RESEARCH_CEILING_SECONDS - elapsed
    return min(TURN_TIMEOUT_SECONDS, room) if room >= MIN_ATTEMPT_SECONDS else None


def _send(client: Any, messages: list[dict[str, Any]], timeout: float) -> Any:
    return client.with_options(timeout=timeout, max_retries=0).beta.messages.create(
        **llm.request_settings(prompts.build_research_prefix(), MAX_TOKENS),
        output_config={"effort": EFFORT},
        tools=list(TOOLS),
        # Caches the growing conversation, so each turn re-reads it cheaply.
        cache_control={"type": "ephemeral"},
        messages=messages,
    )


def _ask(session: "_Session", messages: list[dict[str, Any]]) -> Any:
    """One model turn, tried again once if it fails and the ceiling leaves room."""
    failure: anthropic.APIError | None = None
    for attempt in range(TURN_RETRIES + 1):
        if attempt:
            session.sleep(RETRY_PAUSE_SECONDS)
        timeout = attempt_timeout(session.elapsed())
        if timeout is None:
            break
        try:
            return _send(session.client, messages, timeout)
        except anthropic.APIError as exc:
            failure = exc
            if not llm.is_retryable(exc):
                break
    assert failure is not None  # a turn only starts with room for its first attempt
    raise failure


def _tool_calls(response: Any) -> list[ToolCall]:
    return [
        ToolCall(block.id, block.name, block.input)
        for block in response.content
        if block.type == "tool_use"
    ]


def _ending(response: Any, calls: list[ToolCall], company: str) -> str | None:
    """Why research ends with this reply, or None when it continues."""
    declined = llm.refusal(response)
    if declined is not None:
        raise ResearchError(f"The model declined to research {company!r} ({declined}).")
    if response.stop_reason == "max_tokens":
        return TRUNCATED  # its tool calls may be cut short, so none is run
    if response.stop_reason != "tool_use" or not calls:
        return FINISHED
    return None


def _nothing_citable(company: str, ledger: Ledger, reason: str) -> ResearchError:
    """The error for a run that ended with no source: a failed service, or an unknown name."""
    failure = _FAILURES.get(reason)
    if failure is not None:
        return ResearchError(failure.format(company=company))
    detail = (
        f"Research found nothing citable for {company!r} (searches={ledger.searches}, "
        f"pages opened={len(ledger.pages)}, stopped by {reason})."
    )
    logger.warning(detail)
    return NothingCitable(detail)


def _result(
    company: str, run: _Run, seconds: float, stopped_by: str, cause: BaseException | None = None,
) -> ResearchResult:
    """What research gathered, or an error when there is nothing to cite."""
    ledger = run.ledger
    sources = build_sources(ledger.evidence, ledger.pages)
    spent = ledger.searches >= MAX_SEARCHES or ledger.page_reads >= MAX_PAGES
    reason = BUDGET_SPENT if stopped_by == FINISHED and spent else stopped_by
    # Depth is a count, not a topic: the writer is told what was never looked for.
    not_covered = research_floor.names(
        [item for item in open_items(ledger) if item != research_floor.DEPTH]
    )
    logger.info(
        "research company=%s searches=%d reads=%d opened=%d sources=%d seconds=%.0f "
        "stopped_by=%s nudges=%d facts_kept=%d facts_refused=%d not_covered=%s",
        company, ledger.searches, ledger.page_reads, len(ledger.pages), len(sources), seconds,
        reason, run.nudges, len(ledger.evidence), ledger.facts_refused, "; ".join(not_covered) or "-",
    )
    if not sources:
        raise _nothing_citable(company, ledger, reason) from cause
    return ResearchResult(
        sources, ledger.searches, ledger.page_reads, len(ledger.pages), seconds, reason,
        run.usage, not_covered, len(ledger.evidence), ledger.facts_refused,
    )


def _nudge(run: _Run, elapsed: float) -> str | None:
    """What to tell a model that says it is done, or None when it may stop.

    It is sent back while the floor has open items, it has been sent back
    fewer than the allowed times, and there is still time and search budget
    to act on what it is told.
    """
    still_open = open_items(run.ledger)
    if not still_open or run.nudges >= research_floor.MAX_NUDGES:
        return None
    if elapsed >= SOFT_DEADLINE_SECONDS or run.ledger.searches >= MAX_SEARCHES:
        return None
    todo = research_floor.instructions(still_open, run.ledger.searches, len(run.ledger.pages))
    return prompts.build_floor_nudge(todo, budget_line(run.ledger))


def _after(run: _Run, response: Any, reply: Any) -> tuple[dict[str, Any], ...]:
    """The conversation with the model's turn and the answer to it added."""
    return (
        *run.messages,
        {"role": "assistant", "content": response.content},
        {"role": "user", "content": reply},
    )


@dataclass(frozen=True)
class _Session:
    """What every turn of one research run shares."""

    company: str
    client: Any
    web: WebClient
    fence: str
    started: float
    clock: Clock
    sleep: Callable[[float], None]

    def elapsed(self) -> float:
        return self.clock() - self.started


Step = tuple[_Run, str | None, BaseException | None]


def _turn(run: _Run, session: _Session) -> Step:
    """One model turn and its tool calls: the new state, and why research ends if it does."""
    elapsed = session.elapsed()
    halted = _stop_before_turn(elapsed, run.usage, run.ledger)
    if halted is not None:
        return run, halted, None
    try:
        response = _ask(session, list(run.messages))
    except anthropic.APIError as exc:
        logger.warning("research request failed for %s: %s: %s", session.company, type(exc).__name__, exc)
        return run, MODEL_FAILED, exc
    run = replace(run, usage=llm.add_usage(run.usage, response.usage))
    calls = _tool_calls(response)
    ending = _ending(response, calls, session.company)
    if ending == FINISHED:
        nudge = _nudge(run, session.elapsed())
        if nudge is None:
            return run, FINISHED, None
        return replace(run, messages=_after(run, response, nudge), nudges=run.nudges + 1), None, None
    if ending is not None:
        return run, ending, None
    results, ledger = run_calls(
        calls, run.ledger, session.web, session.fence,
        accepting=session.elapsed() < SOFT_DEADLINE_SECONDS,
        time_left=lambda: session.started + WEB_DEADLINE_SECONDS - session.clock(),
    )
    run = replace(run, ledger=ledger, messages=_after(run, response, results))
    return run, WEB_FAILED if ledger.failures_in_a_row >= MAX_FAILURES_IN_A_ROW else None, None


def research(
    company: str,
    status_callback: Callable[[str], None],
    client: Any,
    web: WebClient,
    clock: Clock = time.monotonic,
    today: date | None = None,
    sleep: Callable[[float], None] | None = None,
) -> ResearchResult:
    """Follow leads on the web until they run out or the budget does.

    ``client`` is an Anthropic client and ``web`` a Tavily client. Raises
    ``ResearchError`` when the model declined or nothing citable was found.
    A web service or a model request that fails after something citable was
    gathered ends the research early instead. A model that says it is done
    before the research floor is covered is sent back to it.
    """
    status_callback("research")
    session = _Session(company, client, web, new_fence(), clock(), clock, sleep or time.sleep)
    opening = prompts.build_research_message(
        company, session.fence, today or date.today(), MAX_SEARCHES, MAX_PAGES, BUDGET_MINUTES,
    )
    run = _Run(messages=({"role": "user", "content": opening},))
    stopped_by, cause = TURN_CAP, None
    for _turn_number in range(MAX_TURNS):
        run, ending, cause = _turn(run, session)
        if ending is not None:
            stopped_by = ending
            break
    return _result(company, run, session.elapsed(), stopped_by, cause)
