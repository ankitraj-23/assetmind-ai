import type { ReactNode } from "react";
import type { Risk } from "@/lib/mock-data";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`min-w-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionTitle({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {subtitle && (
          <p className="text-sm text-[var(--color-muted)]">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}

export function StatCard({
  label,
  value,
  delta,
  hint,
}: {
  label: string;
  value: ReactNode;
  delta?: string;
  hint?: string;
}) {
  return (
    <Card>
      <p className="text-sm text-[var(--color-muted)]">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
      <div className="mt-2 flex items-center gap-2 text-xs">
        {delta && <span className="text-[var(--color-accent)]">{delta}</span>}
        {hint && <span className="text-[var(--color-muted)]">{hint}</span>}
      </div>
    </Card>
  );
}

const riskStyles: Record<Risk, string> = {
  low: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  medium: "bg-amber-500/10 text-amber-300 border-amber-500/30",
  high: "bg-orange-500/10 text-orange-300 border-orange-500/30",
  critical: "bg-red-500/10 text-red-300 border-red-500/30",
};

export function RiskBadge({ risk }: { risk: Risk }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium capitalize ${riskStyles[risk]}`}
    >
      {risk}
    </span>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "ok" | "warn" | "bad";
}) {
  const tones = {
    neutral: "bg-[var(--color-surface-2)] text-[var(--color-muted)] border-[var(--color-border)]",
    ok: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
    warn: "bg-amber-500/10 text-amber-300 border-amber-500/30",
    bad: "bg-red-500/10 text-red-300 border-red-500/30",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

/* ── Responsive table primitives ──────────────────────────────────────
   A horizontally scrollable, keyboard-focusable wrapper for semantic
   tables. Replaces `overflow-hidden` wrappers so no column is clipped and
   the table never widens the page. Pair a `hidden md:block` table with a
   `md:hidden` stack of MobileDataCards for phone layouts. */

export function TableScrollRegion({
  children,
  label,
  className = "",
}: {
  children: ReactNode;
  label: string;
  className?: string;
}) {
  return (
    <div
      role="region"
      aria-label={label}
      tabIndex={0}
      className={`scroll-region rounded-lg border border-[var(--color-border)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] ${className}`}
    >
      {children}
    </div>
  );
}

/* A single record rendered as a stacked card on small screens. */
export function MobileDataCard({
  children,
  href,
  onClick,
  className = "",
}: {
  children: ReactNode;
  href?: string;
  onClick?: () => void;
  className?: string;
}) {
  const base = `block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 ${className}`;
  const content = <div className="space-y-1.5">{children}</div>;
  return (
    <div
      onClick={onClick}
      className={`${base} ${onClick || href ? "cursor-pointer transition hover:border-[var(--color-accent)]" : ""}`}
    >
      {content}
    </div>
  );
}

/* Labelled value row inside a MobileDataCard — the label keeps the field
   understandable without a table header. */
export function DataRow({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-start justify-between gap-3 text-sm ${className}`}>
      <span className="shrink-0 text-xs text-[var(--color-muted)]">{label}</span>
      <span className="min-w-0 wrap-anywhere text-right">{children}</span>
    </div>
  );
}

/* ── Shared status states ──────────────────────────────────────────────
   Unified loading / empty / error surfaces with accessible semantics and
   responsive layout. Page-specific detail is passed through, not lost. */

export function LoadingState({
  label = "Loading…",
  className = "",
}: {
  label?: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center justify-center gap-3 py-10 text-center ${className}`}
    >
      <span
        aria-hidden="true"
        className="h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-accent)]"
      />
      <span className="text-sm text-[var(--color-muted)]">{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
  className = "",
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`px-4 py-10 text-center ${className}`}>
      <p className="text-sm font-medium">{title}</p>
      {description && (
        <p className="mx-auto mt-1 max-w-md wrap-anywhere text-xs text-[var(--color-muted)]">
          {description}
        </p>
      )}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  description,
  detail,
  onRetry,
  retryLabel = "Retry",
  className = "",
}: {
  title?: string;
  description?: ReactNode;
  detail?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={`flex flex-col items-center gap-3 px-4 py-8 text-center ${className}`}
    >
      <div className="rounded-full bg-red-500/10 p-3">
        <svg
          aria-hidden="true"
          className="h-6 w-6 text-red-400"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
      </div>
      <p className="text-sm font-medium text-red-400">{title}</p>
      {description && (
        <p className="max-w-md text-sm text-[var(--color-muted)]">{description}</p>
      )}
      {detail && (
        <p className="max-w-md wrap-anywhere text-xs text-[var(--color-muted)]">{detail}</p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-2 text-sm transition hover:border-[var(--color-accent)]"
        >
          {retryLabel}
        </button>
      )}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="wrap-anywhere text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="mt-1 text-sm text-[var(--color-muted)]">{subtitle}</p>
        )}
      </div>
      {action}
    </div>
  );
}
