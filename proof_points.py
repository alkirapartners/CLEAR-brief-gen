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
# The headline metric for each use case, by its name in the table.
METRIC_FOR_USE_CASE: dict[str, str] = {
    "multi_cloud": "Cloud connection time reduction",
    "china_global": "Network provisioning speed improvement",
    "firewall_consolidation": "Firewall reduction",
    "m_and_a": "Network provisioning speed improvement",
    "network_modernization": "TCO reduction",
    "site_rollout": "Network provisioning speed improvement",
    "partner_connectivity": "Partner onboarding time reduction",
}
# The metric names in Spanish. The figures are the table's in every language.
_SPANISH: dict[str, str] = {
    "Cloud connection time reduction": "Reducción del tiempo de conexión a la nube",
    "Network provisioning speed improvement": "Mejora en la velocidad de aprovisionamiento de red",
    "Firewall reduction": "Reducción de cortafuegos",
    "TCO reduction": "Reducción del costo total de propiedad",
    "Partner onboarding time reduction": "Reducción del tiempo de incorporación de socios",
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
