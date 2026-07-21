"""Tests for the evidence-backed failure-intelligence feature (Day 9).

Covers the pure aggregation logic (``_build_failure_intelligence`` and its
helpers) plus the two routes (``GET /assets/{tag}/failure-intelligence`` and
``GET /dashboard/failure-hotspots``). Every asserted number must trace back to a
real evidence citation, unknown assets must be safe, and JSON mode must never
touch a database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db import repository as repo
from app.main import app


def _asset(tag="P-101", asset_type="pump"):
    return SimpleNamespace(
        id=f"asset-{tag}",
        tag=tag,
        asset_type=asset_type,
        display_name=tag,
        metadata_json={},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _row(text, filename, *, mention_id="m1", doc_id="d1", chunk_id="c1", chunk_index=0,
         created=datetime(2026, 5, 1, tzinfo=timezone.utc)):
    mention = SimpleNamespace(
        id=mention_id, document_id=doc_id, chunk_id=chunk_id, created_at=created
    )
    document = SimpleNamespace(id=doc_id, original_filename=filename, created_at=created)
    chunk = SimpleNamespace(text=text, chunk_index=chunk_index)
    return (mention, document, chunk)


# --- pure aggregation -------------------------------------------------------

def test_detects_failure_modes_and_citations():
    rows = [
        _row("Pump showed high vibration and bearing wear during run.",
             "inspection_report.pdf", mention_id="m1", chunk_id="c1"),
        _row("Work order: replaced mechanical seal after seal failure and leakage.",
             "work_orders.csv", mention_id="m2", doc_id="d2", chunk_id="c2"),
    ]
    view = repo._build_failure_intelligence(_asset(), rows)

    assert view["asset_tag"] == "P-101"
    assert view["insufficient_data"] is False
    assert view["failure_event_count"] == 2
    modes = {m["mode"] for m in view["failure_modes"]}
    assert {"vibration", "bearing_wear", "seal_failure", "leakage"} <= modes
    # every surfaced event carries a real citation
    for event in view["recent_failure_events"]:
        assert event["citation"]["document_id"]
        assert event["failure_modes"]
    # the repair mention is captured as a maintenance action + work-order ref
    assert view["maintenance_actions"], "maintenance action should be captured"
    assert "work_orders.csv" in view["work_order_references"]
    assert view["disclaimer"]


def test_repeated_failure_modes_flagged():
    rows = [
        _row("High vibration alarm on pump.", "r1.pdf", mention_id="m1", chunk_id="c1"),
        _row("Vibration exceeded threshold again.", "r2.pdf", mention_id="m2",
             doc_id="d2", chunk_id="c2"),
    ]
    view = repo._build_failure_intelligence(_asset(), rows)
    assert "vibration" in view["repeated_failure_modes"]
    vib = next(m for m in view["failure_modes"] if m["mode"] == "vibration")
    assert vib["count"] == 2


def test_no_failure_evidence_is_insufficient_not_fabricated():
    rows = [
        _row("SOP for routine pump startup and shutdown checklist.",
             "sop_pump_startup.pdf"),
    ]
    view = repo._build_failure_intelligence(_asset(), rows)
    assert view["insufficient_data"] is True
    assert view["failure_event_count"] == 0
    assert view["failure_modes"] == []
    assert view["recent_failure_events"] == []
    assert view["coverage_confidence"] == "low"


def test_confidence_scales_with_evidence():
    assert repo._failure_confidence(0, 0) == "low"
    assert repo._failure_confidence(2, 1) == "medium"
    assert repo._failure_confidence(4, 2) == "high"


# --- routes -----------------------------------------------------------------

def test_route_returns_intelligence(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    payload = {"asset_tag": "P-101", "failure_event_count": 3, "insufficient_data": False}
    monkeypatch.setattr(repo, "get_asset_failure_intelligence", lambda tag: payload)
    client = TestClient(app)
    resp = client.get("/assets/P-101/failure-intelligence")
    assert resp.status_code == 200
    assert resp.json()["asset_tag"] == "P-101"


def test_route_unknown_asset_404(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    monkeypatch.setattr(repo, "get_asset_failure_intelligence", lambda tag: None)
    client = TestClient(app)
    resp = client.get("/assets/ZZ-999/failure-intelligence")
    assert resp.status_code == 404


def test_route_json_mode_404(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "json")
    client = TestClient(app)
    resp = client.get("/assets/P-101/failure-intelligence")
    assert resp.status_code == 404


def test_hotspots_route(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    result = {"count": 1, "total_assets_with_failures": 1, "hotspots": [
        {"asset_tag": "P-101", "failure_event_count": 5}
    ]}
    monkeypatch.setattr(repo, "get_failure_hotspots", lambda limit=10: dict(result))
    client = TestClient(app)
    resp = client.get("/dashboard/failure-hotspots?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "postgres"
    assert body["hotspots"][0]["asset_tag"] == "P-101"


def test_hotspots_json_mode_safe_empty(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "json")
    client = TestClient(app)
    resp = client.get("/dashboard/failure-hotspots")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0
    assert body["hotspots"] == []
    assert body["mode"] == "json"
