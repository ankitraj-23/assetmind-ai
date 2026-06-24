import Link from "next/link";
import { Card, PageHeader, Badge } from "@/components/ui";
import { documents } from "@/lib/mock-data";

export default function DocumentsPage() {
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
        <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
              <tr>
                <th className="px-4 py-3 font-medium">Document</th>
                <th className="px-4 py-3 font-medium">Type</th>
                <th className="px-4 py-3 font-medium">Linked Asset</th>
                <th className="px-4 py-3 font-medium">Chunks</th>
                <th className="px-4 py-3 font-medium">Embeddings</th>
                <th className="px-4 py-3 font-medium">Indexed On</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((d) => (
                <tr key={d.id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-2)]">
                  <td className="px-4 py-3 font-medium">{d.name}</td>
                  <td className="px-4 py-3">
                    <Badge>{d.type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-[var(--color-muted)]">{d.asset}</td>
                  <td className="px-4 py-3 text-[var(--color-muted)]">{d.chunks}</td>
                  <td className="px-4 py-3 text-[var(--color-muted)]">{d.embeddings}</td>
                  <td className="px-4 py-3 text-[var(--color-muted)]">{d.indexedOn}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
