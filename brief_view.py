"""Shape a stored brief row for the API. Section text stays markdown.

A row holds either a JSON brief document or legacy markdown. Both come out
with every field the current front end reads. A JSON brief also carries the
whole document under ``doc`` for the layout that will replace it.
"""

import re
from typing import Any

import brief_compat
import brief_doc
import i18n
import stored_brief
from briefparse import (
    clean_brief,
    extract_company_header,
    extract_entry_points,
    extract_exec_snippet,
    extract_infra_cells,
    extract_score,
    extract_section,
)

MAX_ENTRY_POINTS = 3
LEGACY_FORMAT = 1
_BULLET_PREFIX = re.compile(r"^[-*]\s+")
# A line that is nothing but dashes divides sections in the stored markdown.
_RULE_LINE = re.compile(r"^\s*-{3,}\s*$")
_EMPHASIS_CHARS = "*_\"' \t"
# The brief ends with a confidentiality marker (*CONFIDENTIAL*), in its own language.
_CONFIDENTIAL_WORDS = frozenset(
    table["confidential"].casefold() for table in i18n.LABELS.values()
)


def _is_chrome(line: str) -> bool:
    """A divider or the confidentiality marker: structure, not content."""
    if _RULE_LINE.match(line):
        return True
    return line.strip(_EMPHASIS_CHARS).casefold() in _CONFIDENTIAL_WORDS


# "October 2026" / "Agosto 2026": one word and a year, once emphasis and brackets are removed.
_DATE_LINE = re.compile(r"^[^\W\d_]+ \d{4}$")


def _stats_line(raw: str) -> str:
    """The company's stats line, or nothing if the header reader picked up the date line.

    A brief written without a stats line has its date line (*[October 2026]*)
    directly under the company heading, which is then read as the stats.
    """
    stats = (raw or "").replace("**", "").strip()
    if _DATE_LINE.match(stats.strip("*_[] \t")):
        return ""
    return stats


def _tidy(text: str) -> str:
    """Section text without the dividers and marker that trail it in the markdown.

    The section readers return everything up to the next heading, which
    includes the rule line that closes a section and, for the last section,
    the confidentiality marker. The page shows that marker itself, from the
    label table.
    """
    return "\n".join(line for line in (text or "").splitlines() if not _is_chrome(line)).strip()


def to_camel(value: Any) -> Any:
    """The same data with snake_case keys turned into camelCase, at every depth."""
    if isinstance(value, dict):
        return {_camel_key(key): to_camel(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_camel(item) for item in value]
    return value


def _camel_key(key: str) -> str:
    head, *rest = key.split("_")
    return head + "".join(part.capitalize() for part in rest)


def to_summary(row: dict) -> dict:
    brief_md = row.get("brief_md") or ""
    doc = brief_doc.load(brief_md)
    # The row is filed under the name that was typed; the brief knows the real one.
    resolved = doc["company"]["name"].strip() if doc else ""
    return {
        "id": row["id"],
        "company": resolved or row.get("company") or "",
        "score": row.get("score") or 0,
        "snippet": brief_compat.snippet(doc) if doc else extract_exec_snippet(brief_md),
        "language": stored_brief.language_of(brief_md),
        "createdAt": row.get("created_at") or "",
    }


def to_detail(row: dict) -> dict:
    doc = brief_doc.load(row.get("brief_md"))
    if doc is not None:
        return _doc_detail(row, doc)
    return _legacy_detail(row)


def _doc_detail(row: dict, doc: brief_doc.BriefDoc) -> dict:
    """A JSON brief: the fields the current page reads, plus the document itself."""
    language = i18n.normalize(doc["language"])
    labels = i18n.labels(language)
    return {
        "id": row["id"],
        "company": doc["company"]["name"].strip() or row.get("company") or "",
        "statsLine": brief_compat.stats_line(doc, labels),
        "score": doc["fit"]["score"],
        "scoreRationale": brief_compat.score_rationale(doc),
        "infra": brief_compat.infra_cells(doc, labels),
        "signals": brief_compat.signals(doc),
        "entryPoints": brief_compat.entry_points(doc)[:MAX_ENTRY_POINTS],
        "startersMd": brief_compat.starters_md(doc, labels),
        "referencesMd": brief_compat.references_md(doc, labels),
        "language": language,
        "labels": labels,
        "createdAt": row.get("created_at") or "",
        "format": brief_doc.FORMAT_VERSION,
        "doc": to_camel(doc),
    }


def _legacy_detail(row: dict) -> dict:
    brief_md = clean_brief(row.get("brief_md") or "")
    score, rationale = extract_score(brief_md)
    company, stats_line = extract_company_header(brief_md)
    cells = extract_infra_cells(brief_md)
    signals_md = (
        extract_section(brief_md, "Signals & Timing")
        or extract_section(brief_md, "Signals and Timing")
    )
    language = i18n.detect_language(brief_md)
    return {
        "id": row["id"],
        "company": company or row.get("company") or "",
        "statsLine": _stats_line(stats_line),
        "score": score,
        "scoreRationale": _tidy(rationale),
        "infra": {
            "cloudPlatforms": _tidy(cells["cloud_platforms"]),
            "onPrem": _tidy(cells["on_prem"]),
            "deployment": _tidy(cells["deployment"]),
            "complexity": _tidy(cells["complexity"]),
        },
        "signals": [
            _BULLET_PREFIX.sub("", line.strip())
            for line in _tidy(signals_md).splitlines()
            if line.strip()
        ],
        "entryPoints": [
            {
                "heading": _tidy(point.get("heading", "")),
                "signal": _tidy(point.get("signal", "")),
                "solution": _tidy(point.get("solution", "")),
                "proof": _tidy(point.get("proof", "")),
            }
            for point in extract_entry_points(brief_md)[:MAX_ENTRY_POINTS]
        ],
        "startersMd": _tidy(extract_section(brief_md, "Conversation Starters")),
        "referencesMd": _tidy(extract_section(brief_md, "References")),
        "language": language,
        "labels": i18n.labels(language),
        "createdAt": row.get("created_at") or "",
        "format": LEGACY_FORMAT,
        "doc": None,
    }
