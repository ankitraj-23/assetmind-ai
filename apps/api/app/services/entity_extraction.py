"""Deterministic industrial equipment tag extraction.

No LLM and no network calls: a single regex recognizes equipment tags of the
form ``PREFIX-NUMBER[SUFFIX]`` (for example ``P-101``, ``P-204A``, ``HX-302``,
``COMP-301``) and the alphabetic prefix is mapped to a coarse asset type.

The extractor is pure and stateless. It takes text plus optional source
identifiers and returns structured :class:`ExtractedTag` records; persistence
is the caller's concern. Tags are normalized to uppercase and deduplicated by
their normalized value within a single call (i.e. within one chunk).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

ENTITY_TYPE = "equipment_tag"
EXTRACTION_METHOD = "regex_equipment_tag_v1"

# 1–4 leading letters, a hyphen, 1–4 digits, and an optional single trailing
# letter for parallel trains (e.g. the "A" in P-204A). Word boundaries keep the
# match from latching onto longer alphanumeric runs or hyphenated words.
_TAG_RE = re.compile(r"\b([A-Za-z]{1,4})-(\d{1,4})([A-Za-z]?)\b")

# Prefix -> asset type. Both the short and long forms map to the same type so
# that, e.g., MTR-07 and M-07 are both motors.
_PREFIX_ASSET_TYPES: dict[str, str] = {
    "P": "pump",
    "V": "valve",
    "HX": "heat_exchanger",
    "COMP": "compressor",
    "MTR": "motor",
    "M": "motor",
    "TK": "tank",
    "T": "tank",
    "BLR": "boiler",
    "B": "boiler",
    "R": "reactor",
}

_KNOWN_CONFIDENCE = 0.95
_UNKNOWN_CONFIDENCE = 0.6


@dataclass(frozen=True)
class ExtractedTag:
    """One extracted equipment tag with its source location and inferred type.

    ``char_start``/``char_end`` are offsets into the text passed to
    :func:`extract_equipment_tags` (i.e. chunk-relative when called per chunk).
    """

    entity_type: str
    raw_value: str
    normalized_value: str
    confidence: float
    char_start: int
    char_end: int
    extraction_method: str
    asset_type: str | None
    document_id: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None


def infer_asset_type(tag_or_prefix: str) -> str | None:
    """Infer a coarse asset type from a full tag or a bare alphabetic prefix.

    Accepts either ``"P-101"`` or ``"P"`` and returns the mapped type (e.g.
    ``"pump"``), or ``None`` for an unrecognized prefix.
    """

    prefix = tag_or_prefix.strip().upper().split("-", 1)[0]
    return _PREFIX_ASSET_TYPES.get(prefix)


def extract_equipment_tags(
    text: str,
    *,
    document_id: str | None = None,
    chunk_id: str | None = None,
    page_number: int | None = None,
) -> list[ExtractedTag]:
    """Extract unique equipment tags from ``text``.

    Tags are normalized to uppercase and deduplicated by normalized value,
    keeping the first occurrence (lowest ``char_start``). Returns an empty list
    for empty text.
    """

    if not text:
        return []

    seen: set[str] = set()
    results: list[ExtractedTag] = []
    for match in _TAG_RE.finditer(text):
        raw = match.group(0)
        normalized = raw.upper()
        if normalized in seen:
            continue
        seen.add(normalized)

        asset_type = _PREFIX_ASSET_TYPES.get(match.group(1).upper())
        confidence = _KNOWN_CONFIDENCE if asset_type else _UNKNOWN_CONFIDENCE
        results.append(
            ExtractedTag(
                entity_type=ENTITY_TYPE,
                raw_value=raw,
                normalized_value=normalized,
                confidence=confidence,
                char_start=match.start(),
                char_end=match.end(),
                extraction_method=EXTRACTION_METHOD,
                asset_type=asset_type,
                document_id=document_id,
                chunk_id=chunk_id,
                page_number=page_number,
            )
        )
    return results
