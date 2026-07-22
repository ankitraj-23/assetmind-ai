"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Card,
  PageHeader,
  Badge,
  TableScrollRegion,
  MobileDataCard,
  DataRow,
  LoadingState,
  EmptyState,
  ErrorState,
} from "@/components/ui";
import { listDocuments, type ApiDocument } from "@/lib/api";

export default function DocumentsPage() {
  const router = useRouter();
  const [docs, setDocs] = useState<ApiDocument[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listDocuments()
      .then((d) => active && setDocs(d))
      .catch((err) => active && setError(err instanceof Error ? err.message : "Failed to load documents."));
    return () => {
      active = false;
    };
  }, []);

  return (
    <div>
      <PageHeader
        title="Documents"
        subtitle="Manuals, SOPs, datasheets and reports indexed into the knowledge base."
        action={
          <Link
            href="/upload"
            className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]"
          >
            + Upload Document
          </Link>
        }
      />

      <Card>
        {error ? (
          <ErrorState title="Could not load documents" detail={error} />
        ) : docs === null ? (
          <LoadingState label="Loading documents…" />
        ) : docs.length === 0 ? (
          <EmptyState
            title="No documents yet"
            description="Upload industrial PDFs, text notes, work order CSVs, or spreadsheet records to start parsing equipment tags and compliance facts."
            action={
              <Link
                href="/upload"
                className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-accent-fg)] hover:bg-[var(--color-accent-hover)]"
              >
                + Upload Document
              </Link>
            }
          />
        ) : (
          <>
            {/* Desktop / tablet: semantic table (md+) */}
            <TableScrollRegion label="Documents" className="hidden md:block">
              <table className="w-full text-sm">
                <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                  <tr>
                    <th className="px-4 py-3 font-medium">Document</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Chunks</th>
                    <th className="px-4 py-3 font-medium">Characters</th>
                    <th className="px-4 py-3 font-medium">Indexed On</th>
                  </tr>
                </thead>
                <tbody>
                  {docs.map((d) => (
                    <tr
                      key={d.id}
                      onClick={() => router.push(`/documents/${d.id}`)}
                      className="cursor-pointer border-t border-[var(--color-border)] hover:bg-[var(--color-surface-2)]"
                    >
                      <td className="max-w-[22rem] truncate px-4 py-3 font-medium" title={d.filename}>
                        {d.filename}
                      </td>
                      <td className="px-4 py-3">
                        <Badge>{d.content_type}</Badge>
                      </td>
                      <td className="px-4 py-3 text-[var(--color-muted)]">
                        {d.status}
                      </td>
                      <td className="px-4 py-3 text-[var(--color-muted)]">
                        {d.chunk_count}
                      </td>
                      <td className="px-4 py-3 text-[var(--color-muted)]">
                        {d.text_char_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-[var(--color-muted)]">
                        {d.created_at.slice(0, 10)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableScrollRegion>

            {/* Mobile: stacked document cards (below md) */}
            <div className="space-y-3 md:hidden">
              {docs.map((d) => (
                <MobileDataCard key={d.id} onClick={() => router.push(`/documents/${d.id}`)}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 flex-1 truncate font-medium" title={d.filename}>
                      {d.filename}
                    </p>
                    <Badge>{d.content_type}</Badge>
                  </div>
                  <DataRow label="Status">{d.status}</DataRow>
                  <DataRow label="Chunks">{d.chunk_count}</DataRow>
                  <DataRow label="Characters">{d.text_char_count.toLocaleString()}</DataRow>
                  <DataRow label="Indexed">{d.created_at.slice(0, 10)}</DataRow>
                </MobileDataCard>
              ))}
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
