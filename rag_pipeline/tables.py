"""Structured extraction for the tabulated plant-wise/year-wise accident
data in the parliamentary Q&A PDFs (Requirement 2) — turns each PDF table
into long-format rows: {plant, section, state, year, metric, value}, one row
per number in the table, instead of dumping the table as unstructured prose.

The two known source tables (Lok Sabha Q.288, Rajya Sabha Q.146) have
different shapes (different metric names, different year ranges, a "State"
column present in one but not the other, metric-row/year-row in a different
top-to-bottom order between the two), so this is a fairly generic
"long-format melt" rather than a schema hardcoded to one table. It works
directly off pdfplumber's raw `page.extract_table()` grid:

  1. Classify every row as HEADER, BANNER, or DATA:
       - DATA:   has at least one "count" cell (a small number that isn't a
                 plausible year).
       - BANNER: no count cells, and at most one non-empty cell (e.g. a
                 "STEEL AUTHORITY OF INDIA LIMITED (SAIL)" section title
                 row spanning the table) — remembered as running context,
                 not emitted as its own record.
       - HEADER: no count cells, two or more non-empty cells (column
                 labels, or bare years like "2016" which read as numeric
                 but aren't counts).
  2. Header rows are forward-filled left-to-right before being merged into
     a single per-column header string — pdfplumber represents a merged
     header cell (one year spanning an "Accidents"/"Persons died" pair) as
     the value once followed by None, not repeated.
  3. The label column count (State, Plant/Unit, ...) is read off the first
     DATA row: everything before its first count cell is a label column.
  4. Each column header is split into (year, metric) by regexing out a
     19xx/20xx year; whatever's left is the metric name.

This is verified against the two real tables in RAG/, not a fully general
table-schema inference engine — a differently-shaped future table may need
this logic adjusted, which is exactly the kind of limitation this module
should flag rather than silently mis-parse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_NUMERIC_RE = re.compile(r"^-?\d[\d,]*\.?\d*$")
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_BARE_YEAR_RE = re.compile(r"^(19|20)\d{2}$")


@dataclass
class TableRow:
    source_name: str
    plant: str
    section: str | None  # e.g. "Steel Authority Of India Limited (SAIL)", from a banner row
    state: str | None
    year: str | None
    metric: str
    value: float
    sentence: str = field(default="")

    def __post_init__(self) -> None:
        if not self.sentence:
            self.sentence = self._render()

    def _render(self) -> str:
        where = self.plant + (f" ({self.state})" if self.state else "")
        who = f" [{self.section}]" if self.section else ""
        when = f" in {self.year}" if self.year else ""
        return f"At {where}{who}{when}, {self.metric}: {self.value:g}."


def _clean(cell) -> str:
    return (cell or "").replace("\n", " ").strip()


def _is_numeric(cell: str) -> bool:
    return bool(cell) and bool(_NUMERIC_RE.match(cell))


def _is_year_cell(cell: str) -> bool:
    return bool(cell) and bool(_BARE_YEAR_RE.match(cell))


def _is_count_cell(cell: str) -> bool:
    return _is_numeric(cell) and not _is_year_cell(cell)


def _forward_fill(row: list[str]) -> list[str]:
    """Left-to-right fill for merged header cells (pdfplumber represents a
    cell spanning N columns as the value once, then N-1 empty cells)."""
    filled = list(row)
    last = ""
    for i, cell in enumerate(filled):
        if cell:
            last = cell
        else:
            filled[i] = last
    return filled


def melt_table(grid: list[list], source_name: str) -> tuple[list[TableRow], list[str]]:
    """Returns (rows, warnings). `grid` is pdfplumber's raw
    page.extract_table() result (list of rows, each a list of cell strings
    or None)."""
    warnings: list[str] = []
    grid = [[_clean(c) for c in row] for row in grid if any(_clean(c) for c in row)]
    if not grid:
        return [], ["empty table grid"]

    n_cols = max(len(row) for row in grid)
    grid = [row + [""] * (n_cols - len(row)) for row in grid]

    col_headers = [""] * n_cols
    running_section: str | None = None
    current_labels: list[str] = []
    label_col_count: int | None = None
    rows: list[TableRow] = []

    for row in grid:
        count_cells = [c for c in row if _is_count_cell(c)]
        non_empty = [c for c in row if c]

        if not count_cells and len(non_empty) <= 1:
            # Banner / section-title row.
            if non_empty:
                running_section = non_empty[0]
            continue

        if not count_cells:
            # Header row (possibly a bare-year row) -- fold into the
            # running per-column header, forward-filling merged cells.
            filled = _forward_fill(row)
            for c in range(n_cols):
                if filled[c]:
                    col_headers[c] = f"{col_headers[c]} {filled[c]}".strip()
            continue

        # First real data row fixes where labels end and values begin.
        if label_col_count is None:
            label_col_count = next((i for i, c in enumerate(row) if _is_count_cell(c)), 1)
            label_col_count = max(1, label_col_count)
            current_labels = [""] * label_col_count

        label_cells = row[:label_col_count]
        data_cells = row[label_col_count:]
        for i, v in enumerate(label_cells):
            if v:
                current_labels[i] = v
        plant = current_labels[-1] or "Unknown"
        state = current_labels[0] if label_col_count > 1 and current_labels[0] != plant else None
        section = running_section
        if "TOTAL" in plant.upper():
            # A (grand) total row aggregates across states/sections, so
            # carrying forward the state/section of the row above it (an
            # artifact of vertical merged-cell carry-forward) would be
            # actively misleading rather than merely imprecise.
            state = None
            section = None

        for c, v in enumerate(data_cells):
            if not _is_count_cell(v):
                continue
            header = col_headers[label_col_count + c]
            year_match = _YEAR_RE.search(header)
            year = year_match.group(0) if year_match else None
            metric = header.replace(year, "", 1).strip(" -/") if year else header
            metric = metric or "value"
            rows.append(
                TableRow(
                    source_name=source_name,
                    plant=plant,
                    section=section,
                    state=state,
                    year=year,
                    metric=metric,
                    value=float(v.replace(",", "")),
                )
            )

    if not rows:
        warnings.append("no data rows with parseable count cells were found in this table")
    return rows, warnings
