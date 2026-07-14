import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";

export const metadata: Metadata = {
  title: "AssetMind AI — Operations Brain",
  description:
    "AI-powered Industrial Knowledge Intelligence for unified asset & operations insight.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased">
        <div className="flex">
          <Sidebar />
          <div className="flex h-screen flex-1 flex-col overflow-hidden">
            <Header />
            <main className="flex-1 overflow-y-auto p-6 pb-24 md:pb-6">{children}</main>
            
            {/* Mobile Bottom Navigation */}
            <nav className="flex md:hidden border-t border-[var(--color-border)] bg-[var(--color-surface)] fixed bottom-0 left-0 right-0 h-16 justify-around items-center z-50 shadow-[0_-2px_10px_rgba(0,0,0,0.3)]">
              <Link href="/" className="flex flex-col items-center gap-1 text-[var(--color-muted)] hover:text-white transition">
                <span className="text-base">🏠</span>
                <span className="text-[9px] font-semibold">Home</span>
              </Link>
              <Link href="/assets" className="flex flex-col items-center gap-1 text-[var(--color-muted)] hover:text-white transition">
                <span className="text-base">⚙️</span>
                <span className="text-[9px] font-semibold">Assets</span>
              </Link>
              <Link href="/rca" className="flex flex-col items-center gap-1 text-[var(--color-muted)] hover:text-white transition">
                <span className="text-base">🔍</span>
                <span className="text-[9px] font-semibold">RCA</span>
              </Link>
              <Link href="/compliance" className="flex flex-col items-center gap-1 text-[var(--color-muted)] hover:text-white transition">
                <span className="text-base">🛡️</span>
                <span className="text-[9px] font-semibold">Compliance</span>
              </Link>
              <Link href="/copilot" className="flex flex-col items-center gap-1 text-[var(--color-muted)] hover:text-white transition">
                <span className="text-base">💬</span>
                <span className="text-[9px] font-semibold">Copilot</span>
              </Link>
            </nav>
          </div>
        </div>
      </body>
    </html>
  );
}
