import { useState } from "react";

interface Chunk {
  text: string;
  source_type: string;
  source_name: string;
  date: string | null;
  score: number;
  is_structured?: boolean;
}

interface SynthesizeResponse {
  query: string;
  answer: string;
  chunks: Chunk[];
}

const EXAMPLE_QUERIES = [
  "what patterns precede fatal accidents in steel plants",
  "common failures in permit-to-work systems",
  "gas leak detection and response near coke oven batteries",
];

export function SafetyIntelligence() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SynthesizeResponse | null>(null);
  const [showChunks, setShowChunks] = useState(false);

  async function runQuery(text: string) {
    if (!text.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: text, top_k: 8 }),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data: SynthesizeResponse = await res.json();
      setResult(data);
      setShowChunks(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rag-panel">
      <div className="rag-panel__intro">
        <p className="muted">
          Ask a question and retrieve patterns synthesized from regulations, real incident
          records, and near-miss reports.
        </p>
        <span className="synthetic-badge">
          NEAR-MISS DATA IS SYNTHETIC — LIMITED DEMO CORPUS, NOT A COMPREHENSIVE INCIDENT DATABASE
        </span>
      </div>

      <form
        className="rag-panel__form"
        onSubmit={(e) => {
          e.preventDefault();
          runQuery(input);
        }}
      >
        <input
          className="rag-panel__input"
          type="text"
          placeholder="e.g. common failures in permit-to-work systems"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button className="rag-panel__submit" type="submit" disabled={loading}>
          {loading ? "Searching…" : "Ask"}
        </button>
      </form>

      <div className="rag-panel__examples">
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            className="rag-panel__example-chip"
            onClick={() => {
              setInput(q);
              runQuery(q);
            }}
            disabled={loading}
          >
            {q}
          </button>
        ))}
      </div>

      {error && <div className="rag-panel__error">{error}</div>}

      {result && (
        <div className="rag-panel__result">
          <h3 className="rag-panel__result-heading">Synthesized findings</h3>
          <pre className="rag-panel__answer">{result.answer}</pre>

          <button
            className="rag-panel__toggle-chunks"
            onClick={() => setShowChunks((v) => !v)}
          >
            {showChunks ? "▾ Hide" : "▸ Show"} {result.chunks.length} raw retrieved chunk
            {result.chunks.length === 1 ? "" : "s"}
          </button>

          {showChunks && (
            <ul className="rag-panel__chunks">
              {result.chunks.map((c, i) => (
                <li key={i} className="rag-panel__chunk">
                  <div className="rag-panel__chunk-meta">
                    <span
                      className={`rag-panel__source-tag rag-panel__source-tag--${c.source_type}`}
                    >
                      {c.source_type}
                    </span>
                    <span className="muted">{c.source_name}</span>
                    {c.date && <span className="muted">· {c.date}</span>}
                    <span className="muted">· score {c.score.toFixed(3)}</span>
                  </div>
                  <p className="rag-panel__chunk-text">{c.text}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
