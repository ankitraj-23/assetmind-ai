"""Execute the RAG benchmark against the live document index.

Uses the *same* production retrieval, embedding-provider and citation logic as
the ``/rag/chat`` endpoint (``app.rag.answer.answer_question`` +
``app.rag.chat._apply_asset_scope``). No separate query architecture is created
and no metrics are fabricated — every hit is derived from real retrieved
citations against the currently seeded database.

Usage:
------
    PERSISTENCE_BACKEND=postgres \
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind \
    .venv/bin/python -m scripts.run_benchmark
"""

from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core import config
from app.db.session import get_database_url

# The benchmark is only meaningful against the persistent Postgres index.
config.settings.persistence_backend = "postgres"


def _ranked_docs(citations) -> list[str]:
    """Ranked, de-duplicated list of source filenames from citations."""
    ranked: list[str] = []
    for citation in citations:
        name = citation.file_name
        if name and name not in ranked:
            ranked.append(name)
    return ranked


def _asset_in_evidence(asset_tag: str | None, retrieved_chunks) -> bool:
    """True when the target asset is present in retrieved evidence.

    Checks structured ``asset_tags`` first, then falls back to a whole-word
    match against the chunk content (same semantics as
    ``app.services.search._mentions_tag``). This keeps the metric truthful even
    when the index did not persist structured tags for a chunk.
    """
    if not asset_tag:
        return False
    target = asset_tag.strip().upper()
    pattern = re.compile(rf"\b{re.escape(target)}\b", re.I)
    for chunk in retrieved_chunks:
        if any(target == tag.strip().upper() for tag in chunk.asset_tags):
            return True
        if chunk.content and pattern.search(chunk.content):
            return True
    return False


def main() -> int:
    try:
        get_database_url()
    except Exception as exc:  # pragma: no cover - config guard
        print(f"Database error: {exc}")
        print("Set DATABASE_URL and PERSISTENCE_BACKEND=postgres before running.")
        return 1

    # Imported lazily so the config guard above runs first.
    from app.rag import answer as answer_service
    from app.rag import embeddings
    from app.rag.chat import _apply_asset_scope, _normalize_asset_tag

    root = Path(__file__).resolve().parents[3]
    questions_path = root / "data" / "benchmark" / "questions.json"
    results_path = root / "data" / "benchmark" / "results_sample.json"

    if not questions_path.exists():
        print(f"ERROR: Benchmark questions not found at {questions_path}")
        return 1

    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    provider = embeddings.active_provider()
    model = embeddings.active_model()

    results = []
    total_latency_ms = 0.0
    top1_hits = 0
    top3_hits = 0
    asset_hits = 0
    asset_total = 0
    failures = 0

    print(
        f"Running benchmark on {len(questions)} questions "
        f"(provider={provider}, model={model})..."
    )

    for q in questions:
        asset_tag = _normalize_asset_tag(q.get("asset_tag"))
        scoped_question = _apply_asset_scope(q["question"], asset_tag)

        start_time = time.perf_counter()
        try:
            response = answer_service.answer_question(scoped_question, top_k=5)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            total_latency_ms += duration_ms
            failures += 1
            print(f"  [{q['id']}] ERROR: {exc}")
            results.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "category": q.get("category", ""),
                    "asset_tag": q.get("asset_tag"),
                    "expected_doc": q["source_doc"],
                    "retrieved_docs": [],
                    "citations": [],
                    "top1_hit": False,
                    "top3_hit": False,
                    "asset_hit": False,
                    "latency_ms": int(duration_ms),
                    "status": "error",
                    "error": str(exc),
                    "actual_answer": "",
                }
            )
            continue

        duration_ms = (time.perf_counter() - start_time) * 1000
        total_latency_ms += duration_ms

        ranked_docs = _ranked_docs(response.citations)
        top1_hit = bool(ranked_docs) and ranked_docs[0] == q["source_doc"]
        top3_hit = q["source_doc"] in ranked_docs[:3]
        asset_hit = _asset_in_evidence(asset_tag, response.retrieved_chunks)

        if asset_tag:
            asset_total += 1
            if asset_hit:
                asset_hits += 1
        if top1_hit:
            top1_hits += 1
        if top3_hit:
            top3_hits += 1

        status = "passed" if top3_hit else "failed"
        if not top3_hit:
            failures += 1

        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "category": q.get("category", ""),
                "asset_tag": q.get("asset_tag"),
                "expected_doc": q["source_doc"],
                "retrieved_docs": ranked_docs,
                "citations": [
                    {
                        "file_name": c.file_name,
                        "page": c.page,
                        "chunk_id": c.chunk_id,
                        "snippet": (c.snippet or "")[:160],
                    }
                    for c in response.citations
                ],
                "top1_hit": top1_hit,
                "top3_hit": top3_hit,
                "asset_hit": asset_hit,
                "latency_ms": int(duration_ms),
                "status": status,
                "actual_answer": response.answer,
            }
        )
        print(
            f"  [{q['id']}] top1={'Y' if top1_hit else 'N'} "
            f"top3={'Y' if top3_hit else 'N'} asset={'Y' if asset_hit else 'N'} "
            f"| {int(duration_ms)}ms | {status}"
        )

    n = len(questions)
    summary = {
        "total_questions": n,
        "top1_source_hit_rate": round(top1_hits / n, 4) if n else 0.0,
        "top3_source_hit_rate": round(top3_hits / n, 4) if n else 0.0,
        "asset_hit_rate": round(asset_hits / asset_total, 4) if asset_total else 0.0,
        "asset_questions": asset_total,
        "average_latency_ms": round(total_latency_ms / n, 1) if n else 0.0,
        "failed_questions_count": failures,
        "embedding_provider": provider,
        "embedding_model": model,
        "last_run_time": datetime.now(timezone.utc).isoformat(),
    }

    report = {"summary": summary, "results": results}

    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\nBenchmark Run Complete:")
    print(f"  Total Questions   : {summary['total_questions']}")
    print(f"  Top-1 Hit Rate    : {summary['top1_source_hit_rate']*100:.1f}%")
    print(f"  Top-3 Hit Rate    : {summary['top3_source_hit_rate']*100:.1f}%")
    print(
        f"  Asset Hit Rate    : {summary['asset_hit_rate']*100:.1f}% "
        f"({asset_hits}/{asset_total})"
    )
    print(f"  Avg Latency       : {summary['average_latency_ms']:.1f}ms")
    print(f"  Failed Questions  : {summary['failed_questions_count']}")
    print(f"  Provider / Model  : {provider} / {model}")
    print(f"  Results written   : {results_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
