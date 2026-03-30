#!/bin/bash

# Sprint Gate — PostToolUse Hook (Matcher: Bash — fires on ALL Bash calls)
# Quickly exits for non-commit calls. Runs full checks only after git commits.
# Works in both interactive AND autonomous mode (no user prompt needed).
#
# NOTE: The matcher is "Bash" (not "Bash(*git commit*)") because Claude Desktop
# interprets matchers as REGEX, and "Bash(*git commit*)" is invalid regex
# (* without preceding char). The script handles the filtering internally.

set -uo pipefail
# NOTE: -e deliberately omitted — pipeline failures in live checks (gh, find, git)
# must not cause silent script abort. Each check handles errors via || true.

STATE_FILE=".sprint/state.md"

# Quick exit: no sprint state → nothing to gate
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Quick exit: check if a new commit happened since our last check.
# This avoids running expensive checks on every Bash call (ruff, pytest, etc.)
LAST_COMMIT=$(git log -1 --format=%H 2>/dev/null || echo "none")
GATE_MARKER=".sprint/.last-gate-commit"
if [[ -f "$GATE_MARKER" ]]; then
  PREV_COMMIT=$(cat "$GATE_MARKER" 2>/dev/null || echo "")
  if [[ "$LAST_COMMIT" == "$PREV_COMMIT" ]]; then
    # No new commit since last check — skip
    exit 0
  fi
fi
# Record current commit so we don't re-check
echo "$LAST_COMMIT" > "$GATE_MARKER"

# Parse housekeeping_done
DONE=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

# If housekeeping is already done (or state.md has no frontmatter → DONE is empty), no gate needed.
# We explicitly check for "false" — any other value (including empty) means "not blocking".
if [[ "$DONE" == "true" ]] || [[ -z "$DONE" ]]; then
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
# Search in the canonical location: _docs/sprint backlogs/sprint_<N>_backlog.md
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
