"""Regex-based structured fact extraction from industrial free text.

Used for PDF and TXT content (complement to column-based extraction for CSV/XLSX).
Deterministic — no LLM, no network calls.

Extracted fact types
--------------------
failure_mode         : equipment failure descriptions
maintenance_action   : repair / corrective actions performed
inspection_reading   : numeric readings with engineering units
sop_reference        : SOP / procedure document references (SOP-XXX)
compliance_reference : regulatory standard references (OISD-137, PESO, ISO…)
spare_part           : part numbers (MS-45-CR, 6309-2RS)
risk_phrase          : criticality / risk level phrases
open_action          : pending / required action phrases
"""

from __future__ import annotations

import re

# ── inspection readings ───────────────────────────────────────────────────────
# Matches: "7.8 mm/s", "3.5 bar", "45 m3/h", "1450 RPM", "11 kW"
_READING_RE = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*"
    r"(mm/s|m/s|bar|kPa|MPa|m3/h|m³/h|RPM|rpm|°C|deg\s*C|kW|MW|Hz|psi|L/min|m|kg|A)\b",
    re.I,
)

# ── SOP references ────────────────────────────────────────────────────────────
# Matches: "SOP-PUMP-STARTUP", "SOP-001", "SOP-BLR-SHUTDOWN"
_SOP_RE = re.compile(r"\bSOP-[A-Z0-9][A-Z0-9\-]{2,29}\b", re.I)

# ── compliance references ─────────────────────────────────────────────────────
_COMPLIANCE_RES = [
    re.compile(r"\bOISD-\d+\b", re.I),
    re.compile(r"\bISO\s+\d{4}(?::\d{4})?\b", re.I),
    re.compile(r"\bPESO\b"),
    re.compile(r"\bFactory\s+Act\b", re.I),
    re.compile(r"\bIBR\b"),
    re.compile(r"\bCEIG\b"),
    re.compile(r"\bAPI\s+\d+\b", re.I),
    re.compile(r"\bASME\b"),
    re.compile(r"\bBIS\b"),
]

# ── spare part / part numbers ─────────────────────────────────────────────────
# Matches: MS-45-CR, 6309-2RS, BRG-6309-A, MS-4502
_SPARE_RE = re.compile(
    r"\b(?:[A-Z]{1,6}-\d{2,6}-[A-Z0-9]{1,8}"
    r"|\d{4}-[A-Z0-9]{2,8}"
    r"|BRG-[A-Z0-9\-]{2,12})\b"
)

# ── failure modes ─────────────────────────────────────────────────────────────
# Ordered: first match wins, so more specific patterns come first.
_FAILURE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bbearing\s+(failure|wear|damage|degradation)\b", re.I), "bearing failure"),
    (re.compile(r"\bseal\s+(failure|damage|wear)\b", re.I), "seal failure"),
    (re.compile(r"\blow\s+suction\s+pressure\b", re.I), "low suction pressure"),
    (re.compile(r"\b(high|excessive)\s+vibration\b", re.I), "high vibration"),
    (re.compile(r"\b(low|reduced)\s+(flow|pressure)\b", re.I), "low flow/pressure"),
    (re.compile(r"\boverheating\b|\bover\s*heat(?:ing)?\b", re.I), "overheating"),
    (re.compile(r"\bleakage?\b|\bseal\s+leak\b", re.I), "leakage"),
    (re.compile(r"\bcavitation\b", re.I), "cavitation"),
    (re.compile(r"\bfouling\b", re.I), "fouling"),
    (re.compile(r"\bcorrosion\b", re.I), "corrosion"),
    (re.compile(r"\berosion\b", re.I), "erosion"),
    (re.compile(r"\bmisalign\w*\b", re.I), "misalignment"),
    (re.compile(r"\bclog\w*\b|\bblockage\b", re.I), "blockage"),
    (re.compile(r"\babnormal\s+noise\b|\bnoisy\b", re.I), "abnormal noise"),
    (re.compile(r"\bflutter\b", re.I), "flutter"),
]

# ── risk phrases ──────────────────────────────────────────────────────────────
_RISK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bimmediate\s+action\s+required\b", re.I), "immediate action required"),
    (re.compile(r"\bnon.?compliant\b", re.I), "non-compliant"),
    (re.compile(r"\bhigh\s+risk\b", re.I), "high risk"),
    (re.compile(r"\bhigh\s+priority\b", re.I), "high priority"),
    (re.compile(r"\bcritical\b", re.I), "critical"),
    (re.compile(r"\boverdue\b", re.I), "overdue"),
    (re.compile(r"\bexpired\b", re.I), "expired"),
    (re.compile(r"\burgent\b", re.I), "urgent"),
    (re.compile(r"\bmedium\s+risk\b", re.I), "medium risk"),
    (re.compile(r"\blow\s+risk\b", re.I), "low risk"),
]

# ── open / pending actions ────────────────────────────────────────────────────
_OPEN_ACTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\balignment\s+recheck\b", re.I), "alignment recheck required"),
    (re.compile(r"\brecheck\s+required\b", re.I), "recheck required"),
    (re.compile(r"\bfollow.?up\s+required\b", re.I), "follow-up required"),
    (re.compile(r"\baction\s+required\b", re.I), "action required"),
    (re.compile(r"\bopen\s+action\b", re.I), "open action"),
    (re.compile(r"\bpending\s+(?:inspection|verification|action|maintenance)\b", re.I), "pending"),
    (re.compile(r"\bmonitor\s+closely\b", re.I), "monitor closely"),
    (re.compile(r"\bimmediately?\s+(?:inspect|replace|shut|repair|check)\b", re.I), "immediate action"),
    (re.compile(r"\brake\s+(?:a\s+)?(?:maintenance\s+)?work\s+order\b", re.I), "raise work order"),
    (re.compile(r"\bdo\s+not\s+(attempt\s+to\s+)?restart\b", re.I), "do not restart"),
]

# ── maintenance actions ───────────────────────────────────────────────────────
# Captures: "Replace the mechanical seal", "Inspect impeller for wear"
_ACTION_VERBS_RE = re.compile(
    r"\b(replac\w+|repair\w*|inspect\w*|calibrat\w*|clean\w*|align\w*|overhaul\w*"
    r"|lubricat\w*|tighten\w*|adjust\w*|flush\w*|install\w*|remov\w*|check\w*"
    r"|verif\w*|test\w*|measur\w*|trim\w*)\s+"
    r"(?:the\s+|and\s+)?(\w+(?:\s+\w+){0,4})",
    re.I,
)

# ── page marker (added by ingestion during PDF extraction) ───────────────────
_PAGE_MARKER_RE = re.compile(r"\[Page (\d+)\]")


def page_number_from_text(text: str) -> int | None:
    """Return the first page number marker found in a chunk's text, or None."""
    m = _PAGE_MARKER_RE.search(text)
    return int(m.group(1)) if m else None


def extract_facts_from_text(text: str) -> dict:
    """Extract structured industrial facts from free text.

    Returns a flat dict containing only fact keys for which a match was found.
    Each key holds the first (highest-priority) match.

    Keys returned (subset, depending on content):
      failure_mode, maintenance_action, inspection_reading,
      sop_reference, compliance_reference, spare_part,
      risk_phrase, open_action
    """
    if not text or not text.strip():
        return {}

    facts: dict[str, str] = {}

    # inspection_reading — first numeric + unit match
    m = _READING_RE.search(text)
    if m:
        facts["inspection_reading"] = m.group(0).strip()

    # sop_reference
    m = _SOP_RE.search(text)
    if m:
        facts["sop_reference"] = m.group(0).upper()

    # compliance_reference — first standard found
    for cre in _COMPLIANCE_RES:
        m = cre.search(text)
        if m:
            facts["compliance_reference"] = m.group(0)
            break

    # spare_part — first part-number pattern
    m = _SPARE_RE.search(text)
    if m:
        facts["spare_part"] = m.group(0)

    # failure_mode — highest-priority keyword wins
    for pattern, label in _FAILURE_PATTERNS:
        if pattern.search(text):
            facts["failure_mode"] = label
            break

    # risk_phrase
    for pattern, label in _RISK_PATTERNS:
        if pattern.search(text):
            facts["risk_phrase"] = label
            break

    # open_action
    for pattern, label in _OPEN_ACTION_PATTERNS:
        if pattern.search(text):
            facts["open_action"] = label
            break

    # maintenance_action — first action verb + object phrase
    m = _ACTION_VERBS_RE.search(text)
    if m:
        # Normalize whitespace in the matched phrase
        facts["maintenance_action"] = " ".join(m.group(0).split())

    return facts
