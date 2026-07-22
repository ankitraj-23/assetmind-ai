"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { Card, PageHeader, Badge } from "@/components/ui";
import {
  getCopilotChat,
  queryCopilot,
  listAssets,
  listCopilotChats,
  type ApiChatSessionSummary,
  type ApiQueryResponse,
  type ApiAsset,
} from "@/lib/api";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  assetTag?: string;
  result?: ApiQueryResponse;
};

const USER_ID_STORAGE_KEY = "assetmind_copilot_user_id";

function extractTags(text: string) {
  const matches = text.match(/\b([A-Za-z]{1,4})-(\d{1,4})([A-Za-z]?)\b/g);
  return matches ? Array.from(new Set(matches.map((match) => match.toUpperCase()))) : [];
}

function getOrCreateUserId() {
  const existing = window.localStorage.getItem(USER_ID_STORAGE_KEY);
  if (existing) return existing;
  const generated =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? `web-${crypto.randomUUID()}`
      : `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  window.localStorage.setItem(USER_ID_STORAGE_KEY, generated);
  return generated;
}

export default function CopilotPage() {
  const [question, setQuestion] = useState("");
  const [selectedAsset, setSelectedAsset] = useState("");
  const [userId, setUserId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ApiChatSessionSummary[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [assets, setAssets] = useState<ApiAsset[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">(
    "idle",
  );
  const [result, setResult] = useState<ApiQueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const uid = getOrCreateUserId();
    setUserId(uid);
    listAssets()
      .then(setAssets)
      .catch(() => setAssets([]));

    // Deep-link handling: ?asset= scopes the chat, ?q= prefills and runs a
    // search. This is a deliberate search action (e.g. from the header), not an
    // agent auto-execution.
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const assetParam = params.get("asset");
    const queryParam = params.get("q");

    const initialAsset = assetParam ? assetParam.toUpperCase() : "";
    if (initialAsset) setSelectedAsset(initialAsset);

    if (queryParam) {
      setQuestion(queryParam);
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: queryParam,
        assetTag: initialAsset || undefined,
      };
      setMessages([userMessage]);
      setStatus("loading");
      setError(null);
      queryCopilot({
        question: queryParam,
        top_k: 7,
        asset_tag: initialAsset || undefined,
        user_id: uid || undefined,
      })
        .then((res) => {
          setSessionId(res.session_id ?? null);
          setResult(res);
          setMessages((current) => [
            ...current,
            {
              id: `assistant-${Date.now()}`,
              role: "assistant",
              content: res.answer,
              assetTag: (res.asset_tag ?? initialAsset) || undefined,
              result: res,
            },
          ]);
          setStatus("done");
          listCopilotChats(uid).then(setSessions).catch(() => {});
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "Failed to run search.");
          setStatus("error");
        });
    }
  }, []);

  useEffect(() => {
    if (!userId) return;
    listCopilotChats(userId)
      .then(setSessions)
      .catch(() => setSessions([]));
  }, [userId]);

  async function refreshSessions(currentUserId = userId) {
    if (!currentUserId) return;
    try {
      setSessions(await listCopilotChats(currentUserId));
    } catch {
      setSessions([]);
    }
  }

  async function handleAsk(e: FormEvent) {
    e.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: trimmed,
      assetTag: selectedAsset || undefined,
    };

    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setStatus("loading");
    setError(null);

    try {
      const res = await queryCopilot({
        question: trimmed,
        top_k: 7,
        asset_tag: selectedAsset || undefined,
        session_id: sessionId || undefined,
        user_id: userId || undefined,
      });
      setSessionId(res.session_id ?? sessionId);
      setResult(res);
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: res.answer,
          assetTag: (res.asset_tag ?? selectedAsset) || undefined,
          result: res,
        },
      ]);
      setStatus("done");
      refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed.");
      setStatus("error");
    }
  }

  function startNewChat() {
    setSessionId(null);
    setMessages([]);
    setResult(null);
    setError(null);
    setStatus("idle");
  }

  async function openChat(chatSessionId: string) {
    if (!userId) return;
    setStatus("loading");
    setError(null);
    try {
      const history = await getCopilotChat(chatSessionId, userId);
      setSessionId(history.session.session_id);
      const loadedMessages: ChatMessage[] = history.messages.map((message) => {
        const result =
          message.role === "assistant"
            ? {
                question: "",
                answer: message.content,
                confidence:
                  message.confidence !== null && message.confidence >= 0.75
                    ? "high"
                    : message.confidence !== null && message.confidence >= 0.4
                      ? "medium"
                      : "low",
                citations: message.citations.map((citation, index) => ({
                  document_id: citation.parent_chunk_id ?? citation.chunk_id,
                  chunk_id: citation.chunk_id,
                  chunk_index: index,
                  score: message.confidence ?? 0,
                  text_preview: citation.snippet,
                  filename: citation.file_name,
                  page_number: citation.page,
                })),
                retrieved_count: message.retrieved_chunk_ids.length,
                query_intent: "rag_chat",
                related_assets: [],
                session_id: history.session.session_id,
                standalone_question: message.standalone_question ?? undefined,
              }
            : undefined;
        return {
          id: message.id,
          role: message.role,
          content: message.content,
          result,
        };
      });
      const latestAssistant = [...loadedMessages]
        .reverse()
        .find((message) => message.role === "assistant" && message.result);
      setMessages(loadedMessages);
      setResult(latestAssistant?.result ?? null);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load chat.");
      setStatus("error");
    }
  }

  const uniqueCitations =
    result?.citations.filter(
      (citation, index, self) =>
        self.findIndex((item) => item.chunk_id === citation.chunk_id) === index,
    ) ?? [];

  return (
    <div>
      <PageHeader
        title="Operations Copilot"
        subtitle="Ask follow-up questions grounded in indexed documents with citations."
        action={
          <button
            type="button"
            onClick={startNewChat}
            aria-label="New chat"
            title="New chat"
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] text-xl leading-none text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-white"
          >
            +
          </button>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <div className="mb-4 min-h-[360px] space-y-4">
              {messages.length === 0 ? (
                <div className="rounded-lg border border-dashed border-[var(--color-border)] bg-[var(--color-base)] p-5">
                  <p className="text-sm text-[var(--color-muted)]">
                    Start with an asset question, then ask follow-ups like "how can we prevent that?"
                  </p>
                </div>
              ) : (
                messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`min-w-0 max-w-[88%] rounded-lg border px-4 py-3 ${
                        message.role === "user"
                          ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-[var(--color-base)]"
                          : "border-[var(--color-border)] bg-[var(--color-base)]"
                      }`}
                    >
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <span className="text-xs font-medium uppercase tracking-wide opacity-80">
                          {message.role === "user" ? "You" : "Copilot"}
                        </span>
                        {message.assetTag && <Badge tone="neutral">{message.assetTag}</Badge>}
                        {message.result?.confidence && (
                          <Badge tone="ok">confidence: {message.result.confidence}</Badge>
                        )}
                      </div>
                      <p className="wrap-anywhere whitespace-pre-wrap text-sm leading-relaxed">
                        {message.content}
                      </p>
                      {message.result?.standalone_question &&
                        message.result.standalone_question !== message.result.question && (
                          <p className="mt-2 wrap-anywhere text-xs text-[var(--color-muted)]">
                            Search query: {message.result.standalone_question}
                          </p>
                        )}
                    </div>
                  </div>
                ))
              )}
            </div>

            {status === "error" && error && (
              <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3">
                <p className="text-sm text-red-300">{error}</p>
              </div>
            )}

            <form onSubmit={handleAsk} className="flex flex-col gap-4">
              <div className="flex flex-col gap-3 md:flex-row">
                <input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="e.g. What could be possible reasons for P-101 to fail?"
                  className="min-w-0 flex-1 rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-4 py-2.5 text-sm outline-none placeholder:text-[var(--color-muted)] focus:border-[var(--color-accent)]"
                />
                <div className="flex shrink-0 items-center gap-2">
                  <label
                    htmlFor="asset-scope"
                    className="whitespace-nowrap text-xs text-[var(--color-muted)]"
                  >
                    Scope by Asset:
                  </label>
                  <select
                    id="asset-scope"
                    value={selectedAsset}
                    onChange={(e) => setSelectedAsset(e.target.value)}
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-2 text-sm outline-none focus:border-[var(--color-accent)]"
                  >
                    <option value="">All assets</option>
                    {assets.map((asset) => (
                      <option key={asset.id} value={asset.tag}>
                        {asset.tag}
                      </option>
                    ))}
                  </select>
                </div>
                <button
                  type="submit"
                  disabled={status === "loading" || !question.trim()}
                  className="whitespace-nowrap rounded-lg bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-[var(--color-base)] hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {status === "loading" ? "Asking..." : "Ask"}
                </button>
              </div>
            </form>

            <div className="mt-3 flex flex-wrap gap-2">
              {[
                "What could be possible reasons for P-101 to fail?",
                "How can we prevent that?",
                "What evidence supports this?",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => setQuestion(suggestion)}
                  className="rounded-full border border-[var(--color-border)] bg-[var(--color-base)] px-3 py-1 text-xs text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-white"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </Card>
        </div>

        <Card>
          <div className="mb-5">
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
                Chats
              </p>
              <button
                type="button"
                onClick={startNewChat}
                aria-label="New chat"
                title="New chat"
                className="flex h-7 w-7 items-center justify-center rounded border border-[var(--color-border)] bg-[var(--color-base)] text-base leading-none text-[var(--color-muted)] hover:border-[var(--color-accent)] hover:text-white"
              >
                +
              </button>
            </div>
            {sessions.length === 0 ? (
              <p className="text-xs text-[var(--color-muted)]">No saved chats yet.</p>
            ) : (
              <div className="max-h-44 space-y-2 overflow-y-auto pr-1">
                {sessions.map((session) => (
                  <button
                    key={session.session_id}
                    type="button"
                    onClick={() => openChat(session.session_id)}
                    className={`w-full rounded-lg border p-2 text-left text-xs hover:border-[var(--color-accent)] ${
                      session.session_id === sessionId
                        ? "border-[var(--color-accent)] bg-[var(--color-base)]"
                        : "border-[var(--color-border)] bg-[var(--color-base)]"
                    }`}
                  >
                    <span className="block truncate text-sm text-white">
                      {session.title || "Untitled chat"}
                    </span>
                    <span className="mt-1 block text-[var(--color-muted)]">
                      {session.message_count} messages
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
              Latest Retrieval
            </p>
            {result?.retrieved_count !== undefined && (
              <Badge tone="neutral">{result.retrieved_count} chunks</Badge>
            )}
          </div>

          {result?.related_assets && result.related_assets.length > 0 && (
            <div className="mb-5">
              <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
                Related Assets
              </p>
              <div className="flex flex-wrap gap-2">
                {result.related_assets.map((asset) => (
                  <Link key={asset} href={`/assets/${asset}`}>
                    <Badge tone="ok">{asset}</Badge>
                  </Link>
                ))}
              </div>
            </div>
          )}

          <p className="mb-3 text-xs uppercase tracking-wide text-[var(--color-muted)]">
            Citations
          </p>

          {uniqueCitations.length === 0 ? (
            <p className="text-xs text-[var(--color-muted)]">
              No citations returned yet.
            </p>
          ) : (
            <ul className="space-y-3">
              {uniqueCitations.map((citation, index) => {
                const tags = extractTags(citation.text_preview);
                return (
                  <li
                    key={citation.chunk_id}
                    className="rounded-lg border border-[var(--color-border)] bg-[var(--color-base)] p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-[var(--color-surface-2)] text-xs text-[var(--color-accent)]">
                          {index + 1}
                        </span>
                        <Link
                          href={`/documents/${citation.document_id}`}
                          className="truncate text-sm font-medium text-[var(--color-accent)] hover:underline"
                          title={citation.filename ?? citation.document_id}
                        >
                          {citation.filename ?? citation.document_id}
                        </Link>
                      </div>
                    </div>
                    {tags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {tags.map((tag) => (
                          <span
                            key={tag}
                            className="rounded border border-emerald-500/20 bg-emerald-500/10 px-1 font-mono text-[9px] uppercase text-emerald-300"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                    <p className="mt-1.5 text-xs text-[var(--color-accent-2)]">
                      chunk {citation.chunk_index}
                      {citation.page_number !== null && citation.page_number !== undefined && (
                        <span> · page {citation.page_number}</span>
                      )}
                      <span> · score {citation.score.toFixed(2)}</span>
                    </p>
                    <p className="mt-1.5 wrap-anywhere rounded bg-[var(--color-surface-2)] p-2 text-xs leading-relaxed text-[var(--color-muted)]">
                      "{citation.text_preview}"
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
