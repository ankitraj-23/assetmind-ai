"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, RiskBadge, SectionTitle, StatCard } from "@/components/ui";
import type { ApiDashboardSummary } from "@/lib/api";
import { getDashboardSummary } from "@/lib/api";
import type { Risk } from "@/lib/mock-data";

export default function DashboardPage() {
  const [data, setData] = useState<ApiDashboardSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDashboardSummary()
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, []);

  /* ── Loading state ───────────────────────────────────────────────── */
  if (loading) {
    return (
      <div>
        <PageHeader
          title="Operations Dashboard"
          subtitle="Unified view of indexed knowledge, asset health, and compliance posture."
        />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i}>
              <div className="h-4 w-24 animate-pulse rounded bg-[var(--color-surface-2)]" />
              <div className="mt-3 h-8 w-16 animate-pulse rounded bg-[var(--color-surface-2)]" />
              <div className="mt-2 h-3 w-32 animate-pulse rounded bg-[var(--color-surface-2)]" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  /* ── Error state — clear backend connection error ────────────────── */
  if (error) {
    return (
      <div>
        <PageHeader
          title="Operations Dashboard"
          subtitle="Unified view of indexed knowledge, asset health, and compliance posture."
        />
        <Card>
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <div className="rounded-full bg-red-500/10 p-3">
              <svg className="h-6 w-6 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-red-400">Backend Connection Error</p>
            <p className="max-w-md text-sm text-[var(--color-muted)]">
              Could not load dashboard data from the backend API. Make sure the
              FastAPI backend is reachable from the configured API base URL.
            </p>
            <p className="text-xs text-[var(--color-muted)]">{error}</p>
            <button
              onClick={() => { setLoading(true); setError(null); getDashboardSummary().then(setData).catch((e) => setError(e instanceof Error ? e.message : String(e))).finally(() => setLoading(false)); }}
              className="mt-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-2 text-sm transition hover:border-[var(--color-accent)]"
            >
              Retry
            </button>
          </div>
        </Card>
      </div>
    );
  }

  /* ── Empty / no data fallback ────────────────────────────────────── */
  if (!data) return null;

  /* ── Stat cards ──────────────────────────────────────────────────── */
  const stats = [
    { label: "Documents Indexed", value: data.documents_indexed, hint: "ingested files" },
    { label: "Chunks Generated", value: data.chunks_created.toLocaleString(), hint: "semantic segments" },
    { label: "Assets Discovered", value: data.assets_discovered, hint: "equipment tags" },
    { label: "Knowledge Edges", value: data.knowledge_edges.toLocaleString(), hint: "graph relations" },
    { label: "High-Risk Assets", value: data.high_risk_assets, hint: "need attention" },
    { label: "Open Compliance Gaps", value: data.open_compliance_gaps, hint: "open findings" },
    { label: "Asset Mentions", value: data.asset_mentions.toLocaleString(), hint: "evidence links" },
    { label: "Failure Patterns", value: data.repeated_failure_patterns, hint: "recurring issues" },
  ];

  /* ── Helper: time ago ────────────────────────────────────────────── */
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

  /* ── Helper: content type label ──────────────────────────────────── */
  function typeLabel(ct: string): string {
    if (ct.includes("pdf")) return "PDF";
    if (ct.includes("csv")) return "CSV";
    if (ct.includes("spreadsheet") || ct.includes("xlsx")) return "XLSX";
    if (ct.includes("text")) return "TXT";
    return ct;
  }

  return (
    <div>
      <PageHeader
        title="Operations Dashboard"
        subtitle="Unified view of indexed knowledge, asset health, and compliance posture."
      />

      {/* 🎬 Judge's Guided Demo Flow: Repeated P-101 Vibration */}
      <Card className="mb-6 border-[var(--color-accent)]/30 bg-[var(--color-surface-2)]/40 backdrop-blur-md shadow-[0_0_20px_rgba(45,212,191,0.08)]">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--color-border)] pb-3.5 mb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="animate-pulse flex h-2 w-2 rounded-full bg-[var(--color-accent)]" />
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent)]">
                Interactive Guided Flow
              </span>
            </div>
            <h3 className="text-base font-bold text-slate-100 mt-0.5">
              Demo Scenario: Repeated P-101 Vibration
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed mt-0.5">
              Follow this step-by-step story sequence to evaluate asset reliability, timeline evidence, compliance audits, and AI reasoning.
            </p>
          </div>
        </div>

        {/* Steps Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Step 1 */}
          <Link href="/assets/P-101" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent)] font-mono">STEP 01</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">Open P-101 Asset Page</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Inspect the physical specifications, properties, and health state.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent)] mt-3 block font-semibold group-hover:underline">
                Go to Asset Page →
              </span>
            </div>
          </Link>

          {/* Step 2 */}
          <Link href="/assets/P-101?tab=timeline" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent)] font-mono">STEP 02</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">View Recent Timeline</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Analyze chronological maintenance logs and seal replacement timestamps.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent)] mt-3 block font-semibold group-hover:underline">
                View Timeline →
              </span>
            </div>
          </Link>

          {/* Step 3 */}
          <Link href="/assets/P-101?tab=graph" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent)] font-mono">STEP 03</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">View Knowledge Graph</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Explore entity linkages between P-101 and industrial manuals.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent)] mt-3 block font-semibold group-hover:underline">
                View Graph →
              </span>
            </div>
          </Link>

          {/* Step 4 */}
          <Link href="/copilot?asset=P-101" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent)] font-mono">STEP 04</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">Ask AI Copilot</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Query the RAG chat scope locked to P-101 context references.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent)] mt-3 block font-semibold group-hover:underline">
                Open Copilot →
              </span>
            </div>
          </Link>

          {/* Step 5 */}
          <Link href="/rca?asset=P-101" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent-2)] font-mono">STEP 05</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">Generate RCA</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Trigger live RCA to pinpoint mechanical seal leakage and misalignment.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent-2)] mt-3 block font-semibold group-hover:underline">
                Run RCA Diagnostic →
              </span>
            </div>
          </Link>

          {/* Step 6 */}
          <Link href="/compliance?asset=P-101" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent-2)] font-mono">STEP 06</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">Check Compliance Gaps</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Audit open gaps showing OISD-137 vibration limit exceedance.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent-2)] mt-3 block font-semibold group-hover:underline">
                Check Compliance →
              </span>
            </div>
          </Link>

          {/* Step 7 */}
          <Link href="/compliance?asset=P-101&action=generate" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent-2)] font-mono">STEP 07</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">Generate Evidence Package</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Compile a citation-backed audit package and download the Markdown report.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent-2)] mt-3 block font-semibold group-hover:underline">
                Compile & Download Report →
              </span>
            </div>
          </Link>

          {/* Step 8 */}
          <Link href="/evaluation" className="group">
            <div className="h-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50 p-3 hover:border-[var(--color-accent)] transition flex flex-col justify-between">
              <div>
                <span className="text-xs font-bold text-[var(--color-accent-2)] font-mono">STEP 08</span>
                <h4 className="text-xs font-semibold text-slate-200 mt-1">View Evaluation Score</h4>
                <p className="text-[10px] text-slate-400 mt-1 leading-normal">
                  Review benchmark accuracy, retrieval confidence, and graph coverage.
                </p>
              </div>
              <span className="text-[10px] text-[var(--color-accent-2)] mt-3 block font-semibold group-hover:underline">
                View Benchmark Scores →
              </span>
            </div>
          </Link>
        </div>
      </Card>

      {/* ── KPI Stat Cards ───────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── Recent Uploads ────────────────────────────────────── */}
        <Card className="lg:col-span-2">
          <SectionTitle
            title="Recent Uploads"
            subtitle="Latest documents ingested into the knowledge base"
            action={
              <Link href="/documents" className="text-sm text-[var(--color-accent)] hover:underline">
                View all
              </Link>
            }
          />
          {data.recent_documents.length === 0 ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">
              No documents ingested yet. Upload files via the Documents page.
            </p>
          ) : (
            <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
              <table className="w-full text-sm">
                <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                  <tr>
                    <th className="px-4 py-2 font-medium">Document</th>
                    <th className="px-4 py-2 font-medium">Type</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Chunks</th>
                    <th className="px-4 py-2 font-medium">When</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_documents.map((d) => (
                    <tr key={d.id} className="border-t border-[var(--color-border)]">
                      <td className="px-4 py-2.5">{d.filename}</td>
                      <td className="px-4 py-2.5 text-[var(--color-muted)]">
                        {typeLabel(d.content_type)}
                      </td>
                      <td className="px-4 py-2.5">
                        <span className={d.status === "processed" || d.status === "extracted" ? "text-emerald-300" : "text-amber-300"}>
                          {d.status === "processed" || d.status === "extracted" ? "Indexed" : d.status}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-[var(--color-muted)]">{d.chunk_count}</td>
                      <td className="px-4 py-2.5 text-[var(--color-muted)]">{timeAgo(d.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* ── High-Risk Assets ──────────────────────────────────── */}
        <Card>
          <SectionTitle
            title="High-Risk Assets"
            action={
              <Link href="/assets" className="text-sm text-[var(--color-accent)] hover:underline">
                View all
              </Link>
            }
          />
          {data.risk_summary.length === 0 ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">
              No risk data available yet. Ingest documents to populate.
            </p>
          ) : (
            <ul className="space-y-3">
              {data.risk_summary.map((a) => (
                <li key={a.asset_tag}>
                  <Link
                    href={`/assets/${a.asset_tag}`}
                    className="flex items-start justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5 transition hover:border-[var(--color-accent)]"
                  >
                    <div>
                      <p className="text-sm font-medium">{a.asset_tag}</p>
                      <p className="text-xs text-[var(--color-muted)]">
                        {a.asset.asset_type ?? "asset"} · {a.risk_reasons[0] ?? "—"}
                      </p>
                    </div>
                    <RiskBadge risk={a.risk_level as Risk} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* ── Top Assets by Mentions ──────────────────────────────── */}
      {data.top_assets_by_mentions.length > 0 && (
        <div className="mt-6">
          <Card>
            <SectionTitle
              title="Top Assets by Mentions"
              subtitle="Most frequently referenced equipment across all documents"
            />
            <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
              <table className="w-full text-sm">
                <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                  <tr>
                    <th className="px-4 py-2 font-medium">Asset Tag</th>
                    <th className="px-4 py-2 font-medium">Type</th>
                    <th className="px-4 py-2 font-medium text-right">Mentions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.top_assets_by_mentions.map((a) => (
                    <tr key={a.asset_tag} className="border-t border-[var(--color-border)]">
                      <td className="px-4 py-2.5">
                        <Link href={`/assets/${a.asset_tag}`} className="text-[var(--color-accent)] hover:underline">
                          {a.asset_tag}
                        </Link>
                      </td>
                      <td className="px-4 py-2.5 text-[var(--color-muted)]">{a.asset_type ?? "—"}</td>
                      <td className="px-4 py-2.5 text-right">{a.mention_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
