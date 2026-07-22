# AssetMind AI — Pitch Deck Outline (10 slides)

Each slide: title · 3–5 key points · recommended visual · speaker note. Keep every
claim consistent with the demo and the genuine benchmark.

---

## 1. The industrial knowledge problem
- Asset knowledge is scattered across PDFs, spreadsheets, SOPs and work orders.
- Answering "why does this pump keep failing?" means manually cross-reading many
  documents.
- Tribal knowledge walks out the door; audits are slow and painful.
- Existing search returns documents, not answers — and no provenance.
- **Visual:** messy pile of document icons → one question mark over an asset.
- **Speaker note:** Anchor in a concrete pain: a recurring P-101 failure buried
  across five document types.

## 2. The AssetMind solution
- An **asset-centric operations brain**: documents in, cited answers out.
- Copilot, RCA, compliance and evidence packages — all grounded in sources.
- Runs fully offline (deterministic) or on Gemini with one key.
- **Visual:** before/after — document pile vs. a clean asset page with citations.
- **Speaker note:** Emphasise *citation-backed*; every answer is auditable.

## 3. User workflow
- Upload or seed → assets & knowledge graph built automatically.
- Open an asset → timeline, facts, graph.
- Ask Copilot → cited answer → RCA → compliance → downloadable evidence package.
- **Visual:** 5-step horizontal flow with the P-101 example.
- **Speaker note:** One continuous flow from raw document to audit-ready output.

## 4. Architecture
- Next.js → FastAPI → canonical ingestion → Postgres + pgvector → hybrid retrieval.
- One embedding contract: uploads use the same model as queries.
- Deterministic-local and Gemini modes, no code change to switch.
- **Visual:** the Mermaid diagram from `docs/architecture.md`.
- **Speaker note:** Call out the single embedding contract as the reliability key.

## 5. Canonical ingestion & knowledge graph
- One pipeline for PDF / TXT / CSV / XLSX; tabular rows become row-chunks.
- Equipment-tag extraction → assets, entities, mentions, `asset→doc/chunk/entity` edges.
- Postgres + pgvector; migrations via Alembic; idempotent seed.
- **Failure intelligence** derived from this graph: per-asset failure modes +
  hotspots ranking, every item citation-backed (retrospective, not predictive).
- **Visual:** a document decomposing into graph nodes for P-101 + a failure-mode panel.
- **Speaker note:** The graph is what makes answers asset-scoped and traceable.

## 6. Copilot, RCA & compliance
- Hybrid retrieval (vector + keyword, RRF → rerank → MMR) with filename citations.
- RCA: ranked likely causes, each with confidence + evidence.
- Compliance: deterministic gaps tied to standards and evidence snippets.
- **Visual:** three side-by-side cards — cited answer, RCA causes, compliance gap.
- **Speaker note:** Position as *recommendation intelligence*, not prediction.

## 7. Evidence package
- One click compiles a real, cited Markdown package (gaps + inspection + maintenance).
- Working download; deterministic from persisted evidence.
- Honest limitation: exports are ephemeral on containers (regenerated on demand).
- **Visual:** screenshot of the generated Markdown package.
- **Speaker note:** Audit-ready output is the "so what" for plant managers.

## 8. Evaluation & benchmark
- Genuine benchmark: same retrieval path as Copilot, no fabricated numbers.
- 40 questions, 8-document corpus: **Top-3 72.5%, asset hit 87.5%, 0 absent-corpus**.
- Live at `/evaluation/latest`; shows all-vs-answerable and a failure breakdown.
- Deterministic-local-mode numbers — honest about the fallback.
- **Visual:** the live Evaluation page with the metric tiles.
- **Speaker note:** Show we measure honestly, including the misses.

## 9. Business impact
- Minutes, not hours, to answer "why is this asset failing?" — with provenance.
- Faster audits; retained tribal knowledge; fewer repeat failures via clear RCA.
- Every answer carries an audit trail (which document, which page).
- **Visual:** simple before/after time + a "traceable to source" badge.
- **Speaker note:** Tie savings to the recurring-failure and audit use cases only.

## 10. Scalability, roadmap & close
- Scales via hosted pgvector Postgres; stateless containerised API.
- Roadmap: Gemini mode by default, durable evidence storage, more asset types,
  richer graph reasoning.
- Close: "Scattered documents → one cited operations brain — live now, offline or
  on Gemini."
- **Visual:** deployment topology (Vercel + Render/Fly + Neon) → roadmap arrows.
- **Speaker note:** End on the demo invitation; avoid over-claiming certification
  or predictive maintenance.
