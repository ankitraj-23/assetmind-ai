"use client";

import { useState } from "react";
import { Card, PageHeader, SectionTitle, Badge, TableScrollRegion, MobileDataCard, DataRow } from "@/components/ui";
import {
  uploadDocument,
  listAssets,
  getAssetMentions,
  getAssetFacts,
  type ApiDocument,
} from "@/lib/api";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">(
    "idle",
  );
  const [result, setResult] = useState<ApiDocument | null>(null);
  const [extractedAssets, setExtractedAssets] = useState<string[]>([]);
  const [extractedFacts, setExtractedFacts] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (!file) return;
    setStatus("uploading");
    setError(null);
    setResult(null);
    setExtractedAssets([]);
    setExtractedFacts([]);

    try {
      const doc = await uploadDocument(file);
      setResult(doc);

      // Fetch matching assets and facts extracted from this document
      try {
        const allAssets = await listAssets();
        const matchingAssets: string[] = [];
        const matchingFacts: any[] = [];

        await Promise.all(
          allAssets.map(async (asset) => {
            const mentionsData = await getAssetMentions(asset.tag);
            const hasMention = mentionsData.mentions.some(
              (m) => m.document_id === doc.id,
            );
            if (hasMention) {
              matchingAssets.push(asset.tag);
              const factsData = await getAssetFacts(asset.tag);
              const docFacts = factsData.entities.filter(
                (e) => e.document_id === doc.id,
              );
              matchingFacts.push(...docFacts);
            }
          }),
        );

        setExtractedAssets(matchingAssets);
        setExtractedFacts(matchingFacts);
      } catch (err) {
        console.error("Error fetching extracted details:", err);
      }

      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setStatus("error");
    }
  }

  return (
    <div>
      <PageHeader
        title="Upload Document"
        subtitle="Add manuals, SOPs, work orders, or spreadsheets. Files are chunked and embedded for semantic search."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionTitle
            title="New Upload"
            subtitle="PDF, TXT, CSV, or XLSX up to 50 MB"
          />

          <label
            htmlFor="file"
            className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-[var(--color-border)] bg-[var(--color-base)] px-6 py-14 text-center transition hover:border-[var(--color-accent)]"
          >
            <span className="text-3xl text-[var(--color-accent)]">↥</span>
            <p className="mt-3 text-sm font-medium">
              {file?.name ?? "Drag & drop a file here, or click to browse"}
            </p>
            <p className="mt-2 text-xs text-[var(--color-muted)] max-w-sm">
              Upload industrial PDFs, text notes, work order CSVs, and spreadsheet records.
            </p>
            <p className="mt-1 text-[10px] text-[var(--color-muted)] font-mono">
              Supported: .pdf, .txt, .csv, .xlsx
            </p>
            <input
              id="file"
              type="file"
              accept=".pdf,.txt,.csv,.xlsx,application/pdf,text/plain,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              className="hidden"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setStatus("idle");
                setResult(null);
                setError(null);
                setExtractedAssets([]);
                setExtractedFacts([]);
              }}
            />
          </label>

          <button
            type="button"
            disabled={!file || status === "uploading"}
            onClick={handleUpload}
            className="mt-5 rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[var(--color-base)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {status === "uploading" ? "Indexing…" : "Index Document"}
          </button>

          {status === "error" && error && (
            <p className="mt-3 text-sm text-red-400">{error}</p>
          )}

          {status === "done" && result && (
            <div className="mt-6 space-y-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-2)]/20 p-5">
              
              {/* Document Metadata section */}
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-accent)] mb-3">
                  Document Created
                </h3>
                <div className="flex items-center gap-2 mb-3">
                  <Badge tone="ok">{result.status}</Badge>
                  <span className="text-sm font-medium text-[var(--color-fg)]">
                    {result.filename}
                  </span>
                </div>
                <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
                  <div className="flex justify-between border-b border-[var(--color-border)]/50 pb-1">
                    <dt className="text-[var(--color-muted)]">Document ID</dt>
                    <dd className="font-mono text-[var(--color-fg)]">{result.id.slice(0, 16)}…</dd>
                  </div>
                  <div className="flex justify-between border-b border-[var(--color-border)]/50 pb-1">
                    <dt className="text-[var(--color-muted)]">Size</dt>
                    <dd className="text-[var(--color-fg)]">
                      {(result.size_bytes / 1024).toFixed(1)} KB
                    </dd>
                  </div>
                  <div className="flex justify-between border-b border-[var(--color-border)]/50 pb-1">
                    <dt className="shrink-0 text-[var(--color-muted)]">Content Type</dt>
                    <dd className="min-w-0 wrap-anywhere text-right text-[var(--color-fg)]">{result.content_type}</dd>
                  </div>
                  <div className="flex justify-between border-b border-[var(--color-border)]/50 pb-1">
                    <dt className="text-[var(--color-muted)]">Indexed On</dt>
                    <dd className="text-[var(--color-fg)]">{result.created_at.slice(0, 19).replace("T", " ")}</dd>
                  </div>
                  {(result.embedding_provider || result.embedding_model) && (
                    <div className="flex justify-between border-b border-[var(--color-border)]/50 pb-1 col-span-2">
                      <dt className="shrink-0 text-[var(--color-muted)]">Embeddings</dt>
                      <dd className="min-w-0 wrap-anywhere text-right font-mono text-[var(--color-fg)]">
                        {result.embedding_provider} · {result.embedding_model}
                      </dd>
                    </div>
                  )}
                </dl>
                {result.warnings && result.warnings.length > 0 && (
                  <ul className="mt-3 space-y-1">
                    {result.warnings.map((w) => (
                      <li
                        key={w}
                        className="wrap-anywhere rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-300"
                      >
                        {w}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Chunks section */}
              <div className="border-t border-[var(--color-border)] pt-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[var(--color-accent)]">
                    Chunks Created
                  </h3>
                  <Badge tone="neutral">{result.chunk_count} chunks</Badge>
                </div>
                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  The document text was parsed, segmented into semantic frames, and registered in vector space.
                </p>
              </div>

              {/* Assets section */}
              <div className="border-t border-[var(--color-border)] pt-4">
                <h3 className="text-sm font-semibold text-[var(--color-accent)] mb-2">
                  Assets Extracted
                </h3>
                {extractedAssets.length === 0 ? (
                  <p className="text-xs text-[var(--color-muted)] italic">
                    No equipment tags extracted from this document.
                  </p>
                ) : (
                  <div className="flex flex-wrap gap-2">
                    {extractedAssets.map((tag) => (
                      <Badge key={tag} tone="ok">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              {/* Facts section */}
              <div className="border-t border-[var(--color-border)] pt-4">
                <h3 className="text-sm font-semibold text-[var(--color-accent)] mb-2">
                  Facts Extracted
                </h3>
                {extractedFacts.length === 0 ? (
                  <p className="text-xs text-[var(--color-muted)] italic">
                    No matching facts extracted from this document.
                  </p>
                ) : (
                  <>
                    {/* Desktop / tablet: table (sm+) */}
                    <TableScrollRegion label="Extracted facts" className="hidden bg-[var(--color-base)] sm:block">
                      <table className="w-full text-[11px]">
                        <thead className="bg-[var(--color-surface-2)] text-left uppercase tracking-wide text-[var(--color-muted)] text-[10px]">
                          <tr>
                            <th className="px-3 py-1.5 font-medium">Type</th>
                            <th className="px-3 py-1.5 font-medium">Value</th>
                            <th className="px-3 py-1.5 font-medium">Normalized</th>
                          </tr>
                        </thead>
                        <tbody>
                          {extractedFacts.map((fact) => (
                            <tr key={fact.id} className="border-t border-[var(--color-border)]">
                              <td className="px-3 py-2 font-mono text-[var(--color-muted)]">
                                {fact.entity_type}
                              </td>
                              <td className="wrap-anywhere px-3 py-2">{fact.raw_value}</td>
                              <td className="wrap-anywhere px-3 py-2 font-semibold text-[var(--color-accent-2)]">
                                {fact.normalized_value}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </TableScrollRegion>

                    {/* Mobile: stacked cards (below sm) */}
                    <div className="space-y-2 sm:hidden">
                      {extractedFacts.map((fact) => (
                        <MobileDataCard key={fact.id} className="bg-[var(--color-base)]">
                          <DataRow label="Type">
                            <span className="font-mono text-[var(--color-muted)]">{fact.entity_type}</span>
                          </DataRow>
                          <DataRow label="Value">{fact.raw_value}</DataRow>
                          <DataRow label="Normalized">
                            <span className="font-semibold text-[var(--color-accent-2)]">{fact.normalized_value}</span>
                          </DataRow>
                        </MobileDataCard>
                      ))}
                    </div>
                  </>
                )}
              </div>

            </div>
          )}
        </Card>

        <Card>
          <SectionTitle title="Ingestion Pipeline" />
          <ol className="space-y-4 text-sm">
            {[
              { step: "Upload", desc: "Original stored securely" },
              { step: "Parse", desc: "Text extracted from PDF/TXT/CSV/XLSX" },
              { step: "Chunk", desc: "Split into semantic segments" },
              { step: "Embed", desc: "Vectors generated for search" },
              { step: "Index", desc: "Available to Copilot & RCA" },
            ].map((s, i) => (
              <li key={s.step} className="flex gap-3">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface-2)] text-xs text-[var(--color-accent)]">
                  {i + 1}
                </span>
                <div>
                  <p className="font-medium">{s.step}</p>
                  <p className="text-xs text-[var(--color-muted)]">{s.desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      </div>
    </div>
  );
}
