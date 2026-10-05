"""What an evidence line, an angle or a plant-network line must be to stay in a brief.

The fit rules say what is never evidence and what an angle has to rest on.
The writer is asked to follow them. This module removes what the code can
recognise when the writer does not: risk-factor language, headcount and
hiring statistics, an angle with no dated fact, a network-modernization
angle that never names network technology, an M&A angle that never names
what is to be connected or separated, and a plant-network line that is not
about industrial control systems.
"""

import re
from typing import Sequence

from brief_doc import Angle, EvidenceLine

NETWORK_MODERNIZATION = "network_modernization"
M_AND_A = "m_and_a"

# What a filing lists as a risk says what could go wrong, not what is happening.
_RISK_LANGUAGE = re.compile(r"\brisk(?:s| factors?)?\b|\briesgos?\b", re.IGNORECASE)
_PEOPLE = r"employees|team members|staff|workers|associates|empleados|colaboradores|trabajadores"
_OPENINGS = (
    r"open (?:roles|positions|jobs)|openings|job postings|job listings|vacancies|vacantes|puestos abiertos"
)
# A count of people, or of job openings. Never a reason to pursue an account.
_HEADCOUNT = re.compile(
    rf"\bheadcount\b|\bplantilla\b"
    rf"|\b\d[\d.,]*\+?\s+(?:[\w-]+\s+){{0,3}}(?:{_PEOPLE})\b"
    rf"|\b\d[\d.,]*\+?\s+(?:[\w-]+\s+){{0,2}}(?:{_OPENINGS})\b",
    re.IGNORECASE,
)
# Words that show a line is about the IT network. A delivery, logistics,
# store, distribution or branch "network" is a business footprint and has
# none of them.
_NETWORK_TECHNOLOGY = re.compile(
    r"\b(?:MPLS|SD-?WAN|SASE|WAN|LAN|BGP|VPN|ZTNA)\b"
    r"|\bbackbone\b|\bdata[- ]?cent(?:er|re)s?\b|\bfirewalls?\b|\brouters?\b|\bcircuits?\b"
    r"|\bExpressRoute\b|\bDirect Connect\b|\bTransit Gateway\b|\bVirtual WAN\b|\bzero trust\b"
    r"|\bnetwork(?:ing)? (?:engineer\w*|architect\w*|infrastructure|security|operations|automation"
    r"|team|moderni[sz]ation|transformation|refresh|upgrade|segmentation)\b"
    r"|\b(?:IT|corporate|enterprise|cloud|campus|wide[- ]area) network\w*\b"
    r"|\bcentros? de datos\b|\bcortafuegos\b|\bingenier\w+ de redes\b|\binfraestructura de red\b"
    r"|\bred (?:corporativa|empresarial|de área amplia)\b",
    re.IGNORECASE,
)
# Industrial control systems. The acronyms are matched as written, so "DCs"
# (distribution centers) is not read as "DCS".
_CONTROL_ACRONYMS = re.compile(r"\b(?:OT|ICS|SCADA|PLCs?|DCS)\b")
_CONTROL_WORDS = re.compile(
    r"\bindustrial control\b|\bcontrol systems?\b|\boperational technology\b|\bprocess control\b"
    r"|\bPurdue\b|\bplant[- ]floor\b|\bshop[- ]floor\b|\bindustrial (?:network|ethernet|automation|DMZ)\w*\b"
    r"|\b(?:plant|factory|refinery|mill|mine) networks?\b"
    r"|\bsistemas? de control\b|\bcontrol de procesos\b|\bred(?:es)? de planta\b|\btecnolog[ií]a operativa\b",
    re.IGNORECASE,
)


# What a deal leaves to connect or to separate: sites, systems, or the
# entities on each side. A deal's name, its price and its closing date are
# none of these.
_TO_CONNECT = re.compile(
    r"\b(?:sites?|locations?|facilit(?:y|ies)|plants?|refiner(?:y|ies)|stores?|storefronts?|branch(?:es)?"
    r"|offices?|warehouses?|terminals?|depots?|clinics?|hospitals?|campus(?:es)?|hubs?|operations?"
    r"|data[- ]?cent(?:er|re)s?|networks?|systems?|platforms?|applications?|infrastructure|technology"
    r"|ERP|subsidiar(?:y|ies)|business units?|segments?|divisions?|entit(?:y|ies)|employees|countries"
    r"|transition services|TSA|carve-?out|standalone|spin-?off"
    r"|(?:independent|separate|new)(?:,? \w+){0,3} compan(?:y|ies)|operat(?:es|ing) in"
    r"|sedes?|plantas?|tiendas?|sucursales?|oficinas?|instalaciones|sistemas?|redes|filiales"
    r"|unidades de negocio|servicios de transici[oó]n)\b",
    re.IGNORECASE,
)


def is_evidence(text: str) -> bool:
    """False for a line that only reports a listed risk, a headcount or a hiring statistic."""
    return not (_RISK_LANGUAGE.search(text) or _HEADCOUNT.search(text))


def kept_lines(lines: Sequence[EvidenceLine]) -> list[EvidenceLine]:
    return [line for line in lines if is_evidence(line["text"])]


def names_network_technology(text: str) -> bool:
    return _NETWORK_TECHNOLOGY.search(text) is not None


def stands(angle: Angle) -> bool:
    """True when an angle rests on a specific, dated fact about the right thing.

    Every angle needs at least one dated line. A network-modernization angle
    also needs a line that names network technology: a business "network"
    being reorganised is about sites, not about the IT network. An M&A angle
    needs a line that names what has to be connected or separated: a deal
    with a price and a date and nothing else is news.
    """
    lines = angle["evidence"]
    if not any(line["date"].strip() for line in lines):
        return False
    if angle["use_case"] == NETWORK_MODERNIZATION:
        return any(names_network_technology(line["text"]) for line in lines)
    if angle["use_case"] == M_AND_A:
        return any(_TO_CONNECT.search(line["text"]) for line in lines)
    return True


def is_plant_network(text: str) -> bool:
    """True when a snapshot line is about industrial control systems."""
    return bool(_CONTROL_ACRONYMS.search(text) or _CONTROL_WORDS.search(text))
