"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { Card, PageHeader, SectionTitle, Badge } from "@/components/ui";
import {
  listAssets,
  performRca,
  getAssetTimeline,
  listDocuments,
  type ApiAsset,
  type ApiRcaResponse,
  type ApiAssetTimelineEvent,
  type ApiLikelyCause,
  type ApiDocument,
} from "@/lib/api";

/* Exact quick-demo presets requested in the task spec. */
const DEMO_SCENARIOS = [
  {
    asset: "P-101",
    symptom: "high vibration after seal replacement",
    label: "P-101 — high vibration after seal replacement",
  },
  {
    asset: "HX-305",
    symptom: "fouling and declining heat-transfer performance",
    label: "HX-305 — fouling and declining heat-transfer performance",
  },
  {
    asset: "M-017",
    symptom: "motor overheating and insulation degradation",
    label: "M-017 — motor overheating and insulation degradation",
  },
] as const;

/* Helper to map event severity to Badge tones */
function severityTone(s: string): "ok" | "warn" | "bad" | "neutral" {
  if (s === "high") return "bad";
  if (s === "medium") return "warn";
  if (s === "low") return "ok";
  return "neutral";
}

/* Helper to map event types to icons */
function eventIcon(type: string): string {
  const m: Record<string, string> = {
    inspection: "🔍",
    work_order: "🔧",
    procedure: "📋",
    compliance: "🛡️",
    failure: "⚠️",
    evidence_mention: "📎",
  };
  return m[type] ?? "•";
}

export default function RcaPage() {
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState("P-101");
  const [symptom, setSymptom] = useState("high vibration after seal replacement");
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [result, setResult] = useState<ApiRcaResponse | null>(null);
  const [timeline, setTimeline] = useState<ApiAssetTimelineEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [documentsList, setDocumentsList] = useState<ApiDocument[]>([]);

  // Load assets and documents on page mount. This never triggers an RCA request.
  useEffect(() => {
    listAssets()
      .then((res) => {
        setAssets(res);
        if (res.length > 0 && !res.some((a) => a.tag === "P-101")) {
          setSelectedAsset(res[0].tag);
        }
      })
      .catch(() => setAssets([]));

    listDocuments()
      .then(setDocumentsList)
      .catch(() => {});
  }, []);

  // Prefill from URL query params (?asset=, ?symptom=). Prefill only — never
  // auto-submit. Generation always requires an explicit user action.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);

    const assetParam = params.get("asset");
    const symptomParam = params.get("symptom");

    if (assetParam) {
      setSelectedAsset(assetParam);
    }

    if (symptomParam) {
      setSymptom(symptomParam);
    } else if (assetParam) {
      // If only an asset is given and it matches a known preset, prefill the
      // matching symptom for convenience — still without submitting.
      const match = DEMO_SCENARIOS.find((d) => d.asset === assetParam);
      if (match) setSymptom(match.symptom);
    }
  }, []);

  async function handleRcaTrigger(assetTag: string, sym: string) {
    const trimmedSym = sym.trim();
    if (!assetTag || !trimmedSym) return;

    setStatus("loading");
    setError(null);

    try {
      // RCA is the primary request; the timeline is a best-effort live extra.
      const [rcaRes, timelineRes] = await Promise.all([
        performRca(assetTag, trimmedSym),
        getAssetTimeline(assetTag).catch(() => ({ events: [] })),
      ]);

      setResult(rcaRes);
      setTimeline(timelineRes.events || []);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "RCA Agent request failed.");
      setStatus("error");
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    handleRcaTrigger(selectedAsset, symptom);
  }

  // Demo presets only prefill the form fields — the user still clicks Generate.
  function applyDemo(asset: string, sym: string) {
    setSelectedAsset(asset);
    setSymptom(sym);
  }

  const docIdMap = new Map<string, string>();
  const docNameMap = new Map<string, string>();
  documentsList.forEach((d) => {
    if (d.filename) {
      docIdMap.set(d.filename, d.id);
    }
    docNameMap.set(d.id, d.filename);
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Root Cause Analysis (RCA)"
        subtitle="AI reliability agent grounded in failure logs, maintenance manuals, and sensor specifications."
        action={result && <Badge tone="ok">Agent Status: Active</Badge>}
      />

      {/* Main Grid: Config Panel Left, Analysis Right */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left Column: Input Form & Asset Timeline (Span 4) */}
        <div className="space-y-6 lg:col-span-4">
          <Card className="border-[var(--color-border)] bg-[var(--color-surface)]">
            <SectionTitle title="Configure Agent" />
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)] mb-1.5">
                  Select Plant Asset
                </label>
                <select
                  value={selectedAsset}
                  onChange={(e) => setSelectedAsset(e.target.value)}
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-fg)] focus:border-[var(--color-accent)] focus:outline-none transition"
                >
                  {/* Ensure the current tag is always selectable, even if it is a
                      custom/query-param value not present in the assets list. */}
                  {!assets.some((a) => a.tag === selectedAsset) && (
                    <option value={selectedAsset}>{selectedAsset}</option>
                  )}
                  {assets.length === 0 ? (
                    <option value="P-101">P-101 - Centrifugal Pump</option>
                  ) : (
                    assets.map((asset) => (
                      <option key={asset.tag} value={asset.tag}>
                        {asset.tag} - {asset.display_name}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)] mb-1.5">
                  Observed Symptom
                </label>
                <textarea
                  value={symptom}
                  onChange={(e) => setSymptom(e.target.value)}
                  placeholder="Describe the failure mode or symptom (e.g. high seal leakage, low flow)..."
                  rows={3}
                  required
                  className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-fg)] placeholder:text-[var(--color-muted)]/50 focus:border-[var(--color-accent)] focus:outline-none transition resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={status === "loading"}
                className="w-full cursor-pointer rounded-lg bg-[var(--color-accent)] px-4 py-2.5 text-center text-sm font-semibold text-[#0b0f17] hover:bg-[var(--color-accent)]/80 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition"
              >
                {status === "loading" ? "Generating RCA..." : "Generate RCA"}
              </button>
            </form>

            {/* Quick demo presets — prefill only */}
            <div className="mt-4 pt-4 border-t border-[var(--color-border)]">
              <p className="text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)] mb-2">
                Quick Demo Presets
              </p>
              <div className="flex flex-col gap-2">
                {DEMO_SCENARIOS.map((demo) => {
                  const active =
                    selectedAsset === demo.asset && symptom === demo.symptom;
                  return (
                    <button
                      key={demo.asset}
                      type="button"
                      onClick={() => applyDemo(demo.asset, demo.symptom)}
                      className={`text-left text-xs px-2.5 py-2 rounded-md transition border hover:bg-[var(--color-surface-2)] hover:border-[var(--color-accent)]/40 ${
                        active
                          ? "bg-[var(--color-surface-2)] border-[var(--color-accent)] text-[var(--color-accent)] font-semibold"
                          : "border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-muted)]"
                      }`}
                    >
                      🚀 {demo.label}
                    </button>
                  );
                })}
              </div>
            </div>
          </Card>

          {/* Live event timeline (best-effort) — only meaningful after a run */}
          {status === "done" && (
            <Card className="bg-[var(--color-surface)]">
              <SectionTitle
                title="Event History"
                subtitle={
                  timeline.length > 0
                    ? `${timeline.length} event(s) in database`
                    : "No events recorded"
                }
              />
              {timeline.length === 0 ? (
                <p className="py-6 text-center text-xs text-[var(--color-muted)]">
                  No past maintenance logs found for {selectedAsset}.
                </p>
              ) : (
                <ol className="relative space-y-4 border-l border-[var(--color-border)] pl-4 ml-1.5 mt-2">
                  {timeline.map((t) => {
                    const dateStr = t.date
                      ? new Date(t.date).toISOString().slice(0, 10)
                      : "—";
                    return (
                      <li key={t.id} className="relative group">
                        <span className="absolute -left-[21px] mt-1.5 h-2.5 w-2.5 rounded-full border border-[var(--color-border)] bg-[var(--color-base)] transition-colors group-hover:bg-[var(--color-accent)]" />
                        <div className="flex items-center gap-2 text-[10px] text-[var(--color-muted)]">
                          <span className="font-mono font-medium">{dateStr}</span>
                          <span>•</span>
                          <span className="capitalize">
                            {t.event_type.replace("_", " ")}
                          </span>
                          <span className="ml-auto">
                            <Badge tone={severityTone(t.severity)}>
                              {t.severity}
                            </Badge>
                          </span>
                        </div>
                        <p className="mt-1 text-xs font-semibold text-[var(--color-fg)]">
                          <span className="mr-1">{eventIcon(t.event_type)}</span>
                          {t.title}
                        </p>
                        {t.filename && (
                          <p className="text-[10px] text-[var(--color-muted)] mt-0.5">
                            Source:{" "}
                            {t.document_id ? (
                              <Link
                                href={`/documents/${t.document_id}`}
                                className="text-[var(--color-accent)] hover:underline font-mono"
                              >
                                {t.filename}
                              </Link>
                            ) : (
                              <span className="font-mono">{t.filename}</span>
                            )}
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ol>
              )}
            </Card>
          )}
        </div>

        {/* Right Column: Loading, Error, Idle, or live RCA Results (Span 8) */}
        <div className="lg:col-span-8">
          {status === "loading" && (
            <Card className="flex flex-col items-center justify-center py-20 text-center space-y-4">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-[var(--color-border)] border-t-[var(--color-accent)]" />
              <div>
                <p className="text-sm font-semibold">
                  Running Root Cause Analysis...
                </p>
                <p className="text-xs text-[var(--color-muted)] mt-1">
                  Ingesting evidence, cross-referencing manuals, and resolving
                  diagnostic logic.
                </p>
              </div>
            </Card>
          )}

          {status === "error" && (
            <Card className="border-red-500/30 bg-red-500/5 py-10 text-center space-y-4">
              <p className="text-lg">⚠️</p>
              <h3 className="text-sm font-semibold text-red-300">
                RCA Diagnostic Failed
              </h3>
              <p className="text-xs text-[var(--color-muted)] max-w-md mx-auto">
                {error ||
                  "An unexpected error occurred while communicating with the analysis agent."}
              </p>
              <button
                type="button"
                onClick={() => handleRcaTrigger(selectedAsset, symptom)}
                className="cursor-pointer rounded bg-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-300 border border-red-500/30 hover:bg-red-500/30 transition"
              >
                Retry Request
              </button>
            </Card>
          )}

          {status === "done" && result && (
            <div className="space-y-6">
              {/* Summary Block */}
              <div className="rounded-xl border border-[var(--color-border)] bg-gradient-to-r from-[var(--color-surface)] to-[var(--color-surface-2)] p-5 relative overflow-hidden">
                <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent-2)]" />

                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent)]">
                      RCA Summary
                    </span>
                    <h2 className="text-lg font-semibold mt-0.5">
                      RCA findings for {result.asset_tag}
                    </h2>
                  </div>
                  <span className="text-[10px] bg-[var(--color-accent)]/10 text-[var(--color-accent)] border border-[var(--color-accent)]/30 rounded-full px-2 py-0.5 font-semibold">
                    Live Analysis
                  </span>
                </div>

                <p className="mt-3.5 text-sm leading-relaxed text-[#e6edf7] font-medium bg-[var(--color-base)]/50 border border-[var(--color-border)]/50 rounded-lg p-3.5">
                  &ldquo;{result.summary}&rdquo;
                </p>
              </div>

              {/* Likely Root Causes */}
              <div className="space-y-4">
                <SectionTitle
                  title="Likely Root Causes & Supporting Evidence"
                  subtitle="Diagnosed causes ranked by evidence matching and confidence"
                />

                {result.likely_causes.length === 0 ? (
                  <Card className="text-center py-6 text-sm text-[var(--color-muted)]">
                    No matching root causes could be extracted from local evidence
                    logs.
                  </Card>
                ) : (
                  <div className="grid grid-cols-1 gap-4">
                    {result.likely_causes.map((item: ApiLikelyCause, i: number) => {
                      const pct = Math.round(item.confidence * 100);
                      const isHigh = item.confidence >= 0.7;
                      return (
                        <Card
                          key={i}
                          className="border-[var(--color-border)] bg-[var(--color-surface)] transition hover:border-[var(--color-accent-2)]/30 p-5 space-y-4"
                        >
                          {/* Heading: Cause + Confidence */}
                          <div className="flex flex-wrap items-start justify-between gap-4">
                            <div className="flex gap-3 items-center">
                              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-surface-2)] text-xs font-semibold text-[var(--color-accent)] border border-[var(--color-border)]">
                                {i + 1}
                              </span>
                              <h4 className="text-sm font-semibold text-[var(--color-fg)]">
                                {item.cause}
                              </h4>
                            </div>

                            <div className="text-right">
                              <div className="flex items-center gap-2">
                                <span
                                  className={`text-xs font-bold ${
                                    isHigh
                                      ? "text-[var(--color-accent)]"
                                      : "text-amber-400"
                                  }`}
                                >
                                  {pct}% Confidence
                                </span>
                              </div>
                              <div className="mt-1 h-1.5 w-24 rounded-full bg-[var(--color-border)] overflow-hidden">
                                <div
                                  className={`h-full rounded-full transition-all duration-500 ${
                                    isHigh
                                      ? "bg-[var(--color-accent)]"
                                      : "bg-amber-400"
                                  }`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                            </div>
                          </div>

                          {/* Evidence Block */}
                          <div className="space-y-3 pt-3 border-t border-[var(--color-border)]/55">
                            <h5 className="text-[10px] uppercase tracking-wider font-bold text-[var(--color-muted)]">
                              Supporting Citations ({item.evidence.length})
                            </h5>

                            {item.evidence.length === 0 ? (
                              <p className="text-xs text-[var(--color-muted)] italic">
                                No supporting citations returned for this cause.
                              </p>
                            ) : (
                              item.evidence.map((ev, evIdx) => {
                                // Resolve a safe document link: prefer a known
                                // filename->id mapping, then an explicit
                                // document_id. Never render a broken link.
                                const mappedId = ev.source
                                  ? docIdMap.get(ev.source)
                                  : undefined;
                                const linkId = mappedId ?? ev.document_id ?? null;
                                const linkLabel =
                                  ev.source ||
                                  (ev.document_id
                                    ? docNameMap.get(ev.document_id)
                                    : undefined) ||
                                  "Source Document";
                                return (
                                  <div
                                    key={evIdx}
                                    className="bg-[var(--color-surface-2)] border border-[var(--color-border)] rounded-lg p-3 text-xs space-y-2.5"
                                  >
                                    <p className="italic leading-relaxed text-[var(--color-fg)]/90 relative pl-4">
                                      <span className="absolute left-0 top-0 text-sm font-serif text-[var(--color-accent)] opacity-60">
                                        &ldquo;
                                      </span>
                                      {ev.text}
                                      <span className="text-sm font-serif text-[var(--color-accent)] opacity-60">
                                        &rdquo;
                                      </span>
                                    </p>

                                    <div className="flex items-center justify-between gap-2 text-[10px] text-[var(--color-muted)] pt-1.5 border-t border-[var(--color-border)]/40 font-mono">
                                      <span>
                                        📁 Source:{" "}
                                        {linkId ? (
                                          <Link
                                            href={`/documents/${linkId}`}
                                            className="text-[var(--color-accent)] hover:underline"
                                          >
                                            {linkLabel}
                                          </Link>
                                        ) : (
                                          <span className="text-[var(--color-accent-2)]">
                                            {linkLabel}
                                          </span>
                                        )}
                                      </span>

                                      {ev.chunk_id && (
                                        <span>ID: {ev.chunk_id.slice(0, 8)}…</span>
                                      )}
                                    </div>
                                  </div>
                                );
                              })
                            )}
                          </div>
                        </Card>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Recommendations & Missing Information */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card className="bg-[var(--color-surface)]">
                  <SectionTitle title="Recommended Actions" />
                  {result.recommended_actions.length === 0 ? (
                    <p className="text-xs text-[var(--color-muted)] italic">
                      No recommended actions returned.
                    </p>
                  ) : (
                    <ul className="space-y-3 text-xs leading-relaxed text-[var(--color-fg)]">
                      {result.recommended_actions.map((act, idx) => (
                        <li key={idx} className="flex gap-2.5 items-start">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent)]/10 text-[var(--color-accent)] text-xs border border-[var(--color-accent)]/30 mt-0.5">
                            ✓
                          </span>
                          <span className="mt-0.5">{act}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>

                <Card className="bg-[var(--color-surface)]">
                  <SectionTitle title="Missing Information" />
                  {result.missing_information.length === 0 ? (
                    <p className="text-xs text-[var(--color-muted)] italic">
                      No information gaps reported.
                    </p>
                  ) : (
                    <ul className="space-y-3 text-xs leading-relaxed text-[var(--color-muted)]">
                      {result.missing_information.map((gap, idx) => (
                        <li key={idx} className="flex gap-2.5 items-start">
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-amber-500/10 text-amber-400 text-[10px] font-bold border border-amber-500/30 mt-0.5">
                            ?
                          </span>
                          <span className="mt-0.5">{gap}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Card>
              </div>
            </div>
          )}

          {status === "idle" && (
            <Card className="py-20 text-center space-y-2">
              <p className="text-2xl">🧭</p>
              <p className="text-sm font-semibold text-[var(--color-fg)]">
                No analysis yet
              </p>
              <p className="text-xs text-[var(--color-muted)] max-w-sm mx-auto">
                Select an asset, describe the observed symptom (or pick a quick
                demo preset), then click <strong>Generate RCA</strong> to run the
                live root cause analysis agent.
              </p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
