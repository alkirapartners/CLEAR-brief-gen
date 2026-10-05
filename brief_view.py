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
        "statsLine": (stats_line or "").replace("**", "").strip(),
        "score": score,
        "scoreRationale": rationale,
        "infra": {
            "cloudPlatforms": cells["cloud_platforms"],
            "onPrem": cells["on_prem"],
            "deployment": cells["deployment"],
            "complexity": cells["complexity"],
        },
        "signals": [
            _BULLET_PREFIX.sub("", line.strip())
            for line in signals_md.splitlines()
            if line.strip()
        ],
        "entryPoints": [
            {
                "heading": point.get("heading", ""),
                "signal": point.get("signal", ""),
                "solution": point.get("solution", ""),
                "proof": point.get("proof", ""),
            }
            for point in extract_entry_points(brief_md)[:MAX_ENTRY_POINTS]
        ],
        "startersMd": extract_section(brief_md, "Conversation Starters"),
        "referencesMd": extract_section(brief_md, "References"),
        "language": language,
        "labels": i18n.labels(language),
        "createdAt": row.get("created_at") or "",
    }
