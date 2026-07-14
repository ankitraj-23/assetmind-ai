"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, StatCard, Badge, RiskBadge, SectionTitle } from "@/components/ui";
import {
  listDocuments,
  getDashboardSummary,
  listAssets,
  generateEvidencePackage,
  getEvidencePackageDownloadUrl,
  type ApiDocument,
  type ApiDashboardSummary,
  type ApiAsset,
  type ApiEvidencePackageResponse,
} from "@/lib/api";

interface ComplianceItem {
  id: string;
  asset: string;
  gapType: "Missing inspection" | "Expired certificate" | "Calibration overdue" | "SOP issue" | "High vibration";
  severity: "high" | "medium" | "low";
  reason: string;
  standard: string;
  evidence: string;
  recommendedAction: string;
  sourceFilename: string;
}

const complianceGaps: ComplianceItem[] = [
  {
    id: "COMP-001",
    asset: "BLR-118",
    gapType: "Expired certificate",
    severity: "high",
    reason: "Annual pressure test certificate is expired. Running a boiler without it is a major regulatory violation and exposes the facility to a shutdown notice.",
    standard: "Factories Act Section 31 / PESO",
    evidence: "A1. BLR-118 - Annual pressure test certificate: EXPIRED (01-Feb-2025). Required by Factories Act Section 31 and PESO. Status: NON-COMPLIANT.",
    recommendedAction: "Schedule approved inspection authority visit immediately to perform pressure test and renew certificate.",
    sourceFilename: "compliance_checklist_2025.pdf",
  },
  {
    id: "COMP-002",
    asset: "P-101",
    gapType: "High vibration",
    severity: "high",
    reason: "Vibration reading of 6.2 mm/s exceeds OISD-137 limit of 4.5 mm/s.",
    standard: "OISD-137 Limit",
    evidence: "B1. P-101 - Vibration inspection: NON-COMPLIANT. Reading 6.2 mm/s exceeds OISD-137 limit of 4.5 mm/s. Action required within 48 hours.",
    recommendedAction: "Perform laser shaft alignment check and re-baseline vibration.",
    sourceFilename: "compliance_checklist_2025.pdf",
  },
  {
    id: "COMP-003",
    asset: "TK-482",
    gapType: "Calibration overdue",
    severity: "medium",
    reason: "Level transmitter LT-482-01 calibration is overdue by 45 days. Factories Act requires process vessel instrument calibration every 6 months.",
    standard: "Factory Act Schedule VIII",
    evidence: "C1. TK-482 Level Transmitter LT-482-01 - Calibration: OVERDUE by 45 days. Required every 6 months.",
    recommendedAction: "Complete level transmitter calibration and submit certificate.",
    sourceFilename: "compliance_checklist_2025.pdf",
  },
  {
    id: "COMP-004",
    asset: "R-201",
    gapType: "Missing inspection",
    severity: "medium",
    reason: "SRV-R201-01 safety relief valve bench-test is due. OISD-116 requires bench-testing every 18 months.",
    standard: "OISD-116 Safety",
    evidence: "A2. R-201 - Safety relief valve SRV-R201-01 test certificate: DUE March 2025. Required by OISD-116 every 18 months.",
    recommendedAction: "Schedule SRV bench test at approved facility.",
    sourceFilename: "compliance_checklist_2025.pdf",
  },
  {
    id: "COMP-005",
    asset: "P-101",
    gapType: "SOP issue",
    severity: "low",
    reason: "SOP-PUMP-07 (Centrifugal Pump Startup/Shutdown) review cycle has elapsed.",
    standard: "ISO 9001:2015 Clause 8",
    evidence: "D1. SOP-PUMP-07 (Pump Startup and Shutdown) - Last reviewed: March 2024. Review cycle: 12 months. Next due: March 2025. Status: DUE FOR REVIEW.",
    recommendedAction: "Initiate annual engineering review and sign-off for SOP-PUMP-07.",
    sourceFilename: "compliance_checklist_2025.pdf",
  },
  {
    id: "COMP-006",
    asset: "Plant-wide",
    gapType: "SOP issue",
    severity: "high",
    reason: "HSE-LOTO-001 (Lockout-Tagout) review is overdue by 6 months.",
    standard: "OSHA 1910.147 LOTO",
    evidence: "D2. HSE-LOTO-001 (Lockout-Tagout) - Last reviewed: November 2023. Status: OVERDUE for review by 6 months.",
    recommendedAction: "Revise LOTO standard operating procedure to include mandatory digital checklists.",
    sourceFilename: "compliance_checklist_2025.pdf",
  },
];

const filters = [
  { id: "all", label: "All Gaps" },
  { id: "high", label: "High Severity" },
  { id: "missing", label: "Missing Inspection" },
  { id: "expired", label: "Expired Certificate" },
  { id: "calibration", label: "Calibration Overdue" },
  { id: "sop", label: "SOP Issue" },
];

export default function CompliancePage() {
  const [documents, setDocuments] = useState<ApiDocument[]>([]);
  const [summary, setSummary] = useState<ApiDashboardSummary | null>(null);
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [activeFilter, setActiveFilter] = useState("all");
  const [assetFilter, setAssetFilter] = useState<string | null>(null);

  // Evidence Package Generation State
  const [targetAsset, setTargetAsset] = useState("");
  const [packageResult, setPackageResult] = useState<ApiEvidencePackageResponse | null>(null);
  const [packageLoading, setPackageLoading] = useState(false);
  const [packageError, setPackageError] = useState<string | null>(null);

  // Load backend stats and documents on mount
  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(() => {});
    
    getDashboardSummary()
      .then(setSummary)
      .catch(() => {});

    listAssets()
      .then((res) => {
        setAssets(res);

        // Check query parameters on mount once assets are loaded
        if (typeof window !== "undefined") {
          const params = new URLSearchParams(window.location.search);
          const assetParam = params.get("asset");
          const actionParam = params.get("action");
          if (assetParam) {
            setTargetAsset(assetParam);
            setAssetFilter(assetParam);
            if (actionParam === "generate") {
              setPackageLoading(true);
              setPackageError(null);
              setPackageResult(null);
              generateEvidencePackage(assetParam)
                .then(setPackageResult)
                .catch((err) => setPackageError(err instanceof Error ? err.message : "Failed to compile package."))
                .finally(() => setPackageLoading(false));
            }
          }
        }
      })
      .catch(() => setAssets([]));
  }, []);

  // Map filename -> document ID for clickable document links
  const docIdMap = new Map<string, string>();
  documents.forEach((doc) => {
    if (doc.filename) {
      docIdMap.set(doc.filename, doc.id);
    }
  });

  // Filtering logic
  const filteredItems = complianceGaps.filter((item) => {
    if (assetFilter && item.asset !== assetFilter && item.asset !== "Plant-wide") return false;
    if (activeFilter === "all") return true;
    if (activeFilter === "high") return item.severity === "high";
    if (activeFilter === "missing") return item.gapType === "Missing inspection";
    if (activeFilter === "expired") return item.gapType === "Expired certificate";
    if (activeFilter === "calibration") return item.gapType === "Calibration overdue";
    if (activeFilter === "sop") return item.gapType === "SOP issue";
    return true;
  });


  // Status badges map
  const gapTypeTones: Record<string, "bad" | "warn" | "neutral" | "ok"> = {
    "Expired certificate": "bad",
    "High vibration": "bad",
    "Calibration overdue": "warn",
    "Missing inspection": "warn",
    "SOP issue": "neutral",
  };

  // Trigger package generation
  async function handleGeneratePackage() {
    setPackageLoading(true);
    setPackageError(null);
    setPackageResult(null);

    try {
      const res = await generateEvidencePackage(
        targetAsset || undefined,
        undefined // compile all matching standards
      );
      setPackageResult(res);
    } catch (err) {
      setPackageError(err instanceof Error ? err.message : "Failed to compile evidence package.");
    } finally {
      setPackageLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Compliance"
        subtitle="Standards coverage and open findings detected across assets and regulatory manuals."
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          label="Open Compliance Gaps"
          value={summary ? summary.open_compliance_gaps : "—"}
          hint="From active document text heuristics"
        />
        <StatCard
          label="Discovered Assets"
          value={summary ? summary.assets_discovered : "—"}
          hint="Total equipment tracked"
        />
        <StatCard
          label="Ingested Regulations & Reports"
          value={summary ? summary.documents_indexed : "—"}
          hint="Referenced source documents"
        />
      </div>

      {/* Evidence Package Generator Panel */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        
        {/* Generator Controls */}
        <Card className="lg:col-span-1 border-[var(--color-border)] bg-[var(--color-surface)]">
          <SectionTitle title="Audit Evidence Packaging" />
          <p className="text-xs text-[var(--color-muted)] leading-relaxed mb-4">
            Select an asset target to autonomously compile safety logs, certifications, and compliance evidence citations into a downloadable package.
          </p>
          <div className="space-y-4">
            <div>
              <label className="block text-[10px] font-semibold uppercase tracking-wider text-[var(--color-muted)] mb-1.5">
                Target Asset
              </label>
              <select
                value={targetAsset}
                onChange={(e) => setTargetAsset(e.target.value)}
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm text-[var(--color-fg)] focus:border-[var(--color-accent)] focus:outline-none transition"
              >
                <option value="">All Discovered Assets</option>
                {assets.map((asset) => (
                  <option key={asset.tag} value={asset.tag}>
                    {asset.tag} - {asset.display_name}
                  </option>
                ))}
              </select>
            </div>

            <button
              type="button"
              onClick={handleGeneratePackage}
              disabled={packageLoading}
              className="w-full cursor-pointer rounded-lg bg-[var(--color-accent)] px-4 py-2.5 text-center text-sm font-semibold text-[#0b0f17] hover:bg-[var(--color-accent)]/80 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50 transition shadow-[0_0_15px_rgba(45,212,191,0.15)]"
            >
              {packageLoading ? "Compiling Report..." : "Generate Evidence Package"}
            </button>
          </div>
        </Card>

        {/* Live Preview & Download Container */}
        <div className="lg:col-span-2">
          {packageLoading && (
            <Card className="flex flex-col items-center justify-center py-16 text-center space-y-3 h-full">
              <div className="h-8 w-8 animate-spin rounded-full border-4 border-[var(--color-border)] border-t-[var(--color-accent)]" />
              <div>
                <p className="text-xs font-semibold">Packaging Evidence...</p>
                <p className="text-[10px] text-[var(--color-muted)] mt-0.5">
                  Collecting verbatim snippets and resolving provenance documents.
                </p>
              </div>
            </Card>
          )}

          {packageError && (
            <Card className="border-red-500/20 bg-red-500/5 py-12 text-center space-y-2 h-full flex flex-col justify-center">
              <span className="text-lg">⚠️</span>
              <h4 className="text-xs font-semibold text-red-300">Compilation Failed</h4>
              <p className="text-[10px] text-[var(--color-muted)] max-w-sm mx-auto">
                {packageError}
              </p>
            </Card>
          )}

          {packageResult && (
            <Card className="border-[var(--color-accent)]/30 bg-[var(--color-surface-2)]/60 backdrop-blur-md p-5 space-y-4 shadow-[0_0_15px_rgba(45,212,191,0.1)] transition-all duration-300">
              <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] pb-3">
                <div>
                  <span className="text-[9px] font-bold uppercase tracking-wider text-[var(--color-accent)]">
                    Audit Readiness Package Generated
                  </span>
                  <h3 className="text-sm font-bold font-mono mt-0.5 text-[var(--color-fg)]">
                    ID: {packageResult.package_id}
                  </h3>
                </div>
                
                <Link
                  href={getEvidencePackageDownloadUrl(packageResult.download_url)}
                  download={`evidence_package_${packageResult.package_id}.txt`}
                  target="_blank"
                  className="inline-flex items-center gap-1.5 cursor-pointer rounded-lg bg-[var(--color-accent)] px-3.5 py-1.5 text-xs font-bold text-[#0b0f17] hover:bg-[var(--color-accent)]/80 focus:outline-none transition shadow-[0_0_10px_rgba(45,212,191,0.25)]"
                >
                  📥 Download Report (.txt)
                </Link>

              </div>

              {/* Package Details */}
              <div className="space-y-3.5 text-xs">
                <div>
                  <h4 className="text-[10px] font-semibold text-[var(--color-muted)] uppercase tracking-wider">
                    Executive Summary
                  </h4>
                  <p className="mt-1 leading-relaxed text-[#e6edf7] font-medium bg-[var(--color-base)]/40 border border-[var(--color-border)]/50 rounded-lg p-3">
                    {packageResult.summary}
                  </p>
                </div>

                <div>
                  <h4 className="text-[10px] font-semibold text-[var(--color-muted)] uppercase tracking-wider mb-2">
                    Compiled Citations ({packageResult.evidence_items.length})
                  </h4>
                  
                  <div className="max-h-40 overflow-y-auto space-y-2 border border-[var(--color-border)]/50 rounded-lg p-2 bg-[var(--color-base)]/20 custom-scrollbar">
                    {packageResult.evidence_items.map((item, idx) => (
                      <div
                        key={idx}
                        className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded p-2.5 text-[10px] space-y-1.5"
                      >
                        <p className="italic text-[var(--color-fg)] leading-relaxed">
                          &ldquo;{item.text}&rdquo;
                        </p>
                        <div className="flex justify-between text-[9px] text-[var(--color-muted)] pt-1 border-t border-[var(--color-border)]/20 font-mono">
                          <span>Ref: {item.source}</span>
                          <span className="font-semibold text-[var(--color-accent-2)]">Status: {item.status}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </Card>
          )}

          {!packageLoading && !packageError && !packageResult && (
            <Card className="flex flex-col items-center justify-center py-20 text-center text-sm text-[var(--color-muted)] border-dashed border-[var(--color-border)] bg-[var(--color-base)]/10 h-full">
              <span className="text-2xl mb-2">🛡️</span>
              <p className="font-medium text-xs">Audit package output is idle.</p>
              <p className="text-[10px] text-[var(--color-muted)] mt-0.5">
                Configure constraints and click generate on the left.
              </p>
            </Card>
          )}
        </div>

      </div>

      {/* Asset Filter Reset Indicator */}
      {assetFilter && (
        <div className="flex items-center gap-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] px-4 py-2.5 text-xs text-[var(--color-fg)]">
          <span>Filtered by asset: <strong className="font-mono text-[var(--color-accent-2)]">{assetFilter}</strong></span>
          <button
            type="button"
            onClick={() => setAssetFilter(null)}
            className="cursor-pointer ml-auto text-[var(--color-accent)] hover:underline font-bold"
          >
            Clear Filter [x]
          </button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-[var(--color-border)] pb-4 pt-4">

        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            onClick={() => setActiveFilter(f.id)}
            className={`cursor-pointer rounded-lg px-4 py-2 text-xs font-semibold border transition ${
              activeFilter === f.id
                ? "bg-[var(--color-surface-2)] border-[var(--color-accent)] text-[var(--color-accent)] shadow-[0_0_10px_rgba(45,212,191,0.15)]"
                : "border-transparent text-[var(--color-muted)] hover:bg-[var(--color-surface-2)]/50 hover:text-[var(--color-fg)]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Main Table Card */}
      <Card>
        <SectionTitle
          title="Regulatory Findings Tracker"
          subtitle={`Showing ${filteredItems.length} of ${complianceGaps.length} compliance checklist items`}
        />
        
        {filteredItems.length === 0 ? (
          <div className="py-12 text-center text-sm text-[var(--color-muted)]">
            No compliance gaps match the selected filter.
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-base)]/50">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-wider text-[var(--color-muted)] border-b border-[var(--color-border)]">
                  <tr>
                    <th className="px-4 py-3 font-semibold w-24">Asset</th>
                    <th className="px-4 py-3 font-semibold w-36">Gap Type</th>
                    <th className="px-4 py-3 font-semibold w-24">Severity</th>
                    <th className="px-4 py-3 font-semibold">Reason</th>
                    <th className="px-4 py-3 font-semibold w-48">Standard/Reference</th>
                    <th className="px-4 py-3 font-semibold w-72">Evidence</th>
                    <th className="px-4 py-3 font-semibold w-64">Recommended Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--color-border)]">
                  {filteredItems.map((c) => {
                    const docId = docIdMap.get(c.sourceFilename);
                    return (
                      <tr
                        key={c.id}
                        className="hover:bg-[var(--color-surface-2)]/30 transition-colors"
                      >
                        {/* Asset Tag */}
                        <td className="px-4 py-4 font-semibold text-[var(--color-fg)]">
                          {c.asset === "Plant-wide" ? (
                            <span className="text-gray-400 font-medium">Plant-wide</span>
                          ) : (
                            <Link
                              href={`/assets/${encodeURIComponent(c.asset)}`}
                              className="text-[var(--color-accent-2)] hover:underline font-mono"
                            >
                              {c.asset}
                            </Link>
                          )}
                        </td>

                        {/* Gap Type Badge */}
                        <td className="px-4 py-4">
                          <Badge tone={gapTypeTones[c.gapType] || "neutral"}>
                            {c.gapType}
                          </Badge>
                        </td>

                        {/* Severity */}
                        <td className="px-4 py-4">
                          <RiskBadge risk={c.severity} />
                        </td>

                        {/* Reason */}
                        <td className="px-4 py-4 text-xs text-[var(--color-fg)] leading-relaxed min-w-[150px]">
                          {c.reason}
                        </td>

                        {/* Standard/Reference + Document link */}
                        <td className="px-4 py-4 text-xs">
                          <div className="font-semibold text-[var(--color-fg)]">{c.standard}</div>
                          <div className="mt-1.5 text-[10px] text-[var(--color-muted)] flex items-center gap-1">
                            <span>📄</span>
                            {docId ? (
                              <Link
                                href={`/documents/${docId}`}
                                className="text-[var(--color-accent)] hover:underline font-mono"
                              >
                                {c.sourceFilename}
                              </Link>
                            ) : (
                              <span className="font-mono">{c.sourceFilename}</span>
                            )}
                          </div>
                        </td>

                        {/* Evidence Quotation */}
                        <td className="px-4 py-4 text-[11px] leading-relaxed text-[var(--color-muted)] font-mono min-w-[200px]">
                          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-md p-2 relative italic">
                            &ldquo;{c.evidence}&rdquo;
                          </div>
                        </td>

                        {/* Recommended Action */}
                        <td className="px-4 py-4 text-xs text-[var(--color-fg)] leading-relaxed min-w-[180px]">
                          <div className="flex gap-1.5 items-start">
                            <span className="text-[var(--color-accent)] font-semibold shrink-0">✓</span>
                            <span>{c.recommendedAction}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
