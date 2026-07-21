"""Conversation-aware RAG chat orchestration."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select

from app.db.models import ChatMessage, ChatSession
from app.db.session import session_scope
from app.rag import answer as answer_service
from app.rag.retrieval import retrieve_relevant_chunks
from app.rag.schemas import (
    RAGChatHistoryResponse,
    RAGChatMessage,
    RAGChatResponse,
    RAGChatSessionSummary,
    RAGChatSessionsResponse,
    RAGCitation,
)

RECENT_MESSAGE_LIMIT = 6
SUMMARY_CHAR_LIMIT = 1400
REWRITE_CHAR_LIMIT = 500
SUMMARY_METADATA_COUNT_KEY = "summary_message_count"


def answer_chat_message(
    message: str,
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    top_k: int = 7,
    asset_tag: str | None = None,
) -> RAGChatResponse:
    """Answer a chat message using short memory plus standalone retrieval."""

    user_message = message.strip()
    if not user_message:
        raise ValueError("'message' must not be empty.")

    normalized_user_id = _normalize_user_id(user_id)
    chat_session, history = _load_or_create_session(
        session_id,
        user_message,
        normalized_user_id,
    )
    memory = _memory_context(chat_session.summary, history)
    scoped_asset = _normalize_asset_tag(asset_tag)
    standalone_question = rewrite_followup_question(user_message, memory)
    standalone_question = _apply_asset_scope(standalone_question, scoped_asset)
    retrieved = retrieve_relevant_chunks(standalone_question, top_k=top_k)
    response = answer_service.answer_with_chunks(
        user_message,
        retrieved,
        standalone_question=standalone_question,
        conversation_messages=memory,
    )

    user_message_id, assistant_message_id = _store_turn(
        chat_session.id,
        user_message,
        response.answer,
        standalone_question,
        response.citations,
        [chunk.parent_chunk_id or chunk.chunk_id for chunk in retrieved],
        response.confidence,
        history,
        chat_session.summary,
        int((chat_session.metadata_json or {}).get(SUMMARY_METADATA_COUNT_KEY) or 0),
        scoped_asset,
    )

    return RAGChatResponse(
        session_id=chat_session.id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        standalone_question=standalone_question,
        asset_tag=scoped_asset,
        answer=response.answer,
        citations=response.citations,
        confidence=response.confidence,
        missing_info=response.missing_info,
        retrieved_chunks=response.retrieved_chunks,
    )


def list_chat_sessions(user_id: str | None = None) -> RAGChatSessionsResponse:
    normalized_user_id = _normalize_user_id(user_id)
    statement = (
        select(ChatSession, func.count(ChatMessage.id).label("message_count"))
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
    )
    if normalized_user_id:
        statement = statement.where(ChatSession.user_id == normalized_user_id)

    with session_scope() as session:
        rows = session.execute(statement).all()

    return RAGChatSessionsResponse(
        sessions=[
            _session_summary(chat_session, int(message_count or 0))
            for chat_session, message_count in rows
        ]
    )


def get_chat_history(
    session_id: str,
    user_id: str | None = None,
) -> RAGChatHistoryResponse:
    normalized_user_id = _normalize_user_id(user_id)
    with session_scope() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise ValueError(f"Chat session '{session_id}' was not found.")
        if normalized_user_id and chat_session.user_id != normalized_user_id:
            raise ValueError(f"Chat session '{session_id}' was not found.")

        messages = session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        ).scalars().all()
        summary = _session_summary(chat_session, len(messages))
        serialized_messages = [_message_to_schema(message) for message in messages]

    return RAGChatHistoryResponse(session=summary, messages=serialized_messages)


def rewrite_followup_question(
    latest_question: str,
    memory_messages: list[dict[str, str]],
) -> str:
    """Rewrite a follow-up into a standalone retrieval query."""

    question = latest_question.strip()
    if not memory_messages:
        return question
    # Follow-up rewriting needs an LLM; without Gemini the raw question (already
    # asset-scoped by the caller) is used directly.
    from app.rag import embeddings

    if not embeddings.gemini_available():
        return question

    prompt = f"""
Rewrite the latest AssetMind AI user question into a standalone retrieval query.
Do not answer the question.
Preserve exact asset tags such as P-101, HX-201, COMP-301, and row/file details.
Use the conversation only to resolve pronouns or phrases like "that", "it", "those failures".
Return only the standalone query, with no markdown and no explanation.

Recent conversation:
{_format_messages(memory_messages)}

Latest user question:
{question}
""".strip()
    client = answer_service._client()
    response = client.models.generate_content(
        model=answer_service._generation_model(),
        contents=prompt,
    )
    rewritten = (getattr(response, "text", "") or "").strip()
    if not rewritten:
        return question
    if len(rewritten) > REWRITE_CHAR_LIMIT:
        return question
    return " ".join(rewritten.split())


def _load_or_create_session(
    session_id: str | None,
    first_message: str,
    user_id: str | None,
) -> tuple[ChatSession, list[ChatMessage]]:
    with session_scope() as session:
        if session_id:
            chat_session = session.get(ChatSession, session_id)
            if chat_session is None:
                raise ValueError(f"Chat session '{session_id}' was not found.")
            if user_id and chat_session.user_id and chat_session.user_id != user_id:
                raise ValueError(f"Chat session '{session_id}' was not found.")
            if user_id and not chat_session.user_id:
                chat_session.user_id = user_id
                session.flush()
        else:
            chat_session = ChatSession(
                id=f"chat-{uuid4().hex}",
                user_id=user_id,
                title=_title_from_message(first_message),
                metadata_json={"source": "rag_chat"},
            )
            session.add(chat_session)
            session.flush()

        rows = session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        ).scalars().all()
        session.expunge(chat_session)
        for row in rows:
            session.expunge(row)
        return chat_session, list(rows)


def _store_turn(
    session_id: str,
    user_content: str,
    assistant_content: str,
    standalone_question: str,
    citations: list[RAGCitation],
    retrieved_chunk_ids: list[str],
    confidence: float,
    previous_history: list[ChatMessage],
    existing_summary: str | None,
    existing_summary_message_count: int,
    asset_tag: str | None,
) -> tuple[str, str]:
    user_message_id = f"msg-{uuid4().hex}"
    assistant_message_id = f"msg-{uuid4().hex}"
    summary, summary_message_count, summary_was_updated = _summarize_session_if_needed(
        existing_summary,
        existing_summary_message_count,
        previous_history,
        user_content,
        assistant_content,
    )
    with session_scope() as session:
        chat_session = session.get(ChatSession, session_id)
        if chat_session is None:
            raise ValueError(f"Chat session '{session_id}' was not found.")

        session.add(
            ChatMessage(
                id=user_message_id,
                session_id=session_id,
                role="user",
                content=user_content,
                standalone_question=standalone_question,
                metadata_json={"source": "rag_chat", "asset_tag": asset_tag},
            )
        )
        session.add(
            ChatMessage(
                id=assistant_message_id,
                session_id=session_id,
                role="assistant",
                content=assistant_content,
                citations_json=[citation.model_dump(mode="json") for citation in citations],
                retrieved_chunk_ids=retrieved_chunk_ids,
                confidence=confidence,
                metadata_json={"source": "rag_chat", "asset_tag": asset_tag},
            )
        )
        if summary_was_updated:
            metadata = dict(chat_session.metadata_json or {})
            metadata[SUMMARY_METADATA_COUNT_KEY] = summary_message_count
            metadata["summary_strategy"] = "llm"
            metadata["summary_recent_message_limit"] = RECENT_MESSAGE_LIMIT
            metadata["summary_updated_at"] = datetime.utcnow().isoformat()
            chat_session.summary = summary
            chat_session.metadata_json = metadata
        chat_session.updated_at = datetime.utcnow()
    return user_message_id, assistant_message_id


def _memory_context(
    summary: str | None,
    history: list[ChatMessage],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if summary and summary.strip():
        messages.append(
            {
                "role": "assistant",
                "content": f"Conversation summary: {summary.strip()}",
            }
        )
    for message in history[-RECENT_MESSAGE_LIMIT:]:
        if message.role in {"user", "assistant"} and message.content.strip():
            messages.append({"role": message.role, "content": message.content.strip()})
    return messages


def _format_messages(messages: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role in {"user", "assistant"} and content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "No prior conversation."


def _normalize_user_id(user_id: str | None) -> str | None:
    normalized = (user_id or "").strip()
    return normalized or None


def _normalize_asset_tag(asset_tag: str | None) -> str | None:
    normalized = (asset_tag or "").strip().upper()
    return normalized or None


def _apply_asset_scope(question: str, asset_tag: str | None) -> str:
    if not asset_tag:
        return question
    if asset_tag.lower() in question.lower():
        return question
    return f"{question} Asset tag: {asset_tag}."


def _summarize_session_if_needed(
    existing_summary: str | None,
    existing_summary_message_count: int,
    previous_history: list[ChatMessage],
    user_content: str,
    assistant_content: str,
) -> tuple[str | None, int, bool]:
    history = _history_messages(previous_history)
    history.extend(
        [
            {"role": "user", "content": user_content.strip()},
            {"role": "assistant", "content": assistant_content.strip()},
        ]
    )
    target_summary_count = max(0, len(history) - RECENT_MESSAGE_LIMIT)
    already_summarized = max(0, min(existing_summary_message_count, len(history)))
    if target_summary_count <= already_summarized:
        return existing_summary, already_summarized, False

    messages_to_summarize = history[already_summarized:target_summary_count]
    if not messages_to_summarize:
        return existing_summary, already_summarized, False

    try:
        summary = _llm_compact_summary(existing_summary, messages_to_summarize)
    except Exception:
        summary = _fallback_compact_summary(existing_summary, messages_to_summarize)
    return summary, target_summary_count, True


def _history_messages(history: list[ChatMessage]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for message in history:
        if message.role in {"user", "assistant"} and message.content.strip():
            messages.append({"role": message.role, "content": message.content.strip()})
    return messages


def _llm_compact_summary(
    existing_summary: str | None,
    messages_to_summarize: list[dict[str, str]],
) -> str:
    prompt = f"""
Compress the older AssetMind AI chat messages into a durable session summary.

Rules:
- Keep only information useful for future follow-up questions.
- Preserve exact asset tags such as P-101, HX-201, COMP-301.
- Preserve important user intent, constraints, conclusions, unresolved questions, and cited maintenance facts.
- Do not add facts that are not present in the messages.
- Keep the summary under {SUMMARY_CHAR_LIMIT} characters.
- Return only the updated summary text.

Existing summary:
{(existing_summary or '').strip() or 'None yet.'}

Older messages to merge:
{_format_messages(messages_to_summarize)}
""".strip()
    client = answer_service._client()
    response = client.models.generate_content(
        model=answer_service._generation_model(),
        contents=prompt,
    )
    summary = " ".join(((getattr(response, "text", "") or "").strip()).split())
    if not summary:
        return _fallback_compact_summary(existing_summary, messages_to_summarize)
    if len(summary) > SUMMARY_CHAR_LIMIT:
        summary = summary[:SUMMARY_CHAR_LIMIT].rstrip()
    return summary


def _fallback_compact_summary(
    existing_summary: str | None,
    messages_to_summarize: list[dict[str, str]],
) -> str:
    parts: list[str] = []
    if existing_summary and existing_summary.strip():
        parts.append(existing_summary.strip())
    parts.append(_format_messages(messages_to_summarize))
    summary = "\n".join(parts)
    if len(summary) <= SUMMARY_CHAR_LIMIT:
        return summary
    return summary[-SUMMARY_CHAR_LIMIT:]


def _title_from_message(message: str) -> str:
    title = " ".join(message.strip().split())
    if len(title) <= 80:
        return title
    return f"{title[:77].rstrip()}..."


def _session_summary(
    chat_session: ChatSession,
    message_count: int,
) -> RAGChatSessionSummary:
    return RAGChatSessionSummary(
        session_id=chat_session.id,
        title=chat_session.title,
        user_id=chat_session.user_id,
        message_count=message_count,
        updated_at=chat_session.updated_at,
        created_at=chat_session.created_at,
    )


def _message_to_schema(message: ChatMessage) -> RAGChatMessage:
    citations: list[RAGCitation] = []
    for citation in list(message.citations_json or []):
        if isinstance(citation, dict):
            try:
                citations.append(RAGCitation(**citation))
            except Exception:
                continue
    return RAGChatMessage(
        id=message.id,
        role=message.role,
        content=message.content,
        standalone_question=message.standalone_question,
        citations=citations,
        retrieved_chunk_ids=list(message.retrieved_chunk_ids or []),
        confidence=message.confidence,
        created_at=message.created_at,
    )
