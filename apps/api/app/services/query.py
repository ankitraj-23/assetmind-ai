"""RAG-style query answering with asset scoping, intent detection, and deduplication.

Pipeline
--------
1. Classify query intent deterministically (procedure / failure_rca /
   maintenance_history / inspection / compliance / general).
2. Retrieve chunks via asset-scoped vector search (boost chunks mentioning
   the requested asset tag, prioritise doc type by intent).
3. Deduplicate citations (no repeated chunk_id; enforced in search layer).
4. Compose a temporary extractive answer (no LLM — placeholder until a real
   model is wired in, designed to be swapped without changing the contract).
5. Surface related asset tags found in the retrieved chunks.
"""

from __future__ import annotations

import re

from app.models.query import QueryCitation, QueryResponse
from app.models.search import SearchResult
from app.services import search as search_service
from app.services.entity_extraction import extract_equipment_tags
from app.services.fact_extraction import page_number_from_text

# ── confidence thresholds ─────────────────────────────────────────────────────
HIGH_CONFIDENCE_SCORE = 0.60
MEDIUM_CONFIDENCE_SCORE = 0.30
PREVIEW_CHARS = 280

# ── query intent detection ────────────────────────────────────────────────────

_INTENT_PATTERNS: list[tuple[str, list[re.Pattern]]] = [
    ("procedure", [
        re.compile(r"\bhow\s+to\b", re.I),
        re.compile(r"\bstep(s|s\s+to)?\b", re.I),
        re.compile(r"\bprocedure\b", re.I),
        re.compile(r"\bstart(up|ing)?\b|\bshutdown\b|\bcommission\w*\b", re.I),
        re.compile(r"\bcheck(list)?\b|\bloto\b|\bsafety\s+steps\b", re.I),
        re.compile(r"\bsop\b", re.I),
    ]),
    ("failure_rca", [
        re.compile(r"\bwhy\s+(is|was|did|does)\b", re.I),
        re.compile(r"\broot\s+cause\b", re.I),
        re.compile(r"\bcause(d|s)?\b|\bfault\b|\bfail(ed|ure|ing)?\b", re.I),
        re.compile(r"\bvibrat(ing|ion)\b|\boverheating\b|\bleaking\b", re.I),
        re.compile(r"\brca\b", re.I),
        re.compile(r"\bwhat\s+(caused|went\s+wrong)\b", re.I),
    ]),
    ("maintenance_history", [
        re.compile(r"\bhistory\b|\bpast\b|\bprevious\b", re.I),
        re.compile(r"\blast\s+(maintenance|service|inspection|repair|year|month)\b", re.I),
        re.compile(r"\bwork\s+order(s)?\b", re.I),
        re.compile(r"\bwhat\s+maintenance\b|\bmaintenance\s+(done|performed|carried|was)\b", re.I),
        re.compile(r"\brepair(ed|s)?\b|\breplace(d|ment)?\b", re.I),
    ]),
    ("inspection", [
        re.compile(r"\binspection\b|\bfinding(s)?\b", re.I),
        re.compile(r"\breading(s)?\b|\bmeasurement(s)?\b", re.I),
        re.compile(r"\bq[1-4]\b|\bquarterly\b|\bannual\s+inspection\b", re.I),
        re.compile(r"\bvibration\s+level\b|\btemperature\s+reading\b", re.I),
    ]),
    ("compliance", [
        re.compile(r"\bcompliance\b|\bregulation\b|\bstandard\b", re.I),
        re.compile(r"\boisd\b|\bpeso\b|\biso\b|\bfactory\s+act\b", re.I),
        re.compile(r"\bcertificate\b|\baudits?\b|\bgap\b", re.I),
        re.compile(r"\bexpired?\b|\boverdue\b|\bnon.?compliant\b", re.I),
    ]),
]


def detect_intent(question: str) -> str:
    """Classify question into one of six intent categories.

    Categories (in priority order):
      procedure, failure_rca, maintenance_history, inspection, compliance, general
    """
    for intent, patterns in _INTENT_PATTERNS:
        if any(p.search(question) for p in patterns):
            return intent
    return "general"


# ── source-type priority by intent ────────────────────────────────────────────
# Maps intent → filename substrings that should be preferred for that intent.
_INTENT_SOURCE_PRIORITY: dict[str, list[str]] = {
    "failure_rca": ["inspection", "work_order", "work-order", "near_miss"],
    "maintenance_history": ["work_order", "work-order", "maintenance"],
    "inspection": ["inspection", "report"],
    "procedure": ["sop", "manual", "oem", "startup", "procedure"],
    "compliance": ["compliance", "checklist", "certificate"],
}

_PRIORITY_BOOST = 0.08


def _boost_by_source(
    results: list[SearchResult], intent: str
) -> list[SearchResult]:
    """Boost chunks whose filename matches the preferred source types for intent."""
    priority_keywords = _INTENT_SOURCE_PRIORITY.get(intent, [])
    if not priority_keywords:
        return results

    boosted = []
    for r in results:
        fname = (r.filename or "").lower()
        extra = _PRIORITY_BOOST if any(kw in fname for kw in priority_keywords) else 0.0
        boosted.append(r.model_copy(update={"score": round(min(1.0, r.score + extra), 6)}))

    boosted.sort(key=lambda r: (-r.score, r.document_id, r.chunk_index))
    return boosted


# ── related asset extraction ──────────────────────────────────────────────────

def _extract_related_assets(
    results: list[SearchResult],
    exclude_tag: str | None = None,
) -> list[str]:
    """Return unique equipment tags found across retrieved chunks.

    The query asset_tag itself is excluded from the list so only *other*
    assets mentioned alongside it are surfaced.
    """
    seen: set[str] = set()
    related: list[str] = []

    exclude = exclude_tag.upper() if exclude_tag else None

    for result in results:
        for tag in extract_equipment_tags(result.text):
            norm = tag.normalized_value
            if norm == exclude or norm in seen:
                continue
            seen.add(norm)
            related.append(norm)

    return related


# ── answer composition ────────────────────────────────────────────────────────

def _confidence_for(score: float) -> str:
    if score >= HIGH_CONFIDENCE_SCORE:
        return "high"
    if score >= MEDIUM_CONFIDENCE_SCORE:
        return "medium"
    return "low"


def _preview(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= PREVIEW_CHARS:
        return collapsed
    return collapsed[:PREVIEW_CHARS].rstrip() + "..."


def _compose_answer(question: str, results: list[SearchResult], intent: str) -> str:
    """Build a deterministic extractive answer from retrieved chunks.

    Temporary placeholder until a real LLM is wired in.
    """
    top = results[0]
    evidence = _preview(top.text)
    intent_note = f" [{intent}]" if intent != "general" else ""
    return (
        f"Based on {len(results)} retrieved chunk(s){intent_note}, the most relevant "
        f'evidence for "{question}" is: "{evidence}" '
        "(Extractive answer — no LLM; see citations for full provenance.)"
    )


NO_CONTEXT_ANSWER = (
    "Not enough indexed context to answer this question. "
    "Ingest related documents via POST /documents and try again."
)


# ── main entry point ──────────────────────────────────────────────────────────

def answer_question(
    question: str,
    top_k: int = 5,
    asset_tag: str | None = None,
) -> QueryResponse:
    """Answer ``question`` from indexed context with citations and metadata.

    Parameters
    ----------
    question:
        The natural-language question.
    top_k:
        Maximum number of chunks to retrieve.
    asset_tag:
        Optional equipment tag. Retrieval is biased towards chunks mentioning
        this tag, and it is excluded from the ``related_assets`` list.
    """
    intent = detect_intent(question)

    results = search_service.search(question, top_k=top_k, asset_tag=asset_tag)

    # Apply source-type priority boost based on detected intent.
    if results and intent in _INTENT_SOURCE_PRIORITY:
        results = _boost_by_source(results, intent)
        # Re-sort after boost (deduplication already happened in search layer).
        results.sort(key=lambda r: (-r.score, r.document_id, r.chunk_index))
        results = results[:top_k]

    if not results:
        return QueryResponse(
            question=question,
            answer=NO_CONTEXT_ANSWER,
            confidence="low",
            citations=[],
            retrieved_count=0,
            query_intent=intent,
            related_assets=[],
        )

    related_assets = _extract_related_assets(results, exclude_tag=asset_tag)

    citations = [
        QueryCitation(
            document_id=r.document_id,
            chunk_id=r.chunk_id,
            chunk_index=r.chunk_index,
            score=r.score,
            text_preview=_preview(r.text),
            filename=r.filename,
            page_number=page_number_from_text(r.text),
        )
        for r in results
    ]

    return QueryResponse(
        question=question,
        answer=_compose_answer(question, results, intent),
        confidence=_confidence_for(results[0].score),
        citations=citations,
        retrieved_count=len(results),
        query_intent=intent,
        related_assets=related_assets,
    )
