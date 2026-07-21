/**
 * Typed API helpers for the AssetMind AI backend (apps/api, FastAPI on :8000).
 *
 * The types below mirror the backend Pydantic models so the frontend/backend
 * contract is explicit. Base URL is environment-driven and falls back to the
 * local FastAPI dev server.
 */

const API_BASE_URL =
process.env.NEXT_PUBLIC_API_BASE_URL ??
(process.env.NODE_ENV === "production"
? "https://assetmind-ai-api.onrender.com"
: "http://127.0.0.1:8000");

/** Mirrors app.models.document.Document */
export interface ApiDocument {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  text_char_count: number;
  status: string;
  storage_path: string;
  created_at: string;
  chunk_count: number;
}

/** Mirrors app.models.chunk.Chunk */
export interface ApiChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  char_start: number;
  char_end: number;
}

/** Mirrors app.models.chunk.DocumentChunks */
export interface ApiDocumentChunks {
  document_id: string;
  chunks: ApiChunk[];
}

/** Mirrors app.models.embedding.EmbeddingPreview */
export interface ApiEmbeddingPreview {
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  dimension: number;
  preview: number[];
}

/** Mirrors app.models.embedding.DocumentEmbeddings */
export interface ApiDocumentEmbeddings {
  document_id: string;
  embedding_model: string;
  dimension: number;
  embeddings: ApiEmbeddingPreview[];
}

/** Mirrors app.models.query.QueryCitation */
export interface ApiCitation {
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
  text_preview: string;
  /** Human-readable source filename; falls back to document_id when absent. */
  filename?: string | null;
  page_number?: number | null; // Added in Week 2
}

/** Mirrors app.models.query.QueryResponse */
export interface ApiQueryResponse {
  question: string;
  answer: string;
  confidence: string;
  citations: ApiCitation[];
  retrieved_count: number;
  query_intent?: string; // Added in Week 2
  related_assets?: string[]; // Added in Week 2
  session_id?: string;
  standalone_question?: string;
  asset_tag?: string | null;
}

/** Throw a readable error, surfacing the backend's `detail` message when present. */
async function ensureOk(res: Response, label: string): Promise<Response> {
  if (res.ok) return res;
  let detail = "";
  try {
    const body = await res.json();
    detail = typeof body?.detail === "string" ? `: ${body.detail}` : "";
  } catch {
    /* response had no JSON body */
  }
  throw new Error(`${label} failed (${res.status})${detail}`);
}

/** POST /documents — upload a file for ingestion; returns its stored metadata. */
export async function uploadDocument(file: File): Promise<ApiDocument> {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    body,
  });
  await ensureOk(res, "Upload");
  return res.json() as Promise<ApiDocument>;
}

/** GET /documents — list ingested documents. */
export async function listDocuments(): Promise<ApiDocument[]> {
  const res = await fetch(`${API_BASE_URL}/documents`);
  await ensureOk(res, "List documents");
  return res.json() as Promise<ApiDocument[]>;
}

/** GET /documents/{id}/chunks — ordered text chunks for one document. */
export async function getDocumentChunks(
  documentId: string,
): Promise<ApiDocumentChunks> {
  const res = await fetch(
    `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/chunks`,
  );
  await ensureOk(res, "Load chunks");
  return res.json() as Promise<ApiDocumentChunks>;
}

/** GET /documents/{id}/embeddings — embedding metadata with vector previews. */
export async function getDocumentEmbeddings(
  documentId: string,
): Promise<ApiDocumentEmbeddings> {
  const res = await fetch(
    `${API_BASE_URL}/documents/${encodeURIComponent(documentId)}/embeddings`,
  );
  await ensureOk(res, "Load embeddings");
  return res.json() as Promise<ApiDocumentEmbeddings>;
}

/** POST /query — ask a question and get a citation-backed answer. */
export async function askQuestion(
  question: string,
  top_k = 5,
): Promise<ApiQueryResponse> {
  const res = await fetch(`${API_BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k }),
  });
  await ensureOk(res, "Query");
  return res.json() as Promise<ApiQueryResponse>;
}

// ---------------------------------------------------------------------------
// Assets
// ---------------------------------------------------------------------------

/** Mirrors the backend asset dict returned by GET /assets and GET /assets/{tag}. */
export interface ApiAsset {
  id: string;
  tag: string;
  asset_type: string;
  display_name: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/** Citation object nested inside each asset mention. */
export interface ApiAssetMentionCitation {
  document_id: string;
  chunk_id: string;
  chunk_index: number | null;
  filename: string | null;
}

/** A single evidence mention returned by GET /assets/{tag}/mentions. */
export interface ApiAssetMention {
  id: string;
  asset_id: string;
  tag: string;
  asset_type: string;
  entity_id: string | null;
  raw_value: string | null;
  normalized_value: string | null;
  document_id: string;
  filename: string | null;
  chunk_id: string;
  chunk_index: number | null;
  text: string | null;
  page_number: number | null;
  confidence: number | null;
  citation: ApiAssetMentionCitation;
  created_at: string;
}

/** Response shape of GET /assets/{tag}/mentions. */
export interface ApiAssetMentionsResponse {
  tag: string;
  count: number;
  mentions: ApiAssetMention[];
}

/** GET /assets — list all extracted equipment assets. */
export async function listAssets(): Promise<ApiAsset[]> {
  const res = await fetch(`${API_BASE_URL}/assets`);
  await ensureOk(res, "List assets");
  return res.json() as Promise<ApiAsset[]>;
}

/** GET /assets/{tag} — get a single asset by its tag (e.g. "P-101"). */
export async function getAsset(tag: string): Promise<ApiAsset> {
  const res = await fetch(
    `${API_BASE_URL}/assets/${encodeURIComponent(tag)}`,
  );
  await ensureOk(res, "Load asset");
  return res.json() as Promise<ApiAsset>;
}

/** GET /assets/{tag}/mentions — evidence-rich mentions with citation data. */
export async function getAssetMentions(
  tag: string,
): Promise<ApiAssetMentionsResponse> {
  const res = await fetch(
    `${API_BASE_URL}/assets/${encodeURIComponent(tag)}/mentions`,
  );
  await ensureOk(res, "Load asset mentions");
  return res.json() as Promise<ApiAssetMentionsResponse>;
}

// ---------------------------------------------------------------------------
// Week 2 Additions (Dashboard, Details, Graphs, Risk & Scoped Query)
// ---------------------------------------------------------------------------

/** Detailed facts returned by GET /assets/{tag}/facts. */
export interface ApiAssetFacts {
  asset: ApiAsset;
  mention_count: number;
  document_count: number;
  documents: ApiDocument[];
  entities: {
    id: string;
    entity_type: string;
    raw_value: string;
    normalized_value: string;
    confidence: number | null;
    document_id: string | null;
    chunk_id: string | null;
    page_number: number | null;
    char_start: number | null;
    char_end: number | null;
    extraction_method: string | null;
    metadata: Record<string, unknown>;
    created_at: string;
  }[];
}

/** Derived timeline event for an asset. */
export interface ApiAssetTimelineEvent {
  id: string;
  asset_tag: string;
  event_type: 'inspection' | 'work_order' | 'procedure' | 'compliance' | 'failure' | 'evidence_mention';
  severity: 'high' | 'medium' | 'low';
  reason_tags: string[];
  title: string;
  date: string | null;
  document_id: string | null;
  filename: string | null;
  chunk_id: string | null;
  chunk_index: number | null;
  text_preview: string | null;
  citation: ApiCitation;
}

/** Derived asset graph node. */
export interface ApiAssetGraphNode {
  id: string;
  type: 'asset' | 'document' | 'chunk' | 'entity';
  label: string;
  asset_id?: string;
  asset_type?: string;
  document_id?: string;
  chunk_id?: string;
  chunk_index?: number;
  entity_id?: string;
  entity_type?: string;
}

/** Derived asset graph edge. */
export interface ApiAssetGraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: 'mentioned_in' | 'supported_by_chunk' | 'has_entity';
}

/** Derived asset graph response. */
export interface ApiAssetGraphResponse {
  asset: ApiAsset;
  nodes: ApiAssetGraphNode[];
  edges: ApiAssetGraphEdge[];
  counts: {
    nodes: number;
    edges: number;
  };
}

/** Asset risk info. */
export interface ApiAssetRiskInfo {
  asset: ApiAsset;
  asset_tag: string;
  risk_score: number;
  risk_level: 'high' | 'medium' | 'low';
  risk_reasons: string[];
  evidence: {
    document_id: string;
    filename: string | null;
    chunk_id: string;
    chunk_index: number | null;
    text_preview: string | null;
  }[];
  mention_count: number;
  document_count: number;
  last_seen: string | null;
}

/** Asset risk summary response. */
export interface ApiAssetRiskSummaryResponse {
  count: number;
  assets: ApiAssetRiskInfo[];
}

/** Dashboard summary v2 response. */
export interface ApiDashboardSummary {
  documents_indexed: number;
  chunks_created: number;
  assets_discovered: number;
  entities_extracted: number;
  asset_mentions: number;
  knowledge_edges: number;
  recent_documents: ApiDocument[];
  high_risk_assets: number;
  medium_risk_assets: number;
  low_risk_assets: number;
  open_compliance_gaps: number;
  repeated_failure_patterns: number;
  top_assets_by_mentions: {
    asset_tag: string;
    asset_type: string;
    mention_count: number;
  }[];
  risk_summary: ApiAssetRiskInfo[];
  mode?: string;
  message?: string;
}

/** GET /dashboard/summary — live summary counts for the dashboard. */
export async function getDashboardSummary(): Promise<ApiDashboardSummary> {
  const res = await fetch(`${API_BASE_URL}/dashboard/summary`);
  await ensureOk(res, "Load dashboard summary");
  return res.json() as Promise<ApiDashboardSummary>;
}

/** GET /assets/{tag}/documents — get unique documents mentioning this asset. */
export async function getAssetDocuments(
  tag: string,
): Promise<{ tag: string; count: number; documents: ApiDocument[] }> {
  const res = await fetch(
    `${API_BASE_URL}/assets/${encodeURIComponent(tag)}/documents`,
  );
  await ensureOk(res, "Load asset documents");
  return res.json() as Promise<{
    tag: string;
    count: number;
    documents: ApiDocument[];
  }>;
}

/** GET /assets/{tag}/timeline — get derived timeline events for this asset. */
export async function getAssetTimeline(
  tag: string,
): Promise<{ tag: string; count: number; events: ApiAssetTimelineEvent[] }> {
  const res = await fetch(
    `${API_BASE_URL}/assets/${encodeURIComponent(tag)}/timeline`,
  );
  await ensureOk(res, "Load asset timeline");
  return res.json() as Promise<{
    tag: string;
    count: number;
    events: ApiAssetTimelineEvent[];
  }>;
}

/** GET /assets/{tag}/graph — get derived knowledge graph for this asset. */
export async function getAssetGraph(
  tag: string,
  includeChunks = true,
  relationType?: string,
): Promise<ApiAssetGraphResponse> {
  let url = `${API_BASE_URL}/assets/${encodeURIComponent(tag)}/graph?include_chunks=${includeChunks}`;
  if (relationType) {
    url += `&relation_type=${encodeURIComponent(relationType)}`;
  }
  const res = await fetch(url);
  await ensureOk(res, "Load asset graph");
  return res.json() as Promise<ApiAssetGraphResponse>;
}

/** GET /assets/{tag}/facts — get compact fact sheet for this asset. */
export async function getAssetFacts(tag: string): Promise<ApiAssetFacts> {
  const res = await fetch(
    `${API_BASE_URL}/assets/${encodeURIComponent(tag)}/facts`,
  );
  await ensureOk(res, "Load asset facts");
  return res.json() as Promise<ApiAssetFacts>;
}

/** GET /assets/risk-summary — get top risky assets. */
export async function getAssetRiskSummary(
  limit = 10,
): Promise<ApiAssetRiskSummaryResponse> {
  const res = await fetch(
    `${API_BASE_URL}/assets/risk-summary?limit=${limit}`,
  );
  await ensureOk(res, "Load asset risk summary");
  return res.json() as Promise<ApiAssetRiskSummaryResponse>;
}

/** POST /query — ask a question with asset scoping option. */
export interface QueryCopilotParams {
  question: string;
  top_k?: number;
  asset_tag?: string;
  session_id?: string;
  user_id?: string;
}

interface ApiRagCitation {
  file_name: string;
  page: number | null;
  row: number | null;
  section_title: string | null;
  parent_chunk_id: string | null;
  retrieval_unit_id: string | null;
  chunk_id: string;
  source_path: string | null;
  snippet: string;
}

interface ApiRetrievedChunk {
  chunk_id: string;
  document_id: string;
  parent_chunk_id?: string | null;
  score: number;
  file_name: string;
  page_number?: number | null;
  page_start?: number | null;
  chunk_index: number;
  raw_text?: string | null;
  content: string;
  asset_tags?: string[];
}

interface ApiRagChatResponse {
  session_id: string;
  user_message_id: string;
  assistant_message_id: string;
  standalone_question: string;
  asset_tag?: string | null;
  answer: string;
  citations: ApiRagCitation[];
  confidence: number;
  missing_info: string[];
  retrieved_chunks: ApiRetrievedChunk[];
}

export interface ApiChatSessionSummary {
  session_id: string;
  title: string | null;
  user_id: string | null;
  message_count: number;
  updated_at: string | null;
  created_at: string | null;
}

interface ApiRagChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  standalone_question: string | null;
  citations: ApiRagCitation[];
  retrieved_chunk_ids: string[];
  confidence: number | null;
  created_at: string | null;
}

export interface ApiChatHistoryResponse {
  session: ApiChatSessionSummary;
  messages: ApiRagChatMessage[];
}

export async function queryCopilot(
  params: QueryCopilotParams,
): Promise<ApiQueryResponse> {
  const res = await fetch(`${API_BASE_URL}/rag/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: params.question,
      top_k: params.top_k ?? 5,
      asset_tag: params.asset_tag || undefined,
      session_id: params.session_id || undefined,
      user_id: params.user_id || undefined,
    }),
  });
  await ensureOk(res, "Query Copilot");
  const body = (await res.json()) as ApiRagChatResponse;
  const chunksById = new Map(body.retrieved_chunks.map((chunk) => [chunk.chunk_id, chunk]));
  const scopedAsset = (body.asset_tag ?? "").toUpperCase();
  const relatedAssets = Array.from(
    new Set(
      body.retrieved_chunks
        .flatMap((chunk) => chunk.asset_tags ?? [])
        .map((tag) => tag.toUpperCase())
        .filter((tag) => tag && tag !== scopedAsset),
    ),
  );

  return {
    question: params.question,
    answer: body.answer,
    confidence: body.confidence >= 0.75 ? "high" : body.confidence >= 0.4 ? "medium" : "low",
    citations: body.citations.map((citation, index) => {
      const chunk = chunksById.get(citation.chunk_id);
      return {
        document_id: chunk?.document_id ?? citation.parent_chunk_id ?? citation.chunk_id,
        chunk_id: citation.chunk_id,
        chunk_index: chunk?.chunk_index ?? index,
        score: chunk?.score ?? body.confidence,
        text_preview: citation.snippet || chunk?.raw_text || chunk?.content || "",
        filename: citation.file_name,
        page_number: citation.page ?? chunk?.page_start ?? chunk?.page_number ?? null,
      };
    }),
    retrieved_count: body.retrieved_chunks.length,
    query_intent: "rag_chat",
    related_assets: relatedAssets,
    session_id: body.session_id,
    standalone_question: body.standalone_question,
    asset_tag: body.asset_tag ?? null,
  };
}

export async function listCopilotChats(
  userId: string,
): Promise<ApiChatSessionSummary[]> {
  const res = await fetch(
    `${API_BASE_URL}/rag/chat/sessions?user_id=${encodeURIComponent(userId)}`,
  );
  await ensureOk(res, "Load chat sessions");
  const body = (await res.json()) as { sessions: ApiChatSessionSummary[] };
  return body.sessions;
}

export async function getCopilotChat(
  sessionId: string,
  userId: string,
): Promise<ApiChatHistoryResponse> {
  const res = await fetch(
    `${API_BASE_URL}/rag/chat/sessions/${encodeURIComponent(sessionId)}?user_id=${encodeURIComponent(userId)}`,
  );
  await ensureOk(res, "Load chat history");
  return res.json() as Promise<ApiChatHistoryResponse>;
}

// ---------------------------------------------------------------------------
// RCA (Root Cause Analysis) Agent
// ---------------------------------------------------------------------------

/** A single piece of grounding evidence attached to a likely cause. */
export interface ApiRcaEvidence {
  source: string;
  text: string;
  document_id?: string | null;
  chunk_id?: string | null;
}

/** One candidate root cause with confidence and supporting evidence. */
export interface ApiLikelyCause {
  cause: string;
  confidence: number;
  evidence: ApiRcaEvidence[];
}

/** Response shape of POST /agents/rca. */
export interface ApiRcaResponse {
  asset_tag: string;
  symptom: string;
  summary: string;
  likely_causes: ApiLikelyCause[];
  recommended_actions: string[];
  missing_information: string[];
}

/** POST /agents/rca — run the root cause analysis agent for an asset symptom. */
export async function performRca(
  assetTag: string,
  symptom: string,
): Promise<ApiRcaResponse> {
  const res = await fetch(`${API_BASE_URL}/agents/rca`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      asset_tag: assetTag,
      symptom,
    }),
  });
  await ensureOk(res, "Perform RCA");
  return res.json() as Promise<ApiRcaResponse>;
}

// ---------------------------------------------------------------------------
// Compliance & Evidence Package agents
// ---------------------------------------------------------------------------

/** One evidence snippet backing a compliance gap. Mirrors ComplianceEvidence. */
export interface ApiComplianceEvidence {
  source: string;
  text: string;
  document_id?: string | null;
  chunk_id?: string | null;
}

/** A single explainable compliance gap. Mirrors ComplianceGap. */
export interface ApiComplianceGap {
  asset_tag: string;
  gap_type: string;
  severity: "high" | "medium" | "low";
  reason: string;
  standard_or_policy?: string | null;
  evidence: ApiComplianceEvidence[];
  recommended_action: string;
}

/** Response of GET /agents/compliance/gaps. Mirrors ComplianceGapsResponse. */
export interface ApiComplianceGapsResponse {
  count: number;
  filters: Record<string, string>;
  gaps: ApiComplianceGap[];
  mode: string;
  message?: string | null;
}

/** GET /agents/compliance/gaps — list gaps with optional filters. */
export async function getComplianceGaps(params?: {
  asset_tag?: string;
  severity?: string;
  gap_type?: string;
}): Promise<ApiComplianceGapsResponse> {
  const qs = new URLSearchParams();
  if (params?.asset_tag) qs.set("asset_tag", params.asset_tag);
  if (params?.severity) qs.set("severity", params.severity);
  if (params?.gap_type) qs.set("gap_type", params.gap_type);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(`${API_BASE_URL}/agents/compliance/gaps${suffix}`);
  await ensureOk(res, "Load compliance gaps");
  return res.json() as Promise<ApiComplianceGapsResponse>;
}

/** GET /agents/compliance/assets/{tag} — gaps scoped to one asset. */
export async function getComplianceGapsForAsset(
  assetTag: string,
): Promise<ApiComplianceGapsResponse> {
  const res = await fetch(
    `${API_BASE_URL}/agents/compliance/assets/${encodeURIComponent(assetTag)}`,
  );
  await ensureOk(res, "Load asset compliance gaps");
  return res.json() as Promise<ApiComplianceGapsResponse>;
}

/** A source document included in an evidence package. */
export interface ApiEvidenceDocumentRef {
  document_id?: string | null;
  filename?: string | null;
  chunk_count?: number | null;
}

/** An inspection/maintenance evidence line in a package. */
export interface ApiEvidenceFinding {
  text: string;
  source?: string | null;
  document_id?: string | null;
  chunk_id?: string | null;
  category?: string | null;
}

/** Response of POST /agents/evidence-package. Mirrors EvidencePackageResponse. */
export interface ApiEvidencePackageResponse {
  package_id: string;
  asset_tag: string;
  package_type: string;
  generated_at: string;
  summary: string;
  included_documents: ApiEvidenceDocumentRef[];
  compliance_gaps: ApiComplianceGap[];
  inspection_findings: ApiEvidenceFinding[];
  maintenance_evidence: ApiEvidenceFinding[];
  missing_evidence: string[];
  recommended_actions: string[];
  download_url: string;
}

/** POST /agents/evidence-package — generate a citation-backed package. */
export async function generateEvidencePackage(
  assetTag: string,
  packageType = "audit",
): Promise<ApiEvidencePackageResponse> {
  const res = await fetch(`${API_BASE_URL}/agents/evidence-package`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset_tag: assetTag, package_type: packageType }),
  });
  await ensureOk(res, "Generate evidence package");
  return res.json() as Promise<ApiEvidencePackageResponse>;
}

/** Absolute URL for a package download path returned by the API. */
export function evidencePackageDownloadUrl(downloadPath: string): string {
  return `${API_BASE_URL}${downloadPath}`;
}

