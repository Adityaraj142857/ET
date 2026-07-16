"""Ingestion entry point (Requirement 1): reads every file in RAG/,
classifies + extracts + chunks + embeds it, and writes the FAISS index +
metadata sidecar to rag_pipeline/index/.

Run as:
    uv run python -m rag_pipeline.build_index
"""

from __future__ import annotations

from collections import Counter

from rag_pipeline.chunk import chunk_document
from rag_pipeline.embed_store import EMBED_MODEL_NAME, build_index
from rag_pipeline.extract import load_documents


def main() -> None:
    print("Loading + classifying documents from RAG/ ...")
    documents = load_documents()

    all_chunks = []
    print(f"\n{'source_name':60} {'source_type':20} {'date':14} {'chunks':>7}")
    print("-" * 105)
    for doc in documents:
        chunks = chunk_document(doc, EMBED_MODEL_NAME)
        all_chunks.extend(chunks)
        print(f"{doc.meta.source_name:60.60} {doc.meta.source_type:20} {str(doc.meta.date):14} {len(chunks):>7}")
        for w in doc.table_warnings:
            print(f"    !! {w}")

    print(f"\nTotal chunks: {len(all_chunks)}")
    for t, n in Counter(c.source_type for c in all_chunks).items():
        print(f"  {t}: {n}")
    structured_count = sum(1 for c in all_chunks if c.is_structured)
    print(f"  (of which structured table-row chunks: {structured_count})")

    print(f"\nEmbedding with {EMBED_MODEL_NAME} and building the FAISS index ...")
    build_index(all_chunks)


if __name__ == "__main__":
    main()
