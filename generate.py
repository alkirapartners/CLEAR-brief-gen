"""Generate a brief: research the company, then judge the fit and write it.

Research follows leads on the web inside a budget (research_loop.py). One
streamed call then scores the fit and writes the brief as a JSON document
from the recorded evidence only. The rules the model is asked to follow
are enforced again in code (brief_rules.py) before anything is stored.
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from tavily import TavilyClient

import brief_doc
import brief_rules
import evidence
import i18n
import llm
import prompts
import research_loop
from research_tools import WebClient

logger = logging.getLogger(__name__)

MAX_TOKENS = 16000
EFFORT = "medium"
# The writer streams, so the client's time limit bounds a silence on the
# stream, not the whole reply. The deadline bounds the whole reply.
WRITER_STALL_SECONDS = 120
WRITER_RETRIES = 1
WRITER_DEADLINE_SECONDS = 180
ERROR_PREFIX_CHARS = 200
ERROR_DETAIL_CHARS = 500

StatusCallback = Callable[[str], None]
Clock = Callable[[], float]


@dataclass(frozen=True)
class Generation:
    """A finished brief with what it took to make."""

    stored: str
    doc: brief_doc.BriefDoc
    research: research_loop.ResearchResult
    usage: llm.Usage
    seconds: float
    cost: float


def _starts_text(event: Any) -> bool:
    """True for the stream event that opens the reply's text, after any thinking."""
    block = getattr(event, "content_block", None)
    return getattr(event, "type", "") == "content_block_start" and getattr(block, "type", "") == "text"


def _write(
    client: Any, company: str, found: research_loop.ResearchResult,
    today: date, language: str, status_callback: StatusCallback, clock: Clock,
) -> Any:
    """The judge-and-write call. Reports "analyze" while it thinks, "compose" once it writes."""
    status_callback("analyze")
    fence = evidence.new_fence()
    content = prompts.build_writer_message(
        company, fence, evidence.format_payload(found.sources, fence), today, language,
        research_loop.EARLY_STOPS.get(found.stopped_by, ""), "; ".join(found.not_covered),
    )
    composing, started = False, clock()
    bounded = client.with_options(timeout=WRITER_STALL_SECONDS, max_retries=WRITER_RETRIES)
    with bounded.beta.messages.stream(
        **llm.request_settings(prompts.build_writer_prefix(), MAX_TOKENS),
        output_config={
            "effort": EFFORT,
            "format": {"type": "json_schema", "schema": brief_doc.WRITER_SCHEMA},
        },
        messages=[{"role": "user", "content": content}],
    ) as stream:
        for event in stream:
            if clock() - started > WRITER_DEADLINE_SECONDS:
                # Leaving the block closes the stream, so nothing more is billed.
                raise RuntimeError(
                    f"Writing the brief for {company!r} ran past {WRITER_DEADLINE_SECONDS} seconds."
                )
            if not composing and _starts_text(event):
                composing = True
                status_callback("compose")
        message = stream.get_final_message()
    if not composing:
        status_callback("compose")
    return message


def _reply_text(company: str, message: Any) -> str:
    """The reply's text, or an error when there is no usable reply."""
    declined = llm.refusal(message)
    if declined is not None:
        raise RuntimeError(f"The model declined to write the brief for {company!r} ({declined}).")
    text = "".join(block.text for block in message.content if block.type == "text")
    if message.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Brief generation for {company!r} was truncated "
            f"(stop_reason=max_tokens, output_tokens={message.usage.output_tokens})."
        )
    if not text.strip():
        raise RuntimeError(
            f"Brief generation for {company!r} returned empty output "
            f"(stop_reason={message.stop_reason}, output_tokens={message.usage.output_tokens})."
        )
    return text


def _document(
    company: str, message: Any, found: research_loop.ResearchResult, today: date, language: str,
) -> brief_doc.BriefDoc:
    """Validate the reply against the schema, then apply the rules the code enforces."""
    text = _reply_text(company, message)
    try:
        output = brief_doc.parse_writer_output(text)
    except brief_doc.BriefFormatError as exc:
        raise RuntimeError(
            f"Brief generation for {company!r} did not follow the output contract "
            f"(stop_reason={message.stop_reason}, output starts with: "
            f"{text.lstrip()[:ERROR_PREFIX_CHARS]!r}): {str(exc)[:ERROR_DETAIL_CHARS]}"
        ) from exc
    note: brief_doc.ResearchNote = {
        "searches": found.searches,
        "pages": found.pages_opened,
        "seconds": round(found.seconds),
        "stopped_by": found.stopped_by,
    }
    return brief_rules.finalize(output, found.sources, i18n.normalize(language), today, note)


def generate_detailed(
    api_key: str,
    tavily_key: str,
    company: str,
    status_callback: StatusCallback,
    timeout_seconds: float = llm.REQUEST_TIMEOUT_SECONDS,
    language: str = "en",
    client: Any = None,
    web: WebClient | None = None,
    today: date | None = None,
    clock: Clock = time.monotonic,
) -> Generation:
    """Research the company and write its brief. Returns the brief with its cost.

    ``language`` sets the prose language of the brief. Research always runs
    in English. ``client``, ``web`` and ``clock`` are for tests; production
    builds the first two from the keys.
    """
    started = clock()
    status_callback("init")
    if web is None and not tavily_key:
        raise research_loop.ResearchError("TAVILY_API_KEY is not configured.")
    client = client or llm.make_client(api_key, timeout_seconds)
    web = web or TavilyClient(api_key=tavily_key)
    day = today or date.today()

    found = research_loop.research(company, status_callback, client, web, clock=clock, today=day)
    message = _write(client, company, found, day, language, status_callback, clock)
    doc = _document(company, message, found, day, language)

    usage = llm.combine(found.usage, llm.add_usage(llm.Usage(), message.usage))
    seconds = clock() - started
    cost = llm.token_cost(usage) + llm.web_cost(found.searches, found.pages_opened)
    logger.info(
        "brief=%s lang=%s score=%d angles=%d requests=%d cache_read=%d cache_write=%d "
        "input=%d output=%d seconds=%.0f cost=%.2f",
        company, language, doc["fit"]["score"], len(doc["angles"]), usage.requests,
        usage.cache_read_tokens, usage.cache_write_5m_tokens + usage.cache_write_1h_tokens,
        usage.input_tokens, usage.output_tokens, seconds, cost,
    )
    status_callback("done")
    return Generation(brief_doc.dump(doc), doc, found, usage, seconds, cost)


def generate_brief(
    api_key: str,
    tavily_key: str,
    company: str,
    status_callback: StatusCallback,
    timeout_seconds: float = llm.REQUEST_TIMEOUT_SECONDS,
    language: str = "en",
) -> str:
    """The brief as the text to store. This is the function the API calls."""
    return generate_detailed(
        api_key, tavily_key, company, status_callback, timeout_seconds, language,
    ).stored
