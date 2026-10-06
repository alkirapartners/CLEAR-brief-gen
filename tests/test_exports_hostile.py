"""Neither export may fail on what a model can write: every string in a brief is untrusted."""

import copy
import io
from datetime import datetime

import pytest
from docx import Document

import docx_doc
import pdf_doc
from tests import export_readers as readers
from tests.brief_fixtures import SAMPLE_DOC

WHEN = datetime(2026, 10, 5, 12, 0)
# Fields whose values are fixed by the schema, not written freely.
FIXED = frozenset({"format", "version", "language", "score", "use_case", "deal_status", "source_type", "id"})
HOSTILE = {
    "empty": "",
    "one very long word": "A" * 3000,
    "a long address": "https://example.com/" + "path/" * 300,
    "another script": "安克创新 العربية Ελληνικά " * 20,
    "emoji only": "🚀🎉",
    "control characters": "nul\x00 bell\x07 vertical tab\x0b newline\n tab\t",
    "stray combining marks": "e\u0301\u0301\u0301 o\u0308",
    "half a surrogate pair": "broken \ud83d emoji",
    "markup": '</w:t><w:fldSimple w:instr="DDEAUTO cmd"/> <script>x</script> &amp; { PAGE }',
    "a pdf destination": "#top",
}


def _everywhere(value: object, text: str) -> object:
    """The document with every freely written string replaced by ``text``."""
    if isinstance(value, str):
        return text
    if isinstance(value, list):
        return [_everywhere(item, text) for item in value]
    if isinstance(value, dict):
        return {key: item if key in FIXED else _everywhere(item, text) for key, item in value.items()}
    return value


@pytest.mark.parametrize("text", HOSTILE.values(), ids=list(HOSTILE))
def test_both_exports_render_whatever_every_field_holds(text):
    doc = _everywhere(copy.deepcopy(SAMPLE_DOC), text)
    printed = pdf_doc.render(doc, WHEN)
    assert printed.startswith(b"%PDF-") and readers.pdf_pages(printed)
    assert readers.pdf_web_links(printed) == [] or text.startswith("https://")
    word = docx_doc.render(doc, WHEN)
    Document(io.BytesIO(word))  # opens
    assert "<w:fldSimple" not in readers.docx_xml(word)["word/document.xml"]
    assert all(target.startswith("https://example.com/") for _, target in readers.docx_external_targets(word))
