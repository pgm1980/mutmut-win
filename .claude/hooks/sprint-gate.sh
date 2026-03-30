#!/bin/bash

# Sprint Gate — PostToolUse Hook
# Filter: "if": "Bash(*git commit*)" — fires ONLY on git commit calls.
#
# Hook config uses TWO levels:
#   "matcher": "Bash"           — matches tool NAME (required for PostToolUse)
#   "if": "Bash(*git commit*)"  — matches command CONTENT (permission rule syntax)
#
# OUTPUT: Normal stdout → Claude AI context (system-reminder)
#         JSON systemMessage → visible to user in chat
#
# IMPORTANT: The leading * in Bash(*git commit*) is required because
# commands typically start with "cd /path && git commit..." not "git commit...".

set -uo pipefail

STATE_FILE=".sprint/state.md"

# No sprint state → nothing to gate
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Parse housekeeping_done
DONE=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

# If housekeeping is already done (or state.md has no frontmatter → DONE is empty), no gate needed.
if [[ "$DONE" == "true" ]] || [[ -z "$DONE" ]]; then
  exit 0
fi

# Housekeeping is incomplete — run live checks
BLOCKERS=""

# Parse sprint info
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
SPRINT=$(echo "$FRONTMATTER" | grep '^current_sprint:' | sed 's/current_sprint: *//' | tr -d '"')
STARTED=$(echo "$FRONTMATTER" | grep '^started_at:' | sed 's/started_at: *//' | tr -d '"')

# Live check 1: MEMORY.md updated since sprint start?
if [[ -n "$STARTED" ]]; then
  MEM_COMMITS=$(git log --since="$STARTED" --oneline -- MEMORY.md 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")
  if [[ "$MEM_COMMITS" -eq 0 ]]; then
    BLOCKERS="$BLOCKERS\n  - [ ] MEMORY.md has NOT been updated since sprint $SPRINT started"
  fi
fi

# Live check 2: Open GitHub Issues?
if command -v gh &>/dev/null; then
  OPEN_COUNT=$(gh issue list --state open --limit 50 2>/dev/null | wc -l | tr -d '[:space:]' || echo "0")
  if [[ "$OPEN_COUNT" -gt 0 ]]; then
    BLOCKERS="$BLOCKERS\n  - [ ] $OPEN_COUNT open GitHub Issues — close completed ones before next sprint"
  fi
fi

# Live check 3: Sprint backlog exists?
BACKLOG_DIR="_docs/sprint backlogs"
BACKLOG_EXISTS=""
if [[ -d "$BACKLOG_DIR" ]]; then
  BACKLOG_EXISTS=$(find "$BACKLOG_DIR" -maxdepth 1 -name "*${SPRINT}*" 2>/dev/null | head -1 || true)
fi
if [[ -z "$BACKLOG_EXISTS" ]]; then
  BLOCKERS="$BLOCKERS\n  - [ ] No sprint backlog document found for Sprint $SPRINT in '$BACKLOG_DIR/'"
fi

# Live check 4: Last semgrep scan?
LAST_SEMGREP=$(git log --all --oneline --grep="semgrep\|security scan" 2>/dev/null | head -1 || true)
if [[ -z "$LAST_SEMGREP" ]]; then
  BLOCKERS="$BLOCKERS\n  - [ ] No evidence of Semgrep security scan for this sprint"
fi

if [[ -n "$BLOCKERS" ]]; then
  # Normal stdout → Claude AI sees this as context/system-reminder
  echo "SPRINT GATE: Housekeeping incomplete for Sprint $SPRINT!"
  echo ""
  echo "STOP — Complete these items BEFORE starting the next sprint:"
  echo -e "$BLOCKERS"
  echo ""
  echo "After completing all items, update .sprint/state.md:"
  echo "  Set all housekeeping items to true"
  echo "  Set housekeeping_done: true"
  echo ""
  echo "Only THEN proceed with the next sprint."

  # JSON systemMessage → visible to user in Claude Desktop chat
  BLOCKER_SHORT=$(echo -e "$BLOCKERS" | tr '\n' ' ' | sed 's/  */ /g')
  echo "{\"systemMessage\": \"⚠️ Sprint $SPRINT Gate: Housekeeping incomplete —$BLOCKER_SHORT\"}"
fi

# Always exit 0 — warn, never block
exit 0
