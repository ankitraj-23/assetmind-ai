"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Card,
  PageHeader,
  RiskBadge,
  SectionTitle,
  Metric,
  ErrorState,
  EmptyState,
} from "@/components/ui";
import {
  AlertIcon,
  ArrowRightIcon,
  ChevronDownIcon,
  CloseIcon,
  CompassIcon,
  CubeIcon,
  DocumentIcon,
  RepeatIcon,
} from "@/components/icons";
import type { ApiDashboardSummary } from "@/lib/api";
import { getDashboardSummary } from "@/lib/api";
import type { Risk } from "@/lib/mock-data";

/* Guided-tour destinations. These preserve the original guided-flow deep
   links; only the presentation is restrained (no "STEP 0X" theatrics). */
const tourSteps: { href: string; label: string }[] = [
  { href: "/assets/P-101", label: "Open the P-101 asset page" },
  { href: "/assets/P-101?tab=timeline", label: "Review the maintenance timeline" },
  { href: "/assets/P-101?tab=graph", label: "Explore the knowledge graph" },
  { href: "/copilot?asset=P-101", label: "Ask the Copilot about P-101" },
  { href: "/rca?asset=P-101", label: "Generate a root-cause analysis" },
  { href: "/compliance?asset=P-101", label: "Check open compliance gaps" },
  { href: "/compliance?asset=P-101&action=generate", label: "Build an evidence package" },
  { href: "/evaluation", label: "View benchmark scores" },
];

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return days === 1 ? "Yesterday" : `${days}d ago`;
}

function typeLabel(ct: string): string {
  if (ct.includes("pdf")) return "PDF";
  if (ct.includes("csv")) return "CSV";
  if (ct.includes("spreadsheet") || ct.includes("xlsx")) return "XLSX";
  if (ct.includes("text")) return "TXT";
  return ct;
}

function prettyType(t?: string | null): string {
  return t ? t.replace(/_/g, " ") : "asset";
}

export default function DashboardPage() {
  const [data, setData] = useState<ApiDashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tourOpen, setTourOpen] = useState(false);

  function load() {
    setLoading(true);
    setError(null);
    getDashboardSummary()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  const header = (
    <PageHeader
      title="Operations Dashboard"
      subtitle="What needs attention across your assets, and where to act next."
      action={
        <button
          type="button"
          onClick={() => setTourOpen((o) => !o)}
          aria-expanded={tourOpen}
          className="inline-flex h-10 items-center gap-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm text-[var(--color-muted)] outline-none transition hover:border-[var(--color-accent)] hover:text-[var(--color-fg)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
        >
          <CompassIcon className="h-4 w-4" />
          Guided tour
          <ChevronDownIcon className={`h-4 w-4 transition ${tourOpen ? "rotate-180" : ""}`} />
        </button>
      }
    />
  );

  /* ── Loading state ───────────────────────────────────────────────── */
  if (loading) {
    return (
      <div>
        {header}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
            >
              <div className="h-3 w-20 animate-pulse rounded bg-[var(--color-surface-2)]" />
              <div className="mt-3 h-7 w-14 animate-pulse rounded bg-[var(--color-surface-2)]" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  /* ── Error state — clear backend connection error ────────────────── */
  if (error) {
    return (
      <div>
        {header}
        <Card>
          <ErrorState
            title="Backend Connection Error"
            description="Could not load dashboard data from the backend API. Make sure the FastAPI backend is reachable from the configured API base URL."
            detail={error}
            onRetry={load}
          />
        </Card>
      </div>
    );
  }

  if (!data) return null;

  const needsAttention = data.risk_summary.slice(0, 6);
  const recent = data.recent_documents.slice(0, 5);
  const topAssets = data.top_assets_by_mentions.slice(0, 5);

  return (
    <div>
      {header}

      {/* ── Guided tour (optional, collapsed by default) ─────────────── */}
      {tourOpen && (
        <Card className="mb-6">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold">Guided tour</h2>
              <p className="mt-0.5 text-xs text-[var(--color-muted)]">
                Walk the P-101 reliability scenario end to end.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setTourOpen(false)}
              aria-label="Close guided tour"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[var(--color-border)] text-[var(--color-muted)] outline-none transition hover:border-[var(--color-accent)] hover:text-[var(--color-fg)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            >
              <CloseIcon className="h-4 w-4" />
            </button>
          </div>
          <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {tourSteps.map((step, i) => (
              <li key={step.href}>
                <Link
                  href={step.href}
                  className="group flex items-center gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5 outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[var(--color-border)] font-mono text-xs text-[var(--color-muted)]">
                    {i + 1}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm">{step.label}</span>
                  <ArrowRightIcon className="h-4 w-4 shrink-0 text-[var(--color-muted)] transition group-hover:text-[var(--color-accent)]" />
                </Link>
              </li>
            ))}
          </ol>
        </Card>
      )}

      {/* ── Priority metric row ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Metric
          emphasis="primary"
          tone={data.high_risk_assets > 0 ? "critical" : "positive"}
          icon={<AlertIcon className="h-4 w-4" />}
          label="High-Risk Assets"
          value={data.high_risk_assets}
          hint="need attention"
          href="/assets"
        />
        <Metric
          emphasis="primary"
          tone={data.open_compliance_gaps > 0 ? "warning" : "positive"}
          icon={<AlertIcon className="h-4 w-4" />}
          label="Compliance Gaps"
          value={data.open_compliance_gaps}
          hint="open findings"
          href="/compliance"
        />
        <Metric
          icon={<RepeatIcon className="h-4 w-4" />}
          label="Failure Patterns"
          value={data.repeated_failure_patterns}
          hint="recurring"
        />
        <Metric
          icon={<DocumentIcon className="h-4 w-4" />}
          label="Documents"
          value={data.documents_indexed}
          hint="indexed"
        />
        <Metric
          icon={<CubeIcon className="h-4 w-4" />}
          label="Assets"
          value={data.assets_discovered}
          hint="discovered"
        />
      </div>

      {/* ── Needs Attention (primary section) ────────────────────────── */}
      <section className="mt-6">
        <Card>
          <SectionTitle
            title="Needs Attention"
            subtitle="Highest-risk assets ranked by evidence and severity"
            action={
              <Link href="/assets" className="text-sm text-[var(--color-accent)] hover:underline">
                View all
              </Link>
            }
          />
          {needsAttention.length === 0 ? (
            <EmptyState
              title="Nothing needs attention"
              description="No high-risk assets have been identified yet. Ingest documents to populate risk signals."
            />
          ) : (
            <ul className="space-y-2.5">
              {needsAttention.map((a) => (
                <li key={a.asset_tag}>
                  <Link
                    href={`/assets/${a.asset_tag}`}
                    className="flex items-start gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-3 outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-mono text-sm font-semibold">{a.asset_tag}</span>
                        <span className="truncate text-xs text-[var(--color-muted)]">
                          {prettyType(a.asset.asset_type)}
                        </span>
                      </div>
                      <p className="mt-1 wrap-anywhere text-xs text-[var(--color-muted)]">
                        {a.risk_reasons[0] ?? "Risk signal detected"}
                      </p>
                      <p className="mt-1 text-xs text-[var(--color-muted)]">
                        {a.mention_count} mentions · {a.document_count} documents
                      </p>
                    </div>
                    <RiskBadge risk={a.risk_level as Risk} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      {/* ── Secondary sections ───────────────────────────────────────── */}
      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent activity — compact list */}
        <Card>
          <SectionTitle
            title="Recent Activity"
            action={
              <Link href="/documents" className="text-sm text-[var(--color-accent)] hover:underline">
                View all
              </Link>
            }
          />
          {recent.length === 0 ? (
            <EmptyState
              title="No recent uploads"
              description="Ingested documents will appear here."
            />
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {recent.map((d) => {
                const indexed = d.status === "processed" || d.status === "extracted";
                return (
                  <li key={d.id} className="flex items-center gap-3 py-2.5">
                    <DocumentIcon className="h-4 w-4 shrink-0 text-[var(--color-muted)]" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm" title={d.filename}>
                        {d.filename}
                      </p>
                      <p className="text-xs text-[var(--color-muted)]">
                        {typeLabel(d.content_type)} · {timeAgo(d.created_at)}
                      </p>
                    </div>
                    <span
                      className={`shrink-0 text-xs ${indexed ? "text-emerald-300" : "text-amber-300"}`}
                    >
                      {indexed ? "Indexed" : d.status}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* Top assets by mentions — demoted */}
        <Card>
          <SectionTitle
            title="Most Referenced"
            subtitle="Frequently mentioned equipment"
            action={
              <Link href="/assets" className="text-sm text-[var(--color-accent)] hover:underline">
                View all
              </Link>
            }
          />
          {topAssets.length === 0 ? (
            <EmptyState title="No mentions yet" description="Asset references will appear here." />
          ) : (
            <ul className="divide-y divide-[var(--color-border)]">
              {topAssets.map((a) => (
                <li key={a.asset_tag}>
                  <Link
                    href={`/assets/${a.asset_tag}`}
                    className="flex items-center justify-between gap-3 rounded-md py-2.5 outline-none transition hover:text-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
                  >
                    <div className="min-w-0">
                      <span className="font-mono text-sm font-medium">{a.asset_tag}</span>
                      <span className="ml-2 truncate text-xs text-[var(--color-muted)]">
                        {prettyType(a.asset_type)}
                      </span>
                    </div>
                    <span className="shrink-0 text-xs text-[var(--color-muted)]">
                      {a.mention_count} mentions
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
