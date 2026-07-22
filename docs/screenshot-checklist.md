# AssetMind AI — Screenshot Checklist

Capture these for the deck and as offline demo fallbacks. Prefer the **local
server on the current code** (14/14 smoke pass) over the public site until the
Render redeploy lands, so the retrieval/failure-intelligence features show.

## Capture environment

- [ ] Clean browser window, no bookmarks bar, no extensions visible
- [ ] Desktop notifications silenced
- [ ] Zoom 100–110%, 1440–1600px wide, light theme (or one consistent theme)
- [ ] No terminal, tokens, or connection strings visible in any frame
- [ ] P-101 preselected where the flow allows

## Shots to take

| # | Page / view | What must be visible |
|---|-------------|----------------------|
| 1 | Dashboard (`/`) | 8 docs · 497 chunks · 60 assets · 2688 edges; risk summary |
| 2 | Upload (`/upload`) | Drag-drop + a completed ingestion with per-format counts |
| 3 | Assets list (`/assets`) | Asset registry with risk badges |
| 4 | Asset P-101 → Overview | Asset header, type, risk, key facts |
| 5 | Asset P-101 → Timeline | Classified events with source-document links |
| 6 | Asset P-101 → **Failure Intelligence** | Failure-mode badges + counts, recent events with citations, coverage confidence, disclaimer |
| 7 | Asset P-101 → Knowledge Graph | Graph nodes/edges, a selected node's evidence |
| 8 | Copilot (`/copilot`) | A P-101 question with a grounded answer + numbered citations |
| 9 | RCA (`/rca`) | Likely causes, confidence, recommended actions, missing info, citations |
| 10 | Compliance (`/compliance`) | Gaps with severity, explanation, source evidence |
| 11 | Evidence package | Generated package + the downloaded Markdown (open it) |
| 12 | Evaluation (`/evaluation`) | Live timestamp, corpus size, provider/model, Top-1/Top-3/asset, failure categories |
| 13 | Failure hotspots | `/dashboard/failure-hotspots` ranked assets (or dashboard widget) |

## After capturing

- [ ] File names describe the shot (e.g. `06-p101-failure-intelligence.png`)
- [ ] Numbers on screen match the published benchmark (Top-1 40% / Top-3 72.5% / asset 87.5%)
- [ ] Store copies with the deck as the offline fallback set
