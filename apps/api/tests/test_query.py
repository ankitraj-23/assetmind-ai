"""Tests for the backward-compatible ``POST /query`` route.

``/query`` is a thin adapter over the canonical RAG pipeline (the same
retrieval/answer path used by ``/rag/chat`` and the benchmark). These tests lock
in the legacy ``QueryResponse`` contract, asset scoping, grounded-citation
mapping, empty-evidence handling, and the deterministic (no-Gemini) fallback.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.rag.schemas import RAGCitation, RAGQueryResponse, RetrievedChunk


def _chunk(**overrides) -> RetrievedChunk:
    data = {
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "parent_chunk_id": "parent-1",
        "content": "P-101 vibration limit is 4.5 mm/s RMS. Related to HX-201.",
        "raw_text": "P-101 vibration limit is 4.5 mm/s RMS. Related to HX-201.",
        "retrieval_summary": "Pump vibration limit.",
        "score": 0.82,
        "file_name": "pump_oem_manual.pdf",
        "source_path": "data/documents/pump_oem_manual.pdf",
        "source_type": "pdf",
        "page_start": 3,
        "page_number": 3,
        "chunk_index": 2,
        "asset_tags": ["P-101"],
        "modality": "text",
    }
    data.update(overrides)
    return RetrievedChunk(**data)


def _citation(chunk: RetrievedChunk) -> RAGCitation:
    return RAGCitation(
        file_name=chunk.file_name,
        page=chunk.page_start,
        chunk_id=chunk.chunk_id,
        parent_chunk_id=chunk.parent_chunk_id,
        source_path=chunk.source_path,
        snippet="P-101 vibration limit is 4.5 mm/s RMS.",
    )


def _grounded_response(chunk: RetrievedChunk) -> RAGQueryResponse:
    return RAGQueryResponse(
        answer="The P-101 vibration limit is 4.5 mm/s RMS. [1]",
        citations=[_citation(chunk)],
        confidence=0.82,
        missing_info=[],
        retrieved_chunks=[chunk],
    )


def test_query_global_returns_contract_and_answer(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    chunk = _chunk()

    from app.routes import query as query_route

    monkeypatch.setattr(query_route, "retrieve_relevant_chunks", lambda q, top_k=5: [chunk])
    monkeypatch.setattr(
        query_route.answer_service,
        "answer_with_chunks",
        lambda question, retrieved, standalone_question=None: _grounded_response(chunk),
    )

    client = TestClient(app)
    response = client.post("/query", json={"question": "What is the vibration limit?", "top_k": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "What is the vibration limit?"
    assert body["answer"].startswith("The P-101 vibration limit")
    assert body["confidence"] == "high"
    assert body["retrieved_count"] == 1


def test_query_asset_scope_is_applied_to_retrieval(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    chunk = _chunk()
    seen: dict[str, str] = {}

    from app.routes import query as query_route

    def fake_retrieve(question, top_k=5):
        seen["question"] = question
        return [chunk]

    monkeypatch.setattr(query_route, "retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr(
        query_route.answer_service,
        "answer_with_chunks",
        lambda question, retrieved, standalone_question=None: _grounded_response(chunk),
    )

    client = TestClient(app)
    response = client.post(
        "/query",
        json={"question": "How can failures be prevented?", "asset_tag": "p-101"},
    )

    assert response.status_code == 200
    # Asset tag is normalized (upper) and appended to the retrieval query.
    assert "Asset tag: P-101." in seen["question"]
    # The query asset itself is excluded from related_assets, but co-mentioned ones remain.
    assert "P-101" not in response.json()["related_assets"]
    assert "HX-201" in response.json()["related_assets"]


def test_query_returns_grounded_citations_mapped_from_chunks(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    chunk = _chunk()

    from app.routes import query as query_route

    monkeypatch.setattr(query_route, "retrieve_relevant_chunks", lambda q, top_k=5: [chunk])
    monkeypatch.setattr(
        query_route.answer_service,
        "answer_with_chunks",
        lambda question, retrieved, standalone_question=None: _grounded_response(chunk),
    )

    client = TestClient(app)
    response = client.post("/query", json={"question": "What is the vibration limit?"})

    assert response.status_code == 200
    citations = response.json()["citations"]
    assert len(citations) == 1
    citation = citations[0]
    # document_id / chunk_index / score are enriched from the originating chunk.
    assert citation["document_id"] == "doc-1"
    assert citation["chunk_id"] == "chunk-1"
    assert citation["chunk_index"] == 2
    assert citation["score"] == 0.82
    assert citation["filename"] == "pump_oem_manual.pdf"
    assert citation["page_number"] == 3
    assert citation["text_preview"]


def test_query_insufficient_evidence_returns_empty_citations(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")

    from app.routes import query as query_route

    insufficient = RAGQueryResponse(
        answer="I could not find enough evidence in the uploaded documents.",
        citations=[],
        confidence=0.0,
        missing_info=["No sufficiently relevant chunks were retrieved."],
        retrieved_chunks=[],
    )
    monkeypatch.setattr(query_route, "retrieve_relevant_chunks", lambda q, top_k=5: [])
    monkeypatch.setattr(
        query_route.answer_service,
        "answer_with_chunks",
        lambda question, retrieved, standalone_question=None: insufficient,
    )

    client = TestClient(app)
    response = client.post("/query", json={"question": "Tell me about ZX-999.", "asset_tag": "ZX-999"})

    assert response.status_code == 200
    body = response.json()
    assert body["citations"] == []
    assert body["confidence"] == "low"
    assert body["retrieved_count"] == 0
    assert body["related_assets"] == []


def test_query_fallback_answer_without_gemini(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    chunk = _chunk()

    from app.routes import query as query_route

    # Only retrieval is stubbed; the *real* answer path runs and, without a
    # Gemini key, falls back to grounded deterministic extraction.
    monkeypatch.setattr(query_route, "retrieve_relevant_chunks", lambda q, top_k=5: [chunk])

    client = TestClient(app)
    response = client.post("/query", json={"question": "What is the P-101 vibration limit?"})

    assert response.status_code == 200
    body = response.json()
    assert "deterministic extraction" in body["answer"]
    assert body["citations"], "fallback answer must still return grounded citations"
    assert body["citations"][0]["filename"] == "pump_oem_manual.pdf"


def test_query_empty_question_returns_400(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")
    client = TestClient(app)
    response = client.post("/query", json={"question": "   "})
    assert response.status_code == 400


def test_query_pipeline_error_maps_to_http_error(monkeypatch):
    monkeypatch.setattr(settings, "persistence_backend", "postgres")

    from app.routes import query as query_route

    def boom(question, top_k=5):
        raise ValueError("bad retrieval input")

    monkeypatch.setattr(query_route, "retrieve_relevant_chunks", boom)

    client = TestClient(app)
    response = client.post("/query", json={"question": "trigger error"})

    # A pipeline exception must become a proper HTTP error, never an AttributeError.
    assert response.status_code == 400
    assert "bad retrieval input" in response.json()["detail"]
