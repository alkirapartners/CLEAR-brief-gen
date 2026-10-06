"""The PDF and the Word document are two layouts of one brief: they must say the same things."""

import copy
from datetime import datetime

import pytest

import docx_doc
import export_content
import i18n
import pdf_doc
from tests import export_readers as readers
from tests.brief_fixtures import SAMPLE_DOC, make_doc

WHEN = datetime(2026, 10, 5, 12, 0)


def _three_angles():
    third = {
        **copy.deepcopy(SAMPLE_DOC["angles"][0]),
        "title": "Firewalls copied per hub",
        "use_case": "firewall_consolidation",
        "story": {"id": "metric", "customer": "", "result": "Firewall reduction: 73% (up to 82% in some accounts)."},
    }
    return make_doc(angles=[*copy.deepcopy(SAMPLE_DOC["angles"]), third])


def _no_angles():
    fit = {"score": 2, "verdict": "No use case with evidence that stands.", "lead": ""}
    return make_doc(angles=[], fit=fit, questions=[])


BRIEFS = {
    "no angles": _no_angles,
    "one angle": lambda: make_doc(angles=make_doc()["angles"][:1]),
    "two angles": make_doc,
    "three angles": _three_angles,
    "spanish": lambda: make_doc(language="es"),
    "nothing but the verdict": lambda: make_doc(
        angles=[], questions=[], people=[], unconfirmed=[], raise_score=[], references=[],
    ),
}


@pytest.fixture(params=BRIEFS, ids=list(BRIEFS))
def exported(request):
    doc = BRIEFS[request.param]()
    return doc, readers.pdf_text(pdf_doc.render(doc, WHEN)), pdf_doc.render(doc, WHEN), docx_doc.render(doc, WHEN)


def _positions(text: str, headings: list[str]) -> list[int]:
    """Where each heading first appears, looking only after the one before it."""
    found, start = [], 0
    for heading in headings:
        start = text.casefold().index(heading.casefold(), start)
        found.append(start)
    return found


def test_both_exports_carry_the_same_section_headings_in_the_same_order(exported):
    doc, pdf_text, _, word = exported
    headings = [section.heading for section in export_content.outline(doc, i18n.labels(doc["language"]))]
    assert [text for style, text in readers.docx_headings(word) if style == "Heading 1"] == headings
    # The PDF sets the first of them as an uppercase label, so case is not compared.
    assert _positions(pdf_text, headings) == sorted(_positions(pdf_text, headings))
    for section in ("why_now", "ask_this", "who_to_talk_to", "unconfirmed", "raise_score", "references"):
        heading = i18n.labels(doc["language"])[section]
        if heading not in headings:
            assert heading.casefold() not in pdf_text.casefold()
            assert heading not in readers.docx_text(word)


def test_both_exports_carry_every_angle_question_and_reference(exported):
    doc, pdf_text, _, word = exported
    word_text = readers.docx_text(word)
    wanted = [angle["title"] for angle in doc["angles"]]
    wanted += [angle["alkira"] for angle in doc["angles"]]
    wanted += [line["text"] for angle in doc["angles"] for line in angle["evidence"]]
    wanted += [item[key] for item in doc["questions"] for key in ("question", "listen_for", "alkira_angle")]
    wanted += [reference["title"] for reference in doc["references"]]
    wanted += [*doc["unconfirmed"], *doc["raise_score"], doc["fit"]["verdict"]]
    wanted += [person["role"] for person in doc["people"]]
    for text in wanted:
        assert text in pdf_text, f"missing from the PDF: {text!r}"
        assert text in word_text, f"missing from the Word document: {text!r}"


def test_both_exports_link_the_same_pages(exported):
    doc, _, pdf_bytes, word = exported
    expected = [doc["company"]["website"], *(reference["url"] for reference in doc["references"])]
    assert readers.docx_links(word) == expected
    assert sorted(readers.pdf_web_links(pdf_bytes)) == sorted(expected)
