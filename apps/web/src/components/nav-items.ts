export type NavItem = { href: string; label: string; icon: string };

// Single source of truth for the primary navigation. Shared by the desktop
// sidebar and the mobile drawer so the two can never drift out of sync.
export const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: "▤" },
  { href: "/documents", label: "Documents", icon: "▦" },
  { href: "/upload", label: "Upload", icon: "↥" },
  { href: "/assets", label: "Assets", icon: "⚙" },
  { href: "/copilot", label: "Copilot", icon: "✦" },
  { href: "/rca", label: "RCA", icon: "◎" },
  { href: "/compliance", label: "Compliance", icon: "✓" },
  { href: "/evaluation", label: "Evaluation", icon: "📊" },
];

export const isNavActive = (pathname: string, href: string) =>
  href === "/" ? pathname === "/" : pathname.startsWith(href);
