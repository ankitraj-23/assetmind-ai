"use client";

import {
  useEffect,
  useRef,
  type KeyboardEvent,
  type ReactNode,
} from "react";
import Link from "next/link";
import type { ApiCitation } from "@/lib/api";
import { CloseIcon, ArrowRightIcon } from "@/components/icons";

/* ── Copilot / citation primitives ────────────────────────────────────────
   Small, focused building blocks for the conversation-first Copilot. They
   keep citations tied to the answer they support and move source detail to
   progressive disclosure (chips → drawer) so evidence stays central to trust
   without dominating the reading surface. Deliberately narrow — not a UI
   framework. */

/** Collapse citations that repeat the same chunk so numbering stays stable
    and a source is never listed twice for one answer. */
export function dedupeCitations(citations: ApiCitation[]): ApiCitation[] {
  return citations.filter(
    (citation, index, self) =>
      self.findIndex((item) => item.chunk_id === citation.chunk_id) === index,
  );
}

/** Pull asset-like tags (e.g. P-101) out of an excerpt so a source can show
    which asset it relates to, when that relation is present in the text. */
function extractTags(text: string): string[] {
  const matches = text.match(/\b([A-Za-z]{1,4})-(\d{1,4})([A-Za-z]?)\b/g);
  return matches
    ? Array.from(new Set(matches.map((match) => match.toUpperCase())))
    : [];
}

/* ── Drawer ────────────────────────────────────────────────────────────────
   Overlay used for both sources and sessions: a bottom sheet on phones, a
   right-side panel on wider screens. Never a permanent side rail. Manages
   focus (into the panel on open, back to the trigger on close), traps Tab,
   closes on Escape or backdrop, and locks body scroll while open. */

export function Drawer({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreRef.current = (document.activeElement as HTMLElement) ?? null;
    closeRef.current?.focus();

    function handleKey(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    }
    document.addEventListener("keydown", handleKey);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", handleKey);
      document.body.style.overflow = previousOverflow;
      restoreRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  function trapTab(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return;
    const panel = panelRef.current;
    if (!panel) return;
    const focusable = panel.querySelectorAll<HTMLElement>(
      'a[href],button:not([disabled]),textarea,input,select,[tabindex]:not([tabindex="-1"])',
    );
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <button
        type="button"
        aria-label="Close"
        tabIndex={-1}
        onClick={onClose}
        className="absolute inset-0 bg-black/50"
      />
      <div
        ref={panelRef}
        onKeyDown={trapTab}
        className="absolute inset-x-0 bottom-0 flex max-h-[85dvh] flex-col rounded-t-2xl border-t border-[var(--color-border)] bg-[var(--color-surface)] sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-full sm:max-w-md sm:rounded-t-none sm:border-l sm:border-t-0"
      >
        <div className="flex items-center justify-between gap-3 border-b border-[var(--color-border)] px-4 py-3">
          <h2 className="min-w-0 truncate text-sm font-semibold tracking-tight">
            {title}
          </h2>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-[var(--color-muted)] outline-none transition hover:bg-[var(--color-surface-2)] hover:text-[var(--color-fg)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>
        <div
          className="min-h-0 flex-1 overflow-y-auto px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
        >
          {children}
        </div>
      </div>
    </div>
  );
}

/* ── CitationChips ─────────────────────────────────────────────────────────
   Compact numbered source chips shown under an assistant answer. Each chip is
   a real button that opens the source drawer at that citation. Filenames
   truncate; the full name stays available via title and inside the drawer. */

export function CitationChips({
  citations,
  onOpen,
}: {
  citations: ApiCitation[];
  onOpen: (index: number) => void;
}) {
  if (citations.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-0.5 text-[11px] font-medium uppercase tracking-wide text-[var(--color-muted)]">
        Sources
      </span>
      {citations.map((citation, index) => (
        <button
          key={citation.chunk_id}
          type="button"
          onClick={() => onOpen(index)}
          title={citation.filename ?? citation.document_id}
          className="inline-flex min-h-9 max-w-[12rem] items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 text-xs text-[var(--color-fg)] outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
        >
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--color-base)] text-[11px] font-semibold text-[var(--color-accent)]">
            {index + 1}
          </span>
          <span className="truncate">
            {citation.filename ?? citation.document_id}
          </span>
        </button>
      ))}
    </div>
  );
}

/* ── CitationItem ──────────────────────────────────────────────────────────
   One source rendered in full inside the drawer: filename (linked to the
   document), page/chunk/score, related assets from the excerpt, and the
   excerpt itself. Scrolls into view and is marked current when it is the
   chip the user selected. */

export function CitationItem({
  citation,
  index,
  active = false,
}: {
  citation: ApiCitation;
  index: number;
  active?: boolean;
}) {
  const ref = useRef<HTMLLIElement>(null);
  const tags = extractTags(citation.text_preview);

  useEffect(() => {
    if (active) ref.current?.scrollIntoView({ block: "nearest" });
  }, [active]);

  return (
    <li
      ref={ref}
      aria-current={active ? "true" : undefined}
      className={`rounded-lg border bg-[var(--color-surface-2)] p-3 ${
        active
          ? "border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]"
          : "border-[var(--color-border)]"
      }`}
    >
      <div className="flex min-w-0 items-start gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--color-base)] text-[11px] font-semibold text-[var(--color-accent)]">
          {index + 1}
        </span>
        <Link
          href={`/documents/${citation.document_id}`}
          className="min-w-0 truncate text-sm font-medium text-[var(--color-accent)] hover:underline"
          title={citation.filename ?? citation.document_id}
        >
          {citation.filename ?? citation.document_id}
        </Link>
      </div>
      <p className="mt-1.5 flex flex-wrap gap-x-2 text-xs text-[var(--color-accent-2)]">
        <span>chunk {citation.chunk_index}</span>
        {citation.page_number !== null && citation.page_number !== undefined && (
          <span>· page {citation.page_number}</span>
        )}
        <span>· score {citation.score.toFixed(2)}</span>
      </p>
      {tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {tags.map((tag) => (
            <span
              key={tag}
              className="rounded border border-emerald-500/20 bg-emerald-500/10 px-1 font-mono text-[9px] uppercase text-emerald-300"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
      <p className="mt-2 wrap-anywhere rounded bg-[var(--color-base)] p-2 text-xs leading-relaxed text-[var(--color-muted)]">
        {citation.text_preview}
      </p>
    </li>
  );
}

/* ── ChatComposer ──────────────────────────────────────────────────────────
   Conversation-first input. The textarea grows with content up to a limit;
   Enter submits, Shift+Enter inserts a newline. Asset scope stays visible and
   clearable. Sending is blocked while a request is in flight, and focus
   returns to the textarea after each send. */

export function ChatComposer({
  value,
  onChange,
  onSubmit,
  loading,
  assets,
  selectedAsset,
  onAssetChange,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  assets: { id: string; tag: string }[];
  selectedAsset: string;
  onAssetChange: (value: string) => void;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  function submit() {
    if (loading || !value.trim()) return;
    onSubmit();
    textareaRef.current?.focus();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="flex flex-col gap-2"
    >
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="asset-scope" className="text-xs text-[var(--color-muted)]">
          Scope
        </label>
        <select
          id="asset-scope"
          value={selectedAsset}
          onChange={(event) => onAssetChange(event.target.value)}
          className="min-h-9 min-w-0 max-w-[10rem] rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1 text-xs outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
        >
          <option value="">All assets</option>
          {assets.map((asset) => (
            <option key={asset.id} value={asset.tag}>
              {asset.tag}
            </option>
          ))}
        </select>
        {selectedAsset && (
          <button
            type="button"
            onClick={() => onAssetChange("")}
            className="rounded-lg px-1.5 py-1 text-xs text-[var(--color-muted)] outline-none hover:text-[var(--color-fg)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
          >
            Clear scope
          </button>
        )}
      </div>
      <div className="flex items-end gap-2">
        <label htmlFor="composer-input" className="sr-only">
          Ask the Operations Copilot
        </label>
        <textarea
          id="composer-input"
          ref={textareaRef}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask a question about your assets…"
          className="min-h-[44px] w-full resize-none rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-sm leading-relaxed outline-none placeholder:text-[var(--color-muted)] focus-visible:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
        />
        <button
          type="submit"
          disabled={loading || !value.trim()}
          aria-label="Send message"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-[var(--color-accent)] text-[var(--color-base)] outline-none transition hover:opacity-90 focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ArrowRightIcon className="h-5 w-5" />
        </button>
      </div>
    </form>
  );
}
