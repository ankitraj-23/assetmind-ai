# AssetMind AI — Judge Demo Script (5–7 minutes)

Deliver in **deterministic local mode**. Keep to the timings. Every claim below is
backed by something visible on screen — do not overstate.

**Honesty guardrails (do not say):** predictive maintenance (we do recommendation
intelligence, not failure prediction); regulatory certification; real customer
validation; live Gemini performance while running the local fallback; or any
score higher than the benchmark shows.

---

### 1. Problem & positioning — 20–30s
> "Industrial teams drown in PDFs, spreadsheets and work orders. When a pump keeps
> failing, the answer is buried across a manual, an inspection report and 60 work
> orders. **AssetMind AI turns those scattered documents into one asset-centric,
> citation-backed operations brain.**"

*On screen:* landing / dashboard.

### 2. Dashboard — 30s
Show live counts: documents indexed, assets discovered, mentions, knowledge edges,
and the risk breakdown.
> "These numbers are live from Postgres — 8 documents, a real knowledge graph,
> risk computed from the evidence, not hard-coded."

### 3. Upload / seed overview — 30s
> "One canonical ingestion pipeline handles PDF, text, CSV and Excel. Uploading a
> document through the UI uses the exact same code and the same embedding contract
> as our demo seed — so anything you upload is immediately answerable by Copilot."

*On screen:* Upload page (optionally drop a file), then Documents list.

### 4. Open P-101 — 45s
Open **Assets → P-101**.
> "P-101 is our problem pump. Here's everything the system knows about it, pulled
> from every document that mentions it — the OEM manual, the SOP, inspection
> report, compliance checklist and work orders."

### 5. Timeline, facts & graph — 45s
Show the P-101 **timeline**, **facts**, and **graph**.
> "A chronological timeline of events, extracted facts, and a knowledge graph
> linking the asset to its documents, chunks and entities — every node traceable
> back to a source."

### 6. Copilot — "Why is P-101 repeatedly failing?" — 60s
Ask it on the **Copilot** page.
> "The answer is grounded — every claim carries a citation to a specific file and
> page. It's pulling the vibration exceedance from the inspection report and the
> repair history from the work orders. Note: we're in deterministic local mode
> right now — extractive answers, no LLM call — and it's still grounded."

### 7. Generate RCA — 60s
Open **RCA**, run for P-101.
> "The RCA agent proposes likely causes — each with a confidence and the evidence
> snippets behind it. This is **recommendation intelligence**: it explains and
> ranks causes from the documents; it does not predict future failures."

### 8. Compliance findings — 45s
Open **Compliance** for P-101.
> "Deterministic compliance gaps — here the vibration reading exceeds the
> OISD-137 limit — each gap tied to a real evidence snippet and the standard it
> references."

### 9. Evidence package — 40s
Generate and **download** the package.
> "One click compiles a real Markdown evidence package — compliance gaps,
> inspection and maintenance evidence, all cited — and downloads it. (In a
> containerised deployment these exports are ephemeral by design; the package is
> regenerated on demand.)"

### 10. Genuine evaluation — 45s
Open **Evaluation**.
> "We benchmark honestly. This page is live from `/evaluation/latest`, running the
> *same* retrieval pipeline as Copilot. Over 40 questions on the 8-document corpus:
> **Top-3 source hit 72.5%, asset hit 87.5%**, zero absent-corpus questions. We
> show both all-questions and the answerable subset, plus a failure breakdown — we
> don't hide the misses. These are deterministic-local-mode numbers, not Gemini."

### 11. Architecture & business impact — 30s
> "Next.js → FastAPI → canonical ingestion → Postgres + pgvector knowledge graph →
> hybrid retrieval → Copilot, RCA, compliance and evidence packages. The impact:
> minutes instead of hours to answer 'why is this asset failing?', with an audit
> trail behind every answer. And it runs fully offline, or on Gemini with one key."

---

**Total: ~6 minutes.** Buffer: skip step 5's graph if short on time.
