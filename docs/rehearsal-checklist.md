# AssetMind AI — Rehearsal Checklist

Target total: **5–7 minutes**. Rehearse twice: once on the intended environment,
once on the offline/local fallback. All numbers quoted must match the latest
genuine benchmark — never round up.

## Timing plan (per section)

| Section | Target | Notes |
|---------|--------|-------|
| Problem & positioning | 0:40 | Industrial knowledge is scattered across PDFs/CSVs/XLSX |
| Dashboard | 0:30 | Live counts, risk view |
| Upload / ingestion | 0:40 | Show a format ingest + counts returned |
| P-101 asset view | 0:30 | Facts, risk |
| Timeline / facts / graph | 0:45 | Evidence-linked events + knowledge graph |
| Copilot with citations | 0:45 | Grounded answer, numbered sources |
| RCA | 0:40 | Causes + confidence + missing info |
| Compliance + evidence package | 0:45 | Gaps with evidence → download package |
| Failure intelligence | 0:30 | Failure modes + coverage, evidence-backed |
| Evaluation | 0:30 | Live metrics + failure categories |
| Architecture & impact / close | 0:40 | One diagram, honest scope |

## Pre-run gate

- [ ] Warm the backend (`GET /health`) to defeat Render cold start (~30–60 s)
- [ ] Local fallback server ready on the current code (14/14 smoke pass)
- [ ] Screenshot fallback set open in a second window
- [ ] P-101 preselected; evidence-package download path tested once live
- [ ] No secrets/terminals in shared screen

## Exact verified numbers to quote

- Corpus: **8 documents · 497 chunks · 60 assets · 896 mentions · 2688 edges**
- Benchmark (local deterministic): **Top-1 40.0% · Top-3 72.5% · asset-hit 87.5%**,
  40/40 answerable, absent-corpus 0
- Tests: **62 passing**; local end-to-end smoke: **14/14**

## Failure fallbacks

- **Public API cold/stale** → switch to the local server on the current code.
- **`/rag/chat` empty on public** → known deployment lag; use local or screenshots.
- **Network down** → drive entirely from the screenshot set; narrate the flow.
- **Evidence download blocked** → open a pre-downloaded package Markdown.

## Claims that must NOT be made (hard stops)

- [ ] No real plant / customer validation — data is **synthetic demo**.
- [ ] No predictive maintenance or failure forecasting — it's **retrospective**.
- [ ] No regulatory/legal certification.
- [ ] No Gemini-mode performance claims — the shown benchmark is **local mode**.
- [ ] No metric higher than the genuine benchmark above.

## Human-only remaining actions

- [ ] Record the actual demo video (cannot be automated).
- [ ] Final dry-run in front of a second person for timing.
