"""Research a company by letting the model follow leads, inside a budget.

One conversation with Claude. Each turn the model asks to search, to open
pages or to record evidence. ``research_tools`` runs those calls and
enforces the search and page budgets. This module enforces the clock and
decides when research is over. The result is the evidence recorded from
pages that were opened. With none, research has failed and no brief is
written.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

import llm
import prompts
from evidence import Source, build_sources, new_fence
from research_tools import (
    MAX_PAGES, MAX_SEARCHES, TOOLS, Ledger, ToolCall, WebClient, run_calls,
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
MAX_TURNS = 40
MAX_FAILURES_IN_A_ROW = 5

FINISHED = "finished"
BUDGET_SPENT = "budget"
DEADLINE = "deadline"
TURN_CAP = "turn_cap"
TRUNCATED = "truncated"
# Stops the writer is told about, with the words it is told in.
EARLY_STOPS: dict[str, str] = {
    DEADLINE: "its time ran out",
    TURN_CAP: "it reached its turn limit",
    TRUNCATED: "a reply was cut off",
}

Clock = Callable[[], float]


class ResearchError(RuntimeError):
    """Research failed. A brief is never written without cited evidence."""


@dataclass(frozen=True)
class ResearchResult:
    sources: tuple[Source, ...]
    searches: int
    page_reads: int
    pages_opened: int
    seconds: float
    stopped_by: str
    usage: llm.Usage


def _ask(client: Any, messages: list[dict[str, Any]]) -> Any:
    return client.beta.messages.create(
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


def _result(
    company: str, ledger: Ledger, usage: llm.Usage, seconds: float, stopped_by: str,
) -> ResearchResult:
    sources = build_sources(ledger.evidence, ledger.pages)
    spent = ledger.searches >= MAX_SEARCHES or ledger.page_reads >= MAX_PAGES
    reason = BUDGET_SPENT if stopped_by == FINISHED and spent else stopped_by
    logger.info(
        "research company=%s searches=%d reads=%d opened=%d sources=%d seconds=%.0f stopped_by=%s",
        company, ledger.searches, ledger.page_reads, len(ledger.pages), len(sources), seconds, reason,
    )
    if not sources:
        raise ResearchError(
            f"Research found nothing citable for {company!r} (searches={ledger.searches}, "
            f"pages opened={len(ledger.pages)}, stopped by {reason})."
        )
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
    ``ResearchError`` when nothing citable was found, the model declined,
    or the web service keeps failing.
    """
    status_callback("research")
    fence, started = new_fence(), clock()
    opening = prompts.build_research_message(
        company, fence, today or date.today(), MAX_SEARCHES, MAX_PAGES, BUDGET_MINUTES,
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": opening}]
    ledger, usage, stopped_by = Ledger(), llm.Usage(), TURN_CAP
    for _turn in range(MAX_TURNS):
        if clock() - started >= HARD_DEADLINE_SECONDS:
            stopped_by = DEADLINE
            break
        response = _ask(client, messages)
        usage = llm.add_usage(usage, response.usage)
        calls = _tool_calls(response)
        ending = _ending(response, calls, company)
        if ending is not None:
            stopped_by = ending
            break
        accepting = clock() - started < SOFT_DEADLINE_SECONDS
        results, ledger = run_calls(calls, ledger, web, fence, accepting)
        if ledger.failures_in_a_row >= MAX_FAILURES_IN_A_ROW:
            raise ResearchError(f"The web search service kept failing while researching {company!r}.")
        messages = [
            *messages,
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": results},
        ]
    return _result(company, ledger, usage, clock() - started, stopped_by)
