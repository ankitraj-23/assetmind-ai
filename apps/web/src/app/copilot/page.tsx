"use client";

import { useState } from "react";
import { Card, PageHeader, Badge } from "@/components/ui";
import { askQuestion, type ApiQueryResponse } from "@/lib/api";

export default function CopilotPage() {
  const [question, setQuestion] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">(
    "idle",
  );
  const [result, setResult] = useState<ApiQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setStatus("loading");
    setError(null);
    try {
      const res = await askQuestion(question.trim());
      setResult(res);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed.");
      setStatus("error");
    }
  }

  return (
    <div>
      <PageHeader
        title="Operations Copilot"
        subtitle="Ask in plain language. Answers are grounded in your indexed documents with citations."
      />

      <Card>
        <form onSubmit={handleAsk} className="flex gap-3">
          <input
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. What is the recommended seal flush plan for Pump P-101?"
            className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-4 py-2.5 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]"
          />
          <button
            type="submit"
            disabled={status === "loading" || !question.trim()}
            className="rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[var(--color-base)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {status === "loading" ? "Asking…" : "Ask"}
          </button>
        </form>

        <div className="mt-3 flex flex-wrap gap-2">
          {[
            "Which assets have overdue calibration?",
            "Summarize the C-220 trip root cause",
            "LOTO steps before pump maintenance",
          ].map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setQuestion(s)}
              className="rounded-full border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-1 text-xs text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-white"
            >
              {s}
            </button>
          ))}
        </div>
      </Card>

      {status === "error" && error && (
        <Card className="mt-6">
          <p className="text-sm text-red-400">{error}</p>
        </Card>
      )}

      {status === "done" && result && (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Question
            </p>
            <p className="mb-5 text-sm font-medium">{result.question}</p>

            <div className="mb-4 flex items-center gap-3 text-xs">
              <Badge tone="ok">confidence: {result.confidence}</Badge>
              <span className="text-[var(--color-muted)]">
                {result.retrieved_count} chunk
                {result.retrieved_count === 1 ? "" : "s"} retrieved
              </span>
            </div>

            <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Answer
            </p>
            <p className="text-sm leading-relaxed">
              {result.answer}{" "}
              {result.citations.map((c, i) => (
                <sup
                  key={c.chunk_id}
                  className="ml-0.5 text-[var(--color-accent)]"
                >
                  [{i + 1}]
                </sup>
              ))}
            </p>
          </Card>

          <Card>
            <p className="mb-3 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Citations
            </p>
            {result.citations.length === 0 ? (
              <p className="text-xs text-[var(--color-muted)]">
                No citations returned.
              </p>
            ) : (
              <ul className="space-y-3">
                {result.citations.map((c, i) => (
                  <li
                    key={c.chunk_id}
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-3"
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex h-5 w-5 items-center justify-center rounded bg-[var(--color-surface-2)] text-xs text-[var(--color-accent)]">
                        {i + 1}
                      </span>
                      <span
                        className="truncate text-sm font-medium"
                        title={c.filename ?? c.document_id}
                      >
                        {c.filename ?? c.document_id}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--color-accent-2)]">
                      Chunk {c.chunk_index} · Score {c.score.toFixed(2)}
                    </p>
                    <p className="mt-1 text-xs text-[var(--color-muted)]">
                      “{c.text_preview}”
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
