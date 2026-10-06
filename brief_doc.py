"""The JSON brief document: its shape, its schema, and reading a stored one.

New briefs are stored as one JSON document in the ``brief_md`` column. A
stored value that starts with ``{`` is a JSON brief; anything else is a
legacy markdown brief and is read by ``briefparse.py``.

The model writes a ``WriterOutput``. The code adds the rest (format,
language, date, references, research note) to make a ``BriefDoc``.
"""

import json
import logging
from typing import Any, Literal

from anthropic import transform_schema
from pydantic import TypeAdapter, ValidationError
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

# Which kind of stored brief this is: 2 is the JSON document.
FORMAT_VERSION = 2
# The revision of that document this code writes. Raise it whenever a field
# is added, and give the field a default in ADDED_FIELDS: a brief stored by
# older code is then read as if it had been written with that default, so it
# always opens.
#   1  the first JSON briefs (references carried a data_broker flag)
#   2  references carry source_type
#   3  angles carry the deal date and status; questions name their angle
#   4  angles carry the pending-deal quote; references mark open postings
DOC_VERSION = 4
FIRST_VERSION = 1
MAX_LOGGED_ERROR_CHARS = 500
JSON_BRIEF_PREFIX = "{"

UseCase = Literal[
    "multi_cloud",
    "china_global",
    "firewall_consolidation",
    "m_and_a",
    "network_modernization",
    "site_rollout",
    "partner_connectivity",
]
SNAPSHOT_KEYS: tuple[str, ...] = (
    "clouds", "cloud_connectivity", "wan", "firewalls", "data_centers", "plant_networks",
)


class BriefFormatError(ValueError):
    """Text that should be a brief document is not one."""


class Company(TypedDict):
    name: str
    legal_name: str
    ticker: str
    website: str
    identity_note: str


class Stats(TypedDict):
    hq: str
    revenue: str
    employees: str
    industry: str
    ownership: str
    cloud_network: str


class Fit(TypedDict):
    score: Literal[1, 2, 3, 4, 5]
    verdict: str
    lead: str


class EvidenceLine(TypedDict):
    text: str
    date: str
    sources: list[int]


class Story(TypedDict):
    id: str
    customer: str
    result: str


DealStatus = Literal["none", "pending", "completed"]


class Angle(TypedDict):
    title: str
    use_case: UseCase
    evidence: list[EvidenceLine]
    alkira: str
    story: Story
    # For an M&A angle: the date of the event (its announcement or its
    # completion) and whether the deal is still pending. Empty and "none"
    # for every other use case. See deal_rules.py.
    deal_date: str
    deal_status: DealStatus
    # For a pending deal: the page's own words saying it has yet to complete.
    deal_pending_quote: str


class SnapshotLine(TypedDict):
    text: str
    sources: list[int]


class Snapshot(TypedDict):
    clouds: SnapshotLine
    cloud_connectivity: SnapshotLine
    wan: SnapshotLine
    firewalls: SnapshotLine
    data_centers: SnapshotLine
    plant_networks: SnapshotLine


class Person(TypedDict):
    name: str
    role: str
    note: str
    sources: list[int]


class Question(TypedDict):
    question: str
    listen_for: str
    alkira_angle: str
    # Which angle the question is about, counting from 1. 0 for none.
    angle: int


class WriterOutput(TypedDict):
    """Exactly what the model is asked to write."""

    company: Company
    stats: Stats
    fit: Fit
    angles: list[Angle]
    snapshot: Snapshot
    people: list[Person]
    questions: list[Question]
    unconfirmed: list[str]
    raise_score: list[str]


class Reference(TypedDict):
    n: int
    title: str
    url: str
    date: str
    source_type: Literal["first_hand", "second_hand", "last_resort"]
    # True when ``date`` is the day the research saw this posting open.
    open_posting: bool


class ResearchNote(TypedDict):
    searches: int
    pages: int
    seconds: int
    stopped_by: str


class BriefDoc(WriterOutput):
    """A stored brief: the writer's output plus what the code adds."""

    format: int
    version: int
    language: str
    generated: str
    references: list[Reference]
    research: ResearchNote


# The fields each part of the document had when the first JSON briefs were
# stored. Nothing may be added to these sets: a new field goes in
# ADDED_FIELDS with its default (tests/test_stored_versions.py checks it).
FIRST_FIELDS: dict[str, frozenset[str]] = {
    "Company": frozenset({"name", "legal_name", "ticker", "website", "identity_note"}),
    "Stats": frozenset({"hq", "revenue", "employees", "industry", "ownership", "cloud_network"}),
    "Fit": frozenset({"score", "verdict", "lead"}),
    "EvidenceLine": frozenset({"text", "date", "sources"}),
    "Story": frozenset({"id", "customer", "result"}),
    "Angle": frozenset({"title", "use_case", "evidence", "alkira", "story"}),
    "SnapshotLine": frozenset({"text", "sources"}),
    "Snapshot": frozenset(SNAPSHOT_KEYS),
    "Person": frozenset({"name", "role", "note", "sources"}),
    "Question": frozenset({"question", "listen_for", "alkira_angle"}),
    "Reference": frozenset({"n", "title", "url", "date"}),
    "ResearchNote": frozenset({"searches", "pages", "seconds", "stopped_by"}),
    "BriefDoc": frozenset({
        "company", "stats", "fit", "angles", "snapshot", "people", "questions", "unconfirmed",
        "raise_score", "format", "language", "generated", "references", "research",
    }),
}
# Every field added since, with what a document stored without it is read as having.
ADDED_FIELDS: dict[str, dict[str, Any]] = {
    "Angle": {"deal_date": "", "deal_status": "none", "deal_pending_quote": ""},
    "Question": {"angle": 0},
    "Reference": {"source_type": "second_hand", "open_posting": False},
    "BriefDoc": {"version": FIRST_VERSION},
}
# The flag the first briefs carried on a reference, and what it reads as now.
_OLD_BROKER_FLAG = "data_broker"
_OLD_BROKER_TYPE = "last_resort"


def _filled(value: Any, part: str) -> Any:
    """A part of an older document with its added fields defaulted. Anything else is left for the check."""
    if not isinstance(value, dict):
        return value
    filled = {**ADDED_FIELDS.get(part, {}), **value}
    if part == "Reference" and "source_type" not in value and value.get(_OLD_BROKER_FLAG) is True:
        filled["source_type"] = _OLD_BROKER_TYPE
    return filled


def _each(value: Any, part: str) -> Any:
    return [_filled(item, part) for item in value] if isinstance(value, list) else value


def with_defaults(data: dict[str, Any]) -> dict[str, Any]:
    """A stored document with every field added since it was written given its default."""
    doc = _filled(data, "BriefDoc")
    return {
        **doc,
        "angles": _each(doc.get("angles"), "Angle"),
        "questions": _each(doc.get("questions"), "Question"),
        "references": _each(doc.get("references"), "Reference"),
    }


_WRITER_ADAPTER: TypeAdapter[WriterOutput] = TypeAdapter(WriterOutput)
_DOC_ADAPTER: TypeAdapter[BriefDoc] = TypeAdapter(BriefDoc)

# Sent as output_config.format. It is part of the cached request, so it must
# be identical on every call: built once, from the types above.
WRITER_SCHEMA: dict[str, Any] = transform_schema(_WRITER_ADAPTER.json_schema())


def parse_writer_output(text: str) -> WriterOutput:
    """The model's reply as a validated ``WriterOutput``."""
    try:
        return _WRITER_ADAPTER.validate_json(text)
    except ValidationError as exc:
        raise BriefFormatError(f"writer output is not a brief document: {exc}") from exc


def is_json_brief(stored: str | None) -> bool:
    """True for a new-format brief. Legacy markdown starts with ``#``, never ``{``."""
    return (stored or "").lstrip().startswith(JSON_BRIEF_PREFIX)


def load(stored: str | None) -> BriefDoc | None:
    """The stored document, or None for a legacy brief or a damaged document.

    A document stored by older code is read with the defaults of every field
    added since (``with_defaults``). A field this code does not know, from
    newer code, is ignored. Never raises: a row that cannot be read is shown
    as an empty brief by the legacy path, the same as markdown the parsers
    cannot follow.
    """
    if not is_json_brief(stored):
        return None
    try:
        data = json.loads(stored or "")
        if not isinstance(data, dict) or data.get("format") != FORMAT_VERSION:
            return None
        return _DOC_ADAPTER.validate_python(with_defaults(data))
    except (ValueError, ValidationError, TypeError, AttributeError, RecursionError) as exc:
        logger.warning("Stored brief is not a readable document: %s", str(exc)[:MAX_LOGGED_ERROR_CHARS])
        return None


def dump(doc: BriefDoc) -> str:
    """The text stored in ``brief_md``. Accented text is kept as written."""
    return json.dumps(doc, ensure_ascii=False)
