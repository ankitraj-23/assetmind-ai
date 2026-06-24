"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Card, PageHeader, Badge, StatCard } from "@/components/ui";
import {
  listDocuments,
  getDocumentChunks,
  getDocumentEmbeddings,
  type ApiDocument,
  type ApiChunk,
  type ApiDocumentEmbeddings,
  type ApiEmbeddingPreview,
} from "@/lib/api";

interface DetailData {
  doc: ApiDocument;
  chunks: ApiChunk[];
  embeddings: ApiDocumentEmbeddings;
}

export default function DocumentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [data, setData] = useState<DetailData | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (!id) return;

    (async () => {
      try {
        const docs = await listDocuments();
        const doc = docs.find((d) => d.id === id);
        if (!doc) {
          if (active) setNotFound(true);
          return;
        }
        const [chunks, embeddings] = await Promise.all([
          getDocumentChunks(id),
          getDocumentEmbeddings(id),
        ]);
        if (active) setData({ doc, chunks: chunks.chunks, embeddings });
      } catch (err) {
        if (active)
          setError(
            err instanceof Error ? err.message : "Failed to load document.",
          );
      }
    })();

    return () => {
      active = false;
    };
  }, [id]);

  const backLink = (
    <Link
      href="/documents"
      className="text-sm text-[var(--color-accent)] hover:opacity-90"
    >
      ← Back to Documents
    </Link>
  );

  if (error) {
    return (
      <div>
        <div className="mb-4">{backLink}</div>
        <Card>
          <p className="px-1 py-6 text-center text-sm text-red-400">{error}</p>
        </Card>
      </div>
    );
  }

  if (notFound) {
    return (
      <div>
        <div className="mb-4">{backLink}</div>
        <Card>
          <div className="px-1 py-10 text-center">
            <p className="text-sm font-medium">Document not found</p>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              No document matches this id. It may have been removed.
            </p>
          </div>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <div className="mb-4">{backLink}</div>
        <Card>
          <p className="px-1 py-6 text-center text-sm text-[var(--color-muted)]">
            Loading document…
          </p>
        </Card>
      </div>
    );
  }

  const { doc, chunks, embeddings } = data;

  // Index embedding previews by chunk_id for per-chunk lookup.
  const previewByChunkId = new Map<string, ApiEmbeddingPreview>(
    embeddings.embeddings.map((e) => [e.chunk_id, e]),
  );

  return (
    <div>
      <div className="mb-4">{backLink}</div>

      <PageHeader
        title={doc.filename}
        subtitle="Document detail — chunks and embedding inspector."
        action={<Badge>{doc.content_type}</Badge>}
      />

      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Status" value={doc.status} />
        <StatCard label="Chunks" value={doc.chunk_count} />
        <StatCard
          label="Characters"
          value={doc.text_char_count.toLocaleString()}
        />
        <StatCard label="Indexed On" value={doc.created_at.slice(0, 10)} />
      </div>

      <Card className="mb-6">
        <h2 className="mb-4 text-lg font-semibold tracking-tight">
          Embedding summary
        </h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Model
            </p>
            <p className="mt-1 text-sm font-medium">
              {embeddings.embedding_model}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Dimension
            </p>
            <p className="mt-1 text-sm font-medium">{embeddings.dimension}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Embeddings
            </p>
            <p className="mt-1 text-sm font-medium">
              {embeddings.embeddings.length}
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <h2 className="mb-4 text-lg font-semibold tracking-tight">
          Chunks{" "}
          <span className="text-sm font-normal text-[var(--color-muted)]">
            ({chunks.length})
          </span>
        </h2>

        {chunks.length === 0 ? (
          <p className="px-1 py-6 text-center text-sm text-[var(--color-muted)]">
            No chunks for this document.
          </p>
        ) : (
          <div className="space-y-3">
            {chunks.map((chunk) => {
              const preview = previewByChunkId.get(chunk.id);
              return (
                <div
                  key={chunk.id}
                  className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-4"
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-[var(--color-muted)]">
                    <Badge>#{chunk.chunk_index}</Badge>
                    <span>
                      chars {chunk.char_start.toLocaleString()}–
                      {chunk.char_end.toLocaleString()}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">
                    {chunk.text}
                  </p>
                  {preview && preview.preview.length > 0 && (
                    <div className="mt-3 border-t border-[var(--color-border)] pt-3">
                      <p className="mb-1 text-xs uppercase tracking-wide text-[var(--color-muted)]">
                        Embedding preview · dim {preview.dimension}
                      </p>
                      <p className="font-mono text-xs text-[var(--color-muted)]">
                        [
                        {preview.preview
                          .map((v) => v.toFixed(4))
                          .join(", ")}
                        , …]
                      </p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
