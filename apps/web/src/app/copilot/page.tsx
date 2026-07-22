"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageHeader, Badge, Disclosure } from "@/components/ui";
import { ChatIcon, CloseIcon } from "@/components/icons";
import {
  Drawer,
  CitationChips,
  CitationItem,
  ChatComposer,
  dedupeCitations,
} from "@/components/chat";
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

/** Suggested starter questions. Uses the scoped asset when one is selected so
    the prompts stay relevant; falls back to general operations questions the
    indexed corpus can answer. These are prompts, not fabricated data. */
function suggestionsFor(asset: string): string[] {
  if (asset) {
    return [
      `What could cause ${asset} to fail?`,
      `What is the maintenance history of ${asset}?`,
      `What evidence links ${asset} to recent issues?`,
      `How can failures on ${asset} be prevented?`,
    ];
  }
  return [
    "What are the most common failure causes across assets?",
    "Summarise recent maintenance findings.",
    "Which documents describe pump failures?",
    "What preventive actions are recommended?",
  ];
}

const confidenceTone: Record<string, "ok" | "warn" | "bad"> = {
  high: "ok",
  medium: "warn",
  low: "bad",
};

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
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState("");
  const [sessionsOpen, setSessionsOpen] = useState(false);
  const [sourceView, setSourceView] = useState<{
    messageId: string;
    index: number;
  } | null>(null);

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
      const userMessage: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: queryParam,
        assetTag: initialAsset || undefined,
      };
      setMessages([userMessage]);
      setStatus("loading");
      setError(null);
      setLive("Searching indexed documents…");
      queryCopilot({
        question: queryParam,
        top_k: 7,
        asset_tag: initialAsset || undefined,
        user_id: uid || undefined,
      })
        .then((res) => {
          setSessionId(res.session_id ?? null);
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
          setLive("Copilot replied.");
          listCopilotChats(uid).then(setSessions).catch(() => {});
        })
        .catch((err) => {
          setError(err instanceof Error ? err.message : "Failed to run search.");
          setStatus("error");
          setLive("Copilot could not answer. See the error near the composer.");
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

  async function runQuery(text: string) {
    setStatus("loading");
    setError(null);
    setLive("Searching indexed documents…");
    try {
      const res = await queryCopilot({
        question: text,
        top_k: 7,
        asset_tag: selectedAsset || undefined,
        session_id: sessionId || undefined,
        user_id: userId || undefined,
      });
      setSessionId(res.session_id ?? sessionId);
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
      setLive("Copilot replied.");
      refreshSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed.");
      setStatus("error");
      setLive("Copilot could not answer. See the error near the composer.");
    }
  }

  function ask(rawQuestion?: string) {
    const trimmed = (rawQuestion ?? question).trim();
    if (!trimmed || status === "loading") return;
    setMessages((current) => [
      ...current,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
        assetTag: selectedAsset || undefined,
      },
    ]);
    setQuestion("");
    runQuery(trimmed);
  }

  function retryLast() {
    const lastUser = [...messages].reverse().find((m) => m.role === "user");
    if (!lastUser || status === "loading") return;
    runQuery(lastUser.content);
  }

  function startNewChat() {
    setSessionId(null);
    setMessages([]);
    setError(null);
    setStatus("idle");
    setSourceView(null);
    setSessionsOpen(false);
    setLive("Started a new chat.");
  }

  async function openChat(chatSessionId: string) {
    if (!userId) return;
    setSessionsOpen(false);
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
      setMessages(loadedMessages);
      setStatus("done");
      setLive("Loaded chat.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load chat.");
      setStatus("error");
    }
  }

  const hasConversation = messages.length > 0;
  const suggestions = useMemo(
    () => suggestionsFor(selectedAsset),
    [selectedAsset],
  );

  const activeSourceMessage = sourceView
    ? messages.find((m) => m.id === sourceView.messageId)
    : undefined;
  const activeSourceCitations = activeSourceMessage?.result
    ? dedupeCitations(activeSourceMessage.result.citations)
    : [];

  return (
    <div>
      {/* Restrained live region: announces state changes, not full answers. */}
      <div aria-live="polite" role="status" className="sr-only">
        {live}
      </div>

      <PageHeader
        title="Operations Copilot"
        subtitle="Grounded answers with citations from your indexed documents."
        action={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={startNewChat}
              className="min-h-9 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-sm text-[var(--color-fg)] outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            >
              New chat
            </button>
            <button
              type="button"
              onClick={() => setSessionsOpen(true)}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-sm text-[var(--color-fg)] outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            >
              <ChatIcon className="h-4 w-4" />
              Chats
            </button>
          </div>
        }
      />

      {/* Active scope indicator — always visible in the first viewport. */}
      <div className="mb-4 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-[var(--color-muted)]">Scope</span>
        {selectedAsset ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--color-accent)]/40 bg-[var(--color-surface-2)] py-0.5 pl-2.5 pr-1 font-medium text-[var(--color-fg)]">
            {selectedAsset}
            <button
              type="button"
              onClick={() => setSelectedAsset("")}
              aria-label={`Clear ${selectedAsset} scope`}
              className="flex h-5 w-5 items-center justify-center rounded-full text-[var(--color-muted)] outline-none hover:text-[var(--color-fg)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
            >
              <CloseIcon className="h-3.5 w-3.5" />
            </button>
          </span>
        ) : (
          <span className="text-[var(--color-fg)]">All assets</span>
        )}
      </div>

      <div className="mx-auto flex min-h-[calc(100dvh-14rem)] w-full max-w-3xl flex-col">
        {/* Conversation region — the primary surface. */}
        <div
          role="log"
          aria-label="Conversation with Operations Copilot"
          className="flex-1 space-y-6"
        >
          {!hasConversation && status !== "loading" ? (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
              <h2 className="text-lg font-semibold tracking-tight">
                Ask the Operations Copilot
              </h2>
              <p className="mt-1 max-w-prose text-sm text-[var(--color-muted)]">
                Get grounded answers from indexed maintenance reports, manuals
                and logs. Every answer cites the sources it used
                {selectedAsset ? (
                  <>
                    , scoped to <span className="text-[var(--color-fg)]">{selectedAsset}</span>
                  </>
                ) : null}
                .
              </p>
              <div className="mt-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
                  Try asking
                </p>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((suggestion) => (
                    <button
                      key={suggestion}
                      type="button"
                      onClick={() => ask(suggestion)}
                      className="min-h-9 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-1.5 text-xs text-[var(--color-fg)] outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            messages.map((message) => {
              if (message.role === "user") {
                return (
                  <div key={message.id} className="flex justify-end">
                    <div className="max-w-[85%] rounded-2xl rounded-br-sm border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-2.5">
                      {message.assetTag && (
                        <div className="mb-1">
                          <Badge tone="neutral">{message.assetTag}</Badge>
                        </div>
                      )}
                      <p className="wrap-anywhere whitespace-pre-wrap text-sm leading-relaxed">
                        {message.content}
                      </p>
                    </div>
                  </div>
                );
              }

              const result = message.result;
              const citations = result ? dedupeCitations(result.citations) : [];
              const hasContext =
                (result?.related_assets?.length ?? 0) > 0 ||
                (result?.retrieved_count ?? 0) > 0 ||
                (!!result?.standalone_question &&
                  result.standalone_question !== result.question);

              return (
                <div key={message.id} className="min-w-0">
                  <div className="mb-1.5 flex flex-wrap items-center gap-2">
                    <span className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                      Copilot
                    </span>
                    {result?.confidence && (
                      <Badge tone={confidenceTone[result.confidence] ?? "neutral"}>
                        {result.confidence} confidence
                      </Badge>
                    )}
                  </div>
                  <div className="wrap-anywhere whitespace-pre-wrap text-sm leading-relaxed text-[var(--color-fg)]">
                    {message.content}
                  </div>

                  {result && (
                    <div className="mt-3 space-y-2">
                      {citations.length > 0 ? (
                        <CitationChips
                          citations={citations}
                          onOpen={(index) =>
                            setSourceView({ messageId: message.id, index })
                          }
                        />
                      ) : (
                        <p className="text-xs text-[var(--color-muted)]">
                          No supporting sources were returned in the corpus for
                          this answer.
                        </p>
                      )}
                      {hasContext && (
                        <button
                          type="button"
                          onClick={() =>
                            setSourceView({ messageId: message.id, index: -1 })
                          }
                          className="text-xs font-medium text-[var(--color-accent)] outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
                        >
                          Retrieval details
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}

          {status === "loading" && (
            <div className="min-w-0">
              <div className="mb-1.5">
                <span className="text-xs font-medium uppercase tracking-wide text-[var(--color-muted)]">
                  Copilot
                </span>
              </div>
              <div className="flex items-center gap-2.5 text-sm text-[var(--color-muted)]">
                <span
                  aria-hidden="true"
                  className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-[var(--color-border)] border-t-[var(--color-accent)]"
                />
                Searching indexed documents…
              </div>
            </div>
          )}
        </div>

        {/* Composer stays with the conversation, sticky above the fold. */}
        <div className="sticky bottom-0 mt-4 border-t border-[var(--color-border)] bg-[var(--color-base)] pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
          {status === "error" && error && (
            <div
              role="alert"
              className="mb-3 rounded-lg border border-red-200 bg-red-50 p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="min-w-0 wrap-anywhere text-sm text-red-700">
                  Copilot couldn’t answer that.
                </p>
                <button
                  type="button"
                  onClick={retryLast}
                  className="min-h-9 shrink-0 rounded-lg border border-red-300 px-3 py-1 text-xs text-red-700 outline-none hover:bg-red-50 focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
                >
                  Retry
                </button>
              </div>
              <div className="mt-2">
                <Disclosure summary="Technical details">
                  <p className="wrap-anywhere text-xs text-[var(--color-muted)]">
                    {error}
                  </p>
                </Disclosure>
              </div>
            </div>
          )}

          <ChatComposer
            value={question}
            onChange={setQuestion}
            onSubmit={() => ask()}
            loading={status === "loading"}
            assets={assets}
            selectedAsset={selectedAsset}
            onAssetChange={setSelectedAsset}
          />
        </div>
      </div>

      {/* Sessions drawer — secondary, opened from the header. */}
      <Drawer
        open={sessionsOpen}
        title="Chats"
        onClose={() => setSessionsOpen(false)}
      >
        <button
          type="button"
          onClick={startNewChat}
          className="mb-4 min-h-10 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2 text-sm text-[var(--color-fg)] outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)]"
        >
          New chat
        </button>
        {sessions.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">No saved chats yet.</p>
        ) : (
          <ul className="space-y-2">
            {sessions.map((session) => {
              const isActive = session.session_id === sessionId;
              return (
                <li key={session.session_id}>
                  <button
                    type="button"
                    onClick={() => openChat(session.session_id)}
                    aria-current={isActive ? "true" : undefined}
                    className={`min-h-10 w-full rounded-lg border p-2.5 text-left outline-none transition hover:border-[var(--color-accent)] focus-visible:ring-2 focus-visible:ring-[var(--color-ring)] ${
                      isActive
                        ? "border-[var(--color-accent)] bg-[var(--color-surface-2)]"
                        : "border-[var(--color-border)] bg-[var(--color-surface-2)]"
                    }`}
                  >
                    <span className="block truncate text-sm text-[var(--color-fg)]">
                      {session.title || "Untitled chat"}
                    </span>
                    <span className="mt-0.5 block text-xs text-[var(--color-muted)]">
                      {session.message_count} messages
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </Drawer>

      {/* Source & context drawer — populated only when a chip/details is opened. */}
      <Drawer
        open={!!sourceView}
        title="Sources & context"
        onClose={() => setSourceView(null)}
      >
        {activeSourceMessage?.result && (
          <div className="space-y-4">
            <div className="space-y-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs uppercase tracking-wide text-[var(--color-muted)]">
                  Retrieval
                </span>
                <Badge tone="neutral">
                  {activeSourceMessage.result.retrieved_count} chunks
                </Badge>
                {activeSourceMessage.result.confidence && (
                  <Badge
                    tone={
                      confidenceTone[activeSourceMessage.result.confidence] ??
                      "neutral"
                    }
                  >
                    {activeSourceMessage.result.confidence} confidence
                  </Badge>
                )}
              </div>
              {activeSourceMessage.result.standalone_question &&
                activeSourceMessage.result.standalone_question !==
                  activeSourceMessage.result.question && (
                  <p className="wrap-anywhere text-xs text-[var(--color-muted)]">
                    Interpreted as: {activeSourceMessage.result.standalone_question}
                  </p>
                )}
              {(activeSourceMessage.result.related_assets?.length ?? 0) > 0 && (
                <div>
                  <p className="mb-1.5 text-xs text-[var(--color-muted)]">
                    Related assets
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {activeSourceMessage.result.related_assets?.map((asset) => (
                      <Link key={asset} href={`/assets/${asset}`}>
                        <Badge tone="ok">{asset}</Badge>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div>
              <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">
                Sources ({activeSourceCitations.length})
              </p>
              {activeSourceCitations.length === 0 ? (
                <p className="text-sm text-[var(--color-muted)]">
                  No supporting sources were returned for this answer.
                </p>
              ) : (
                <ol className="space-y-3">
                  {activeSourceCitations.map((citation, index) => (
                    <CitationItem
                      key={citation.chunk_id}
                      citation={citation}
                      index={index}
                      active={sourceView?.index === index}
                    />
                  ))}
                </ol>
              )}
            </div>
          </div>
        )}
      </Drawer>
    </div>
  );
}
