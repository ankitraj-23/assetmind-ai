import base64
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.rag.chunking import build_parent_chunks
from app.rag.extraction import extract_file
from app.rag.schemas import (
    DocumentElement,
    RAGChatHistoryResponse,
    RAGChatMessage,
    RAGChatResponse,
    RAGChatSessionSummary,
    RAGChatSessionsResponse,
    RAGQueryResponse,
    RetrievedChunk,
)
from app.rag.summaries import (
    build_parent_summary,
    build_retrieval_unit,
    summarize_atomic_elements,
)
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


def test_csv_row_becomes_text_element_with_quoted_columns(tmp_path: Path):
    path = tmp_path / "work_orders.csv"
    path.write_text(
        "Equipment_ID,OrderType,Status,Action\nP-101,CM,Closed,Replaced seal\n",
        encoding="utf-8",
    )

    elements = extract_file(path, document_id="doc-1")

    assert len(elements) == 1
    assert elements[0].element_type == "paragraph"
    assert elements[0].row_index == 1
    assert elements[0].modality == "text"
    assert elements[0].text == (
        "'Equipment_ID': P-101. 'OrderType': CM. 'Status': Closed. "
        "'Action': Replaced seal."
    )
    assert "P-101" in elements[0].asset_tags


def test_pdf_embedded_image_becomes_visual_element(tmp_path: Path, monkeypatch):
    import fitz

    monkeypatch.setattr(settings, "rag_visual_storage_dir", str(tmp_path / "visuals"))
    pdf_path = tmp_path / "visual.pdf"
    png_bytes = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Pump P-101 inspection visual.")
    page.insert_image(fitz.Rect(72, 100, 140, 160), stream=png_bytes)
    document.save(pdf_path)
    document.close()

    elements = extract_file(pdf_path, document_id="doc-visual")
    visual_elements = [element for element in elements if element.modality == "image"]
    embedded = [
        element
        for element in visual_elements
        if element.metadata.get("visual_kind") == "embedded_image"
    ]

    assert len(embedded) == 1
    assert embedded[0].element_type == "image"
    assert embedded[0].source_path == str(pdf_path.resolve())
    assert Path(embedded[0].metadata["visual_path"]).exists()


def test_pdf_text_only_page_does_not_create_visual_element(tmp_path: Path, monkeypatch):
    import fitz

    monkeypatch.setattr(settings, "rag_visual_storage_dir", str(tmp_path / "visuals"))
    pdf_path = tmp_path / "text_only.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Pump P-101 text-only page.")
    document.save(pdf_path)
    document.close()

    elements = extract_file(pdf_path, document_id="doc-text-visual")

    assert not [element for element in elements if element.modality == "image"]


def test_direct_image_file_becomes_visual_element(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "rag_visual_storage_dir", str(tmp_path / "visuals"))
    image_path = tmp_path / "pump_p101.png"
    image_path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
    )

    elements = extract_file(image_path, document_id="doc-image")

    assert len(elements) == 1
    assert elements[0].element_type == "image"
    assert elements[0].source_type == "image"
    assert elements[0].modality == "image"
    assert elements[0].metadata["visual_kind"] == "direct_image"
    assert elements[0].metadata["mime_type"] == "image/png"
    assert Path(elements[0].metadata["visual_path"]).exists()
    assert elements[0].metadata["original_visual_path"] == str(image_path.resolve())


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

    assert retrieval_unit.summary_strategy == "parent_passthrough"
    assert "P-101" in retrieval_unit.summary_text
    assert retrieval_unit.answerable_questions
    assert retrieval_unit.parent_chunk_id == parent.parent_chunk_id


def test_csv_text_element_is_not_atomically_summarized():
    csv_element = _element(
        0,
        "'Equipment_ID': P-101. 'OrderType': CM. 'Status': Closed. 'Action': Bearing replaced.",
        element_type="paragraph",
        source_type="csv",
        file_name="work_orders_clean.csv",
        row_index=12,
        section_title=None,
        modality="text",
    )

    summarized = summarize_atomic_elements([csv_element])

    assert summarized[0].element_summary is None
    assert summarized[0].summary_strategy is None
    assert "atomic_summary" not in summarized[0].metadata


def test_parent_summary_contains_questions_and_asset_tags(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    parent = build_parent_chunks("doc-1", [_element(0, "P-101 startup checks.")])[0]

    summary = build_parent_summary(parent)

    assert summary.summary_strategy == "parent_passthrough"
    assert "P-101" in summary.asset_tags
    assert len(summary.answerable_questions) == 5


def test_parent_chunk_uses_csv_text_directly():
    csv_element = _element(
        0,
        "'Equipment_ID': P-101. 'OrderType': CM. 'Status': Closed. 'Action': Bearing replaced.",
        element_type="paragraph",
        source_type="csv",
        file_name="work_orders_clean.csv",
        row_index=12,
        section_title=None,
        modality="text",
    )

    summarized = summarize_atomic_elements([csv_element])
    parent = build_parent_chunks("doc-1", summarized)[0]

    assert parent.element_summaries == []
    assert "summary for" not in parent.raw_text
    assert "Row 12:" in parent.raw_text
    assert "'Equipment_ID': P-101" in parent.raw_text
    assert "P-101" in parent.raw_text


def test_parent_chunk_keeps_original_visual_evidence_separate_from_summary():
    visual_element = _element(
        0,
        "Original chart values show P-101 vibration rising from 2.1 to 4.4 mm/s.",
        element_type="image_caption",
        source_type="pdf",
        file_name="inspection_report_q1_2025.pdf",
        page_number=2,
        section_title="Trend Chart",
        modality="image",
        metadata={
            "atomic_summary": {
                "element_id": "doc-1:element:image_caption:0",
                "element_type": "image_caption",
                "summary_text": "Summary says P-101 vibration trend increased.",
                "summary_strategy": "visual_llm",
                "asset_tags": ["P-101"],
                "metadata": {"questions_generated": False},
            }
        },
        element_summary="Summary says P-101 vibration trend increased.",
        summary_strategy="visual_llm",
    )

    parent = build_parent_chunks("doc-1", [visual_element])[0]

    assert parent.element_summaries
    assert parent.visual_elements
    assert "Original chart values" in parent.raw_text
    assert "Summary says" not in parent.raw_text
    assert parent.metadata["text_evidence"] == ""
    assert parent.visual_elements[0].text.startswith("Original chart values")


def test_each_csv_row_becomes_its_own_parent_chunk():
    rows = [
        _element(
            0,
            "'Equipment_ID': P-101. 'OrderType': CM. 'Status': Closed.",
            element_type="paragraph",
            source_type="csv",
            file_name="work_orders_clean.csv",
            row_index=1,
            section_title=None,
            modality="text",
        ),
        _element(
            1,
            "'Equipment_ID': P-102. 'OrderType': PM. 'Status': Open.",
            element_type="paragraph",
            source_type="csv",
            file_name="work_orders_clean.csv",
            row_index=2,
            section_title=None,
            modality="text",
            asset_tags=["P-102"],
        ),
    ]

    chunks = build_parent_chunks("doc-1", rows)

    assert len(chunks) == 2
    assert chunks[0].row_start == 1
    assert chunks[0].row_end == 1
    assert chunks[0].metadata["element_count"] == 1
    assert chunks[1].row_start == 2
    assert chunks[1].row_end == 2
    assert chunks[1].metadata["element_count"] == 1


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
            answerable_questions=["What is the P-101 vibration limit?"],
            summary_strategy="parent_passthrough",
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
            element_summaries=[{"element_id": "el-1"}],
        )
    ]

    monkeypatch.setattr(embeddings, "embed_query", lambda question: [0.1] * 384)
    monkeypatch.setattr(retrieval, "_retrieve_by_vector", lambda vector, top_k: expected)
    monkeypatch.setattr(retrieval, "_retrieve_by_keyword", lambda question, top_k: [])

    results = retrieval.retrieve_relevant_chunks("What is the P-101 vibration limit?")

    assert len(results) == 1
    assert results[0].raw_text
    assert results[0].retrieval_summary
    assert results[0].answerable_questions
    assert results[0].element_summaries
    assert results[0].parent_chunk_id == "parent-1"
    assert results[0].metadata["retrieval_strategy"] == "hybrid_vector_keyword_rrf_rerank_mmr"
    assert results[0].metadata["mmr"]["enabled"] is True


def test_hybrid_retrieval_fuses_vector_keyword_and_metadata(monkeypatch):
    from app.rag import embeddings, retrieval

    vector_only = RetrievedChunk(
        chunk_id="chunk-vector",
        document_id="doc-1",
        parent_chunk_id="parent-vector",
        content="Generic pump information.",
        raw_text="Generic pump information.",
        retrieval_summary="Generic centrifugal pump summary.",
        answerable_questions=["What generic pump information is available?"],
        score=0.95,
        file_name="manual.pdf",
        chunk_index=0,
        asset_tags=[],
    )
    keyword_match = RetrievedChunk(
        chunk_id="chunk-keyword",
        document_id="doc-1",
        parent_chunk_id="parent-keyword",
        content="P-101 startup says open suction valve and start centrifugal pump.",
        raw_text="P-101 startup says open suction valve and start centrifugal pump.",
        retrieval_summary="P-101 centrifugal pump startup procedure.",
        answerable_questions=[
            "What is the standard procedure for starting centrifugal pump P-101?"
        ],
        score=42.0,
        file_name="sop_pump_startup.pdf",
        chunk_index=1,
        asset_tags=["P-101"],
    )

    monkeypatch.setattr(embeddings, "embed_query", lambda question: [0.1] * 384)
    monkeypatch.setattr(retrieval, "_retrieve_by_vector", lambda vector, top_k: [vector_only])
    monkeypatch.setattr(retrieval, "_retrieve_by_keyword", lambda question, top_k: [keyword_match])

    results = retrieval.retrieve_relevant_chunks(
        "what is the standard procedure for starting centrifugal pump P-101",
        top_k=2,
    )

    assert [chunk.parent_chunk_id for chunk in results] == ["parent-keyword", "parent-vector"]
    assert results[0].metadata["hybrid_scores"]["keyword_score"] == 1.0
    assert results[0].metadata["hybrid_scores"]["metadata_boost"] > 0
    assert results[0].metadata["hybrid_ranks"]["keyword_rank"] == 1
    assert results[1].metadata["hybrid_ranks"]["vector_rank"] == 1


def test_mmr_promotes_diverse_sources_after_hybrid_rank():
    from app.rag import retrieval

    def chunk(chunk_id: str, summary: str, file_name: str, row: int, score: float):
        return RetrievedChunk(
            chunk_id=chunk_id,
            document_id="doc-1",
            parent_chunk_id=chunk_id,
            content=summary,
            raw_text=summary,
            retrieval_summary=summary,
            answerable_questions=[f"What does {summary} say?"],
            score=score,
            file_name=file_name,
            row_start=row,
            row_end=row,
            chunk_index=row,
            asset_tags=["P-101"],
        )

    near_duplicate = retrieval.CandidateScores(
        chunk=chunk("near", "P-101 seal failure leakage work order", "work_orders.csv", 11, 0.98),
        raw_hybrid_score=0.98,
    )
    diverse = retrieval.CandidateScores(
        chunk=chunk("diverse", "P-101 bearing overheating alarm", "work_orders.csv", 40, 0.93),
        raw_hybrid_score=0.93,
    )
    first = retrieval.CandidateScores(
        chunk=chunk("first", "P-101 seal failure leakage work order", "work_orders.csv", 10, 1.0),
        raw_hybrid_score=1.0,
    )

    selected = retrieval._mmr_select([first, near_duplicate, diverse], top_k=2)

    assert [entry.chunk.chunk_id for entry, _ in selected] == ["first", "diverse"]


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
        visual_elements=[
            {
                "element_id": "visual-1",
                "element_type": "image_caption",
                "modality": "image",
                "page_number": 1,
                "bbox": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
                "text": "Original visual says P-101 vibration was 4.4 mm/s.",
            }
        ],
    )

    context = _context([chunk])

    assert "Retrieval summary label (not evidence): SUMMARY ONLY" in context
    assert "Raw parent chunk evidence:" in context
    assert "RAW EVIDENCE" in context
    assert "Original visual element evidence:" in context
    assert "Original visual says P-101 vibration was 4.4 mm/s." in context


def test_gemini_contents_attach_visual_bytes(tmp_path: Path):
    from app.rag.answer import _gemini_contents

    image_path = tmp_path / "visual.png"
    image_path.write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
        )
    )
    chunk = RetrievedChunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        content="Visual evidence available.",
        score=0.9,
        file_name="inspection_report_q1_2025.pdf",
        page_start=1,
        chunk_index=0,
        visual_elements=[
            {
                "element_id": "visual-1",
                "element_type": "image",
                "modality": "image",
                "page_number": 1,
                "text": "visual_path reference",
                "metadata": {
                    "visual_path": str(image_path),
                    "mime_type": "image/png",
                },
            }
        ],
    )

    contents = _gemini_contents("prompt", [chunk])

    assert isinstance(contents, list)
    assert contents[0] == "prompt"
    assert "visual-1" in contents[1]
    assert len(contents) == 3


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


def test_chat_memory_uses_summary_and_recent_messages_only():
    from app.rag import chat

    class Message:
        def __init__(self, role: str, content: str):
            self.role = role
            self.content = content

    history = [Message("user", f"question {index}") for index in range(10)]

    memory = chat._memory_context("The user is discussing P-101 failures.", history)

    assert memory[0]["content"] == "Conversation summary: The user is discussing P-101 failures."
    assert len(memory) == chat.RECENT_MESSAGE_LIMIT + 1
    assert memory[1]["content"] == "question 4"
    assert memory[-1]["content"] == "question 9"


def test_chat_summary_compression_starts_after_fourth_user_question(monkeypatch):
    from app.rag import chat

    class Message:
        def __init__(self, role: str, content: str):
            self.role = role
            self.content = content

    six_messages = [
        Message("user", "question 1"),
        Message("assistant", "answer 1"),
        Message("user", "question 2"),
        Message("assistant", "answer 2"),
        Message("user", "question 3"),
        Message("assistant", "answer 3"),
    ]
    summarized_batches = []

    def fake_llm_summary(existing_summary, messages_to_summarize):
        summarized_batches.append(messages_to_summarize)
        return "LLM summary of older P-101 discussion."

    monkeypatch.setattr(chat, "_llm_compact_summary", fake_llm_summary)

    summary, message_count, was_updated = chat._summarize_session_if_needed(
        None,
        0,
        six_messages,
        "question 4",
        "answer 4",
    )

    assert was_updated is True
    assert summary == "LLM summary of older P-101 discussion."
    assert message_count == 2
    assert summarized_batches == [
        [
            {"role": "user", "content": "question 1"},
            {"role": "assistant", "content": "answer 1"},
        ]
    ]


def test_chat_asset_scope_is_added_to_standalone_query():
    from app.rag import chat

    assert (
        chat._apply_asset_scope("How can failures be prevented?", "P-101")
        == "How can failures be prevented? Asset tag: P-101."
    )
    assert chat._apply_asset_scope("How can P-101 failures be prevented?", "P-101") == (
        "How can P-101 failures be prevented?"
    )


def test_rag_chat_endpoint_validates_response_schema(monkeypatch):
    from app.rag import chat

    monkeypatch.setattr(settings, "persistence_backend", "postgres")

    response_model = RAGChatResponse(
        session_id="chat-1",
        user_message_id="msg-user",
        assistant_message_id="msg-assistant",
        standalone_question="How can pump P-101 failures be prevented?",
        answer="Prevent P-101 failures by addressing seal leakage and overloads. [1]",
        citations=[],
        confidence=0.82,
        missing_info=[],
        retrieved_chunks=[],
    )
    monkeypatch.setattr(
        chat,
        "answer_chat_message",
        lambda message, session_id=None, user_id=None, top_k=7, asset_tag=None: response_model,
    )

    client = TestClient(app)
    response = client.post(
        "/rag/chat",
        json={"message": "How can we prevent that?", "top_k": 7},
    )

    assert response.status_code == 200
    assert response.json()["session_id"] == "chat-1"
    assert response.json()["standalone_question"] == response_model.standalone_question
    assert response.json()["answer"] == response_model.answer


def test_rag_chat_session_endpoints_validate_response_schema(monkeypatch):
    from app.rag import chat

    monkeypatch.setattr(settings, "persistence_backend", "postgres")

    session_summary = RAGChatSessionSummary(
        session_id="chat-1",
        title="P-101 failure",
        user_id="user-1",
        message_count=2,
    )
    monkeypatch.setattr(
        chat,
        "list_chat_sessions",
        lambda user_id=None: RAGChatSessionsResponse(sessions=[session_summary]),
    )
    monkeypatch.setattr(
        chat,
        "get_chat_history",
        lambda session_id, user_id=None: RAGChatHistoryResponse(
            session=session_summary,
            messages=[
                RAGChatMessage(id="m1", role="user", content="Why can P-101 fail?"),
                RAGChatMessage(id="m2", role="assistant", content="Seal leakage. [1]"),
            ],
        ),
    )

    client = TestClient(app)
    list_response = client.get("/rag/chat/sessions?user_id=user-1")
    history_response = client.get("/rag/chat/sessions/chat-1?user_id=user-1")

    assert list_response.status_code == 200
    assert list_response.json()["sessions"][0]["session_id"] == "chat-1"
    assert history_response.status_code == 200
    assert len(history_response.json()["messages"]) == 2
