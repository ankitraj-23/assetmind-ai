"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Card, PageHeader, Badge } from "@/components/ui";
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
            className="rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-base)] hover:opacity-90"
          >
            + Upload Document
          </Link>
        }
      />

      <Card>
        {error ? (
          <p className="px-1 py-6 text-center text-sm text-red-400">{error}</p>
        ) : docs === null ? (
          <p className="px-1 py-6 text-center text-sm text-[var(--color-muted)]">
            Loading documents…
          </p>
        ) : docs.length === 0 ? (
          <div className="px-1 py-10 text-center">
            <p className="text-sm font-medium">No documents yet</p>
            <p className="mt-1 text-xs text-[var(--color-muted)] max-w-md mx-auto">
              Upload industrial PDFs, text notes, work order CSVs, or spreadsheet records to start parsing equipment tags and compliance facts.
            </p>
            <Link
              href="/upload"
              className="mt-4 inline-block rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-[var(--color-base)] hover:opacity-90"
            >
              + Upload Document
            </Link>
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
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
                    <td className="px-4 py-3 font-medium">{d.filename}</td>
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
          </div>
        )}
      </Card>
    </div>
  );
}
