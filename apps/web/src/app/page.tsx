import Link from "next/link";
import { Card, PageHeader, RiskBadge, SectionTitle, StatCard } from "@/components/ui";
import {
  dashboardStats,
  highRiskAssets,
  recentQueries,
  recentUploads,
} from "@/lib/mock-data";

export default function DashboardPage() {
  return (
    <div>
      <PageHeader
        title="Operations Dashboard"
        subtitle="Unified view of indexed knowledge, asset health, and compliance posture."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {dashboardStats.map((s) => (
          <StatCard key={s.label} {...s} />
        ))}
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionTitle
            title="Recent Uploads"
            subtitle="Latest documents ingested into the knowledge base"
            action={
              <Link href="/documents" className="text-sm text-[var(--color-accent)] hover:underline">
                View all
              </Link>
            }
          />
          <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
            <table className="w-full text-sm">
              <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
                <tr>
                  <th className="px-4 py-2 font-medium">Document</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Chunks</th>
                  <th className="px-4 py-2 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {recentUploads.map((u) => (
                  <tr key={u.id} className="border-t border-[var(--color-border)]">
                    <td className="px-4 py-2.5">{u.name}</td>
                    <td className="px-4 py-2.5 text-[var(--color-muted)]">{u.type}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className={
                          u.status === "Indexed"
                            ? "text-emerald-300"
                            : "text-amber-300"
                        }
                      >
                        {u.status}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-[var(--color-muted)]">{u.chunks}</td>
                    <td className="px-4 py-2.5 text-[var(--color-muted)]">{u.when}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <SectionTitle
            title="High-Risk Assets"
            action={
              <Link href="/assets" className="text-sm text-[var(--color-accent)] hover:underline">
                View all
              </Link>
            }
          />
          <ul className="space-y-3">
            {highRiskAssets.map((a) => (
              <li key={a.id}>
                <Link
                  href={`/assets/${a.id}`}
                  className="flex items-start justify-between gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2.5 transition hover:border-[var(--color-accent)]"
                >
                  <div>
                    <p className="text-sm font-medium">{a.name}</p>
                    <p className="text-xs text-[var(--color-muted)]">
                      {a.area} · {a.issue}
                    </p>
                  </div>
                  <RiskBadge risk={a.risk} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="mt-6">
        <Card>
          <SectionTitle
            title="Recent Copilot Queries"
            subtitle="Citation-backed answers requested by operators"
            action={
              <Link href="/copilot" className="text-sm text-[var(--color-accent)] hover:underline">
                Open Copilot
              </Link>
            }
          />
          <ul className="divide-y divide-[var(--color-border)]">
            {recentQueries.map((q) => (
              <li key={q.q} className="flex items-center justify-between gap-4 py-3">
                <span className="text-sm">{q.q}</span>
                <span className="flex shrink-0 items-center gap-3 text-xs text-[var(--color-muted)]">
                  <span>{q.citations} citations</span>
                  <span>{q.when}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
