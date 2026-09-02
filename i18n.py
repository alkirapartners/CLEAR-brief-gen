"""Output language for briefs: visible labels and month names.

Only the *visible* chrome lives here. The markdown headings the model
emits stay English in every language, because ``app.py``'s regex
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
    },
}

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


def format_period(when: date, language: str | None) -> str:
    """Month and year in the brief's language, e.g. 'Agosto 2026'.

    Deliberately table-driven rather than locale-driven: ``locale.setlocale``
    is process-wide and not thread-safe, and Streamlit serves every session
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
