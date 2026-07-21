"""Read-only evaluation route.

``GET /evaluation/latest`` serves the *latest genuine benchmark result* written
by ``scripts.run_benchmark`` (``data/benchmark/results_sample.json``). It runs no
retrieval and fabricates no numbers — it only parses and returns the persisted
report so the Evaluation page can show live, honest metrics with provenance.

There is intentionally no "run benchmark" endpoint: executing the full retrieval
benchmark on request would be a denial-of-service and deployment risk. The
benchmark is run offline via ``python -m scripts.run_benchmark``.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import settings

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

# apps/api/app/routes/evaluation.py -> repo root is parents[4].
_DEFAULT_RESULTS_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "benchmark" / "results_sample.json"
)


def _results_path() -> Path:
    if settings.benchmark_results_path:
        return Path(settings.benchmark_results_path)
    return _DEFAULT_RESULTS_PATH


@router.get(
    "/latest",
    summary="Latest genuine benchmark result",
    description=(
        "Returns the most recent benchmark report produced by "
        "`scripts.run_benchmark`: summary metrics (all questions and the "
        "answerable-corpus subset), failure-category breakdown and per-question "
        "results with expected source and actual citations. Read-only."
    ),
)
def get_latest_evaluation() -> dict:
    path = _results_path()
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "No benchmark results available. Run "
                "`python -m scripts.run_benchmark` to generate them."
            ),
        )
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to read benchmark results: {exc}"
        ) from exc

    summary = report.get("summary")
    results = report.get("results")
    if not isinstance(summary, dict) or not isinstance(results, list):
        raise HTTPException(
            status_code=500,
            detail="Benchmark results file is malformed (missing summary/results).",
        )

    return {
        "available": True,
        "source_file": path.name,
        "summary": summary,
        "results": results,
    }
