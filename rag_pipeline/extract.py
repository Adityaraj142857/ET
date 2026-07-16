"""Reads every file in RAG/, classifies it, and extracts either plain text
(Requirement 1) or, for the tabulated accident-data PDFs, structured table
rows on top of the surrounding prose (Requirement 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pdfplumber

from rag_pipeline.classify import SourceMeta, classify
from rag_pipeline.tables import TableRow, melt_table

REPO_ROOT = Path(__file__).resolve().parent.parent
RAG_DIR = REPO_ROOT / "RAG"


@dataclass
class Document:
    meta: SourceMeta
    text: str
    table_rows: list[TableRow]
    table_warnings: list[str]


def _read_pdf_by_page(path: Path) -> tuple[list[str], list[list[list]]]:
    """Returns (text_per_page, table_grids_per_page)."""
    pages_text: list[str] = []
    pages_grids: list[list[list]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            pages_text.append(page.extract_text() or "")
            pages_grids.append(page.extract_tables())
    return pages_text, pages_grids


def load_documents(rag_dir: Path = RAG_DIR) -> list[Document]:
    if not rag_dir.exists():
        raise FileNotFoundError(f"RAG source folder not found: {rag_dir}")

    documents: list[Document] = []
    for path in sorted(rag_dir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            pages_text, pages_grids = _read_pdf_by_page(path)
        elif suffix in (".txt", ".md"):
            pages_text, pages_grids = [path.read_text(encoding="utf-8", errors="replace")], [[]]
        else:
            print(f"  skipping {path.name}: unsupported file type ({suffix})")
            continue

        full_text = "\n".join(pages_text)
        meta = classify(path.name, full_text)

        table_rows: list[TableRow] = []
        table_warnings: list[str] = []
        # A page is "consumed" by successful structured extraction (its raw
        # text is dropped from the prose pool) only once we know its table
        # actually melted into rows -- a page with a table pdfplumber
        # couldn't parse still keeps its raw text, per Requirement 2's
        # "fall back to chunked text" instruction.
        consumed_pages = [False] * len(pages_text)
        if meta.source_type == "incident_data":
            for page_i, grids in enumerate(pages_grids):
                for grid in grids:
                    rows, warnings = melt_table(grid, meta.source_name)
                    if rows:
                        table_rows.extend(rows)
                        consumed_pages[page_i] = True
                    else:
                        table_warnings.extend(
                            f"page {page_i}: {w}" for w in warnings
                        )
            if not table_rows:
                table_warnings.append(
                    "no structured rows extracted at all for this incident_data source "
                    "-- falling back to plain chunked text for its table content"
                )

        prose_text = "\n".join(t for t, consumed in zip(pages_text, consumed_pages) if not consumed)
        documents.append(Document(meta=meta, text=prose_text, table_rows=table_rows, table_warnings=table_warnings))

    return documents
