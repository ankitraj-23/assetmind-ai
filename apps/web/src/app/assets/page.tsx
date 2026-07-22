"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, RiskBadge, Badge, ErrorState, EmptyState } from "@/components/ui";
import { SearchIcon, CloseIcon } from "@/components/icons";
import {
  listAssets,
  getAssetRiskSummary,
  type ApiAsset,
  type ApiAssetRiskInfo,
} from "@/lib/api";
import type { Risk } from "@/lib/mock-data";

type SortKey = "risk" | "recent" | "alpha";

const RISK_RANK: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };

function prettyType(t?: string | null): string {
  return t ? t.replace(/_/g, " ") : "equipment";
}

export default function AssetsPage() {
  const [assets, setAssets] = useState<ApiAsset[] | null>(null);
  const [riskMap, setRiskMap] = useState<Record<string, ApiAssetRiskInfo>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Discovery toolbar state — all filtering is client-side over the already
  // fetched asset list, so no new API architecture is introduced.
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [riskFilter, setRiskFilter] = useState("all");
  const [sort, setSort] = useState<SortKey>("risk");

  function load() {
    setLoading(true);
    setError(null);
    Promise.all([listAssets(), getAssetRiskSummary(50)])
      .then(([assetList, riskData]) => {
        setAssets(assetList);
        const map: Record<string, ApiAssetRiskInfo> = {};
        for (const r of riskData.assets) map[r.asset_tag] = r;
        setRiskMap(map);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load assets."),
      )
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  const assetTypes = useMemo(() => {
    const set = new Set<string>();
    for (const a of assets ?? []) if (a.asset_type) set.add(a.asset_type);
    return Array.from(set).sort();
  }, [assets]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (assets ?? []).filter((a) => {
      if (q && !a.tag.toLowerCase().includes(q) && !a.display_name.toLowerCase().includes(q))
        return false;
      if (typeFilter !== "all" && a.asset_type !== typeFilter) return false;
      if (riskFilter !== "all" && riskMap[a.tag]?.risk_level !== riskFilter) return false;
      return true;
    });

    const sorted = [...list];
    if (sort === "alpha") {
      sorted.sort((a, b) => a.tag.localeCompare(b.tag));
    } else if (sort === "recent") {
      sorted.sort((a, b) => {
        const la = riskMap[a.tag]?.last_seen ?? a.created_at;
        const lb = riskMap[b.tag]?.last_seen ?? b.created_at;
        return (lb ?? "").localeCompare(la ?? "");
      });
    } else {
      sorted.sort(
        (a, b) =>
          (riskMap[b.tag]?.risk_score ?? -1) - (riskMap[a.tag]?.risk_score ?? -1) ||
          a.tag.localeCompare(b.tag),
      );
    }
    return sorted;
  }, [assets, query, typeFilter, riskFilter, sort, riskMap]);

  const hasAssets = (assets?.length ?? 0) > 0;
  const filtersActive = query.trim() !== "" || typeFilter !== "all" || riskFilter !== "all";

  function clearFilters() {
    setQuery("");
    setTypeFilter("all");
    setRiskFilter("all");
  }

  const selectClass =
    "h-10 min-w-0 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm text-[var(--color-fg)] outline-none transition focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]";

  return (
    <div>
      <PageHeader
        title="Assets"
        subtitle="Find equipment and read its most important signal at a glance."
      />

      {/* ── Discovery toolbar ────────────────────────────────────────── */}
      {hasAssets && (
        <div className="mb-5 space-y-3">
          <div className="relative">
            <label htmlFor="asset-search" className="sr-only">
              Search assets by tag or name
            </label>
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-muted)]" />
            <input
              id="asset-search"
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by tag or name (e.g. P-101)"
              className="h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] pl-9 pr-9 text-sm text-[var(--color-fg)] outline-none transition placeholder:text-[var(--color-muted)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            />
            {query && (
              <button
                type="button"
                onClick={() => setQuery("")}
                aria-label="Clear search"
                className="absolute right-2 top-1/2 inline-flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-[var(--color-muted)] outline-none transition hover:text-[var(--color-fg)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
              >
                <CloseIcon className="h-4 w-4" />
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="type-filter" className="sr-only">
              Filter by asset type
            </label>
            <select
              id="type-filter"
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className={selectClass}
            >
              <option value="all">All types</option>
              {assetTypes.map((t) => (
                <option key={t} value={t}>
                  {prettyType(t)}
                </option>
              ))}
            </select>

            <label htmlFor="risk-filter" className="sr-only">
              Filter by risk level
            </label>
            <select
              id="risk-filter"
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className={selectClass}
            >
              <option value="all">All risk levels</option>
              <option value="high">High risk</option>
              <option value="medium">Medium risk</option>
              <option value="low">Low risk</option>
            </select>

            <label htmlFor="sort-order" className="sr-only">
              Sort assets
            </label>
            <select
              id="sort-order"
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              className={selectClass}
            >
              <option value="risk">Highest risk</option>
              <option value="recent">Most recent evidence</option>
              <option value="alpha">Alphabetical</option>
            </select>

            {filtersActive && (
              <button
                type="button"
                onClick={clearFilters}
                className="h-10 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 text-sm text-[var(--color-muted)] outline-none transition hover:border-[var(--color-accent)] hover:text-[var(--color-fg)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
              >
                Clear
              </button>
            )}

            <p role="status" aria-live="polite" className="ml-auto text-sm text-[var(--color-muted)]">
              {filtered.length} of {assets?.length ?? 0} assets
            </p>
          </div>
        </div>
      )}

      {/* ── Content ──────────────────────────────────────────────────── */}
      {error ? (
        <Card>
          <ErrorState title="Backend Connection Error" detail={error} onRetry={load} />
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
      ) : !hasAssets ? (
        <Card>
          <EmptyState
            title="No assets found"
            description="Upload industrial documents to extract equipment tags."
            action={
              <Link
                href="/upload"
                className="inline-flex h-10 items-center rounded-lg bg-[var(--color-accent)] px-4 text-sm font-medium text-[var(--color-base)] transition hover:opacity-90"
              >
                Upload document
              </Link>
            }
          />
        </Card>
      ) : filtered.length === 0 ? (
        <Card>
          <EmptyState
            title="No matching assets"
            description="No assets match the current search and filters."
            action={
              <button
                type="button"
                onClick={clearFilters}
                className="inline-flex h-10 items-center rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 text-sm transition hover:border-[var(--color-accent)]"
              >
                Clear filters
              </button>
            }
          />
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((a) => {
            const risk = riskMap[a.tag];
            return (
              <Link
                key={a.id}
                href={`/assets/${a.tag}`}
                className="block rounded-xl outline-none transition focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] hover:[&>div]:border-[var(--color-accent)]"
              >
                <Card className="h-full">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="wrap-anywhere font-mono font-semibold">{a.tag}</p>
                      <p className="truncate text-xs text-[var(--color-muted)]">
                        {prettyType(a.asset_type)}
                      </p>
                    </div>
                    {risk ? (
                      <RiskBadge risk={risk.risk_level as Risk} />
                    ) : (
                      <Badge>{prettyType(a.asset_type)}</Badge>
                    )}
                  </div>

                  {risk ? (
                    <>
                      <div className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-muted)]">
                        <span>{risk.mention_count} mentions</span>
                        <span>{risk.document_count} documents</span>
                        <span>Score {risk.risk_score}</span>
                      </div>
                      {risk.risk_reasons.length > 0 && (
                        <p className="mt-2 wrap-anywhere text-xs text-[var(--color-muted)]">
                          {risk.risk_reasons[0]}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="mt-4 text-xs text-[var(--color-muted)]">
                      Discovered {a.created_at.slice(0, 10)}
                    </p>
                  )}
                </Card>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
