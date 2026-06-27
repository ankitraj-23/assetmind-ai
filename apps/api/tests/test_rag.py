from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.rag.chunking import chunk_units
from app.rag.schemas import ExtractedTextUnit, RAGQueryResponse, RetrievedChunk
from app.services.entity_extraction import extract_equipment_tags


def test_rag_chunking_is_deterministic():
    unit = ExtractedTextUnit(
        file_name="manual.md",
        source_path="data/documents/manual.md",
        unit_index=0,
        page_number=1,
        text="P-101 startup checks. " * 400,
    )

    first = chunk_units("doc-1", [unit], chunk_size=120, overlap=20)
    second = chunk_units("doc-1", [unit], chunk_size=120, overlap=20)

    assert first == second
    assert first[0].chunk_index == 0
    assert first[0].page_number == 1


def test_equipment_tag_extraction_finds_week1_tags():
    tags = extract_equipment_tags(
        "P-101, P-204A, V-101, HX-302, MTR-07, COMP-301, T-301, and B-12."
    )
    normalized = {tag.normalized_value for tag in tags}

    assert {
        "P-101",
        "P-204A",
        "V-101",
        "HX-302",
        "MTR-07",
        "COMP-301",
        "T-301",
        "B-12",
    }.issubset(normalized)


def test_retrieval_returns_structured_output_when_mocked(monkeypatch):
    from app.rag import embeddings, retrieval

    expected = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            content="P-101 vibration limit is 4.5 mm/s RMS.",
            score=0.91,
            distance=0.09,
            file_name="pump_oem_manual.pdf",
            source_path="data/documents/pump_oem_manual.pdf",
            page_number=1,
            chunk_index=0,
        )
    ]

    monkeypatch.setattr(embeddings, "embed_query", lambda question: [0.1] * 384)
    monkeypatch.setattr(retrieval, "_retrieve_by_vector", lambda vector, top_k: expected)

    results = retrieval.retrieve_relevant_chunks("What is the P-101 vibration limit?")

    assert results == expected
    assert results[0].file_name == "pump_oem_manual.pdf"
    assert results[0].score == 0.91


def test_embed_texts_sends_chunks_one_by_one_with_delay(monkeypatch):
    from app.rag import embeddings

    calls = []
    sleeps = []

    def fake_embed_text(text):
        calls.append(text)
        return [float(len(text))]

    monkeypatch.setattr(embeddings, "embed_text", fake_embed_text)
    monkeypatch.setattr(embeddings.time, "sleep", lambda seconds: sleeps.append(seconds))

    vectors = embeddings.embed_texts(["chunk one", "chunk two"])

    assert calls == ["chunk one", "chunk two"]
    assert sleeps == [embeddings.CHUNK_EMBED_DELAY_SECONDS] * 2
    assert vectors == [[9.0], [9.0]]


def test_rag_query_endpoint_validates_response_schema(monkeypatch):
    from app.rag import answer

    monkeypatch.setattr(settings, "persistence_backend", "postgres")

    response_model = RAGQueryResponse(
        answer="P-101 limit is 4.5 mm/s RMS. [1]",
        citations=[],
        confidence=0.8,
        missing_info=[],
        retrieved_chunks=[],
    )
    monkeypatch.setattr(answer, "answer_question", lambda question, top_k=5: response_model)

    client = TestClient(app)
    response = client.post(
        "/rag/query",
        json={"question": "What is the vibration limit for P-101?", "top_k": 5},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == response_model.answer
    assert response.json()["confidence"] == 0.8
