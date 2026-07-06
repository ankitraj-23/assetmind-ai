# AssetMind AI — RAG & KG Evaluation Suite

This document describes the automated evaluation framework for AssetMind AI's retrieval, entity extraction, and knowledge graph mapping pipelines.

## Evaluation Metrics

The suite evaluates three key dimensions:

| Metric | Target Pipeline | Mathematical Definition / Meaning |
|---|---|---|
| **Top-1 Source Hit Rate** | Document Retrieval | Percentage of questions where the rank #1 retrieved chunk belongs to the gold-standard source document. |
| **Top-3 Source Hit Rate** | Document Retrieval | Percentage of questions where the gold-standard source document is found anywhere in the top 3 retrieved chunks. |
| **Asset Hit Rate** | Query Asset Scoping | Percentage of queries where the targeted equipment tag is correctly parsed and scoped. |
| **Entity Extraction Score** | Entity Extraction | F1-Score (harmonic mean of Precision and Recall) comparing database-extracted tags against `entity_gold.json`. |
| **Graph Completeness Score**| Knowledge Graph | Percentage of gold-standard connections successfully materialized in the `knowledge_edges` table. |
| **Average Latency** | General Performance | Average time (ms) taken to embed a question and retrieve top-k chunks. |

---

## Benchmark Question Set

Located at `data/benchmark/questions.json`, this dataset contains **40 curated industrial questions** across these categories:
* `equipment_spec`
* `spare_parts`
* `failure_mode`
* `procedure`
* `inspection_finding`
* `compliance_gap`
* `regulatory`
* `maintenance_history`
* `asset_timeline`
* `knowledge_graph_relationship`
* `multi-document reasoning`
* `citation_accuracy`

---

## Evaluation Scripts

Three Python scripts are provided under `apps/api/scripts/` to run these benchmarks locally. Ensure your virtual environment is active and variables are set:

```bash
cd apps/api
export PERSISTENCE_BACKEND=postgres
export DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind
```

### 1. Run RAG Retrieval Benchmark
Runs all 40 questions against the active vector index and updates the RAG dashboard output:
```bash
.venv/bin/python -m scripts.run_benchmark
```
* **Output:** Updates `data/benchmark/results_sample.json`.

### 2. Evaluate Entity Extraction (F1 Score)
Evaluates tags inside the database against `data/benchmark/entity_gold.json`:
```bash
.venv/bin/python -m scripts.evaluate_entities
```

### 3. Evaluate Knowledge Graph Materialization
Evaluates materialized edges inside the database against `data/benchmark/graph_gold.json`:
```bash
.venv/bin/python -m scripts.evaluate_graph
```
