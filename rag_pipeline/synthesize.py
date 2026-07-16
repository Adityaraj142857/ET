"""Synthesis layer: retrieves top-k chunks across all source_types for a
query and asks an LLM to identify recurring patterns, attributing each
pattern to the source_type(s) it draws from and clearly distinguishing real
sources from fabricated near-miss data.
"""

from __future__ import annotations

from rag_pipeline import llm_client
from rag_pipeline.query import query as retrieve

SYSTEM_PROMPT = """You are a safety-intelligence analyst reviewing retrieved documents \
for a coke oven battery risk-detection system. You will be given a user question and a \
numbered list of retrieved text chunks, each labeled with its source_type:

- regulation: real statutory/standards text (e.g. Factories Act, OISD standards)
- incident_data: real structured accident statistics from Parliamentary records
- incident_narrative: real narrative accounts of accidents (e.g. press releases)
- near_miss_synthetic: FABRICATED near-miss reports written for this demo project. \
These are NOT real recorded incidents and must never be described as if they happened.

Your task:
1. Identify recurring patterns across the retrieved chunks that are relevant to the \
user's question.
2. Present findings as short plain-language bullet points.
3. For each bullet, end with the source_type(s) it draws from in square brackets, e.g.:
   "Pattern: hot-work permits issued without verifying current gas readings \
[near_miss_synthetic, incident_narrative]"
4. Explicitly and clearly distinguish points drawn only from real sources (regulation, \
incident_data, incident_narrative) from points that draw on near_miss_synthetic data. \
Never phrase a synthetic-only point as if it describes a real recorded incident -- use \
language like "a simulated near-miss scenario suggests..." rather than "a past incident \
showed...".
5. If the retrieved chunks are insufficient to support a confident pattern for the \
question asked, say so plainly instead of inventing one.

Base your answer only on the retrieved chunks provided -- do not use outside knowledge."""


def _format_chunks(chunks: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(chunks, 1):
        blocks.append(
            f"[{i}] source_type={c['source_type']} | source_name={c['source_name']} | "
            f"date={c['date']}\n{c['text']}"
        )
    return "\n\n".join(blocks)


def synthesize(query_text: str, top_k: int = 8) -> dict:
    chunks = retrieve(query_text, top_k=top_k)
    user_prompt = f'User question: "{query_text}"\n\nRetrieved chunks:\n\n{_format_chunks(chunks)}'
    answer = llm_client.chat(SYSTEM_PROMPT, user_prompt)
    return {"query": query_text, "answer": answer, "chunks": chunks}


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "what patterns precede fatal accidents in steel plants"
    result = synthesize(q)
    print(f'\nQuery: "{result["query"]}"')
    print("=" * 78)
    print(result["answer"])
