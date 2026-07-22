"use client";

import { useEffect, useState } from "react";
import {
  Card,
  PageHeader,
  Badge,
  SectionTitle,
  StatCard,
  TableScrollRegion,
  MobileDataCard,
} from "@/components/ui";
import Link from "next/link";
import { CheckIcon, CloseIcon, DocumentIcon } from "@/components/icons";
import {
  getLatestEvaluation,
  listDocuments,
  type ApiDocument,
  type ApiEvaluationResponse,
} from "@/lib/api";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

/* Pass/fail indicator — a coloured stroke icon instead of an emoji so it
   inherits the restrained local icon treatment. */
function HitMark({ hit, label }: { hit: boolean; label: string }) {
  return (
    <span role="img" aria-label={`${label}: ${hit ? "hit" : "miss"}`} className="inline-flex">
      {hit ? (
        <CheckIcon className="h-4 w-4 text-emerald-600" />
      ) : (
        <CloseIcon className="h-4 w-4 text-[var(--color-subtle)]" />
      )}
    </span>
  );
}

export default function EvaluationPage() {
  const [data, setData] = useState<ApiEvaluationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [docs, setDocs] = useState<ApiDocument[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getLatestEvaluation()
      .then((res) => {
        if (active) {
          setData(res);
          setError(null);
        }
      })
      .catch((e: Error) => active && setError(e.message))
      .finally(() => active && setLoading(false));
    listDocuments().then(setDocs).catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  // ── Loading / error / empty states ─────────────────────────────────────────
  if (loading) {
    return (
      <div className="space-y-6">
        <PageHeader title="RAG Evaluation" subtitle="Loading the latest genuine benchmark…" />
        <Card>
          <div className="animate-pulse text-sm text-[var(--color-muted)]">
            Fetching /evaluation/latest…
          </div>
        </Card>
      </div>
    );
  }

  if (error || !data) {
    const isMissing = (error ?? "").includes("404");
    return (
      <div className="space-y-6">
        <PageHeader title="RAG Evaluation" subtitle="Genuine benchmark results" />
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-amber-700">
          <p className="text-sm font-semibold">
            {isMissing ? "No benchmark results yet" : "Could not load evaluation"}
          </p>
          <p className="mt-1 text-xs leading-relaxed opacity-90">
            {isMissing
              ? "Run the benchmark to generate results:"
              : `Backend error: ${error}`}
          </p>
          {isMissing && (
            <pre className="mt-2 overflow-x-auto rounded border border-amber-200 bg-[var(--color-surface)] px-2 py-1 font-mono text-[11px] text-[var(--color-fg)]">
              cd apps/api && python -m scripts.run_benchmark
            </pre>
          )}
        </div>
      </div>
    );
  }

  const { summary, results } = data;
  const generatedAt = summary.generated_at ?? summary.last_run_time;
  const deterministic = summary.answer_provider.includes("deterministic");
  const selected = results.find((r) => r.id === selectedId);

  const allStats = [
    { label: "Top-1 Source Hit", value: pct(summary.top1_source_hit_rate), hint: "target doc rank 1" },
    { label: "Top-3 Source Hit", value: pct(summary.top3_source_hit_rate), hint: "target doc in top 3" },
    { label: "Asset Hit Rate", value: pct(summary.asset_hit_rate), hint: `${summary.asset_questions} asset Qs` },
    { label: "Avg Latency", value: `${summary.average_latency_ms.toFixed(0)}ms`, hint: `p95 ${summary.p95_latency_ms.toFixed(0)}ms` },
  ];

  const failureEntries = Object.entries(summary.failure_category_breakdown).sort(
    (a, b) => b[1] - a[1],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title="RAG Evaluation"
        subtitle="Live benchmark results — retrieval measured against the seeded index."
      />

      {/* ── Provenance ────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <span className="flex items-center gap-1.5">
            <Badge tone="ok">LIVE</Badge>
            <span className="text-[var(--color-muted)]">
              from <code className="wrap-anywhere font-mono">{data.source_file}</code>
            </span>
          </span>
          <span className="text-[var(--color-muted)]">
            Generated: <span className="font-semibold text-[var(--color-fg)]">{new Date(generatedAt).toUTCString()}</span>
          </span>
          <span className="text-[var(--color-muted)]">
            Corpus: <span className="font-semibold text-[var(--color-fg)]">{summary.corpus_document_count} docs</span>
          </span>
          <span className="text-[var(--color-muted)]">
            Embedding: <span className="font-mono text-[var(--color-fg)]">{summary.embedding_provider}/{summary.embedding_model}</span>
          </span>
          <span className="text-[var(--color-muted)]">
            Generation: <span className="font-mono text-[var(--color-fg)]">{summary.answer_provider}/{summary.answer_model}</span>
          </span>
        </div>
        {deterministic && (
          <p className="mt-2 text-[11px] leading-relaxed text-amber-700">
            Running in deterministic local mode (hashing embeddings, extractive answers, no Gemini call).
            Scores reflect the offline fallback, not live Gemini performance.
          </p>
        )}
      </div>

      {/* ── All-questions metrics ─────────────────────────────────────── */}
      <div>
        <SectionTitle
          title={`All benchmark questions (${summary.total_questions})`}
          subtitle="Every question in questions.json, including any whose source is absent from the corpus."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {allStats.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </div>
      </div>

      {/* ── Answerable subset + absent-corpus disclosure ──────────────── */}
      <div>
        <SectionTitle
          title={`Answerable-corpus questions (${summary.answerable_questions})`}
          subtitle="Questions whose expected source document is present in the seeded corpus."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Answerable Top-3" value={pct(summary.answerable_top3_source_hit_rate)} hint="of answerable Qs" />
          <StatCard label="Answerable Asset Hit" value={pct(summary.answerable_asset_hit_rate)} hint={`${summary.answerable_asset_questions} asset Qs`} />
          <StatCard label="Failed Questions" value={summary.failed_questions_count} hint="target doc not in top-3" />
          <StatCard
            label="Absent-Corpus Qs"
            value={summary.absent_corpus_count}
            hint={summary.absent_corpus_count === 0 ? "corpus complete" : "expected source missing"}
          />
        </div>
        {summary.absent_corpus_count > 0 && (
          <p className="mt-2 text-[11px] text-amber-700">
            {summary.absent_corpus_count} question(s) reference a document not in the corpus and cannot be answered — counted as failures above, not hidden.
          </p>
        )}
      </div>

      {/* ── Failure-category breakdown ────────────────────────────────── */}
      <Card>
        <SectionTitle title="Failure-category breakdown" subtitle="Why each question passed or failed the Top-3 source check" />
        <div className="flex flex-wrap gap-2">
          {failureEntries.map(([cat, count]) => (
            <span
              key={cat}
              className={`rounded-full border px-3 py-1 text-xs ${
                cat === "pass"
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-rose-200 bg-rose-50 text-rose-700"
              }`}
            >
              {cat.replace(/_/g, " ")}: <span className="font-semibold">{count}</span>
            </span>
          ))}
        </div>
      </Card>

      {/* ── Per-question table + inspector ────────────────────────────── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionTitle title="Per-question results" subtitle="Click a row to compare expected source and actual citations" />
          {/* Desktop / tablet: results table (md+) */}
          <TableScrollRegion label="Per-question results" className="hidden md:block">
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                <tr>
                  <th className="px-3 py-2 font-medium">ID</th>
                  <th className="px-3 py-2 font-medium">Expected Source</th>
                  <th className="px-3 py-2 text-center font-medium">T1</th>
                  <th className="px-3 py-2 text-center font-medium">T3</th>
                  <th className="px-3 py-2 text-center font-medium">Asset</th>
                  <th className="px-3 py-2 text-center font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => setSelectedId(r.id)}
                    className={`cursor-pointer border-t border-[var(--color-border)] transition hover:bg-[var(--color-surface-2)] ${
                      selectedId === r.id ? "bg-[var(--color-surface-2)]" : ""
                    }`}
                  >
                    <td className="px-3 py-3 font-mono font-medium">{r.id}</td>
                    <td className="max-w-[160px] truncate px-3 py-3 text-xs" title={r.expected_doc}>
                      {r.expected_doc}
                      {!r.expected_source_in_corpus && (
                        <span className="ml-1 rounded bg-amber-50 px-1 text-[11px] text-amber-600">absent</span>
                      )}
                    </td>
                    <td className="px-3 py-3 text-center"><HitMark hit={r.top1_hit} label="Top-1" /></td>
                    <td className="px-3 py-3 text-center"><HitMark hit={r.top3_hit} label="Top-3" /></td>
                    <td className="px-3 py-3 text-center"><HitMark hit={r.asset_hit} label="Asset" /></td>
                    <td className="px-3 py-3 text-center">
                      <Badge tone={r.status === "passed" ? "ok" : "bad"}>{r.status}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScrollRegion>

          {/* Mobile: result cards (below md) */}
          <div className="space-y-3 md:hidden">
            {results.map((r) => (
              <MobileDataCard
                key={r.id}
                onClick={() => setSelectedId(r.id)}
                className={selectedId === r.id ? "border-[var(--color-accent)]" : ""}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-sm font-medium">{r.id}</span>
                  <Badge tone={r.status === "passed" ? "ok" : "bad"}>{r.status}</Badge>
                </div>
                <p className="wrap-anywhere text-xs text-[var(--color-muted)]">
                  <span className="text-[var(--color-fg)]">{r.expected_doc}</span>
                  {!r.expected_source_in_corpus && (
                    <span className="ml-1 rounded bg-amber-50 px-1 text-[11px] text-amber-600">absent</span>
                  )}
                </p>
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-muted)]">
                  <span className="inline-flex items-center gap-1">T1 <HitMark hit={r.top1_hit} label="Top-1" /></span>
                  <span className="inline-flex items-center gap-1">T3 <HitMark hit={r.top3_hit} label="Top-3" /></span>
                  <span className="inline-flex items-center gap-1">Asset <HitMark hit={r.asset_hit} label="Asset" /></span>
                </div>
              </MobileDataCard>
            ))}
          </div>
        </Card>

        <Card className="flex flex-col">
          <SectionTitle title="Run inspector" subtitle="Expected vs actual retrieval" />
          {!selected ? (
            <div className="mt-2 flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface-2)] px-4 py-12 text-center text-[var(--color-muted)]">
              <DocumentIcon className="mb-2 h-7 w-7 text-[var(--color-subtle)]" />
              <p className="text-xs">Select a question to inspect its expected source, expected answer, and actual citations.</p>
            </div>
          ) : (
            <div className="mt-2 flex-1 space-y-4 text-xs">
              <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                <div className="mb-1.5 flex items-center gap-2">
                  <Badge tone={selected.status === "passed" ? "ok" : "bad"}>{selected.status}</Badge>
                  <span className="font-mono text-[var(--color-muted)]">{selected.id}</span>
                  <span className="rounded bg-[var(--color-surface)] px-1.5 py-0.5 font-mono text-[11px] uppercase text-[var(--color-muted)]">
                    {selected.category.replace(/_/g, " ")}
                  </span>
                </div>
                <h3 className="text-xs font-semibold leading-relaxed">&ldquo;{selected.question}&rdquo;</h3>
              </div>

              <dl className="space-y-3">
                <div>
                  <dt className="font-medium text-[var(--color-muted)]">Target Asset</dt>
                  <dd className="mt-0.5 font-mono text-sm font-semibold text-[var(--color-accent)]">{selected.asset_tag ?? "—"}</dd>
                </div>

                <div>
                  <dt className="font-medium text-[var(--color-muted)]">Expected Source</dt>
                  <dd className="mt-0.5 wrap-anywhere font-mono">
                    {selected.expected_doc}
                    {!selected.expected_source_in_corpus && (
                      <span className="ml-1 text-amber-600">(absent from corpus)</span>
                    )}
                  </dd>
                </div>

                <div>
                  <dt className="font-medium text-[var(--color-muted)]">Actual Citations (ranked)</dt>
                  <dd className="mt-1 space-y-1">
                    {selected.citations.length === 0 && <span className="text-[var(--color-muted)]">No citations retrieved.</span>}
                    {selected.citations.map((c, i) => {
                      const match = docs.find((d) => d.filename === c.file_name);
                      const isTarget = c.file_name === selected.expected_doc;
                      return (
                        <div key={`${c.chunk_id}-${i}`} className="flex items-center gap-1.5">
                          <span className="font-mono text-[11px] text-[var(--color-muted)]">[{i + 1}]</span>
                          {match ? (
                            <Link
                              href={`/documents/${match.id}`}
                              className={`hover:underline ${isTarget ? "font-semibold text-emerald-700" : "text-[var(--color-accent)]"}`}
                            >
                              {c.file_name}
                            </Link>
                          ) : (
                            <span className={isTarget ? "font-semibold text-emerald-700" : ""}>{c.file_name}</span>
                          )}
                          {c.page != null && <span className="text-[11px] text-[var(--color-muted)]">p{c.page}</span>}
                          {isTarget && (
                            <span className="rounded border border-emerald-200 bg-emerald-50 px-1 text-[11px] text-emerald-700">target</span>
                          )}
                        </div>
                      );
                    })}
                  </dd>
                </div>

                <div className="border-t border-[var(--color-border)] pt-2">
                  <dt className="mb-1 font-medium text-[var(--color-muted)]">Expected Answer</dt>
                  <dd className="rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] p-2.5 leading-relaxed text-[var(--color-muted)]">
                    {selected.expected_answer || "—"}
                  </dd>
                </div>

                <div className="border-t border-[var(--color-border)] pt-2">
                  <dt className="mb-1 font-medium text-[var(--color-muted)]">Actual System Output</dt>
                  <dd className="rounded border border-[var(--color-border)] bg-[var(--color-surface-2)] p-2.5 italic leading-relaxed">
                    &ldquo;{selected.actual_answer || "—"}&rdquo;
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
