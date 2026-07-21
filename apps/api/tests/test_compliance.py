"""Deterministic tests for the compliance rule engine and evidence packages.

These tests stub the repository layer so they exercise the real rule logic
without requiring a live Postgres/demo database. The end-to-end check against
seeded data lives in ``scripts/verify_compliance_agent.py``.
"""

from __future__ import annotations

import pytest

from app.core import config
from app.services import compliance as C
from app.services import evidence_package as EP


def _mention(text, *, filename="doc.pdf", document_id="doc-1", chunk_id="doc-1-0"):
    return {
        "text": text,
        "filename": filename,
        "document_id": document_id,
        "chunk_id": chunk_id,
    }


@pytest.fixture
def postgres_mode(monkeypatch):
    monkeypatch.setattr(config.settings, "persistence_backend", "postgres")


def _patch_mentions(monkeypatch, mapping):
    from app.db import repository as repo

    def fake(tag, session=None):
        return mapping.get(tag.strip().upper(), [])

    monkeypatch.setattr(repo, "list_asset_mentions_by_tag", fake)


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------


def test_certificate_expired_rule(monkeypatch):
    _patch_mentions(
        monkeypatch,
        {
            "BLR-118": [
                _mention(
                    "A1. BLR-118 - Annual pressure test certificate: EXPIRED (01-Feb-2025). "
                    "Required by Factories Act Section 31 and PESO. Status: NON-COMPLIANT."
                )
            ]
        },
    )
    gaps = C.evaluate_asset_gaps("BLR-118")
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap["gap_type"] == C.GAP_CERTIFICATE_EXPIRED
    assert gap["severity"] == "high"
    assert gap["evidence"] and gap["evidence"][0]["text"]
    assert gap["evidence"][0]["document_id"] == "doc-1"
    assert "Factories Act" in (gap["standard_or_policy"] or "")


def test_calibration_overdue_rule(monkeypatch):
    _patch_mentions(
        monkeypatch,
        {
            "TK-482": [
                _mention(
                    "C1. TK-482 Level Transmitter LT-482-01 - Calibration: OVERDUE by 45 days. "
                    "Required every 6 months."
                )
            ]
        },
    )
    gaps = C.evaluate_asset_gaps("TK-482")
    assert [g["gap_type"] for g in gaps] == [C.GAP_CALIBRATION_OVERDUE]
    assert "45 days" in gaps[0]["reason"]
    assert gaps[0]["evidence"][0]["chunk_id"] == "doc-1-0"


def test_vibration_followup_rule_fires_without_closure(monkeypatch):
    _patch_mentions(
        monkeypatch,
        {
            "P-101": [
                _mention("P-101 - Vibration inspection: NON-COMPLIANT. Reading 6.2 mm/s exceeds OISD-137 limit.")
            ]
        },
    )
    gaps = C.evaluate_asset_gaps("P-101")
    assert [g["gap_type"] for g in gaps] == [C.GAP_INSPECTION_OVERDUE]
    assert gaps[0]["standard_or_policy"] == "OISD-137"


def test_vibration_followup_suppressed_when_closure_present(monkeypatch):
    _patch_mentions(
        monkeypatch,
        {
            "P-101": [
                _mention(
                    "P-101 - Vibration inspection: NON-COMPLIANT. Reading exceeds OISD-137 limit. "
                    "Alignment check completed and vibration re-baselined within limit. NCR closed."
                )
            ]
        },
    )
    gaps = C.evaluate_asset_gaps("P-101")
    assert all(g["gap_type"] != C.GAP_INSPECTION_OVERDUE for g in gaps)


# ---------------------------------------------------------------------------
# Attribution / truthfulness guarantees
# ---------------------------------------------------------------------------


def test_summary_line_does_not_cross_contaminate(monkeypatch):
    """A multi-asset summary line must not create a certificate gap for P-101."""
    _patch_mentions(
        monkeypatch,
        {
            "P-101": [
                _mention(
                    "Non-compliant: 3 - BLR-118 pressure cert, P-101 vibration, TK-482 calibration."
                )
            ]
        },
    )
    gaps = C.evaluate_asset_gaps("P-101")
    assert all(g["gap_type"] != C.GAP_CERTIFICATE_EXPIRED for g in gaps)
    assert all(g["gap_type"] != C.GAP_CALIBRATION_OVERDUE for g in gaps)


def test_no_evidence_no_gap(monkeypatch):
    _patch_mentions(
        monkeypatch,
        {"P-102": [_mention("P-102 - Vibration inspection: COMPLIANT. Reading 3.1 mm/s within limit.")]},
    )
    assert C.evaluate_asset_gaps("P-102") == []


def test_every_gap_has_evidence(monkeypatch):
    _patch_mentions(
        monkeypatch,
        {
            "BLR-118": [
                _mention("BLR-118 - Annual pressure test certificate: EXPIRED (01-Feb-2025).")
            ]
        },
    )
    for gap in C.evaluate_asset_gaps("BLR-118"):
        assert gap["evidence"], "each gap must carry supporting evidence"
        assert all(ev["text"] for ev in gap["evidence"])


def test_unknown_asset_returns_no_gaps(monkeypatch):
    _patch_mentions(monkeypatch, {})
    assert C.evaluate_asset_gaps("ZZ-999") == []


# ---------------------------------------------------------------------------
# Aggregate endpoint + filters + JSON-mode safety
# ---------------------------------------------------------------------------


def test_json_mode_returns_safe_empty(monkeypatch):
    monkeypatch.setattr(config.settings, "persistence_backend", "json")
    result = C.evaluate_gaps()
    assert result["mode"] == "json"
    assert result["count"] == 0
    assert result["gaps"] == []


def test_filters_apply(monkeypatch, postgres_mode):
    from app.db import repository as repo

    monkeypatch.setattr(repo, "list_assets", lambda session=None: [{"tag": "BLR-118"}, {"tag": "P-102"}])
    _patch_mentions(
        monkeypatch,
        {
            "BLR-118": [_mention("BLR-118 - Annual pressure test certificate: EXPIRED (01-Feb-2025).")],
            "P-102": [_mention("P-102 - Vibration inspection: COMPLIANT.")],
        },
    )
    high = C.evaluate_gaps(severity="high")
    assert high["count"] == 1 and high["gaps"][0]["asset_tag"] == "BLR-118"
    typed = C.evaluate_gaps(gap_type=C.GAP_CERTIFICATE_EXPIRED)
    assert typed["count"] == 1
    none = C.evaluate_gaps(gap_type="does_not_exist")
    assert none["count"] == 0


# ---------------------------------------------------------------------------
# Helper units
# ---------------------------------------------------------------------------


def test_parse_date_and_standard():
    from datetime import date

    assert C._parse_date("EXPIRED (01-Feb-2025)") == date(2025, 2, 1)
    assert C._parse_date("last tested: September 2023") == date(2023, 9, 1)
    assert C._parse_date("no date here") is None
    assert "OISD-137" in (C._detect_standard("exceeds OISD-137 limit") or "")


# ---------------------------------------------------------------------------
# Evidence package
# ---------------------------------------------------------------------------


def _patch_package_repo(monkeypatch):
    from app.db import repository as repo

    _patch_mentions(
        monkeypatch,
        {
            "P-101": [
                _mention(
                    "P-101 - Vibration inspection: NON-COMPLIANT. Reading 6.2 mm/s exceeds OISD-137 limit."
                )
            ]
        },
    )
    monkeypatch.setattr(
        repo,
        "get_asset_facts_by_tag",
        lambda tag, session=None: {
            "asset": {"tag": "P-101", "display_name": "Centrifugal Pump P-101"},
            "mention_count": 3,
            "document_count": 1,
            "documents": [{"id": "doc-1", "filename": "inspection.pdf", "chunk_count": 4}],
            "entities": [],
        },
    )
    monkeypatch.setattr(
        repo,
        "list_asset_timeline_by_tag",
        lambda tag, session=None: [
            {
                "event_type": "inspection",
                "text_preview": "Vibration 6.2 mm/s exceeds limit",
                "filename": "inspection.pdf",
                "document_id": "doc-1",
                "chunk_id": "doc-1-0",
            },
            {
                "event_type": "work_order",
                "text_preview": "Replaced mechanical seal on P-101",
                "filename": "work_orders.csv",
                "document_id": "doc-2",
                "chunk_id": "doc-2-5",
            },
        ],
    )


def test_evidence_package_generation_and_download(monkeypatch, postgres_mode):
    _patch_package_repo(monkeypatch)
    pkg = EP.generate_evidence_package("P-101", "audit")

    assert pkg["asset_tag"] == "P-101"
    assert pkg["package_id"].startswith("P-101-audit-")
    assert pkg["compliance_gaps"], "package should surface computed gaps"
    assert pkg["inspection_findings"] and pkg["maintenance_evidence"]
    assert pkg["recommended_actions"]
    assert pkg["download_url"].endswith("/download")

    path = EP.resolve_package_path(pkg["package_id"])
    assert path is not None and path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "Citation Index" in text
    assert "Recommended Corrective Actions" in text
    assert "Disclaimer" in text
    assert "not** an audit certification" in text
    path.unlink()  # keep the exports dir clean between runs


def test_package_path_traversal_is_blocked(postgres_mode):
    assert EP.resolve_package_path("../../etc/passwd") is None
    assert EP.resolve_package_path("does-not-exist-xyz") is None


def test_package_requires_postgres(monkeypatch):
    monkeypatch.setattr(config.settings, "persistence_backend", "json")
    with pytest.raises(EP.ComplianceModeError):
        EP.generate_evidence_package("P-101", "audit")


def test_package_rejects_empty_tag(postgres_mode):
    with pytest.raises(ValueError):
        EP.generate_evidence_package("", "audit")
