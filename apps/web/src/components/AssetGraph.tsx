"use client";

/* ── AssetGraph ─────────────────────────────────────────────────────────
   Frontend-only redesign of the derived knowledge-graph visualisation. The
   backend graph payload is unchanged; this component only improves layout,
   responsiveness and accessibility:

   - dimensions derive from a responsive viewBox (no fixed pixel width),
   - label density is reduced and labels are truncated on narrow containers,
   - a compact filter/legend toolbar collapses below md,
   - an Expand / full-screen action gives the graph the whole viewport,
   - an equivalent, keyboard-operable node list provides non-pointer access
     and a live-region announces the current selection.

   Node-detail rendering stays in the page (it needs mention/fact context);
   this component owns selection and reports it through `onSelect`. */

import { useEffect, useRef, useState } from "react";
import type { ApiAssetGraphEdge, ApiAssetGraphNode } from "@/lib/api";
import { ExpandIcon, CloseIcon } from "@/components/icons";

const NODE_STYLE: Record<
  ApiAssetGraphNode["type"],
  { r: number; fill: string; ring: string; labelDy: number }
> = {
  asset: { r: 22, fill: "rgb(235, 120, 20)", ring: "rgba(235, 120, 20, 0.4)", labelDy: 34 },
  document: { r: 15, fill: "rgb(16, 185, 129)", ring: "rgba(16, 185, 129, 0.3)", labelDy: 25 },
  entity: { r: 13, fill: "rgb(245, 158, 11)", ring: "rgba(245, 158, 11, 0.3)", labelDy: 23 },
  chunk: { r: 10, fill: "rgb(139, 92, 246)", ring: "rgba(139, 92, 246, 0.3)", labelDy: 20 },
};

const LEGEND: { type: ApiAssetGraphNode["type"]; label: string }[] = [
  { type: "asset", label: "Asset" },
  { type: "document", label: "Document" },
  { type: "entity", label: "Entity" },
  { type: "chunk", label: "Chunk" },
];

function truncate(label: string, max: number): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

export function AssetGraph({
  nodes,
  edges,
  counts,
  assetTag,
  includeChunks,
  onIncludeChunks,
  relationType,
  onRelationType,
  selectedId,
  onSelect,
}: {
  nodes: ApiAssetGraphNode[];
  edges: ApiAssetGraphEdge[];
  counts: { nodes: number; edges: number };
  assetTag: string;
  includeChunks: boolean;
  onIncludeChunks: (value: boolean) => void;
  relationType: string;
  onRelationType: (value: string) => void;
  selectedId: string | null;
  onSelect: (node: ApiAssetGraphNode) => void;
}) {
  const [fullscreen, setFullscreen] = useState(false);
  const [compact, setCompact] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  /* Reduce label density based on the actual container width, not the
     viewport, so the graph stays legible in any layout slot. */
  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width ?? 0;
      setCompact(w > 0 && w < 480);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  /* Close full-screen on Escape. */
  useEffect(() => {
    if (!fullscreen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setFullscreen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen]);

  const width = 640;
  const height = 480;
  const cx = width / 2;
  const cy = height / 2;
  const centerId = `asset:${assetTag}`;

  const outer = nodes.filter((n) => n.id !== centerId);
  const pos: Record<string, { x: number; y: number }> = { [centerId]: { x: cx, y: cy } };
  outer.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(outer.length, 1);
    pos[node.id] = { x: cx + 175 * Math.cos(angle), y: cy + 175 * Math.sin(angle) };
  });

  const selectedNode = nodes.find((n) => n.id === selectedId) ?? null;
  const labelMax = compact ? 9 : 16;

  function renderSvg(large: boolean) {
    return (
      <svg
        role="img"
        aria-label={`Knowledge graph for ${assetTag}: ${counts.nodes} nodes and ${counts.edges} relations, radial layout.`}
        viewBox={`0 0 ${width} ${height}`}
        className="h-full w-full select-none"
      >
        <defs>
          <marker
            id="graph-arrow"
            viewBox="0 0 10 10"
            refX="24"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-border-strong)" />
          </marker>
        </defs>

        {/* Edges */}
        {edges.map((edge) => {
          const s = pos[edge.source];
          const t = pos[edge.target];
          if (!s || !t) return null;
          return (
            <line
              key={edge.id}
              x1={s.x}
              y1={s.y}
              x2={t.x}
              y2={t.y}
              stroke="var(--color-border-strong)"
              strokeWidth="1.5"
              strokeDasharray={edge.relation_type === "supported_by_chunk" ? "4" : undefined}
              markerEnd="url(#graph-arrow)"
            >
              <title>{edge.relation_type.replace(/_/g, " ")}</title>
            </line>
          );
        })}

        {/* Nodes */}
        {nodes.map((node) => {
          const p = pos[node.id];
          if (!p) return null;
          const style = NODE_STYLE[node.type];
          const isSelected = node.id === selectedId;
          // Skip chunk labels on narrow containers to cut clutter.
          const showLabel = !(compact && !large && node.type === "chunk");
          return (
            <g
              key={node.id}
              transform={`translate(${p.x}, ${p.y})`}
              onClick={() => onSelect(node)}
              className="cursor-pointer"
            >
              {isSelected && (
                <circle cx="0" cy="0" r={style.r + 6} fill="none" stroke="var(--color-accent)" strokeWidth="2" />
              )}
              <circle cx="0" cy="0" r={style.r + 3} fill="none" stroke={style.ring} strokeWidth="2" />
              <circle cx="0" cy="0" r={style.r} fill={style.fill}>
                <title>{`${node.type}: ${node.label}`}</title>
              </circle>
              {showLabel && (
                <text
                  x="0"
                  y={style.labelDy}
                  textAnchor="middle"
                  className="fill-[var(--color-fg)] text-[11px] font-semibold"
                  stroke="var(--color-base)"
                  strokeWidth="3px"
                  paintOrder="stroke"
                  strokeLinejoin="round"
                >
                  {truncate(node.label, large ? 22 : labelMax)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
    );
  }

  const empty = nodes.length === 0;

  return (
    <div className="space-y-4">
      {/* Toolbar: filters + legend + counts. Collapses below md. */}
      <details className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]" open>
        <summary className="flex min-h-[40px] cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium marker:hidden [&::-webkit-details-marker]:hidden">
          <span>Filters &amp; legend</span>
          <span className="font-mono text-xs text-[var(--color-muted)]">
            {counts.nodes} nodes · {counts.edges} edges
          </span>
        </summary>
        <div className="flex flex-col gap-4 border-t border-[var(--color-border)] px-4 py-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <label className="flex min-h-[40px] cursor-pointer items-center gap-2 text-sm font-medium">
              <input
                type="checkbox"
                checked={includeChunks}
                onChange={(e) => onIncludeChunks(e.target.checked)}
                className="rounded border-[var(--color-border)] bg-[var(--color-base)] text-[var(--color-accent)] focus:ring-0"
              />
              Include chunks
            </label>
            <div className="flex items-center gap-2">
              <label htmlFor="relation-filter" className="text-sm font-medium">
                Relation
              </label>
              <select
                id="relation-filter"
                value={relationType}
                onChange={(e) => onRelationType(e.target.value)}
                className="min-h-[40px] rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-2.5 py-1 text-xs outline-none focus:border-[var(--color-accent)]"
              >
                <option value="">All relations</option>
                <option value="mentioned_in">mentioned in</option>
                <option value="supported_by_chunk">supported by chunk</option>
                <option value="has_entity">has entity</option>
              </select>
            </div>
          </div>
          <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-[var(--color-muted)]">
            {LEGEND.map((item) => (
              <li key={item.type} className="flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: NODE_STYLE[item.type].fill }}
                />
                {item.label}
              </li>
            ))}
          </ul>
        </div>
      </details>

      {/* Graph panel — gets the majority of the space. */}
      <div
        ref={containerRef}
        className="relative w-full overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-base)]"
      >
        {empty ? (
          <div className="flex min-h-[320px] items-center justify-center px-4 py-16 text-center">
            <p className="text-sm text-[var(--color-muted)]">No graph nodes match the current filters.</p>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={() => setFullscreen(true)}
              className="absolute right-2 top-2 z-10 inline-flex min-h-[40px] items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]/90 px-2.5 py-1.5 text-xs font-medium outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            >
              <ExpandIcon className="h-3.5 w-3.5" />
              Expand
            </button>
            <div className="aspect-square max-h-[70vh] w-full sm:aspect-[4/3]">{renderSvg(false)}</div>
          </>
        )}
      </div>

      {/* Accessible, keyboard-operable equivalent of the node graph. */}
      {!empty && (
        <details className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)]">
          <summary className="flex min-h-[40px] cursor-pointer list-none items-center gap-1.5 px-4 py-2.5 text-sm font-medium marker:hidden [&::-webkit-details-marker]:hidden">
            Node list ({nodes.length})
          </summary>
          <ul className="flex flex-wrap gap-2 border-t border-[var(--color-border)] p-3">
            {nodes.map((node) => {
              const isSelected = node.id === selectedId;
              return (
                <li key={node.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(node)}
                    aria-pressed={isSelected}
                    className={`inline-flex min-h-[40px] max-w-full items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs outline-none transition focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] ${
                      isSelected
                        ? "border-[var(--color-accent)] bg-[var(--color-surface-2)]"
                        : "border-[var(--color-border)] hover:border-[var(--color-accent)]"
                    }`}
                  >
                    <span
                      aria-hidden="true"
                      className="inline-block h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: NODE_STYLE[node.type].fill }}
                    />
                    <span className="truncate">{node.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </details>
      )}

      {/* Selection announcement for assistive tech. */}
      <p aria-live="polite" className="sr-only">
        {selectedNode ? `Selected ${selectedNode.type}: ${selectedNode.label}` : "No node selected"}
      </p>

      {/* Full-screen overlay. */}
      {fullscreen && !empty && (
        <div className="fixed inset-0 z-50 flex flex-col bg-[var(--color-base)] p-4" role="dialog" aria-modal="true" aria-label={`Knowledge graph for ${assetTag}, full screen`}>
          <div className="mb-3 flex items-center justify-between">
            <span className="text-sm font-medium">Knowledge graph · {assetTag}</span>
            <button
              type="button"
              onClick={() => setFullscreen(false)}
              className="inline-flex min-h-[40px] items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-1.5 text-sm outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            >
              <CloseIcon className="h-4 w-4" />
              Close
            </button>
          </div>
          <div className="min-h-0 flex-1 overflow-hidden rounded-xl border border-[var(--color-border)]">
            {renderSvg(true)}
          </div>
        </div>
      )}
    </div>
  );
}
