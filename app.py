"""
Alkira Opportunity Brief Generator — Web App

Streamlit frontend for the Managed Agent. Partners type a company name,
the agent researches it and returns a formatted brief on the page.

Usage:
    streamlit run app.py
"""

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

import db

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


# ── Configuration ────────────────────────────────────────────────

@dataclass(frozen=True)
class AgentConfig:
    agent_id: str
    env_id: str
    api_key: str


def _secret(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        try:
            val = st.secrets.get(key, "")
        except FileNotFoundError:
            pass
    return val


def load_config() -> AgentConfig:
    return AgentConfig(
        agent_id=_secret("ALKIRA_AGENT_ID"),
        env_id=_secret("ALKIRA_ENV_ID"),
        api_key=_secret("ANTHROPIC_API_KEY"),
    )


# ── Agent Session ────────────────────────────────────────────────

def run_agent_session(
    config: AgentConfig,
    company_name: str,
    status_callback,
    timeout_seconds: float = 300,
) -> str:
    client = Anthropic(api_key=config.api_key)

    prompt = (
        f'Research the company "{company_name}" and generate an Alkira '
        f"opportunity brief. Follow the brief structure and writing style in your "
        f"instructions exactly. Include the Alkira Fit Score, strategic sales "
        f"questions, and references. Focus on information from the past 12 months. "
        f"Return the brief as markdown text. Do not narrate your process."
    )

    status_callback("init")
    session = client.beta.sessions.create(
        agent=config.agent_id,
        environment_id=config.env_id,
        title=f"Alkira Brief: {company_name}",
    )

    brief_parts: list[str] = []

    try:
        status_callback("research")
        session_start = time.monotonic()

        with client.beta.sessions.events.stream(session.id) as stream:
            client.beta.sessions.events.send(
                session.id,
                events=[
                    {
                        "type": "user.message",
                        "content": [{"type": "text", "text": prompt}],
                    },
                ],
            )

            for event in stream:
                if time.monotonic() - session_start > timeout_seconds:
                    raise TimeoutError("Agent did not finish in time")

                if not hasattr(event, "type"):
                    continue

                if event.type == "agent.message":
                    for block in getattr(event, "content", []):
                        if getattr(block, "type", None) == "text":
                            brief_parts.append(block.text)

                if event.type == "agent.tool_use":
                    tool_name = getattr(event, "name", "")
                    if "search" in tool_name:
                        status_callback("search")
                    elif "skill" in tool_name or "read" in tool_name:
                        status_callback("analyze")

                if event.type == "session.status_idle":
                    status_callback("done")
                    break

                if event.type == "session.error":
                    msg = getattr(
                        getattr(event, "error", None), "message", "unknown"
                    )
                    brief_parts.append(f"\n\n[Error: {msg}]")
                    break

        return "".join(brief_parts)

    finally:
        try:
            client.beta.sessions.delete(session.id)
        except Exception:
            pass


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
    pattern = rf"###?\s*{re.escape(heading)}\s*\n"
    match = re.search(pattern, brief, re.IGNORECASE)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"\n###?\s", brief[start:])
    end = start + next_heading.start() if next_heading else len(brief)
    return brief[start:end].strip()


class EntryPoint(TypedDict):
    heading: str
    signal: str
    solution: str
    proof: str


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

        points.append(EntryPoint(
            heading=heading,
            signal=_grab(body, "signal"),
            solution=_grab(body, "solution"),
            proof=_grab(body, "proof"),
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
    """
    empty: InfraCells = {
        "cloud_platforms": "",
        "on_prem": "",
        "deployment": "",
        "complexity": "",
    }
    section = extract_section(brief, "Infrastructure Snapshot")
    if not section:
        return empty

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
                section,
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


# ── HTML Rendering ───────────────────────────────────────────────

def md_to_html(md: str) -> str:
    """Convert brief markdown to styled HTML with consistent visual treatment."""
    lines = md.split("\n")
    out: list[str] = []
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    for line in lines:
        stripped = line.strip()

        # Close lists if current line isn't a list item
        if in_ul and not stripped.startswith("- ") and not stripped.startswith("* "):
            close_lists()
        if in_ol and not re.match(r"^\d+\.\s", stripped):
            close_lists()

        if not stripped:
            continue

        # ── H3 = section card with blue accent ───────
        if stripped.startswith("### "):
            close_lists()
            title = stripped[4:]
            out.append(
                f'<div class="sec">'
                f'<div class="sec-bar"></div>'
                f'<h3>{inline(title)}</h3>'
                f'</div>'
            )
            continue

        # ── H2 ───────────────────────────────────────
        if stripped.startswith("## "):
            close_lists()
            out.append(f"<h2>{inline(stripped[3:])}</h2>")
            continue

        # ── Skip H1 (rendered separately) ────────────
        if stripped.startswith("# "):
            continue

        # ── Skip HRs ─────────────────────────────────
        if stripped in ("---", "***", "___"):
            continue

        # ── Bold entry point heading (e.g. **1. Multi-Cloud Networking**) ──
        ep_match = re.match(r"^\*\*(\d+\..+?)\*\*\s*$", stripped)
        if ep_match:
            close_lists()
            out.append(
                f'<div class="entry-point-head">'
                f'{inline(stripped)}'
                f'</div>'
            )
            continue

        # ── Bullet items ─────────────────────────────
        if stripped.startswith("- ") or stripped.startswith("* "):
            content = stripped[2:]

            # Bold-label bullet: **Label:** content
            label_match = re.match(r"\*\*(.+?):?\*\*:?\s*(.*)", content)
            if label_match:
                label = label_match.group(1).rstrip(":")
                rest = label_match.group(2).strip()
                if not in_ul:
                    out.append('<ul class="brief-list">')
                    in_ul = True
                rest_html = f' {inline(rest)}' if rest else ""
                out.append(
                    f'<li><span class="label">{label}:</span>{rest_html}</li>'
                )
                continue

            # Regular bullet
            if not in_ul:
                out.append('<ul class="brief-list">')
                in_ul = True
            out.append(f"<li>{inline(content)}</li>")
            continue

        # ── Ordered list ─────────────────────────────
        ol_match = re.match(r"^(\d+)\.\s(.+)", stripped)
        if ol_match:
            if not in_ol:
                out.append('<ol class="brief-list">')
                in_ol = True
            out.append(f"<li>{inline(ol_match.group(2))}</li>")
            continue

        # ── CONFIDENTIAL ─────────────────────────────
        if "CONFIDENTIAL" in stripped.upper():
            close_lists()
            out.append('<p class="confidential">CONFIDENTIAL</p>')
            continue

        # ── Paragraph (bold-label line without bullet) ──
        label_p = re.match(r"^\*\*(.+?):?\*\*:?\s+(.+)", stripped)
        if label_p:
            close_lists()
            label = label_p.group(1).rstrip(":")
            rest = label_p.group(2)
            out.append(
                f'<p><span class="label">{label}:</span> {inline(rest)}</p>'
            )
            continue

        out.append(f"<p>{inline(stripped)}</p>")

    close_lists()
    return "\n".join(out)


def inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    text = re.sub(
        r"\[(\d+)\]\s*(.+?)\s*[—–-]\s*(https?://\S+)",
        r'<a href="\3" target="_blank">[\1] \2</a>',
        text,
    )
    text = re.sub(
        r"\[(.+?)\]\((.+?)\)",
        r'<a href="\2" target="_blank">\1</a>',
        text,
    )
    return text


# ── Custom CSS ───────────────────────────────────────────────────

CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    :root {
        /* Brand */
        --alkira-blue: #2D58F2;
        --alkira-navy: #0A1F44;
        --alkira-ink: #211F1F;
        --alkira-muted: #7F7F7F;
        --alkira-orange: #FB923C;
        --alkira-amber: #FBBF24;

        /* Surfaces */
        --alkira-bg: #f8faff;
        --alkira-surface: #ffffff;
        --alkira-border: #e0e7ff;

        /* Score color stops */
        --score-5: #2D58F2;
        --score-4: #60a5fa;
        --score-3: #fbbf24;
        --score-2: #cbd5e1;
        --score-1: #cbd5e1;

        /* Type */
        --font-sans: 'Inter', system-ui, sans-serif;

        /* Radii / spacing */
        --tile-radius: 16px;
        --tile-pad: 14px 16px;
        --tile-shadow: 0 1px 3px rgba(10,31,68,0.04);
    }

    /* ── Reset & Global ──────────────────────────── */
    .stApp {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background: #f4f6f9;
    }
    .stDeployButton, #MainMenu, footer { display: none !important; }
    /* Lock sidebar open — hide collapse button */
    button[data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"] { display: none !important; }
    [data-testid="stSidebar"] {
        min-width: 260px !important;
        max-width: 260px !important;
        transform: none !important;
    }
    .stSpinner, div[data-testid="stSpinner"] { display: none !important; }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 820px !important;
    }

    /* ── Hero ────────────────────────────────────── */
    .hero {
        background: linear-gradient(140deg, #0b1a33 0%, #152a4e 40%, #1e3f6e 100%);
        border-radius: 14px;
        padding: 1.6rem 1.8rem;
        margin-bottom: 1.25rem;
        position: relative;
        overflow: hidden;
    }
    .hero::after {
        content: '';
        position: absolute;
        top: -60%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(59,130,246,0.07) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero-top {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .hero-icon {
        width: 28px;
        height: 28px;
        background: rgba(59,130,246,0.2);
        border-radius: 7px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.85rem;
    }
    .hero-badge {
        font-size: 0.6rem;
        font-weight: 700;
        color: #93c5fd;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .hero h2 {
        font-size: 1.35rem;
        font-weight: 800;
        color: #fff;
        margin: 0 0 0.25rem;
        letter-spacing: -0.02em;
    }
    .hero p {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.5);
        margin: 0;
        line-height: 1.45;
    }

    /* ── Search bar ──────────────────────────────── */
    .search-wrap {
        background: #fff;
        border: 1px solid #dde3eb;
        border-radius: 12px;
        padding: 0.2rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    div[data-testid="stTextInput"] > div > div > input {
        border: none !important;
        box-shadow: none !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 0.8rem !important;
        background: transparent !important;
    }
    div[data-testid="stTextInput"] > div {
        border: none !important;
        box-shadow: none !important;
        background: transparent !important;
    }

    /* ── Buttons ──────────────────────────────────── */
    .stButton > button,
    .stFormSubmitButton > button,
    button[kind="formSubmit"] {
        background: #1a3a6b !important;
        color: white !important;
        border: none !important;
        padding: 0.6rem 1.6rem !important;
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        border-radius: 9px !important;
        width: 100% !important;
        transition: all 0.15s ease;
        letter-spacing: 0.01em;
    }
    .stButton > button:hover,
    .stFormSubmitButton > button:hover,
    button[kind="formSubmit"]:hover {
        background: #244d8a !important;
        box-shadow: 0 3px 10px rgba(26,58,107,0.25);
    }
    /* Hide "Press Enter to submit form" hint */
    .stForm [data-testid="InputInstructions"] {
        display: none !important;
    }

    /* ── Step tracker ─────────────────────────────── */
    .step-tracker {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0;
        padding: 1.25rem 0;
        margin: 0.5rem 0;
    }
    .step {
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .step-dot {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.65rem;
        font-weight: 700;
        flex-shrink: 0;
        transition: all 0.3s ease;
    }
    .step-dot.pending {
        background: #e8ecf1;
        color: #94a3b8;
    }
    .step-dot.active {
        background: #1a3a6b;
        color: #fff;
        box-shadow: 0 0 0 4px rgba(26,58,107,0.15);
        animation: step-pulse 1.5s ease-in-out infinite;
    }
    .step-dot.done {
        background: #059669;
        color: #fff;
    }
    .step-label {
        font-size: 0.68rem;
        font-weight: 600;
        color: #94a3b8;
        transition: color 0.3s ease;
    }
    .step-label.active { color: #1a3a6b; }
    .step-label.done { color: #059669; }
    .step-line {
        width: 36px;
        height: 2px;
        background: #e8ecf1;
        margin: 0 0.35rem;
        flex-shrink: 0;
        transition: background 0.3s ease;
    }
    .step-line.done { background: #059669; }
    @keyframes step-pulse {
        0%, 100% { box-shadow: 0 0 0 4px rgba(26,58,107,0.15); }
        50% { box-shadow: 0 0 0 8px rgba(26,58,107,0.08); }
    }

    /* ── Results card ─────────────────────────────── */
    .result-card {
        background: #fff;
        border: 1px solid #dde3eb;
        border-radius: 14px;
        padding: 1.4rem 1.6rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .result-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.6rem;
    }
    .result-company {
        font-size: 1.2rem;
        font-weight: 800;
        color: #0f172a;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .result-meta {
        font-size: 0.72rem;
        color: #94a3b8;
    }
    .result-stats {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        margin-top: 0.5rem;
    }
    .stat-pill {
        display: inline-block;
        background: #f4f6f9;
        color: #475569;
        font-size: 0.67rem;
        font-weight: 500;
        padding: 0.2rem 0.55rem;
        border-radius: 5px;
    }
    .score-row {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-top: 0.75rem;
        padding-top: 0.75rem;
        border-top: 1px solid #f1f5f9;
    }
    .score-stars {
        font-size: 1.15rem;
        letter-spacing: 1px;
        line-height: 1;
    }
    .star-on { color: #f59e0b; }
    .star-off { color: #e2e8f0; }
    .score-num {
        font-size: 0.75rem;
        font-weight: 700;
        color: #475569;
    }
    .score-reason {
        font-size: 0.75rem;
        color: #64748b;
        line-height: 1.45;
        margin-top: 0.4rem;
    }


    /* ── Brief document ──────────────────────────── */
    .brief-doc {
        background: #fff;
        border: 1px solid #dde3eb;
        border-radius: 14px;
        padding: 1.8rem 2rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        color: #1e293b;
        line-height: 1.6;
    }
    .brief-doc h2 {
        font-size: 1rem;
        font-weight: 700;
        color: #152a4e;
        margin: 1.2rem 0 0.4rem;
    }

    /* Section headings — blue accent bar */
    .brief-doc .sec {
        display: flex;
        align-items: center;
        gap: 0.55rem;
        margin-top: 1.5rem;
        margin-bottom: 0.55rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #edf0f4;
    }
    .brief-doc .sec-bar {
        width: 3px;
        height: 16px;
        background: #2563eb;
        border-radius: 2px;
        flex-shrink: 0;
    }
    .brief-doc .sec h3 {
        font-size: 0.78rem;
        font-weight: 700;
        color: #1a3a6b;
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    /* Entry point headings (bold numbered like **1. Multi-Cloud**) */
    .brief-doc .entry-point-head {
        margin-top: 1rem;
        margin-bottom: 0.35rem;
        padding: 0.5rem 0.7rem;
        background: #f8fafc;
        border-left: 3px solid #1a3a6b;
        border-radius: 0 6px 6px 0;
        font-size: 0.82rem;
        font-weight: 700;
        color: #152a4e;
    }

    /* Paragraphs */
    .brief-doc p {
        font-size: 0.82rem;
        margin-bottom: 0.45rem;
    }

    /* Lists */
    .brief-doc .brief-list {
        font-size: 0.82rem;
        padding-left: 1.1rem;
        margin: 0.25rem 0 0.5rem;
    }
    .brief-doc .brief-list li {
        margin-bottom: 0.3rem;
        line-height: 1.5;
    }
    .brief-doc .brief-list li::marker {
        color: #94a3b8;
    }

    /* Bold labels (uniform treatment everywhere) */
    .brief-doc .label {
        font-size: 0.72rem;
        font-weight: 700;
        color: #1a3a6b;
        text-transform: uppercase;
        letter-spacing: 0.03em;
    }

    /* Inline styling */
    .brief-doc strong { color: #0f172a; }
    .brief-doc em { color: #64748b; font-style: italic; }
    .brief-doc a { color: #2563eb; text-decoration: none; }
    .brief-doc a:hover { text-decoration: underline; }
    .brief-doc code {
        background: #f1f5f9;
        padding: 0.1rem 0.3rem;
        border-radius: 3px;
        font-size: 0.78rem;
    }

    .brief-doc .confidential {
        text-align: center;
        font-size: 0.7rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-top: 1.5rem;
        padding-top: 1rem;
        border-top: 1px solid #edf0f4;
    }

    /* ── Sidebar ──────────────────────────────────── */
    [data-testid="stSidebar"] { background: #f9fafb; }
    [data-testid="stSidebar"] .block-container { padding-top: 1.5rem !important; }
    .sb-title {
        font-size: 0.65rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.6rem;
    }
    .sb-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0.6rem;
        border-radius: 8px;
        margin-bottom: 0.25rem;
        transition: background 0.1s ease;
        cursor: default;
    }
    /* Sidebar brief cards (buttons styled as cards) */
    [data-testid="stSidebar"] .stButton > button {
        background: #fff !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 0.6rem 0.7rem !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-align: left !important;
        margin-bottom: 0.35rem;
        transition: all 0.12s ease;
        cursor: pointer;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: #f8fafc !important;
        border-color: #93c5fd !important;
        box-shadow: 0 1px 4px rgba(26,58,107,0.08) !important;
        transform: none !important;
    }
    .sb-company {
        font-size: 0.78rem;
        font-weight: 600;
        color: #1e293b;
    }
    .sb-right {
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }
    .sb-stars {
        font-size: 0.7rem;
        color: #f59e0b;
        letter-spacing: 0.5px;
    }
    .sb-time {
        font-size: 0.62rem;
        color: #94a3b8;
    }

    /* ── How it works ─────────────────────────────── */
    .hiw-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.6rem;
        margin: 0.5rem 0;
    }
    .hiw-card {
        background: #f4f6f9;
        border-radius: 10px;
        padding: 0.8rem;
        text-align: center;
    }
    .hiw-num {
        width: 22px;
        height: 22px;
        background: #1a3a6b;
        color: #fff;
        border-radius: 50%;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.6rem;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }
    .hiw-label {
        font-size: 0.68rem;
        font-weight: 600;
        color: #1e293b;
        margin: 0;
    }
    .hiw-desc {
        font-size: 0.62rem;
        color: #64748b;
        margin: 0.15rem 0 0;
        line-height: 1.35;
    }

    /* ── Stats bar ────────────────────────────────── */
    .stats-bar {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.6rem;
        margin-bottom: 1.25rem;
    }
    .stats-metric {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.75rem 0.9rem;
        text-align: center;
    }
    .stats-value {
        font-size: 1.2rem;
        font-weight: 800;
        color: #0f172a;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .stats-label {
        font-size: 0.62rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin: 0.15rem 0 0;
    }

    /* ── Dashboard cards ──────────────────────────── */
    .dash-label {
        font-size: 0.68rem;
        font-weight: 700;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin: 1rem 0 0.6rem;
    }
    .dash-card {
        background: #fff;
        border: 1px solid #e2e8f0;
        border-radius: 10px 10px 0 0;
        padding: 0.9rem 1rem;
        min-height: 130px;
    }
    .dash-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.3rem;
    }
    .dash-company {
        font-size: 0.85rem;
        font-weight: 700;
        color: #0f172a;
        margin: 0;
        display: -webkit-box;
        -webkit-line-clamp: 1;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .dash-stars {
        font-size: 0.75rem;
        color: #f59e0b;
        letter-spacing: 1px;
        flex-shrink: 0;
    }
    .dash-snippet {
        font-size: 0.72rem;
        color: #64748b;
        line-height: 1.4;
        margin: 0;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .dash-date {
        font-size: 0.6rem;
        color: #94a3b8;
        margin: 0.3rem 0 0;
    }
    /* Dashboard open buttons — attached to card bottom */
    [data-testid="stMainBlockContainer"] .stColumn .stButton > button {
        border-radius: 0 0 10px 10px !important;
        margin-top: -1px;
        border-top: none !important;
    }

    /* ── Empty state ──────────────────────────────── */
    .empty-state {
        text-align: center;
        padding: 3rem 1rem;
    }
    .empty-state-icon {
        font-size: 2.5rem;
        margin-bottom: 0.75rem;
        opacity: 0.3;
    }
    .empty-state-text {
        font-size: 0.85rem;
        color: #94a3b8;
        margin: 0;
    }


    /* ── Welcome screen ──────────────────────────── */
    .welcome-card {
        background: #fff;
        border: 1px solid #dde3eb;
        border-radius: 16px;
        padding: 2.5rem 2rem;
        max-width: 420px;
        margin: 3rem auto;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .welcome-icon {
        width: 48px;
        height: 48px;
        background: linear-gradient(140deg, #0b1a33 0%, #1e3f6e 100%);
        border-radius: 12px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.3rem;
        color: #fff;
        margin-bottom: 1rem;
    }
    .welcome-title {
        font-size: 1.25rem;
        font-weight: 800;
        color: #0f172a;
        margin: 0 0 0.3rem;
        letter-spacing: -0.02em;
    }
    .welcome-sub {
        font-size: 0.82rem;
        color: #64748b;
        margin: 0 0 1.5rem;
        line-height: 1.45;
    }
    .welcome-footer {
        font-size: 0.65rem;
        color: #94a3b8;
        margin-top: 1.25rem;
    }

    /* ── Sidebar user ────────────────────────────── */
    .sb-user {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 0.6rem;
        margin-bottom: 0.75rem;
        border-bottom: 1px solid #edf0f4;
        padding-bottom: 0.75rem;
    }
    .sb-avatar {
        width: 28px;
        height: 28px;
        background: #1a3a6b;
        color: #fff;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7rem;
        font-weight: 700;
        flex-shrink: 0;
    }
    .sb-email {
        font-size: 0.72rem;
        color: #475569;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
</style>
"""


# ── Step tracker ─────────────────────────────────────────────────

STEPS = [
    ("1", "Starting"),
    ("2", "Researching"),
    ("3", "Analyzing"),
    ("4", "Composing"),
]

PHASE_TO_STEP = {
    "init": 0,
    "research": 1,
    "search": 1,
    "analyze": 2,
    "compose": 3,
    "done": 4,
}


def render_step_tracker(current_phase: str) -> str:
    active_idx = PHASE_TO_STEP.get(current_phase, 0)
    parts = []
    for i, (num, label) in enumerate(STEPS):
        if i < active_idx:
            dot_cls = "done"
            label_cls = "done"
            icon = "&#10003;"
        elif i == active_idx:
            dot_cls = "active"
            label_cls = "active"
            icon = num
        else:
            dot_cls = "pending"
            label_cls = ""
            icon = num

        parts.append(
            f'<div class="step">'
            f'<span class="step-dot {dot_cls}">{icon}</span>'
            f'<span class="step-label {label_cls}">{label}</span>'
            f'</div>'
        )
        if i < len(STEPS) - 1:
            line_cls = "done" if i < active_idx else ""
            parts.append(f'<div class="step-line {line_cls}"></div>')

    return f'<div class="step-tracker">{"".join(parts)}</div>'


# ── Welcome Screen ───────────────────────────────────────────────

def _show_welcome() -> None:
    """Show email entry screen. Blocks the rest of the app via st.stop()."""
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(
            '<div class="welcome-card">'
            '<div class="welcome-icon">&#9670;</div>'
            '<p class="welcome-title">Alkira Brief Generator</p>'
            '<p class="welcome-sub">Enter your email to get started. '
            "Your briefs will be saved to your account.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        with st.form("welcome_form", border=False):
            email = st.text_input(
                "Email",
                placeholder="you@company.com",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Continue", use_container_width=True)

        if submitted:
            email = email.strip()
            if email and "@" in email and "." in email.split("@")[-1]:
                st.session_state["user_email"] = email.lower()
                st.rerun()
            else:
                st.error("Enter a valid email address.")

    st.stop()


def _ensure_briefs_loaded() -> None:
    """Load briefs from Supabase once per session."""
    if st.session_state.get("_briefs_loaded"):
        return

    email = st.session_state.get("user_email", "")
    if not email:
        return

    rows = db.get_user_briefs(email)
    history = []
    for row in rows:
        created = row.get("created_at", "")
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            display_time = dt.strftime("%b %d, %I:%M %p")
        except (ValueError, AttributeError):
            display_time = ""

        history.append({
            "id": row.get("id", ""),
            "company": row.get("company", ""),
            "brief_md": row.get("brief_md", ""),
            "score": row.get("score", 0),
            "time": display_time,
        })

    st.session_state.brief_history = history
    st.session_state._briefs_loaded = True


# ── Stats Bar ────────────────────────────────────────────────────

def _render_stats_bar(history: list[dict]) -> None:
    """Render 3-metric stats bar from brief history."""
    if not history:
        return

    total = len(history)
    scores = [e.get("score", 0) for e in history if e.get("score", 0) > 0]
    avg = sum(scores) / len(scores) if scores else 0
    latest = history[0].get("time", "").split(",")[0] if history else ""

    st.markdown(
        f'<div class="stats-bar">'
        f'<div class="stats-metric">'
        f'<p class="stats-value">{total}</p>'
        f'<p class="stats-label">Briefs Generated</p>'
        f'</div>'
        f'<div class="stats-metric">'
        f'<p class="stats-value">{avg:.1f} / 5</p>'
        f'<p class="stats-label">Avg Fit Score</p>'
        f'</div>'
        f'<div class="stats-metric">'
        f'<p class="stats-value">{latest or "—"}</p>'
        f'<p class="stats-label">Latest Brief</p>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Dashboard Cards ──────────────────────────────────────────────

def _render_dashboard_cards(history: list[dict]) -> None:
    """Render up to 4 recent briefs as preview cards, or empty state."""
    if not history:
        st.markdown(
            '<div class="empty-state">'
            '<div class="empty-state-icon">&#9670;</div>'
            '<p class="empty-state-text">Generate your first brief to get started.</p>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        '<p class="dash-label">Recent Briefs</p>',
        unsafe_allow_html=True,
    )

    cards = sorted(history, key=lambda x: x.get("score", 0), reverse=True)[:4]
    rows = [cards[:2], cards[2:4]]

    for row in rows:
        if not row:
            break
        cols = st.columns(2)
        for col_idx, entry in enumerate(row):
            with cols[col_idx]:
                s = entry.get("score", 0)
                stars = "\u2605" * s + "\u2606" * (5 - s)
                snippet = extract_exec_snippet(entry.get("brief_md", ""))
                date = entry.get("time", "")

                st.markdown(
                    f'<div class="dash-card">'
                    f'<div class="dash-top">'
                    f'<p class="dash-company">{entry.get("company", "")}</p>'
                    f'<span class="dash-stars">{stars}</span>'
                    f'</div>'
                    f'<p class="dash-snippet">{snippet}</p>'
                    f'<p class="dash-date">{date}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Find the real index in history for this entry
                real_idx = history.index(entry)
                if st.button(
                    "Open",
                    key=f"dash_{real_idx}",
                    use_container_width=True,
                ):
                    st.session_state["viewing_brief"] = real_idx
                    st.rerun()


# ── Brief Display ────────────────────────────────────────────────

def render_brief_display(
    brief_md: str,
    meta_right: str = "",
    show_update: bool = False,
) -> None:
    """Render a full brief with results card, score, and tabs."""
    score, reasoning = extract_score(brief_md)
    company, stats_line = extract_company_header(brief_md)

    # Stats pills
    stat_pills = ""
    if stats_line:
        parts = re.split(r"\s*\|\s*", stats_line.strip("* "))
        pills = "".join(
            f'<span class="stat-pill">{p.strip()}</span>'
            for p in parts if p.strip()
        )
        stat_pills = f'<div class="result-stats">{pills}</div>'

    # Score stars
    filled = ''.join(
        '<span class="star-on">&#9733;</span>' for _ in range(score)
    )
    empty = ''.join(
        '<span class="star-off">&#9733;</span>' for _ in range(5 - score)
    )

    # Results card
    card_radius = "14px"
    st.markdown(
        f'<div class="result-card" style="border-radius:{card_radius};">'
        f'<div class="result-top">'
        f'<div>'
        f'<p class="result-company">{company or "Brief"}</p>'
        f'{stat_pills}'
        f'</div>'
        f'<span class="result-meta">{meta_right}</span>'
        f'</div>'
        f'<div class="score-row">'
        f'<span class="score-stars">{filled}{empty}</span>'
        f'<span class="score-num">{score}/5</span>'
        f'</div>'
        f'<p class="score-reason">{reasoning}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Update button
    if show_update and company:
        if st.button("Update Brief", key="update_brief", use_container_width=True):
            st.session_state["_update_company"] = company
            st.rerun()

    # Full brief as single scrollable document
    body = get_brief_body(brief_md)
    html = md_to_html(body)
    st.markdown(
        f'<div class="brief-doc">{html}</div>',
        unsafe_allow_html=True,
    )


# ── Streamlit UI ─────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="Alkira Brief Generator",
        page_icon="https://alkira.com/favicon.ico",
        layout="centered",
        initial_sidebar_state="expanded",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # ── Auth gate ────────────────────────────────────────────
    if not st.session_state.get("user_email"):
        _show_welcome()
        return  # st.stop() already called inside _show_welcome

    # ── Load briefs from DB ──────────────────────────────────
    _ensure_briefs_loaded()

    if "brief_history" not in st.session_state:
        st.session_state.brief_history = []

    user_email = st.session_state["user_email"]
    db_connected = db.is_available()

    # ── Sidebar ──────────────────────────────────────────────
    with st.sidebar:
        # User identity
        initial = user_email[0].upper()
        st.markdown(
            f'<div class="sb-user">'
            f'<div class="sb-avatar">{initial}</div>'
            f'<span class="sb-email">{user_email}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )

        # DB status
        if not db_connected:
            st.warning("Database not connected. Briefs won't persist across sessions.", icon="⚠️")

        st.markdown('<p class="sb-title">Your Briefs</p>', unsafe_allow_html=True)

        if not st.session_state.brief_history:
            st.caption("No briefs yet. Generate one to get started.")
        else:
            sorted_briefs = sorted(
                enumerate(st.session_state.brief_history),
                key=lambda x: x[1].get("score", 0),
                reverse=True,
            )
            for i, entry in sorted_briefs:
                s = entry.get("score", 0)
                star_str = "\u2605" * s + "\u2606" * (5 - s)
                is_active = st.session_state.get("viewing_brief") == i
                prefix = "\u25B8 " if is_active else ""
                label = f"{prefix}{entry['company']}  {star_str}"
                if st.button(
                    label,
                    key=f"view_{i}",
                    use_container_width=True,
                ):
                    st.session_state["viewing_brief"] = i
                    st.rerun()

        # Sign out
        st.markdown("---")
        if st.button("Sign out", use_container_width=True, key="signout"):
            for key in ["user_email", "brief_history", "_briefs_loaded"]:
                st.session_state.pop(key, None)
            st.rerun()

    # ── Hero ─────────────────────────────────────────────────
    st.markdown(
        '<div class="hero">'
        '<div class="hero-top">'
        '<div class="hero-icon">&#9670;</div>'
        '<span class="hero-badge">Channel Sales Intelligence</span>'
        '</div>'
        "<h2>Alkira Brief Generator</h2>"
        "<p>Research any company. Get a scored opportunity brief with "
        "Alkira fit analysis, proof points, and sales questions.</p>"
        "</div>",
        unsafe_allow_html=True,
    )


    # ── Config ───────────────────────────────────────────────
    config = load_config()
    if not config.agent_id or not config.env_id or not config.api_key:
        st.error(
            "Missing config. Set ANTHROPIC_API_KEY, ALKIRA_AGENT_ID, "
            "and ALKIRA_ENV_ID in .env or Streamlit secrets."
        )
        return

    # ── Update trigger (re-research) ────────────────────────
    update_company = st.session_state.pop("_update_company", None)
    if update_company:
        st.session_state.pop("viewing_brief", None)

        # Find and remove old brief from history
        old_id = ""
        old_idx = None
        for idx_u, entry_u in enumerate(st.session_state.brief_history):
            if entry_u.get("company", "").lower() == update_company.lower():
                old_id = entry_u.get("id", "")
                old_idx = idx_u
                break

        tracker_ph = st.empty()

        def update_status(phase: str) -> None:
            tracker_ph.markdown(
                render_step_tracker(phase),
                unsafe_allow_html=True,
            )

        start = time.time()
        try:
            with st.spinner(""):
                raw = run_agent_session(
                    config, update_company, update_status,
                )

            elapsed = time.time() - start
            tracker_ph.empty()

            brief_md = clean_brief(raw)
            score, _ = extract_score(brief_md)
            company_name_clean, _ = extract_company_header(brief_md)
            if not company_name_clean:
                company_name_clean = update_company

            saved = db.replace_brief(old_id, user_email, company_name_clean, score, brief_md)
            brief_id = saved.get("id", "") if saved else ""
            created_at = saved.get("created_at", "") if saved else ""

            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                display_time = dt.strftime("%b %d, %I:%M %p")
            except (ValueError, AttributeError):
                display_time = time.strftime("%b %d, %I:%M %p")

            # Remove old entry, add new at top
            if old_idx is not None:
                st.session_state.brief_history.pop(old_idx)
            st.session_state.brief_history.insert(0, {
                "id": brief_id,
                "company": company_name_clean,
                "brief_md": brief_md,
                "score": score,
                "time": display_time,
            })
            st.session_state["viewing_brief"] = 0

            render_brief_display(brief_md, meta_right=f"Updated in {elapsed:.0f}s")

        except TimeoutError:
            tracker_ph.empty()
            st.error("Timed out after 5 minutes. Try again.")
        except Exception as exc:
            tracker_ph.empty()
            st.error(f"Something went wrong: {exc}")
        return

    # ── Search bar ───────────────────────────────────────────
    form_area = st.empty()
    with form_area.container():
        with st.form("brief_form", clear_on_submit=False, border=False):
            col1, col2 = st.columns([5, 1])
            with col1:
                company_name = st.text_input(
                    "Company",
                    placeholder="Enter a company name...",
                    label_visibility="collapsed",
                )
            with col2:
                generate = st.form_submit_button("Generate", use_container_width=True)

    # ── Generation ───────────────────────────────────────────
    if generate and company_name.strip():
        st.session_state.pop("viewing_brief", None)  # Clear any viewed brief
        form_area.empty()  # Hide form while generating
        tracker_ph = st.empty()
        current_phase = {"value": "init"}

        def update_status(phase: str) -> None:
            current_phase["value"] = phase
            tracker_ph.markdown(
                render_step_tracker(phase),
                unsafe_allow_html=True,
            )

        start = time.time()

        try:
            with st.spinner(""):
                raw = run_agent_session(
                    config, company_name.strip(), update_status,
                )

            elapsed = time.time() - start
            tracker_ph.empty()

            brief_md = clean_brief(raw)
            score, reasoning = extract_score(brief_md)
            company, stats_line = extract_company_header(brief_md)
            if not company:
                company = company_name.strip()

            render_brief_display(brief_md, meta_right=f"Generated in {elapsed:.0f}s")

            # ── Save to DB + session state ───────────────
            saved = db.save_brief(user_email, company, score, brief_md)
            brief_id = saved.get("id", "") if saved else ""
            created_at = saved.get("created_at", "") if saved else ""

            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                display_time = dt.strftime("%b %d, %I:%M %p")
            except (ValueError, AttributeError):
                display_time = time.strftime("%b %d, %I:%M %p")

            st.session_state.brief_history.insert(0, {
                "id": brief_id,
                "company": company,
                "brief_md": brief_md,
                "score": score,
                "time": display_time,
            })

            if not saved:
                st.warning(
                    "Brief saved locally but could not sync to your account.",
                    icon="&#9888;",
                )

        except TimeoutError:
            tracker_ph.empty()
            st.error("Timed out after 5 minutes. Try again.")

        except Exception as exc:
            tracker_ph.empty()
            st.error(f"Something went wrong: {exc}")

    elif generate:
        st.warning("Enter a company name first.")

    # ── View history brief ───────────────────────────────────
    elif (
        not generate
        and "viewing_brief" in st.session_state
        and st.session_state.brief_history
    ):
        idx = st.session_state["viewing_brief"]
        if 0 <= idx < len(st.session_state.brief_history):
            entry = st.session_state.brief_history[idx]
            brief_md = entry.get("brief_md", "")
            if brief_md:
                render_brief_display(
                    brief_md,
                    meta_right=entry.get("time", ""),
                    show_update=True,
                )

    # ── Home: dashboard cards or empty state ─────────────────
    else:
        _render_dashboard_cards(st.session_state.brief_history)

        # "How it works" only for first-time users
        if not st.session_state.brief_history:
            with st.expander("How it works", expanded=True):
                st.markdown(
                    '<div class="hiw-grid">'
                    '<div class="hiw-card"><div class="hiw-num">1</div>'
                    '<p class="hiw-label">Enter</p>'
                    '<p class="hiw-desc">Type any company name</p></div>'
                    '<div class="hiw-card"><div class="hiw-num">2</div>'
                    '<p class="hiw-label">Research</p>'
                    '<p class="hiw-desc">Agent searches the web</p></div>'
                    '<div class="hiw-card"><div class="hiw-num">3</div>'
                    '<p class="hiw-label">Score</p>'
                    '<p class="hiw-desc">Maps to Alkira fit 1-5</p></div>'
                    '<div class="hiw-card"><div class="hiw-num">4</div>'
                    '<p class="hiw-label">Brief</p>'
                    '<p class="hiw-desc">Proof points + questions</p></div>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                st.caption("Briefs take 2-4 minutes.")


if __name__ == "__main__":
    main()
