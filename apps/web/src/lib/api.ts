/**
 * API helper placeholders for the AssetMind AI backend (apps/api, FastAPI on :8000).
 *
 * NOTE: The web shell currently renders mock data only. These helpers define the
 * intended contract for later wiring — they are NOT called by any page yet.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  listDocuments: () => getJSON("/documents"),
  getChunks: (documentId: string) =>
    getJSON(`/documents/${documentId}/chunks`),
  getEmbeddings: (documentId: string) =>
    getJSON(`/documents/${documentId}/embeddings`),
  search: (q: string) => getJSON(`/search?q=${encodeURIComponent(q)}`),
  uploadDocument: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return fetch(`${API_BASE_URL}/documents`, { method: "POST", body });
  },
  query: (question: string) =>
    fetch(`${API_BASE_URL}/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }).then((r) => r.json()),
};
