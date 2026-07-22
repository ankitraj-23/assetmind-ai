"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, SectionTitle, Badge, StatCard } from "@/components/ui";
import {
  getComplianceGaps,
  listAssets,
  generateEvidencePackage,
  evidencePackageDownloadUrl,
  type ApiComplianceGap,
  type ApiAsset,
  type ApiEvidencePackageResponse,
} from "@/lib/api";

/* Filter definitions — each maps to a predicate over gap fields. No hardcoded
   findings anywhere: every gap shown comes from the live compliance API. */
type FilterKey =
  | "all"
  | "high"
  | "inspection"
  | "certificate"
  | "calibration"
  | "sop"
  | "rca_safety";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "high", label: "High severity" },
  { key: "inspection", label: "Inspection" },
  { key: "certificate", label: "Certificate" },
  { key: "calibration", label: "Calibration" },
  { key: "sop", label: "SOP" },
  { key: "rca_safety", label: "Missing RCA/safety evidence" },
];

function matchesFilter(gap: ApiComplianceGap, key: FilterKey): boolean {
  switch (key) {
    case "all":
      return true;
    case "high":
      return gap.severity === "high";
    case "inspection":
      return gap.gap_type.startsWith("inspection");
    case "certificate":
      return gap.gap_type.startsWith("certificate");
    case "calibration":
      return gap.gap_type.startsWith("calibration");
    case "sop":
      return gap.gap_type.startsWith("sop");
    case "rca_safety":
      return (
        gap.gap_type === "repeated_failure_no_rca" ||
        gap.gap_type === "safety_procedure_missing"
      );
    default:
      return true;
  }
}

function severityTone(s: string): "ok" | "warn" | "bad" | "neutral" {
  if (s === "high") return "bad";
  if (s === "medium") return "warn";
  if (s === "low") return "ok";
  return "neutral";
}

function prettyGapType(t: string): string {
  return t.replace(/_/g, " ");
}

export default function CompliancePage() {
  const [assetScope, setAssetScope] = useState<string>("");
  const [gaps, setGaps] = useState<ApiComplianceGap[]>([]);
  const [status, setStatus] = useState<"loading" | "done" | "error">("loading");
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");

  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [pkgAsset, setPkgAsset] = useState<string>("P-101");
  const [pkgStatus, setPkgStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [pkg, setPkg] = useState<ApiEvidencePackageResponse | null>(null);
  const [pkgError, setPkgError] = useState<string | null>(null);

  /* Deep-link support: ?asset=P-101 scopes the gaps + evidence package. */
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const asset = params.get("asset");
    if (asset) {
      setAssetScope(asset.toUpperCase());
      setPkgAsset(asset.toUpperCase());
    }
    if (params.get("action") === "generate") {
      // Scroll to the generate panel without auto-submitting.
      setTimeout(() => {
        document.getElementById("evidence-package")?.scrollIntoView({ behavior: "smooth" });
      }, 200);
    }
  }, []);

  function loadGaps(scope: string) {
    setStatus("loading");
    setError(null);
    const req = scope ? { asset_tag: scope } : undefined;
    getComplianceGaps(req)
      .then((res) => {
        setGaps(res.gaps);
        setStatus("done");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load compliance gaps.");
        setStatus("error");
      });
  }

  useEffect(() => {
    loadGaps(assetScope);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assetScope]);

  useEffect(() => {
    listAssets()
      .then((res) => {
        setAssets(res);
        if (res.length > 0 && !res.some((a) => a.tag === pkgAsset)) {
          setPkgAsset(res[0].tag);
        }
      })
      .catch(() => setAssets([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const visibleGaps = useMemo(
    () => gaps.filter((g) => matchesFilter(g, filter)),
    [gaps, filter],
  );

  const summary = useMemo(() => {
    const high = gaps.filter((g) => g.severity === "high").length;
    const medium = gaps.filter((g) => g.severity === "medium").length;
    const assetsAffected = new Set(gaps.map((g) => g.asset_tag)).size;
    return { total: gaps.length, high, medium, assetsAffected };
  }, [gaps]);

  function handleGenerate() {
    if (!pkgAsset) return;
    setPkgStatus("loading");
    setPkgError(null);
    setPkg(null);
    generateEvidencePackage(pkgAsset, "audit")
      .then((res) => {
        setPkg(res);
        setPkgStatus("done");
      })
      .catch((err) => {
        setPkgError(err instanceof Error ? err.message : "Evidence package generation failed.");
        setPkgStatus("error");
      });
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compliance"
        subtitle="Explainable, evidence-backed compliance gaps computed live from indexed plant documents."
        action={
          assetScope ? (
            <span className="flex items-center gap-2">
              <Badge tone="neutral">Scoped: {assetScope}</Badge>
              <button
                onClick={() => setAssetScope("")}
                className="text-xs text-[var(--color-accent)] hover:underline"
              >
                Clear
              </button>
            </span>
          ) : undefined
        }
      />

      {/* Summary tiles */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Open Gaps" value={status === "done" ? summary.total : "—"} />
        <StatCard label="High Severity" value={status === "done" ? summary.high : "—"} />
        <StatCard label="Medium Severity" value={status === "done" ? summary.medium : "—"} />
        <StatCard label="Assets Affected" value={status === "done" ? summary.assetsAffected : "—"} />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((f) => {
          const count = gaps.filter((g) => matchesFilter(g, f.key)).length;
          const active = filter === f.key;
          return (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                active
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                  : "border-[var(--color-border)] bg-[var(--color-surface-2)] text-[var(--color-muted)] hover:border-[var(--color-accent)]/40"
              }`}
            >
              {f.label}
              {status === "done" && <span className="ml-1.5 opacity-70">({count})</span>}
            </button>
          );
        })}
      </div>

      {/* Gaps list — loading / error / empty / data */}
      {status === "loading" && (
        <Card className="flex items-center justify-center gap-3 py-16">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-accent)]" />
          <p className="text-sm text-[var(--color-muted)]">Analyzing compliance evidence…</p>
        </Card>
      )}

      {status === "error" && (
        <Card className="border-red-500/30 bg-red-500/5 py-10 text-center">
          <p className="text-lg">⚠️</p>
          <h3 className="mt-2 text-sm font-semibold text-red-300">Could not load compliance gaps</h3>
          <p className="mx-auto mt-1 max-w-md text-xs text-[var(--color-muted)]">{error}</p>
          <button
            onClick={() => loadGaps(assetScope)}
            className="mt-4 rounded border border-red-500/30 bg-red-500/20 px-3 py-1.5 text-xs font-semibold text-red-300 hover:bg-red-500/30"
          >
            Retry
          </button>
        </Card>
      )}

      {status === "done" && visibleGaps.length === 0 && (
        <Card className="py-14 text-center">
          <p className="text-2xl">✅</p>
          <p className="mt-2 text-sm font-semibold">No compliance gaps for this view</p>
          <p className="mx-auto mt-1 max-w-sm text-xs text-[var(--color-muted)]">
            {gaps.length === 0
              ? assetScope
                ? `No evidence-backed gaps were detected for ${assetScope}.`
                : "No evidence-backed gaps were detected in the indexed corpus."
              : "No gaps match the selected filter. Try a different filter."}
          </p>
        </Card>
      )}

      {status === "done" && visibleGaps.length > 0 && (
        <div className="space-y-4">
          {visibleGaps.map((gap, i) => (
            <Card key={`${gap.asset_tag}-${gap.gap_type}-${i}`} className="space-y-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    href={`/assets/${encodeURIComponent(gap.asset_tag)}`}
                    className="font-semibold text-[var(--color-accent)] hover:underline"
                  >
                    {gap.asset_tag}
                  </Link>
                  <Badge tone="neutral">{prettyGapType(gap.gap_type)}</Badge>
                  <Badge tone={severityTone(gap.severity)}>{gap.severity}</Badge>
                </div>
                {gap.standard_or_policy && (
                  <span className="text-xs text-[var(--color-muted)]">
                    📑 {gap.standard_or_policy}
                  </span>
                )}
              </div>

              <p className="text-sm leading-relaxed text-[var(--color-fg)]">{gap.reason}</p>

              {gap.evidence.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-muted)]">
                    Evidence ({gap.evidence.length})
                  </p>
                  {gap.evidence.map((ev, evIdx) => (
                    <div
                      key={evIdx}
                      className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 text-xs"
                    >
                      <p className="wrap-anywhere italic leading-relaxed text-[var(--color-fg)]/90">
                        &ldquo;{ev.text}&rdquo;
                      </p>
                      <p className="mt-2 border-t border-[var(--color-border)]/40 pt-1.5 font-mono text-[10px] text-[var(--color-muted)]">
                        📁 Source:{" "}
                        {ev.document_id ? (
                          <Link
                            href={`/documents/${ev.document_id}`}
                            className="text-[var(--color-accent)] hover:underline"
                          >
                            {ev.source ?? ev.document_id}
                          </Link>
                        ) : (
                          <span>{ev.source ?? "—"}</span>
                        )}
                        {ev.chunk_id && <span> · chunk {ev.chunk_id.slice(0, 12)}…</span>}
                      </p>
                    </div>
                  ))}
                </div>
              )}

              <div className="rounded-lg border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 p-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent)]">
                  Recommended Action
                </p>
                <p className="mt-1 text-xs leading-relaxed text-[var(--color-fg)]">
                  {gap.recommended_action}
                </p>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Evidence Package generator */}
      <div id="evidence-package" className="scroll-mt-6" />
      <Card className="space-y-4">
        <SectionTitle
          title="Generate Evidence Package"
          subtitle="Compile a citation-backed audit package for an asset from live evidence."
        />
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-[var(--color-muted)]">
              Asset
            </label>
            <select
              value={pkgAsset}
              onChange={(e) => setPkgAsset(e.target.value)}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-fg)] focus:border-[var(--color-accent)] focus:outline-none"
            >
              {!assets.some((a) => a.tag === pkgAsset) && (
                <option value={pkgAsset}>{pkgAsset}</option>
              )}
              {assets.length === 0 ? (
                <option value="P-101">P-101</option>
              ) : (
                assets.map((a) => (
                  <option key={a.tag} value={a.tag}>
                    {a.tag}
                    {a.display_name ? ` — ${a.display_name}` : ""}
                  </option>
                ))
              )}
            </select>
          </div>
          <button
            onClick={handleGenerate}
            disabled={pkgStatus === "loading" || !pkgAsset}
            className="rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-semibold text-[#0b0f17] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pkgStatus === "loading" ? "Generating…" : "📦 Generate Evidence Package"}
          </button>
        </div>

        {pkgStatus === "error" && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3">
            <p className="text-sm text-red-300">{pkgError}</p>
          </div>
        )}

        {pkgStatus === "done" && pkg && (
          <div className="space-y-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--color-accent)]">
                  Package Generated
                </p>
                <h4 className="mt-0.5 text-sm font-semibold">
                  {pkg.asset_tag} · {pkg.package_type}
                </h4>
              </div>
              <a
                href={evidencePackageDownloadUrl(pkg.download_url)}
                target="_blank"
                rel="noopener noreferrer"
                download
                className="rounded-lg border border-[var(--color-accent)]/40 bg-[var(--color-accent)]/10 px-3 py-1.5 text-xs font-semibold text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20"
              >
                ⬇ Download Markdown
              </a>
            </div>

            <p className="text-sm leading-relaxed text-[var(--color-fg)]/90">{pkg.summary}</p>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-3 text-center">
                <p className="text-xl font-semibold">{pkg.included_documents.length}</p>
                <p className="text-[10px] text-[var(--color-muted)]">Documents</p>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-3 text-center">
                <p className="text-xl font-semibold">{pkg.compliance_gaps.length}</p>
                <p className="text-[10px] text-[var(--color-muted)]">Compliance Gaps</p>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-3 text-center">
                <p className="text-xl font-semibold">{pkg.inspection_findings.length}</p>
                <p className="text-[10px] text-[var(--color-muted)]">Inspection Findings</p>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-3 text-center">
                <p className="text-xl font-semibold">{pkg.maintenance_evidence.length}</p>
                <p className="text-[10px] text-[var(--color-muted)]">Maintenance Records</p>
              </div>
            </div>

            <p className="wrap-anywhere font-mono text-[10px] text-[var(--color-muted)]">
              Package ID: {pkg.package_id}
            </p>
          </div>
        )}
      </Card>

      <p className="text-center text-[10px] text-[var(--color-muted)]">
        Findings are automated decision support and require review by an authorised competent
        person before any compliance action.
      </p>
    </div>
  );
}
