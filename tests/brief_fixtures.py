"""A complete JSON brief for tests, in the shape production stores.

The two angles are in the order the tests were written around. A brief
that goes through brief_rules.finalize has its qualifying M&A angle first.
"""

import copy
import json

SAMPLE_DOC: dict = {
    "format": 2,
    "version": 4,
    "language": "en",
    "generated": "2026-10-05",
    "company": {
        "name": "Northwind Energy",
        "legal_name": "Northwind Energy Corporation",
        "ticker": "NYSE: NWE",
        "website": "https://www.northwind.example",
        "identity_note": "Researched Northwind Energy Corporation of Dallas, not Northwind Traders.",
    },
    "stats": {
        "hq": "Dallas, TX",
        "revenue": "$28B",
        "employees": "5,200",
        "industry": "Refining",
        "ownership": "Public",
        "cloud_network": "Azure, ExpressRoute and Virtual WAN, SD-WAN",
    },
    "fit": {
        "score": 5,
        "verdict": "Strong fit: a hand-built Azure network and a business separation, both dated this year.",
        "lead": "Open with the Azure hub build and call the Director of Network Engineering.",
    },
    "angles": [
        {
            "title": "Hand-built Azure network",
            "use_case": "multi_cloud",
            "evidence": [
                {
                    "text": "A network engineer posting lists ExpressRoute and a Virtual WAN hub-and-spoke.",
                    "date": "2026-09-23",
                    "sources": [1],
                },
            ],
            "alkira": "Alkira replaces hand-built hubs with one design deployed per region.",
            "story": {
                "id": "koch",
                "customer": "Koch Industries",
                "result": "Significant reduction in network complexity across acquisitions and business units.",
            },
            "deal_date": "",
            "deal_status": "none",
            "deal_pending_quote": "",
        },
        {
            "title": "Lubricants separation",
            "use_case": "m_and_a",
            "evidence": [
                {
                    "text": "The annual report describes separating the lubricants business into a standalone company.",
                    "date": "2026-02-20",
                    "sources": [2],
                },
            ],
            "alkira": "Both businesses run as separate segments on one fabric until cutover.",
            "story": {
                "id": "nemertes-4",
                "customer": "A software company (Nemertes study)",
                "result": "An acquired company's cloud networks integrated in days instead of months.",
            },
            "deal_date": "2026-02-20",
            "deal_status": "pending",
            "deal_pending_quote": "The separation is expected to be completed over the next 12-18 months.",
        },
    ],
    "snapshot": {
        "clouds": {"text": "Azure is the primary cloud.", "sources": [1]},
        "cloud_connectivity": {"text": "ExpressRoute into a Virtual WAN hub-and-spoke.", "sources": [1]},
        "wan": {"text": "SD-WAN at refineries and terminals.", "sources": [1]},
        "firewalls": {"text": "Palo Alto or Fortinet.", "sources": [1]},
        "data_centers": {"text": "", "sources": []},
        "plant_networks": {"text": "Plant networks at five refineries.", "sources": [2]},
    },
    "people": [
        {"name": "", "role": "Director of Network Engineering", "note": "Owns the Azure network.", "sources": [1]},
        {"name": "Dana Ruiz", "role": "Chief Information Officer", "note": "Named in the annual report.", "sources": [2]},
    ],
    "questions": [
        {
            "question": "Who builds a new Virtual WAN hub today, and how long does one take?",
            "listen_for": "hand-built hubs, weeks of lead time",
            "alkira_angle": "A new region is a design change deployed in a day.",
            "angle": 1,
        },
        {
            "question": "Which network services stay shared after the lubricants split?",
            "listen_for": "a transition services agreement with an end date",
            "alkira_angle": "Separate segments on one fabric until cutover.",
            "angle": 2,
        },
    ],
    "unconfirmed": ["Who owns the WAN contract.", "Whether a second cloud is in use."],
    "raise_score": ["A dated SD-WAN or MPLS renewal."],
    "references": [
        {
            "n": 1,
            "title": "Senior Network Engineer posting",
            "url": "https://careers.northwind.example/job/123",
            "date": "2026-09-23",
            "source_type": "first_hand",
            "open_posting": False,
        },
        {
            "n": 2,
            "title": "Annual report",
            "url": "https://www.northwind.example/annual-report.pdf",
            "date": "2026-02-20",
            "source_type": "first_hand",
            "open_posting": False,
        },
    ],
    "research": {"searches": 21, "pages": 17, "seconds": 203, "stopped_by": "finished"},
}

WRITER_KEYS = (
    "company", "stats", "fit", "angles", "snapshot", "people",
    "questions", "unconfirmed", "raise_score",
)


def make_doc(**changes: object) -> dict:
    """A deep copy of the sample with top-level keys replaced."""
    doc = copy.deepcopy(SAMPLE_DOC)
    doc.update(changes)
    return doc


def writer_output(**changes: object) -> dict:
    """Only the part of the sample the model writes."""
    doc = make_doc(**changes)
    return {key: doc[key] for key in WRITER_KEYS}


def stored(**changes: object) -> str:
    """The sample as it sits in the brief_md column."""
    return json.dumps(make_doc(**changes), ensure_ascii=False)


SAMPLE_JSON_BRIEF = stored()
