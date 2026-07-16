"""Chunks extracted document text into overlapping ~300-500 token segments,
carrying source_type/source_name/date metadata on every chunk (Requirement 3).

Chunking tokenizes the full text with the SAME tokenizer the embedding
model uses (so "300-500 tokens" means exactly what the model will see, not
a word-count estimate), then slides a fixed-size window over the token ids
with a stride shorter than the window -- the overlap. Windows are decoded
back to text for storage/embedding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from transformers import AutoTokenizer

from rag_pipeline.extract import Document

CHUNK_TOKENS = 420  # within the requested 300-500 range
CHUNK_OVERLAP_TOKENS = 90

_tokenizer_cache: dict[str, Any] = {}


def _get_tokenizer(model_name: str):
    if model_name not in _tokenizer_cache:
        _tokenizer_cache[model_name] = AutoTokenizer.from_pretrained(model_name)
    return _tokenizer_cache[model_name]


@dataclass
class Chunk:
    text: str
    source_type: str
    source_name: str
    date: str | None
    chunk_index: int
    n_tokens: int
    is_structured: bool = False
    structured_fields: dict | None = None


def _sliding_index_windows(n: int, size: int, overlap: int) -> list[tuple[int, int]]:
    """(start, end) token-index ranges, end exclusive, over a sequence of length n."""
    if n <= size:
        return [(0, n)] if n else []
    stride = size - overlap
    windows: list[tuple[int, int]] = []
    start = 0
    while start < n:
        end = min(start + size, n)
        windows.append((start, end))
        if end >= n:
            break
        start += stride
    return windows


def chunk_text(
    text: str,
    source_type: str,
    source_name: str,
    date: str | None,
    model_name: str,
    size: int = CHUNK_TOKENS,
    overlap: int = CHUNK_OVERLAP_TOKENS,
    index_offset: int = 0,
) -> list[Chunk]:
    text = text.strip()
    if not text:
        return []
    tokenizer = _get_tokenizer(model_name)
    # Windowing over character OFFSETS (not decode()) so a chunk's stored
    # text is a verbatim slice of the original string -- decode() round-trips
    # through the model's WordPiece vocab, which silently lowercases and
    # respaces punctuation, degrading exactly the human-readability that
    # matters for "print retrieved chunks so I can manually check them".
    encoding = tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
    offsets = encoding["offset_mapping"]
    chunks: list[Chunk] = []
    for i, (start_tok, end_tok) in enumerate(_sliding_index_windows(len(offsets), size, overlap)):
        if start_tok >= end_tok:
            continue
        char_start, char_end = offsets[start_tok][0], offsets[end_tok - 1][1]
        piece = text[char_start:char_end].strip()
        if not piece:
            continue
        chunks.append(
            Chunk(
                text=piece,
                source_type=source_type,
                source_name=source_name,
                date=date,
                chunk_index=index_offset + i,
                n_tokens=end_tok - start_tok,
            )
        )
    return chunks


def _group_key(row) -> tuple:
    return (row.plant, row.section, row.state)


def _render_group_sentence(plant: str, section: str | None, state: str | None, facts: list) -> str:
    """One chunk per plant, not per data point: a table with N plants x
    M years x K metrics emits N chunks (each mentioning all M*K numbers for
    that plant), not N*M*K near-duplicate one-number chunks. Retrieval
    quality, not just token budget, is the reason -- see the module
    docstring's note on why per-datapoint chunking crowded out prose."""
    where = plant + (f" ({state})" if state else "")
    who = f" [{section}]" if section else ""
    by_metric: dict[str, list[tuple[str | None, float]]] = {}
    for row in facts:
        by_metric.setdefault(row.metric, []).append((row.year, row.value))

    parts = [f"At {where}{who}:"]
    for metric, year_values in by_metric.items():
        year_values.sort(key=lambda t: t[0] or "")
        values = ", ".join(f"{v:g} in {y}" if y else f"{v:g}" for y, v in year_values)
        parts.append(f"{metric}: {values}.")
    return " ".join(parts)


def chunk_document(doc: Document, model_name: str) -> list[Chunk]:
    """Structured table rows (if any) are grouped by plant into one chunk
    per plant (not one chunk per data point -- see `_render_group_sentence`),
    each carrying every underlying (year, metric, value) fact in
    `structured_fields["data"]` for programmatic use even though the
    embedded text is the consolidated sentence. The surrounding prose (a
    parliamentary Q&A's actual answer text: causes, compensation, remedial
    steps) is chunked normally on top of that; the table isn't the whole
    document, and that narrative is exactly the kind of thing a "recurring
    causes" query should also retrieve."""
    chunks: list[Chunk] = []

    if doc.table_rows:
        tokenizer = _get_tokenizer(model_name)
        groups: dict[tuple, list] = {}
        for row in doc.table_rows:
            groups.setdefault(_group_key(row), []).append(row)

        for i, ((plant, section, state), facts) in enumerate(groups.items()):
            sentence = _render_group_sentence(plant, section, state, facts)
            n_tokens = len(tokenizer.encode(sentence, add_special_tokens=False))
            chunks.append(
                Chunk(
                    text=sentence,
                    source_type=doc.meta.source_type,
                    source_name=doc.meta.source_name,
                    date=doc.meta.date,
                    chunk_index=i,
                    n_tokens=n_tokens,
                    is_structured=True,
                    structured_fields={
                        "plant": plant,
                        "section": section,
                        "state": state,
                        "data": [{"year": r.year, "metric": r.metric, "value": r.value} for r in facts],
                    },
                )
            )
        chunks.extend(
            chunk_text(
                doc.text, doc.meta.source_type, doc.meta.source_name, doc.meta.date, model_name, index_offset=len(chunks)
            )
        )
        return chunks

    return chunk_text(doc.text, doc.meta.source_type, doc.meta.source_name, doc.meta.date, model_name)
