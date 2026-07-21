"""End-to-end verification for the compliance and evidence-package agents.

Runs the real FastAPI routes in-process (no separate server needed) against the
seeded Postgres demo database and checks the guarantees from the milestone spec:

* the gaps endpoint works and every gap has a reason + actual evidence;
* the asset filter works;
* an evidence package is generated and the file exists on disk;
* the generated Markdown contains citations and recommended actions;
* an unknown asset returns a safe empty response (never fabricated findings).

Usage::

    PERSISTENCE_BACKEND=postgres \\
    DATABASE_URL=postgresql+psycopg://assetmind:assetmind@localhost:5432/assetmind \\
    .venv/bin/python -m scripts.verify_compliance_agent
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from app.core import config

# Force Postgres so the compliance/evidence routes read the seeded demo data.
config.settings.persistence_backend = "postgres"

DEMO_ASSET = "P-101"
UNKNOWN_ASSET = "ZZ-999"


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def _ok(msg: str) -> None:
    print(f"OK: {msg}")


async def _run() -> None:
    from app.main import app
    from app.services import evidence_package as evidence_service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://verify") as client:
        # 1. Gaps endpoint works and returns evidence-backed gaps.
        resp = await client.get("/agents/compliance/gaps")
        if resp.status_code != 200:
            _fail(f"/agents/compliance/gaps returned {resp.status_code}: {resp.text}")
        payload = resp.json()
        if payload.get("mode") != "postgres":
            _fail(f"expected postgres mode, got {payload.get('mode')} — is the demo DB seeded?")
        gaps = payload.get("gaps", [])
        if not gaps:
            _fail("no compliance gaps detected — expected findings from the demo dataset.")
        _ok(f"gaps endpoint returned {len(gaps)} gap(s).")

        for gap in gaps:
            if not gap.get("reason"):
                _fail(f"gap {gap.get('gap_type')} for {gap.get('asset_tag')} has no reason.")
            evidence = gap.get("evidence") or []
            if not evidence or not any(ev.get("text") for ev in evidence):
                _fail(f"gap {gap.get('gap_type')} for {gap.get('asset_tag')} has no real evidence.")
        _ok("every gap has a reason and at least one real evidence snippet.")

        # 2. Asset filter works.
        resp = await client.get(f"/agents/compliance/assets/{DEMO_ASSET}")
        if resp.status_code != 200:
            _fail(f"/agents/compliance/assets/{DEMO_ASSET} returned {resp.status_code}")
        asset_payload = resp.json()
        if any(g["asset_tag"] != DEMO_ASSET for g in asset_payload.get("gaps", [])):
            _fail("asset filter leaked gaps from other assets.")
        _ok(f"asset filter works ({asset_payload['count']} gap(s) for {DEMO_ASSET}).")

        # 3. Evidence package is generated.
        resp = await client.post(
            "/agents/evidence-package", json={"asset_tag": DEMO_ASSET, "package_type": "audit"}
        )
        if resp.status_code != 200:
            _fail(f"evidence-package generation returned {resp.status_code}: {resp.text}")
        pkg = resp.json()
        for key in ("package_id", "summary", "compliance_gaps", "recommended_actions", "download_url"):
            if key not in pkg:
                _fail(f"evidence package missing key '{key}'.")
        _ok(f"evidence package generated: {pkg['package_id']}")

        # 4. Generated file exists on disk.
        path = evidence_service.resolve_package_path(pkg["package_id"])
        if path is None or not path.is_file():
            _fail("generated evidence-package file does not exist on disk.")
        _ok(f"generated file exists: {path}")

        # 5. Markdown contains citations and recommended actions.
        markdown = path.read_text(encoding="utf-8")
        if "Citation Index" not in markdown:
            _fail("generated Markdown has no citation index.")
        if "Recommended Corrective Actions" not in markdown:
            _fail("generated Markdown has no recommended actions section.")
        if "audit certification" not in markdown:
            _fail("generated Markdown is missing the decision-support disclaimer.")
        _ok("generated Markdown contains citations, recommended actions, and disclaimer.")

        # 6. Download route serves the file.
        resp = await client.get(pkg["download_url"])
        if resp.status_code != 200 or "Evidence Package" not in resp.text:
            _fail(f"download route failed ({resp.status_code}).")
        _ok("download route serves the generated package.")

        # 7. Unknown asset returns a safe, empty (non-fabricated) response.
        resp = await client.get(f"/agents/compliance/assets/{UNKNOWN_ASSET}")
        if resp.status_code != 200:
            _fail(f"unknown-asset gaps returned {resp.status_code}")
        if resp.json().get("count", -1) != 0:
            _fail("unknown asset produced fabricated gaps — must be empty.")
        resp = await client.post(
            "/agents/evidence-package", json={"asset_tag": UNKNOWN_ASSET, "package_type": "audit"}
        )
        if resp.status_code != 200 or resp.json().get("compliance_gaps"):
            _fail("unknown asset produced fabricated evidence-package findings.")
        _ok("unknown asset returns a safe, empty response (no fabricated findings).")

    print("\n--- Compliance Agent Verification PASSED ---")


def main() -> int:
    try:
        asyncio.run(_run())
    except httpx.HTTPError as exc:  # pragma: no cover - network/transport errors
        _fail(f"HTTP transport error: {exc}")
    except Exception as exc:  # pragma: no cover
        _fail(f"unexpected error: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
