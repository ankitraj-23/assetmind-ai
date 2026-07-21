"""Hybrid retrieval over pgvector-backed parent summary chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select

from app.db.models import Document, DocumentChunk
from app.db.session import session_scope
from app.rag import embeddings
from app.rag.schemas import RetrievedChunk

VECTOR_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30
RRF_K = 60
MIN_CANDIDATES = 50
MAX_CANDIDATES = 150
METADATA_BOOST_CAP = 0.55
MMR_LAMBDA = 0.72
# Source-diversity cap: at most this many chunks from any single source document
# may occupy the final ranked list, so a high-volume file (e.g. a work-order CSV
# with hundreds of row-chunks) cannot crowd out the correct source document.
# Slots that cannot be filled under the cap fall back to the next-best chunks.
MAX_CHUNKS_PER_DOCUMENT = 2
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "procedure",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "with",
}
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.-]*", re.IGNORECASE)
ASSET_RE = re.compile(r"\b[A-Z]{1,8}-[A-Z0-9-]*\d[A-Z0-9-]*\b")

# Filename / document-type boost by query intent. When a question implies a
# document type (a procedure question → an SOP/manual, a compliance question →
# a checklist/certificate, etc.), chunks whose source filename matches that type
# get a small additive boost. These are generic document-type cues, not
# per-question rules, and mirror the intent→source-priority already used by the
# project's query service.
FILENAME_INTENT_BOOST = 0.12
_INTENT_FILENAME_HINTS: list[tuple[re.Pattern, tuple[str, ...]]] = [
    (
        re.compile(
            r"\b(step|steps|procedure|start|starting|startup|shut\s*down|shutdown|"
            r"isolation|loto|lockout|commission\w*|checklist before)\b",
            re.I,
        ),
        ("sop", "manual", "procedure", "startup", "oem"),
    ),
    (
        re.compile(
            r"\b(compliance|recertif\w*|certificat\w*|standard|regulat\w*|audit|"
            r"deadline|govern\w*|oisd|peso|non.?compliant|expired?)\b",
            re.I,
        ),
        ("compliance", "checklist", "certificate"),
    ),
    (
        re.compile(
            r"\b(reading|readings|vibration|inspection|finding|findings|"
            r"measurement|measurements|pending|current|acceptable limit)\b",
            re.I,
        ),
        ("inspection", "report"),
    ),
    (
        re.compile(
            r"\b(work\s*order|maintenance|repair\w*|replaced|replacement|history|"
            r"past|previous|seal failure)\b",
            re.I,
        ),
        ("work_order", "work-order", "maintenance", "rca"),
    ),
]


def _filename_intent_boost(question: str, file_name: str | None) -> float:
    """Boost chunks whose filename matches the document type a question implies."""
    fname = (file_name or "").lower()
    if not fname:
        return 0.0
    for pattern, hints in _INTENT_FILENAME_HINTS:
        if pattern.search(question) and any(hint in fname for hint in hints):
            return FILENAME_INTENT_BOOST
    return 0.0


@dataclass
class CandidateScores:
    chunk: RetrievedChunk
    vector_score: float = 0.0
    keyword_score: float = 0.0
    vector_rank: int | None = None
    keyword_rank: int | None = None
    rrf_score: float = 0.0
    metadata_boost: float = 0.0
    filename_boost: float = 0.0
    raw_hybrid_score: float = 0.0


def retrieve_relevant_chunks(question: str, top_k: int = 5) -> list[RetrievedChunk]:
    """Embed ``question`` and return hybrid-ranked raw parent chunks."""

    if not question.strip():
        raise ValueError("Question must not be empty.")
    if top_k < 1 or top_k > 20:
        raise ValueError("top_k must be between 1 and 20.")

    candidate_limit = _candidate_limit(top_k)
    query_vector = embeddings.embed_query(question)
    vector_candidates = _retrieve_by_vector(query_vector, candidate_limit)
    keyword_candidates = _retrieve_by_keyword(question, candidate_limit)
    return _hybrid_rank(question, vector_candidates, keyword_candidates, top_k)


def _candidate_limit(top_k: int) -> int:
    return max(MIN_CANDIDATES, min(MAX_CANDIDATES, top_k * 10))


def _retrieve_by_vector(query_vector: list[float], top_k: int) -> list[RetrievedChunk]:
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
    statement = (
        select(DocumentChunk, Document, distance)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.embedding.isnot(None))
        .where(DocumentChunk.embedding_model == embeddings.active_model())
        .order_by(distance.asc(), DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc())
        .limit(top_k)
    )

    with session_scope() as session:
        rows = session.execute(statement).all()

    results: list[RetrievedChunk] = []
    for chunk, document, raw_distance in rows:
        distance_value = float(raw_distance) if raw_distance is not None else None
        vector_score = 0.0 if distance_value is None else max(0.0, 1.0 - distance_value)
        results.append(
            _chunk_from_row(
                chunk,
                document,
                score=vector_score,
                distance=distance_value,
            )
        )
    return results


def _retrieve_by_keyword(question: str, top_k: int) -> list[RetrievedChunk]:
    statement = (
        select(DocumentChunk, Document)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.embedding.isnot(None))
        .where(DocumentChunk.embedding_model == embeddings.active_model())
        .order_by(DocumentChunk.document_id.asc(), DocumentChunk.chunk_index.asc())
    )

    with session_scope() as session:
        rows = session.execute(statement).all()

    scored: list[tuple[float, RetrievedChunk]] = []
    for chunk, document in rows:
        candidate = _chunk_from_row(chunk, document, score=0.0, distance=None)
        score = _keyword_score(question, candidate)
        if score > 0:
            scored.append((score, candidate))

    scored.sort(
        key=lambda item: (
            item[0],
            item[1].file_name,
            -(item[1].row_start or item[1].row_number or 0),
        ),
        reverse=True,
    )
    results: list[RetrievedChunk] = []
    for score, chunk in scored[:top_k]:
        results.append(chunk.model_copy(update={"score": round(score, 6)}))
    return results


def _chunk_from_row(
    chunk: DocumentChunk,
    document: Document,
    *,
    score: float,
    distance: float | None,
) -> RetrievedChunk:
    metadata = dict(chunk.metadata_json or {})
    parent_chunk_id = metadata.get("parent_chunk_id") or chunk.id
    retrieval_unit_id = metadata.get("retrieval_unit_id") or f"{chunk.id}:summary:0"
    raw_text = chunk.text
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        parent_chunk_id=parent_chunk_id,
        retrieval_unit_id=retrieval_unit_id,
        content=raw_text,
        raw_text=raw_text,
        retrieval_summary=metadata.get("retrieval_summary"),
        answerable_questions=list(metadata.get("answerable_questions") or []),
        summary_strategy=metadata.get("summary_strategy"),
        score=round(score, 6),
        distance=round(distance, 6) if distance is not None else None,
        file_name=metadata.get("file_name") or document.original_filename,
        source_path=metadata.get("source_path") or document.storage_path,
        source_type=metadata.get("source_type"),
        page_number=metadata.get("page_number"),
        page_start=metadata.get("page_start"),
        page_end=metadata.get("page_end"),
        row_number=metadata.get("row_number"),
        row_index=metadata.get("row_index"),
        row_start=metadata.get("row_start"),
        row_end=metadata.get("row_end"),
        section_title=metadata.get("section_title"),
        asset_tags=sorted(
            set(metadata.get("asset_tags") or [])
            | set(metadata.get("parent_summary_asset_tags") or [])
        ),
        modality=metadata.get("modality"),
        element_summaries=list(metadata.get("atomic_element_summaries") or []),
        visual_elements=list(metadata.get("visual_elements") or []),
        chunk_index=chunk.chunk_index,
        metadata=metadata,
    )


def _hybrid_rank(
    question: str,
    vector_candidates: list[RetrievedChunk],
    keyword_candidates: list[RetrievedChunk],
    top_k: int,
) -> list[RetrievedChunk]:
    candidates: dict[str, CandidateScores] = {}

    max_vector_score = max((chunk.score for chunk in vector_candidates), default=0.0) or 1.0
    for rank, chunk in enumerate(_dedupe_parent_chunks(vector_candidates), start=1):
        key = _parent_key(chunk)
        candidates[key] = CandidateScores(
            chunk=chunk,
            vector_score=max(0.0, chunk.score / max_vector_score),
            vector_rank=rank,
        )

    max_keyword_score = max((chunk.score for chunk in keyword_candidates), default=0.0) or 1.0
    for rank, chunk in enumerate(_dedupe_parent_chunks(keyword_candidates), start=1):
        key = _parent_key(chunk)
        entry = candidates.setdefault(key, CandidateScores(chunk=chunk))
        entry.keyword_score = max(0.0, chunk.score / max_keyword_score)
        entry.keyword_rank = rank
        if entry.chunk.distance is None and chunk.distance is not None:
            entry.chunk = chunk

    for entry in candidates.values():
        entry.rrf_score = _rrf_score(entry.vector_rank, entry.keyword_rank)
        entry.metadata_boost = _metadata_boost(question, entry.chunk)
        entry.filename_boost = _filename_intent_boost(question, entry.chunk.file_name)
        entry.raw_hybrid_score = (
            VECTOR_WEIGHT * entry.vector_score
            + KEYWORD_WEIGHT * entry.keyword_score
            + entry.rrf_score
            + entry.metadata_boost
            + entry.filename_boost
        )

    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            item.raw_hybrid_score,
            item.vector_score,
            item.keyword_score,
            -(item.chunk.row_start or item.chunk.row_number or 0),
        ),
        reverse=True,
    )
    max_score = max((entry.raw_hybrid_score for entry in ranked), default=0.0) or 1.0

    selected = _mmr_select(ranked, top_k)

    results: list[RetrievedChunk] = []
    for mmr_rank, (entry, mmr_score) in enumerate(selected, start=1):
        normalized_score = max(0.0, min(1.0, entry.raw_hybrid_score / max_score))
        metadata = {
            **entry.chunk.metadata,
            "retrieval_strategy": "hybrid_vector_keyword_rrf_rerank_mmr",
            "hybrid_weights": {"vector": VECTOR_WEIGHT, "keyword": KEYWORD_WEIGHT},
            "mmr": {
                "enabled": True,
                "lambda": MMR_LAMBDA,
                "rank": mmr_rank,
                "score": round(mmr_score, 6),
            },
            "hybrid_scores": {
                "vector_score": round(entry.vector_score, 6),
                "keyword_score": round(entry.keyword_score, 6),
                "rrf_score": round(entry.rrf_score, 6),
                "metadata_boost": round(entry.metadata_boost, 6),
                "filename_boost": round(entry.filename_boost, 6),
                "raw_hybrid_score": round(entry.raw_hybrid_score, 6),
            },
            "hybrid_ranks": {
                "vector_rank": entry.vector_rank,
                "keyword_rank": entry.keyword_rank,
            },
        }
        results.append(
            entry.chunk.model_copy(
                update={
                    "score": round(normalized_score, 6),
                    "metadata": metadata,
                }
            )
        )
    return results


def _mmr_select(
    ranked: list[CandidateScores],
    top_k: int,
) -> list[tuple[CandidateScores, float]]:
    remaining = list(ranked)
    selected: list[tuple[CandidateScores, float]] = []
    per_document: dict[str, int] = {}

    def _document_key(candidate: CandidateScores) -> str:
        return candidate.chunk.file_name

    while remaining and len(selected) < top_k:
        if not selected:
            first = remaining.pop(0)
            selected.append((first, first.raw_hybrid_score))
            per_document[_document_key(first)] = 1
            continue

        best_index: int | None = None
        best_score = float("-inf")
        for index, candidate in enumerate(remaining):
            if per_document.get(_document_key(candidate), 0) >= MAX_CHUNKS_PER_DOCUMENT:
                continue
            max_similarity = max(
                _candidate_similarity(candidate.chunk, chosen.chunk)
                for chosen, _ in selected
            )
            mmr_score = (
                MMR_LAMBDA * candidate.raw_hybrid_score
                - (1.0 - MMR_LAMBDA) * max_similarity
            )
            if mmr_score > best_score:
                best_score = mmr_score
                best_index = index
        if best_index is None:
            # Every remaining candidate is from a document already at its cap;
            # relax the cap to fill the remaining slots by raw hybrid rank.
            break
        chosen = remaining.pop(best_index)
        selected.append((chosen, best_score))
        per_document[_document_key(chosen)] = per_document.get(_document_key(chosen), 0) + 1

    for candidate in remaining:
        if len(selected) >= top_k:
            break
        selected.append((candidate, candidate.raw_hybrid_score))
    return selected


def _candidate_similarity(first: RetrievedChunk, second: RetrievedChunk) -> float:
    first_tokens = _chunk_tokens(first)
    second_tokens = _chunk_tokens(second)
    if not first_tokens or not second_tokens:
        return 0.0

    overlap = len(first_tokens & second_tokens) / len(first_tokens | second_tokens)
    source_penalty = 0.0
    if first.file_name == second.file_name:
        source_penalty += 0.08
    first_row = first.row_start or first.row_number
    second_row = second.row_start or second.row_number
    if first_row is not None and second_row is not None and abs(first_row - second_row) <= 2:
        source_penalty += 0.12
    return min(1.0, overlap + source_penalty)


def _chunk_tokens(chunk: RetrievedChunk) -> set[str]:
    text = " ".join(
        [
            chunk.retrieval_summary or "",
            " ".join(chunk.answerable_questions),
            " ".join(chunk.asset_tags),
            chunk.section_title or "",
            chunk.file_name,
        ]
    )
    return set(_query_tokens(text))


def _rrf_score(vector_rank: int | None, keyword_rank: int | None) -> float:
    score = 0.0
    if vector_rank is not None:
        score += VECTOR_WEIGHT / (RRF_K + vector_rank)
    if keyword_rank is not None:
        score += KEYWORD_WEIGHT / (RRF_K + keyword_rank)
    return score


def _keyword_score(question: str, chunk: RetrievedChunk) -> float:
    tokens = _query_tokens(question)
    assets = _query_assets(question)
    if not tokens and not assets:
        return 0.0

    summary = (chunk.retrieval_summary or "").lower()
    raw_text = (chunk.raw_text or chunk.content or "").lower()
    questions = " ".join(chunk.answerable_questions).lower()
    asset_tags = {tag.upper() for tag in chunk.asset_tags}
    score = 0.0

    for token in tokens:
        if token in summary:
            score += 2.0
        if token in raw_text:
            score += 1.0
        if token in questions:
            score += 3.0

    for asset in assets:
        if asset in asset_tags:
            score += 8.0
        if asset.lower() in summary:
            score += 4.0
        if asset.lower() in raw_text:
            score += 2.0
        if asset.lower() in questions:
            score += 4.0

    return score


def _metadata_boost(question: str, chunk: RetrievedChunk) -> float:
    tokens = _query_tokens(question)
    assets = _query_assets(question)
    if not tokens and not assets:
        return 0.0

    questions_text = " ".join(chunk.answerable_questions).lower()
    asset_tags = {tag.upper() for tag in chunk.asset_tags}
    boost = 0.0

    if assets and any(asset in asset_tags for asset in assets):
        boost += 0.25
    question_overlap = sum(1 for token in tokens if token in questions_text)
    if question_overlap >= 2:
        boost += min(0.25, question_overlap * 0.05)
    if tokens and chunk.asset_tags and any(token in " ".join(chunk.asset_tags).lower() for token in tokens):
        boost += 0.05

    return min(METADATA_BOOST_CAP, boost)


def _query_tokens(question: str) -> list[str]:
    tokens: list[str] = []
    for raw_token in TOKEN_RE.findall(question.lower()):
        token = raw_token.strip("._-")
        if len(token) < 3 or token in STOPWORDS:
            continue
        if token not in tokens:
            tokens.append(token)
    return tokens


def _query_assets(question: str) -> list[str]:
    assets: list[str] = []
    for match in ASSET_RE.findall(question.upper()):
        if match not in assets:
            assets.append(match)
    return assets


def _dedupe_parent_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    deduped: list[RetrievedChunk] = []
    for chunk in chunks:
        key = _parent_key(chunk)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(chunk)
    return deduped


def _parent_key(chunk: RetrievedChunk) -> str:
    return chunk.parent_chunk_id or chunk.chunk_id
