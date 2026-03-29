#!/bin/bash

# Sprint Gate — PostToolUse Hook (Matcher: Bash(git commit*))
# Fires after every git commit. Checks if housekeeping is incomplete
# and warns Claude before it moves to the next sprint.
# Works in both interactive AND autonomous mode (no user prompt needed).

set -uo pipefail
# NOTE: -e deliberately omitted — pipeline failures in live checks (gh, find, git)
# must not cause silent script abort. Each check handles errors via || true.

STATE_FILE=".sprint/state.md"

# No sprint state → nothing to gate
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Parse housekeeping_done
DONE=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

# If housekeeping is already done, no gate needed
if [[ "$DONE" != "false" ]]; then
  exit 0
fi

# Housekeeping is incomplete — run live checks on every commit
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
BACKLOG_EXISTS=$(find . -maxdepth 4 \( -name "*sprint_backlog*${SPRINT}*" -o -name "*sprint*${SPRINT}*backlog*" \) 2>/dev/null | head -1 || true)
if [[ -z "$BACKLOG_EXISTS" ]]; then
  BLOCKERS="$BLOCKERS\n  - [ ] No sprint backlog document found for Sprint $SPRINT"
fi

# Live check 4: Last semgrep scan?
LAST_SEMGREP=$(git log --all --oneline --grep="semgrep\|security scan" 2>/dev/null | head -1 || true)
if [[ -z "$LAST_SEMGREP" ]]; then
  BLOCKERS="$BLOCKERS\n  - [ ] No evidence of Semgrep security scan for this sprint"
fi

if [[ -n "$BLOCKERS" ]]; then
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
fi

# Always exit 0 — warn, never block
exit 0
