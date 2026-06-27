"""Run source-hit evaluation for the Week 1 RAG benchmark questions."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from app.core.config import settings
from app.rag.answer import answer_question
from app.rag.embeddings import MissingGeminiApiKeyError
from app.rag.retrieval import retrieve_relevant_chunks
from app.rag.storage import repo_root

DEFAULT_REQUEST_DELAY_SECONDS = 0.0
DEFAULT_RETRY_DELAY_SECONDS = 60.0


def _load_questions(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Benchmark questions file must contain a JSON list.")
    return data


def _source_hit(expected: str | None, cited_docs: set[str]) -> bool:
    if not expected:
        return False
    expected_lower = expected.lower()
    return any(expected_lower == doc.lower() for doc in cited_docs)


def _is_quota_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 429 or "RESOURCE_EXHAUSTED" in str(exc)


def _answer_with_retry(question: str, top_k: int, retry_delay: float):
    try:
        return answer_question(question, top_k=top_k)
    except MissingGeminiApiKeyError:
        raise
    except Exception as exc:
        if not _is_quota_error(exc):
            raise
        print(
            f"  quota_wait      : {retry_delay:.0f}s before retry",
            flush=True,
        )
        time.sleep(retry_delay)
        return answer_question(question, top_k=top_k)


def _retrieval_confidence(top_score: float, retrieved_count: int) -> float:
    coverage_bonus = min(retrieved_count, 5) * 0.03
    return round(min(1.0, max(0.0, top_score) + coverage_bonus), 2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        default="data/benchmark/questions.json",
        help="Benchmark questions JSON file.",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--generate-answers",
        action="store_true",
        help="Call Gemini generation for each benchmark question. By default "
        "the script runs source-hit retrieval evaluation only.",
    )
    parser.add_argument(
        "--request-delay",
        type=float,
        default=DEFAULT_REQUEST_DELAY_SECONDS,
        help="Seconds to wait between benchmark questions to avoid Gemini RPM limits.",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=DEFAULT_RETRY_DELAY_SECONDS,
        help="Seconds to wait before retrying once after a Gemini quota error.",
    )
    args = parser.parse_args()

    settings.persistence_backend = "postgres"
    questions_path = Path(args.questions)
    if not questions_path.is_absolute():
        questions_path = repo_root() / questions_path

    questions = _load_questions(questions_path)
    total = len(questions)
    source_hits = 0
    latencies: list[float] = []
    confidences: list[float] = []

    for index, item in enumerate(questions, start=1):
        if index > 1 and args.request_delay > 0:
            time.sleep(args.request_delay)

        question = item.get("question", "")
        expected_source = item.get("source_doc")
        print(f"{item.get('id', '?')}: {question}", flush=True)
        started = time.perf_counter()
        if args.generate_answers:
            try:
                response = _answer_with_retry(
                    question,
                    top_k=args.top_k,
                    retry_delay=args.retry_delay,
                )
            except MissingGeminiApiKeyError as exc:
                print(f"Gemini API key missing: {exc}", file=sys.stderr)
                return 2
            cited_docs = {citation.file_name for citation in response.citations}
            retrieved = response.retrieved_chunks
            confidence = response.confidence
        else:
            try:
                retrieved = retrieve_relevant_chunks(question, top_k=args.top_k)
            except MissingGeminiApiKeyError as exc:
                print(f"Gemini API key missing: {exc}", file=sys.stderr)
                return 2
            cited_docs = set()
            confidence = _retrieval_confidence(
                retrieved[0].score if retrieved else 0.0,
                len(retrieved),
            )
        latency = time.perf_counter() - started
        latencies.append(latency)
        confidences.append(confidence)

        retrieved_docs = {chunk.file_name for chunk in retrieved}
        hit = _source_hit(expected_source, cited_docs | retrieved_docs)
        source_hits += int(hit)
        top_cited_doc = next(iter(cited_docs), None)
        if top_cited_doc is None and retrieved:
            top_cited_doc = retrieved[0].file_name

        print(f"  expected_source : {expected_source or 'n/a'}")
        print(f"  top_cited_doc   : {top_cited_doc or 'none'}")
        print(f"  source_hit      : {hit}")
        print(f"  confidence      : {confidence:.2f}")
        print(f"  latency_seconds : {latency:.3f}", flush=True)

    avg_latency = sum(latencies) / total if total else 0.0
    avg_confidence = sum(confidences) / total if total else 0.0
    hit_rate = source_hits / total if total else 0.0

    print("")
    print("Summary")
    print(f"  total_questions    : {total}")
    print(f"  source_hit_count   : {source_hits}")
    print(f"  source_hit_rate    : {hit_rate:.2%}")
    print(f"  average_latency    : {avg_latency:.3f}s")
    print(f"  average_confidence : {avg_confidence:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
