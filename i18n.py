"""Output language for briefs: visible labels and month names.

Only the *visible* chrome lives here. The markdown headings the model
emits stay English in every language, because ``briefparse.py``'s regex
extractors match them literally and neither renderer ever displays them --
both the PDF and the web tiles print their own labels from this table.
Translating a heading would blank a section; translating a label here
cannot.
"""

from __future__ import annotations

import re
from datetime import date

DEFAULT_LANGUAGE = "en"

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "es": "Español",
}

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "alkira_fit": "Alkira Fit",
        "cloud_platforms": "Cloud Platforms",
        "on_prem": "On-Prem / Hybrid",
        "deployment": "Deployment Model",
        "complexity": "Resulting Complexity",
        "signals_timing": "Signals & Timing",
        "entry_points": "Three Alkira Entry Points",
        "entry": "Entry",
        "signal": "Signal",
        "solution": "Solution",
        "proof": "Proof",
        "conversation_starters": "Conversation Starters",
        "references": "References",
        "confidential": "CONFIDENTIAL",
        "page": "Page",
        "of": "of",
        "generated": "Generated",
        # Briefs stored as a JSON document (brief_doc.py).
        "not_found": "Not found",
        "not_found_public": "Not found in public sources.",
        "identity": "Which company",
        "stat_entity": "Entity",
        "stat_hq": "HQ",
        "stat_revenue": "Revenue",
        "stat_employees": "Employees",
        "stat_industry": "Industry",
        "stat_ownership": "Ownership",
        "stat_cloud_network": "Cloud and network",
        "lead": "Lead with",
        "why_now": "Why this account, why now",
        "angle": "Angle",
        "evidence": "Evidence",
        "alkira_answer": "What Alkira does",
        "customer_story": "Customer story",
        "proof_point": "Proof point",
        "technical_snapshot": "Technical snapshot",
        "snap_clouds": "Clouds",
        "snap_cloud_connectivity": "Cloud connectivity",
        "snap_wan": "WAN",
        "snap_firewalls": "Firewalls",
        "snap_data_centers": "Data centers",
        "snap_plant_networks": "Plant networks",
        "who_to_talk_to": "Who to talk to",
        "questions": "Questions to ask",
        "listen_for": "Listen for",
        "alkira_angle": "Alkira angle",
        "unconfirmed": "What we couldn't confirm",
        "raise_score": "What would raise the score",
        "source_second_hand": "second-hand",
        "source_last_resort": "last-resort source",
        "undated": "source undated",
        "source_dated": "source dated {date}",
        "open_posting_seen": "open posting, seen {date}",
        # What the code says about a score it had to lower, in place of the writer's verdict.
        "verdict_2": "No use case with evidence that stands.",
        "verdict_3": "A use case without current first-hand evidence.",
        "verdict_4": "One use case with current first-hand evidence.",
        "score_held_no_angles": (
            "Score held at {score}: no angle is left with a dated fact from an opened page."
        ),
        "score_held_evidence": (
            "Score held at {score}: no use case has first-hand evidence dated in the last two years."
        ),
        "score_held_use_cases": (
            "Score held at {score}: a higher score needs two use cases, each with its own "
            "first-hand source, one of them dated in the last two years."
        ),
        "stakeholders": "Stakeholders",
        "best_first_question": "Best First Question",
        "lead_with_first_question": "Lead with question 1.",
        "validate_early": "Validate early",
    },
    "es": {
        "alkira_fit": "Ajuste Alkira",
        "cloud_platforms": "Plataformas Cloud",
        "on_prem": "On-Prem / Híbrido",
        "deployment": "Modelo de Despliegue",
        "complexity": "Complejidad Resultante",
        "signals_timing": "Señales y Oportunidad",
        "entry_points": "Tres Puntos de Entrada Alkira",
        "entry": "Punto",
        "signal": "Señal",
        "solution": "Solución",
        "proof": "Evidencia",
        "conversation_starters": "Temas de Conversación",
        "references": "Referencias",
        "confidential": "CONFIDENCIAL",
        "page": "Página",
        "of": "de",
        "generated": "Generado",
        "not_found": "No encontrado",
        "not_found_public": "No se encontró en fuentes públicas.",
        "identity": "Qué empresa",
        "stat_entity": "Entidad",
        "stat_hq": "Sede",
        "stat_revenue": "Ingresos",
        "stat_employees": "Empleados",
        "stat_industry": "Industria",
        "stat_ownership": "Propiedad",
        "stat_cloud_network": "Nube y red",
        "lead": "Empiece con",
        "why_now": "Por qué esta cuenta, por qué ahora",
        "angle": "Ángulo",
        "evidence": "Hallazgos",
        "alkira_answer": "Qué hace Alkira",
        "customer_story": "Caso de cliente",
        "proof_point": "Dato de referencia",
        "technical_snapshot": "Panorama técnico",
        "snap_clouds": "Nubes",
        "snap_cloud_connectivity": "Conectividad cloud",
        "snap_wan": "Red WAN",
        "snap_firewalls": "Cortafuegos",
        "snap_data_centers": "Centros de datos",
        "snap_plant_networks": "Redes de planta",
        "who_to_talk_to": "Con quién hablar",
        "questions": "Preguntas para hacer",
        "listen_for": "Qué escuchar",
        "alkira_angle": "Ángulo Alkira",
        "unconfirmed": "Lo que no pudimos confirmar",
        "raise_score": "Qué subiría la puntuación",
        "source_second_hand": "fuente indirecta",
        "source_last_resort": "fuente de último recurso",
        "undated": "fuente sin fecha",
        "source_dated": "fuente con fecha {date}",
        "open_posting_seen": "vacante abierta, vista el {date}",
        "verdict_2": "Ningún caso de uso con evidencia que se sostenga.",
        "verdict_3": "Un caso de uso sin evidencia de primera mano reciente.",
        "verdict_4": "Un caso de uso con evidencia de primera mano reciente.",
        "score_held_no_angles": (
            "Puntuación limitada a {score}: no queda ningún ángulo con un hecho fechado de una página abierta."
        ),
        "score_held_evidence": (
            "Puntuación limitada a {score}: ningún caso de uso tiene evidencia de primera mano "
            "fechada en los últimos dos años."
        ),
        "score_held_use_cases": (
            "Puntuación limitada a {score}: una puntuación mayor requiere dos casos de uso, cada uno "
            "con su propia fuente de primera mano, y uno de ellos fechado en los últimos dos años."
        ),
        "stakeholders": "Interlocutores",
        "best_first_question": "Mejor pregunta inicial",
        "lead_with_first_question": "Empiece con la pregunta 1.",
        "validate_early": "Validar primero",
    },
}

# Month names as they are abbreviated inside a sentence.
SHORT_MONTHS: dict[str, tuple[str, ...]] = {
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
}
_STORED_DATE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")

_SPANISH_MONTHS: tuple[str, ...] = (
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
)

# How far into a brief to look for its date line.
_DATE_LINE_CHARS = 400


def normalize(language: str | None) -> str:
    """Coerce any input to a supported language code."""
    code = (language or "").strip().lower()
    return code if code in LABELS else DEFAULT_LANGUAGE


def labels(language: str | None) -> dict[str, str]:
    """Visible label table for a language. Unknown codes fall back to English."""
    return LABELS[normalize(language)]


def readable_date(stored: str, language: str | None) -> str:
    """A stored date as people write it: "23 Sep 2026", "Sep 2026" or "2026".

    Text that is not a stored date (YYYY, YYYY-MM or YYYY-MM-DD) gives "".
    """
    match = _STORED_DATE.match(stored.strip())
    if match is None:
        return ""
    year, month, day = match.group(1), int(match.group(2) or 0), int(match.group(3) or 0)
    if not 0 <= month <= 12:
        return ""
    if month == 0:
        return year
    name = SHORT_MONTHS[normalize(language)][month - 1]
    return f"{day} {name} {year}" if day else f"{name} {year}"


def format_period(when: date, language: str | None) -> str:
    """Month and year in the brief's language, e.g. 'Agosto 2026'.

    Deliberately table-driven rather than locale-driven: ``locale.setlocale``
    is process-wide and not thread-safe, and the API serves every request
    from the same process.
    """
    if normalize(language) == "es":
        return f"{_SPANISH_MONTHS[when.month - 1]} {when.year}"
    return when.strftime("%B %Y")


def detect_language(brief_md: str) -> str:
    """Best-effort language of an already-generated brief.

    Reads the localized date line near the top (``*[Agosto 2026]*``), the
    one piece of visible prose whose wording this module dictates. Used to
    stop the repeat-company cache from serving a brief in the language the
    user did not ask for; the stored briefs carry no language column.

    Deliberately biased toward "en": an unrecognized brief is treated as
    English, which at worst costs a regeneration rather than reusing a
    Spanish brief for an English request.
    """
    head = brief_md[:_DATE_LINE_CHARS]
    for month in _SPANISH_MONTHS:
        if re.search(rf"\b{month}\s+\d{{4}}", head, re.IGNORECASE):
            return "es"
    return DEFAULT_LANGUAGE
