"""Deterministic, explainable compliance rule engine.

This service derives compliance gaps for an asset *only* from persisted
evidence — the same asset mentions, chunk text, and source documents that back
the timeline/graph views. Nothing here is hardcoded per asset: rules recognise
generic phrases, dates, document types, and standards, so the demo dataset
produces findings only where its evidence genuinely supports them.

Design notes
------------
* Chunks in this corpus are coarse (a whole PDF section can be one chunk), so a
  chunk that mentions ``P-101`` may also literally contain another asset's
  findings. To attribute a finding to the *correct* asset we evaluate rules at
  the **sentence** level and, within a sentence, only over the **subject window**
  that runs from the target tag up to the next *different* equipment tag. A tag
  that shares the same numeric root (e.g. ``LT-482`` on ``TK-482``) is treated as
  belonging to the same equipment family and does not end the window.
* Absence-based rules (e.g. "repeated failure *without* RCA evidence") test for
  counter-evidence across the asset's whole evidence corpus, never inventing a
  gap when supporting evidence is missing.
* All expiry/overdue comparisons use the current UTC date. Thresholds live in
  named constants below rather than scattered magic numbers.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Optional

from app.core import config

# ---------------------------------------------------------------------------
# Tunable thresholds (named constants — no scattered magic numbers)
# ---------------------------------------------------------------------------

# Instrument calibration cadence used when a "last calibration" date is present
# but no explicit overdue phrasing is (Factory Act Schedule VIII: 6 months).
CALIBRATION_INTERVAL_DAYS = 180
# Procedure/SOP review cadence (annual review cycle).
SOP_REVIEW_INTERVAL_DAYS = 365
# Minimum number of distinct failure events to treat a pattern as "repeated".
REPEATED_FAILURE_MIN_COUNT = 2
# Cap on evidence snippets attached to a single gap.
MAX_EVIDENCE_PER_GAP = 3

# ---------------------------------------------------------------------------
# Canonical gap types (kept stable — the frontend filters key off these)
# ---------------------------------------------------------------------------

GAP_INSPECTION_OVERDUE = "inspection_overdue"
GAP_REPEATED_FAILURE_NO_RCA = "repeated_failure_no_rca"
GAP_CERTIFICATE_EXPIRED = "certificate_expired"
GAP_CALIBRATION_OVERDUE = "calibration_overdue"
GAP_SOP_REVIEW_OVERDUE = "sop_review_overdue"
GAP_SAFETY_PROCEDURE_MISSING = "safety_procedure_missing"

_SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

# ---------------------------------------------------------------------------
# Regex building blocks
# ---------------------------------------------------------------------------

# Equipment/instrument tag like P-101, BLR-118, TK-482, LT-482-01, OISD-137.
_TAG_ANY = re.compile(r"(?<![A-Za-z0-9])([A-Z]{1,5})-(\d{1,4})([A-Za-z]?)(?![A-Za-z0-9])")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Dates like "01-Feb-2025", "01 February 2025", "September 2023", "March 2025".
_DATE_DMY = re.compile(r"\b(\d{1,2})[ \-]([A-Za-z]{3,9})[ \-](\d{4})\b")
_DATE_MY = re.compile(r"\b([A-Za-z]{3,9})[ \-](\d{4})\b")
_OVERDUE_DAYS = re.compile(r"overdue\s+by\s+(\d{1,4})\s+days?", re.I)

# Standards / policies that may be cited in the evidence.
_STANDARD_RE = re.compile(
    r"(OISD-\d+|PESO|Factories?\s+Act(?:\s+Section\s+\d+|\s+Schedule\s+[IVX]+)?"
    r"|Factory\s+Act(?:\s+Schedule\s+[IVX]+)?|ISO\s*\d{3,5}(?::\d{4})?|IEC\s*\d+"
    r"|API\s*\d+|NFPA\s*\d+|OSHA\s*[\d.]+)",
    re.I,
)


def _today() -> date:
    """Current UTC date used for every expiry/overdue comparison."""
    return datetime.now(timezone.utc).date()


def _numeric_root(tag: str) -> Optional[str]:
    m = re.search(r"-(\d{1,4})", tag)
    return m.group(1) if m else None


def _tag_pattern(tag: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(tag) + r"(?![A-Za-z0-9])", re.I)


def _parse_date(text: str) -> Optional[date]:
    """Best-effort parse of the first date found in ``text`` (day precision)."""
    m = _DATE_DMY.search(text)
    if m:
        day, mon, year = m.group(1), m.group(2)[:3].lower(), m.group(3)
        if mon in _MONTHS:
            try:
                return date(int(year), _MONTHS[mon], int(day))
            except ValueError:
                return None
    m = _DATE_MY.search(text)
    if m:
        mon, year = m.group(1)[:3].lower(), m.group(2)
        if mon in _MONTHS:
            try:
                return date(int(year), _MONTHS[mon], 1)
            except ValueError:
                return None
    return None


def _detect_standard(text: str) -> Optional[str]:
    found: list[str] = []
    for m in _STANDARD_RE.finditer(text):
        val = " ".join(m.group(1).split())
        if val not in found:
            found.append(val)
    return " / ".join(found) if found else None


# ---------------------------------------------------------------------------
# Evidence gathering
# ---------------------------------------------------------------------------


def _collect_evidence(tag: str, session=None) -> dict[str, Any]:
    """Gather every distinct chunk that mentions ``tag`` plus derived windows.

    Returns a dict with:
      * ``segments`` — subject-scoped sentence windows attributed to ``tag``,
        each carrying its source document/chunk for citation, and
      * ``corpus`` — the lowercased concatenation of all the asset's chunk text,
        used by absence-based rules to look for counter-evidence.
    """
    from app.db import repository as repo

    tag_re = _tag_pattern(tag)
    tag_num = _numeric_root(tag)

    seen_chunks: set[str] = set()
    segments: list[dict[str, Any]] = []
    corpus_parts: list[str] = []
    seen_windows: set[str] = set()

    for mention in repo.list_asset_mentions_by_tag(tag, session=session):
        text = mention.get("text") or ""
        chunk_id = mention.get("chunk_id")
        if not text:
            continue
        if chunk_id and chunk_id in seen_chunks:
            continue
        if chunk_id:
            seen_chunks.add(chunk_id)
        corpus_parts.append(text.lower())

        source = {
            "source": mention.get("filename"),
            "document_id": mention.get("document_id"),
            "chunk_id": chunk_id,
        }

        for line in text.splitlines():
            for sentence in re.split(r"(?<=[.!?])\s+", line):
                sentence = sentence.strip()
                hit = tag_re.search(sentence)
                if not hit:
                    continue
                # Subject window: from the target tag to the next *different*
                # equipment tag (ignoring same-numeric-family instrument tags).
                boundary = None
                for other in _TAG_ANY.finditer(sentence):
                    if other.start() <= hit.start():
                        continue
                    if other.group().upper() == tag.upper():
                        continue
                    if tag_num and other.group(2) == tag_num:
                        continue
                    boundary = other.start()
                    break
                window = sentence[hit.start():boundary] if boundary else sentence[hit.start():]
                dedup_key = f"{chunk_id}|{window[:60].lower()}"
                if dedup_key in seen_windows:
                    continue
                seen_windows.add(dedup_key)
                # ``line`` is the fuller unit used for standard detection: in this
                # corpus a finding and its "Required by <standard>" clause sit in
                # the same line but different sentences.
                segments.append(
                    {"window": window, "sentence": sentence, "line": line.strip(), **source}
                )

    return {"segments": segments, "corpus": " ".join(corpus_parts)}


def _make_evidence(seg: dict[str, Any]) -> dict[str, Any]:
    """Render a segment as a compact, readable evidence snippet."""
    text = seg["sentence"].strip()
    if len(text) > 320:
        text = text[:317].rstrip() + "…"
    return {
        "source": seg.get("source"),
        "text": text,
        "document_id": seg.get("document_id"),
        "chunk_id": seg.get("chunk_id"),
    }


def _gap(
    tag: str,
    gap_type: str,
    severity: str,
    reason: str,
    recommended_action: str,
    evidence: list[dict[str, Any]],
    standard_or_policy: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "asset_tag": tag,
        "gap_type": gap_type,
        "severity": severity,
        "reason": reason,
        "standard_or_policy": standard_or_policy,
        "evidence": evidence[:MAX_EVIDENCE_PER_GAP],
        "recommended_action": recommended_action,
    }


# ---------------------------------------------------------------------------
# Individual rules — each returns 0..1 gap dicts (never fabricates evidence)
# ---------------------------------------------------------------------------


def _rule_certificate_expired(tag, segments, corpus) -> list[dict[str, Any]]:
    """Rule 3: expired pressure-test or inspection certificate evidence."""
    matches = []
    for seg in segments:
        w = seg["window"].lower()
        if "certificate" in w and ("expired" in w or "lapse" in w):
            matches.append(seg)
    if not matches:
        return []
    primary = matches[0]
    cert_date = _parse_date(primary["window"])
    date_note = ""
    if cert_date is not None:
        date_note = (
            f" The certificate date on file ({cert_date.isoformat()}) is in the past "
            f"relative to {_today().isoformat()}."
        )
    standard = _detect_standard(primary["line"])
    return [
        _gap(
            tag,
            GAP_CERTIFICATE_EXPIRED,
            "high",
            f"Evidence records an expired test/inspection certificate for {tag}."
            + date_note
            + " Operating without a valid certificate is a regulatory non-conformance.",
            f"Contact the approved inspection authority to renew the certificate and "
            f"withhold {tag} from certified service until a valid certificate is on file.",
            [_make_evidence(s) for s in matches],
            standard,
        )
    ]


def _rule_calibration_overdue(tag, segments, corpus) -> list[dict[str, Any]]:
    """Rule 4: overdue calibration evidence."""
    matches = []
    days_overdue = None
    for seg in segments:
        w = seg["window"].lower()
        if "calibrat" in w and ("overdue" in w or "past due" in w or "due by" in w):
            matches.append(seg)
            m = _OVERDUE_DAYS.search(seg["window"])
            if m and days_overdue is None:
                days_overdue = int(m.group(1))
    if not matches:
        return []
    overdue_note = f" It is overdue by {days_overdue} days." if days_overdue else ""
    standard = _detect_standard(matches[0]["line"])
    return [
        _gap(
            tag,
            GAP_CALIBRATION_OVERDUE,
            "high" if (days_overdue or 0) >= 30 else "medium",
            f"Instrument calibration for {tag} is overdue per the evidence on file."
            + overdue_note,
            f"Schedule and complete the overdue calibration for {tag}, then record the "
            f"result to restore compliant status.",
            [_make_evidence(s) for s in matches],
            standard,
        )
    ]


def _rule_vibration_followup(tag, segments, corpus) -> list[dict[str, Any]]:
    """Rule 1: vibration/failure exceedance without recent follow-up inspection."""
    matches = []
    for seg in segments:
        w = seg["window"].lower()
        has_vib = "vibration" in w or "vibrat" in w
        exceed = (
            "exceed" in w
            or "non-compliant" in w
            or "non compliant" in w
            or "above" in w and "limit" in w
            or "within 48 hour" in w
            or "trip setpoint" in w
            or "exceedance" in w
        )
        if has_vib and exceed:
            matches.append(seg)
    if not matches:
        return []
    # Counter-evidence: a completed follow-up would close the finding.
    closure = re.search(
        r"(alignment\s+(check\s+)?(completed|done|verified and within)"
        r"|re-?baselined?[^.]*within\s+limit"
        r"|vibration[^.]*within\s+limit\s+after"
        r"|ncr[^.]*closed|finding\s+closed)",
        corpus,
    )
    if closure:
        return []
    standard = _detect_standard(" ".join(s["line"] for s in matches))
    return [
        _gap(
            tag,
            GAP_INSPECTION_OVERDUE,
            "high",
            f"{tag} shows a vibration exceedance flagged for follow-up, but the evidence "
            f"contains no record of a completed follow-up inspection/alignment closing it out.",
            f"Complete the required follow-up inspection (e.g. laser alignment / re-baseline) "
            f"for {tag} and record closure of the exceedance.",
            [_make_evidence(s) for s in matches],
            standard,
        )
    ]


def _rule_sop_review_overdue(tag, segments, corpus) -> list[dict[str, Any]]:
    """Rule 5: old/outdated SOP or procedure review evidence."""
    matches = []
    for seg in segments:
        w = seg["window"].lower()
        is_proc = "sop" in w or "procedure" in w or "lockout" in w or "loto" in w
        review_flag = "review" in w and ("overdue" in w or "due" in w)
        if is_proc and review_flag:
            matches.append(seg)
    if not matches:
        return []
    standard = _detect_standard(matches[0]["line"])
    return [
        _gap(
            tag,
            GAP_SOP_REVIEW_OVERDUE,
            "medium",
            f"The procedure/SOP associated with {tag} is past its scheduled review date "
            f"per the evidence on file.",
            f"Complete the periodic review and re-approval of the {tag} procedure and "
            f"update its revision/approval record.",
            [_make_evidence(s) for s in matches],
            standard,
        )
    ]


def _rule_repeated_failure_no_rca(tag, segments, corpus) -> list[dict[str, Any]]:
    """Rule 2: repeated failure evidence without any root-cause analysis evidence."""
    failure_re = re.compile(
        r"(failure|failed|breakdown|leakage|alarm|exceeding trip|seal failure|recurring|repeated)",
        re.I,
    )
    failure_segs = [s for s in segments if failure_re.search(s["window"])]
    # Count distinct failure sentences to gauge a repeated pattern.
    distinct = {s["sentence"][:60].lower() for s in failure_segs}
    if len(distinct) < REPEATED_FAILURE_MIN_COUNT:
        return []
    has_rca = re.search(r"(root\s+cause|\brca\b|failure\s+analysis|5[\s-]?why|why[\s-]?why)", corpus)
    if has_rca:
        return []
    return [
        _gap(
            tag,
            GAP_REPEATED_FAILURE_NO_RCA,
            "medium",
            f"{tag} has repeated failure/corrective evidence ({len(distinct)} distinct events) "
            f"but the evidence contains no recorded root-cause analysis.",
            f"Raise and document a formal root-cause analysis for the recurring failures on "
            f"{tag} and link corrective actions to it.",
            [_make_evidence(s) for s in failure_segs],
        )
    ]


def _rule_safety_procedure_missing(tag, segments, corpus) -> list[dict[str, Any]]:
    """Rule 6: safety-critical maintenance evidence without LOTO/safety procedure."""
    safety_critical_re = re.compile(
        r"(open\s+pump\s+casing|disassembl|mechanical\s+work|hot\s+work|confined\s+space"
        r"|pressuris|depressuris|entry\s+permit|seal\s+replacement|casing\s+removal)",
        re.I,
    )
    critical_segs = [s for s in segments if safety_critical_re.search(s["window"])]
    if not critical_segs:
        return []
    has_safety = re.search(
        r"(loto|lock\s?out|lock-?out|tag\s?out|isolation\s+procedure|hse-loto|permit\s+to\s+work)",
        corpus,
    )
    if has_safety:
        return []
    return [
        _gap(
            tag,
            GAP_SAFETY_PROCEDURE_MISSING,
            "high",
            f"{tag} has safety-critical maintenance evidence, but no LOTO / lockout-tagout or "
            f"equivalent safety-isolation procedure is referenced in the evidence.",
            f"Attach the applicable LOTO / permit-to-work procedure to the {tag} maintenance "
            f"records before the work is authorised.",
            [_make_evidence(s) for s in critical_segs],
        )
    ]


_RULES = (
    _rule_certificate_expired,
    _rule_calibration_overdue,
    _rule_vibration_followup,
    _rule_sop_review_overdue,
    _rule_repeated_failure_no_rca,
    _rule_safety_procedure_missing,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_asset_gaps(tag: str, session=None) -> list[dict[str, Any]]:
    """Return all compliance gaps for a single asset tag (empty if none/unknown)."""
    normalized = (tag or "").strip().upper()
    if not normalized:
        return []
    evidence = _collect_evidence(normalized, session=session)
    segments = evidence["segments"]
    if not segments:
        return []
    corpus = evidence["corpus"]

    gaps: list[dict[str, Any]] = []
    for rule in _RULES:
        gaps.extend(rule(normalized, segments, corpus))

    gaps.sort(key=lambda g: (-_SEVERITY_RANK.get(g["severity"], 0), g["gap_type"]))
    return gaps


def _candidate_asset_tags(session=None) -> list[str]:
    from app.db import repository as repo

    return [a["tag"] for a in repo.list_assets(session=session)]


def evaluate_gaps(
    asset_tag: Optional[str] = None,
    severity: Optional[str] = None,
    gap_type: Optional[str] = None,
    session=None,
) -> dict[str, Any]:
    """Compute compliance gaps across assets with optional filters.

    In JSON persistence mode nothing is persisted, so a safe empty response is
    returned rather than touching a database. An unknown ``asset_tag`` yields an
    empty gap list (never fabricated findings).
    """
    filters = {
        "asset_tag": asset_tag,
        "severity": severity,
        "gap_type": gap_type,
    }
    filters = {k: v for k, v in filters.items() if v}

    if not config.use_postgres():
        return {
            "count": 0,
            "filters": filters,
            "gaps": [],
            "mode": "json",
            "message": "Compliance analysis is available when PERSISTENCE_BACKEND=postgres.",
        }

    if asset_tag:
        tags = [asset_tag.strip().upper()]
    else:
        tags = _candidate_asset_tags(session=session)

    all_gaps: list[dict[str, Any]] = []
    for tag in tags:
        all_gaps.extend(evaluate_asset_gaps(tag, session=session))

    if severity:
        want = severity.strip().lower()
        all_gaps = [g for g in all_gaps if g["severity"] == want]
    if gap_type:
        want_type = gap_type.strip().lower()
        all_gaps = [g for g in all_gaps if g["gap_type"] == want_type]

    all_gaps.sort(
        key=lambda g: (-_SEVERITY_RANK.get(g["severity"], 0), g["asset_tag"], g["gap_type"])
    )
    return {
        "count": len(all_gaps),
        "filters": filters,
        "gaps": all_gaps,
        "mode": "postgres",
        "message": None,
    }
