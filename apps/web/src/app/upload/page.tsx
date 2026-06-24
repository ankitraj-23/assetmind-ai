"use client";

import { useState } from "react";
import { Card, PageHeader, SectionTitle } from "@/components/ui";

export default function UploadPage() {
  const [fileName, setFileName] = useState<string | null>(null);

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
              {fileName ?? "Drag & drop a file here, or click to browse"}
            </p>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              Supported: .pdf, .txt
            </p>
            <input
              id="file"
              type="file"
              accept=".pdf,.txt"
              className="hidden"
              onChange={(e) => setFileName(e.target.files?.[0]?.name ?? null)}
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
            disabled={!fileName}
            className="mt-5 rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[var(--color-base)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Index Document
          </button>
          <p className="mt-2 text-xs text-[var(--color-muted)]">
            Demo only — file is not sent to the backend yet.
          </p>
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
