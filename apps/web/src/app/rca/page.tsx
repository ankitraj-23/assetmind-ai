import { Card, PageHeader, RiskBadge, SectionTitle, Badge } from "@/components/ui";
import { rcaCase } from "@/lib/mock-data";

export default function RcaPage() {
  return (
    <div>
      <PageHeader
        title="Root Cause Analysis"
        subtitle="AI-assisted RCA grounded in failure history, SOPs, and survey data."
        action={<Badge tone="warn">{rcaCase.status}</Badge>}
      />

      <Card className="mb-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
              {rcaCase.id} · Asset {rcaCase.asset}
            </p>
            <h2 className="mt-1 text-lg font-semibold">{rcaCase.title}</h2>
          </div>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-[var(--color-muted)]">
          {rcaCase.problem}
        </p>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle title="Event Timeline" />
          <ol className="relative space-y-4 border-l border-[var(--color-border)] pl-5">
            {rcaCase.timeline.map((t) => (
              <li key={t.date}>
                <span className="absolute -left-[5px] mt-1 h-2.5 w-2.5 rounded-full bg-[var(--color-accent)]" />
                <p className="text-xs text-[var(--color-muted)]">{t.date}</p>
                <p className="text-sm">{t.event}</p>
              </li>
            ))}
          </ol>
        </Card>

        <Card>
          <SectionTitle title="5 Whys" />
          <ol className="space-y-2">
            {rcaCase.fiveWhys.map((w, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface-2)] text-xs text-[var(--color-accent)]">
                  {i + 1}
                </span>
                <span>{w}</span>
              </li>
            ))}
          </ol>
        </Card>

        <Card className="lg:col-span-2 border-[var(--color-accent)]/40">
          <SectionTitle title="Identified Root Cause" />
          <p className="text-sm leading-relaxed">{rcaCase.rootCause}</p>
        </Card>

        <Card className="lg:col-span-2">
          <SectionTitle title="Recommended Actions" />
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                <tr>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Owner</th>
                  <th className="px-4 py-2 font-medium">Priority</th>
                </tr>
              </thead>
              <tbody>
                {rcaCase.recommendations.map((r) => (
                  <tr key={r.action} className="border-t border-[var(--color-border)]">
                    <td className="px-4 py-2.5">{r.action}</td>
                    <td className="px-4 py-2.5 text-[var(--color-muted)]">{r.owner}</td>
                    <td className="px-4 py-2.5">
                      <RiskBadge risk={r.priority} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
