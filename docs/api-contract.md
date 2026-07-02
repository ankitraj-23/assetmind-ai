# AssetMind AI — API Contract (Week 1 + Week 2 Ingestion & Retrieval)

Backend: FastAPI, served at `http://127.0.0.1:8000` (interactive docs at `/docs`).

This document describes the endpoints available in the Week 1 RAG foundation and the
Week 2 ingestion/retrieval additions (CSV/XLSX support, structured fact extraction,
asset-scoped retrieval, and query intent detection). All embeddings and the query answer
are **deterministic local placeholders** (no external model calls) and are designed to
be swapped for real models later without changing these contracts.

## Endpoint summary

| Method | Path                                | Purpose                                            |
| ------ | ----------------------------------- | -------------------------------------------------- |
| POST   | `/documents`                        | Upload a PDF, text, CSV, or XLSX file; extract text and store it. |
| GET    | `/documents`                        | List ingested documents.                           |
| GET    | `/documents/{document_id}/chunks`   | Return ordered text chunks for a document.         |
| GET    | `/documents/{document_id}/embeddings` | Return embedding metadata + short vector previews. |
| GET    | `/search?q=...`                     | Retrieve top-k chunks for a query (no answer).     |
| POST   | `/query`                            | Citation-backed answer assembled from top-k chunks.|

A health check is also available at `GET /health`.

---

## POST /documents

Upload a document. The backend extracts text, chunks it, computes embeddings, and stores
metadata locally. Structured industrial facts are also extracted and persisted alongside
each chunk.

**Supported file types (Week 2 additions marked):**

| Extension | Content-Type | Notes |
| --------- | ------------ | ----- |
| `.pdf` | `application/pdf` | Page numbers tracked via `[Page N]` markers |
| `.txt` | `text/plain` | Full text chunked as-is |
| `.csv` *(Week 2)* | `text/csv` | Each row becomes one chunk; fact extraction per row |
| `.xlsx` *(Week 2)* | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | All sheets ingested; `sheet_name` stored in each fact entry |

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

Week 2 additions: `asset_tag` scoping on the request; `page_number` on each citation;
`query_intent` and `related_assets` on the response.

- **Request (`QueryRequest`):**

```json
{
  "question": "Why is Pump P-101 vibrating?",
  "top_k": 5,
  "asset_tag": "P-101"
}
```

| Field | Type | Required | Description |
| ----- | ---- | -------- | ----------- |
| `question` | string | yes | Natural-language question |
| `top_k` | integer | no (default `5`) | Max chunks to retrieve (`1`–`50`) |
| `asset_tag` | string \| null | no | Equipment tag to scope retrieval (e.g. `"P-101"`). Chunks mentioning this tag receive a similarity boost; the tag is excluded from `related_assets`. |

- **Errors:** `400` if `question` is empty.
- **Response (`QueryResponse`):**

```json
{
  "question": "Why is Pump P-101 vibrating?",
  "answer": "string",
  "confidence": "high",
  "citations": [
    {
      "document_id": "string",
      "chunk_id": "string",
      "chunk_index": 0,
      "score": 0.87,
      "text_preview": "string",
      "filename": "pump_p101_inspection.pdf",
      "page_number": 3
    }
  ],
  "retrieved_count": 3,
  "query_intent": "failure_rca",
  "related_assets": ["HX-305", "BLR-118"]
}
```

| Field | Type | Description |
| ----- | ---- | ----------- |
| `answer` | string | Extractive answer (placeholder until LLM is wired in) |
| `confidence` | `"high"` \| `"medium"` \| `"low"` | Based on top citation score |
| `citations[].page_number` | integer \| null | PDF page where the chunk was found; `null` for CSV/XLSX/TXT |
| `query_intent` | string | Detected intent: `procedure`, `failure_rca`, `maintenance_history`, `inspection`, `compliance`, or `general` |
| `related_assets` | list[string] | Other equipment tags found in the retrieved chunks (excludes `asset_tag`) |

`filename` is included on citations so the UI can show a human-readable source; it falls
back to `document_id` when absent.

### Query intent classes

| Intent | Triggered by | Source preference |
| ------ | ------------ | ----------------- |
| `procedure` | "how to", "steps", "startup", "SOP" | `sop`, `manual`, `oem`, `startup` filenames |
| `failure_rca` | "why is/was", "root cause", "fault", "vibrating" | `inspection`, `work_order`, `near_miss` filenames |
| `maintenance_history` | "history", "last maintenance", "work orders" | `work_order`, `maintenance` filenames |
| `inspection` | "inspection", "reading", "Q1–Q4", "quarterly" | `inspection`, `report` filenames |
| `compliance` | "compliance", "OISD", "PESO", "ISO", "certificate" | `compliance`, `checklist`, `certificate` filenames |
| `general` | (catch-all) | no source priority |

---

# AssetMind AI — API Contract (Week 2: Knowledge Graph)

Week 2 adds a read-only asset knowledge-graph layer over the ingested corpus. These
endpoints derive an asset → document/chunk/entity graph, a per-asset timeline, a
deterministic risk view, and a dashboard summary.

**Mode behavior:** the graph endpoints only return data when the backend runs with
`PERSISTENCE_BACKEND=postgres`. In JSON/local mode no assets or mentions are persisted,
so each endpoint returns a **safe, empty, DB-free response** carrying `"mode": "json"`
and a `message`, rather than touching a database (the two exceptions, noted below,
return `404`). Tags are matched case-insensitively.

## Endpoint summary

| Method | Path                            | Purpose                                                  |
| ------ | ------------------------------- | -------------------------------------------------------- |
| GET    | `/assets`                       | List extracted equipment assets.                         |
| GET    | `/assets/{tag}`                 | One asset by tag.                                         |
| GET    | `/assets/{tag}/mentions`        | Evidence-rich mentions of an asset.                      |
| GET    | `/assets/{tag}/documents`       | Unique documents that mention an asset.                  |
| GET    | `/assets/{tag}/timeline`        | Classified timeline events for an asset.                 |
| GET    | `/assets/{tag}/facts`           | Compact fact sheet for an asset.                         |
| GET    | `/assets/{tag}/graph`           | Derived knowledge graph for an asset.                    |
| GET    | `/assets/{tag}/graph/summary`   | Aggregate counts for an asset's graph.                   |
| GET    | `/assets/risk-summary`          | Top risky assets ranked by deterministic heuristics.     |
| GET    | `/dashboard/summary`            | Live counts plus v2 risk intelligence fields.            |

---

## GET /assets/{tag}/documents

Return the unique documents that mention an asset, newest first.

- **Mode (JSON):** `{ "tag": "P-101", "count": 0, "documents": [], "mode": "json", "message": "Asset document links are available in Postgres mode." }`
- **Response (Postgres):**

```json
{
  "tag": "P-101",
  "count": 2,
  "documents": [
    {
      "id": "string",
      "filename": "pump_p101_inspection.pdf",
      "original_filename": "pump_p101_inspection.pdf",
      "status": "processed",
      "chunk_count": 4,
      "created_at": "2026-06-24T10:00:00Z"
    }
  ]
}
```

## GET /assets/{tag}/timeline

Derive classified timeline events for an asset from its mentions, newest first.

- **Mode (JSON):** `{ "tag": "P-101", "count": 0, "events": [], "mode": "json", "message": "Asset timeline is available in Postgres mode." }`
- **Event classification:** `event_type` is one of `inspection`, `work_order`,
  `procedure`, `compliance`, `failure`, or the `evidence_mention` fallback. Each event
  also carries `severity` (`high` / `medium` / `low`) and `reason_tags` (matched
  keywords). All pre-existing fields are preserved.
- **Response (Postgres):**

```json
{
  "tag": "P-101",
  "count": 1,
  "events": [
    {
      "id": "string",
      "asset_tag": "P-101",
      "event_type": "inspection",
      "severity": "medium",
      "reason_tags": ["inspection", "vibration"],
      "title": "P-101 mentioned in pump_p101_inspection.pdf",
      "date": "2026-06-24T10:00:00Z",
      "document_id": "string",
      "filename": "pump_p101_inspection.pdf",
      "chunk_id": "string",
      "chunk_index": 0,
      "text_preview": "Vibration reading on P-101 trending high…",
      "citation": {
        "document_id": "string",
        "chunk_id": "string",
        "chunk_index": 0,
        "filename": "pump_p101_inspection.pdf"
      }
    }
  ]
}
```

## GET /assets/{tag}/facts

Return a compact fact sheet for an asset (asset, mention/document counts, supporting
documents, and distinct linked entities).

- **Errors:** `404` if the asset is unknown, **or** in JSON mode (assets are not
  persisted — mirrors `GET /assets/{tag}`).
- **Response (Postgres):**

```json
{
  "asset": { "id": "string", "tag": "P-101", "asset_type": "pump", "display_name": null },
  "mention_count": 3,
  "document_count": 2,
  "documents": [ { "id": "string", "filename": "pump_p101_inspection.pdf" } ],
  "entities": [ { "id": "string", "entity_type": "equipment_tag", "raw_value": "P-101" } ]
}
```

## GET /assets/{tag}/graph

Build a derived knowledge graph for an asset from its mentions (asset node plus
document/chunk/entity nodes, with edges from the asset to each related node).

- **Query params:**
  - `include_chunks` — boolean, default `true`. When `false`, drops chunk nodes and
    `supported_by_chunk` edges.
  - `relation_type` — optional string. Keeps only edges of that relation
    (`mentioned_in`, `supported_by_chunk`, or `has_entity`); nodes left without an
    incident edge are pruned (the asset node is always kept).
- **Errors:** `404` if the asset is unknown.
- **Mode (JSON):** `{ "asset": null, "nodes": [], "edges": [], "counts": {"nodes": 0, "edges": 0}, "mode": "json", "message": "Asset graph is available in Postgres mode." }`
- **Response (Postgres):**

```json
{
  "asset": { "id": "string", "tag": "P-101", "asset_type": "pump" },
  "nodes": [
    { "id": "asset:P-101", "type": "asset", "label": "P-101", "asset_id": "string" },
    { "id": "document:abc", "type": "document", "label": "pump_p101_inspection.pdf", "document_id": "abc" },
    { "id": "chunk:abc-0", "type": "chunk", "label": "chunk #0", "chunk_id": "abc-0", "chunk_index": 0 },
    { "id": "entity:xyz", "type": "entity", "label": "P-101", "entity_id": "xyz" }
  ],
  "edges": [
    { "id": "asset:P-101|mentioned_in|document:abc", "source": "asset:P-101", "target": "document:abc", "relation_type": "mentioned_in" },
    { "id": "asset:P-101|supported_by_chunk|chunk:abc-0", "source": "asset:P-101", "target": "chunk:abc-0", "relation_type": "supported_by_chunk" },
    { "id": "asset:P-101|has_entity|entity:xyz", "source": "asset:P-101", "target": "entity:xyz", "relation_type": "has_entity" }
  ],
  "counts": { "nodes": 4, "edges": 3 }
}
```

## GET /assets/{tag}/graph/summary

Return aggregate counts for an asset's derived graph.

- **Errors:** `404` if the asset is unknown.
- **Mode (JSON):** returns zeroed counts with `"mode": "json"` and a `message`.
- **Response (Postgres):**

```json
{
  "asset": { "id": "string", "tag": "P-101" },
  "asset_tag": "P-101",
  "document_count": 2,
  "chunk_count": 4,
  "entity_count": 1,
  "edge_count": 7,
  "relation_type_counts": { "mentioned_in": 2, "supported_by_chunk": 4, "has_entity": 1 },
  "top_documents": [ { "document_id": "string", "filename": "pump_p101_inspection.pdf", "mention_count": 3 } ]
}
```

## GET /assets/risk-summary

Return the top risky assets ranked by deterministic text heuristics over the
filename + chunk-text evidence for each asset. Sorted by `risk_score` desc,
`mention_count` desc, then `asset_tag` asc.

- **Query params:** `limit` — integer, default `10`.
- **Mode (JSON):** `{ "count": 0, "assets": [], "mode": "json", "message": "Asset risk summary is available in Postgres mode." }`
- **Risk levels:** `risk_score >= 5` → `high`, `>= 3` → `medium`, else `low`.
- **Response (Postgres):**

```json
{
  "count": 1,
  "assets": [
    {
      "asset": { "id": "string", "tag": "P-101", "asset_type": "pump" },
      "asset_tag": "P-101",
      "risk_score": 5,
      "risk_level": "high",
      "risk_reasons": [
        "Mechanical degradation symptom in evidence",
        "Open action or follow-up pending in evidence"
      ],
      "evidence": [
        {
          "document_id": "string",
          "filename": "pump_p101_inspection.pdf",
          "chunk_id": "string",
          "chunk_index": 0,
          "text_preview": "High vibration on P-101; alignment recheck pending…"
        }
      ],
      "mention_count": 3,
      "document_count": 2,
      "last_seen": "2026-06-24T10:00:00Z"
    }
  ],
  "mode": "postgres"
}
```

## GET /dashboard/summary

Return live counts over the ingested knowledge base plus v2 risk-intelligence fields.

- **Mode (JSON):** all counts `0`, empty lists, with `"mode": "json"` and a `message`.
- **Response (Postgres):**

```json
{
  "documents_indexed": 12,
  "chunks_created": 84,
  "assets_discovered": 9,
  "entities_extracted": 30,
  "asset_mentions": 41,
  "knowledge_edges": 110,
  "recent_documents": [ { "id": "string", "filename": "pump_p101_inspection.pdf" } ],
  "high_risk_assets": 1,
  "medium_risk_assets": 3,
  "low_risk_assets": 5,
  "open_compliance_gaps": 2,
  "repeated_failure_patterns": 1,
  "top_assets_by_mentions": [ { "asset_tag": "P-101", "asset_type": "pump", "mention_count": 8 } ],
  "risk_summary": [ { "asset_tag": "P-101", "risk_score": 5, "risk_level": "high" } ],
  "mode": "postgres"
}
```

The `documents_indexed`, `chunks_created`, `assets_discovered`, `entities_extracted`,
`asset_mentions`, `knowledge_edges`, and `recent_documents` fields are unchanged from
Week 1's dashboard; the remaining fields are the v2 additions.
