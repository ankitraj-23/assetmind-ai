"""Re-index chunk embeddings onto the active embedding provider/model.

The retrieval layer only compares vectors produced by the *active* provider
(see :func:`app.rag.embeddings.active_model`). Chunks embedded with a different
or unknown model are therefore invisible to Copilot until re-indexed. This
script safely re-embeds those chunks *in place* using the canonical provider.

What it does / does not do:

* Identifies embedded chunks whose ``embedding_model`` differs from the active
  model (these are the incompatible / unknown vectors).
* Re-embeds the *exact text that was originally embedded* — the stored
  ``retrieval_summary`` for summary-indexed parent chunks, otherwise the chunk
  text — with the active provider, and overwrites only the vector + model.
* Never creates new chunk / asset / mention rows (no duplicates) and never
  deletes documents or source files.

Usage::

    cd apps/api
    source .venv/bin/activate
    export PERSISTENCE_BACKEND=postgres
    export DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind

    python -m scripts.reindex_documents --dry-run   # report only, no writes
    python -m scripts.reindex_documents             # apply
"""

from __future__ import annotations

import argparse
import sys

from app.core import config
from app.db.models import Document, DocumentChunk
from app.db.session import session_scope
from app.rag import embeddings


def _text_to_embed(chunk: DocumentChunk) -> str:
    """Reproduce the text originally fed to the embedder for this chunk."""
    metadata = dict(chunk.metadata_json or {})
    summary = metadata.get("retrieval_summary")
    if summary and str(summary).strip():
        return str(summary)
    return chunk.text or ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing anything.",
    )
    parser.add_argument(
        "--document-id",
        default=None,
        help="Restrict re-indexing to a single document id.",
    )
    args = parser.parse_args()

    if not config.use_postgres():
        print("ERROR: PERSISTENCE_BACKEND=postgres is required.")
        return 2

    active_model = embeddings.active_model()
    provider = embeddings.active_provider()
    print(f"Active embedding provider/model: {provider} / {active_model}")
    print(f"Mode: {'DRY RUN (no writes)' if args.dry_run else 'APPLY'}")
    print()

    reindexed = 0
    skipped_compatible = 0
    skipped_no_embedding = 0
    failures: list[str] = []
    per_document: dict[str, int] = {}

    # Collect the work list first (short-lived read session).
    with session_scope() as session:
        query = session.query(DocumentChunk)
        if args.document_id:
            query = query.filter(DocumentChunk.document_id == args.document_id)
        rows = query.order_by(
            DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc()
        ).all()
        work = []
        for chunk in rows:
            if chunk.embedding is None:
                skipped_no_embedding += 1
                continue
            if chunk.embedding_model == active_model:
                skipped_compatible += 1
                continue
            work.append((chunk.id, chunk.document_id, _text_to_embed(chunk), chunk.embedding_model))

    for chunk_id, document_id, text, old_model in work:
        if args.dry_run:
            reindexed += 1
            per_document[document_id] = per_document.get(document_id, 0) + 1
            continue
        try:
            vector = embeddings.embed_text(text)
            with session_scope() as session:
                chunk = session.get(DocumentChunk, chunk_id)
                if chunk is None:
                    failures.append(f"{chunk_id}: disappeared before write")
                    continue
                chunk.embedding = vector
                chunk.embedding_model = active_model
            reindexed += 1
            per_document[document_id] = per_document.get(document_id, 0) + 1
        except Exception as exc:  # noqa: BLE001 — report and continue
            failures.append(f"{chunk_id} (was {old_model}): {exc}")

    print("Documents affected:")
    if per_document:
        with session_scope() as session:
            for document_id, count in sorted(per_document.items()):
                doc = session.get(Document, document_id)
                name = doc.original_filename if doc else "?"
                print(f"  {document_id}  {name}  — {count} chunk(s)")
    else:
        print("  (none)")

    print()
    verb = "would re-index" if args.dry_run else "re-indexed"
    print(f"{verb}: {reindexed} chunk(s)")
    print(f"skipped (already {active_model}): {skipped_compatible}")
    print(f"skipped (no embedding): {skipped_no_embedding}")
    print(f"failures: {len(failures)}")
    for failure in failures:
        print(f"  - {failure}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
