"""Focused tests for the evidence-grounded RCA fallback.

These stub the retrieval layer so the deterministic fallback is exercised
without a live Postgres/demo database or Gemini. The end-to-end check against
seeded data lives in ``scripts/verify_rca_agent.py``.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app.core import config
from app.models.agents import RcaRequest
from app.services import rca as R


def _ev(text, *, filename="work_orders_clean.csv", document_id="doc-1", chunk_id="doc-1-0"):
    return {
        "text": text,
        "filename": filename,
        "document_id": document_id,
        "chunk_id": chunk_id,
    }


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    # Force the deterministic (no-Gemini) path for these tests.
    monkeypatch.setattr(config.settings, "llm_provider", None, raising=False)


def _patch_evidence(monkeypatch, chunks):
    async def fake(question, asset_tag=None, top_k=10):
        return list(chunks)

    monkeypatch.setattr(R, "get_evidence_for_rca", fake)


def _run(asset, symptom):
    return asyncio.run(R.perform_rca(RcaRequest(asset_tag=asset, symptom=symptom)))


# 1. P-101 with realistic seeded-style evidence ------------------------------

def test_p101_vibration_returns_grounded_causes(monkeypatch):
    evidence = [
        _ev(
            "Equipment_ID: P-101 WorkOrderDescription: Centrifugal Pump P-101 vibration "
            "trending upward. Bearing defect frequency identified in spectrum. Replace "
            "drive end bearing proactively.",
            filename="work_orders_clean.csv",
        ),
        _ev(
            "P-101 - Cooling Water Pump. Vibration at drive end bearing exceeds limit. "
            "Visual inspection reveals slight misalignment of flexible coupling. Last "
            "seal replacement on 12 January 2025.",
            filename="inspection_report_q1_2025.pdf",
            document_id="doc-2",
            chunk_id="doc-2-0",
        ),
    ]
    _patch_evidence(monkeypatch, evidence)

    resp = _run("P-101", "high vibration after seal replacement")

    assert resp.asset_tag == "P-101"
    assert len(resp.likely_causes) >= 2
    assert resp.recommended_actions
    assert resp.missing_information
    for cause in resp.likely_causes:
        assert 0.0 < cause.confidence <= 0.75
        assert cause.evidence
    # No fixed/nonexistent source ever leaks in.
    blob = json.dumps(resp.model_dump())
    assert "pump_p101_note.txt" not in blob


# 2. Another known asset -----------------------------------------------------

def test_overheating_asset_lubrication_cause(monkeypatch):
    evidence = [
        _ev(
            "Equipment_ID: M-017 Motor M-017 overheating. Bearing lubrication grease "
            "degraded, oil analysis overdue.",
            filename="work_orders_clean.csv",
        ),
    ]
    _patch_evidence(monkeypatch, evidence)

    resp = _run("M-017", "overheating during operation")

    assert resp.asset_tag == "M-017"
    assert resp.likely_causes
    assert any("lubric" in c.cause.lower() or "cooling" in c.cause.lower() for c in resp.likely_causes)


# 3. Unknown asset -> insufficient evidence, no cross-asset answer -----------

def test_unknown_asset_insufficient(monkeypatch):
    # Retrieval returns chunks that reference *other* assets, never ZZ-999.
    evidence = [
        _ev("Equipment_ID: P-101 vibration and bearing fault. Replace bearing."),
        _ev("Equipment_ID: M-017 overcurrent trip."),
    ]
    _patch_evidence(monkeypatch, evidence)

    resp = _run("ZZ-999", "high vibration after seal replacement")

    assert resp.asset_tag == "ZZ-999"
    assert resp.likely_causes == []
    assert "insufficient" in resp.summary.lower() or "no documents" in resp.summary.lower()
    assert resp.recommended_actions
    assert resp.missing_information


# 4. Every cited evidence source is one that was actually retrieved ----------

def test_evidence_sources_only_from_retrieved(monkeypatch):
    evidence = [
        _ev(
            "Equipment_ID: P-101 vibration; bearing defect; coupling misalignment; seal replaced.",
            filename="work_orders_clean.csv",
        ),
        _ev(
            "P-101 inspection: misalignment of flexible coupling noted.",
            filename="inspection_report_q1_2025.pdf",
            document_id="doc-2",
            chunk_id="doc-2-0",
        ),
    ]
    _patch_evidence(monkeypatch, evidence)

    resp = _run("P-101", "vibration after seal replacement")

    retrieved_sources = {c["filename"] for c in evidence}
    for cause in resp.likely_causes:
        for ev in cause.evidence:
            assert ev.source in retrieved_sources
            assert ev.chunk_id in {"doc-1-0", "doc-2-0"}


# 5. No cross-asset fallback contamination -----------------------------------

def test_no_cross_asset_contamination(monkeypatch):
    # Even though retrieved evidence is entirely about P-101, an RCA for a
    # different asset must never surface a P-101 answer.
    evidence = [
        _ev("Equipment_ID: P-101 bearing fault, coupling misalignment, seal replacement."),
    ]
    _patch_evidence(monkeypatch, evidence)

    resp = _run("HX-999", "high vibration after seal replacement")

    assert resp.asset_tag == "HX-999"
    assert resp.likely_causes == []
    blob = json.dumps(resp.model_dump())
    assert "P-101" not in blob
    assert "pump_p101_note.txt" not in blob


# Retrieval failure is handled safely ----------------------------------------

def test_retrieval_error_is_safe(monkeypatch):
    async def boom(question, asset_tag=None, top_k=10):
        raise RuntimeError("db down")

    monkeypatch.setattr(R, "get_evidence_for_rca", boom)

    resp = _run("P-101", "high vibration")
    assert resp.likely_causes == []
    assert resp.recommended_actions
    assert resp.missing_information
