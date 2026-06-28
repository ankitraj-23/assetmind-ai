from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.rag.chunking import build_parent_chunks
from app.rag.extraction import extract_file
from app.rag.schemas import DocumentElement, RAGQueryResponse, RetrievedChunk
from app.rag.summaries import build_retrieval_unit, template_summary
from app.services.entity_extraction import extract_equipment_tags


def _element(index: int, text: str, **overrides):
    data = {
        "element_id": f"doc-1:element:paragraph:{index}",
        "document_id": "doc-1",
        "element_type": "paragraph",
        "text": text,
        "source_type": "pdf",
        "file_name": "manual.pdf",
        "source_path": "data/documents/manual.pdf",
        "page_number": 1,
        "section_title": "Startup",
        "asset_tags": ["P-101"],
        "modality": "text",
    }
    data.update(overrides)
    return DocumentElement(**data)


def test_text_extraction_returns_document_elements(tmp_path: Path):
    path = tmp_path / "sample.md"
    path.write_text("# Startup\n- Check P-101 seal flush.\nConfirm vibration.", encoding="utf-8")

    elements = extract_file(path, document_id="doc-1")

    assert elements
    assert elements[0].element_type == "heading"
    assert all(element.document_id == "doc-1" for element in elements)
    assert any("P-101" in element.asset_tags for element in elements)


def test_csv_row_becomes_table_row_element(tmp_path: Path):
    path = tmp_path / "work_orders.csv"
    path.write_text(
        "Equipment_ID,OrderType,Status,Action\nP-101,CM,Closed,Replaced seal\n",
        encoding="utf-8",
    )

    elements = extract_file(path, document_id="doc-1")

    assert len(elements) == 1
    assert elements[0].element_type == "table_row"
    assert elements[0].row_index == 1
    assert elements[0].modality == "table"
    assert "P-101" in elements[0].asset_tags


def test_parent_chunk_builder_preserves_metadata():
    elements = [
        _element(0, "Startup procedure for P-101."),
        _element(1, "Verify suction valve and seal flush pressure."),
    ]

    chunks = build_parent_chunks("doc-1", elements)

    assert len(chunks) == 1
    assert chunks[0].section_title == "Startup"
    assert chunks[0].page_start == 1
    assert chunks[0].asset_tags == ["P-101"]
    assert set(chunks[0].element_ids) == {element.element_id for element in elements}


def test_summary_fallback_works_without_gemini_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    parent = build_parent_chunks("doc-1", [_element(0, "P-101 startup checks.")])[0]

    retrieval_unit = build_retrieval_unit(parent)

    assert retrieval_unit.summary_strategy == "passthrough"
    assert "P-101" in retrieval_unit.summary_text
    assert retrieval_unit.parent_chunk_id == parent.parent_chunk_id


def test_template_summary_for_csv_contains_equipment_id_and_fields():
    csv_element = _element(
        0,
        "Equipment_ID: P-101 | OrderType: CM | Status: Closed | Action: Bearing replaced",
        element_type="table_row",
        source_type="csv",
        file_name="work_orders_clean.csv",
        row_index=12,
        section_title=None,
        modality="table",
    )
    parent = build_parent_chunks("doc-1", [csv_element])[0]

    summary = template_summary(parent)

    assert "P-101" in summary
    assert "work order" in summary.lower()
    assert "Status" in summary or "statuses" in summary


def test_retrieval_returns_structured_output_when_mocked(monkeypatch):
    from app.rag import embeddings, retrieval

    expected = [
        RetrievedChunk(
            chunk_id="chunk-1",
            document_id="doc-1",
            parent_chunk_id="parent-1",
            retrieval_unit_id="ru-1",
            content="P-101 vibration limit is 4.5 mm/s RMS.",
            raw_text="P-101 vibration limit is 4.5 mm/s RMS.",
            retrieval_summary="Pump vibration limit for P-101.",
            summary_strategy="template",
            score=0.91,
            distance=0.09,
            file_name="pump_oem_manual.pdf",
            source_path="data/documents/pump_oem_manual.pdf",
            source_type="pdf",
            page_number=1,
            page_start=1,
            page_end=1,
            chunk_index=0,
            asset_tags=["P-101"],
            modality="text",
        )
    ]

    monkeypatch.setattr(embeddings, "embed_query", lambda question: [0.1] * 384)
    monkeypatch.setattr(retrieval, "_retrieve_by_vector", lambda vector, top_k: expected)

    results = retrieval.retrieve_relevant_chunks("What is the P-101 vibration limit?")

    assert results == expected
    assert results[0].raw_text
    assert results[0].retrieval_summary
    assert results[0].parent_chunk_id == "parent-1"


def test_answer_context_uses_raw_text_not_summary_as_evidence():
    from app.rag.answer import _context

    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        parent_chunk_id="parent-1",
        retrieval_unit_id="ru-1",
        content="RAW EVIDENCE: seal flush pressure is 0.8 to 1.2 bar.",
        raw_text="RAW EVIDENCE: seal flush pressure is 0.8 to 1.2 bar.",
        retrieval_summary="SUMMARY ONLY: pump startup checks.",
        summary_strategy="llm",
        score=0.9,
        file_name="sop_pump_startup.pdf",
        page_start=1,
        chunk_index=0,
    )

    context = _context([chunk])

    assert "Retrieval summary label (not evidence): SUMMARY ONLY" in context
    assert "Raw parent chunk evidence:" in context
    assert "RAW EVIDENCE" in context


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
