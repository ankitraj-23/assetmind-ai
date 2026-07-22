"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Card,
  PageHeader,
  Badge,
  RiskBadge,
  SectionTitle,
  StatCard,
  TableScrollRegion,
  MobileDataCard,
  DataRow,
  ErrorState,
} from "@/components/ui";
import {
  getAsset,
  getAssetMentions,
  getAssetDocuments,
  getAssetTimeline,
  getAssetGraph,
  getAssetFacts,
  getAssetFailureIntelligence,
  queryCopilot,
  type ApiAsset,
  type ApiAssetMentionsResponse,
  type ApiDocument,
  type ApiAssetTimelineEvent,
  type ApiAssetGraphResponse,
  type ApiAssetFacts,
  type ApiFailureIntelligence,
  type ApiQueryResponse,
} from "@/lib/api";
import type { Risk } from "@/lib/mock-data";

/* ── Tab definitions ────────────────────────────────────────────────── */
const TABS = [
  { key: "overview", label: "Overview" },
  { key: "documents", label: "Related Documents" },
  { key: "timeline", label: "Timeline" },
  { key: "failure", label: "Failure Intelligence" },
  { key: "mentions", label: "Evidence Mentions" },
  { key: "graph", label: "Knowledge Graph" },
  { key: "facts", label: "Facts" },
  { key: "ask", label: "Ask About This Asset" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

/* ── Helper: relative time ─────────────────────────────────────────── */
function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? "Yesterday" : `${days}d ago`;
}

/* ── Severity → tone map for badges ────────────────────────────────── */
function severityTone(s: string): "ok" | "warn" | "bad" | "neutral" {
  if (s === "high") return "bad";
  if (s === "medium") return "warn";
  if (s === "low") return "ok";
  return "neutral";
}

/* ── Event type → icon letter ──────────────────────────────────────── */
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

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const tag = decodeURIComponent(params.id);

  /* ── State ────────────────────────────────────────────────────────── */
  const [tab, setTab] = useState<TabKey>("overview");
  const [asset, setAsset] = useState<ApiAsset | null>(null);
  const [mentions, setMentions] = useState<ApiAssetMentionsResponse | null>(null);
  const [documents, setDocuments] = useState<ApiDocument[] | null>(null);
  const [timeline, setTimeline] = useState<ApiAssetTimelineEvent[] | null>(null);
  const [graph, setGraph] = useState<ApiAssetGraphResponse | null>(null);
  const [facts, setFacts] = useState<ApiAssetFacts | null>(null);
  const [failure, setFailure] = useState<ApiFailureIntelligence | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  /* Deep-link: ?tab= opens a specific tab on mount (used by the guided flow). */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const tabParam = new URLSearchParams(window.location.search).get("tab");
    if (tabParam && TABS.some((t) => t.key === tabParam)) {
      setTab(tabParam as TabKey);
    }
  }, []);

  /* Graph visualization state */
  const [graphIncludeChunks, setGraphIncludeChunks] = useState(true);
  const [graphRelationType, setGraphRelationType] = useState("");
  const [selectedNode, setSelectedNode] = useState<any>(null);

  /* Ask About This Asset state */
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState<ApiQueryResponse | null>(null);

  /* Refetch Graph on filter changes */
  useEffect(() => {
    if (loading) return;
    getAssetGraph(tag, graphIncludeChunks, graphRelationType || undefined)
      .then((newGraph) => {
        setGraph(newGraph);
        // Clear selection if the node is no longer in the filtered set
        if (selectedNode && !newGraph.nodes.some((n: any) => n.id === selectedNode.id)) {
          setSelectedNode(null);
        }
      })
      .catch((err) => console.error("Error updating graph:", err));
  }, [tag, graphIncludeChunks, graphRelationType, loading]);

  /* ── Fetch all data in parallel ───────────────────────────────────── */
  useEffect(() => {
    let active = true;

    Promise.all([
      getAsset(tag),
      getAssetMentions(tag),
      getAssetDocuments(tag),
      getAssetTimeline(tag),
      getAssetGraph(tag),
      getAssetFacts(tag),
      getAssetFailureIntelligence(tag),
    ])
      .then(([a, m, d, t, g, f, fi]) => {
        if (!active) return;
        setAsset(a);
        setMentions(m);
        setDocuments(d.documents);
        setTimeline(t.events);
        setGraph(g);
        setFacts(f);
        setFailure(fi);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Could not load asset.");
      })
      .finally(() => active && setLoading(false));

    return () => {
      active = false;
    };
  }, [tag]);

  /* ── Ask handler ──────────────────────────────────────────────────── */
  function handleAsk() {
    if (!question.trim()) return;
    setAsking(true);
    setAnswer(null);
    queryCopilot({ question, top_k: 5, asset_tag: tag })
      .then(setAnswer)
      .catch((err) => setAnswer({ question, answer: `Error: ${err instanceof Error ? err.message : String(err)}`, confidence: "low", citations: [], retrieved_count: 0 }))
      .finally(() => setAsking(false));
  }

  /* ── Back link ───────────────────────────────────────────────────── */
  const backLink = (
    <Link href="/assets" className="text-sm text-[var(--color-accent)] hover:underline">
      ← Back to assets
    </Link>
  );

  /* ── Error state ─────────────────────────────────────────────────── */
  if (error) {
    return (
      <div>
        <PageHeader title="Asset" action={backLink} />
        <Card>
          <ErrorState title="Backend Connection Error" detail={error} />
        </Card>
      </div>
    );
  }

  /* ── Loading state ───────────────────────────────────────────────── */
  if (loading || !asset) {
    return (
      <div>
        <PageHeader title="Asset" action={backLink} />
        <Card>
          <div className="space-y-3 py-6">
            <div className="mx-auto h-5 w-32 animate-pulse rounded bg-[var(--color-surface-2)]" />
            <div className="mx-auto h-3 w-48 animate-pulse rounded bg-[var(--color-surface-2)]" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={asset.tag}
        subtitle={`${asset.asset_type ? asset.asset_type.replace("_", " ") : "equipment"} · ${asset.display_name}`}
        action={backLink}
      />

      {/* ── Tab bar ──────────────────────────────────────────────── */}
      <div className="mb-6 flex gap-1 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition ${
              tab === t.key
                ? "bg-[var(--color-accent)] text-[var(--color-base)]"
                : "text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Overview tab ─────────────────────────────────────────── */}
      {tab === "overview" && (
        <div className="space-y-6">
          {/* Quick stats row */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatCard label="Asset Tag" value={asset.tag} />
            <StatCard label="Type" value={asset.asset_type ? asset.asset_type.replace("_", " ") : "—"} />
            <StatCard label="Mentions" value={mentions?.count ?? "—"} />
            <StatCard label="Documents" value={documents?.length ?? "—"} />
          </div>

          {/* Overview details */}
          <Card>
            <h2 className="mb-4 text-lg font-semibold tracking-tight">Asset Details</h2>
            <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Asset Tag</dt>
                <dd className="mt-0.5 font-medium">{asset.tag}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Type</dt>
                <dd className="mt-0.5 font-medium capitalize">{asset.asset_type ? asset.asset_type.replace("_", " ") : "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Display Name</dt>
                <dd className="mt-0.5 font-medium">{asset.display_name}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Discovered</dt>
                <dd className="mt-0.5 font-medium">{asset.created_at.slice(0, 10)}</dd>
              </div>
            </dl>
          </Card>

          {/* Reliability & Compliance Actions — all link to real workflows */}
          <Card>
            <h2 className="mb-4 text-lg font-semibold tracking-tight">
              Reliability &amp; Compliance Actions
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Link href={`/copilot?asset=${encodeURIComponent(asset.tag)}`}>
                <div className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 text-center transition hover:border-[var(--color-accent)]">
                  <span className="mb-2 text-2xl">💬</span>
                  <span className="text-sm font-semibold text-[var(--color-fg)]">
                    Ask Copilot About This Asset
                  </span>
                  <span className="mt-1.5 text-[10px] leading-relaxed text-[var(--color-muted)]">
                    Chat with the AI, scoped to this equipment
                  </span>
                </div>
              </Link>
              <Link href={`/rca?asset=${encodeURIComponent(asset.tag)}`}>
                <div className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 text-center transition hover:border-[var(--color-accent)]">
                  <span className="mb-2 text-2xl">🔍</span>
                  <span className="text-sm font-semibold text-[var(--color-fg)]">Generate RCA</span>
                  <span className="mt-1.5 text-[10px] leading-relaxed text-[var(--color-muted)]">
                    Analyze failure evidence &amp; root causes
                  </span>
                </div>
              </Link>
              <Link href={`/compliance?asset=${encodeURIComponent(asset.tag)}`}>
                <div className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 text-center transition hover:border-[var(--color-accent)]">
                  <span className="mb-2 text-2xl">🛡️</span>
                  <span className="text-sm font-semibold text-[var(--color-fg)]">Check Compliance</span>
                  <span className="mt-1.5 text-[10px] leading-relaxed text-[var(--color-muted)]">
                    Review evidence-backed compliance gaps
                  </span>
                </div>
              </Link>
              <Link href={`/compliance?asset=${encodeURIComponent(asset.tag)}&action=generate`}>
                <div className="flex h-full cursor-pointer flex-col items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4 text-center transition hover:border-[var(--color-accent)]">
                  <span className="mb-2 text-2xl">📦</span>
                  <span className="text-sm font-semibold text-[var(--color-fg)]">
                    Generate Evidence Package
                  </span>
                  <span className="mt-1.5 text-[10px] leading-relaxed text-[var(--color-muted)]">
                    Compile a citation-backed audit package
                  </span>
                </div>
              </Link>
            </div>
          </Card>

          {/* Timeline preview */}
          {timeline && timeline.length > 0 && (
            <Card>
              <SectionTitle
                title="Recent Timeline Events"
                subtitle={`${timeline.length} event(s) detected`}
                action={
                  <button onClick={() => setTab("timeline")} className="text-sm text-[var(--color-accent)] hover:underline">
                    View all
                  </button>
                }
              />
              <ul className="space-y-2">
                {timeline.slice(0, 3).map((e) => (
                  <li key={e.id} className="flex items-start gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5">
                    <span className="mt-0.5 text-base">{eventIcon(e.event_type)}</span>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{e.title}</p>
                      <p className="text-xs text-[var(--color-muted)]">{e.date ? timeAgo(e.date) : "—"}</p>
                    </div>
                    <Badge tone={severityTone(e.severity)}>{e.severity}</Badge>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* Graph preview */}
          {graph && graph.counts.nodes > 0 && (
            <Card>
              <SectionTitle
                title="Knowledge Graph Preview"
                subtitle={`${graph.counts.nodes} node(s), ${graph.counts.edges} edge(s)`}
                action={
                  <button onClick={() => setTab("graph")} className="text-sm text-[var(--color-accent)] hover:underline">
                    View full graph
                  </button>
                }
              />
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-3">
                  <p className="text-2xl font-semibold">{graph.nodes.filter((n) => n.type === "document").length}</p>
                  <p className="text-xs text-[var(--color-muted)]">Documents</p>
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-3">
                  <p className="text-2xl font-semibold">{graph.nodes.filter((n) => n.type === "chunk").length}</p>
                  <p className="text-xs text-[var(--color-muted)]">Chunks</p>
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-3">
                  <p className="text-2xl font-semibold">{graph.nodes.filter((n) => n.type === "entity").length}</p>
                  <p className="text-xs text-[var(--color-muted)]">Entities</p>
                </div>
              </div>
            </Card>
          )}
        </div>
      )}

      {/* ── Related Documents tab ────────────────────────────────── */}
      {tab === "documents" && (
        <Card>
          <SectionTitle title="Related Documents" subtitle={`${documents?.length ?? 0} document(s) mention ${asset.tag}`} />
          {!documents || documents.length === 0 ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">No related documents found.</p>
          ) : (
            <>
              {/* Desktop / tablet: table (md+) */}
              <TableScrollRegion label={`Documents mentioning ${asset.tag}`} className="hidden md:block">
                <table className="w-full text-sm">
                  <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                    <tr>
                      <th className="px-4 py-2 font-medium">Document</th>
                      <th className="px-4 py-2 font-medium">Type</th>
                      <th className="px-4 py-2 font-medium">Chunks</th>
                      <th className="px-4 py-2 font-medium">When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((d) => (
                      <tr key={d.id} className="border-t border-[var(--color-border)]">
                        <td className="max-w-[20rem] truncate px-4 py-2.5" title={d.filename}>
                          <Link href={`/documents/${d.id}`} className="hover:underline">{d.filename}</Link>
                        </td>
                        <td className="px-4 py-2.5 text-[var(--color-muted)]">{d.content_type?.split("/").pop() ?? "—"}</td>
                        <td className="px-4 py-2.5 text-[var(--color-muted)]">{d.chunk_count}</td>
                        <td className="px-4 py-2.5 text-[var(--color-muted)]">{timeAgo(d.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScrollRegion>

              {/* Mobile: stacked cards (below md) */}
              <div className="space-y-3 md:hidden">
                {documents.map((d) => (
                  <MobileDataCard key={d.id}>
                    <Link href={`/documents/${d.id}`} className="block truncate font-medium text-[var(--color-accent)] hover:underline" title={d.filename}>
                      {d.filename}
                    </Link>
                    <DataRow label="Type">{d.content_type?.split("/").pop() ?? "—"}</DataRow>
                    <DataRow label="Chunks">{d.chunk_count}</DataRow>
                    <DataRow label="When">{timeAgo(d.created_at)}</DataRow>
                  </MobileDataCard>
                ))}
              </div>
            </>
          )}
        </Card>
      )}

      {/* ── Timeline tab ─────────────────────────────────────────── */}
      {tab === "timeline" && (
        <Card>
          <SectionTitle title="Timeline" subtitle={`${timeline?.length ?? 0} event(s) for ${asset.tag}`} />
          {!timeline || timeline.length === 0 ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">
              No timeline events found yet. Upload work orders, inspection reports, or maintenance records mentioning {asset.tag} to populate this timeline.
            </p>
          ) : (
            <div className="space-y-3">
              {timeline.map((e) => {
                const dateStr = e.date ? new Date(e.date).toISOString().slice(0, 10) : "—";
                return (
                  <div
                    key={e.id}
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4 transition hover:border-[var(--color-accent)]"
                  >
                    {/* Top row: date, event type badge, severity */}
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-mono font-medium text-[var(--color-fg)]">{dateStr}</span>
                      <span className="text-[var(--color-muted)]">|</span>
                      <Badge tone={
                        e.event_type === "failure" ? "bad"
                        : e.event_type === "compliance" ? "warn"
                        : e.event_type === "inspection" ? "ok"
                        : "neutral"
                      }>
                        {e.event_type.replace("_", " ")}
                      </Badge>
                      <span className="ml-auto"><Badge tone={severityTone(e.severity)}>{e.severity}</Badge></span>
                    </div>

                    {/* Title / description */}
                    <p className="mt-2 text-sm font-medium">
                      <span className="mr-1.5">{eventIcon(e.event_type)}</span>
                      {e.title}
                    </p>

                    {/* Evidence text preview */}
                    {e.text_preview && (
                      <p className="mt-2 wrap-anywhere rounded-md bg-[var(--color-surface-2)] px-3 py-2 text-xs leading-relaxed text-[var(--color-muted)]">
                        &ldquo;{e.text_preview}&rdquo;
                      </p>
                    )}

                    {/* Source document + evidence chunk link */}
                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--color-muted)]">
                      {e.filename && e.document_id && (
                        <span>
                          <strong className="text-[var(--color-accent-2)]">Source:</strong>{" "}
                          <Link href={`/documents/${e.document_id}`} className="text-[var(--color-accent)] hover:underline font-mono">
                            {e.filename}
                          </Link>
                        </span>
                      )}
                      {e.chunk_id && (
                        <span>
                          <strong className="text-[var(--color-accent-2)]">Evidence:</strong>{" "}
                          chunk {e.chunk_index ?? "?"} ({e.chunk_id.slice(0, 12)}…)
                        </span>
                      )}
                      {e.reason_tags.length > 0 && (
                        <span className="flex gap-1">
                          {e.reason_tags.map((t) => (
                            <Badge key={t}>{t}</Badge>
                          ))}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>
      )}

      {/* ── Failure Intelligence tab ─────────────────────────────── */}
      {tab === "failure" && (
        <Card>
          <SectionTitle
            title="Failure Intelligence"
            subtitle={`Evidence-backed failure history for ${asset.tag}`}
          />
          {!failure || failure.insufficient_data ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">
              No documented failure evidence for {asset.tag} yet. Upload work orders,
              RCA findings, or inspection reports mentioning {asset.tag} to build its
              failure history.
            </p>
          ) : (
            <div className="space-y-5">
              {/* Summary stats */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard label="Failure events" value={String(failure.failure_event_count)} />
                <StatCard label="Distinct modes" value={String(failure.distinct_failure_modes)} />
                <StatCard label="Source documents" value={String(failure.document_count)} />
                <StatCard label="Evidence coverage" value={failure.coverage_confidence} />
              </div>

              {/* Failure modes */}
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  Failure modes (by documented occurrences)
                </p>
                <div className="flex flex-wrap gap-2">
                  {failure.failure_modes.map((m) => (
                    <Badge
                      key={m.mode}
                      tone={failure.repeated_failure_modes.includes(m.mode) ? "bad" : "neutral"}
                    >
                      {m.mode.replace(/_/g, " ")} · {m.count}
                    </Badge>
                  ))}
                </div>
                {failure.repeated_failure_modes.length > 0 && (
                  <p className="mt-2 text-xs text-[var(--color-muted)]">
                    Highlighted modes recur across multiple evidence items.
                  </p>
                )}
              </div>

              {/* Recent failure events */}
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                  Recent failure events
                </p>
                <div className="space-y-3">
                  {failure.recent_failure_events.map((e, i) => {
                    const dateStr = e.date ? new Date(e.date).toISOString().slice(0, 10) : "—";
                    return (
                      <div
                        key={`${e.citation.chunk_id ?? "x"}-${i}`}
                        className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4"
                      >
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="font-mono font-medium text-[var(--color-fg)]">{dateStr}</span>
                          <span className="text-[var(--color-muted)]">|</span>
                          <Badge tone="neutral">{e.event_type.replace(/_/g, " ")}</Badge>
                          <span className="ml-auto"><Badge tone={severityTone(e.severity)}>{e.severity}</Badge></span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {e.failure_modes.map((m) => (
                            <Badge key={m} tone="warn">{m.replace(/_/g, " ")}</Badge>
                          ))}
                        </div>
                        {e.text_preview && (
                          <p className="mt-2 wrap-anywhere rounded-md bg-[var(--color-surface-2)] px-3 py-2 text-xs leading-relaxed text-[var(--color-muted)]">
                            &ldquo;{e.text_preview}&rdquo;
                          </p>
                        )}
                        {e.filename && e.citation.document_id && (
                          <p className="mt-3 text-xs text-[var(--color-muted)]">
                            <strong className="text-[var(--color-accent-2)]">Source:</strong>{" "}
                            <Link
                              href={`/documents/${e.citation.document_id}`}
                              className="font-mono text-[var(--color-accent)] hover:underline"
                            >
                              {e.filename}
                            </Link>
                            {e.citation.chunk_index != null && (
                              <span> · chunk {e.citation.chunk_index}</span>
                            )}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Maintenance actions */}
              {failure.maintenance_actions.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">
                    Documented maintenance actions
                  </p>
                  <div className="space-y-2">
                    {failure.maintenance_actions.map((a, i) => (
                      <div
                        key={`${a.citation.chunk_id ?? "m"}-${i}`}
                        className="rounded-md border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2 text-xs"
                      >
                        {a.text_preview && (
                          <p className="text-[var(--color-muted)]">&ldquo;{a.text_preview}&rdquo;</p>
                        )}
                        {a.filename && a.citation.document_id && (
                          <p className="mt-1 text-[var(--color-muted)]">
                            <strong className="text-[var(--color-accent-2)]">Source:</strong>{" "}
                            <Link
                              href={`/documents/${a.citation.document_id}`}
                              className="font-mono text-[var(--color-accent)] hover:underline"
                            >
                              {a.filename}
                            </Link>
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <p className="border-t border-[var(--color-border)] pt-3 text-xs italic text-[var(--color-muted)]">
                {failure.disclaimer}
              </p>
            </div>
          )}
        </Card>
      )}

      {/* ── Evidence Mentions tab ────────────────────────────────── */}
      {tab === "mentions" && (
        <Card>
          <SectionTitle title="Evidence Mentions" subtitle={`${mentions?.count ?? 0} mention(s) with citation data`} />
          {!mentions || mentions.mentions.length === 0 ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">No evidence mentions found for this asset.</p>
          ) : (
            <ul className="space-y-4">
              {mentions.mentions.map((m, i) => (
                <li key={m.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4">
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded bg-[var(--color-surface-2)] text-xs font-medium text-[var(--color-accent)]">{i + 1}</span>
                    <Link
                      href={`/documents/${m.document_id}`}
                      className="text-sm font-medium text-[var(--color-accent)] hover:underline"
                    >
                      {m.filename ?? m.document_id}
                    </Link>
                    <span className="text-xs text-[var(--color-muted)]">— chunk {m.chunk_index ?? "?"}</span>
                  </div>
                  {m.text && (
                    <p className="mt-2 wrap-anywhere rounded-md bg-[var(--color-surface-2)] px-3 py-2 text-sm leading-relaxed text-[var(--color-muted)]">
                      &ldquo;{m.text}&rdquo;
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-muted)]">
                    <span>
                      <strong className="text-[var(--color-accent-2)]">Citation:</strong>{" "}
                      doc {m.citation.document_id?.slice(0, 8) ?? "—"}…
                    </span>
                    <span>chunk_id: {m.citation.chunk_id?.slice(0, 12) ?? "—"}…</span>
                    <span>chunk_index: {m.citation.chunk_index ?? "—"}</span>
                    {m.confidence !== null && <Badge>confidence: {m.confidence.toFixed(2)}</Badge>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {/* ── Knowledge Graph tab ──────────────────────────────────── */}
      {tab === "graph" && (
        <div className="space-y-6">
          {/* Controls Bar */}
          <Card className="flex flex-wrap items-center justify-between gap-4 py-3">
            <div className="flex flex-wrap items-center gap-6">
              <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                <input
                  type="checkbox"
                  checked={graphIncludeChunks}
                  onChange={(e) => setGraphIncludeChunks(e.target.checked)}
                  className="rounded border-[var(--color-border)] bg-[var(--color-base)] text-[var(--color-accent)] focus:ring-0"
                />
                Include Chunks
              </label>

              <div className="flex items-center gap-2">
                <label htmlFor="relation-filter" className="text-sm font-medium">
                  Relation Type:
                </label>
                <select
                  id="relation-filter"
                  value={graphRelationType}
                  onChange={(e) => setGraphRelationType(e.target.value)}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-2.5 py-1 text-xs outline-none focus:border-[var(--color-accent)]"
                >
                  <option value="">All Relations</option>
                  <option value="mentioned_in">mentioned_in</option>
                  <option value="supported_by_chunk">supported_by_chunk</option>
                  <option value="has_entity">has_entity</option>
                </select>
              </div>
            </div>

            {graph && (
              <span className="text-xs text-[var(--color-muted)] font-mono">
                {graph.counts.nodes} Nodes | {graph.counts.edges} Edges
              </span>
            )}
          </Card>

          {/* Visualization Split Layout */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* SVG Graph Viewport */}
            <Card className="lg:col-span-2 flex flex-col items-center justify-center overflow-hidden">
              <SectionTitle title="Knowledge Graph Visualization" subtitle="Radial node-link layout representing derived asset relations" />
              
              {!graph || graph.nodes.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <p className="text-sm text-[var(--color-muted)]">No graph nodes match current filters.</p>
                </div>
              ) : (() => {
                const width = 600;
                const height = 450;
                const centerX = width / 2;
                const centerY = height / 2;

                // Center node ID namespaces
                const centerNodeId = `asset:${asset.tag}`;

                // Separate center node from outer nodes
                const outerNodes = graph.nodes.filter(n => n.id !== centerNodeId);
                const nOuter = outerNodes.length;

                // Position map
                const positions: Record<string, { x: number; y: number }> = {
                  [centerNodeId]: { x: centerX, y: centerY }
                };

                // Place outer nodes radially
                outerNodes.forEach((node, i) => {
                  const r = 160; // radius of layout circle
                  const angle = (2 * Math.PI * i) / nOuter;
                  positions[node.id] = {
                    x: centerX + r * Math.cos(angle),
                    y: centerY + r * Math.sin(angle)
                  };
                });

                // Colors mapping helper
                const getNodeConfig = (type: string, isSelected: boolean) => {
                  const base = {
                    asset: { r: 22, fill: "rgb(235, 120, 20)", stroke: "rgba(235, 120, 20, 0.4)", textYOffset: 34 },
                    document: { r: 15, fill: "rgb(16, 185, 129)", stroke: "rgba(16, 185, 129, 0.3)", textYOffset: 25 },
                    chunk: { r: 10, fill: "rgb(139, 92, 246)", stroke: "rgba(139, 92, 246, 0.3)", textYOffset: 20 },
                    entity: { r: 13, fill: "rgb(245, 158, 11)", stroke: "rgba(245, 158, 11, 0.3)", textYOffset: 23 },
                  }[type] || { r: 12, fill: "#71717a", stroke: "rgba(113, 113, 122, 0.3)", textYOffset: 22 };

                  if (isSelected) {
                    return {
                      ...base,
                      stroke: "var(--color-accent)",
                      r: base.r + 4
                    };
                  }
                  return base;
                };

                return (
                  <div className="relative w-full aspect-[4/3] bg-[var(--color-base)] border border-[var(--color-border)] rounded-xl overflow-hidden mt-2">
                    <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} className="select-none">
                      {/* Define defs for markers */}
                      <defs>
                        <marker id="arrow" viewBox="0 0 10 10" refX="24" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-border)" />
                        </marker>
                      </defs>

                      {/* Edges layer */}
                      {graph.edges.map((edge) => {
                        const sourcePos = positions[edge.source];
                        const targetPos = positions[edge.target];
                        if (!sourcePos || !targetPos) return null;

                        return (
                          <g key={edge.id}>
                            <line
                              x1={sourcePos.x}
                              y1={sourcePos.y}
                              x2={targetPos.x}
                              y2={targetPos.y}
                              stroke="var(--color-border)"
                              strokeWidth="1.5"
                              strokeDasharray={edge.relation_type === "supported_by_chunk" ? "4" : undefined}
                              markerEnd="url(#arrow)"
                            />
                            {/* Invisible fat line for hover */}
                            <line
                              x1={sourcePos.x}
                              y1={sourcePos.y}
                              x2={targetPos.x}
                              y2={targetPos.y}
                              stroke="transparent"
                              strokeWidth="12"
                              className="cursor-pointer"
                            >
                              <title>Relation: {edge.relation_type}</title>
                            </line>
                          </g>
                        );
                      })}

                      {/* Nodes layer */}
                      {graph.nodes.map((node) => {
                        const pos = positions[node.id];
                        if (!pos) return null;
                        
                        const isSelected = selectedNode?.id === node.id;
                        const config = getNodeConfig(node.type, isSelected);

                        return (
                          <g
                            key={node.id}
                            transform={`translate(${pos.x}, ${pos.y})`}
                            onClick={() => setSelectedNode(node)}
                            className="cursor-pointer"
                          >
                            {/* Outer Glow for selection */}
                            {isSelected && (
                              <circle
                                cx="0"
                                cy="0"
                                r={config.r + 6}
                                fill="transparent"
                                stroke="var(--color-accent)"
                                strokeWidth="1.5"
                                strokeDasharray="3 3"
                                className="animate-spin"
                                style={{ animationDuration: '8s' }}
                              />
                            )}

                            {/* Outer halo */}
                            <circle
                              cx="0"
                              cy="0"
                              r={config.r + 3}
                              fill="transparent"
                              stroke={config.stroke}
                              strokeWidth="2"
                            />

                            {/* Core circle */}
                            <circle
                              cx="0"
                              cy="0"
                              r={config.r}
                              fill={config.fill}
                              className="transition-transform duration-200 hover:scale-110"
                            />

                            {/* Label Text */}
                            <text
                              x="0"
                              y={config.textYOffset}
                              textAnchor="middle"
                              className="text-[10px] font-bold fill-white select-none pointer-events-none"
                              stroke="var(--color-surface)"
                              strokeWidth="3px"
                              paintOrder="stroke"
                              strokeLinejoin="round"
                            >
                              {node.label}
                            </text>
                          </g>
                        );
                      })}
                    </svg>
                  </div>
                );
              })()}
            </Card>

            {/* Sidebar Details Panel */}
            <Card className="flex flex-col">
              <SectionTitle title="Node Inspector" subtitle="Metadata & source chunk properties" />

              {!selectedNode ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center py-12 text-[var(--color-muted)] border-2 border-dashed border-[var(--color-border)] rounded-xl px-4 mt-2 bg-[var(--color-surface-2)]/20">
                  <span className="text-2xl mb-2">ℹ️</span>
                  <p className="text-xs">Click on any node in the graph visualization to view detailed properties, relationships, and links to source documents.</p>
                </div>
              ) : (() => {
                const node = selectedNode;
                
                // Helper to resolve chunk text preview from other components
                const getChunkText = (id: string) => {
                  if (mentions) {
                    const m = mentions.mentions.find(x => x.chunk_id === id);
                    if (m && m.text) return m.text;
                  }
                  if (timeline) {
                    const t = timeline.find(x => x.chunk_id === id);
                    if (t && t.text_preview) return t.text_preview;
                  }
                  return null;
                };

                // Helper to resolve entity details
                const getEntityDetails = (id: string) => {
                  return facts?.entities.find(x => x.id === id) || null;
                };

                return (
                  <div className="flex-1 space-y-4 mt-2">
                    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge tone={
                          node.type === "asset" ? "warn"
                          : node.type === "document" ? "ok"
                          : "neutral"
                        }>
                          {node.type}
                        </Badge>
                        <span className="text-xs text-[var(--color-muted)] font-mono">{node.id.split(":").shift()}</span>
                      </div>
                      <h3 className="text-base font-bold break-all">{node.label}</h3>
                    </div>

                    <dl className="space-y-3 text-xs">
                      <div>
                        <dt className="text-[var(--color-muted)] font-medium">Node ID</dt>
                        <dd className="font-mono bg-[var(--color-surface-2)] p-1.5 rounded mt-1 overflow-x-auto select-all">{node.id}</dd>
                      </div>

                      {/* Render type-specific fields */}
                      {node.type === "document" && node.document_id && (
                        <div className="pt-2">
                          <dt className="text-[var(--color-muted)] font-medium">Document ID</dt>
                          <dd className="break-all font-mono text-xs">{node.document_id}</dd>
                          
                          <Link
                            href={`/documents/${node.document_id}`}
                            className="mt-4 inline-flex items-center justify-center w-full rounded-lg bg-[var(--color-accent)] px-3 py-2 text-xs font-semibold text-[var(--color-base)] hover:opacity-90 transition"
                          >
                            📄 View Document Chunks &rarr;
                          </Link>
                        </div>
                      )}

                      {node.type === "chunk" && (
                        <div className="space-y-3 pt-2">
                          {node.document_id && (
                            <div>
                              <dt className="text-[var(--color-muted)] font-medium">Parent Document</dt>
                              <dd>
                                <Link href={`/documents/${node.document_id}`} className="text-[var(--color-accent)] hover:underline font-mono">
                                  {node.document_id.slice(0, 12)}…
                                </Link>
                              </dd>
                            </div>
                          )}
                          {node.chunk_index !== undefined && (
                            <div>
                              <dt className="text-[var(--color-muted)] font-medium">Chunk index</dt>
                              <dd>{node.chunk_index}</dd>
                            </div>
                          )}
                          <div>
                            <dt className="text-[var(--color-muted)] font-medium mb-1.5">Evidence Text</dt>
                            {(() => {
                              const text = getChunkText(node.chunk_id || node.id.split(":").pop() || "");
                              return text ? (
                                <dd className="bg-[var(--color-surface-2)] p-3 rounded-lg border border-[var(--color-border)] leading-relaxed max-h-52 overflow-y-auto select-text font-serif italic text-xs">
                                  &ldquo;{text}&rdquo;
                                </dd>
                              ) : (
                                <dd className="text-[var(--color-muted)] italic">Evidence snippet not stored in preview memory.</dd>
                              );
                            })()}
                          </div>
                        </div>
                      )}

                      {node.type === "entity" && (
                        <div className="space-y-3 pt-2">
                          {(() => {
                            const details = getEntityDetails(node.entity_id || node.id.split(":").pop() || "");
                            if (!details) return (
                              <div>
                                <dt className="text-[var(--color-muted)] font-medium">Raw Value</dt>
                                <dd className="font-semibold text-sm">{node.label}</dd>
                              </div>
                            );
                            return (
                              <>
                                <div>
                                  <dt className="text-[var(--color-muted)] font-medium">Entity Type</dt>
                                  <dd className="capitalize font-semibold">{details.entity_type.replace("_", " ")}</dd>
                                </div>
                                <div>
                                  <dt className="text-[var(--color-muted)] font-medium">Raw value</dt>
                                  <dd className="mt-0.5 inline-block max-w-full wrap-anywhere rounded bg-[var(--color-surface-2)] px-2 py-1 font-mono">{details.raw_value}</dd>
                                </div>
                                <div>
                                  <dt className="text-[var(--color-muted)] font-medium">Normalized value</dt>
                                  <dd className="mt-0.5 inline-block max-w-full wrap-anywhere rounded bg-[var(--color-surface-2)] px-2 py-1 font-mono">{details.normalized_value}</dd>
                                </div>
                                {details.confidence !== null && (
                                  <div>
                                    <dt className="text-[var(--color-muted)] font-medium">Extraction Confidence</dt>
                                    <dd>{(details.confidence * 100).toFixed(0)}% ({details.confidence.toFixed(2)})</dd>
                                  </div>
                                )}
                                {details.extraction_method && (
                                  <div>
                                    <dt className="text-[var(--color-muted)] font-medium">Extraction Method</dt>
                                    <dd className="text-[var(--color-muted)]">{details.extraction_method}</dd>
                                  </div>
                                )}
                              </>
                            );
                          })()}
                        </div>
                      )}

                      {node.type === "asset" && (
                        <div className="space-y-3 pt-2">
                          {asset.asset_type && (
                            <div>
                              <dt className="text-[var(--color-muted)] font-medium">Equipment category</dt>
                              <dd className="capitalize">{asset.asset_type.replace("_", " ")}</dd>
                            </div>
                          )}
                          <div>
                            <dt className="text-[var(--color-muted)] font-medium">Display name</dt>
                            <dd>{asset.display_name}</dd>
                          </div>
                          <div>
                            <dt className="text-[var(--color-muted)] font-medium">Created</dt>
                            <dd>{asset.created_at}</dd>
                          </div>
                        </div>
                      )}
                    </dl>
                  </div>
                );
              })()}
            </Card>
          </div>
        </div>
      )}

      {/* ── Facts tab ────────────────────────────────────────────── */}
      {tab === "facts" && (
        <div className="space-y-6">
          {!facts ? (
            <Card>
              <p className="py-6 text-center text-sm text-[var(--color-muted)]">No facts available.</p>
            </Card>
          ) : (
            <>
              {/* Summary stats */}
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <StatCard label="Mentions" value={facts.mention_count} />
                <StatCard label="Documents" value={facts.document_count} />
                <StatCard label="Entities" value={facts.entities.length} />
              </div>

              {/* Entities table */}
              <Card>
                <SectionTitle title="Extracted Entities" subtitle={`${facts.entities.length} entity(ies) linked to ${asset.tag}`} />
                {facts.entities.length === 0 ? (
                  <p className="py-6 text-center text-sm text-[var(--color-muted)]">No entities extracted.</p>
                ) : (
                  <>
                    {/* Desktop / tablet: table (md+) */}
                    <TableScrollRegion label={`Extracted entities for ${asset.tag}`} className="hidden md:block">
                      <table className="w-full text-sm">
                        <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                          <tr>
                            <th className="px-4 py-2 font-medium">Type</th>
                            <th className="px-4 py-2 font-medium">Value</th>
                            <th className="px-4 py-2 font-medium">Normalized</th>
                            <th className="px-4 py-2 font-medium">Confidence</th>
                            <th className="px-4 py-2 font-medium">Method</th>
                          </tr>
                        </thead>
                        <tbody>
                          {facts.entities.map((e) => (
                            <tr key={e.id} className="border-t border-[var(--color-border)]">
                              <td className="px-4 py-2.5"><Badge>{e.entity_type}</Badge></td>
                              <td className="wrap-anywhere px-4 py-2.5">{e.raw_value}</td>
                              <td className="wrap-anywhere px-4 py-2.5 font-medium">{e.normalized_value}</td>
                              <td className="px-4 py-2.5 text-[var(--color-muted)]">{e.confidence !== null ? e.confidence.toFixed(2) : "—"}</td>
                              <td className="px-4 py-2.5 text-xs text-[var(--color-muted)]">{e.extraction_method ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </TableScrollRegion>

                    {/* Mobile: stacked cards (below md) */}
                    <div className="space-y-3 md:hidden">
                      {facts.entities.map((e) => (
                        <MobileDataCard key={e.id}>
                          <div className="flex items-center justify-between gap-2">
                            <Badge>{e.entity_type}</Badge>
                            <span className="text-xs text-[var(--color-muted)]">
                              {e.confidence !== null ? `conf ${e.confidence.toFixed(2)}` : "—"}
                            </span>
                          </div>
                          <DataRow label="Value">{e.raw_value}</DataRow>
                          <DataRow label="Normalized">{e.normalized_value}</DataRow>
                          <DataRow label="Method">{e.extraction_method ?? "—"}</DataRow>
                        </MobileDataCard>
                      ))}
                    </div>
                  </>
                )}
              </Card>

              {/* Supporting documents */}
              <Card>
                <SectionTitle title="Supporting Documents" subtitle={`${facts.documents.length} document(s)`} />
                {facts.documents.length === 0 ? (
                  <p className="py-6 text-center text-sm text-[var(--color-muted)]">No supporting documents.</p>
                ) : (
                  <ul className="divide-y divide-[var(--color-border)]">
                    {facts.documents.map((d) => (
                      <li key={d.id} className="flex items-center justify-between gap-4 py-3">
                        <span className="text-sm">{d.filename}</span>
                        <span className="text-xs text-[var(--color-muted)]">{d.chunk_count} chunks</span>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </>
          )}
        </div>
      )}

      {/* ── Ask About This Asset tab ─────────────────────────────── */}
      {tab === "ask" && (
        <Card>
          <SectionTitle
            title={`Ask About ${asset.tag}`}
            subtitle="Asset-scoped question answering with citations from relevant documents"
          />

          {/* Input */}
          <div className="flex flex-col gap-3 sm:flex-row">
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAsk()}
              placeholder={`e.g. "What maintenance was done on ${asset.tag}?"`}
              className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-4 py-2.5 text-sm outline-none transition focus:border-[var(--color-accent)]"
            />
            <button
              onClick={handleAsk}
              disabled={asking || !question.trim()}
              className="shrink-0 rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[var(--color-base)] transition hover:opacity-90 disabled:opacity-50"
            >
              {asking ? "Asking…" : "Ask"}
            </button>
          </div>

          {/* Answer */}
          {answer && (
            <div className="mt-6 space-y-4">
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4">
                <div className="mb-2 flex items-center gap-2">
                  <Badge tone={answer.confidence === "high" ? "ok" : answer.confidence === "medium" ? "warn" : "bad"}>
                    {answer.confidence} confidence
                  </Badge>
                  {answer.query_intent && <Badge>{answer.query_intent}</Badge>}
                  <span className="text-xs text-[var(--color-muted)]">{answer.retrieved_count} chunk(s) retrieved</span>
                </div>
                <p className="text-sm leading-relaxed">{answer.answer}</p>
              </div>

              {/* Citations */}
              {answer.citations.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Citations</h3>
                  <ul className="space-y-2">
                    {answer.citations.map((c, i) => (
                      <li key={c.chunk_id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
                        <div className="flex items-center gap-2 text-xs text-[var(--color-muted)]">
                          <span className="flex h-5 w-5 items-center justify-center rounded bg-[var(--color-accent)] text-[10px] font-bold text-[var(--color-base)]">{i + 1}</span>
                          <Link
                            href={`/documents/${c.document_id}`}
                            className="font-medium text-[var(--color-accent)] hover:underline"
                          >
                            {c.filename ?? c.document_id}
                          </Link>
                          {c.page_number !== null && c.page_number !== undefined && <span>page {c.page_number}</span>}
                          <span>score: {c.score.toFixed(3)}</span>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-[var(--color-muted)]">&ldquo;{c.text_preview}&rdquo;</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Related assets */}
              {answer.related_assets && answer.related_assets.length > 0 && (
                <div>
                  <h3 className="mb-2 text-sm font-semibold">Related Assets</h3>
                  <div className="flex flex-wrap gap-2">
                    {answer.related_assets.map((t) => (
                      <Link key={t} href={`/assets/${t}`}>
                        <Badge tone="ok">{t}</Badge>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
