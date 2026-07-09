"""Ingest the Week 1 dataset into Postgres/pgvector using Gemini embeddings."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import settings
from app.rag.embeddings import MissingGeminiApiKeyError
from app.rag.storage import ingest_dataset


def _progress(message: str) -> None:
    print(f"[rag-ingest] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="data/documents", help="Dataset directory.")
    parser.add_argument(
        "--force-reingest",
        action="store_true",
        help="Delete and recreate existing dataset documents.",
    )
    parser.add_argument(
        "--parent-summaries",
        default=None,
        help="JSONL file of externally generated parent summaries to embed.",
    )
    parser.add_argument(
        "--max-parent-chunks",
        type=int,
        default=None,
        help="Smoke-test limit: ingest at most this many parent chunks.",
    )
    args = parser.parse_args()

    settings.persistence_backend = "postgres"
    try:
        result = ingest_dataset(
            args.path,
            force_reingest=args.force_reingest,
            parent_summaries_path=args.parent_summaries,
            max_parent_chunks=args.max_parent_chunks,
            progress_callback=_progress,
        )
    except MissingGeminiApiKeyError as exc:
        print(f"Gemini API key missing: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Ingestion failed: {exc}", file=sys.stderr)
        return 1

    print("Week 1 parent-child RAG dataset ingestion complete")
    print(f"  path                : {Path(args.path)}")
    print(f"  documents_ingested  : {result.documents_ingested}")
    print(f"  elements_extracted  : {result.elements_extracted}")
    print(f"  atomic_summaries    : {result.atomic_summaries_created}")
    print(f"  parent_chunks       : {result.parent_chunks_created}")
    print(f"  retrieval_summaries : {result.retrieval_summaries_created}")
    print(f"  embeddings_created  : {result.embeddings_created}")
    print(f"  template_summaries  : {result.template_summaries_count}")
    print(f"  llm_summaries       : {result.llm_summaries_count}")
    print(f"  fallback_summaries  : {result.fallback_summaries_count}")
    if args.parent_summaries:
        print(f"  parent_summaries    : {Path(args.parent_summaries)}")
    if args.max_parent_chunks:
        print(f"  max_parent_chunks   : {args.max_parent_chunks}")
    if result.skipped:
        print("  skipped:")
        for item in result.skipped:
            print(f"    - {item}")
    else:
        print("  skipped             : none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
