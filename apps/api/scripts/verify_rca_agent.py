"""Self-contained verification of the RCA agent.

Uses FastAPI's ``TestClient`` against the current internal application, so no
developer needs to start ``uvicorn`` manually. It runs against the explicitly
configured local Postgres acceptance database and asserts that the RCA agent
returns evidence-grounded output whose every source genuinely exists in the
seeded documents.

    PERSISTENCE_BACKEND=postgres \
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@127.0.0.1:5432/assetmind \
    .venv/bin/python -m scripts.verify_rca_agent
"""

from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("PERSISTENCE_BACKEND", "postgres")

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Document
from app.db.session import session_scope
from app.main import app

FORBIDDEN_SOURCE = "pump_p101_note.txt"


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def _section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def _seeded_filenames() -> set[str]:
    with session_scope() as session:
        return {
            name
            for name in session.execute(select(Document.original_filename)).scalars().all()
            if name
        }


def _post_rca(client: TestClient, asset_tag: str, symptom: str) -> dict:
    resp = client.post("/agents/rca", json={"asset_tag": asset_tag, "symptom": symptom})
    if resp.status_code != 200:
        _fail(f"/agents/rca returned {resp.status_code}: {resp.text}")
    return resp.json()


def _all_evidence_sources(data: dict) -> list[str]:
    sources: list[str] = []
    for cause in data.get("likely_causes", []):
        for ev in cause.get("evidence", []):
            if ev.get("source"):
                sources.append(ev["source"])
    return sources


def main() -> int:
    print("\nverify_rca_agent: self-contained TestClient run against Postgres")

    seeded = _seeded_filenames()
    _section("Seeded corpus")
    if not seeded:
        _fail("No documents in the database — seed the demo plant before verifying.")
    _ok(f"{len(seeded)} seeded documents")
    if FORBIDDEN_SOURCE in seeded:
        print(f"  [WARN] {FORBIDDEN_SOURCE} is actually seeded; grounding check relaxed.")

    client = TestClient(app)

    # ── P-101: the canonical RCA case ────────────────────────────────────────
    _section("P-101 RCA (evidence-grounded)")
    data = _post_rca(client, "P-101", "high vibration after seal replacement")

    if data.get("asset_tag") != "P-101":
        _fail(f"asset_tag mismatch: {data.get('asset_tag')}")
    _ok("asset_tag = P-101")

    causes = data.get("likely_causes", [])
    if len(causes) < 2:
        _fail(f"expected >= 2 likely causes for P-101, got {len(causes)}")
    _ok(f"likely_causes = {len(causes)} (>= 2)")

    if not data.get("recommended_actions"):
        _fail("recommended_actions is empty")
    _ok(f"recommended_actions = {len(data['recommended_actions'])}")

    if "missing_information" not in data or not data["missing_information"]:
        _fail("missing_information is missing or empty")
    _ok(f"missing_information = {len(data['missing_information'])}")

    evidence_sources = _all_evidence_sources(data)
    if not evidence_sources:
        _fail("no evidence attached to any likely cause")
    _ok(f"evidence entries = {len(evidence_sources)}")

    if FORBIDDEN_SOURCE not in seeded and FORBIDDEN_SOURCE in json.dumps(data):
        _fail(f"response references nonexistent fixed source {FORBIDDEN_SOURCE}")
    _ok(f"no reference to nonexistent {FORBIDDEN_SOURCE}")

    missing_sources = sorted(set(evidence_sources) - seeded)
    if missing_sources:
        _fail(f"evidence cites sources not in seeded documents: {missing_sources}")
    _ok("every evidence source exists in seeded documents")

    for cause in causes:
        conf = cause.get("confidence")
        if conf is None or not 0.0 <= conf <= 1.0:
            _fail(f"cause confidence out of range: {conf}")
    _ok("all cause confidences within [0, 1]")

    # ── Unknown asset: must NOT get a P-101 answer ───────────────────────────
    _section("Unknown asset (no cross-asset contamination)")
    unknown = _post_rca(client, "ZZ-999", "high vibration after seal replacement")

    if unknown.get("asset_tag") != "ZZ-999":
        _fail(f"unknown asset_tag mismatch: {unknown.get('asset_tag')}")
    _ok("asset_tag = ZZ-999")

    if unknown.get("likely_causes"):
        _fail("unknown asset should not receive likely causes from unrelated evidence")
    _ok("no fabricated causes for unknown asset")

    blob = json.dumps(unknown)
    if "P-101" in blob:
        _fail("unknown-asset response leaked a P-101 answer")
    _ok("no P-101 answer leaked to unknown asset")

    if FORBIDDEN_SOURCE in blob:
        _fail(f"unknown-asset response references {FORBIDDEN_SOURCE}")
    _ok(f"no reference to {FORBIDDEN_SOURCE} for unknown asset")

    _section("Summary")
    print("  ALL RCA CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
