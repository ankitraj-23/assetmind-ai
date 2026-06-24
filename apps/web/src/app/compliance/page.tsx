import { Card, PageHeader, StatCard, Badge } from "@/components/ui";
import { complianceItems, complianceSummary } from "@/lib/mock-data";

const statusBadge = {
  compliant: <Badge tone="ok">Compliant</Badge>,
  "at-risk": <Badge tone="warn">At Risk</Badge>,
  gap: <Badge tone="bad">Gap</Badge>,
};

export default function CompliancePage() {
  return (
    <div>
      <PageHeader
        title="Compliance"
        subtitle="Standards coverage and open findings detected across assets and documents."
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {complianceSummary.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} />
        ))}
      </div>

      <Card className="mt-6">
        <div className="overflow-hidden rounded-lg border border-[var(--color-border)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--color-surface-2)] text-left text-xs uppercase tracking-wide text-[var(--color-muted)]">
              <tr>
                <th className="px-4 py-3 font-medium">Standard</th>
                <th className="px-4 py-3 font-medium">Asset</th>
                <th className="px-4 py-3 font-medium">Finding</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Due</th>
              </tr>
            </thead>
            <tbody>
              {complianceItems.map((c) => (
                <tr key={c.id} className="border-t border-[var(--color-border)] hover:bg-[var(--color-surface-2)]">
                  <td className="px-4 py-3 font-medium">{c.standard}</td>
                  <td className="px-4 py-3 text-[var(--color-muted)]">{c.asset}</td>
                  <td className="px-4 py-3 text-[var(--color-muted)]">{c.finding}</td>
                  <td className="px-4 py-3">
                    {statusBadge[c.status as keyof typeof statusBadge]}
                  </td>
                  <td className="px-4 py-3 text-[var(--color-muted)]">{c.due}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
