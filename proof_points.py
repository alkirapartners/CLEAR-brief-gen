"""The proof an angle shows when no customer story fits it.

A named story that does not match the angle's situation is worse than none,
so brief_rules removes it. The angle then shows the headline figure for its
use case from the knowledge base's Proof Points table, with no customer
named. The figure is chosen here, in code, and read from the table: the
model never writes it.
"""

import re
from functools import lru_cache
from pathlib import Path

from brief_doc import Story

KNOWLEDGE_BASE_PATH = Path(__file__).parent / "skills" / "alkira-customer" / "SKILL.md"
TABLE_HEADING = "## Proof Points"
# The story id that marks a proof point: a figure, not a named customer story.
METRIC = "metric"
# The table's names for the figures used below. Each name says whose figure
# it is: an average across the customers in the Nemertes study, or Alkira's own.
_CLOUD = "Less calendar time to add a cloud environment (Nemertes study average)"
_FIREWALLS = "Fewer firewalls for cloud (Nemertes study average)"
_PARTNER = "Less staff time to add an extranet partner (Nemertes study average)"
_PROVISIONING = "Provisioning time reduction (Alkira's own figure)"
_TCO = "TCO reduction (Alkira's own figure)"
# The headline metric for each use case, by its name in the table.
METRIC_FOR_USE_CASE: dict[str, str] = {
    "multi_cloud": _CLOUD,
    "china_global": _PROVISIONING,
    "firewall_consolidation": _FIREWALLS,
    "m_and_a": _PROVISIONING,
    "network_modernization": _TCO,
    "site_rollout": _PROVISIONING,
    "partner_connectivity": _PARTNER,
}
# The metric names in Spanish. The figures are the table's in every language.
_SPANISH: dict[str, str] = {
    _CLOUD: "Menos tiempo calendario para agregar un entorno de nube (promedio del estudio de Nemertes)",
    _FIREWALLS: "Menos cortafuegos para la nube (promedio del estudio de Nemertes)",
    _PARTNER: "Menos tiempo del personal para incorporar un socio a la extranet (promedio del estudio de Nemertes)",
    _PROVISIONING: "Reducción del tiempo de aprovisionamiento (cifra propia de Alkira)",
    _TCO: "Reducción del costo total de propiedad (cifra propia de Alkira)",
}
_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


@lru_cache(maxsize=1)
def load() -> dict[str, str]:
    """Every metric in the Proof Points table with its figure. Read once per process."""
    text = KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8")
    section = text.split(TABLE_HEADING, 1)[1].split("\n## ", 1)[0]
    rows = (_ROW.match(line) for line in section.splitlines())
    found = {row.group(1): row.group(2) for row in rows if row and not set(row.group(1)) <= set("-: ")}
    return {metric: value for metric, value in found.items() if metric != "Metric"}


def fallback(use_case: str, language: str) -> Story:
    """The headline figure for a use case, as a story with no customer and the id ``metric``."""
    metric = METRIC_FOR_USE_CASE[use_case]
    name = _SPANISH[metric] if language == "es" else metric
    return {"id": METRIC, "customer": "", "result": f"{name}: {load()[metric]}."}
