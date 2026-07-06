"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const nav = [
  { href: "/", label: "Dashboard", icon: "▤" },
  { href: "/documents", label: "Documents", icon: "▦" },
  { href: "/upload", label: "Upload", icon: "↥" },
  { href: "/assets", label: "Assets", icon: "⚙" },
  { href: "/copilot", label: "Copilot", icon: "✦" },
  { href: "/rca", label: "RCA", icon: "◎" },
  { href: "/compliance", label: "Compliance", icon: "✓" },
  { href: "/evaluation", label: "Evaluation", icon: "📊" },
];

export default function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)]">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-2)] font-bold text-[var(--color-base)]">
          A
        </div>
        <div>
          <p className="font-semibold leading-tight">AssetMind AI</p>
          <p className="text-xs text-[var(--color-muted)]">Operations Brain</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-2">
        {nav.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
              isActive(item.href)
                ? "bg-[var(--color-surface-2)] text-white"
                : "text-[var(--color-muted)] hover:bg-[var(--color-surface-2)] hover:text-white"
            }`}
          >
            <span className="w-4 text-center text-[var(--color-accent)]">
              {item.icon}
            </span>
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="border-t border-[var(--color-border)] px-5 py-4 text-xs text-[var(--color-muted)]">
        <p>ET AI Hackathon 2026</p>
        <p className="mt-0.5">PS 8 · Unified Asset Brain</p>
      </div>
    </aside>
  );
}
