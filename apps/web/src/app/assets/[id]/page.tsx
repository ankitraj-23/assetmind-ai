"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Card,
  Badge,
  Metric,
  SectionTitle,
  Tabs,
  Disclosure,
  TableScrollRegion,
  MobileDataCard,
  DataRow,
  EmptyState,
  ErrorState,
  LoadingState,
  type TabItem,
} from "@/components/ui";
import {
  ChatIcon,
  SearchIcon,
  ShieldIcon,
  CubeIcon,
  DocumentIcon,
  AlertIcon,
  ClockIcon,
  ArrowRightIcon,
  RepeatIcon,
} from "@/components/icons";
import { AssetGraph } from "@/components/AssetGraph";
import {
  getAsset,
  getAssetMentions,
  getAssetDocuments,
  getAssetTimeline,
  getAssetGraph,
  getAssetFacts,
  getAssetFailureIntelligence,
  type ApiAsset,
  type ApiAssetMention,
  type ApiAssetMentionsResponse,
  type ApiDocument,
  type ApiAssetTimelineEvent,
  type ApiAssetGraphResponse,
  type ApiAssetGraphNode,
  type ApiAssetFacts,
  type ApiFailureIntelligence,
  type ApiFailureEvent,
} from "@/lib/api";

/* ── Visible tabs (reduced from 8 to 5) ─────────────────────────────────
   Failure Intelligence, Evidence Mentions and Facts are consolidated into
   "Intelligence"; the old "Ask" tab is replaced by the header action. */
const TABS: readonly TabItem[] = [
  { key: "overview", label: "Overview" },
  { key: "timeline", label: "Timeline" },
  { key: "documents", label: "Documents" },
  { key: "intelligence", label: "Intelligence" },
  { key: "graph", label: "Graph" },
];
type TabKey = (typeof TABS)[number]["key"];

/* Legacy ?tab= values → current tab, so old deep links keep working. */
const TAB_ALIASES: Record<string, TabKey> = {
  overview: "overview",
  timeline: "timeline",
  documents: "documents",
  graph: "graph",
  intelligence: "intelligence",
  failure: "intelligence",
  mentions: "intelligence",
  facts: "intelligence",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

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

function prettyType(t?: string | null): string {
  return t ? t.replace(/_/g, " ") : "equipment";
}

function severityTone(s: string): "ok" | "warn" | "bad" | "neutral" {
  if (s === "high") return "bad";
  if (s === "medium") return "warn";
  if (s === "low") return "ok";
  return "neutral";
}

function eventTypeTone(type: string): "ok" | "warn" | "bad" | "neutral" {
  if (type === "failure") return "bad";
  if (type === "compliance") return "warn";
  if (type === "inspection") return "ok";
  return "neutral";
}

type StatusLevel = "critical" | "warning" | "positive" | "neutral";
const LEVEL_BADGE: Record<StatusLevel, "ok" | "warn" | "bad" | "neutral"> = {
  critical: "bad",
  warning: "warn",
  positive: "ok",
  neutral: "neutral",
};

/* A conservative, evidence-derived status — never an invented risk score. */
function failureStatus(f: ApiFailureIntelligence | null): { level: StatusLevel; label: string } {
  if (!f || f.insufficient_data) return { level: "neutral", label: "No failure evidence" };
  if (f.repeated_failure_modes.length > 0) return { level: "critical", label: "Recurring failure evidence" };
  if (f.failure_event_count > 0) return { level: "warning", label: `${f.failure_event_count} failure events` };
  return { level: "positive", label: "No failure evidence" };
}

/* ── Header action ──────────────────────────────────────────────────── */
function HeaderAction({
  href,
  icon,
  children,
  variant,
}: {
  href: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  variant: "primary" | "secondary" | "ghost";
}) {
  const base =
    "inline-flex min-h-[40px] items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium outline-none transition focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]";
  const variants = {
    primary: "bg-[var(--color-accent)] text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]",
    secondary: "border border-[var(--color-border)] hover:border-[var(--color-accent)]",
    ghost: "border border-[var(--color-border)] text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-fg)]",
  } as const;
  return (
    <Link href={href} className={`${base} ${variants[variant]}`}>
      {icon}
      {children}
    </Link>
  );
}

/* ── Source citation line (secondary, links to the document) ─────────── */
function CitationSource({
  filename,
  documentId,
  chunkIndex,
}: {
  filename: string | null;
  documentId: string | null | undefined;
  chunkIndex: number | null | undefined;
}) {
  if (!filename || !documentId) return null;
  return (
    <p className="text-xs text-[var(--color-muted)]">
      <span className="font-medium text-[var(--color-accent-2)]">Source: </span>
      <Link href={`/documents/${documentId}`} className="wrap-anywhere text-[var(--color-accent)] hover:underline">
        {filename}
      </Link>
      {chunkIndex != null && <span> · chunk {chunkIndex}</span>}
    </p>
  );
}

/* ── A single failure event (Intelligence tab) ──────────────────────── */
function FailureEventItem({ event }: { event: ApiFailureEvent }) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <time className="font-medium text-[var(--color-fg)]">{formatDate(event.date)}</time>
        <Badge tone={eventTypeTone(event.event_type)}>{event.event_type.replace(/_/g, " ")}</Badge>
        <span className="ml-auto">
          <Badge tone={severityTone(event.severity)}>{event.severity}</Badge>
        </span>
      </div>
      {event.failure_modes.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {event.failure_modes.map((m) => (
            <Badge key={m} tone="warn">
              {m.replace(/_/g, " ")}
            </Badge>
          ))}
        </div>
      )}
      {(event.text_preview || (event.filename && event.citation.document_id)) && (
        <div className="mt-3">
          <Disclosure summary="Show evidence">
            {event.text_preview && (
              <p className="wrap-anywhere rounded-md bg-[var(--color-surface-2)] px-3 py-2 text-xs leading-relaxed text-[var(--color-muted)]">
                &ldquo;{event.text_preview}&rdquo;
              </p>
            )}
            <div className="mt-2">
              <CitationSource
                filename={event.filename}
                documentId={event.citation.document_id}
                chunkIndex={event.citation.chunk_index}
              />
            </div>
          </Disclosure>
        </div>
      )}
    </div>
  );
}

/* ── A single evidence mention (Intelligence tab) ───────────────────── */
function MentionItem({ mention, index }: { mention: ApiAssetMention; index: number }) {
  return (
    <li className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-[var(--color-surface-2)] text-xs font-medium text-[var(--color-accent)]">
          {index + 1}
        </span>
        <Link
          href={`/documents/${mention.document_id}`}
          className="wrap-anywhere text-sm font-medium text-[var(--color-accent)] hover:underline"
        >
          {mention.filename ?? mention.document_id}
        </Link>
        {mention.chunk_index != null && (
          <span className="text-xs text-[var(--color-muted)]">chunk {mention.chunk_index}</span>
        )}
        {mention.confidence !== null && (
          <span className="ml-auto">
            <Badge>confidence {mention.confidence.toFixed(2)}</Badge>
          </span>
        )}
      </div>
      {mention.text && (
        <p className="mt-2 wrap-anywhere rounded-md bg-[var(--color-surface-2)] px-3 py-2 text-sm leading-relaxed text-[var(--color-muted)]">
          &ldquo;{mention.text}&rdquo;
        </p>
      )}
      {mention.citation.chunk_id && (
        <div className="mt-2">
          <Disclosure summary="Citation IDs">
            <dl className="space-y-1 text-xs text-[var(--color-muted)]">
              <div className="flex gap-2">
                <dt className="font-medium">document_id</dt>
                <dd className="wrap-anywhere font-mono">{mention.citation.document_id ?? "—"}</dd>
              </div>
              <div className="flex gap-2">
                <dt className="font-medium">chunk_id</dt>
                <dd className="wrap-anywhere font-mono">{mention.citation.chunk_id ?? "—"}</dd>
              </div>
            </dl>
          </Disclosure>
        </div>
      )}
    </li>
  );
}

/* ── Graph node inspector (Graph tab side panel) ────────────────────── */
function NodeInspector({
  node,
  asset,
  mentions,
  timeline,
  facts,
}: {
  node: ApiAssetGraphNode | null;
  asset: ApiAsset;
  mentions: ApiAssetMentionsResponse | null;
  timeline: ApiAssetTimelineEvent[] | null;
  facts: ApiAssetFacts | null;
}) {
  if (!node) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--color-border)] px-4 py-12 text-center">
        <CubeIcon className="h-6 w-6 text-[var(--color-muted)]" />
        <p className="text-xs text-[var(--color-muted)]">
          Select a node in the graph or node list to inspect its properties, relationships and source links.
        </p>
      </div>
    );
  }

  const chunkText = (() => {
    const id = node.chunk_id ?? node.id.split(":").pop() ?? "";
    const m = mentions?.mentions.find((x) => x.chunk_id === id);
    if (m?.text) return m.text;
    const t = timeline?.find((x) => x.chunk_id === id);
    return t?.text_preview ?? null;
  })();
  const entity = facts?.entities.find((x) => x.id === (node.entity_id ?? node.id.split(":").pop()));

  return (
    <div className="flex-1 space-y-4">
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
        <Badge tone={node.type === "asset" ? "warn" : node.type === "document" ? "ok" : "neutral"}>
          {node.type}
        </Badge>
        <h3 className="mt-2 wrap-anywhere text-base font-semibold">{node.label}</h3>
      </div>

      <dl className="space-y-3 text-xs">
        {node.type === "document" && node.document_id && (
          <Link
            href={`/documents/${node.document_id}`}
            className="inline-flex min-h-[40px] w-full items-center justify-center gap-1.5 rounded-lg bg-[var(--color-accent)] px-3 py-2 text-xs font-semibold text-[var(--color-accent-fg)] transition hover:bg-[var(--color-accent-hover)]"
          >
            <DocumentIcon className="h-4 w-4" />
            View document
          </Link>
        )}

        {node.type === "chunk" && (
          <>
            {node.document_id && (
              <div>
                <dt className="font-medium text-[var(--color-muted)]">Parent document</dt>
                <dd>
                  <Link href={`/documents/${node.document_id}`} className="text-[var(--color-accent)] hover:underline">
                    Open document
                  </Link>
                </dd>
              </div>
            )}
            {node.chunk_index !== undefined && (
              <div>
                <dt className="font-medium text-[var(--color-muted)]">Chunk index</dt>
                <dd>{node.chunk_index}</dd>
              </div>
            )}
            <div>
              <dt className="mb-1 font-medium text-[var(--color-muted)]">Evidence text</dt>
              {chunkText ? (
                <dd className="max-h-52 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 text-xs italic leading-relaxed">
                  &ldquo;{chunkText}&rdquo;
                </dd>
              ) : (
                <dd className="italic text-[var(--color-muted)]">Evidence snippet not available in preview.</dd>
              )}
            </div>
          </>
        )}

        {node.type === "entity" && entity && (
          <>
            <div>
              <dt className="font-medium text-[var(--color-muted)]">Entity type</dt>
              <dd className="capitalize">{entity.entity_type.replace(/_/g, " ")}</dd>
            </div>
            <div>
              <dt className="font-medium text-[var(--color-muted)]">Value</dt>
              <dd className="wrap-anywhere font-medium">{entity.normalized_value || entity.raw_value}</dd>
            </div>
            {entity.confidence !== null && (
              <div>
                <dt className="font-medium text-[var(--color-muted)]">Extraction confidence</dt>
                <dd>{(entity.confidence * 100).toFixed(0)}%</dd>
              </div>
            )}
          </>
        )}
        {node.type === "entity" && !entity && (
          <div>
            <dt className="font-medium text-[var(--color-muted)]">Value</dt>
            <dd className="wrap-anywhere font-medium">{node.label}</dd>
          </div>
        )}

        {node.type === "asset" && (
          <>
            {asset.asset_type && (
              <div>
                <dt className="font-medium text-[var(--color-muted)]">Equipment category</dt>
                <dd className="capitalize">{prettyType(asset.asset_type)}</dd>
              </div>
            )}
            <div>
              <dt className="font-medium text-[var(--color-muted)]">Display name</dt>
              <dd className="wrap-anywhere">{asset.display_name}</dd>
            </div>
          </>
        )}

        <Disclosure summary="Technical IDs">
          <div className="space-y-1 text-xs text-[var(--color-muted)]">
            <p className="wrap-anywhere font-mono">
              <span className="font-sans font-medium">node_id: </span>
              {node.id}
            </p>
            {node.document_id && (
              <p className="wrap-anywhere font-mono">
                <span className="font-sans font-medium">document_id: </span>
                {node.document_id}
              </p>
            )}
            {node.chunk_id && (
              <p className="wrap-anywhere font-mono">
                <span className="font-sans font-medium">chunk_id: </span>
                {node.chunk_id}
              </p>
            )}
            {node.entity_id && (
              <p className="wrap-anywhere font-mono">
                <span className="font-sans font-medium">entity_id: </span>
                {node.entity_id}
              </p>
            )}
          </div>
        </Disclosure>
      </dl>
    </div>
  );
}

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const tag = decodeURIComponent(params.id);

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

  /* Graph interaction state */
  const [graphIncludeChunks, setGraphIncludeChunks] = useState(true);
  const [graphRelationType, setGraphRelationType] = useState("");
  const [selectedNode, setSelectedNode] = useState<ApiAssetGraphNode | null>(null);

  /* Progressive-disclosure caps in the Intelligence tab */
  const [showAllEvents, setShowAllEvents] = useState(false);
  const [showAllMentions, setShowAllMentions] = useState(false);

  /* Deep link: resolve ?tab= (with legacy aliases). ?tab=ask navigates to
     the Ask Copilot action, which is now a header action. */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const param = new URLSearchParams(window.location.search).get("tab");
    if (!param) return;
    if (param === "ask") {
      router.replace(`/copilot?asset=${encodeURIComponent(tag)}`);
      return;
    }
    const resolved = TAB_ALIASES[param];
    if (resolved) setTab(resolved);
  }, [router, tag]);

  /* Keep the ?tab= param in sync without a full navigation, so links remain
     shareable and consistent with the guided-tour deep links. */
  function selectTab(key: TabKey) {
    setTab(key);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("tab", key);
      window.history.replaceState(null, "", url.toString());
    }
  }

  /* Refetch graph on filter change (data-fetching behaviour unchanged). */
  useEffect(() => {
    if (loading) return;
    getAssetGraph(tag, graphIncludeChunks, graphRelationType || undefined)
      .then((newGraph) => {
        setGraph(newGraph);
        setSelectedNode((prev) => (prev && newGraph.nodes.some((n) => n.id === prev.id) ? prev : null));
      })
      .catch((err) => console.error("Error updating graph:", err));
  }, [tag, graphIncludeChunks, graphRelationType, loading]);

  /* Fetch everything in parallel. */
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
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

  /* Newest-first timeline (nulls last). */
  const sortedTimeline = useMemo(() => {
    return [...(timeline ?? [])].sort((a, b) => {
      if (!a.date && !b.date) return 0;
      if (!a.date) return 1;
      if (!b.date) return -1;
      return a.date < b.date ? 1 : a.date > b.date ? -1 : 0;
    });
  }, [timeline]);

  const latestActivity = useMemo(() => {
    const dates = (timeline ?? []).map((e) => e.date).filter(Boolean) as string[];
    return dates.length ? dates.reduce((a, b) => (a > b ? a : b)) : null;
  }, [timeline]);

  /* Per-mode aggregation for "Recurring failure modes". */
  const modeRows = useMemo(() => {
    if (!failure) return [];
    return failure.failure_modes
      .map((m) => {
        const events = failure.recent_failure_events.filter((e) => e.failure_modes.includes(m.mode));
        const dates = events.map((e) => e.date).filter(Boolean) as string[];
        return {
          mode: m.mode,
          count: m.count,
          events,
          latest: dates.length ? dates.reduce((a, b) => (a > b ? a : b)) : null,
          repeated: failure.repeated_failure_modes.includes(m.mode),
        };
      })
      .sort((a, b) => b.count - a.count);
  }, [failure]);

  const entityGroups = useMemo(() => {
    const groups: Record<string, string[]> = {};
    for (const e of facts?.entities ?? []) {
      const val = e.normalized_value || e.raw_value;
      if (!val) continue;
      (groups[e.entity_type] ??= []).push(val);
    }
    for (const key of Object.keys(groups)) groups[key] = Array.from(new Set(groups[key]));
    return groups;
  }, [facts]);

  const backLink = (
    <Link href="/assets" className="inline-flex items-center gap-1 text-sm text-[var(--color-accent)] hover:underline">
      <ArrowRightIcon className="h-4 w-4 rotate-180" />
      Back to assets
    </Link>
  );

  if (error) {
    return (
      <div>
        <div className="mb-6">{backLink}</div>
        <Card>
          <ErrorState title="Backend Connection Error" detail={error} onRetry={() => router.refresh()} />
        </Card>
      </div>
    );
  }

  if (loading || !asset) {
    return (
      <div>
        <div className="mb-6">{backLink}</div>
        <Card>
          <LoadingState label="Loading asset…" />
        </Card>
      </div>
    );
  }

  const status = failureStatus(failure);

  return (
    <div>
      {/* ── Asset header ─────────────────────────────────────────── */}
      <div className="mb-6">
        {backLink}
        <div className="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="wrap-anywhere text-2xl font-semibold tracking-tight">{asset.tag}</h1>
              <Badge tone={LEVEL_BADGE[status.level]}>{status.label}</Badge>
            </div>
            <p className="mt-1 wrap-anywhere text-sm capitalize text-[var(--color-muted)]">
              {prettyType(asset.asset_type)} · {asset.display_name}
            </p>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              {documents?.length ?? 0} documents · {mentions?.count ?? 0} mentions
              {latestActivity && <> · latest activity {timeAgo(latestActivity)}</>}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <HeaderAction href={`/copilot?asset=${encodeURIComponent(asset.tag)}`} icon={<ChatIcon className="h-4 w-4" />} variant="primary">
              Ask Copilot
            </HeaderAction>
            <HeaderAction href={`/rca?asset=${encodeURIComponent(asset.tag)}`} icon={<SearchIcon className="h-4 w-4" />} variant="secondary">
              Generate RCA
            </HeaderAction>
            <HeaderAction href={`/compliance?asset=${encodeURIComponent(asset.tag)}`} icon={<ShieldIcon className="h-4 w-4" />} variant="ghost">
              Compliance
            </HeaderAction>
            <HeaderAction
              href={`/compliance?asset=${encodeURIComponent(asset.tag)}&action=generate`}
              icon={<CubeIcon className="h-4 w-4" />}
              variant="ghost"
            >
              Evidence package
            </HeaderAction>
          </div>
        </div>
      </div>

      <Tabs tabs={TABS} active={tab} onChange={(k) => selectTab(k as TabKey)} label="Asset sections" />

      {/* ── Overview ─────────────────────────────────────────────── */}
      {tab === "overview" && (
        <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" tabIndex={0} className="space-y-6 outline-none">
          {/* Status strip */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric
              label="Failure events"
              value={failure ? failure.failure_event_count : "—"}
              emphasis="primary"
              tone={failure && !failure.insufficient_data ? status.level : "neutral"}
              icon={<AlertIcon className="h-4 w-4" />}
              hint={failure && failure.distinct_failure_modes > 0 ? `${failure.distinct_failure_modes} distinct modes` : undefined}
            />
            <Metric label="Documents" value={documents?.length ?? 0} icon={<DocumentIcon className="h-4 w-4" />} />
            <Metric label="Mentions" value={mentions?.count ?? 0} icon={<ChatIcon className="h-4 w-4" />} />
            <Metric label="Latest activity" value={latestActivity ? timeAgo(latestActivity) : "—"} icon={<ClockIcon className="h-4 w-4" />} />
          </div>

          {/* Current concerns */}
          <Card>
            <SectionTitle
              title="Current concerns"
              subtitle="Recurring failure modes drawn from documented evidence"
              action={
                <button onClick={() => selectTab("intelligence")} className="text-sm text-[var(--color-accent)] hover:underline">
                  View intelligence
                </button>
              }
            />
            {modeRows.length === 0 || !failure || failure.insufficient_data ? (
              <p className="py-2 text-sm text-[var(--color-muted)]">
                No documented failure concerns for {asset.tag} yet.
              </p>
            ) : (
              <ul className="space-y-2">
                {modeRows.slice(0, 3).map((row) => (
                  <li
                    key={row.mode}
                    className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5"
                  >
                    <span className="flex min-w-0 items-center gap-2">
                      {row.repeated && <RepeatIcon className="h-4 w-4 shrink-0 text-amber-700" />}
                      <span className="truncate text-sm font-medium capitalize">{row.mode.replace(/_/g, " ")}</span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2 text-xs text-[var(--color-muted)]">
                      <span>{row.count} occurrences</span>
                      {row.repeated && <Badge tone="bad">recurring</Badge>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Recent activity */}
          <Card>
            <SectionTitle
              title="Recent activity"
              subtitle={`${sortedTimeline.length} timeline event(s)`}
              action={
                sortedTimeline.length > 0 ? (
                  <button onClick={() => selectTab("timeline")} className="text-sm text-[var(--color-accent)] hover:underline">
                    View timeline
                  </button>
                ) : undefined
              }
            />
            {sortedTimeline.length === 0 ? (
              <p className="py-2 text-sm text-[var(--color-muted)]">No timeline events recorded yet.</p>
            ) : (
              <ul className="space-y-2">
                {sortedTimeline.slice(0, 4).map((e) => (
                  <li
                    key={e.id}
                    className="flex items-start justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{e.title}</p>
                      <p className="mt-0.5 text-xs text-[var(--color-muted)]">{formatDate(e.date)}</p>
                    </div>
                    <Badge tone={eventTypeTone(e.event_type)}>{e.event_type.replace(/_/g, " ")}</Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Evidence summary */}
          <Card>
            <SectionTitle
              title="Evidence coverage"
              subtitle="Citation-backed sources linked to this asset"
              action={
                <button onClick={() => selectTab("documents")} className="text-sm text-[var(--color-accent)] hover:underline">
                  View documents
                </button>
              }
            />
            <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Documents</dt>
                <dd className="mt-0.5 font-medium">{documents?.length ?? 0}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Mentions</dt>
                <dd className="mt-0.5 font-medium">{mentions?.count ?? 0}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Entities</dt>
                <dd className="mt-0.5 font-medium">{facts?.entities.length ?? 0}</dd>
              </div>
              <div>
                <dt className="text-xs text-[var(--color-muted)]">Coverage</dt>
                <dd className="mt-0.5 font-medium capitalize">{failure?.coverage_confidence ?? "—"}</dd>
              </div>
            </dl>
          </Card>
        </div>
      )}

      {/* ── Timeline ─────────────────────────────────────────────── */}
      {tab === "timeline" && (
        <div id="panel-timeline" role="tabpanel" aria-labelledby="tab-timeline" tabIndex={0} className="outline-none">
          <Card>
            <SectionTitle title="Timeline" subtitle={`${sortedTimeline.length} event(s), newest first`} />
            {sortedTimeline.length === 0 ? (
              <EmptyState
                title="No timeline events yet"
                description={`Upload work orders, inspection reports or maintenance records mentioning ${asset.tag} to populate this timeline.`}
              />
            ) : (
              <div className="space-y-3">
                {sortedTimeline.map((e) => (
                  <div key={e.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <time className="font-medium text-[var(--color-fg)]">{formatDate(e.date)}</time>
                      <Badge tone={eventTypeTone(e.event_type)}>{e.event_type.replace(/_/g, " ")}</Badge>
                      <span className="ml-auto">
                        <Badge tone={severityTone(e.severity)}>{e.severity}</Badge>
                      </span>
                    </div>
                    <p className="mt-2 text-sm font-medium">{e.title}</p>
                    <div className="mt-2">
                      <CitationSource filename={e.filename} documentId={e.document_id} chunkIndex={e.chunk_index} />
                    </div>
                    {(e.text_preview || e.chunk_id || e.reason_tags.length > 0) && (
                      <div className="mt-2">
                        <Disclosure summary="Show evidence">
                          {e.text_preview && (
                            <p className="wrap-anywhere rounded-md bg-[var(--color-surface-2)] px-3 py-2 text-xs leading-relaxed text-[var(--color-muted)]">
                              &ldquo;{e.text_preview}&rdquo;
                            </p>
                          )}
                          {e.reason_tags.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {e.reason_tags.map((t) => (
                                <Badge key={t}>{t}</Badge>
                              ))}
                            </div>
                          )}
                          {e.chunk_id && (
                            <p className="mt-2 wrap-anywhere font-mono text-xs text-[var(--color-muted)]">
                              chunk {e.chunk_index ?? "?"} · {e.chunk_id}
                            </p>
                          )}
                        </Disclosure>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Documents ────────────────────────────────────────────── */}
      {tab === "documents" && (
        <div id="panel-documents" role="tabpanel" aria-labelledby="tab-documents" tabIndex={0} className="outline-none">
          <Card>
            <SectionTitle title="Related documents" subtitle={`${documents?.length ?? 0} document(s) mention ${asset.tag}`} />
            {!documents || documents.length === 0 ? (
              <EmptyState title="No related documents" description={`No documents currently mention ${asset.tag}.`} />
            ) : (
              <>
                <TableScrollRegion label={`Documents mentioning ${asset.tag}`} className="hidden md:block">
                  <table className="w-full text-sm">
                    <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                      <tr>
                        <th className="px-4 py-2 font-medium">Document</th>
                        <th className="px-4 py-2 font-medium">Type</th>
                        <th className="px-4 py-2 font-medium">Chunks</th>
                        <th className="px-4 py-2 font-medium">Added</th>
                        <th className="px-4 py-2 font-medium">
                          <span className="sr-only">Action</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((d) => (
                        <tr key={d.id} className="border-t border-[var(--color-border)]">
                          <td className="max-w-[20rem] truncate px-4 py-2.5" title={d.filename}>
                            <Link href={`/documents/${d.id}`} className="hover:underline">
                              {d.filename}
                            </Link>
                          </td>
                          <td className="px-4 py-2.5 text-[var(--color-muted)]">{d.content_type?.split("/").pop() ?? "—"}</td>
                          <td className="px-4 py-2.5 text-[var(--color-muted)]">{d.chunk_count}</td>
                          <td className="px-4 py-2.5 text-[var(--color-muted)]">{timeAgo(d.created_at)}</td>
                          <td className="px-4 py-2.5 text-right">
                            <Link href={`/documents/${d.id}`} className="inline-flex items-center gap-1 text-[var(--color-accent)] hover:underline">
                              View
                              <ArrowRightIcon className="h-3.5 w-3.5" />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableScrollRegion>

                <div className="space-y-3 md:hidden">
                  {documents.map((d) => (
                    <MobileDataCard key={d.id} href={`/documents/${d.id}`}>
                      <p className="truncate font-medium text-[var(--color-accent)]" title={d.filename}>
                        {d.filename}
                      </p>
                      <DataRow label="Type">{d.content_type?.split("/").pop() ?? "—"}</DataRow>
                      <DataRow label="Chunks">{d.chunk_count}</DataRow>
                      <DataRow label="Added">{timeAgo(d.created_at)}</DataRow>
                    </MobileDataCard>
                  ))}
                </div>
              </>
            )}
          </Card>
        </div>
      )}

      {/* ── Intelligence (Failure + Facts + Mentions) ────────────── */}
      {tab === "intelligence" && (
        <div id="panel-intelligence" role="tabpanel" aria-labelledby="tab-intelligence" tabIndex={0} className="space-y-6 outline-none">
          {/* 1. Failure summary */}
          {failure && !failure.insufficient_data ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Metric label="Failure events" value={failure.failure_event_count} emphasis="primary" tone={status.level} icon={<AlertIcon className="h-4 w-4" />} />
              <Metric label="Distinct modes" value={failure.distinct_failure_modes} icon={<RepeatIcon className="h-4 w-4" />} />
              <Metric label="Source documents" value={failure.document_count} icon={<DocumentIcon className="h-4 w-4" />} />
              <Metric label="Coverage" value={<span className="capitalize">{failure.coverage_confidence}</span>} />
            </div>
          ) : (
            <Card>
              <EmptyState
                title="No documented failure evidence"
                description={`Upload work orders, RCA findings or inspection reports mentioning ${asset.tag} to build its failure history.`}
              />
            </Card>
          )}

          {/* 2. Recurring failure modes */}
          {modeRows.length > 0 && (
            <Card>
              <SectionTitle title="Recurring failure modes" subtitle="Ranked by documented occurrences" />
              <ul className="space-y-2">
                {modeRows.map((row) => (
                  <li key={row.mode} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="truncate text-sm font-medium capitalize">{row.mode.replace(/_/g, " ")}</span>
                        {row.repeated && <Badge tone="bad">recurring</Badge>}
                      </span>
                      <span className="flex shrink-0 items-center gap-3 text-xs text-[var(--color-muted)]">
                        <span>{row.count} occurrences</span>
                        {row.latest && <span>latest {formatDate(row.latest)}</span>}
                      </span>
                    </div>
                    {row.events.length > 0 && (
                      <div className="mt-2">
                        <Disclosure summary={`Evidence (${row.events.length})`}>
                          <ul className="space-y-2">
                            {row.events.map((ev, i) => (
                              <li key={`${row.mode}-${i}`} className="rounded-md bg-[var(--color-surface-2)] p-2.5">
                                {ev.text_preview && (
                                  <p className="wrap-anywhere text-xs leading-relaxed text-[var(--color-muted)]">&ldquo;{ev.text_preview}&rdquo;</p>
                                )}
                                <div className="mt-1">
                                  <CitationSource filename={ev.filename} documentId={ev.citation.document_id} chunkIndex={ev.citation.chunk_index} />
                                </div>
                              </li>
                            ))}
                          </ul>
                        </Disclosure>
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {/* 3. Recent failure events — capped with progressive disclosure */}
          {failure && failure.recent_failure_events.length > 0 && (
            <Card>
              <SectionTitle
                title="Recent failure events"
                subtitle={`Showing ${showAllEvents ? failure.recent_failure_events.length : Math.min(5, failure.recent_failure_events.length)} of ${failure.recent_failure_events.length}`}
              />
              <div className="space-y-3">
                {(showAllEvents ? failure.recent_failure_events : failure.recent_failure_events.slice(0, 5)).map((e, i) => (
                  <FailureEventItem key={`${e.citation.chunk_id ?? "x"}-${i}`} event={e} />
                ))}
              </div>
              {failure.recent_failure_events.length > 5 && (
                <button
                  onClick={() => setShowAllEvents((v) => !v)}
                  className="mt-3 inline-flex min-h-[40px] items-center rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm font-medium transition hover:border-[var(--color-accent)]"
                >
                  {showAllEvents ? "Show fewer" : `Show all ${failure.recent_failure_events.length} events`}
                </button>
              )}
              {failure.disclaimer && (
                <p className="mt-4 border-t border-[var(--color-border)] pt-3 text-xs italic text-[var(--color-muted)]">{failure.disclaimer}</p>
              )}
            </Card>
          )}

          {/* 4. Facts & entities */}
          {facts && facts.entities.length > 0 && (
            <Card>
              <SectionTitle title="Facts & entities" subtitle={`${facts.entities.length} entity(ies) across ${Object.keys(entityGroups).length} categories`} />
              <div className="space-y-4">
                {Object.entries(entityGroups).map(([type, values]) => (
                  <div key={type}>
                    <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--color-muted)]">{type.replace(/_/g, " ")}</p>
                    <div className="flex flex-wrap gap-2">
                      {values.map((v) => (
                        <span key={v} className="wrap-anywhere rounded-md border border-[var(--color-border)] bg-[var(--color-base)] px-2.5 py-1 text-xs">
                          {v}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <Disclosure summary="Inspect entities (values, confidence, method)">
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
                            <td className="px-4 py-2.5">
                              <Badge>{e.entity_type}</Badge>
                            </td>
                            <td className="wrap-anywhere px-4 py-2.5">{e.raw_value}</td>
                            <td className="wrap-anywhere px-4 py-2.5 font-medium">{e.normalized_value}</td>
                            <td className="px-4 py-2.5 text-[var(--color-muted)]">{e.confidence !== null ? e.confidence.toFixed(2) : "—"}</td>
                            <td className="px-4 py-2.5 text-xs text-[var(--color-muted)]">{e.extraction_method ?? "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </TableScrollRegion>
                  <div className="space-y-3 md:hidden">
                    {facts.entities.map((e) => (
                      <MobileDataCard key={e.id}>
                        <div className="flex items-center justify-between gap-2">
                          <Badge>{e.entity_type}</Badge>
                          <span className="text-xs text-[var(--color-muted)]">{e.confidence !== null ? `conf ${e.confidence.toFixed(2)}` : "—"}</span>
                        </div>
                        <DataRow label="Value">{e.raw_value}</DataRow>
                        <DataRow label="Normalized">{e.normalized_value}</DataRow>
                        <DataRow label="Method">{e.extraction_method ?? "—"}</DataRow>
                      </MobileDataCard>
                    ))}
                  </div>
                </Disclosure>
              </div>
            </Card>
          )}

          {/* 5. Evidence mentions (secondary) */}
          {mentions && mentions.mentions.length > 0 && (
            <Card>
              <SectionTitle
                title="Evidence mentions"
                subtitle={`Showing ${showAllMentions ? mentions.mentions.length : Math.min(5, mentions.mentions.length)} of ${mentions.count}`}
              />
              <ul className="space-y-3">
                {(showAllMentions ? mentions.mentions : mentions.mentions.slice(0, 5)).map((m, i) => (
                  <MentionItem key={m.id} mention={m} index={i} />
                ))}
              </ul>
              {mentions.mentions.length > 5 && (
                <button
                  onClick={() => setShowAllMentions((v) => !v)}
                  className="mt-3 inline-flex min-h-[40px] items-center rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm font-medium transition hover:border-[var(--color-accent)]"
                >
                  {showAllMentions ? "Show fewer" : `Show all ${mentions.mentions.length} mentions`}
                </button>
              )}
            </Card>
          )}

          {/* Overall empty fallback */}
          {(!failure || failure.insufficient_data) &&
            modeRows.length === 0 &&
            (!facts || facts.entities.length === 0) &&
            (!mentions || mentions.mentions.length === 0) && (
              <Card>
                <EmptyState title="No intelligence available yet" description={`No failure, fact or mention evidence has been extracted for ${asset.tag}.`} />
              </Card>
            )}
        </div>
      )}

      {/* ── Graph ────────────────────────────────────────────────── */}
      {tab === "graph" && (
        <div id="panel-graph" role="tabpanel" aria-labelledby="tab-graph" tabIndex={0} className="outline-none">
          {!graph ? (
            <Card>
              <LoadingState label="Loading graph…" />
            </Card>
          ) : (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className="min-w-0 lg:col-span-2">
                <AssetGraph
                  nodes={graph.nodes}
                  edges={graph.edges}
                  counts={graph.counts}
                  assetTag={asset.tag}
                  includeChunks={graphIncludeChunks}
                  onIncludeChunks={setGraphIncludeChunks}
                  relationType={graphRelationType}
                  onRelationType={setGraphRelationType}
                  selectedId={selectedNode?.id ?? null}
                  onSelect={setSelectedNode}
                />
              </div>
              <Card className="flex flex-col">
                <SectionTitle title="Node inspector" subtitle="Metadata & source links" />
                <NodeInspector node={selectedNode} asset={asset} mentions={mentions} timeline={timeline} facts={facts} />
              </Card>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
