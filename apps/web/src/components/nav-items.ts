import type { ComponentType } from "react";
import {
  DashboardIcon,
  DocumentIcon,
  UploadIcon,
  CubeIcon,
  SparkleIcon,
  TargetIcon,
  ShieldIcon,
  ChartIcon,
} from "./icons";

export type NavItem = {
  href: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
};

// Single source of truth for the primary navigation. Shared by the desktop
// sidebar and the mobile drawer so the two can never drift out of sync.
export const navItems: NavItem[] = [
  { href: "/", label: "Dashboard", icon: DashboardIcon },
  { href: "/documents", label: "Documents", icon: DocumentIcon },
  { href: "/upload", label: "Upload", icon: UploadIcon },
  { href: "/assets", label: "Assets", icon: CubeIcon },
  { href: "/copilot", label: "Copilot", icon: SparkleIcon },
  { href: "/rca", label: "RCA", icon: TargetIcon },
  { href: "/compliance", label: "Compliance", icon: ShieldIcon },
  { href: "/evaluation", label: "Evaluation", icon: ChartIcon },
];

export const isNavActive = (pathname: string, href: string) =>
  href === "/" ? pathname === "/" : pathname.startsWith(href);
