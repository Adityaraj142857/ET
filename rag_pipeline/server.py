"""Minimal HTTP bridge exposing the RAG synthesis layer to the browser UI.

Run with: uv run uvicorn rag_pipeline.server:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rag_pipeline.synthesize import synthesize

app = FastAPI(title="Compound Risk Detection — Safety Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SynthesizeRequest(BaseModel):
    query: str
    top_k: int = 8


@app.post("/api/synthesize")
def post_synthesize(req: SynthesizeRequest) -> dict:
    return synthesize(req.query, top_k=req.top_k)
