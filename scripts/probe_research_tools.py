"""Probe the production keys before building research on them.

Run it where ANTHROPIC_API_KEY and TAVILY_API_KEY are set (a server, never
a laptop). It makes a handful of small requests and answers:

  1. Does claude-sonnet-5-5 answer, with the refusal fallback switched on?
  2. Does it call a strict client tool, and return structured JSON?
  3. Does Tavily search work, and does Tavily extract read the careers
     sites and a PDF from the evaluation set?
  4. For the record: does Anthropic's own web fetch read the same careers
     sites? The design chose Tavily because web fetch does not render
     JavaScript and two of these sites need it. This confirms it.

It prints one JSON report ending in a verdict, and never prints a key. The
keys come from the environment, or from a .env file in the repository root.

    python scripts/probe_research_tools.py > probe.json
"""

import json
import os
import sys
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from tavily import TavilyClient

MODEL = "claude-sonnet-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
MIN_READABLE_CHARS = 1500
TAVILY_TIMEOUT_SECONDS = 30
# Careers sites of companies in the evaluation set. The two Workday sites
# render their job lists with JavaScript.
CAREERS_URLS: tuple[str, ...] = (
    "https://careers.hfsinclair.com/",
    "https://oxy.wd5.myworkdayjobs.com/en-US/Corporate",
    "https://kemper.wd5.myworkdayjobs.com/en-US/Kemper_Careers",
    "https://www.jobs-ups.com/",
    "https://jobs.globalpayments.com/",
)
PDF_URL = "https://www.sec.gov/Archives/edgar/data/1090727/000162828026019882/ups2025arsa.pdf"

USE_TAVILY = "tavily"
USE_ANTHROPIC = "anthropic"
BLOCKED = "blocked"


def _error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def check_model(client: Any, with_fallback: bool) -> str:
    """'ok' when the model answers. Tried with and without the refusal fallback."""
    extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if with_fallback else {}
    try:
        reply = client.beta.messages.create(
            model=MODEL, max_tokens=200, messages=[{"role": "user", "content": "Reply with OK."}], **extra,
        )
    except Exception as exc:
        return _error(exc)
    return "ok" if reply.stop_reason in ("end_turn", "max_tokens") else str(reply.stop_reason)


def check_strict_tool(client: Any) -> str:
    tool = {
        "name": "record", "description": "Record one word.", "strict": True,
        "input_schema": {
            "type": "object", "properties": {"word": {"type": "string"}},
            "required": ["word"], "additionalProperties": False,
        },
    }
    try:
        reply = client.beta.messages.create(
            model=MODEL, max_tokens=500, tools=[tool],
            messages=[{"role": "user", "content": "Call the record tool with the word 'probe'."}],
        )
    except Exception as exc:
        return _error(exc)
    called = [block for block in reply.content if block.type == "tool_use"]
    return "ok" if called and called[0].input.get("word") else f"no tool call ({reply.stop_reason})"


def check_structured_output(client: Any) -> str:
    schema = {
        "type": "object", "properties": {"score": {"type": "integer", "enum": [1, 2, 3, 4, 5]}},
        "required": ["score"], "additionalProperties": False,
    }
    try:
        reply = client.beta.messages.create(
            model=MODEL, max_tokens=500,
            output_config={"format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": "Give a score of 3."}],
        )
        text = "".join(block.text for block in reply.content if block.type == "text")
        return "ok" if json.loads(text).get("score") == 3 else f"unexpected: {text[:80]}"
    except Exception as exc:
        return _error(exc)


def anthropic_fetch_chars(client: Any, url: str) -> int | str:
    """Characters of text Anthropic's web fetch returned, or the error it gave."""
    tool = {
        "type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 1,
        "max_content_tokens": 3000, "allowed_callers": ["direct"],
    }
    try:
        reply = client.beta.messages.create(
            model=MODEL, max_tokens=400, tools=[tool],
            messages=[{"role": "user", "content": f"Fetch {url} and reply with its title only."}],
        )
    except Exception as exc:
        return _error(exc)
    for block in reply.content:
        if block.type == "web_fetch_tool_result":
            result = block.content
            if getattr(result, "type", "") != "web_fetch_result":
                return str(getattr(result, "error_code", "error"))
            return len(str(getattr(result.content.source, "data", "") or ""))
    return "no fetch attempted"


def tavily_search_count(web: Any) -> int | str:
    try:
        found = web.search("HF Sinclair network engineer careers", max_results=3, search_depth="advanced")
    except Exception as exc:
        return _error(exc)
    return len(found.get("results") or [])


def tavily_extract_chars(web: Any, url: str) -> int | str:
    try:
        found = web.extract(urls=[url], extract_depth="advanced", timeout=TAVILY_TIMEOUT_SECONDS)
    except Exception as exc:
        return _error(exc)
    results = found.get("results") or []
    return len(str(results[0].get("raw_content") or "")) if results else "not extracted"


def _readable(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= MIN_READABLE_CHARS


def decide(report: dict[str, Any]) -> tuple[str, str]:
    """The verdict and the reason, from a report. Pure, so it can be tested."""
    claude = [report["model"], report["strict_tool"], report["structured_output"]]
    if any(status != "ok" for status in claude):
        return BLOCKED, "Claude checks failed: the model, strict tools or structured output is not usable."
    careers = report["careers"]
    by_anthropic = [url for url, got in careers.items() if _readable(got["anthropic"])]
    by_tavily = [url for url, got in careers.items() if _readable(got["tavily"])]
    if len(by_anthropic) == len(careers):
        return USE_ANTHROPIC, (
            "Anthropic's web fetch read every careers site. The spec's rule then prefers "
            "Anthropic's tools: stop and have the plan revised before building on Tavily."
        )
    tavily_ok = _readable(report["tavily_pdf"]) and isinstance(report["tavily_search"], int) and report["tavily_search"] > 0
    if tavily_ok and len(by_tavily) > len(by_anthropic):
        return USE_TAVILY, (
            f"Tavily read {len(by_tavily)} of {len(careers)} careers sites and the PDF; "
            f"Anthropic's web fetch read {len(by_anthropic)}. Build on Tavily as planned."
        )
    return BLOCKED, "Tavily did not read more of the careers sites than Anthropic's web fetch, or its search or PDF read failed."


def run(client: Any, web: Any) -> dict[str, Any]:
    report: dict[str, Any] = {
        "model": check_model(client, with_fallback=False),
        "refusal_fallback": check_model(client, with_fallback=True),
        "strict_tool": check_strict_tool(client),
        "structured_output": check_structured_output(client),
        "tavily_search": tavily_search_count(web),
        "tavily_pdf": tavily_extract_chars(web, PDF_URL),
        "careers": {
            url: {"tavily": tavily_extract_chars(web, url), "anthropic": anthropic_fetch_chars(client, url)}
            for url in CAREERS_URLS
        },
    }
    report["verdict"], report["reason"] = decide(report)
    return report


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not anthropic_key or not tavily_key:
        print("ANTHROPIC_API_KEY and TAVILY_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)
    report = run(Anthropic(api_key=anthropic_key, timeout=120), TavilyClient(api_key=tavily_key))
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["verdict"] == USE_TAVILY else 2)


if __name__ == "__main__":
    main()
