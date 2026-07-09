# Week 2 — Asset Knowledge Graph

This document explains the read-only asset knowledge-graph layer added in Week 2: the
graph model, how the derived graph relates to materialized edges, the timeline
classification, the deterministic risk scoring, the dashboard v2 fields, and the known
limitations of this branch.

All of this requires `PERSISTENCE_BACKEND=postgres` and a `DATABASE_URL`. In JSON/local
mode the corresponding endpoints return safe, empty responses (see
[api-contract.md](api-contract.md), Week 2 section).

## Asset graph model

For each asset (an equipment tag such as `P-101`), the graph connects the asset to the
evidence that mentions it. Three relation types are derived from `asset_mentions`:

| Relation             | From → To          | Meaning                                            |
| -------------------- | ------------------ | -------------------------------------------------- |
| `mentioned_in`       | asset → document   | The asset is mentioned in this document.           |
| `supported_by_chunk` | asset → chunk      | The mention is supported by this specific chunk.   |
| `has_entity`         | asset → entity     | The asset is linked to this extracted entity.      |

Node IDs are stable and namespaced: `asset:<tag>`, `document:<id>`, `chunk:<id>`,
`entity:<id>`.

## Derived graph vs. materialized `KnowledgeEdge` rows

There are two representations of the same relationships:

- **Derived graph** — `get_asset_graph_by_tag` / `get_asset_graph_summary_by_tag`
  compute the graph **on the fly** from `asset_mentions` (joined to documents, chunks,
  and entities). This is always correct regardless of edge state and powers the graph
  endpoints. The graph supports `include_chunks=false` (drop chunk nodes/edges) and a
  `relation_type` filter.
- **Materialized `KnowledgeEdge` rows** — `create_asset_mention` also writes idempotent
  `knowledge_edges` rows for the same three relations via `upsert_knowledge_edge`. These
  give a queryable, persisted edge table (counted in the dashboard's `knowledge_edges`
  and read by `list_edges_for_asset`) without recomputing from mentions.

### Why `backfill_knowledge_edges.py` exists

Asset mentions created **before** `create_asset_mention` started materializing edges
have no corresponding `knowledge_edges` rows. The backfill script scans every existing
`asset_mentions` row and idempotently creates the same edges the live path now creates.
It is safe to run repeatedly: `upsert_knowledge_edge` only inserts an edge when an
equivalent one is absent, so reruns create nothing new. It never deletes or mutates
existing rows. The derived graph endpoints do not depend on this backfill — it only
keeps the materialized edge table and its counts in sync.

## Timeline classification

`list_asset_timeline_by_tag` turns each document-backed mention into a timeline event,
newest first. Beyond the original fields, each event now carries a classified
`event_type`, a `severity`, and `reason_tags` (the matched keywords). Classification is
a case-insensitive substring match over the filename + chunk text.

`event_type` is the **first** matching category (else `evidence_mention`):

| `event_type`       | Keywords                                                            |
| ------------------ | ------------------------------------------------------------------- |
| `inspection`       | inspection, vibration reading, reading, calibration, test           |
| `work_order`       | work order, maintenance, repair, replaced, action taken             |
| `procedure`        | sop, procedure, startup, shutdown, checklist                        |
| `compliance`       | compliance, audit, certificate, oisd, factory act, peso, iso        |
| `failure`          | failure, vibration, leakage, overheating, cavitation, alarm, abnormal |
| `evidence_mention` | (fallback when nothing matches)                                     |

`severity` is the first matching band:

- **high** — high priority, alarm, exceeds, overdue, expired, abnormal, shutdown
- **medium** — vibration, leakage, follow-up, recheck, pending, inspection
- **low** — otherwise

All pre-existing timeline fields are preserved for frontend compatibility.

## Risk scoring rules

`get_asset_risk_summary(limit=10)` scores every mentioned asset deterministically over
its combined filename + chunk-text evidence (case-insensitive substring matches).
Reasons are deduplicated per asset and evidence is capped at the three most recent
chunk-backed snippets.

| Points | Triggers                                                                                  | Reason                                          |
| ------ | ----------------------------------------------------------------------------------------- | ----------------------------------------------- |
| +2     | repeated failure, repeated issue, recurring, repeatedly                                   | Repeated or recurring failure pattern           |
| +2     | overdue, expired, compliance gap, missing certificate, not recorded                       | Overdue item or compliance gap                  |
| +1     | high vibration, leakage, overheating, cavitation, corrosion, bearing wear, misalignment, fouling | Mechanical degradation symptom            |
| +1     | abnormal, alarm, exceeds, threshold, high priority                                        | Abnormal reading or alarm                       |
| +1     | open action, recheck, follow-up, pending, not closed                                      | Open action or follow-up pending                |

**Risk level** from the total score: `>= 5` → `high`, `>= 3` → `medium`, else `low`.
Assets are sorted by `risk_score` desc, `mention_count` desc, then `asset_tag` asc, and
the top `limit` are returned.

## Dashboard v2 fields

`get_dashboard_summary` keeps all Week 1 fields (`documents_indexed`, `chunks_created`,
`assets_discovered`, `entities_extracted`, `asset_mentions`, `knowledge_edges`,
`recent_documents`) and adds:

- `high_risk_assets` / `medium_risk_assets` / `low_risk_assets` — counts by risk level.
- `open_compliance_gaps` — estimated from the risk heuristics (assets flagged with an
  overdue/compliance-gap reason).
- `repeated_failure_patterns` — estimated from the risk heuristics (assets flagged with
  a repeated/recurring-failure reason).
- `top_assets_by_mentions` — top 5 assets by mention count.
- `risk_summary` — the top 5 risky assets (same shape as `/assets/risk-summary`).

## Known limitations

- **Deterministic heuristic risk scoring.** Risk scores, timeline classification, and
  the estimated compliance/failure counts are keyword/substring heuristics — they are
  explainable and reproducible, but not a learned or semantic model.
- **No Neo4j.** The graph is derived from relational tables (`asset_mentions`,
  `knowledge_edges`) and computed on the fly; there is no dedicated graph database.
- **No LLM dependency.** Nothing in this layer calls an external model or API key.
- **No schema change in this branch.** No new tables, columns, or migrations were added
  for Week 2; the layer reuses the existing models.
- **Quality depends on ingestion.** Graph completeness and risk/timeline accuracy are
  bounded by the upstream document ingestion and entity/equipment-tag extraction — if a
  mention was not extracted, it cannot appear in the graph.
