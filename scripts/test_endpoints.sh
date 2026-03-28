#!/usr/bin/env bash
# ============================================================================
# test_endpoints.sh - Smoke tests for every API endpoint
#
# Run this after starting the backend with:
#   uvicorn app.main:app --reload --port 8000
#
# The "Why did my build fail?" query pointing at broken-pipeline is the
# showstopper demo. That's the one you show mentors first.
# ============================================================================

set -euo pipefail

API="http://localhost:8000"
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "========================================"
echo "  Jenkins Workflow Chatbot - API Tests"
echo "========================================"
echo ""

# --------------------------------------------------------------------------
# 1. Health check
# --------------------------------------------------------------------------
echo -e "${YELLOW}[1/7] Health check${NC}"
curl -s "${API}/api/health" | python3 -m json.tool
echo ""

# --------------------------------------------------------------------------
# 2. Jenkins server info (proves context-awareness)
# --------------------------------------------------------------------------
echo -e "${YELLOW}[2/7] Jenkins server info${NC}"
curl -s "${API}/api/jenkins/info" | python3 -m json.tool
echo ""

# --------------------------------------------------------------------------
# 3. Failed builds summary
# --------------------------------------------------------------------------
echo -e "${YELLOW}[3/7] Failed builds summary${NC}"
curl -s "${API}/api/jenkins/failed" | python3 -m json.tool
echo ""

# --------------------------------------------------------------------------
# 4. TROUBLESHOOT - "Why did my build fail?" (THE KILLER DEMO)
#    This reads the actual build log from broken-pipeline and diagnoses it
# --------------------------------------------------------------------------
echo -e "${YELLOW}[4/7] TROUBLESHOOT: Why did my build fail?${NC}"
echo "  (This is the showstopper - reads real build logs)"
echo ""
curl -s -X POST "${API}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"query": "Why did my build fail?", "job_name": "broken-pipeline"}' \
    | python3 -m json.tool
echo ""

# --------------------------------------------------------------------------
# 5. WORKFLOW - "How do I set up a multibranch pipeline?"
#    This checks installed plugins before giving advice
# --------------------------------------------------------------------------
echo -e "${YELLOW}[5/7] WORKFLOW: How to set up multibranch pipeline${NC}"
curl -s -X POST "${API}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"query": "How do I set up a multibranch pipeline with GitHub webhooks?"}' \
    | python3 -m json.tool
echo ""

# --------------------------------------------------------------------------
# 6. RECOMMEND - "What plugin for Slack notifications?"
#    This cross-references your installed plugins for compatibility
# --------------------------------------------------------------------------
echo -e "${YELLOW}[6/7] RECOMMEND: Slack notification plugin${NC}"
curl -s -X POST "${API}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"query": "What plugin should I use for sending Slack notifications on build failures?"}' \
    | python3 -m json.tool
echo ""

# --------------------------------------------------------------------------
# 7. GENERAL - Simple knowledge question
# --------------------------------------------------------------------------
echo -e "${YELLOW}[7/7] GENERAL: What version am I running?${NC}"
curl -s -X POST "${API}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"query": "What version of Jenkins am I running?"}' \
    | python3 -m json.tool
echo ""

echo "========================================"
echo -e "${GREEN}  All tests complete!${NC}"
echo "========================================"
echo ""
echo "If Jenkins is connected, the troubleshoot response should reference"
echo "actual error lines from the broken-pipeline build log."
echo ""
echo "If Jenkins is offline, you'll see mock data responses which still"
echo "demonstrate the multi-agent routing and response structure."
