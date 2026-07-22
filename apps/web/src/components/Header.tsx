"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { listAssets, type ApiAsset } from "@/lib/api";
import MobileNav from "./MobileNav";

export default function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const [searchVal, setSearchVal] = useState("");
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  // Search is only visible on the main assets pages
  const isAssetsPage = pathname.startsWith("/assets");

  useEffect(() => {
    if (isAssetsPage) {
      listAssets()
        .then(setAssets)
        .catch(() => {});
    }
  }, [isAssetsPage]);

  const handleSearch = () => {
    const query = searchVal.trim();
    if (!query) return;

    // Check if query matches a known asset tag or display_name
    const found = assets.find(
      (a) =>
        a.tag.toLowerCase() === query.toLowerCase() ||
        a.display_name.toLowerCase() === query.toLowerCase()
    );

    if (found) {
      router.push(`/assets/${found.tag}`);
    } else {
      const isAssetTag = /^[A-Za-z]{1,4}-[0-9]{1,4}/.test(query);
      if (isAssetTag) {
        router.push(`/assets/${encodeURIComponent(query.toUpperCase())}`);
      } else {
        router.push(`/copilot?q=${encodeURIComponent(query)}`);
      }
    }
    setSearchVal("");
    setShowSuggestions(false);
  };

  const suggestions = searchVal.trim()
    ? assets
        .filter(
          (a) =>
            a.tag.toLowerCase().includes(searchVal.toLowerCase()) ||
            a.display_name.toLowerCase().includes(searchVal.toLowerCase())
        )
        .slice(0, 5)
    : [];

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 sm:px-6">
      <MobileNav />

      {/* Compact product identity on mobile; the desktop sidebar carries it at lg+ */}
      <Link href="/" className="flex min-w-0 items-center gap-2 lg:hidden">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-2)] text-sm font-bold text-[var(--color-base)]">
          A
        </span>
        <span className="truncate font-semibold sm:hidden">AssetMind</span>
      </Link>

      <div className="relative min-w-0 flex-1 lg:max-w-md">
        {isAssetsPage ? (
          <>
            <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)]">
              ⌕
            </span>
            <input
              type="text"
              placeholder="Search assets (e.g. P-101)..."
              value={searchVal}
              onChange={(e) => {
                setSearchVal(e.target.value);
                setShowSuggestions(true);
              }}
              onFocus={() => setShowSuggestions(true)}
              onBlur={() => {
                // Delay slightly so click is registered on the suggestions before blur closes it
                setTimeout(() => setShowSuggestions(false), 200);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleSearch();
                }
              }}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] py-2 pl-9 pr-3 text-sm text-white outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)] transition"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1.5 max-h-60 overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] shadow-lg z-50 py-1">
                {suggestions.map((asset) => (
                  <button
                    key={asset.tag}
                    type="button"
                    onMouseDown={() => {
                      router.push(`/assets/${asset.tag}`);
                      setSearchVal("");
                      setShowSuggestions(false);
                    }}
                    className="w-full px-4 py-2 text-left text-sm hover:bg-[var(--color-surface-2)] hover:text-white flex items-center justify-between gap-2 border-b border-[var(--color-border)]/30 last:border-b-0 transition-colors"
                  >
                    <div className="min-w-0 truncate">
                      <span className="font-semibold text-white mr-2">{asset.tag}</span>
                      <span className="text-[var(--color-muted)] text-xs">{asset.display_name}</span>
                    </div>
                    <span className="shrink-0 text-[var(--color-muted)] text-[10px] capitalize bg-[var(--color-surface-2)] px-1.5 py-0.5 rounded border border-[var(--color-border)]">
                      {asset.asset_type}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="h-9" /> // placeholder to preserve header layout
        )}
      </div>

      <div className="flex shrink-0 items-center gap-3 sm:gap-4">
        <span className="hidden rounded-full border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-1 text-xs text-[var(--color-muted)] md:inline">
          Demo Plant · Refinery North
        </span>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface-2)] text-sm font-medium">
          AR
        </div>
      </div>
    </header>
  );
}
