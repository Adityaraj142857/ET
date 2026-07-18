import { useEffect, useRef, useState } from "react";
import { useSimulationStore } from "../store/simulationStore";

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

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  chunks?: Chunk[];
  error?: boolean;
}

const EXAMPLE_QUERIES = [
  "what patterns precede fatal accidents in steel plants",
  "common failures in permit-to-work systems",
  "gas leak detection and response near coke oven batteries",
];

// How many prior messages (user + assistant) to fold into the retrieval
// query so follow-ups like "what about permit-related ones specifically"
// have enough context to resolve — without changing anything server-side.
const HISTORY_MESSAGES_FOR_CONTEXT = 6;

function buildContextualQuery(history: ChatMessage[], question: string): string {
  const recent = history.slice(-HISTORY_MESSAGES_FOR_CONTEXT).filter((m) => !m.error);
  if (recent.length === 0) return question;

  const transcript = recent
    .map((m) => `${m.role === "user" ? "Q" : "A"}: ${m.text}`)
    .join("\n");

  return `Conversation so far:\n${transcript}\n\nFollow-up question: ${question}`;
}

function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function SafetyIntelligence() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [openChunksFor, setOpenChunksFor] = useState<Set<string>>(new Set());
  const historyRef = useRef<HTMLDivElement>(null);

  const pendingAssistantQuery = useSimulationStore((s) => s.pendingAssistantQuery);
  const clearPendingAssistantQuery = useSimulationStore((s) => s.clearPendingAssistantQuery);

  // Cross-link handoff from the Live Simulation detail panel: pre-fill the
  // input but never auto-submit, so the operator can review/edit first.
  useEffect(() => {
    if (pendingAssistantQuery) {
      setInput(pendingAssistantQuery);
      clearPendingAssistantQuery();
    }
  }, [pendingAssistantQuery, clearPendingAssistantQuery]);

  useEffect(() => {
    historyRef.current?.scrollTo({ top: historyRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function runQuery(text: string) {
    const question = text.trim();
    if (!question || loading) return;

    const userMessage: ChatMessage = { id: makeId(), role: "user", text: question };
    const historyForContext = messages;
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const composedQuery = buildContextualQuery(historyForContext, question);
      const res = await fetch("/api/synthesize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: composedQuery, top_k: 8 }),
      });
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data: SynthesizeResponse = await res.json();
      setMessages((prev) => [
        ...prev,
        { id: makeId(), role: "assistant", text: data.answer, chunks: data.chunks },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          id: makeId(),
          role: "assistant",
          text: e instanceof Error ? e.message : "Request failed",
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function toggleChunks(id: string) {
    setOpenChunksFor((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
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

      <div className="rag-chat">
        <div className="rag-chat__history" ref={historyRef}>
          {messages.length === 0 && (
            <div className="rag-chat__empty">
              <p className="muted">
                No messages yet — ask a question below, or try one of these:
              </p>
              <div className="rag-panel__examples">
                {EXAMPLE_QUERIES.map((q) => (
                  <button
                    key={q}
                    className="rag-panel__example-chip"
                    onClick={() => runQuery(q)}
                    disabled={loading}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((m) =>
            m.role === "user" ? (
              <div key={m.id} className="rag-chat__row rag-chat__row--user">
                <div className="rag-chat__bubble rag-chat__bubble--user">{m.text}</div>
              </div>
            ) : (
              <div key={m.id} className="rag-chat__row rag-chat__row--assistant">
                <div
                  className={`rag-chat__bubble rag-chat__bubble--assistant${
                    m.error ? " rag-chat__bubble--error" : ""
                  }`}
                >
                  {m.error ? (
                    <p className="rag-panel__error">{m.text}</p>
                  ) : (
                    <>
                      <pre className="rag-panel__answer">{m.text}</pre>

                      {m.chunks && m.chunks.length > 0 && (
                        <>
                          <button
                            className="rag-panel__toggle-chunks"
                            onClick={() => toggleChunks(m.id)}
                          >
                            {openChunksFor.has(m.id) ? "▾ Hide" : "▸ Show"} {m.chunks.length} raw
                            retrieved chunk
                            {m.chunks.length === 1 ? "" : "s"}
                          </button>

                          {openChunksFor.has(m.id) && (
                            <ul className="rag-panel__chunks">
                              {m.chunks.map((c, i) => (
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
                        </>
                      )}
                    </>
                  )}
                </div>
              </div>
            )
          )}

          {loading && (
            <div className="rag-chat__row rag-chat__row--assistant">
              <div className="rag-chat__bubble rag-chat__bubble--assistant rag-chat__bubble--pending">
                Retrieving and synthesizing…
              </div>
            </div>
          )}
        </div>

        <form
          className="rag-chat__form"
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
      </div>
    </div>
  );
}
