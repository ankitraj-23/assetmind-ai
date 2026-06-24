"use client";

import { useState } from "react";
import { Card, PageHeader, SectionTitle, Badge } from "@/components/ui";
import { uploadDocument, type ApiDocument } from "@/lib/api";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">(
    "idle",
  );
  const [result, setResult] = useState<ApiDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleUpload() {
    if (!file) return;
    setStatus("uploading");
    setError(null);
    setResult(null);
    try {
      const doc = await uploadDocument(file);
      setResult(doc);
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
        subtitle="Add manuals, SOPs, or reports. Files are chunked and embedded for semantic search."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionTitle title="New Upload" subtitle="PDF or TXT, up to 50 MB" />

          <label
            htmlFor="file"
            className="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-[var(--color-border)] bg-[var(--color-base)] px-6 py-14 text-center transition hover:border-[var(--color-accent)]"
          >
            <span className="text-3xl text-[var(--color-accent)]">↥</span>
            <p className="mt-3 text-sm font-medium">
              {file?.name ?? "Drag & drop a file here, or click to browse"}
            </p>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              Supported: .pdf, .txt
            </p>
            <input
              id="file"
              type="file"
              accept=".pdf,.txt"
              className="hidden"
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setStatus("idle");
                setResult(null);
                setError(null);
              }}
            />
          </label>

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-[var(--color-muted)]">
                Document Type
              </label>
              <select className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]">
                <option>Manual</option>
                <option>SOP</option>
                <option>Datasheet</option>
                <option>Report</option>
                <option>Record</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-[var(--color-muted)]">
                Linked Asset (optional)
              </label>
              <input
                placeholder="e.g. P-101"
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]"
              />
            </div>
          </div>

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
            <div className="mt-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-4">
              <div className="mb-3 flex items-center gap-2">
                <Badge tone="ok">{result.status}</Badge>
                <span className="text-sm font-medium">{result.filename}</span>
              </div>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Characters</dt>
                  <dd>{result.text_char_count.toLocaleString()}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Chunks</dt>
                  <dd>{result.chunk_count}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Type</dt>
                  <dd>{result.content_type}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Size</dt>
                  <dd>{(result.size_bytes / 1024).toFixed(1)} KB</dd>
                </div>
              </dl>
            </div>
          )}
        </Card>

        <Card>
          <SectionTitle title="Ingestion Pipeline" />
          <ol className="space-y-4 text-sm">
            {[
              { step: "Upload", desc: "Original stored securely" },
              { step: "Parse", desc: "Text extracted from PDF/TXT" },
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
