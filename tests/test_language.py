"""Tests for the Spanish brief language option.

The design constraint under test: Spanish changes the CONTENT and the
VISIBLE labels, but never the machine-parsed markdown contract and never
the cached system prefix.
"""

from datetime import date

import pytest

import i18n
import prompts


# ── Label table ──────────────────────────────────────────────────

def test_every_english_label_key_exists_in_spanish():
    assert set(i18n.LABELS["en"]) == set(i18n.LABELS["es"])


def test_no_spanish_label_is_left_untranslated():
    """A copy-paste miss would leave an English string in the Spanish table."""
    shared = {"CONFIDENTIAL"}  # intentionally near-identical across languages
    same = {
        key
        for key, value in i18n.LABELS["es"].items()
        if value == i18n.LABELS["en"][key] and value not in shared
    }
    assert not same, f"untranslated Spanish labels: {sorted(same)}"


def test_labels_falls_back_to_english_for_unknown_language():
    assert i18n.labels("fr") is i18n.LABELS["en"]
    assert i18n.labels("") is i18n.LABELS["en"]
    assert i18n.labels(None) is i18n.LABELS["en"]


def test_normalize_rejects_unknown_language():
    assert i18n.normalize("es") == "es"
    assert i18n.normalize("ES") == "es"
    assert i18n.normalize("pt") == "en"
    assert i18n.normalize(None) == "en"


def test_all_spanish_labels_survive_the_pdf_latin1_sanitizer():
    """PDF chrome must not degrade to '?' — this is why we can skip a font."""
    from pdf import _safe_text

    for key, value in i18n.LABELS["es"].items():
        assert "?" not in _safe_text(value), f"{key} lost characters: {value}"


# ── Period formatting ────────────────────────────────────────────

def test_format_period_uses_spanish_month_names():
    assert i18n.format_period(date(2026, 8, 31), "es") == "Agosto 2026"
    assert i18n.format_period(date(2026, 1, 5), "es") == "Enero 2026"
    assert i18n.format_period(date(2026, 12, 5), "es") == "Diciembre 2026"


def test_format_period_english_matches_strftime():
    when = date(2026, 8, 31)
    assert i18n.format_period(when, "en") == when.strftime("%B %Y")


def test_every_month_has_a_spanish_name():
    for month in range(1, 13):
        name = i18n.format_period(date(2026, month, 1), "es")
        assert name.split()[0] not in ("", None)
        assert name.endswith("2026")


# ── Prompt construction ──────────────────────────────────────────

TODAY = date(2026, 8, 31)


def test_english_user_message_is_unchanged_by_the_language_parameter():
    """The existing English path must be byte-identical to the default."""
    explicit = prompts.build_user_message("Acme", "sources", TODAY, language="en")
    default = prompts.build_user_message("Acme", "sources", TODAY)
    assert explicit == default


def test_spanish_user_message_adds_a_language_directive():
    english = prompts.build_user_message("Acme", "sources", TODAY, language="en")
    spanish = prompts.build_user_message("Acme", "sources", TODAY, language="es")
    assert spanish != english
    assert "Spanish" in spanish


def test_spanish_user_message_protects_every_machine_marker():
    """The parser keys must be named as untranslatable in the directive."""
    spanish = prompts.build_user_message("Acme", "sources", TODAY, language="es")
    for marker in (
        "## Infrastructure Snapshot",
        "## Signals & Timing",
        "## Three Alkira Entry Points",
        "## Conversation Starters",
        "## References",
        "**Cloud Platforms:**",
        "**On-Prem / Hybrid:**",
        "**Deployment Model:**",
        "**Resulting Complexity:**",
        "Alkira Fit Score",
        "Signal:",
        "Solution:",
        "Proof:",
    ):
        assert marker in spanish, f"directive never mentions {marker!r}"


def test_spanish_user_message_localizes_the_date_line():
    spanish = prompts.build_user_message("Acme", "sources", TODAY, language="es")
    assert "Agosto 2026" in spanish
    assert "August 2026" not in spanish


def test_unknown_language_falls_back_to_the_english_message():
    assert prompts.build_user_message(
        "Acme", "sources", TODAY, language="fr"
    ) == prompts.build_user_message("Acme", "sources", TODAY)


# ── Prompt cache integrity ───────────────────────────────────────

def test_system_prefix_takes_no_language_and_is_byte_stable():
    """The cached prefix must never vary — that is the whole cost saving.

    Called via subprocess so the lru_cache cannot make this vacuous by
    comparing an object to itself.
    """
    import subprocess
    import sys

    script = (
        "import hashlib, prompts;"
        "print(hashlib.sha256(prompts.build_system_prefix().encode()).hexdigest())"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, check=True
        ).stdout.strip()
        for _ in range(2)
    ]
    assert runs[0] == runs[1]

    import inspect

    assert not inspect.signature(prompts.build_system_prefix).parameters, (
        "build_system_prefix must take no arguments; a language parameter "
        "would fork the cached prefix and destroy the prompt cache"
    )


def test_language_never_appears_in_the_system_prefix():
    prefix = prompts.build_system_prefix()
    assert "Spanish" not in prefix
    assert "español" not in prefix.lower()


# ── generate.py passthrough ──────────────────────────────────────

def _run_generate(language=None):
    """Drive generate_brief with a stubbed client; return the request kwargs."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    import generate

    message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="# ALKIRA OPPORTUNITY BRIEF\n")],
        stop_reason="end_turn",
        usage=SimpleNamespace(
            input_tokens=1,
            output_tokens=1,
            cache_read_input_tokens=None,
            cache_creation_input_tokens=None,
        ),
    )
    client = MagicMock()
    stream = MagicMock()
    stream.__enter__.return_value.get_final_message.return_value = message
    client.messages.stream.return_value = stream

    kwargs = {} if language is None else {"language": language}
    with patch("generate.Anthropic", return_value=client), patch(
        "generate.research.research",
        return_value=SimpleNamespace(sources=[], payload="[1] src"),
    ):
        generate.generate_brief(
            "k", "t", "Acme", lambda phase: None, **kwargs
        )
    return client.messages.stream.call_args.kwargs


def test_generate_defaults_to_english():
    sent = _run_generate()
    assert "Spanish" not in sent["messages"][0]["content"]


def test_generate_passes_spanish_through_to_the_user_message():
    sent = _run_generate("es")
    assert "Spanish" in sent["messages"][0]["content"]


def test_generate_never_puts_language_in_the_cached_system_block():
    """The system block must be identical in both languages."""
    english = _run_generate("en")["system"]
    spanish = _run_generate("es")["system"]
    assert english == spanish
    assert spanish[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


# ── PDF rendering ────────────────────────────────────────────────

FULL_BRIEF = """# ALKIRA OPPORTUNITY BRIEF
## Cemex
*[Agosto 2026]*

**Alkira Fit Score: 4 / 5**
Operación multinacional con presencia en AWS y centros de datos propios.

## Infrastructure Snapshot
**Cloud Platforms:** AWS es el proveedor principal (confirmado).
**On-Prem / Hybrid:** Centros de datos en México y España (direccional).
**Deployment Model:** Híbrido, con migración de SAP en curso.
**Resulting Complexity:** Interconexión entre regiones sin diseño unificado.

## Signals & Timing
- Migración de SAP a la nube anunciada en 2026 (confirmado).
- Desinversión de activos en Asia (direccional).

## Three Alkira Entry Points
**1. Conectividad multinube**
Signal: Cargas de trabajo repartidas entre AWS y sitios propios.
Solution: Alkira une ambos entornos en una sola red.
Proof: 96% menos tiempo de conexión frente a un diseño propio.

**2. Integración tras adquisiciones**
Signal: Adquisiciones frecuentes en América Latina.
Solution: Alkira incorpora nuevas entidades sin rediseñar la red.
Proof: 98% de reducción en tiempo de integración.

**3. Segmentación**
Signal: Requisitos regulatorios por país.
Solution: Alkira aplica políticas de segmentación como capa superpuesta.
Proof: Alineado con NIST SP 800-207.

## Conversation Starters
1. ¿Cómo conectan hoy sus plantas con las aplicaciones en la nube?
2. ¿Qué tan rápido pueden integrar una empresa recién adquirida?

## References
[1] Reporte anual Cemex - https://example.com/cemex-annual
"""


def _render(language):
    from datetime import datetime

    from pdf import generate_brief_pdf

    return generate_brief_pdf(
        FULL_BRIEF, "Cemex", 4, datetime(2026, 8, 31, 12, 0), language=language
    )


def test_spanish_pdf_renders_without_crashing():
    out = _render("es")
    assert out.startswith(b"%PDF-")
    assert len(out) > 1000


def test_language_reaches_the_renderer():
    assert _render("es") != _render("en")


def test_pdf_labels_come_from_the_language_table():
    from datetime import datetime

    from pdf import _BriefPDF

    doc = _BriefPDF(datetime(2026, 8, 31), language="es")
    assert doc.labels is i18n.LABELS["es"]
    assert _BriefPDF(datetime(2026, 8, 31)).labels is i18n.LABELS["en"]


def test_spanish_pdf_contains_spanish_chrome_and_content():
    """Read the rendered text back so a label regression cannot hide."""
    import io

    pypdf = pytest.importorskip("pypdf")

    reader = pypdf.PdfReader(io.BytesIO(_render("es")))
    text = "\n".join(page.extract_text() for page in reader.pages)

    for expected in (
        "CONFIDENCIAL",
        "AGOSTO 2026",
        "SEÑALES Y OPORTUNIDAD",
        "PLATAFORMAS CLOUD",
        "MODELO DE DESPLIEGUE",
        "TRES PUNTOS DE ENTRADA ALKIRA",
        "TEMAS DE CONVERSACIÓN",
        "REFERENCIAS",
        "Página",
    ):
        assert expected in text, f"missing Spanish chrome: {expected!r}"

    # Accented Spanish body content must survive latin-1, not become '?'.
    assert "Híbrido" in text
    assert "migración" in text

    for leaked in ("SIGNALS & TIMING", "CONVERSATION STARTERS", "CLOUD PLATFORMS"):
        assert leaked not in text, f"English chrome leaked: {leaked!r}"


def test_english_pdf_chrome_is_unchanged():
    import io

    pypdf = pytest.importorskip("pypdf")

    reader = pypdf.PdfReader(io.BytesIO(_render("en")))
    text = "\n".join(page.extract_text() for page in reader.pages)

    for expected in (
        "CONFIDENTIAL",
        "SIGNALS & TIMING",
        "CLOUD PLATFORMS",
        "THREE ALKIRA ENTRY POINTS",
        "CONVERSATION STARTERS",
        "REFERENCES",
        "Page",
    ):
        assert expected in text, f"missing English chrome: {expected!r}"


def test_spanish_brief_still_parses_through_the_english_extractors():
    """The whole design rests on this: Spanish content, English keys."""
    from app import extract_entry_points, extract_infra_cells, extract_score, extract_section

    cells = extract_infra_cells(FULL_BRIEF)
    assert all(cells.values()), f"blank infra cell: {cells}"
    assert "AWS" in cells["cloud_platforms"]

    assert extract_score(FULL_BRIEF)[0] == 4
    assert extract_section(FULL_BRIEF, "Signals & Timing").strip()
    assert extract_section(FULL_BRIEF, "Conversation Starters").strip()
    assert extract_section(FULL_BRIEF, "References").strip()

    points = extract_entry_points(FULL_BRIEF)
    assert len(points) == 3
    assert points[0]["heading"] == "Conectividad multinube"
    assert points[0]["solution"].startswith("Alkira une")


# ── Cache-safety: never serve a brief in the wrong language ──────

def test_detect_language_reads_the_spanish_date_line():
    assert i18n.detect_language(FULL_BRIEF) == "es"


def test_detect_language_returns_english_for_an_english_brief():
    english = FULL_BRIEF.replace("*[Agosto 2026]*", "*[August 2026]*")
    assert i18n.detect_language(english) == "en"


def test_detect_language_recognizes_every_spanish_month():
    for month in range(1, 13):
        period = i18n.format_period(date(2026, month, 1), "es")
        brief = f"# ALKIRA OPPORTUNITY BRIEF\n## Acme\n*[{period}]*\n"
        assert i18n.detect_language(brief) == "es", period


def test_detect_language_is_biased_to_english_when_unsure():
    assert i18n.detect_language("") == "en"
    assert i18n.detect_language("# ALKIRA OPPORTUNITY BRIEF\n## Acme\n") == "en"


def test_detect_language_ignores_a_month_deep_in_the_body():
    """Only the date line counts; a source description must not flip it."""
    brief = (
        "# ALKIRA OPPORTUNITY BRIEF\n## Acme\n*[August 2026]*\n"
        + "filler line\n" * 80
        + "[1] Informe de Agosto 2025 - https://example.com\n"
    )
    assert i18n.detect_language(brief) == "en"
