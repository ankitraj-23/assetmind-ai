"""End-to-end proof: normal upload -> canonical index -> production Copilot.

Exercises exactly the public path a browser upload takes (``POST /documents``)
and then the production Copilot endpoint (``POST /rag/chat``), asserting that a
freshly uploaded document is retrievable and cited by Copilot.

Run (Postgres backend required)::

    cd apps/api
    source .venv/bin/activate
    export PERSISTENCE_BACKEND=postgres
    export DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind
    python -m scripts.verify_upload_to_rag

Exit code 0 means every check passed. The script is safe to re-run: each run
uploads a uniquely named file and never mutates prior documents.

Cleanup
-------
This proof persists a ``final_e2e_marker_*.txt`` document (with ZZ-991 marker
data) on every run. To keep the acceptance database clean:

* ``--cleanup`` deletes *only* the document uploaded by this specific run (and
  the ZZ-991 marker asset if it becomes orphaned), so a run leaves no trace.
* ``--cleanup-markers`` deletes every ``final_e2e_marker_*.txt`` document and
  the orphaned ZZ-991 marker asset, then exits without running the proof.

Both options identify records strictly by the unique test filename prefix / this
run's document id and never touch unrelated documents.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete
from sqlalchemy import func

from app.core import config
from app.db.models import (
    Asset,
    AssetMention,
    Document,
    DocumentChunk,
    DocumentPage,
    ExtractedEntity,
)
from app.db.session import session_scope
from app.main import app
from app.rag import embeddings

MARKER_ASSET = "ZZ-991"
MARKER_FILENAME_PREFIX = "final_e2e_marker_"
MARKER_SEAL = "TC-77"
MARKER_COOLDOWN = "41 minute"
CONTENT = (
    "Pump ZZ-991 uses a tungsten-ceramic TC-77 seal and requires a 41 minute "
    "cooldown before inspection."
)
QUESTION = (
    "What seal does ZZ-991 use and how long must it cool before inspection?"
)


class Reporter:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        suffix = f" — {detail}" if detail else ""
        print(f"  [{status}] {label}{suffix}")
        if not ok:
            self.failures.append(label)


def _upload(client: TestClient, filename: str) -> dict:
    response = client.post(
        "/documents",
        files={"file": (filename, CONTENT.encode("utf-8"), "text/plain")},
    )
    if response.status_code != 201:
        raise RuntimeError(
            f"Upload failed: HTTP {response.status_code} — {response.text}"
        )
    return response.json()


def _chat(client: TestClient, message: str, *, asset_tag: str | None = None) -> dict:
    payload: dict = {"message": message, "top_k": 7}
    if asset_tag:
        payload["asset_tag"] = asset_tag
    response = client.post("/rag/chat", json=payload)
    if response.status_code != 200:
        raise RuntimeError(
            f"/rag/chat failed: HTTP {response.status_code} — {response.text}"
        )
    return response.json()


def _citation_filenames(chat_response: dict) -> list[str]:
    return [c.get("file_name") for c in chat_response.get("citations", [])]


def _delete_document(session, document_id: str) -> None:
    """Delete a single document and its dependent rows (chunks, pages, entities,
    asset mentions). Scoped strictly to ``document_id`` — nothing else."""
    session.execute(sa_delete(AssetMention).where(AssetMention.document_id == document_id))
    session.execute(sa_delete(ExtractedEntity).where(ExtractedEntity.document_id == document_id))
    session.execute(sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
    session.execute(sa_delete(DocumentPage).where(DocumentPage.document_id == document_id))
    session.execute(sa_delete(Document).where(Document.id == document_id))


def _delete_orphan_marker_asset(session, tag: str) -> bool:
    """Delete the marker asset only if it has no remaining mentions."""
    asset = session.query(Asset).filter(Asset.tag == tag).one_or_none()
    if asset is None:
        return False
    remaining = (
        session.query(func.count(AssetMention.id))
        .filter(AssetMention.asset_id == asset.id)
        .scalar()
    )
    if remaining:
        return False
    session.delete(asset)
    return True


def cleanup_markers() -> int:
    """Delete all E2E marker documents and the orphaned ZZ-991 marker asset."""
    if not config.use_postgres():
        print("ERROR: PERSISTENCE_BACKEND=postgres is required for cleanup.")
        return 2
    with session_scope() as session:
        marker_ids = [
            row[0]
            for row in session.query(Document.id)
            .filter(Document.original_filename.like(f"{MARKER_FILENAME_PREFIX}%"))
            .all()
        ]
        for document_id in marker_ids:
            _delete_document(session, document_id)
        asset_removed = _delete_orphan_marker_asset(session, MARKER_ASSET)
    print(
        f"Cleanup: removed {len(marker_ids)} '{MARKER_FILENAME_PREFIX}*' document(s); "
        f"ZZ-991 marker asset removed: {asset_removed}."
    )
    return 0


def main(cleanup: bool = False) -> int:
    if not config.use_postgres():
        print("ERROR: PERSISTENCE_BACKEND=postgres is required for this proof.")
        return 2

    provider = embeddings.active_provider()
    model = embeddings.active_model()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    filename = f"final_e2e_marker_{timestamp}.txt"

    print("AssetMind AI — upload → RAG end-to-end proof")
    print(f"  embedding provider/model: {provider} / {model}")
    print(f"  upload filename:          {filename}")
    print()

    report = Reporter()
    client = TestClient(app)

    # 1) Upload succeeds.
    doc = _upload(client, filename)
    document_id = doc["id"]
    report.check(bool(document_id), "1. Upload succeeds", f"document_id={document_id}")
    report.check(
        doc.get("embedding_model") == model,
        "5. Upload used the active embedding provider/model",
        f"{doc.get('embedding_provider')} / {doc.get('embedding_model')}",
    )
    report.check(
        MARKER_ASSET in (doc.get("assets_extracted") or []),
        "4a. Upload response reports ZZ-991 extracted",
        f"assets={doc.get('assets_extracted')}",
    )

    # 2/3/4/5 — persistence assertions straight from the database.
    with session_scope() as session:
        chunks = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .all()
        )
        report.check(len(chunks) >= 1, "3. Retrieval chunks persisted", f"{len(chunks)} chunk(s)")
        embedded = [c for c in chunks if c.embedding is not None]
        report.check(len(embedded) >= 1, "3b. Chunk embeddings persisted", f"{len(embedded)} embedded")
        models = {c.embedding_model for c in embedded}
        report.check(
            models == {model},
            "5b. Persisted vectors use the active model only",
            f"models={models}",
        )

        asset = session.query(Asset).filter(Asset.tag == MARKER_ASSET).one_or_none()
        report.check(asset is not None, "4b. ZZ-991 asset persisted")
        if asset is not None:
            mention = (
                session.query(AssetMention)
                .filter(
                    AssetMention.asset_id == asset.id,
                    AssetMention.document_id == document_id,
                )
                .first()
            )
            report.check(
                mention is not None,
                "4c. ZZ-991 mention linked to the uploaded document",
            )

        chunk_count_after_first = len(chunks)

    # 2) Document persisted (list route).
    listed = client.get("/documents").json()
    report.check(
        any(d["id"] == document_id for d in listed),
        "2. Document persisted and listed",
    )

    # 6/7/8) Production Copilot answers and cites the new document.
    chat = _chat(client, QUESTION)
    answer = chat.get("answer", "")
    citations = _citation_filenames(chat)
    report.check(
        filename in citations,
        "7. Copilot citations contain the uploaded filename",
        f"citations={citations}",
    )
    report.check(
        MARKER_SEAL in answer and MARKER_COOLDOWN in answer,
        "8. Copilot answer conveys TC-77 and 41 minutes",
        f"answer[:160]={answer[:160]!r}",
    )

    # 9) Asset-scoped retrieval cites the same file.
    scoped = _chat(client, "What seal is required and its cooldown time?", asset_tag=MARKER_ASSET)
    report.check(
        filename in _citation_filenames(scoped),
        "9. Asset-scoped Copilot cites the uploaded file",
        f"citations={_citation_filenames(scoped)}",
    )

    # 10) Re-running retrieval does not corrupt or duplicate the index.
    time.sleep(0.1)
    repeat = _chat(client, QUESTION)
    repeat_citations = _citation_filenames(repeat)
    report.check(
        filename in repeat_citations,
        "10a. Repeat Copilot query is stable and still cites the file",
    )
    with session_scope() as session:
        chunk_count_repeat = (
            session.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .count()
        )
    report.check(
        chunk_count_repeat == chunk_count_after_first,
        "10b. No duplicate chunks created for the document",
        f"{chunk_count_after_first} -> {chunk_count_repeat}",
    )

    if cleanup:
        with session_scope() as session:
            _delete_document(session, document_id)
            asset_removed = _delete_orphan_marker_asset(session, MARKER_ASSET)
        print(
            f"\nCleanup: removed this run's document {filename} ({document_id})"
            f"{'; orphaned ZZ-991 marker asset removed' if asset_removed else ''}."
        )

    print()
    if report.failures:
        print(f"RESULT: FAILED ({len(report.failures)} check(s) failed)")
        for failure in report.failures:
            print(f"  - {failure}")
        return 1
    print("RESULT: PASSED — uploaded document is fully visible to production Copilot.")
    print(f"  Answer:\n    {answer}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete only the document created by this run after verifying.",
    )
    parser.add_argument(
        "--cleanup-markers",
        action="store_true",
        help="Delete all final_e2e_marker_* documents and the ZZ-991 marker asset, then exit.",
    )
    args = parser.parse_args()

    if args.cleanup_markers:
        sys.exit(cleanup_markers())
    sys.exit(main(cleanup=args.cleanup))
