# AssetMind AI — API Contract (Week 1)

Backend: FastAPI, served at `http://127.0.0.1:8000` (interactive docs at `/docs`).

This document describes the endpoints available in the Week 1 RAG foundation. All
embeddings and the query answer are **deterministic local placeholders** (no external
model calls) and are designed to be swapped for real models later without changing
these contracts.

## Endpoint summary

| Method | Path                                | Purpose                                            |
| ------ | ----------------------------------- | -------------------------------------------------- |
| POST   | `/documents`                        | Upload a PDF/text file; extract text and store it. |
| GET    | `/documents`                        | List ingested documents.                           |
| GET    | `/documents/{document_id}/chunks`   | Return ordered text chunks for a document.         |
| GET    | `/documents/{document_id}/embeddings` | Return embedding metadata + short vector previews. |
| GET    | `/search?q=...`                     | Retrieve top-k chunks for a query (no answer).     |
| POST   | `/query`                            | Citation-backed answer assembled from top-k chunks.|

A health check is also available at `GET /health`.

---

## POST /documents

Upload a PDF or text file. The backend extracts text, chunks it, computes embeddings,
and stores metadata locally.

- **Request:** `multipart/form-data` with a single `file` field.
- **Status:** `201 Created`
- **Response (`Document`):**

```json
{
  "id": "string",
  "filename": "pump_p101_note.txt",
  "content_type": "text/plain",
  "size_bytes": 1820,
  "text_char_count": 1750,
  "status": "processed",
  "storage_path": "string",
  "created_at": "2026-06-24T10:00:00Z",
  "chunk_count": 3
}
```

## GET /documents

List all ingested documents.

- **Response:** `list[Document]` (see shape above).

## GET /documents/{document_id}/chunks

Return the ordered, character-bounded text chunks for one document.

- **Errors:** `404` if the document id is unknown.
- **Response (`DocumentChunks`):**

```json
{
  "document_id": "string",
  "chunks": [
    {
      "id": "string",
      "document_id": "string",
      "chunk_index": 0,
      "text": "string",
      "char_start": 0,
      "char_end": 800
    }
  ]
}
```

## GET /documents/{document_id}/embeddings

Return embedding metadata for a document. Full vectors are stored locally; the API
returns only a short `preview` of each vector to avoid large payloads.

- **Errors:** `404` if the document id is unknown.
- **Embedding model:** `local-hashing-v1`, dimension `384` (deterministic placeholder).
- **Response (`DocumentEmbeddings`):**

```json
{
  "document_id": "string",
  "embedding_model": "local-hashing-v1",
  "dimension": 384,
  "embeddings": [
    {
      "chunk_id": "string",
      "document_id": "string",
      "chunk_index": 0,
      "dimension": 384,
      "preview": [0.12, -0.03, 0.41]
    }
  ]
}
```

## GET /search?q=...

Embed the query and return the most similar stored chunks. Retrieval only — no
generated answer.

- **Query params:** `q` (required, non-empty), `top_k` (optional, default `5`, `1`–`50`).
- **Errors:** `400` if `q` is empty.
- **Response (`SearchResponse`):**

```json
{
  "query": "Why is Pump P-101 vibrating?",
  "top_k": 5,
  "results": [
    {
      "document_id": "string",
      "chunk_id": "string",
      "chunk_index": 0,
      "score": 0.87,
      "text": "string",
      "filename": "pump_p101_note.txt",
      "citation": {
        "document_id": "string",
        "chunk_id": "string",
        "chunk_index": 0,
        "filename": "pump_p101_note.txt"
      }
    }
  ]
}
```

## POST /query

Answer a natural-language question from retrieved context. The answer is produced by a
temporary deterministic generator and is returned with citations to the source chunks.

- **Request (`QueryRequest`):**

```json
{
  "question": "Why is Pump P-101 vibrating?",
  "top_k": 5
}
```

- **Errors:** `400` if `question` is empty.
- **Response (`QueryResponse`):**

```json
{
  "question": "Why is Pump P-101 vibrating?",
  "answer": "string",
  "confidence": "string",
  "citations": [
    {
      "document_id": "string",
      "chunk_id": "string",
      "chunk_index": 0,
      "score": 0.87,
      "text_preview": "string",
      "filename": "pump_p101_note.txt"
    }
  ],
  "retrieved_count": 3
}
```

`filename` is included on citations so the UI can show a human-readable source; it falls
back to `document_id` when absent.
