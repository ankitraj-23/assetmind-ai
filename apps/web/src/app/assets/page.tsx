"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, Badge, RiskBadge } from "@/components/ui";
import {
  listAssets,
  getAssetRiskSummary,
  type ApiAsset,
  type ApiAssetRiskInfo,
} from "@/lib/api";
import type { Risk } from "@/lib/mock-data";

// Set to 9 to display 9 assets per page
const PAGE_SIZE = 9;

export default function AssetsPage() {
  const [assets, setAssets] = useState<ApiAsset[] | null>(null);
  const [riskMap, setRiskMap] = useState<Record<string, ApiAssetRiskInfo>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    let active = true;

    Promise.all([listAssets(), getAssetRiskSummary(100)])
      .then(([assetList, riskData]) => {
        if (!active) return;
        setAssets(assetList);
        const map: Record<string, ApiAssetRiskInfo> = {};
        for (const r of riskData.assets) {
          map[r.asset_tag] = r;
        }
        setRiskMap(map);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Could not load assets.");
      })
      .finally(() => active && setLoading(false));

    return () => {
      active = false;
    };
  }, []);

  // Pagination calculation
  const totalAssets = assets ?? [];
  const totalPages = Math.ceil(totalAssets.length / PAGE_SIZE);
  const paginatedAssets = totalAssets.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

  return (
    <div>
      <PageHeader
        title="Assets"
        subtitle="Equipment discovered and cross-referenced across the document corpus."
      />

      {error ? (
        <Card>
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <div className="rounded-full bg-red-500/10 p-3">
              <svg className="h-6 w-6 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-red-400">Backend Connection Error</p>
            <p className="max-w-md text-sm text-[var(--color-muted)]">{error}</p>
          </div>
        </Card>
      ) : loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}>
              <div className="h-5 w-20 animate-pulse rounded bg-[var(--color-surface-2)]" />
              <div className="mt-2 h-3 w-32 animate-pulse rounded bg-[var(--color-surface-2)]" />
              <div className="mt-4 space-y-2">
                <div className="h-3 w-full animate-pulse rounded bg-[var(--color-surface-2)]" />
                <div className="h-3 w-full animate-pulse rounded bg-[var(--color-surface-2)]" />
              </div>
            </Card>
          ))}
        </div>
      ) : assets !== null && assets.length === 0 ? (
        <Card>
          <div className="px-1 py-10 text-center">
            <p className="text-sm font-medium">No assets found</p>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              Upload industrial documents to extract equipment tags.
            </p>
            <Link
              href="/upload"
              className="mt-4 inline-block rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-base)] hover:opacity-90"
            >
              + Upload Document
            </Link>
          </div>
        </Card>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {paginatedAssets.map((a) => {
              const risk = riskMap[a.tag];
              return (
                <Link key={a.id} href={`/assets/${a.tag}`}>
                  <Card className="h-full transition hover:border-[var(--color-accent)]">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold">{a.tag}</p>
                        <p className="text-xs text-[var(--color-muted)]">
                          {a.asset_type ? a.asset_type.replace("_", " ") : "equipment"}
                        </p>
                      </div>
                      {risk ? (
                        <RiskBadge risk={risk.risk_level as Risk} />
                      ) : (
                        <Badge>{a.asset_type}</Badge>
                      )}
                    </div>

                    <dl className="mt-4 space-y-2 text-sm">
                      {risk && (
                        <>
                          <div className="flex justify-between">
                            <dt className="text-[var(--color-muted)]">Mentions</dt>
                            <dd>{risk.mention_count}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-[var(--color-muted)]">Documents</dt>
                            <dd>{risk.document_count}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt className="text-[var(--color-muted)]">Risk Score</dt>
                            <dd>{risk.risk_score}</dd>
                          </div>
                        </>
                      )}
                      <div className="flex justify-between">
                        <dt className="text-[var(--color-muted)]">Discovered</dt>
                        <dd>{a.created_at.slice(0, 10)}</dd>
                      </div>
                    </dl>

                    {risk && risk.risk_reasons.length > 0 && (
                      <p className="mt-3 text-xs text-[var(--color-muted)] line-clamp-1">
                        {risk.risk_reasons.slice(0, 2).join(" · ")}
                      </p>
                    )}

                    <p className="mt-3 text-xs text-[var(--color-accent)]">
                      View detail →
                    </p>
                  </Card>
                </Link>
              );
            })}
          </div>

          {/* Pagination Controls */}
          {totalPages > 0 && (
            <div className="flex items-center justify-between border-t border-[var(--color-border)] pt-4 mt-6">
              <button
                type="button"
                disabled={currentPage === 1}
                onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
                className={`px-3.5 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] text-xs font-semibold transition ${
                  currentPage === 1
                    ? "text-[var(--color-muted)]/40 cursor-not-allowed opacity-50"
                    : "text-[var(--color-fg)] hover:border-[var(--color-accent)] cursor-pointer"
                }`}
              >
                ← Previous Page
              </button>

              <span className="text-xs text-[var(--color-muted)] font-medium">
                Page {currentPage} of {totalPages || 1}
              </span>

              <button
                type="button"
                disabled={currentPage === totalPages || totalPages === 0}
                onClick={() => setCurrentPage((prev) => Math.min(totalPages, prev + 1))}
                className={`px-3.5 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] text-xs font-semibold transition ${
                  currentPage === totalPages || totalPages === 0
                    ? "text-[var(--color-muted)]/40 cursor-not-allowed opacity-50"
                    : "text-[var(--color-fg)] hover:border-[var(--color-accent)] cursor-pointer"
                }`}
              >
                Next Page →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
