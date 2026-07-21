import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.agents import LikelyCause, RcaEvidence, RcaResponse, RcaRequest
from app.services.llm import generate_with_fallback
from app.services.query import get_evidence_for_rca

logger = logging.getLogger(__name__)

# Maximum verbatim characters copied from a retrieved chunk into an evidence
# snippet. The snippet is always a prefix of the *actual* chunk text — never a
# fabricated quotation.
_SNIPPET_CHARS = 300


# ── Generic, evidence-driven cause rules ──────────────────────────────────────
#
# Each rule fires only when the *symptom* matches one of its ``triggers`` AND the
# cause is reasonably indicated — either the retrieved asset evidence contains an
# ``indicator`` keyword, or the symptom text itself mentions one. Nothing here is
# asset-specific: the same rules apply to any asset. Causes are always grounded
# in the chunks that were actually retrieved for the requested asset.
_CAUSE_RULES: List[Dict[str, Any]] = [
    {
        "triggers": ["vibrat", "imbalance", "unbalance"],
        "cause": "Shaft/coupling misalignment, likely introduced during recent maintenance.",
        "indicators": ["misalign", "coupl", "align", "seal", "replace", "maintenance", "overhaul"],
        "actions": [
            "Perform a precision (laser) shaft alignment check between the driver and driven equipment.",
            "Re-baseline vibration readings after any alignment correction.",
        ],
        "missing": [
            "Confirmation that a post-maintenance alignment check was completed.",
            "Latest vibration spectrum / FFT analysis.",
        ],
    },
    {
        "triggers": ["vibrat", "noise", "bearing"],
        "cause": "Bearing wear or degradation on the affected equipment.",
        "indicators": ["bearing", "defect frequency", "lubric", "grease", "noise"],
        "actions": [
            "Inspect and trend the drive-end and non-drive-end bearings.",
            "Review the lubrication schedule and bearing condition history.",
        ],
        "missing": [
            "Bearing vibration / temperature trend data.",
            "Lubricant (oil) analysis results.",
        ],
    },
    {
        "triggers": ["overheat", "temperature", "hot", "thermal"],
        "cause": "Inadequate lubrication or cooling.",
        "indicators": ["lubric", "oil", "grease", "cool", "coolant", "flow"],
        "actions": [
            "Verify lubrication level/quality and confirm the cooling system is operating.",
            "Check for restricted cooling passages or fouling.",
        ],
        "missing": ["Lubricant analysis and temperature trend data."],
    },
    {
        "triggers": ["overheat", "temperature", "overload", "load", "current", "trip"],
        "cause": "Excessive load or overcurrent condition.",
        "indicators": ["load", "current", "amp", "overload", "power", "overcurrent"],
        "actions": ["Review operating load and motor current against rated values."],
        "missing": ["Recent load / motor current readings."],
    },
    {
        "triggers": ["overheat", "temperature", "insulation", "winding", "earth", "phase"],
        "cause": "Insulation or winding degradation.",
        "indicators": ["insulation", "winding", "megger", "earth", "phase", "ir "],
        "actions": ["Perform insulation resistance (IR) testing on the windings."],
        "missing": ["Insulation resistance test records."],
    },
    {
        "triggers": ["leak", "leakage", "seep", "weep"],
        "cause": "Mechanical seal degradation.",
        "indicators": ["seal", "gland", "packing", "flush"],
        "actions": [
            "Inspect the mechanical seal condition and seal faces.",
            "Verify the seal flush plan and shaft alignment.",
        ],
        "missing": ["Seal inspection / replacement history."],
    },
    {
        "triggers": ["leak", "leakage", "corros"],
        "cause": "Gasket / joint or corrosion-related leakage.",
        "indicators": ["gasket", "flange", "joint", "corros"],
        "actions": ["Inspect flange joints, gaskets and surfaces for corrosion."],
        "missing": ["Recent inspection findings for joints/gaskets."],
    },
    {
        "triggers": ["foul", "clog", "block", "restrict"],
        "cause": "Fouling or flow restriction.",
        "indicators": ["foul", "clean", "tube", "clog", "deposit"],
        "actions": ["Schedule cleaning / de-fouling and inspect for flow restriction."],
        "missing": ["Differential pressure / flow trend data."],
    },
]


def _mentions_asset(text: str, asset_tag: str) -> bool:
    """True if ``text`` references ``asset_tag`` as a whole token (case-insensitive)."""
    tag = (asset_tag or "").strip()
    if not tag:
        return False
    return bool(re.search(rf"\b{re.escape(tag)}\b", text or "", re.IGNORECASE))


def _snippet(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= _SNIPPET_CHARS:
        return text
    return text[:_SNIPPET_CHARS].rstrip()


def _evidence_from_chunk(chunk: Dict[str, Any]) -> RcaEvidence:
    return RcaEvidence(
        source=chunk.get("filename") or "unknown",
        text=_snippet(chunk.get("text", "")),
        document_id=chunk.get("document_id"),
        chunk_id=chunk.get("chunk_id"),
    )


def _cause_confidence(keyword_support: int) -> float:
    """Conservative confidence scaled by evidence coverage (never a fixed score).

    A cause supported only by the symptom (no matching keyword in the retrieved
    evidence) gets a low floor; each chunk that independently corroborates the
    cause raises confidence, capped well below certainty.
    """
    if keyword_support <= 0:
        return 0.25
    return round(min(0.3 + 0.12 * keyword_support, 0.75), 2)


def _build_rca_prompt(symptom: str, asset_tag: str, evidence_chunks: List[Dict[str, Any]]) -> str:
    """Constructs the prompt for the RCA LLM."""

    evidence_text = "\n\n---\n\n".join(
        f"Source: {chunk.get('filename', 'Unknown')}\n\n{chunk.get('text', '')}" for chunk in evidence_chunks
    )

    prompt = f"""
You are an expert reliability engineer performing a root cause analysis (RCA).

**Asset:** {asset_tag}
**Symptom:** {symptom}

**Available Evidence:**
---
{evidence_text}
---

**Your Task:**
Analyze the evidence to determine the likely root causes for the symptom.
Your response MUST be a single, valid JSON object that adheres to the following structure. Do not add any text before or after the JSON object.

**JSON Structure:**
{{
  "asset_tag": "{asset_tag}",
  "symptom": "{symptom}",
  "summary": "<A brief, one-sentence summary of your findings.>",
  "likely_causes": [
    {{
      "cause": "<Description of the first likely cause.>",
      "confidence": <A float between 0.0 and 1.0 representing your confidence.>,
      "evidence": [
        {{
          "source": "<The filename of the document providing this evidence.>",
          "text": "<The exact, verbatim text snippet from the evidence that supports this cause.>"
        }}
      ]
    }}
  ],
  "recommended_actions": [
    "<A brief, actionable recommendation.>",
    "<Another recommendation.>"
  ],
  "missing_information": [
    "<A piece of information that is missing but would help the analysis.>",
    "<Another piece of missing information.>"
  ]
}}

**Instructions:**
1.  **`summary`**: Write a concise, high-level summary.
2.  **`likely_causes`**: Identify at least two distinct potential causes if supported by evidence. For each cause:
    -   `cause`: Clearly state the cause.
    -   `confidence`: Provide a numerical confidence score.
    -   `evidence`: Provide at least one direct quote from the provided evidence. The `source` must be the filename and the `text` must be a verbatim snippet.
3.  **`recommended_actions`**: Suggest concrete, actionable steps to diagnose or fix the issue.
4.  **`missing_information`**: List specific data or reports that are not in the evidence but would be crucial for a more definitive analysis.
5.  **Grounding**: Base all your findings strictly on the provided evidence. If the evidence is insufficient, state that in the summary and list what's missing. Do not hallucinate.
"""
    return prompt


def _llm_configured() -> bool:
    return bool(
        settings.llm_provider
        and settings.llm_provider.lower() == "gemini"
        and settings.gemini_api_key
    )


def _dedupe(items: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _insufficient_evidence_response(request: RcaRequest, retrieved_any: bool) -> RcaResponse:
    """Safe result when no asset-specific evidence was retrieved.

    Crucially, this never invents causes or cites documents that were not
    retrieved for the requested asset, so an unknown asset can never receive
    another asset's answer.
    """
    if retrieved_any:
        summary = (
            f"Insufficient evidence specific to {request.asset_tag} was retrieved to "
            f"determine a root cause for '{request.symptom}'. Retrieved documents did "
            f"not reference this asset."
        )
    else:
        summary = (
            f"No documents were retrieved for {request.asset_tag}, so a root cause for "
            f"'{request.symptom}' cannot be determined."
        )
    return RcaResponse(
        asset_tag=request.asset_tag,
        symptom=request.symptom,
        summary=summary,
        likely_causes=[],
        recommended_actions=[
            f"Manually review maintenance logs and inspection reports for {request.asset_tag}.",
            f"Confirm that documentation for {request.asset_tag} has been ingested into the knowledge base.",
        ],
        missing_information=[
            f"Any maintenance, inspection or work-order records that explicitly reference {request.asset_tag}.",
        ],
        citations=[],
    )


def _deterministic_rca(request: RcaRequest, asset_evidence: List[Dict[str, Any]]) -> RcaResponse:
    """Build an RCA result purely from evidence actually retrieved for the asset.

    Works for any asset. Only causes that are reasonably indicated by the
    symptom and the retrieved evidence are included, and every cited source is
    one of the retrieved chunks.
    """
    symptom_l = request.symptom.lower()
    likely_causes: List[LikelyCause] = []
    recommended_actions: List[str] = []
    missing_information: List[str] = []
    used_causes: set[str] = set()

    for rule in _CAUSE_RULES:
        if not any(trigger in symptom_l for trigger in rule["triggers"]):
            continue
        if rule["cause"] in used_causes:
            continue

        supporting = [
            chunk
            for chunk in asset_evidence
            if any(ind in (chunk.get("text", "").lower()) for ind in rule["indicators"])
        ]
        symptom_indicates = any(ind in symptom_l for ind in rule["indicators"])
        if not supporting and not symptom_indicates:
            # Neither the evidence nor the symptom supports this cause — skip it.
            continue

        evidence_chunks = supporting if supporting else asset_evidence[:1]
        cause = LikelyCause(
            cause=rule["cause"],
            confidence=_cause_confidence(len(supporting)),
            evidence=[_evidence_from_chunk(c) for c in evidence_chunks[:3]],
        )
        likely_causes.append(cause)
        used_causes.add(rule["cause"])
        recommended_actions.extend(rule["actions"])
        missing_information.extend(rule["missing"])

    if not likely_causes:
        # Symptom did not match any rule (or matched none with support). Fall back
        # to a single, evidence-anchored observation rather than inventing a cause.
        top = asset_evidence[:2]
        likely_causes.append(
            LikelyCause(
                cause=(
                    f"Condition consistent with the most recent records retrieved for "
                    f"{request.asset_tag}; specific root cause could not be isolated from "
                    f"the available evidence."
                ),
                confidence=_cause_confidence(0),
                evidence=[_evidence_from_chunk(c) for c in top],
            )
        )
        recommended_actions.append(
            f"Review the retrieved records for {request.asset_tag} and gather targeted "
            f"diagnostic data for the reported symptom."
        )
        missing_information.append(
            f"Diagnostic data (trends, spectra, readings) specific to '{request.symptom}'."
        )

    recommended_actions = _dedupe(recommended_actions)
    missing_information = _dedupe(missing_information)

    top_conf = max((c.confidence for c in likely_causes), default=0.0)
    summary = (
        f"Analysis of {len(asset_evidence)} evidence item(s) retrieved for "
        f"{request.asset_tag} indicates {len(likely_causes)} likely cause(s) for "
        f"'{request.symptom}' (top confidence {top_conf:.2f})."
    )

    return RcaResponse(
        asset_tag=request.asset_tag,
        symptom=request.symptom,
        summary=summary,
        likely_causes=likely_causes,
        recommended_actions=recommended_actions,
        missing_information=missing_information,
        citations=[],
    )


def _parse_llm_rca(
    llm_result_str: str, asset_evidence: List[Dict[str, Any]]
) -> Optional[RcaResponse]:
    """Parse an LLM RCA response, attaching real chunk IDs. Returns None on failure."""
    if not llm_result_str or not llm_result_str.strip():
        return None
    text = llm_result_str.strip()
    if text.startswith("```json"):
        text = text[7:-3].strip()
    elif text.startswith("```"):
        text = text.strip("`").strip()

    try:
        response_data = json.loads(text)
        chunk_map = {c["text"]: c for c in asset_evidence}
        for cause in response_data.get("likely_causes", []):
            for ev in cause.get("evidence", []):
                match = chunk_map.get(ev.get("text"))
                if match:
                    ev["document_id"] = match["document_id"]
                    ev["chunk_id"] = match["chunk_id"]
        return RcaResponse(**response_data)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.error(f"Failed to parse LLM RCA response: {exc}\nResponse was: {llm_result_str}")
        return None


async def perform_rca(request: RcaRequest) -> RcaResponse:
    """Perform Root Cause Analysis for a given asset and symptom.

    Retrieval → (optional Gemini) → evidence-grounded deterministic fallback.
    The fallback is fully derived from the chunks retrieved for *this* asset, so
    it works for any asset and never emits another asset's answer or a source
    that was not actually retrieved.
    """
    search_query = f"Evidence for root cause of '{request.symptom}' on asset {request.asset_tag}"
    try:
        evidence_chunks = await get_evidence_for_rca(
            question=search_query, asset_tag=request.asset_tag, top_k=10
        )
    except Exception as exc:
        logger.error(f"Failed to retrieve evidence for RCA: {exc}")
        evidence_chunks = []

    # Keep only evidence that genuinely references the requested asset. This is
    # what prevents an unknown asset from being answered with unrelated content.
    asset_evidence = [
        chunk for chunk in evidence_chunks if _mentions_asset(chunk.get("text", ""), request.asset_tag)
    ]

    if not asset_evidence:
        return _insufficient_evidence_response(request, retrieved_any=bool(evidence_chunks))

    if _llm_configured():
        prompt = _build_rca_prompt(request.symptom, request.asset_tag, asset_evidence)
        llm_result_str = await generate_with_fallback(prompt, fallback_text="")
        parsed = _parse_llm_rca(llm_result_str, asset_evidence)
        if parsed is not None:
            return parsed
        logger.info("LLM RCA unavailable or unparseable; using deterministic fallback.")

    return _deterministic_rca(request, asset_evidence)
