"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, PageHeader, Badge } from "@/components/ui";
import {
  getAsset,
  getAssetMentions,
  type ApiAsset,
  type ApiAssetMentionsResponse,
} from "@/lib/api";

export default function AssetDetailPage() {
  const params = useParams<{ id: string }>();
  const tag = decodeURIComponent(params.id);

  const [asset, setAsset] = useState<ApiAsset | null>(null);
  const [mentions, setMentions] = useState<ApiAssetMentionsResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    Promise.all([getAsset(tag), getAssetMentions(tag)])
      .then(([assetData, mentionsData]) => {
        if (!active) return;
        setAsset(assetData);
        setMentions(mentionsData);
      })
      .catch((err) => {
        if (!active) return;
        setError(
          err instanceof Error ? err.message : "Could not load asset.",
        );
      });

    return () => {
      active = false;
    };
  }, [tag]);

  if (error) {
    return (
      <div>
        <PageHeader
          title="Asset"
          action={
            <Link
              href="/assets"
              className="text-sm text-[var(--color-accent)] hover:underline"
            >
              ← Back to assets
            </Link>
          }
        />
        <Card>
          <p className="px-1 py-6 text-center text-sm text-red-400">
            {error}
          </p>
        </Card>
      </div>
    );
  }

  if (!asset) {
    return (
      <div>
        <PageHeader
          title="Asset"
          action={
            <Link
              href="/assets"
              className="text-sm text-[var(--color-accent)] hover:underline"
            >
              ← Back to assets
            </Link>
          }
        />
        <Card>
          <p className="px-1 py-6 text-center text-sm text-[var(--color-muted)]">
            Loading asset…
          </p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title={asset.tag}
        subtitle={`${asset.asset_type.replace("_", " ")} · ${asset.display_name}`}
        action={
          <Link
            href="/assets"
            className="text-sm text-[var(--color-accent)] hover:underline"
          >
            ← Back to assets
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Overview */}
        <Card className="lg:col-span-2">
          <h2 className="mb-4 text-lg font-semibold tracking-tight">
            Overview
          </h2>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-[var(--color-muted)]">Asset Tag</dt>
              <dd className="mt-0.5 font-medium">{asset.tag}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--color-muted)]">Type</dt>
              <dd className="mt-0.5 font-medium capitalize">
                {asset.asset_type.replace("_", " ")}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--color-muted)]">
                Display Name
              </dt>
              <dd className="mt-0.5 font-medium">{asset.display_name}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--color-muted)]">
                Discovered
              </dt>
              <dd className="mt-0.5 font-medium">
                {asset.created_at.slice(0, 10)}
              </dd>
            </div>
          </dl>
        </Card>

        {/* Mention count summary */}
        <Card>
          <h2 className="mb-4 text-lg font-semibold tracking-tight">
            Evidence Summary
          </h2>
          {mentions === null ? (
            <p className="text-sm text-[var(--color-muted)]">Loading…</p>
          ) : (
            <div className="text-center">
              <p className="text-4xl font-semibold tracking-tight">
                {mentions.count}
              </p>
              <p className="mt-1 text-sm text-[var(--color-muted)]">
                mention{mentions.count === 1 ? "" : "s"} found
              </p>
            </div>
          )}
        </Card>
      </div>

      {/* Evidence mentions */}
      <div className="mt-6">
        <Card>
          <h2 className="mb-4 text-lg font-semibold tracking-tight">
            Evidence Mentions
          </h2>

          {mentions === null ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">
              Loading mentions…
            </p>
          ) : mentions.mentions.length === 0 ? (
            <p className="py-6 text-center text-sm text-[var(--color-muted)]">
              No evidence mentions found for this asset.
            </p>
          ) : (
            <ul className="space-y-4">
              {mentions.mentions.map((m, i) => (
                <li
                  key={m.id}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex h-6 w-6 items-center justify-center rounded bg-[var(--color-surface-2)] text-xs font-medium text-[var(--color-accent)]">
                      {i + 1}
                    </span>
                    <span className="text-sm font-medium">
                      {m.filename ?? m.document_id}
                    </span>
                    <span className="text-xs text-[var(--color-muted)]">
                      — chunk {m.chunk_index ?? "?"}
                    </span>
                  </div>

                  {m.text && (
                    <p className="mt-2 rounded-md bg-[var(--color-surface-2)] px-3 py-2 text-sm leading-relaxed text-[var(--color-muted)]">
                      &ldquo;{m.text}&rdquo;
                    </p>
                  )}

                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--color-muted)]">
                    <span>
                      <strong className="text-[var(--color-accent-2)]">
                        Citation:
                      </strong>{" "}
                      doc {m.citation.document_id?.slice(0, 8) ?? "—"}…
                    </span>
                    <span>chunk_id: {m.citation.chunk_id?.slice(0, 12) ?? "—"}…</span>
                    <span>chunk_index: {m.citation.chunk_index ?? "—"}</span>
                    {m.confidence !== null && (
                      <Badge>confidence: {m.confidence.toFixed(2)}</Badge>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
