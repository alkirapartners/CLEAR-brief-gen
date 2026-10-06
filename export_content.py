"""What both exports of a brief say: the PDF and the Word document.

The two are laid out differently and must not differ in content. The order
of the sections, their headings and every derived phrase (how strong the
fit is, a deal's status, how a source is dated, what kind of source it is)
are worked out here once, in the brief's language, the way the brief page
words them. Nothing here draws anything.
"""

import re
from typing import Literal, NamedTuple, Sequence
from urllib.parse import urlsplit

import brief_compat
import i18n
import stat_pills
from brief_doc import Angle, BriefDoc, EvidenceLine, Reference, Story
from evidence import safe_url

Labels = dict[str, str]
DateKind = Literal["dated", "open", "undated"]
ProofKind = Literal["story", "metric"]

FIT_SCALE = 5
STRONG_FROM = 4
MODERATE_FROM = 3
MAX_INITIALS = 2


class Section(NamedTuple):
    """One section of a brief: the key its renderer is found by, and its heading."""

    key: str
    heading: str


def outline(doc: BriefDoc, labels: Labels) -> list[Section]:
    """The sections a brief has, in the order of the page. One with nothing in it is left out."""
    sections = [
        ("fit", labels["alkira_fit"], True),
        ("why_now", labels["why_now"], bool(doc["angles"])),
        ("ask_this", labels["ask_this"], bool(doc["questions"])),
        ("for_engineer", labels["for_engineer"], True),
        ("who_to_talk_to", labels["who_to_talk_to"], bool(doc["people"])),
        ("unconfirmed", labels["unconfirmed"], bool(doc["unconfirmed"])),
        ("raise_score", labels["raise_score"], bool(doc["raise_score"])),
        ("references", labels["references"], bool(doc["references"])),
    ]
    return [Section(key, heading) for key, heading, has_content in sections if has_content]


def sentence_case(text: str) -> str:
    return text[:1].upper() + text[1:]


# ── The verdict ──────────────────────────────────────────────────────────────

def fit_label(score: int, labels: Labels) -> str:
    """How strong a score is, in words: the pill beside the number."""
    if score >= STRONG_FROM:
        return labels["fit_strong"]
    return labels["fit_moderate"] if score >= MODERATE_FROM else labels["fit_weak"]


def score_text(score: int) -> str:
    return f"{score} / {FIT_SCALE}"


# The end of a sentence: a stop, then space, then a capital or an opening mark.
_SENTENCE_END = re.compile(r"[.!?]\s+(?=[A-ZÁÉÍÓÚÑ¿¡\"“])")


def split_lead(lead: str) -> tuple[str, str]:
    """The lead's first sentence (what to open with) and whatever follows it (whom to call)."""
    text = lead.strip()
    end = _SENTENCE_END.search(text)
    if end is None:
        return text, ""
    return text[: end.start() + 1], text[end.end():]


# ── Angles ───────────────────────────────────────────────────────────────────

def use_case_name(use_case: str, labels: Labels) -> str:
    """A use case's name. One this code does not know yet is shown as plain words."""
    known = labels.get(f"use_case_{use_case}")
    return known or sentence_case(use_case.replace("_", " ").strip())


def deal_parts(angle: Angle, labels: Labels, language: str | None) -> tuple[str, str]:
    """An M&A angle's status and its date: ("Pending deal", "announced 28 Jul 2026"). Empty for any other angle."""
    when = i18n.readable_date(angle["deal_date"], language)
    if angle["deal_status"] == "pending":
        return labels["deal_pending"], labels["deal_announced"].format(date=when) if when else ""
    if angle["deal_status"] == "completed":
        return labels["deal_completed"], when
    return "", ""


def deal_text(angle: Angle, labels: Labels, language: str | None) -> str:
    return ", ".join(part for part in deal_parts(angle, labels, language) if part)


class DateNote(NamedTuple):
    """How a fact is dated. ``stamp`` stands alone above it; ``note`` reads inside a sentence."""

    kind: DateKind
    stamp: str
    note: str


def _date_note(kind: DateKind, note: str, stamp: str | None = None) -> DateNote:
    return DateNote(kind, sentence_case(note) if stamp is None else stamp, note)


def evidence_date(
    line: EvidenceLine, references: Sequence[Reference], labels: Labels, language: str | None,
) -> DateNote:
    """When an evidence line's source is dated: by the page, by a posting seen open, or not at all.

    A line that says itself that its source is undated is not labelled so a second time.
    """
    when = i18n.readable_date(line["date"], language)
    if not when:
        return _date_note("undated", brief_compat.undated_note(line, labels))
    is_open = any(
        ref["open_posting"] and ref["date"] == line["date"] and ref["n"] in line["sources"] for ref in references
    )
    if is_open:
        return _date_note("open", labels["open_posting_seen"].format(date=when))
    return _date_note("dated", labels["source_dated"].format(date=when), stamp=when)


# ── References ───────────────────────────────────────────────────────────────

_SOURCE_TYPE_LABELS: dict[str, str] = {
    "first_hand": "source_first_hand",
    "second_hand": "source_second_hand",
    "last_resort": "source_last_resort",
}


def source_type_label(reference: Reference, labels: Labels) -> str:
    """How close a source is to the company: "First-hand", "Second-hand", "Last-resort source"."""
    key = _SOURCE_TYPE_LABELS.get(reference["source_type"], "source_second_hand")
    return sentence_case(labels[key])


def reference_date(reference: Reference, labels: Labels, language: str | None) -> DateNote:
    when = i18n.readable_date(reference["date"], language)
    if not when:
        return _date_note("undated", labels["undated"])
    if reference["open_posting"]:
        return _date_note("open", labels["open_posting_seen"].format(date=when))
    return _date_note("dated", labels["source_dated"].format(date=when), stamp=when)


def reference_title(reference: Reference, labels: Labels) -> str:
    """A reference's title without the "(open posting, seen 2026-10-06)" stored at its end.

    The row gives that as its date, so it is not said twice.
    """
    if not reference["open_posting"]:
        return reference["title"]
    lead = labels["open_posting_seen"].split("{date}")[0].strip()
    note = re.compile(rf"\s*\({re.escape(lead)}[^)]*\)\s*$", re.IGNORECASE)
    return note.sub("", reference["title"]).strip() or reference["title"]


def link_target(url: str) -> str | None:
    """The address a link may point at, or None: only a public http(s) page is ever linked.

    Every address in a brief was written by a model from other people's pages.
    """
    return safe_url(url)


def display_url(url: str) -> str:
    """An address as a reader wants it: no scheme, no "www.", no bare trailing slash."""
    if link_target(url) is None:
        return url
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").removeprefix("www.")
    path = "" if parts.path == "/" else parts.path
    return f"{host}{path}{f'?{parts.query}' if parts.query else ''}"


# ── Proof ────────────────────────────────────────────────────────────────────

class Proof(NamedTuple):
    """What an angle shows as proof: a named customer's result, or a figure with no customer."""

    kind: ProofKind
    label: str
    customer: str
    qualifier: str
    figure: str
    name: str
    result: str
    # Said under a knowledge-base figure, so it is never read as a customer's result.
    note: str


_QUALIFIED_NAME = re.compile(r"^(.+?)\s*\(([^()]+)\)$")
# "80%", "40-60%", "Up to 1650%", then whatever follows it.
_FIGURE = re.compile(
    r"^((?:up to |about |over )?\d[\d.,]*(?:\s?[-–]\s?\d[\d.,]*)?\s?(?:%|x|×)?\+?)\s*(.*)$", re.IGNORECASE,
)
_NAME_SEPARATOR = ": "


def _split_metric(result: str) -> tuple[str, str, str]:
    """"Firewall reduction: 73% (up to 82%)." as its name, its figure and the rest."""
    text = result.strip()
    name, separator, value = text.partition(_NAME_SEPARATOR)
    match = _FIGURE.match(value.rstrip(".,")) if separator else None
    if match is None:
        return "", "", text
    return name.strip(), match.group(1).strip().rstrip(".,"), match.group(2).strip()


def proof(story: Story, labels: Labels) -> Proof | None:
    """An angle's proof, or None when it has none.

    A result with no customer named is a proof point, never a customer story.
    """
    customer, result = story["customer"].strip(), story["result"].strip()
    if not customer and not result:
        return None
    is_figure = brief_compat.is_proof_point(story)
    if is_figure or not customer:
        name, figure, rest = _split_metric(result)
        note = labels["no_story_note"] if is_figure else ""
        return Proof("metric", labels["proof_point"], "", "", figure, name, rest, note)
    named = _QUALIFIED_NAME.match(customer)
    who, qualifier = (named.group(1), named.group(2)) if named else (customer, "")
    return Proof("story", labels["customer_story"], who, qualifier, "", "", result, "")


_NUMBER = r"\d+(?:,\d{3})*(?:\.\d+)?"
_NUMBER_WORDS = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
_TIME_UNITS = "minutes?|hours?|days?|weeks?|months?|years?"
# A length of time ("three weeks", "2 days"), or a figure with its sign ("1,400", "1650%", "99%+", "60-88%").
_NUMBERS = re.compile(
    rf"\b(?:{_NUMBER_WORDS}|{_NUMBER}) (?:{_TIME_UNITS})\b|{_NUMBER}(?:[-–]{_NUMBER})?(?:%\+?|\+|x\b)?",
    re.IGNORECASE,
)


def emphasise_numbers(text: str) -> list[tuple[str, bool]]:
    """A result split around its numbers, so they can be set heavier than the words."""
    parts: list[tuple[str, bool]] = []
    end = 0
    for match in _NUMBERS.finditer(text):
        if match.start() > end:
            parts.append((text[end:match.start()], False))
        parts.append((match.group(0), True))
        end = match.end()
    if end < len(text):
        parts.append((text[end:], False))
    return parts


# ── The company ──────────────────────────────────────────────────────────────

class Identity(NamedTuple):
    """Which company the brief resolved: its entity and listing, its site, and a note when names collide."""

    facts: tuple[str, ...]
    site: str
    site_url: str | None
    note: str


def identity(doc: BriefDoc, labels: Labels) -> Identity:
    company = doc["company"]
    legal_name = company["legal_name"].strip()
    # The legal name is left out when it only repeats the company name above it.
    repeats_name = legal_name.casefold() == company["name"].strip().casefold()
    ownership = stat_pills.ownership(doc["stats"]["ownership"], company["ticker"])
    facts = tuple(fact for fact in ("" if repeats_name else legal_name, ownership) if fact)
    site_url = link_target(company["website"])
    site = (urlsplit(site_url).hostname or "").removeprefix("www.") if site_url else ""
    return Identity(facts, site, site_url, company["identity_note"].strip())


def stat_pills_for(doc: BriefDoc, labels: Labels) -> list[tuple[str, str]]:
    """The short company basics. Ownership is not among them: the identity line states it."""
    return [pill for pill in stat_pills.pills(doc, labels) if pill[0] != labels["stat_ownership"]]


def initials(name: str) -> str:
    return "".join(word[0].upper() for word in name.split()[:MAX_INITIALS])


def research_note(doc: BriefDoc, labels: Labels) -> str:
    """How much research stands behind the brief."""
    research = doc["research"]
    return labels["research_note"].format(
        searches=research["searches"], pages=research["pages"], seconds=research["seconds"],
    )
