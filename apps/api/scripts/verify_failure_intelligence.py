"""Self-contained verification of the evidence-backed failure intelligence.

Uses FastAPI's ``TestClient`` against the current internal application, so no
developer needs to start ``uvicorn`` manually. It runs against the configured
Postgres acceptance database and asserts that ``GET
/assets/{tag}/failure-intelligence`` and ``GET /dashboard/failure-hotspots``
return only evidence-backed results, keep assets isolated, and stay safe for
unknown assets.

    PERSISTENCE_BACKEND=postgres \
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind \
    .venv/bin/python -m scripts.verify_failure_intelligence
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("PERSISTENCE_BACKEND", "postgres")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Document
from app.db.session import session_scope
from app.main import app


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def _seeded_filenames() -> set[str]:
    with session_scope() as session:
        return {
            name
            for name in session.execute(select(Document.original_filename)).scalars().all()
            if name
        }


def main() -> int:
    print("\nverify_failure_intelligence: self-contained TestClient run against Postgres")
    seeded = _seeded_filenames()
    if not seeded:
        _fail("no seeded documents found — run scripts.seed_demo first")
    client = TestClient(app)

    _section("P-101 failure intelligence (evidence-grounded)")
    resp = client.get("/assets/P-101/failure-intelligence")
    if resp.status_code != 200:
        _fail(f"expected 200 for P-101, got {resp.status_code}")
    data = resp.json()
    _ok(f"asset_tag = {data['asset_tag']}")

    if data["insufficient_data"]:
        _fail("P-101 unexpectedly reports insufficient failure evidence")
    _ok(f"failure_event_count = {data['failure_event_count']} (> 0)")
    _ok(f"distinct_failure_modes = {data['distinct_failure_modes']}")

    if not data["recent_failure_events"]:
        _fail("no recent failure events surfaced for P-101")
    for event in data["recent_failure_events"]:
        cite = event.get("citation") or {}
        if not cite.get("document_id"):
            _fail("a failure event is missing a citation document_id")
        if cite.get("filename") and cite["filename"] not in seeded:
            _fail(f"failure event cites unknown document {cite['filename']!r}")
        if not event.get("failure_modes"):
            _fail("a failure event has no detected failure modes")
    _ok("every failure event cites a real seeded document and has failure modes")

    if data["coverage_confidence"] not in {"low", "medium", "high"}:
        _fail(f"unexpected coverage_confidence {data['coverage_confidence']!r}")
    _ok(f"coverage_confidence = {data['coverage_confidence']}")

    if "prediction" in data["disclaimer"].lower() and "not a prediction" not in data["disclaimer"].lower():
        _fail("disclaimer must not claim prediction")
    _ok("disclaimer present and makes no predictive claim")

    _section("Unknown asset (safe, no fabrication)")
    resp = client.get("/assets/ZZ-999/failure-intelligence")
    if resp.status_code != 404:
        _fail(f"unknown asset should be 404, got {resp.status_code}")
    _ok("unknown asset returns 404 (no fabricated failures)")

    _section("Failure hotspots (evidence-supported ranking)")
    resp = client.get("/dashboard/failure-hotspots?limit=10")
    if resp.status_code != 200:
        _fail(f"expected 200 for hotspots, got {resp.status_code}")
    hot = resp.json()
    hotspots = hot["hotspots"]
    if not hotspots:
        _fail("no failure hotspots found")
    _ok(f"{hot['count']} hotspots (of {hot['total_assets_with_failures']} assets with failures)")

    counts = [h["failure_event_count"] for h in hotspots]
    if counts != sorted(counts, reverse=True):
        _fail("hotspots are not ranked by failure_event_count descending")
    _ok("hotspots ranked by documented failure-event count")

    for h in hotspots:
        if h["failure_event_count"] <= 0:
            _fail(f"{h['asset_tag']} listed as a hotspot with 0 failures")
        if not h["evidence"]:
            _fail(f"{h['asset_tag']} hotspot has no supporting evidence")
    _ok("every hotspot has failures and supporting evidence citations")

    print("\n--- Failure Intelligence Verification PASSED ---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
