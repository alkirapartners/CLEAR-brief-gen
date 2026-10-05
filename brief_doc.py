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

FORMAT_VERSION = 2
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


class ResearchNote(TypedDict):
    searches: int
    pages: int
    seconds: int
    stopped_by: str


class BriefDoc(WriterOutput):
    """A stored brief: the writer's output plus what the code adds."""

    format: int
    language: str
    generated: str
    references: list[Reference]
    research: ResearchNote


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

    Never raises: a row that cannot be read is shown as an empty brief by
    the legacy path, the same as markdown the parsers cannot follow.
    """
    if not is_json_brief(stored):
        return None
    try:
        data = json.loads(stored or "")
        if not isinstance(data, dict) or data.get("format") != FORMAT_VERSION:
            return None
        return _DOC_ADAPTER.validate_python(data)
    except (ValueError, ValidationError) as exc:
        logger.warning("Stored brief is not a readable document: %s", exc)
        return None


def dump(doc: BriefDoc) -> str:
    """The text stored in ``brief_md``. Accented text is kept as written."""
    return json.dumps(doc, ensure_ascii=False)
