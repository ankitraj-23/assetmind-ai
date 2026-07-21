/**
 * Mock data for the AssetMind AI demo shell.
 * Replace with live API responses (see lib/api.ts) once wiring begins.
 */

export type Risk = "low" | "medium" | "high" | "critical";

export const dashboardStats = [
  { label: "Documents Indexed", value: 1284, delta: "+37 this week", hint: "manuals, SOPs, reports" },
  { label: "Assets Discovered", value: 312, delta: "+8 this week", hint: "pumps, valves, motors" },
  { label: "Chunks Generated", value: "48.6k", delta: "+2.1k this week", hint: "semantic segments" },
  { label: "Compliance Gaps", value: 17, delta: "-4 this week", hint: "open findings" },
];

export const recentUploads = [
  { id: "doc-1041", name: "Pump P-101 O&M Manual.pdf", type: "Manual", status: "Indexed", chunks: 214, when: "2h ago" },
  { id: "doc-1040", name: "Annual Safety Audit 2026.pdf", type: "Report", status: "Indexed", chunks: 96, when: "5h ago" },
  { id: "doc-1039", name: "SOP-Lockout-Tagout.txt", type: "SOP", status: "Indexed", chunks: 12, when: "Yesterday" },
  { id: "doc-1038", name: "Compressor C-220 Datasheet.pdf", type: "Datasheet", status: "Processing", chunks: 0, when: "Yesterday" },
  { id: "doc-1037", name: "Vibration Survey Q2.pdf", type: "Report", status: "Indexed", chunks: 58, when: "2d ago" },
];

export const highRiskAssets = [
  { id: "P-101", name: "Pump P-101", area: "Crude Unit", risk: "critical" as Risk, issue: "Recurring seal failure" },
  { id: "C-220", name: "Compressor C-220", area: "Gas Plant", risk: "high" as Risk, issue: "Bearing temp trending up" },
  { id: "V-310", name: "Control Valve V-310", area: "Distillation", risk: "high" as Risk, issue: "Overdue calibration" },
  { id: "M-118", name: "Motor M-118", area: "Utilities", risk: "medium" as Risk, issue: "Insulation degradation" },
];

export const recentQueries = [
  { q: "What is the recommended seal flush plan for P-101?", when: "12m ago", citations: 4 },
  { q: "Which assets have overdue calibration this quarter?", when: "48m ago", citations: 6 },
  { q: "Summarize root cause of the C-220 trip event.", when: "3h ago", citations: 3 },
  { q: "List lockout/tagout steps before pump maintenance.", when: "Yesterday", citations: 2 },
];

export const documents = [
  { id: "doc-1041", name: "Pump P-101 O&M Manual.pdf", type: "Manual", asset: "P-101", chunks: 214, embeddings: 214, indexedOn: "2026-06-24" },
  { id: "doc-1040", name: "Annual Safety Audit 2026.pdf", type: "Report", asset: "—", chunks: 96, embeddings: 96, indexedOn: "2026-06-24" },
  { id: "doc-1039", name: "SOP-Lockout-Tagout.txt", type: "SOP", asset: "—", chunks: 12, embeddings: 12, indexedOn: "2026-06-23" },
  { id: "doc-1038", name: "Compressor C-220 Datasheet.pdf", type: "Datasheet", asset: "C-220", chunks: 0, embeddings: 0, indexedOn: "—" },
  { id: "doc-1037", name: "Vibration Survey Q2.pdf", type: "Report", asset: "Multiple", chunks: 58, embeddings: 58, indexedOn: "2026-06-22" },
  { id: "doc-1036", name: "Valve V-310 Calibration Record.pdf", type: "Record", asset: "V-310", chunks: 9, embeddings: 9, indexedOn: "2026-06-20" },
];

export const assets = [
  { id: "P-101", name: "Pump P-101", type: "Centrifugal Pump", area: "Crude Unit", risk: "critical" as Risk, docs: 7, lastEvent: "Seal failure" },
  { id: "C-220", name: "Compressor C-220", type: "Recip Compressor", area: "Gas Plant", risk: "high" as Risk, docs: 5, lastEvent: "High bearing temp" },
  { id: "V-310", name: "Control Valve V-310", type: "Globe Valve", area: "Distillation", risk: "high" as Risk, docs: 3, lastEvent: "Calibration drift" },
  { id: "M-118", name: "Motor M-118", type: "Induction Motor", area: "Utilities", risk: "medium" as Risk, docs: 4, lastEvent: "Insulation test" },
  { id: "HX-205", name: "Heat Exchanger HX-205", type: "Shell & Tube", area: "Crude Unit", risk: "low" as Risk, docs: 6, lastEvent: "Routine inspection" },
  { id: "T-401", name: "Storage Tank T-401", type: "Atmospheric Tank", area: "Tank Farm", risk: "low" as Risk, docs: 2, lastEvent: "Level audit" },
];

export const assetDetail = {
  id: "P-101",
  name: "Pump P-101",
  type: "Centrifugal Pump",
  area: "Crude Unit — Train A",
  manufacturer: "FlowServe",
  installed: "2014",
  risk: "critical" as Risk,
  summary:
    "Primary crude charge pump. History of mechanical seal failures linked to flush line fouling. Currently flagged critical pending seal plan revision and vibration re-baseline.",
  relatedDocuments: [
    { id: "doc-1041", name: "Pump P-101 O&M Manual.pdf", type: "Manual" },
    { id: "doc-1037", name: "Vibration Survey Q2.pdf", type: "Report" },
    { id: "doc-1039", name: "SOP-Lockout-Tagout.txt", type: "SOP" },
  ],
  failureHistory: [
    { date: "2026-05-18", event: "Mechanical seal failure", downtime: "14h", cause: "Flush line fouling" },
    { date: "2025-11-02", event: "High vibration trip", downtime: "6h", cause: "Coupling misalignment" },
    { date: "2025-03-27", event: "Seal weep", downtime: "2h", cause: "Worn seal faces" },
  ],
  sops: [
    { id: "sop-01", title: "Lockout/Tagout before maintenance", ref: "SOP-LOTO-04" },
    { id: "sop-02", title: "Mechanical seal replacement procedure", ref: "SOP-SEAL-12" },
    { id: "sop-03", title: "Vibration baseline measurement", ref: "SOP-VIB-07" },
  ],
  risks: [
    { label: "Recurring seal failure", level: "critical" as Risk, note: "3 events in 14 months" },
    { label: "Flush line fouling", level: "high" as Risk, note: "Root cause not yet eliminated" },
    { label: "Vibration baseline stale", level: "medium" as Risk, note: "Re-baseline overdue" },
  ],
};

export const copilotAnswer = {
  question: "What is the recommended seal flush plan for Pump P-101?",
  answer:
    "For Pump P-101, the O&M manual specifies an API Plan 11 seal flush taken from the pump discharge through an orifice, supplemented by a Plan 62 external quench given the recurring fouling history. Vibration surveys recommend re-baselining after any seal replacement before returning to service.",
  citations: [
    { id: 1, doc: "Pump P-101 O&M Manual.pdf", section: "§5.3 Seal Flush Arrangements", snippet: "Standard configuration is API Plan 11; for fouling-prone services add Plan 62 quench." },
    { id: 2, doc: "Vibration Survey Q2.pdf", section: "Recommendations", snippet: "Re-baseline vibration after seal work prior to normal operation." },
    { id: 3, doc: "SOP-SEAL-12", section: "Step 7", snippet: "Verify flush line cleanliness and orifice sizing before reassembly." },
  ],
};

export const rcaCase = {
  id: "RCA-2026-014",
  title: "Pump P-101 recurring mechanical seal failure",
  status: "In Review",
  asset: "P-101",
  problem:
    "Pump P-101 has experienced three mechanical seal failures in 14 months, the most recent causing 14 hours of unplanned downtime on the crude charge train.",
  timeline: [
    { date: "2025-03-27", event: "Seal weep observed, faces replaced" },
    { date: "2025-11-02", event: "High vibration trip, coupling realigned" },
    { date: "2026-05-18", event: "Full seal failure, 14h downtime" },
  ],
  fiveWhys: [
    "Why did the pump trip? — Mechanical seal failed and leaked.",
    "Why did the seal fail? — Seal faces overheated and lost lubrication.",
    "Why did faces overheat? — Flush flow was insufficient.",
    "Why was flush flow insufficient? — Flush line orifice was fouled.",
    "Why was the orifice fouled? — No strainer / quench on a fouling-prone service.",
  ],
  rootCause:
    "Inadequate seal flush design for a fouling-prone service: API Plan 11 alone cannot maintain flush flow once the orifice fouls.",
  recommendations: [
    { action: "Add API Plan 62 external quench", owner: "Reliability Eng.", priority: "high" as Risk },
    { action: "Install flush line strainer with DP monitoring", owner: "Maintenance", priority: "high" as Risk },
    { action: "Re-baseline vibration after next seal change", owner: "Condition Monitoring", priority: "medium" as Risk },
  ],
};

// NOTE: Compliance findings are no longer mocked. The Compliance page renders
// live, evidence-backed gaps from the /agents/compliance API (see
// apps/web/src/app/compliance/page.tsx).
