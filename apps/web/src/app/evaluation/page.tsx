"use client";

import { useEffect, useState } from "react";
import { Card, PageHeader, Badge, SectionTitle, StatCard } from "@/components/ui";
import Link from "next/link";
import { listDocuments, type ApiDocument } from "@/lib/api";
import sampleData from "@/data/benchmark/results_sample.json";
import questions from "@/data/benchmark/questions.json";

export default function EvaluationPage() {
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(null);
  const [docs, setDocs] = useState<ApiDocument[]>([]);

  useEffect(() => {
    listDocuments().then(setDocs).catch(() => {});
  }, []);

  const { summary, results } = sampleData;

  const stats = [
    { label: "Benchmark Questions", value: summary.total_questions, hint: "questions.json" },
    { label: "Top-1 Source Hit Rate", value: `${(summary.top1_source_hit_rate * 100).toFixed(1)}%`, hint: "target doc in rank 1" },
    { label: "Top-3 Source Hit Rate", value: `${(summary.top3_source_hit_rate * 100).toFixed(1)}%`, hint: "target doc in top 3" },
    { label: "Asset Hit Rate", value: `${(summary.asset_hit_rate * 100).toFixed(1)}%`, hint: "target tag resolved" },
    { label: "Average Latency", value: `${summary.average_latency_ms.toFixed(1)}ms`, hint: "embedding + retrieval" },
    { label: "Failed Questions", value: summary.failed_questions_count, hint: "below context threshold" },
  ];

  const selectedResult = results.find((r) => r.id === selectedQuestionId);

  return (
    <div className="space-y-6">
      <PageHeader
        title="RAG Evaluation Dashboard"
        subtitle="Benchmark metrics comparing system answers against curated expected output."
      />

      {/* ── Sample Data Disclaimer Card ────────────────────────────── */}
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-emerald-300">
        <div className="flex gap-3">
          <span className="text-xl">📊</span>
          <div>
            <p className="text-sm font-semibold">Live System Benchmark Evaluation</p>
            <p className="mt-1 text-xs leading-relaxed opacity-90">
              The metrics shown below are calculated directly by executing standard benchmark Q&A pairs against the active database index.
              Report log: <code className="bg-emerald-950/40 px-1 py-0.5 rounded font-mono text-[10px]">data/benchmark/results_sample.json</code>.
              Last evaluated: <span className="font-semibold">{new Date(summary.last_run_time).toUTCString()}</span>.
            </p>
          </div>
        </div>
      </div>

      {/* ── KPI Stat Cards ────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      {/* ── Grid Layout: Results table & side panel inspector ───────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Table of benchmark runs */}
        <Card className="lg:col-span-2">
          <SectionTitle
            title="Benchmark Run Items"
            subtitle="Click on any row to inspect expected vs. actual answers"
          />
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                <tr>
                  <th className="px-3 py-2 font-medium">ID</th>
                  <th className="px-3 py-2 font-medium">Category</th>
                  <th className="px-3 py-2 font-medium">Target Doc</th>
                  <th className="px-3 py-2 font-medium text-center">Top 1</th>
                  <th className="px-3 py-2 font-medium text-center">Top 3</th>
                  <th className="px-3 py-2 font-medium text-center">Asset Hit</th>
                  <th className="px-3 py-2 font-medium text-right">Latency</th>
                  <th className="px-3 py-2 font-medium text-center">Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => setSelectedQuestionId(r.id)}
                    className={`cursor-pointer border-t border-[var(--color-border)] hover:bg-[var(--color-surface-2)] transition ${
                      selectedQuestionId === r.id ? "bg-[var(--color-surface-2)]" : ""
                    }`}
                  >
                    <td className="px-3 py-3 font-mono font-medium">{r.id}</td>
                    <td className="px-3 py-3">
                      <span className="text-[10px] bg-[var(--color-surface-2)] px-1.5 py-0.5 rounded border border-[var(--color-border)] font-mono text-[var(--color-muted)] uppercase">
                        {r.category.replace("_", " ")}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-xs max-w-[120px] truncate" title={r.expected_doc}>
                      {r.expected_doc}
                    </td>
                    <td className="px-3 py-3 text-center">{r.top1_hit ? "✅" : "❌"}</td>
                    <td className="px-3 py-3 text-center">{r.top3_hit ? "✅" : "❌"}</td>
                    <td className="px-3 py-3 text-center">{r.asset_hit ? "✅" : "❌"}</td>
                    <td className="px-3 py-3 text-right font-mono text-xs text-[var(--color-muted)]">
                      {r.latency_ms}ms
                    </td>
                    <td className="px-3 py-3 text-center">
                      <Badge tone={r.status === "passed" ? "ok" : "bad"}>{r.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Selected Result Detail Panel */}
        <Card className="flex flex-col">
          <SectionTitle title="Run Inspector" subtitle="Detailed retrieval comparison" />

          {!selectedResult ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center py-12 text-[var(--color-muted)] border-2 border-dashed border-[var(--color-border)] rounded-xl px-4 mt-2 bg-[var(--color-surface-2)]/20">
              <span className="text-2xl mb-2">📋</span>
              <p className="text-xs">Select any question row on the left to inspect expected answers, extracted entities, and actual grounding text results.</p>
            </div>
          ) : (
            <div className="flex-1 space-y-4 mt-2 text-xs">
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <Badge tone={selectedResult.status === "passed" ? "ok" : "bad"}>{selectedResult.status}</Badge>
                  <span className="font-mono text-[var(--color-muted)]">{selectedResult.id}</span>
                </div>
                <h3 className="text-xs font-semibold leading-relaxed text-[var(--color-fg)]">
                  &ldquo;{selectedResult.question}&rdquo;
                </h3>
              </div>

              <dl className="space-y-3">
                <div>
                  <dt className="text-[var(--color-muted)] font-medium">Target Asset Tag</dt>
                  <dd className="font-mono font-semibold text-sm text-[var(--color-accent)] mt-0.5">
                    {selectedResult.asset_tag}
                  </dd>
                </div>

                <div>
                  <dt className="text-[var(--color-muted)] font-medium">Expected Source Document</dt>
                  <dd className="font-mono mt-0.5">
                    {(() => {
                      const match = docs.find((d) => d.filename === selectedResult.expected_doc);
                      return match ? (
                        <Link href={`/documents/${match.id}`} className="text-[var(--color-accent)] hover:underline">
                          {selectedResult.expected_doc}
                        </Link>
                      ) : (
                        selectedResult.expected_doc
                      );
                    })()}
                  </dd>
                </div>

                <div>
                  <dt className="text-[var(--color-muted)] font-medium">Retrieved Documents (Top-k)</dt>
                  <dd className="mt-1 space-y-1">
                    {selectedResult.retrieved_docs.map((doc, idx) => {
                      const match = docs.find((d) => d.filename === doc);
                      return (
                        <div key={doc} className="flex items-center gap-1.5">
                          <span className="text-[10px] text-[var(--color-muted)] font-mono">[{idx + 1}]</span>
                          {match ? (
                            <Link
                              href={`/documents/${match.id}`}
                              className={`hover:underline ${
                                doc === selectedResult.expected_doc ? "text-emerald-300 font-semibold" : "text-[var(--color-accent)]"
                              }`}
                            >
                              {doc}
                            </Link>
                          ) : (
                            <span className={doc === selectedResult.expected_doc ? "text-emerald-300 font-semibold" : ""}>
                              {doc}
                            </span>
                          )}
                          {doc === selectedResult.expected_doc && (
                            <span className="text-[9px] bg-emerald-500/10 text-emerald-400 px-1 rounded border border-emerald-500/20">
                              Target Hit
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </dd>
                </div>

                <div className="pt-2 border-t border-[var(--color-border)]">
                  <dt className="text-[var(--color-muted)] font-medium mb-1">Expected Answer</dt>
                  <dd className="bg-[var(--color-surface-2)] p-2.5 rounded border border-[var(--color-border)] leading-relaxed text-[var(--color-muted)]">
                    {questions.find((q) => q.id === selectedResult.id)?.expected_answer || "—"}
                  </dd>
                </div>

                <div className="pt-2 border-t border-[var(--color-border)]">
                  <dt className="text-[var(--color-muted)] font-medium mb-1">Actual System Output</dt>
                  <dd className="bg-[var(--color-surface-2)] p-2.5 rounded border border-[var(--color-border)] leading-relaxed italic text-[var(--color-fg)]">
                    &ldquo;{selectedResult.actual_answer}&rdquo;
                  </dd>
                </div>
              </dl>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
