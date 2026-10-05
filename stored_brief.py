"""Read a stored brief without caring which format it is.

A row's ``brief_md`` holds either a JSON brief document or legacy markdown.
The service, the PDF route and the views ask their questions here.
"""

import brief_doc
import i18n
from briefparse import clean_brief, extract_company_header, extract_score


def normalise(raw: str) -> str:
    """The text to store: a JSON brief as it is, legacy markdown cleaned."""
    if brief_doc.is_json_brief(raw):
        return raw.strip()
    return clean_brief(raw)


def language_of(stored: str | None) -> str:
    """The language a stored brief was written in."""
    doc = brief_doc.load(stored)
    if doc is not None:
        return i18n.normalize(doc["language"])
    return i18n.detect_language(stored or "")


def score_and_company(stored: str) -> tuple[int, str]:
    """The fit score and the company name the brief itself gives."""
    doc = brief_doc.load(stored)
    if doc is not None:
        return doc["fit"]["score"], doc["company"]["name"].strip()
    score, _ = extract_score(stored)
    company, _ = extract_company_header(stored)
    return score, company
