"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, Badge } from "@/components/ui";
import {
  queryCopilot,
  listAssets,
  type ApiQueryResponse,
  type ApiAsset,
} from "@/lib/api";

export default function CopilotPage() {
  const [question, setQuestion] = useState("");
  const [selectedAsset, setSelectedAsset] = useState("");
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">(
    "idle",
  );
  const [result, setResult] = useState<ApiQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Load available assets for scoping dropdown
  useEffect(() => {
    listAssets()
      .then(setAssets)
      .catch(() => {
        // Fallback silently or empty list if no assets/database not ready
        setAssets([]);
      });
  }, []);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setStatus("loading");
    setError(null);
    try {
      const res = await queryCopilot({
        question: question.trim(),
        top_k: 5,
        asset_tag: selectedAsset || undefined,
      });
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
        <form onSubmit={handleAsk} className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 md:flex-row">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. What is the recommended seal flush plan for Pump P-101?"
              className="flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-4 py-2.5 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]"
            />
            <div className="flex shrink-0 items-center gap-2">
              <label htmlFor="asset-scope" className="text-xs text-[var(--color-muted)] whitespace-nowrap">
                Scope by Asset:
              </label>
              <select
                id="asset-scope"
                value={selectedAsset}
                onChange={(e) => setSelectedAsset(e.target.value)}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
              >
                <option value="">All assets</option>
                {assets.map((a) => (
                  <option key={a.id} value={a.tag}>
                    {a.tag}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              disabled={status === "loading" || !question.trim()}
              className="rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[var(--color-base)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40 whitespace-nowrap"
            >
              {status === "loading" ? "Asking…" : "Ask"}
            </button>
          </div>
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

            <div className="mb-4 flex flex-wrap items-center gap-3 text-xs">
              <Badge tone="ok">confidence: {result.confidence}</Badge>
              {result.query_intent && (
                <Badge tone="neutral">intent: {result.query_intent}</Badge>
              )}
              <span className="text-[var(--color-muted)]">
                {result.retrieved_count} chunk
                {result.retrieved_count === 1 ? "" : "s"} retrieved
              </span>
            </div>

            <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Answer
            </p>
            <div className="mb-6">
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
            </div>

            {result.related_assets && result.related_assets.length > 0 && (
              <div className="border-t border-[var(--color-border)] pt-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
                  Related Assets
                </p>
                <div className="flex flex-wrap gap-2">
                  {result.related_assets.map((a) => (
                    <Link key={a} href={`/assets/${a}`}>
                      <Badge tone="ok">{a}</Badge>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </Card>

          <Card>
            <p className="mb-3 text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Citations
            </p>
            {(() => {
              // Deduplicate citations by chunk_id to avoid repeated cards
              const uniqueCitations = result.citations.filter(
                (c, index, self) => self.findIndex((x) => x.chunk_id === c.chunk_id) === index
              );

              const extractTags = (text: string) => {
                const matches = text.match(/\b([A-Za-z]{1,4})-(\d{1,4})([A-Za-z]?)\b/g);
                return matches ? Array.from(new Set(matches.map(m => m.toUpperCase()))) : [];
              };

              if (uniqueCitations.length === 0) {
                return (
                  <p className="text-xs text-[var(--color-muted)]">
                    No citations returned.
                  </p>
                );
              }

              return (
                <ul className="space-y-3">
                  {uniqueCitations.map((c, i) => {
                    const tags = extractTags(c.text_preview);
                    return (
                      <li
                        key={c.chunk_id}
                        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-3"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--color-surface-2)] text-xs text-[var(--color-accent)]">
                              {i + 1}
                            </span>
                            <Link
                              href={`/documents/${c.document_id}`}
                              className="truncate text-sm font-medium text-[var(--color-accent)] hover:underline"
                              title={c.filename ?? c.document_id}
                            >
                              {c.filename ?? c.document_id}
                            </Link>
                          </div>
                          {tags.length > 0 && (
                            <div className="flex flex-wrap gap-1 shrink-0">
                              {tags.map((t) => (
                                <span key={t} className="text-[9px] bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 rounded px-1 font-mono uppercase">
                                  {t}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <p className="mt-1.5 text-xs text-[var(--color-accent-2)]">
                          {c.chunk_index !== undefined && <span>chunk {c.chunk_index}</span>}
                          {c.page_number !== null && c.page_number !== undefined && (
                            <span> · page {c.page_number}</span>
                          )}
                          <span> · score {c.score.toFixed(2)}</span>
                        </p>
                        <p className="mt-1.5 text-xs text-[var(--color-muted)] bg-[var(--color-surface-2)] p-2 rounded leading-relaxed italic">
                          “{c.text_preview}”
                        </p>
                      </li>
                    );
                  })}
                </ul>
              );
            })()}
          </Card>
        </div>
      )}
    </div>
  );
}
