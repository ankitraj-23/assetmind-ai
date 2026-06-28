"""Grounded Gemini answer generation over retrieved RAG chunks."""

from __future__ import annotations

from app.core.config import settings
from app.rag import citations
from app.rag.embeddings import MissingGeminiApiKeyError
from app.rag.retrieval import retrieve_relevant_chunks
from app.rag.schemas import RAGQueryResponse, RetrievedChunk

INSUFFICIENT_ANSWER = "I could not find enough evidence in the uploaded documents."
MIN_CONTEXT_SCORE = 0.15


def _api_key() -> str:
    key = (settings.gemini_api_key or "").strip()
    if not key:
        raise MissingGeminiApiKeyError(
            "GEMINI_API_KEY is not set. Set it before calling /rag/query."
        )
    return key


def _generation_model() -> str:
    return (settings.gemini_generation_model or "gemini-3.5-flash").strip()


def _client():
    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required for Gemini answer generation. "
            "Run 'pip install -r requirements.txt' from apps/api."
        ) from exc

    return genai.Client(api_key=_api_key())


def _confidence(chunks: list[RetrievedChunk]) -> float:
    if not chunks:
        return 0.0
    top_score = max(0.0, min(1.0, chunks[0].score))
    coverage_bonus = min(len(chunks), 5) * 0.03
    return round(min(1.0, top_score + coverage_bonus), 2)


def _context(chunks: list[RetrievedChunk]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        location = f"page {chunk.page_start or chunk.page_number}" if (chunk.page_start or chunk.page_number) else ""
        if chunk.row_start or chunk.row_number:
            row_start = chunk.row_start or chunk.row_number
            row_end = chunk.row_end or row_start
            location = f"rows {row_start}-{row_end}" if row_end != row_start else f"row {row_start}"
        summary = chunk.retrieval_summary or ""
        raw_text = chunk.raw_text or chunk.content
        blocks.append(
            "\n".join(
                [
                    (
                        f"[{index}] file={chunk.file_name} {location} "
                        f"section={chunk.section_title or 'n/a'} "
                        f"parent_chunk_id={chunk.parent_chunk_id or chunk.chunk_id}"
                    ),
                    f"Retrieval summary label (not evidence): {summary}",
                    "Raw parent chunk evidence:",
                    raw_text,
                ]
            )
        )
    return "\n\n".join(blocks)


def _generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    prompt = f"""
You answer questions for AssetMind AI using only the supplied document context.
If the context does not contain enough evidence, answer exactly:
{INSUFFICIENT_ANSWER}

Rules:
- Do not use outside knowledge.
- Use only the text under "Raw parent chunk evidence" as evidence.
- Retrieval summary labels are search hints only; do not cite them as evidence.
- Keep the answer concise and factual.
- Mention source numbers like [1] or [2] beside supported claims.

Question:
{question}

Context:
{_context(chunks)}
""".strip()
    client = _client()
    response = client.models.generate_content(
        model=_generation_model(),
        contents=prompt,
    )
    text = getattr(response, "text", "") or ""
    return text.strip() or INSUFFICIENT_ANSWER


def answer_question(question: str, top_k: int = 5) -> RAGQueryResponse:
    retrieved = retrieve_relevant_chunks(question, top_k=top_k)
    if not retrieved or retrieved[0].score < MIN_CONTEXT_SCORE:
        return RAGQueryResponse(
            answer=INSUFFICIENT_ANSWER,
            citations=[],
            confidence=0.0,
            missing_info=["No sufficiently relevant chunks were retrieved."],
            retrieved_chunks=retrieved,
        )

    answer = _generate_answer(question, retrieved)
    response_citations = citations.citations_from_chunks(retrieved)
    missing_info: list[str] = []
    if answer.strip() == INSUFFICIENT_ANSWER:
        response_citations = []
        missing_info.append("Gemini judged the retrieved context insufficient.")

    return RAGQueryResponse(
        answer=answer,
        citations=response_citations,
        confidence=_confidence(retrieved),
        missing_info=missing_info,
        retrieved_chunks=retrieved,
    )
