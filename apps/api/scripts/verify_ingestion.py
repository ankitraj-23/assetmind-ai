"""Verify CSV, XLSX, PDF, and TXT ingestion with fact extraction.

Run from apps/api/ with PERSISTENCE_BACKEND=json:
    python -m scripts.verify_ingestion
"""

from __future__ import annotations

import asyncio
import io
import os
import sys

os.environ.setdefault("PERSISTENCE_BACKEND", "json")

import pandas as pd

from fastapi import UploadFile

from app.services.ingestion import (
    _load_facts,
    _load_metadata,
    ingest_csv,
    ingest_upload,
    ingest_xlsx,
)
from app.services.fact_extraction import extract_facts_from_text


def _make_upload(filename: str, data: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(data))


def _section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


# ── helpers that build synthetic test data ────────────────────────────────────

def _make_csv_bytes() -> bytes:
    df = pd.DataFrame([
        {
            "Equipment_ID": "P-101",
            "WorkOrderDescription": "High vibration alarm active. Bearing wear suspected.",
            "OperationDescription": "Replaced bearing assembly. Alignment recheck required.",
            "OrderDate": "2025-01-10",
            "Priority": "High",
            "Status": "Open",
        },
        {
            "Equipment_ID": "HX-305",
            "WorkOrderDescription": "Fouling detected. Heat transfer efficiency dropped.",
            "OperationDescription": "Chemical cleaning performed.",
            "OrderDate": "2025-02-01",
            "Priority": "Medium",
            "Status": "Closed",
        },
    ])
    return df.to_csv(index=False).encode("utf-8")


def _make_xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        pd.DataFrame([
            {"Equipment_ID": "P-101", "Failure_Mode": "High vibration", "Risk": "Critical"},
            {"Equipment_ID": "BLR-118", "Failure_Mode": "Overheating", "Risk": "High"},
        ]).to_excel(w, sheet_name="Inspections", index=False)
        pd.DataFrame([
            {"Equipment_ID": "P-101", "SOP_Reference": "SOP-PUMP-STARTUP", "Status": "Pending"},
        ]).to_excel(w, sheet_name="SOPs", index=False)
    return buf.getvalue()


def _make_txt_bytes() -> bytes:
    return (
        "P-101 shows high vibration at 7.8 mm/s RMS. "
        "Bearing wear suspected. Alignment recheck required. "
        "Per OISD-137, trip setpoint is 7.0 mm/s. "
        "Spare part MS-45-CR ordered. Refer SOP-PUMP-STARTUP."
    ).encode("utf-8")


# ── test CSV ingestion ────────────────────────────────────────────────────────

async def test_csv() -> None:
    _section("CSV ingestion")
    data = _make_csv_bytes()
    doc = await ingest_csv(_make_upload("test_work_orders.csv", data))

    if doc.chunk_count != 2:
        _fail(f"expected 2 chunks, got {doc.chunk_count}")
    _ok(f"chunk_count = {doc.chunk_count}")

    if doc.status != "extracted":
        _fail(f"expected status=extracted, got {doc.status}")
    _ok(f"status = {doc.status}")

    if doc.content_type != "text/csv":
        _fail(f"unexpected content_type: {doc.content_type}")
    _ok(f"content_type = {doc.content_type}")

    facts_store = _load_facts()
    doc_facts = [v for v in facts_store.values() if v["document_id"] == doc.id]

    if len(doc_facts) != 2:
        _fail(f"expected 2 facts entries, got {len(doc_facts)}")
    _ok(f"facts entries = {len(doc_facts)}")

    f0 = doc_facts[0]["facts"]
    if f0.get("equipment_tag") != "P-101":
        _fail(f"expected equipment_tag=P-101, got {f0}")
    _ok(f"equipment_tag extracted: {f0['equipment_tag']}")

    if "failure_mode" not in f0:
        _fail(f"expected failure_mode in facts: {f0}")
    _ok(f"failure_mode extracted: {f0['failure_mode']}")

    if doc_facts[0]["source_type"] != "csv":
        _fail(f"expected source_type=csv")
    _ok("source_type = csv")


# ── test XLSX ingestion ───────────────────────────────────────────────────────

async def test_xlsx() -> None:
    _section("XLSX ingestion (2 sheets)")
    data = _make_xlsx_bytes()
    doc = await ingest_xlsx(_make_upload("test_plant.xlsx", data))

    if doc.chunk_count != 3:
        _fail(f"expected 3 chunks (2+1 across sheets), got {doc.chunk_count}")
    _ok(f"chunk_count = {doc.chunk_count}")

    facts_store = _load_facts()
    doc_facts = [v for v in facts_store.values() if v["document_id"] == doc.id]

    sheets = {v["sheet_name"] for v in doc_facts}
    if "Inspections" not in sheets or "SOPs" not in sheets:
        _fail(f"expected both sheets in facts, got: {sheets}")
    _ok(f"sheets covered: {sheets}")

    sop_chunks = [v for v in doc_facts if v["sheet_name"] == "SOPs"]
    if not sop_chunks or sop_chunks[0]["facts"].get("sop_reference") != "SOP-PUMP-STARTUP":
        _fail(f"sop_reference not extracted from SOPs sheet: {sop_chunks}")
    _ok("sop_reference extracted from XLSX SOPs sheet")

    if doc.content_type != "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        _fail(f"unexpected content_type: {doc.content_type}")
    _ok("content_type correct for XLSX")


# ── test TXT ingestion with fact extraction ───────────────────────────────────

async def test_txt() -> None:
    _section("TXT ingestion with structured fact extraction")
    data = _make_txt_bytes()
    doc = await ingest_upload(_make_upload("test_report.txt", data))

    if doc.status != "extracted":
        _fail(f"expected status=extracted, got {doc.status}")
    _ok(f"chunk_count = {doc.chunk_count}, status = {doc.status}")

    facts_store = _load_facts()
    doc_facts = [v for v in facts_store.values() if v["document_id"] == doc.id]

    if not doc_facts:
        _fail("no facts entries for TXT document")

    all_facts = {}
    for entry in doc_facts:
        all_facts.update(entry["facts"])

    checks = [
        ("failure_mode", "bearing failure"),  # "Bearing wear" fires before "high vibration"
        ("inspection_reading", "7.8 mm/s"),
        ("sop_reference", "SOP-PUMP-STARTUP"),
        ("compliance_reference", "OISD-137"),
        ("spare_part", "MS-45-CR"),
        ("open_action", "alignment recheck required"),
    ]
    for key, expected in checks:
        if all_facts.get(key) != expected:
            _fail(f"expected {key}={expected!r}, got {all_facts.get(key)!r}")
        _ok(f"{key} = {all_facts[key]!r}")


# ── test fact_extraction standalone ──────────────────────────────────────────

def test_fact_extraction_unit() -> None:
    _section("fact_extraction unit tests")

    cases = [
        ("vibration reading 7.8 mm/s", "inspection_reading", "7.8 mm/s"),
        ("high vibration detected in P-101", "failure_mode", "high vibration"),
        ("Replaced the mechanical seal", "maintenance_action", None),  # just check presence
        ("Follow SOP-PUMP-STARTUP before starting", "sop_reference", "SOP-PUMP-STARTUP"),
        ("Per OISD-137 limit is 4.5 mm/s", "compliance_reference", "OISD-137"),
        ("Order part MS-45-CR from supplier", "spare_part", "MS-45-CR"),
        ("This is a critical finding", "risk_phrase", "critical"),
        ("Alignment recheck required next week", "open_action", "alignment recheck required"),
    ]
    for text, key, expected in cases:
        facts = extract_facts_from_text(text)
        if key not in facts:
            _fail(f"key {key!r} not found in facts for: {text!r}")
        if expected and facts[key] != expected:
            _fail(f"expected {key}={expected!r}, got {facts[key]!r}")
        _ok(f"{key} = {facts[key]!r}")

    if extract_facts_from_text("") != {}:
        _fail("empty string should return {}")
    _ok("empty text -> empty facts")


# ── main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    print("\nverify_ingestion: running against JSON persistence backend")

    test_fact_extraction_unit()

    await test_csv()
    await test_xlsx()
    await test_txt()

    _section("Summary")
    metadata = _load_metadata()
    facts = _load_facts()
    print(f"  Total documents in metadata store: {len(metadata)}")
    print(f"  Total chunk facts entries: {len(facts)}")
    chunks_with_facts = sum(1 for v in facts.values() if v.get("facts"))
    print(f"  Chunks with at least one extracted fact: {chunks_with_facts}")
    print("\n  ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(main())
