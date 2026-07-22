"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { navItems, isNavActive } from "./nav-items";

export default function MobileNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  // Lock body scroll and wire up Escape-to-close while the drawer is open.
  useEffect(() => {
    if (!open) return;

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open navigation menu"
        aria-expanded={open}
        aria-controls="mobile-nav-drawer"
        className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] text-lg text-[var(--color-fg)] transition-colors motion-reduce:transition-none hover:bg-[var(--color-surface-2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] lg:hidden"
      >
        <span aria-hidden="true">☰</span>
      </button>

      {/* Overlay + drawer. Kept mounted so it can animate; `inert` removes it
          from tab order and the a11y tree while closed. */}
      <div
        id="mobile-nav-drawer"
        className={`fixed inset-0 z-50 lg:hidden ${open ? "" : "pointer-events-none"}`}
        inert={open ? undefined : true}
      >
        <div
          onClick={() => setOpen(false)}
          aria-hidden="true"
          className={`absolute inset-0 bg-black/60 transition-opacity duration-200 motion-reduce:transition-none ${
            open ? "opacity-100" : "opacity-0"
          }`}
        />

        <nav
          aria-label="Primary"
          className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] shadow-xl transition-transform duration-200 ease-out motion-reduce:transition-none ${
            open ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <div className="flex items-center justify-between gap-3 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-2)] font-bold text-[var(--color-base)]">
                A
              </div>
              <div>
                <p className="font-semibold leading-tight">AssetMind AI</p>
                <p className="text-xs text-[var(--color-muted)]">
                  Operations Brain
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close navigation menu"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-lg text-[var(--color-muted)] transition-colors motion-reduce:transition-none hover:bg-[var(--color-surface-2)] hover:text-[var(--color-fg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            >
              <span aria-hidden="true">✕</span>
            </button>
          </div>

          <div className="flex-1 space-y-1 overflow-y-auto px-3 py-2">
            {navItems.map((item) => {
              const active = isNavActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  aria-current={active ? "page" : undefined}
                  className={`flex min-h-11 items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors motion-reduce:transition-none ${
                    active
                      ? "bg-[var(--color-surface-2)] text-[var(--color-fg)]"
                      : "text-[var(--color-muted)] hover:bg-[var(--color-surface-2)] hover:text-[var(--color-fg)]"
                  }`}
                >
                  <span className="w-4 text-center text-[var(--color-accent)]">
                    {item.icon}
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </div>

          <div className="border-t border-[var(--color-border)] px-5 py-4 text-xs text-[var(--color-muted)]">
            <p>ET AI Hackathon 2026</p>
            <p className="mt-0.5">PS 8 · Unified Asset Brain</p>
          </div>
        </nav>
      </div>
    </>
  );
}
