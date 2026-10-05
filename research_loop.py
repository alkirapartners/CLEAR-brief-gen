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
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import anthropic

import llm
import prompts
from errors import UserFacingError
from evidence import Source, build_sources, new_fence
from research_tools import (
    MAX_PAGES, MAX_SEARCHES, TAVILY_TIMEOUT_SECONDS, TOOLS, Ledger, ToolCall, WebClient, run_calls,
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
# One request to the model. Early in a run a stalled request is retried once,
# and both attempts end by the hard deadline. Late in a run there is a single
# attempt, long enough to record what was just read.
TURN_TIMEOUT_SECONDS = 90
TURN_RETRIES = 1
LAST_TURN_TIMEOUT_SECONDS = 60
# Research cannot run longer than this, whatever the model or the web does.
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


def turn_limits(elapsed: float) -> tuple[float, int]:
    """Seconds per attempt, and retries, for a model turn that starts now."""
    remaining = HARD_DEADLINE_SECONDS - elapsed
    attempts = TURN_RETRIES + 1
    if remaining >= attempts * LAST_TURN_TIMEOUT_SECONDS:
        return min(TURN_TIMEOUT_SECONDS, remaining / attempts), TURN_RETRIES
    return LAST_TURN_TIMEOUT_SECONDS, 0


def _ask(client: Any, messages: list[dict[str, Any]], elapsed: float) -> Any:
    timeout, retries = turn_limits(elapsed)
    return client.with_options(timeout=timeout, max_retries=retries).beta.messages.create(
        **llm.request_settings(prompts.build_research_prefix(), MAX_TOKENS),
        output_config={"effort": EFFORT},
        tools=list(TOOLS),
        # Caches the growing conversation, so each turn re-reads it cheaply.
        cache_control={"type": "ephemeral"},
        messages=messages,
    )


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
    company: str, ledger: Ledger, usage: llm.Usage, seconds: float, stopped_by: str,
    cause: BaseException | None = None,
) -> ResearchResult:
    """What research gathered, or an error when there is nothing to cite."""
    sources = build_sources(ledger.evidence, ledger.pages)
    spent = ledger.searches >= MAX_SEARCHES or ledger.page_reads >= MAX_PAGES
    reason = BUDGET_SPENT if stopped_by == FINISHED and spent else stopped_by
    logger.info(
        "research company=%s searches=%d reads=%d opened=%d sources=%d seconds=%.0f stopped_by=%s",
        company, ledger.searches, ledger.page_reads, len(ledger.pages), len(sources), seconds, reason,
    )
    if not sources:
        raise _nothing_citable(company, ledger, reason) from cause
    return ResearchResult(
        sources, ledger.searches, ledger.page_reads, len(ledger.pages), seconds, reason, usage,
    )


def research(
    company: str,
    status_callback: Callable[[str], None],
    client: Any,
    web: WebClient,
    clock: Clock = time.monotonic,
    today: date | None = None,
) -> ResearchResult:
    """Follow leads on the web until they run out or the budget does.

    ``client`` is an Anthropic client and ``web`` a Tavily client. Raises
    ``ResearchError`` when the model declined or nothing citable was found.
    A web service or a model request that fails after something citable was
    gathered ends the research early instead.
    """
    status_callback("research")
    fence, started = new_fence(), clock()
    opening = prompts.build_research_message(
        company, fence, today or date.today(), MAX_SEARCHES, MAX_PAGES, BUDGET_MINUTES,
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": opening}]
    ledger, usage, stopped_by = Ledger(), llm.Usage(), TURN_CAP
    cause: BaseException | None = None
    for _turn in range(MAX_TURNS):
        elapsed = clock() - started
        halted = _stop_before_turn(elapsed, usage, ledger)
        if halted is not None:
            stopped_by = halted
            break
        try:
            response = _ask(client, messages, elapsed)
        except anthropic.APIError as exc:
            logger.warning("research request failed for %s: %s: %s", company, type(exc).__name__, exc)
            stopped_by, cause = MODEL_FAILED, exc
            break
        usage = llm.add_usage(usage, response.usage)
        calls = _tool_calls(response)
        ending = _ending(response, calls, company)
        if ending is not None:
            stopped_by = ending
            break
        accepting = clock() - started < SOFT_DEADLINE_SECONDS
        results, ledger = run_calls(
            calls, ledger, web, fence, accepting,
            time_left=lambda: started + WEB_DEADLINE_SECONDS - clock(),
        )
        if ledger.failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
            stopped_by = WEB_FAILED
            break
        messages = [
            *messages,
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": results},
        ]
    return _result(company, ledger, usage, clock() - started, stopped_by, cause)
