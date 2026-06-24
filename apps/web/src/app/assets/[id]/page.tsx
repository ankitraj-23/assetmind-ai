import Link from "next/link";
import { Card, PageHeader, RiskBadge, SectionTitle, Badge } from "@/components/ui";
import { assetDetail } from "@/lib/mock-data";

export default function AssetDetailPage() {
  // Demo shell: always renders the Pump P-101 reference asset regardless of [id].
  const a = assetDetail;

  return (
    <div>
      <PageHeader
        title={a.name}
        subtitle={`${a.type} · ${a.area}`}
        action={
          <Link href="/assets" className="text-sm text-[var(--color-accent)] hover:underline">
            ← Back to assets
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="flex items-center justify-between">
            <SectionTitle title="Overview" />
            <RiskBadge risk={a.risk} />
          </div>
          <p className="text-sm leading-relaxed text-[var(--color-muted)]">
            {a.summary}
          </p>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-[var(--color-muted)]">Asset ID</dt>
              <dd className="mt-0.5 font-medium">{a.id}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--color-muted)]">Manufacturer</dt>
              <dd className="mt-0.5 font-medium">{a.manufacturer}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--color-muted)]">Installed</dt>
              <dd className="mt-0.5 font-medium">{a.installed}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--color-muted)]">Type</dt>
              <dd className="mt-0.5 font-medium">{a.type}</dd>
            </div>
          </dl>
        </Card>

        <Card>
          <SectionTitle title="Risk Signals" />
          <ul className="space-y-3">
            {a.risks.map((r) => (
              <li
                key={r.label}
                className="flex items-start justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5"
              >
                <div>
                  <p className="text-sm font-medium">{r.label}</p>
                  <p className="text-xs text-[var(--color-muted)]">{r.note}</p>
                </div>
                <RiskBadge risk={r.level} />
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <SectionTitle title="Related Documents" />
          <ul className="space-y-2">
            {a.relatedDocuments.map((d) => (
              <li
                key={d.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5 text-sm"
              >
                <span>{d.name}</span>
                <Badge>{d.type}</Badge>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <SectionTitle title="Linked SOPs" />
          <ul className="space-y-2">
            {a.sops.map((s) => (
              <li
                key={s.id}
                className="flex items-center justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5 text-sm"
              >
                <span>{s.title}</span>
                <span className="text-xs text-[var(--color-muted)]">{s.ref}</span>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <SectionTitle title="Failure History" />
          <ul className="space-y-3">
            {a.failureHistory.map((f) => (
              <li key={f.date} className="text-sm">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{f.event}</span>
                  <span className="text-xs text-[var(--color-muted)]">{f.date}</span>
                </div>
                <p className="text-xs text-[var(--color-muted)]">
                  Cause: {f.cause} · Downtime: {f.downtime}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
