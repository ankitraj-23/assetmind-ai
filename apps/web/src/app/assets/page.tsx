"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, Badge, RiskBadge, ErrorState, EmptyState } from "@/components/ui";
import {
  listAssets,
  getAssetRiskSummary,
  type ApiAsset,
  type ApiAssetRiskInfo,
} from "@/lib/api";
import type { Risk } from "@/lib/mock-data";

export default function AssetsPage() {
  const [assets, setAssets] = useState<ApiAsset[] | null>(null);
  const [riskMap, setRiskMap] = useState<Record<string, ApiAssetRiskInfo>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    Promise.all([listAssets(), getAssetRiskSummary(50)])
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

  return (
    <div>
      <PageHeader
        title="Assets"
        subtitle="Equipment discovered and cross-referenced across the document corpus."
      />

      {error ? (
        <Card>
          <ErrorState title="Backend Connection Error" detail={error} />
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
          <EmptyState
            title="No assets found"
            description="Upload industrial documents to extract equipment tags."
            action={
              <Link
                href="/upload"
                className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-base)] hover:opacity-90"
              >
                + Upload Document
              </Link>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(assets ?? []).map((a) => {
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
                    <p className="mt-3 text-xs text-[var(--color-muted)]">
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
      )}
    </div>
  );
}
