export default function Header() {
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-6">
      <div className="relative w-full max-w-md">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)]">
          ⌕
        </span>
        <input
          type="text"
          placeholder="Search assets, documents, procedures…"
          className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-2 pl-9 pr-3 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]"
        />
      </div>

      <div className="flex items-center gap-4">
        <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-1 text-xs text-[var(--color-muted)]">
          Demo Plant · Refinery North
        </span>
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-surface-2)] text-sm font-medium">
          AR
        </div>
      </div>
    </header>
  );
}
