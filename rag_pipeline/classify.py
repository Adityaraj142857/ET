"""Classifies a source document into (source_type, source_name, date).

Deliberately content-driven (regex over the extracted text), not a filename
lookup table — the folder's actual filenames (lu288.pdf, ru146.pdf, ...) are
opaque IDs, not descriptive names, and the user has said more files (synthetic
near-miss reports, possibly news text) will be dropped in later. A classifier
that only recognized today's six files by name would silently misclassify
everything added afterward.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SOURCE_TYPES = ("regulation", "incident_data", "incident_narrative", "near_miss_synthetic")

_DATE_PATTERNS = (
    r"\d{1,2}[-\s][A-Za-z]{3,9}[-\s]\d{4}",  # 20-February-2014
    r"\d{1,2}[/.]\d{1,2}[/.]\d{4}",  # 24/06/2019
    r"\b(?:19|20)\d{2}\b",  # bare year, last resort
)


@dataclass(frozen=True)
class SourceMeta:
    source_type: str
    source_name: str
    date: str | None  # rough date/year as found in the text; None if not identifiable


def _extract_date(text: str, pattern: str | None = None) -> str | None:
    for p in ([pattern] if pattern else _DATE_PATTERNS):
        if p is None:
            continue
        m = re.search(p, text)
        if m:
            return m.group(1) if m.lastindex else m.group(0)
    return None


def classify(filename: str, text: str) -> SourceMeta:
    """`filename` is only used as a last-resort label/type hint (e.g. the
    .txt extension for near-miss reports); classification itself reads the
    document's own text."""
    head = text[:3000]
    upper = head.upper()
    full_upper = text.upper()  # some markers (e.g. a long table of contents) push past `head`

    # Parliamentary Q&A with tabulated plant-wise/year-wise accident data.
    house_match = re.search(r"(LOK SABHA|RAJYA SABHA)", upper)
    question_match = re.search(r"UNSTARRED QUESTION NO[.:]?\s*(\d+)", upper)
    if house_match and question_match:
        house = "Lok Sabha" if "LOK" in house_match.group(1) else "Rajya Sabha"
        date = _extract_date(head, pattern=r"FOR ANSWER ON\s+(\d{1,2}[/.]\d{1,2}[/.]\d{4})")
        return SourceMeta(
            source_type="incident_data",
            source_name=f"{house} Unstarred Question No. {question_match.group(1)}",
            date=date,
        )

    # PIB press release.
    if "PRESS INFORMATION BUREAU" in upper:
        date = _extract_date(head, pattern=r"\d{1,2}-[A-Za-z]{3,9}-\d{4}")
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), filename)
        return SourceMeta(source_type="incident_narrative", source_name=first_line, date=date)

    # The Factories Act, 1948 -- any edition/annotation level. The title
    # itself is always near the top, but a long "arrangement of sections"
    # table of contents in some editions pushes the confirming phrase
    # ("An Act to consolidate...", "63 of 1948") well past `head`.
    if "FACTORIES ACT" in upper and ("CONSOLIDATE AND AMEND" in full_upper or "63 OF 1948" in full_upper):
        variant = "annotated, with State Amendments" if "STATE AMENDMENTS" in full_upper else "bare text"
        return SourceMeta(source_type="regulation", source_name=f"The Factories Act, 1948 ({variant})", date="1948")

    # OISD standards index/list.
    if "OISD" in upper:
        return SourceMeta(source_type="regulation", source_name="OISD Standards & Guidelines Index", date=None)

    # .txt files the user will add later: near-miss reports by default,
    # unless they read as a news/press item.
    if filename.lower().endswith(".txt"):
        if "PRESS INFORMATION BUREAU" in upper or re.search(r"\bNEWS\b", upper):
            return SourceMeta(source_type="incident_narrative", source_name=filename, date=_extract_date(head))
        return SourceMeta(source_type="near_miss_synthetic", source_name=filename, date=_extract_date(head))

    # Unrecognized PDF -- best-effort fallback; a None date flags that this
    # document didn't match any known pattern and may need a human look.
    return SourceMeta(source_type="incident_narrative", source_name=filename, date=_extract_date(head))
