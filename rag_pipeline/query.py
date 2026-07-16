"""Basic top-k retrieval test function (Requirement 5) — embeds a query,
searches the FAISS index, and returns/prints the matching chunks with their
source_type and source_name so retrieval quality can be checked by eye.
"""

from __future__ import annotations

from rag_pipeline.embed_store import EMBED_MODEL_NAME, embed_texts, load_index


def query(text: str, top_k: int = 5, model_name: str = EMBED_MODEL_NAME) -> list[dict]:
    index, metadata = load_index()
    query_embedding = embed_texts([text], model_name)
    scores, indices = index.search(query_embedding, top_k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        results.append({**metadata[idx], "score": float(score)})
    return results


def print_query(text: str, top_k: int = 5) -> list[dict]:
    results = query(text, top_k)
    print(f'\nQuery: "{text}"  (top {top_k})')
    print("-" * 78)
    for i, r in enumerate(results, 1):
        tag = "[structured]" if r.get("is_structured") else "[prose]"
        print(f"[{i}] score={r['score']:.3f}  {tag}  {r['source_type']} | {r['source_name']} | date={r['date']}")
        preview = r["text"][:220].replace("\n", " ")
        print(f"    {preview}{'...' if len(r['text']) > 220 else ''}")
        print()
    return results


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "recurring causes of fatal accidents in steel plants"
    print_query(q)
