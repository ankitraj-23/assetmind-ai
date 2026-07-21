"""Genuine, citation-backed evidence-package generation.

``generate_evidence_package`` assembles a substantive Markdown report for an
asset entirely from persisted evidence (asset facts, classified timeline
events, and the computed compliance gaps), writes it to
``apps/api/storage/exports/`` under a sanitised filename, and returns a
structured summary plus a working download URL. Nothing is fabricated: if the
evidence is thin, the report says so in its "Missing Evidence" section.

The package store is the generated file on disk (not an in-memory dict); the
download route re-resolves the sanitised path from disk.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.core import config
from app.core.config import settings
from app.services import compliance as compliance_service

EXPORTS_SUBDIR = "exports"
PACKAGE_SUFFIX = ".md"

# Timeline event types treated as inspection vs maintenance evidence.
_INSPECTION_EVENT_TYPES = {"inspection", "failure", "compliance"}
_MAINTENANCE_EVENT_TYPES = {"work_order", "procedure"}


# ---------------------------------------------------------------------------
# Path + filename safety
# ---------------------------------------------------------------------------


def _exports_dir() -> Path:
    path = Path(settings.storage_dir) / EXPORTS_SUBDIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_component(value: str, fallback: str) -> str:
    """Collapse a tag/type to a safe, path-free filename component."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", (value or "").strip())
    cleaned = cleaned.strip(".-")
    return cleaned[:64] or fallback


def resolve_package_path(package_id: str) -> Optional[Path]:
    """Resolve a package id to its on-disk path, refusing traversal escapes."""
    safe_id = _sanitize_component(package_id, "")
    if not safe_id:
        return None
    exports = _exports_dir().resolve()
    candidate = (exports / f"{safe_id}{PACKAGE_SUFFIX}").resolve()
    # Guard against any residual traversal: the resolved file must sit in exports.
    if exports != candidate.parent:
        return None
    if not candidate.is_file():
        return None
    return candidate


# ---------------------------------------------------------------------------
# Evidence assembly
# ---------------------------------------------------------------------------


def _classify_timeline(tag: str, session=None) -> tuple[list[dict], list[dict]]:
    """Split an asset's timeline into inspection vs maintenance evidence lists."""
    from app.db import repository as repo

    inspection: list[dict] = []
    maintenance: list[dict] = []
    seen: set[str] = set()
    for event in repo.list_asset_timeline_by_tag(tag, session=session):
        text = event.get("text_preview")
        if not text:
            continue
        key = f"{event.get('chunk_id')}|{text[:60]}"
        if key in seen:
            continue
        seen.add(key)
        finding = {
            "text": text,
            "source": event.get("filename"),
            "document_id": event.get("document_id"),
            "chunk_id": event.get("chunk_id"),
            "category": event.get("event_type"),
        }
        if event.get("event_type") in _INSPECTION_EVENT_TYPES:
            inspection.append(finding)
        elif event.get("event_type") in _MAINTENANCE_EVENT_TYPES:
            maintenance.append(finding)
    return inspection[:12], maintenance[:12]


def _derive_missing_evidence(
    gaps: list[dict], inspection: list[dict], maintenance: list[dict]
) -> list[str]:
    missing: list[str] = []
    gap_types = {g["gap_type"] for g in gaps}
    if compliance_service.GAP_INSPECTION_OVERDUE in gap_types:
        missing.append("No completed follow-up inspection is recorded for the flagged exceedance.")
    if compliance_service.GAP_REPEATED_FAILURE_NO_RCA in gap_types:
        missing.append("No formal root-cause analysis is on file for the recurring failures.")
    if compliance_service.GAP_SAFETY_PROCEDURE_MISSING in gap_types:
        missing.append("No LOTO / permit-to-work evidence is linked to safety-critical maintenance.")
    if not inspection:
        missing.append("No inspection evidence was found for this asset in the indexed corpus.")
    if not maintenance:
        missing.append("No maintenance/work-order evidence was found for this asset.")
    return missing


def _summarize(tag: str, facts: Optional[dict], gaps: list[dict]) -> str:
    asset = (facts or {}).get("asset") or {}
    display = asset.get("display_name") or tag
    label = display if display == tag else f"{display} ({tag})"
    doc_count = (facts or {}).get("document_count", 0)
    mention_count = (facts or {}).get("mention_count", 0)
    high = sum(1 for g in gaps if g["severity"] == "high")
    return (
        f"{label} is supported by {mention_count} evidence mention(s) across "
        f"{doc_count} source document(s). The compliance engine detected {len(gaps)} open "
        f"gap(s), {high} at high severity, all backed by cited evidence."
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _cite(item: dict) -> str:
    doc = item.get("document_id")
    chunk = item.get("chunk_id")
    doc_s = doc[:12] + "…" if doc and len(doc) > 12 else (doc or "—")
    chunk_s = chunk[:16] + "…" if chunk and len(chunk) > 16 else (chunk or "—")
    return f"{item.get('source') or '—'} · doc `{doc_s}` · chunk `{chunk_s}`"


def _render_markdown(response: dict) -> str:
    tag = response["asset_tag"]
    lines: list[str] = []
    lines.append(f"# Evidence Package — {tag}")
    lines.append("")
    lines.append(f"- **Package ID:** `{response['package_id']}`")
    lines.append(f"- **Package type:** {response['package_type']}")
    lines.append(f"- **Generated at (UTC):** {response['generated_at']}")
    lines.append("")
    lines.append("## 1. Asset Summary")
    lines.append("")
    lines.append(response["summary"])
    lines.append("")

    lines.append("## 2. Included Source Documents")
    lines.append("")
    if response["included_documents"]:
        lines.append("| Document | Chunks | Document ID |")
        lines.append("| --- | --- | --- |")
        for d in response["included_documents"]:
            lines.append(
                f"| {d.get('filename') or '—'} | {d.get('chunk_count') if d.get('chunk_count') is not None else '—'} "
                f"| `{d.get('document_id') or '—'}` |"
            )
    else:
        lines.append("_No source documents are linked to this asset._")
    lines.append("")

    lines.append("## 3. Compliance Findings")
    lines.append("")
    if response["compliance_gaps"]:
        for i, g in enumerate(response["compliance_gaps"], 1):
            lines.append(f"### 3.{i} {g['gap_type']} — severity: {g['severity']}")
            lines.append("")
            lines.append(f"- **Reason:** {g['reason']}")
            if g.get("standard_or_policy"):
                lines.append(f"- **Standard / policy:** {g['standard_or_policy']}")
            lines.append(f"- **Recommended action:** {g['recommended_action']}")
            if g.get("evidence"):
                lines.append("- **Evidence:**")
                for ev in g["evidence"]:
                    lines.append(f"  - \"{ev['text']}\" — {_cite(ev)}")
            lines.append("")
    else:
        lines.append("_No compliance gaps were detected from the available evidence._")
    lines.append("")

    lines.append("## 4. Inspection Evidence")
    lines.append("")
    if response["inspection_findings"]:
        for f in response["inspection_findings"]:
            lines.append(f"- \"{f['text']}\" — {_cite(f)}")
    else:
        lines.append("_No inspection evidence found._")
    lines.append("")

    lines.append("## 5. Maintenance Evidence")
    lines.append("")
    if response["maintenance_evidence"]:
        for f in response["maintenance_evidence"]:
            lines.append(f"- \"{f['text']}\" — {_cite(f)}")
    else:
        lines.append("_No maintenance evidence found._")
    lines.append("")

    lines.append("## 6. Missing Evidence")
    lines.append("")
    if response["missing_evidence"]:
        for m in response["missing_evidence"]:
            lines.append(f"- {m}")
    else:
        lines.append("_No material evidence gaps identified._")
    lines.append("")

    lines.append("## 7. Recommended Corrective Actions")
    lines.append("")
    if response["recommended_actions"]:
        for i, a in enumerate(response["recommended_actions"], 1):
            lines.append(f"{i}. {a}")
    else:
        lines.append("_No corrective actions required from the current evidence._")
    lines.append("")

    lines.append("## 8. Citation Index")
    lines.append("")
    citations = _gather_citations(response)
    if citations:
        lines.append("| # | Source | Document ID | Chunk ID |")
        lines.append("| --- | --- | --- | --- |")
        for i, c in enumerate(citations, 1):
            lines.append(
                f"| {i} | {c.get('source') or '—'} | `{c.get('document_id') or '—'}` "
                f"| `{c.get('chunk_id') or '—'}` |"
            )
    else:
        lines.append("_No chunk-addressable citations available._")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "> **Disclaimer:** This package is automated decision-support compiled from indexed "
        "plant documents. It is **not** an audit certification. All findings must be verified "
        "by an authorised competent person before any compliance or safety decision is made."
    )
    lines.append("")
    return "\n".join(lines)


def _gather_citations(response: dict) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    buckets = (
        [ev for g in response["compliance_gaps"] for ev in g.get("evidence", [])]
        + response["inspection_findings"]
        + response["maintenance_evidence"]
    )
    for item in buckets:
        key = (item.get("document_id"), item.get("chunk_id"))
        if key in seen or (key[0] is None and key[1] is None):
            continue
        seen.add(key)
        out.append(
            {
                "source": item.get("source"),
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


class ComplianceModeError(RuntimeError):
    """Raised when evidence-package generation is attempted outside Postgres mode."""


def generate_evidence_package(
    asset_tag: str, package_type: str = "audit", session=None
) -> dict[str, Any]:
    """Compile, persist, and summarise an evidence package for an asset.

    Raises :class:`ComplianceModeError` in JSON mode and :class:`ValueError` when
    the asset tag is empty. An unknown (but well-formed) tag still produces a
    valid, honest package that reports the absence of evidence rather than
    fabricating findings.
    """
    if not config.use_postgres():
        raise ComplianceModeError(
            "Evidence packages require PERSISTENCE_BACKEND=postgres."
        )

    tag = (asset_tag or "").strip().upper()
    if not tag:
        raise ValueError("asset_tag is required.")
    pkg_type = _sanitize_component(package_type or "audit", "audit").lower()

    from app.db import repository as repo

    facts = repo.get_asset_facts_by_tag(tag, session=session)
    gaps = compliance_service.evaluate_asset_gaps(tag, session=session)
    inspection, maintenance = _classify_timeline(tag, session=session)

    included_documents = [
        {
            "document_id": d.get("id"),
            "filename": d.get("filename") or d.get("original_filename"),
            "chunk_count": d.get("chunk_count"),
        }
        for d in ((facts or {}).get("documents") or [])
    ]

    recommended_actions: list[str] = []
    for g in gaps:
        action = g["recommended_action"]
        if action not in recommended_actions:
            recommended_actions.append(action)

    generated_at = datetime.now(timezone.utc).isoformat()
    package_id = (
        f"{_sanitize_component(tag, 'asset')}-{pkg_type}-"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:8]}"
    )

    response: dict[str, Any] = {
        "package_id": package_id,
        "asset_tag": tag,
        "package_type": pkg_type,
        "generated_at": generated_at,
        "summary": _summarize(tag, facts, gaps),
        "included_documents": included_documents,
        "compliance_gaps": gaps,
        "inspection_findings": inspection,
        "maintenance_evidence": maintenance,
        "missing_evidence": _derive_missing_evidence(gaps, inspection, maintenance),
        "recommended_actions": recommended_actions,
        "download_url": f"/agents/evidence-package/{package_id}/download",
    }

    markdown = _render_markdown(response)
    path = _exports_dir() / f"{package_id}{PACKAGE_SUFFIX}"
    path.write_text(markdown, encoding="utf-8")

    return response
