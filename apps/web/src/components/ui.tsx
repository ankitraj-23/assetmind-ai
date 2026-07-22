import type { KeyboardEvent, ReactNode } from "react";
import Link from "next/link";
import type { Risk } from "@/lib/mock-data";
import { ChevronDownIcon } from "@/components/icons";

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

/* ── Priority metric ───────────────────────────────────────────────────
   A single dashboard metric with two emphasis levels so the layout can
   distinguish one or two primary operational signals from demoted
   secondary counts, instead of showing every metric with equal weight.
   `tone` colours only the primary value, and only for real status. */

const metricToneText: Record<"neutral" | "critical" | "warning" | "positive", string> = {
  neutral: "text-[var(--color-fg)]",
  critical: "text-red-600",
  warning: "text-amber-600",
  positive: "text-emerald-600",
};

export function Metric({
  label,
  value,
  hint,
  icon,
  href,
  tone = "neutral",
  emphasis = "secondary",
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  href?: string;
  tone?: "neutral" | "critical" | "warning" | "positive";
  emphasis?: "primary" | "secondary";
}) {
  const primary = emphasis === "primary";
  const body = (
    <div
      className={`flex h-full min-w-0 flex-col rounded-xl border bg-[var(--color-surface)] p-4 ${
        primary ? "border-[var(--color-border)]" : "border-[var(--color-border)]/70"
      }`}
    >
      <div className="flex items-center gap-1.5 text-[var(--color-muted)]">
        {icon && <span className="shrink-0">{icon}</span>}
        <p className="truncate text-xs font-medium uppercase tracking-wide">{label}</p>
      </div>
      <p
        className={`mt-2 font-semibold tracking-tight ${
          primary ? `text-3xl ${metricToneText[tone]}` : "text-2xl text-[var(--color-fg)]"
        }`}
      >
        {value}
      </p>
      {hint && <p className="mt-1 truncate text-xs text-[var(--color-muted)]">{hint}</p>}
    </div>
  );

  if (!href) return body;
  return (
    <Link
      href={href}
      className="block rounded-xl outline-none transition focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] hover:[&>div]:border-[var(--color-accent)]"
    >
      {body}
    </Link>
  );
}

const riskStyles: Record<Risk, string> = {
  low: "bg-emerald-50 text-emerald-700 border-emerald-200",
  medium: "bg-amber-50 text-amber-700 border-amber-200",
  high: "bg-orange-50 text-orange-700 border-orange-200",
  critical: "bg-red-50 text-red-700 border-red-200",
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
    neutral: "bg-[var(--color-surface-3)] text-[var(--color-muted)] border-[var(--color-border)]",
    ok: "bg-emerald-50 text-emerald-700 border-emerald-200",
    warn: "bg-amber-50 text-amber-700 border-amber-200",
    bad: "bg-red-50 text-red-700 border-red-200",
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

/* A single record rendered as a stacked card on small screens. When `href`
   is set the whole card is a real, keyboard-focusable link (preferred for
   navigable rows); `onClick` remains for non-navigational actions. */
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
  const interactive = Boolean(href || onClick);
  const base = `block rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3 ${
    interactive ? "cursor-pointer transition hover:border-[var(--color-accent)]" : ""
  } ${className}`;
  const content = <div className="space-y-1.5">{children}</div>;
  if (href) {
    return (
      <Link
        href={href}
        className={`${base} outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]`}
      >
        {content}
      </Link>
    );
  }
  return (
    <div onClick={onClick} className={base}>
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
      <div className="rounded-full bg-red-50 p-3">
        <svg
          aria-hidden="true"
          className="h-6 w-6 text-red-600"
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
      <p className="text-sm font-medium text-red-600">{title}</p>
      {description && (
        <p className="max-w-md text-sm text-[var(--color-muted)]">{description}</p>
      )}
      {detail && (
        <p className="max-w-md wrap-anywhere text-xs text-[var(--color-muted)]">{detail}</p>
      )}
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2 text-sm text-[var(--color-fg)] transition-colors hover:bg-[var(--color-surface-2)] hover:border-[var(--color-border-strong)]"
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

/* ── Tabs ───────────────────────────────────────────────────────────────
   Accessible, horizontally scrollable tab strip. Controlled by the parent
   (active key + onChange) so panels can be rendered wherever the page needs
   them. Roving tabindex + arrow/Home/End keys follow the WAI-ARIA tabs
   pattern; render each panel with id=`panel-<key>`, role="tabpanel" and
   aria-labelledby=`tab-<key>` to complete the relationship. */

export interface TabItem {
  key: string;
  label: string;
}

export function Tabs({
  tabs,
  active,
  onChange,
  label,
  className = "",
}: {
  tabs: readonly TabItem[];
  active: string;
  onChange: (key: string) => void;
  label: string;
  className?: string;
}) {
  function handleKey(e: KeyboardEvent<HTMLButtonElement>, idx: number) {
    let next = idx;
    if (e.key === "ArrowRight") next = (idx + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (idx - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    onChange(tabs[next].key);
    const list = e.currentTarget.parentElement;
    (list?.children[next] as HTMLElement | undefined)?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label={label}
      className={`mb-6 flex gap-1 overflow-x-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-1 ${className}`}
    >
      {tabs.map((t, i) => {
        const selected = t.key === active;
        return (
          <button
            key={t.key}
            role="tab"
            id={`tab-${t.key}`}
            type="button"
            aria-selected={selected}
            aria-controls={`panel-${t.key}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.key)}
            onKeyDown={(e) => handleKey(e, i)}
            className={`min-h-[40px] whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium outline-none transition-colors focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] ${
              selected
                ? "bg-[var(--color-surface)] text-[var(--color-accent)] shadow-sm"
                : "text-[var(--color-muted)] hover:text-[var(--color-fg)]"
            }`}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

/* ── Disclosure ─────────────────────────────────────────────────────────
   Progressive-disclosure wrapper built on native <details>/<summary>, so
   expanded/collapsed state is exposed to assistive tech and keyboard-
   operable for free. Used to demote technical detail (chunk IDs, long
   evidence) out of the primary hierarchy without hiding it permanently. */

export function Disclosure({
  summary,
  children,
  defaultOpen = false,
  className = "",
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  return (
    <details open={defaultOpen} className={`group/disclosure ${className}`}>
      <summary className="flex cursor-pointer list-none items-center gap-1.5 text-xs font-medium text-[var(--color-accent)] outline-none marker:hidden hover:underline focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] [&::-webkit-details-marker]:hidden">
        <ChevronDownIcon className="h-3.5 w-3.5 shrink-0 transition-transform group-open/disclosure:rotate-180" />
        {summary}
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}
