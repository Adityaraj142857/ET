"""Embeds chunks with a local sentence-transformers model and stores them in
a FAISS flat index, alongside a parallel JSONL sidecar of chunk text +
metadata (FAISS itself only stores vectors, not payloads) (Requirement 4).

Model: sentence-transformers/all-mpnet-base-v2 -- fully local, no API key,
no network calls at query time (~420MB, downloaded once). Tried the smaller
all-MiniLM-L6-v2 (~80MB) first; A/B'd both against the required test query
("recurring causes of fatal accidents in steel plants") and MiniLM buried
the one chunk that actually names causes (fall from height, gas poisoning,
electrocution...) at rank 75/331, swamped by short structured "Fatal
Accidents: N" chunks that share the query's literal words without being
about causes at all. mpnet ranks that same chunk #2/5. Slower to embed
(~2 min vs ~5s for this corpus) and 2x the vector size (768 vs 384-dim),
both irrelevant at this corpus's few-hundred-chunk scale and a non-issue at
query time (embedding one query sentence is instant either way).

Vectors are L2-normalized so a plain inner-product FAISS index
(IndexFlatIP) is equivalent to cosine similarity, and the index is exact
(no approximation) since a few hundred/thousand chunks is well within
IndexFlatIP's comfortable range -- no need for IVF/HNSW at this scale.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from rag_pipeline.chunk import Chunk

EMBED_MODEL_NAME = "sentence-transformers/all-mpnet-base-v2"

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_DIR = REPO_ROOT / "rag_pipeline" / "index"
INDEX_PATH = INDEX_DIR / "chunks.faiss"
METADATA_PATH = INDEX_DIR / "chunks.jsonl"

_model_cache: dict[str, SentenceTransformer] = {}


def get_model(model_name: str = EMBED_MODEL_NAME) -> SentenceTransformer:
    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def embed_texts(texts: list[str], model_name: str = EMBED_MODEL_NAME) -> np.ndarray:
    model = get_model(model_name)
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=len(texts) > 20,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return embeddings.astype("float32")


def build_index(chunks: list[Chunk], model_name: str = EMBED_MODEL_NAME) -> None:
    if not chunks:
        raise ValueError("no chunks to index")
    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    embeddings = embed_texts([c.text for c in chunks], model_name)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)
    faiss.write_index(index, str(INDEX_PATH))

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c)) + "\n")

    print(f"Wrote {len(chunks)} chunks -> {INDEX_PATH.relative_to(REPO_ROOT)} + {METADATA_PATH.relative_to(REPO_ROOT)} ({dim}-dim)")


def load_index() -> tuple[faiss.Index, list[dict]]:
    if not INDEX_PATH.exists() or not METADATA_PATH.exists():
        raise FileNotFoundError(f"No index found at {INDEX_PATH} -- run `uv run python -m rag_pipeline.build_index` first.")
    index = faiss.read_index(str(INDEX_PATH))
    metadata = [json.loads(line) for line in METADATA_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return index, metadata
