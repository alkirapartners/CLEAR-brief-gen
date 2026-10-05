"""Pure parsers for brief markdown, plus the company-name cleaner.

No Streamlit and no I/O: the API, the PDF renderer and the legacy Streamlit
page all import from here. The markdown headings these functions match are
English in every output language (see i18n.py).
"""

import re
from typing import TypedDict


# Matches Account Radar's own cap on an account name.
MAX_COMPANY_PREFILL_CHARS = 100


def clean_company_prefill(raw: str | None) -> str:
    """Turn a ``?company=`` value into text safe to drop in the search box.

    The value comes from a URL anyone can craft, so control characters and
    line breaks are flattened and an over-long value is ignored outright.
    Returns "" when there is nothing usable.
    """
    if not raw:
        return ""
    printable = "".join(ch if ch.isprintable() else " " for ch in raw)
    name = " ".join(printable.split())
    if len(name) > MAX_COMPANY_PREFILL_CHARS:
        return ""
    return name


# ── Brief Parsing ────────────────────────────────────────────────

def clean_brief(raw: str) -> str:
    markers = ["# ALKIRA OPPORTUNITY BRIEF", "ALKIRA OPPORTUNITY BRIEF"]
    for marker in markers:
        idx = raw.find(marker)
        if idx != -1:
            return raw[idx:]
    return raw


def extract_score(brief: str) -> tuple[int, str]:
    match = re.search(r"\*?\*?Alkira Fit Score:\s*(\d)\s*/\s*5\*?\*?", brief)
    score = int(match.group(1)) if match else 0
    reasoning = ""
    if match:
        after = brief[match.end():].lstrip("* \n")
        lines = after.split("\n")
        reason_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                if reason_lines:
                    break
                continue
            if stripped.startswith("#") or stripped.startswith("---"):
                break
            reason_lines.append(stripped)
        reasoning = " ".join(reason_lines)
    return score, reasoning


def extract_company_header(brief: str) -> tuple[str, str]:
    """Extract company name and stats line from the brief."""
    lines = brief.split("\n")
    company = ""
    stats_lines = []
    capturing_stats = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") and "OPPORTUNITY" not in stripped.upper():
            company = stripped.lstrip("# ").strip()
            capturing_stats = True
            continue
        if capturing_stats and stripped:
            # Stop at score line, next heading, or blank after stats
            if "Alkira Fit Score" in stripped or stripped.startswith("#"):
                break
            stats_lines.append(stripped)
        elif capturing_stats and not stripped and stats_lines:
            break

    raw_stats = " ".join(stats_lines)
    # Strip all markdown bold markers
    clean_stats = raw_stats.replace("**", "")
    return company, clean_stats


def extract_section(brief: str, heading: str) -> str:
    """Find a section by heading and return its body.

    The heading may be written as ``## Heading`` / ``### Heading`` (the
    contract we mandate in prompts.py) or, tolerating a known production
    failure mode, as a **bold** line containing only that heading text. A
    bold *sub-label* inside a section body (e.g. ``**Cloud Platforms:**
    text``) is never mistaken for a heading, because it has content after
    the closing ``**`` on the same line — only a bold span that is the
    ENTIRE line counts.
    """
    esc = re.escape(heading)
    start_pattern = rf"###?\s*{esc}\s*\n|\*\*\s*{esc}\s*\*\*[ \t]*\n"
    match = re.search(start_pattern, brief, re.IGNORECASE)
    if not match:
        return ""
    start = match.end()
    # A bold line only counts as the START of the next section if it is not
    # a numbered entry-point subheading (``**1. Title**``) — those live
    # INSIDE "Three Alkira Entry Points" and must not truncate that section.
    next_heading = re.search(
        r"\n(?:###?\s|\*\*(?!\d+\.\s)[^\n*]+\*\*[ \t]*\n)", brief[start:]
    )
    end = start + next_heading.start() if next_heading else len(brief)
    return brief[start:end].strip()


class EntryPoint(TypedDict):
    heading: str
    signal: str
    solution: str
    proof: str
    body: str  # raw cleaned body text — always populated for fallback rendering


def _label_pattern(label: str) -> re.Pattern[str]:
    """Build a regex matching a Signal/Solution/Proof label across formatting variations.

    Handles: bare ``Signal: foo``, bullet ``- Signal: foo``, numbered ``1. Signal: foo``,
    bold ``**Signal**: foo`` / ``**Signal:** foo``, and combinations thereof.
    """
    return re.compile(
        rf"(?im)^\s*[-*\d.\s]*\**\s*\b{label}\b\s*[:\-]?\s*\**\s*[:\-]?\s*(.+?)"
        rf"(?=\n\s*[-*\d.\s]*\**\s*\b(?:Signal|Solution|Proof)\b\s*[:\-]?\s*\**\s*[:\-]?|\Z)",
        re.DOTALL,
    )


def _grab(body: str, label: str) -> str:
    m = _label_pattern(label).search(body)
    return m.group(1).strip() if m else ""


def extract_entry_points(brief: str) -> list[EntryPoint]:
    """Parse the 'Three Alkira Entry Points' section into 3 dicts.

    Each dict has: heading, signal, solution, proof.
    Returns empty list if section is missing.
    """
    section = extract_section(brief, "Three Alkira Entry Points")
    if not section:
        section = extract_section(brief, "Alkira Entry Points")
    if not section:
        return []

    # Split on bold-numbered headings: **1. Title**, **2. Title**, **3. Title**.
    # Allow markdown emphasis (e.g. *italic*) inside the heading by closing on
    # the trailing ``**`` followed by a newline.
    parts = re.split(r"\*\*\s*\d+\.\s+(.+?)\*\*\s*\n", section, flags=re.DOTALL)
    # parts = ["", "heading1", "body1", "heading2", "body2", ...]

    points: list[EntryPoint] = []
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""

        signal = _grab(body, "signal")
        solution = _grab(body, "solution")
        proof = _grab(body, "proof")

        # Always preserve a cleaned raw body as a fallback for the renderer.
        # Strip leading numbered-sentence markers (``1. ``) so prose reads
        # cleanly as a single paragraph if the renderer has to fall back.
        cleaned_body = body.strip()
        cleaned_body = re.sub(r"^(\d+\.\s+)", "", cleaned_body, flags=re.MULTILINE)

        # Fallback: agent sometimes emits a 3-sentence paragraph WITHOUT
        # Signal/Solution/Proof labels. Stash the whole body in `signal` so
        # legacy callers still see content there.
        if not (signal or solution or proof):
            points.append(EntryPoint(
                heading=heading,
                signal=cleaned_body,
                solution="",
                proof="",
                body=cleaned_body,
            ))
        else:
            points.append(EntryPoint(
                heading=heading,
                signal=signal,
                solution=solution,
                proof=proof,
                body=cleaned_body,
            ))

    return points[:3]


class InfraCells(TypedDict):
    cloud_platforms: str
    on_prem: str
    deployment: str
    complexity: str


def extract_infra_cells(brief: str) -> InfraCells:
    """Parse the 4 bold sub-labels from Infrastructure Snapshot.

    Returns dict with keys: cloud_platforms, on_prem, deployment, complexity.
    Missing values are empty strings.

    Measured production failure: the model sometimes writes all four bold
    sub-labels with real content but omits the '## Infrastructure Snapshot'
    heading entirely (not even a bold-only heading line), so
    ``extract_section`` finds no section to bound. Rather than blank the PDF
    grid in that case, fall back to scanning the whole brief for the four
    bold sub-labels directly. This only changes behavior when the heading is
    missing; when the section is found, matching proceeds exactly as before.
    """
    empty: InfraCells = {
        "cloud_platforms": "",
        "on_prem": "",
        "deployment": "",
        "complexity": "",
    }
    section = extract_section(brief, "Infrastructure Snapshot")
    haystack = section or brief

    label_map = {
        "cloud_platforms": [r"Cloud Platforms?"],
        "on_prem": [r"On-?Prem(?:\s*/\s*Hybrid)?", r"Hybrid"],
        "deployment": [r"Deployment Model", r"Deployment"],
        "complexity": [r"Resulting Complexity", r"Complexity"],
    }

    out: InfraCells = dict(empty)  # type: ignore[assignment]
    for key, patterns in label_map.items():
        for pat in patterns:
            m = re.search(
                rf"\*\*\s*{pat}\s*:?\s*\*\*\s*:?\s*(.+?)(?=\n\s*\*\*|\Z)",
                haystack,
                re.DOTALL | re.IGNORECASE,
            )
            if m:
                out[key] = m.group(1).strip()  # type: ignore[literal-required]
                break

    return out


def extract_exec_snippet(brief_md: str, max_chars: int = 120) -> str:
    """Pull a preview snippet from the score reasoning or first section."""
    # Try score reasoning first (it's the new exec summary)
    _, reasoning = extract_score(brief_md)
    if reasoning and len(reasoning) > 20:
        if len(reasoning) > max_chars:
            cut = reasoning[:max_chars].rsplit(" ", 1)[0]
            return cut + "..."
        return reasoning

    # Fallback: try Executive Summary (old format) or Infrastructure Snapshot
    for heading in ["Executive Summary", "Infrastructure Snapshot"]:
        section = extract_section(brief_md, heading)
        if not section:
            continue
        for line in section.split("\n"):
            stripped = line.strip().lstrip("- *")
            stripped = re.sub(r"\*\*.*?\*\*", "", stripped).strip()
            if len(stripped) > 20:
                if len(stripped) > max_chars:
                    cut = stripped[:max_chars].rsplit(" ", 1)[0]
                    return cut + "..."
                return stripped
    return ""


def get_brief_body(brief: str) -> str:
    """Get the brief content starting from the first content section,
    excluding the title, company header, and score (rendered separately)."""
    markers = [
        "### Infrastructure Snapshot",
        "### Executive Summary",
        "## Executive Summary",
        "### Company Snapshot",
        "### Cloud & Infrastructure",
        "### Signals & Timing",
    ]
    for marker in markers:
        idx = brief.find(marker)
        if idx != -1:
            # Find the CONFIDENTIAL marker or end
            end_markers = ["*CONFIDENTIAL*", "*\"CONFIDENTIAL\"*", "CONFIDENTIAL"]
            end_idx = len(brief)
            for em in end_markers:
                ei = brief.find(em, idx)
                if ei != -1:
                    end_idx = min(end_idx, ei + len(em))
            return brief[idx:end_idx].strip()
    return brief
