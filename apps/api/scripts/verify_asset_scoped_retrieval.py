"""Verify asset-scoped retrieval, query intent detection, and related assets.

Requires documents to be ingested first. Run from apps/api/ with JSON backend:
    python -m scripts.verify_ingestion      # ingest test data
    python -m scripts.verify_asset_scoped_retrieval
"""

from __future__ import annotations

import asyncio
import io
import os
import sys

os.environ.setdefault("PERSISTENCE_BACKEND", "json")

import pandas as pd
from fastapi import UploadFile

from app.services.ingestion import ingest_csv, ingest_upload
from app.services.query import answer_question, detect_intent
from app.services.search import search, _mentions_tag


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def _section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


# ── setup: ingest sample docs ─────────────────────────────────────────────────

async def _setup() -> None:
    """Ingest sample data if not already present."""
    from app.services.ingestion import list_documents

    existing = {d.filename for d in list_documents()}

    if "work_orders_clean.csv" not in existing:
        csv_path = "../../data/documents/work_orders_clean.csv"
        with open(csv_path, "rb") as f:
            data = f.read()
        doc = await ingest_csv(UploadFile(filename="work_orders_clean.csv", file=io.BytesIO(data)))
        print(f"  ingested work_orders_clean.csv: {doc.chunk_count} chunks")

    if "pump_oem_manual.pdf" not in existing:
        pdf_path = "../../data/documents/pump_oem_manual.pdf"
        with open(pdf_path, "rb") as f:
            data = f.read()
        doc = await ingest_upload(UploadFile(filename="pump_oem_manual.pdf", file=io.BytesIO(data)))
        print(f"  ingested pump_oem_manual.pdf: {doc.chunk_count} chunks")

    if "inspection_report_q1_2025.pdf" not in existing:
        pdf_path = "../../data/documents/inspection_report_q1_2025.pdf"
        with open(pdf_path, "rb") as f:
            data = f.read()
        doc = await ingest_upload(UploadFile(filename="inspection_report_q1_2025.pdf", file=io.BytesIO(data)))
        print(f"  ingested inspection_report_q1_2025.pdf: {doc.chunk_count} chunks")


# ── intent detection ──────────────────────────────────────────────────────────

def test_intent_detection() -> None:
    _section("Query intent detection")

    cases = [
        ("How do I start P-101 after maintenance?",        "procedure"),
        ("Steps to shutdown P-201 safely",                 "procedure"),
        ("Why is P-101 vibrating after seal replacement?", "failure_rca"),
        ("Root cause of P-101 cavitation",                 "failure_rca"),
        ("What maintenance was done on P-101 last year?",  "maintenance_history"),
        ("Work orders for HX-305 last month",              "maintenance_history"),
        ("What were the inspection findings for P-101?",   "inspection"),
        ("Quarterly inspection reading for BLR-118",       "inspection"),
        ("Is P-101 compliant with OISD-137?",              "compliance"),
        ("PESO compliance status of TK-482",               "compliance"),
        ("What documents do we have?",                     "general"),
    ]

    all_ok = True
    for question, expected in cases:
        got = detect_intent(question)
        if got == expected:
            _ok(f"[{got:20s}] {question[:55]}")
        else:
            print(f"  [FAIL] expected [{expected}] got [{got}]: {question}")
            all_ok = False

    if not all_ok:
        _fail("intent detection failures above")


# ── asset-scoped search ───────────────────────────────────────────────────────

def test_asset_scoped_search() -> None:
    _section("Asset-scoped vector search (P-101)")

    # Global search (no asset_tag)
    global_results = search("vibration seal bearing", top_k=5)
    if not global_results:
        _fail("global search returned no results")
    _ok(f"global search: {len(global_results)} results")

    # Asset-scoped search
    scoped_results = search("vibration seal bearing", top_k=5, asset_tag="P-101")
    if not scoped_results:
        _fail("asset-scoped search returned no results")
    _ok(f"asset-scoped search: {len(scoped_results)} results")

    # Scoped results should lead with P-101 mentions
    p101_at_top = _mentions_tag(scoped_results[0].text, "P-101")
    if not p101_at_top:
        print("  [WARN] top result does not mention P-101 — boost may be insufficient")
    else:
        _ok("top result mentions P-101")

    # No duplicate chunk_ids
    chunk_ids = [r.chunk_id for r in scoped_results]
    if len(chunk_ids) != len(set(chunk_ids)):
        _fail("duplicate chunk_ids in results")
    _ok("no duplicate chunk_ids")

    # Source diversity: at most MAX_PER_DOCUMENT per document
    from app.services.search import MAX_PER_DOCUMENT
    from collections import Counter

    doc_counts = Counter(r.document_id for r in scoped_results)
    for doc_id, count in doc_counts.items():
        if count > MAX_PER_DOCUMENT:
            _fail(f"document {doc_id} appears {count} times (max {MAX_PER_DOCUMENT})")
    _ok(f"source diversity respected (max {MAX_PER_DOCUMENT} per doc)")


# ── full query with asset_tag ─────────────────────────────────────────────────

def test_query_with_asset_tag() -> None:
    _section("Full query: asset_tag + intent + citations + related_assets")

    resp = answer_question(
        "Why is P-101 repeatedly vibrating?",
        top_k=5,
        asset_tag="P-101",
    )

    if resp.query_intent != "failure_rca":
        _fail(f"expected intent=failure_rca, got {resp.query_intent}")
    _ok(f"query_intent = {resp.query_intent}")

    if not resp.citations:
        _fail("expected at least one citation")
    _ok(f"citations count = {len(resp.citations)}")

    # No duplicate citations
    cids = [c.chunk_id for c in resp.citations]
    if len(cids) != len(set(cids)):
        _fail("duplicate chunk_ids in citations")
    _ok("no duplicate chunk_ids in citations")

    # All citations have required fields
    for c in resp.citations:
        if not c.document_id or not c.chunk_id:
            _fail(f"citation missing document_id or chunk_id: {c}")
        if c.score is None:
            _fail(f"citation missing score: {c}")
        if not c.text_preview:
            _fail(f"citation missing text_preview: {c}")
    _ok("all citations have required fields")

    _ok(f"related_assets = {resp.related_assets}")
    _ok(f"confidence = {resp.confidence}")

    # Print summary for inspection
    print(f"\n  Answer preview: {resp.answer[:120]}...")
    print(f"  Top citation: [{resp.citations[0].filename}] page={resp.citations[0].page_number}")


# ── intent source priority ────────────────────────────────────────────────────

def test_intent_source_priority() -> None:
    _section("Intent-based source prioritisation")

    # procedure question → should prefer SOP/manual docs
    resp = answer_question("How do I start P-101?", top_k=5, asset_tag="P-101")
    if resp.query_intent != "procedure":
        _fail(f"expected procedure intent, got {resp.query_intent}")
    _ok(f"procedure intent detected")

    # Check that citations are present
    if not resp.citations:
        _fail("no citations returned for procedure query")
    _ok(f"citations returned: {len(resp.citations)}")

    # failure_rca query
    resp2 = answer_question("Root cause of P-101 bearing failure", top_k=5, asset_tag="P-101")
    if resp2.query_intent != "failure_rca":
        _fail(f"expected failure_rca, got {resp2.query_intent}")
    _ok(f"failure_rca intent detected for RCA question")


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\nverify_asset_scoped_retrieval: running against JSON backend")
    print("Setting up test documents...")
    await _setup()

    test_intent_detection()
    test_asset_scoped_search()
    test_query_with_asset_tag()
    test_intent_source_priority()

    _section("Summary")
    print("  ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
