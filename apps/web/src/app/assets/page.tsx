import Link from "next/link";
import { Card, PageHeader, RiskBadge } from "@/components/ui";
import { assets } from "@/lib/mock-data";

export default function AssetsPage() {
  return (
    <div>
      <PageHeader
        title="Assets"
        subtitle="Equipment discovered and cross-referenced across the document corpus."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {assets.map((a) => (
          <Link key={a.id} href={`/assets/${a.id}`}>
            <Card className="h-full transition hover:border-[var(--color-accent)]">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-semibold">{a.name}</p>
                  <p className="text-xs text-[var(--color-muted)]">{a.type}</p>
                </div>
                <RiskBadge risk={a.risk} />
              </div>
              <dl className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Area</dt>
                  <dd>{a.area}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Documents</dt>
                  <dd>{a.docs}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Last Event</dt>
                  <dd>{a.lastEvent}</dd>
                </div>
              </dl>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
