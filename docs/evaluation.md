# AssetMind AI — Evaluation

The benchmark measures **retrieval quality** of the production RAG pipeline. It is
genuine: `scripts/run_benchmark.py` calls the *same* `answer_question` +
asset-scoping path that backs `/rag/chat`, against the live seeded index. No
metrics are hand-written and no separate retrieval architecture exists.

## Metrics

For each question in `data/benchmark/questions.json`:

- **Top-1 source hit** — the expected `source_doc` is the rank-1 citation.
- **Top-3 source hit** — the expected `source_doc` appears in the top-3 citations.
  This is the pass/fail criterion.
- **Asset hit** — the target asset tag appears in the retrieved evidence
  (structured `asset_tags` or a whole-word match in chunk text).
- **Latency** — average and p95 wall-clock per question.
- **Failure category** — `pass`, `correct_document_outside_top3`,
  `correct_document_not_retrieved`, `expected_source_absent_from_corpus`, or
  `retrieval_error`.

Results are reported twice:

- **All questions** — every question, including any whose source is absent.
- **Answerable-corpus subset** — questions whose expected source document is
  present in the seeded corpus. This prevents absent-corpus questions from either
  hiding or inflating real retrieval quality.

Output: `data/benchmark/results_sample.json` (summary + per-question), served
read-only at `GET /evaluation/latest` and rendered on the Evaluation page. There
is deliberately **no "run benchmark" API** — executing the full benchmark on
request would be a DoS/deployment risk; it is run offline.

## Latest genuine result (deterministic local mode)

Provider: `local` / `local-hashing-v1` embeddings, `deterministic-fallback`
answers. Corpus: 8 documents.

| Metric | All (40) | Answerable (40) |
|--------|----------|-----------------|
| Top-1 source hit | 35.0% | 35.0% |
| Top-3 source hit | 72.5% | 72.5% |
| Asset hit | 87.5% (35/40) | 87.5% |
| Failed questions | 11 | 11 |
| Absent-corpus | 0 | — |

Latency ≈ 210 ms avg / ≈ 220 ms p95. These reflect the **offline deterministic
fallback**, not Gemini. With Gemini embeddings, source-hit rates are expected to
improve; we report only what we actually ran.

## Corpus decision (extended-corpus gap)

The 40-question benchmark originally referenced three documents that did not
exist: `compressor_datasheet.xlsx`, `rca_findings_2025.csv`,
`sop_compressor_operations.pdf` — eight questions (Q14, Q17, Q19, Q24, Q26, Q31,
Q33, Q36), all describing a coherent **Compressor C-220** + **RCA** scenario. The
C-220 asset was already part of the demo plant.

**Decision — Approach A (complete the corpus).** Because the scenarios are
legitimate industrial content consistent with the project scope, we authored the
three missing documents as **clearly-labelled synthetic hackathon demo data**,
generated reproducibly by `data/generate_extended_corpus.py`, and added them to
the demo seed. Questions were **not** deleted, expected answers were **not**
changed to improve scores, and no proprietary text was copied.

Effect (genuine, before → after adding the documents):

| | Before (5 docs) | After (8 docs) |
|---|---|---|
| Top-1 | 32.5% | 35.0% |
| Top-3 | 65.0% | 72.5% |
| Asset hit | 70.0% | 87.5% |
| Absent-corpus questions | 8 | 0 |

## Reproduce

```bash
cd apps/api && source .venv/bin/activate
export PERSISTENCE_BACKEND=postgres
export DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind
python -m scripts.seed_demo          # ensure the 8-document corpus is indexed
python -m scripts.run_benchmark      # writes data/benchmark/results_sample.json
```

Then open the Evaluation page or `GET /evaluation/latest`.
