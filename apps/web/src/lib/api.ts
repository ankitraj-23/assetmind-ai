/**
 * Typed API helpers for the AssetMind AI backend (apps/api, FastAPI on :8000).
 *
 * The types below mirror the backend Pydantic models so the frontend/backend
 * contract is explicit. Base URL is environment-driven and falls back to the
 * local FastAPI dev server.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

/** Mirrors app.models.document.Document */
export interface ApiDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  text_char_count: number;
  status: string;
  storage_path: string;
  created_at: string;
  chunk_count: number;
}

/** Mirrors app.models.chunk.Chunk */
export interface ApiChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  char_start: number;
  char_end: number;
}

/** Mirrors app.models.chunk.DocumentChunks */
export interface ApiDocumentChunks {
  document_id: string;
  chunks: ApiChunk[];
}

/** Mirrors app.models.embedding.EmbeddingPreview */
export interface ApiEmbeddingPreview {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  dimension: number;
  preview: number[];
}

/** Mirrors app.models.embedding.DocumentEmbeddings */
export interface ApiDocumentEmbeddings {
  document_id: string;
  embedding_model: string;
  dimension: number;
  embeddings: ApiEmbeddingPreview[];
}

/** Mirrors app.models.query.QueryCitation */
export interface ApiCitation {
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
  text_preview: string;
  /** Human-readable source filename; falls back to document_id when absent. */
  filename?: string | null;
}

/** Mirrors app.models.query.QueryResponse */
export interface ApiQueryResponse {
  question: string;
  answer: string;
  confidence: string;
  citations: ApiCitation[];
  retrieved_count: number;
}

/** Throw a readable error, surfacing the backend's `detail` message when present. */
async function ensureOk(res: Response, label: string): Promise<Response> {
  if (res.ok) return res;
  let detail = "";
  try {
    const body = await res.json();
    detail = typeof body?.detail === "string" ? `: ${body.detail}` : "";
  } catch {
    /* response had no JSON body */
  }
  throw new Error(`${label} failed (${res.status})${detail}`);
}

/** POST /documents — upload a file for ingestion; returns its stored metadata. */
export async function uploadDocument(file: File): Promise<ApiDocument> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    body,
  });
  await ensureOk(res, "Upload");
  return res.json() as Promise<ApiDocument>;
}

/** GET /documents — list ingested documents. */
export async function listDocuments(): Promise<ApiDocument[]> {
  const res = await fetch(`${API_BASE_URL}/documents`);
  await ensureOk(res, "List documents");
  return res.json() as Promise<ApiDocument[]>;
}

/** GET /documents/{id}/chunks — ordered text chunks for one document. */
export async function getDocumentChunks(
  documentId: string,
): Promise<ApiDocumentChunks> {
  const res = await fetch(
    `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/chunks`,
  );
  await ensureOk(res, "Load chunks");
  return res.json() as Promise<ApiDocumentChunks>;
}

/** GET /documents/{id}/embeddings — embedding metadata with vector previews. */
export async function getDocumentEmbeddings(
  documentId: string,
): Promise<ApiDocumentEmbeddings> {
  const res = await fetch(
    `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/embeddings`,
  );
  await ensureOk(res, "Load embeddings");
  return res.json() as Promise<ApiDocumentEmbeddings>;
}

/** POST /query — ask a question and get a citation-backed answer. */
export async function askQuestion(
  question: string,
  top_k = 5,
): Promise<ApiQueryResponse> {
  const res = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k }),
  });
  await ensureOk(res, "Query");
  return res.json() as Promise<ApiQueryResponse>;
}
