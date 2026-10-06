"""
Generate an Alkira opportunity brief for any company, from the terminal.

Usage:
    python generate_brief.py "Mary Kay" --verbose
    python generate_brief.py "Walmart" --output walmart.md
    python generate_brief.py "Cemex" --language es
    python generate_brief.py "HF Sinclair" --save-dir out/

--save-dir writes the stored JSON, readable text and the PDF for the brief,
and adds one line of time and cost to metrics.jsonl in that directory.
"""

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import asdict
from datetime import datetime

from dotenv import load_dotenv

import brief_text
import generate
import i18n
import llm
import pdf

METRICS_FILE = "metrics.jsonl"
VERBOSE_LOGGERS: tuple[str, ...] = ("research_loop", "research_tools", "generate", "brief_rules")


def _slug(company: str) -> str:
    """A file name from a company name: lower-case words joined by hyphens."""
    return re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or "brief"


def metrics(company: str, made: generate.Generation) -> dict:
    """What one brief took, as one flat record."""
    return {
        "company": company,
        "resolved": made.doc["company"]["name"],
        "score": made.doc["fit"]["score"],
        "angles": len(made.doc["angles"]),
        "seconds": round(made.seconds),
        "searches": made.research.searches,
        "page_reads": made.research.page_reads,
        "pages_opened": made.research.pages_opened,
        "sources": len(made.research.sources),
        "stopped_by": made.research.stopped_by,
        "not_covered": list(made.research.not_covered),
        "facts_kept": made.research.facts_kept,
        "facts_refused": made.research.facts_refused,
        **asdict(made.usage),
        "tavily_credits": round(llm.web_credits(made.research.searches, made.research.pages_opened), 1),
        "cost_usd": round(made.cost, 3),
    }


def save_bundle(directory: str, company: str, made: generate.Generation) -> list[str]:
    """Write the JSON, the readable text and the PDF. Returns the paths written."""
    os.makedirs(directory, exist_ok=True)
    base = os.path.join(directory, _slug(company))
    with open(f"{base}.json", "w", encoding="utf-8") as handle:
        handle.write(made.stored)
    with open(f"{base}.md", "w", encoding="utf-8") as handle:
        handle.write(brief_text.render(made.doc))
    rendered = pdf.generate_brief_pdf(
        made.stored, made.doc["company"]["name"], made.doc["fit"]["score"],
        datetime.now(), made.doc["language"],
    )
    with open(f"{base}.pdf", "wb") as handle:
        handle.write(rendered)
    with open(os.path.join(directory, METRICS_FILE), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(metrics(company, made)) + "\n")
    return [f"{base}.json", f"{base}.md", f"{base}.pdf"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an Alkira opportunity brief for a target company."
    )
    parser.add_argument("company", help="Company name (e.g., 'Mary Kay')")
    parser.add_argument("--output", "-o", help="Save the readable text to this file")
    parser.add_argument("--save-dir", help="Save JSON, text, PDF and metrics in this directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show phase progress")
    parser.add_argument(
        "--language", "-l", default=i18n.DEFAULT_LANGUAGE, choices=sorted(i18n.LABELS),
        help="Language of the brief prose (default: en)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    args = _parser().parse_args(argv)

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key or not tavily_key:
        print("Error: ANTHROPIC_API_KEY and TAVILY_API_KEY must be set.")
        sys.exit(1)

    if args.verbose:
        # Show what research kept and refused. Only this app's own loggers are turned up.
        logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")
        for name in VERBOSE_LOGGERS:
            logging.getLogger(name).setLevel(logging.INFO)

    def status(phase: str) -> None:
        if args.verbose:
            print(f"  [{phase}]", flush=True)

    made = generate.generate_detailed(
        api_key, tavily_key, args.company, status, language=args.language
    )
    readable = brief_text.render(made.doc)
    print(readable)
    print(json.dumps(metrics(args.company, made)))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(readable)
        print(f"\nBrief saved to: {args.output}")
    if args.save_dir:
        for path in save_bundle(args.save_dir, args.company, made):
            print(f"Saved: {path}")


if __name__ == "__main__":
    main()
