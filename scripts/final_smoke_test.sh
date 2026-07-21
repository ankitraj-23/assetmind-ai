#!/usr/bin/env bash
#
# final_smoke_test.sh — end-to-end HTTP smoke test for the AssetMind AI backend.
#
# Drives the full demo path against a *running* API and fails loudly on any
# non-2xx response, empty citation set, empty RCA cause list, empty compliance
# evidence, a missing evidence-package download, or missing benchmark metrics.
#
# No credentials are embedded. Configure via environment variables:
#   API_BASE_URL   Base URL of the running API   (default: http://127.0.0.1:8000)
#   ASSET_TAG      Asset to exercise             (default: P-101)
#
# Prerequisites: the API must be running with PERSISTENCE_BACKEND=postgres against
# a seeded database (python -m scripts.seed_demo) and the benchmark must have been
# run at least once (python -m scripts.run_benchmark). Requires: curl, jq.
#
# Usage:
#   API_BASE_URL=http://127.0.0.1:8000 ./scripts/final_smoke_test.sh
#
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8000}"
ASSET_TAG="${ASSET_TAG:-P-101}"

command -v curl >/dev/null 2>&1 || { echo "FATAL: curl is required"; exit 2; }
command -v jq   >/dev/null 2>&1 || { echo "FATAL: jq is required";   exit 2; }

STEP=0
BODY=""
CODE=""

pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; echo "----- response body -----"; echo "$BODY"; echo "-------------------------"; exit 1; }

# http METHOD PATH [JSON_BODY]
http() {
  local method="$1" path="$2" data="${3:-}" resp
  if [[ "$method" == "GET" ]]; then
    resp=$(curl -sS -w $'\n%{http_code}' "$API_BASE_URL$path") || fail "curl failed: $method $path"
  else
    resp=$(curl -sS -w $'\n%{http_code}' -X "$method" -H "Content-Type: application/json" \
      -d "$data" "$API_BASE_URL$path") || fail "curl failed: $method $path"
  fi
  CODE="${resp##*$'\n'}"
  BODY="${resp%$'\n'*}"
}

expect_2xx() {
  [[ "$CODE" =~ ^2[0-9][0-9]$ ]] || fail "$1 -> HTTP $CODE (expected 2xx)"
}

# jq_true PATH_LABEL FILTER  — assert jq filter is true against $BODY
jq_true() {
  echo "$BODY" | jq -e "$2" >/dev/null 2>&1 || fail "$1"
}

step() { STEP=$((STEP + 1)); printf '\n[%02d] %s\n' "$STEP" "$1"; }

echo "AssetMind AI smoke test"
echo "  API_BASE_URL = $API_BASE_URL"
echo "  ASSET_TAG    = $ASSET_TAG"

# 1. Health --------------------------------------------------------------------
step "GET /health"
http GET "/health"; expect_2xx "/health"
jq_true "/health status not ok" '.status == "ok"'
pass "service healthy"

# 2. Dashboard summary ---------------------------------------------------------
step "GET /dashboard/summary"
http GET "/dashboard/summary"; expect_2xx "/dashboard/summary"
jq_true "dashboard has no documents indexed" '.documents_indexed > 0'
pass "documents_indexed = $(echo "$BODY" | jq -r '.documents_indexed')"

# 3. Asset detail --------------------------------------------------------------
step "GET /assets/$ASSET_TAG"
http GET "/assets/$ASSET_TAG"; expect_2xx "/assets/$ASSET_TAG"
jq_true "asset has no tag" '.tag | length > 0'
pass "asset $(echo "$BODY" | jq -r '.tag') present"

# 4. Asset documents -----------------------------------------------------------
step "GET /assets/$ASSET_TAG/documents"
http GET "/assets/$ASSET_TAG/documents"; expect_2xx "/assets/$ASSET_TAG/documents"
jq_true "no documents linked to asset" '.count > 0'
pass "$(echo "$BODY" | jq -r '.count') linked document(s)"

# 5. Asset timeline ------------------------------------------------------------
step "GET /assets/$ASSET_TAG/timeline"
http GET "/assets/$ASSET_TAG/timeline"; expect_2xx "/assets/$ASSET_TAG/timeline"
jq_true "empty timeline" '.count > 0'
pass "$(echo "$BODY" | jq -r '.count') timeline event(s)"

# 6. Asset facts ---------------------------------------------------------------
step "GET /assets/$ASSET_TAG/facts"
http GET "/assets/$ASSET_TAG/facts"; expect_2xx "/assets/$ASSET_TAG/facts"
jq_true "no mentions in facts" '.mention_count > 0'
pass "$(echo "$BODY" | jq -r '.mention_count') mention(s)"

# 7. Asset graph ---------------------------------------------------------------
step "GET /assets/$ASSET_TAG/graph"
http GET "/assets/$ASSET_TAG/graph"; expect_2xx "/assets/$ASSET_TAG/graph"
jq_true "empty knowledge graph" '.counts.nodes > 0 and .counts.edges > 0'
pass "graph: $(echo "$BODY" | jq -r '.counts.nodes') nodes / $(echo "$BODY" | jq -r '.counts.edges') edges"

# 8. Copilot RAG chat ----------------------------------------------------------
step "POST /rag/chat — Why is $ASSET_TAG repeatedly failing?"
http POST "/rag/chat" "{\"message\":\"Why is $ASSET_TAG repeatedly failing?\",\"top_k\":5}"
expect_2xx "/rag/chat"
jq_true "empty citations from /rag/chat" '.citations | length > 0'
pass "$(echo "$BODY" | jq -r '.citations | length') citation(s)"

# 9. RCA agent -----------------------------------------------------------------
step "POST /agents/rca"
http POST "/agents/rca" "{\"asset_tag\":\"$ASSET_TAG\",\"symptom\":\"repeated high vibration and mechanical seal failures\"}"
expect_2xx "/agents/rca"
jq_true "empty likely_causes from RCA" '.likely_causes | length > 0'
pass "$(echo "$BODY" | jq -r '.likely_causes | length') likely cause(s)"

# 10. Compliance for asset -----------------------------------------------------
step "GET /agents/compliance/assets/$ASSET_TAG"
http GET "/agents/compliance/assets/$ASSET_TAG"; expect_2xx "/agents/compliance"
jq_true "no compliance gaps for asset" '.gaps | length > 0'
jq_true "compliance gap has no evidence" '[.gaps[] | select((.evidence | length) > 0)] | length > 0'
pass "$(echo "$BODY" | jq -r '.gaps | length') gap(s) with evidence"

# 11. Evidence package ---------------------------------------------------------
step "POST /agents/evidence-package"
http POST "/agents/evidence-package" "{\"asset_tag\":\"$ASSET_TAG\",\"package_type\":\"audit\"}"
expect_2xx "/agents/evidence-package"
jq_true "evidence package missing download_url" '.download_url | length > 0'
DOWNLOAD_URL="$(echo "$BODY" | jq -r '.download_url')"
pass "package $(echo "$BODY" | jq -r '.package_id')"

# 12. Download the generated package ------------------------------------------
step "GET $DOWNLOAD_URL (download package)"
http GET "$DOWNLOAD_URL"; expect_2xx "package download"
[[ -n "$BODY" ]] || fail "downloaded package is empty"
pass "downloaded $(printf '%s' "$BODY" | wc -c) bytes of Markdown"

# 13. Latest evaluation --------------------------------------------------------
step "GET /evaluation/latest"
http GET "/evaluation/latest"; expect_2xx "/evaluation/latest"
jq_true "benchmark metrics missing" '.summary.top3_source_hit_rate != null and .summary.total_questions > 0'
pass "Top-3 $(echo "$BODY" | jq -r '.summary.top3_source_hit_rate * 100')% over $(echo "$BODY" | jq -r '.summary.total_questions') Qs"

# 14. /query compatibility route ----------------------------------------------
step "POST /query (compatibility route)"
http POST "/query" "{\"question\":\"What is the maximum allowable vibration for $ASSET_TAG?\",\"top_k\":5}"
expect_2xx "/query"
jq_true "empty citations from /query" '.citations | length > 0'
pass "$(echo "$BODY" | jq -r '.citations | length') citation(s)"

printf '\n\033[32mAll %d smoke-test checks passed.\033[0m\n' "$STEP"
