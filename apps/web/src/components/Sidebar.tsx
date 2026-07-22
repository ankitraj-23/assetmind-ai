"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { navItems, isNavActive } from "./nav-items";

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden h-dvh w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] lg:sticky lg:top-0 lg:flex">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-2)] font-bold text-[var(--color-base)]">
          A
        </div>
        <div>
          <p className="font-semibold leading-tight">AssetMind AI</p>
          <p className="text-xs text-[var(--color-muted)]">Operations Brain</p>
        </div>
      </div>

      <nav aria-label="Primary" className="flex-1 space-y-1 px-3 py-2">
        {navItems.map((item) => {
          const active = isNavActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors motion-reduce:transition-none ${
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
      </nav>

      <div className="border-t border-[var(--color-border)] px-5 py-4 text-xs text-[var(--color-muted)]">
        <p>ET AI Hackathon 2026</p>
        <p className="mt-0.5">PS 8 · Unified Asset Brain</p>
      </div>
    </aside>
  );
}
