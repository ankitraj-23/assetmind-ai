"""Verify asset-scoped retrieval and citations via the production RAG path.

This exercises the *same* retrieval, embedding-provider and citation logic used
by the ``/rag/chat`` endpoint (``app.rag.retrieval.retrieve_relevant_chunks``,
``app.rag.answer.answer_question`` and ``app.rag.chat._apply_asset_scope``). The
removed ``app.services.query.answer_question`` helper is intentionally *not*
used — there is a single production query architecture.

Runs against the seeded local Postgres acceptance database:

    PERSISTENCE_BACKEND=postgres \
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind \
    .venv/bin/python -m scripts.verify_asset_scoped_retrieval
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PERSISTENCE_BACKEND", "postgres")

from app.core import config
from app.rag import embeddings
from app.rag.answer import answer_question
from app.rag.chat import _apply_asset_scope, _normalize_asset_tag
from app.rag.retrieval import retrieve_relevant_chunks
from app.services.search import _mentions_tag

config.settings.persistence_backend = "postgres"


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


ASSET = "P-101"


def test_environment() -> None:
    _section("Environment / provider")
    if not config.use_postgres():
        _fail("PERSISTENCE_BACKEND must be postgres for this verifier")
    _ok("persistence backend = postgres")
    _ok(f"embedding provider = {embeddings.active_provider()}")
    _ok(f"embedding model = {embeddings.active_model()}")


def test_asset_scoped_retrieval() -> None:
    _section(f"Asset-scoped retrieval ({ASSET})")

    global_chunks = retrieve_relevant_chunks("vibration seal bearing", top_k=5)
    if not global_chunks:
        _fail("global retrieval returned no results — is the database seeded?")
    _ok(f"global retrieval: {len(global_chunks)} chunks")

    scoped_question = _apply_asset_scope(
        "vibration seal bearing", _normalize_asset_tag(ASSET)
    )
    scoped_chunks = retrieve_relevant_chunks(scoped_question, top_k=5)
    if not scoped_chunks:
        _fail("asset-scoped retrieval returned no results")
    _ok(f"asset-scoped retrieval: {len(scoped_chunks)} chunks")

    # The asset must appear somewhere in the retrieved evidence.
    mentions = [
        c for c in scoped_chunks
        if _mentions_tag(c.content, ASSET)
        or any(t.upper() == ASSET for t in c.asset_tags)
    ]
    if not mentions:
        _fail(f"no retrieved chunk mentions {ASSET}")
    _ok(f"{len(mentions)}/{len(scoped_chunks)} retrieved chunks mention {ASSET}")

    if _mentions_tag(scoped_chunks[0].content, ASSET):
        _ok(f"top result mentions {ASSET}")
    else:
        print(f"  [WARN] top result does not mention {ASSET} — boost may be weak")

    chunk_ids = [c.chunk_id for c in scoped_chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        _fail("duplicate chunk_ids in retrieval results")
    _ok("no duplicate chunk_ids")


def test_full_query_citations() -> None:
    _section("Full query: citations + confidence via answer_question")

    scoped = _apply_asset_scope(
        "Why is P-101 repeatedly vibrating after a seal replacement?",
        _normalize_asset_tag(ASSET),
    )
    resp = answer_question(scoped, top_k=5)

    if not resp.retrieved_chunks:
        _fail("answer_question returned no retrieved_chunks")
    _ok(f"retrieved_chunks = {len(resp.retrieved_chunks)}")

    if not resp.citations:
        _fail("expected at least one citation")
    _ok(f"citations count = {len(resp.citations)}")

    cids = [c.chunk_id for c in resp.citations]
    if len(cids) != len(set(cids)):
        _fail("duplicate chunk_ids in citations")
    _ok("no duplicate chunk_ids in citations")

    for c in resp.citations:
        if not c.chunk_id or not c.file_name:
            _fail(f"citation missing chunk_id or file_name: {c}")
        if not c.snippet:
            _fail(f"citation missing snippet: {c}")
    _ok("all citations have chunk_id, file_name and snippet")

    if not 0.0 <= resp.confidence <= 1.0:
        _fail(f"confidence out of range: {resp.confidence}")
    _ok(f"confidence = {resp.confidence}")

    top = resp.citations[0]
    print(f"\n  Answer preview: {resp.answer[:120]}...")
    print(f"  Top citation: [{top.file_name}] page={top.page}")


def main() -> None:
    print("\nverify_asset_scoped_retrieval: production RAG path against Postgres")
    test_environment()
    test_asset_scoped_retrieval()
    test_full_query_citations()

    _section("Summary")
    print("  ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
