"""Shape a stored brief row for the API. Section text stays markdown."""

import re

import i18n
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


def to_summary(row: dict) -> dict:
    brief_md = row.get("brief_md") or ""
    return {
        "id": row["id"],
        "company": row.get("company") or "",
        "score": row.get("score") or 0,
        "snippet": extract_exec_snippet(brief_md),
        "language": i18n.detect_language(brief_md),
        "createdAt": row.get("created_at") or "",
    }


def to_detail(row: dict) -> dict:
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
    }
