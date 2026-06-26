"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, PageHeader, Badge } from "@/components/ui";
import { listAssets, type ApiAsset } from "@/lib/api";

export default function AssetsPage() {
  const [assets, setAssets] = useState<ApiAsset[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listAssets()
      .then((data) => active && setAssets(data))
      .catch(
        (err) =>
          active &&
          setError(
            err instanceof Error ? err.message : "Could not load assets.",
          ),
      );
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
          <p className="px-1 py-6 text-center text-sm text-red-400">
            {error}
          </p>
        </Card>
      ) : assets === null ? (
        <Card>
          <p className="px-1 py-6 text-center text-sm text-[var(--color-muted)]">
            Loading assets…
          </p>
        </Card>
      ) : assets.length === 0 ? (
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
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {assets.map((a) => (
            <Link key={a.id} href={`/assets/${a.tag}`}>
              <Card className="h-full transition hover:border-[var(--color-accent)]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold">{a.tag}</p>
                    <p className="text-xs text-[var(--color-muted)]">
                      {a.display_name}
                    </p>
                  </div>
                  <Badge>{a.asset_type}</Badge>
                </div>
                <dl className="mt-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-[var(--color-muted)]">Type</dt>
                    <dd className="capitalize">{a.asset_type.replace("_", " ")}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-[var(--color-muted)]">Added</dt>
                    <dd>{a.created_at.slice(0, 10)}</dd>
                  </div>
                </dl>
                <p className="mt-4 text-xs text-[var(--color-accent)]">
                  View evidence →
                </p>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
