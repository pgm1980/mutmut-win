#!/bin/bash

# Sprint Health Check — SessionStart Hook
# Shows sprint status, open housekeeping items, and warnings at session start.
# Reads .sprint/state.md if it exists.
# Validates YAML frontmatter schema (all 11 required fields).
#
# OUTPUT: Normal stdout → Claude AI context (system-reminder)
#         JSON systemMessage → visible to user in chat

set -uo pipefail
# NOTE: -e deliberately omitted — git commands may fail in edge cases

STATE_FILE=".sprint/state.md"

# No sprint state → nothing to show
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Parse YAML frontmatter
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")

# --- Schema Validation ---
REQUIRED_FIELDS=(
  "current_sprint"
  "sprint_goal"
  "branch"
  "started_at"
  "housekeeping_done"
  "memory_updated"
  "github_issues_closed"
  "sprint_backlog_written"
  "semgrep_passed"
  "tests_passed"
  "documentation_updated"
)

MISSING_FIELDS=""
if [[ -z "$FRONTMATTER" ]]; then
  MISSING_FIELDS="ALL (no YAML frontmatter found)"
else
  for field in "${REQUIRED_FIELDS[@]}"; do
    if ! echo "$FRONTMATTER" | grep -q "^${field}:"; then
      MISSING_FIELDS="$MISSING_FIELDS $field"
    fi
  done
fi

if [[ -n "$MISSING_FIELDS" ]]; then
  echo "SPRINT STATE VALIDATION FAILED"
  echo "  Missing fields: $MISSING_FIELDS"
  echo "  See CLAUDE.md 'Sprint State Management' for the schema."
  echo "{\"systemMessage\": \"❌ Sprint state.md validation failed — missing fields:$MISSING_FIELDS\"}"
  exit 0
fi

# Parse fields
SPRINT=$(echo "$FRONTMATTER" | grep '^current_sprint:' | sed 's/current_sprint: *//' | tr -d '"')
GOAL=$(echo "$FRONTMATTER" | grep '^sprint_goal:' | sed 's/sprint_goal: *//' | tr -d '"')
BRANCH=$(echo "$FRONTMATTER" | grep '^branch:' | sed 's/branch: *//' | tr -d '"')
STARTED=$(echo "$FRONTMATTER" | grep '^started_at:' | sed 's/started_at: *//' | tr -d '"')
DONE=$(echo "$FRONTMATTER" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

# Current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
LAST_COMMITS=$(git log -3 --oneline 2>/dev/null || echo "no commits")
CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

# Build normal output (→ Claude AI context)
OUTPUT="SPRINT STATUS"
OUTPUT="$OUTPUT\n  Sprint: $SPRINT — $GOAL"
OUTPUT="$OUTPUT\n  Branch: $CURRENT_BRANCH (expected: $BRANCH)"
OUTPUT="$OUTPUT\n  Started: $STARTED"
OUTPUT="$OUTPUT\n  Changes: $CHANGES uncommitted files"
OUTPUT="$OUTPUT\n  Recent: $LAST_COMMITS"

# Warnings
WARNINGS=""
USER_WARNINGS=""

if [[ "$CURRENT_BRANCH" != "$BRANCH" ]] && [[ -n "$BRANCH" ]]; then
  WARNINGS="$WARNINGS\n  WARNING: On branch '$CURRENT_BRANCH' but sprint expects '$BRANCH'"
  USER_WARNINGS="$USER_WARNINGS Branch mismatch ($CURRENT_BRANCH vs $BRANCH)."
fi

if [[ "$CURRENT_BRANCH" == "main" ]] || [[ "$CURRENT_BRANCH" == "master" ]]; then
  WARNINGS="$WARNINGS\n  WARNING: On main/master branch! Create a feature branch before coding."
  USER_WARNINGS="$USER_WARNINGS On main — create feature branch!"
fi

LAST_COMMIT_EPOCH=$(git log -1 --format=%ct 2>/dev/null || echo "0")
NOW_EPOCH=$(date +%s)
DAYS_SINCE=$(( (NOW_EPOCH - LAST_COMMIT_EPOCH) / 86400 ))
if [[ $DAYS_SINCE -gt 3 ]]; then
  WARNINGS="$WARNINGS\n  WARNING: Last commit was $DAYS_SINCE days ago. Stale branch?"
fi

HK_COUNT=0
if [[ "$DONE" == "false" ]]; then
  WARNINGS="$WARNINGS\n  HOUSEKEEPING INCOMPLETE — Complete before starting next sprint:"
  MEM=$(echo "$FRONTMATTER" | grep 'memory_updated:' | sed 's/.*: *//' | tr -d '"')
  ISS=$(echo "$FRONTMATTER" | grep 'github_issues_closed:' | sed 's/.*: *//' | tr -d '"')
  SBL=$(echo "$FRONTMATTER" | grep 'sprint_backlog_written:' | sed 's/.*: *//' | tr -d '"')
  SEM=$(echo "$FRONTMATTER" | grep 'semgrep_passed:' | sed 's/.*: *//' | tr -d '"')
  TST=$(echo "$FRONTMATTER" | grep 'tests_passed:' | sed 's/.*: *//' | tr -d '"')
  DOC=$(echo "$FRONTMATTER" | grep 'documentation_updated:' | sed 's/.*: *//' | tr -d '"')

  [[ "$MEM" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] MEMORY.md not updated" && HK_COUNT=$((HK_COUNT+1))
  [[ "$ISS" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] GitHub Issues not closed" && HK_COUNT=$((HK_COUNT+1))
  [[ "$SBL" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Sprint Backlog not written" && HK_COUNT=$((HK_COUNT+1))
  [[ "$SEM" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Semgrep scan not passed" && HK_COUNT=$((HK_COUNT+1))
  [[ "$TST" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Tests not confirmed passing" && HK_COUNT=$((HK_COUNT+1))
  [[ "$DOC" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Documentation not updated" && HK_COUNT=$((HK_COUNT+1))
  USER_WARNINGS="$USER_WARNINGS HK: $HK_COUNT open items."
fi

if [[ -n "$WARNINGS" ]]; then
  OUTPUT="$OUTPUT\n$WARNINGS"
fi

# Normal stdout → Claude AI context
echo -e "$OUTPUT"

# JSON systemMessage → visible to user in chat
if [[ -n "$USER_WARNINGS" ]]; then
  echo "{\"systemMessage\": \"📋 Sprint $SPRINT ($GOAL) —$USER_WARNINGS\"}"
else
  echo "{\"systemMessage\": \"✅ Sprint $SPRINT ($GOAL) — all clear\"}"
fi

exit 0
