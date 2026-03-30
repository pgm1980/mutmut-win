#!/bin/bash

# Sprint Health Check — SessionStart Hook
# Shows sprint status, open housekeeping items, and warnings at session start.
# Reads .sprint/state.md if it exists.
# Validates YAML frontmatter schema (all 11 required fields).

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
# All 11 fields are required per CLAUDE.md "Sprint State Management" section.
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
  MISSING_FIELDS="ALL (no YAML frontmatter found — file must start with ---)"
else
  for field in "${REQUIRED_FIELDS[@]}"; do
    if ! echo "$FRONTMATTER" | grep -q "^${field}:"; then
      MISSING_FIELDS="$MISSING_FIELDS $field"
    fi
  done
fi

if [[ -n "$MISSING_FIELDS" ]]; then
  echo "SPRINT STATE VALIDATION FAILED"
  echo ""
  echo "  .sprint/state.md is missing required YAML frontmatter fields:"
  echo "  $MISSING_FIELDS"
  echo ""
  echo "  See CLAUDE.md section 'Sprint State Management' for the required schema."
  echo "  Fix .sprint/state.md before proceeding."
  echo ""
  # Continue with remaining checks — don't exit, so Claude still gets branch/commit info
fi

# Parse fields
SPRINT=$(echo "$FRONTMATTER" | grep '^current_sprint:' | sed 's/current_sprint: *//' | tr -d '"')
GOAL=$(echo "$FRONTMATTER" | grep '^sprint_goal:' | sed 's/sprint_goal: *//' | tr -d '"')
BRANCH=$(echo "$FRONTMATTER" | grep '^branch:' | sed 's/branch: *//' | tr -d '"')
STARTED=$(echo "$FRONTMATTER" | grep '^started_at:' | sed 's/started_at: *//' | tr -d '"')
DONE=$(echo "$FRONTMATTER" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

# Current branch
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")

# Last 3 commits
LAST_COMMITS=$(git log -3 --oneline 2>/dev/null || echo "no commits")

# Uncommitted changes count
CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

# Build output
OUTPUT="SPRINT STATUS"
OUTPUT="$OUTPUT\n  Sprint: $SPRINT — $GOAL"
OUTPUT="$OUTPUT\n  Branch: $CURRENT_BRANCH (expected: $BRANCH)"
OUTPUT="$OUTPUT\n  Started: $STARTED"
OUTPUT="$OUTPUT\n  Changes: $CHANGES uncommitted files"
OUTPUT="$OUTPUT\n  Recent: $LAST_COMMITS"

# Warnings
WARNINGS=""

# Wrong branch?
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]] && [[ -n "$BRANCH" ]]; then
  WARNINGS="$WARNINGS\n  WARNING: On branch '$CURRENT_BRANCH' but sprint expects '$BRANCH'"
fi

# On main/master?
if [[ "$CURRENT_BRANCH" == "main" ]] || [[ "$CURRENT_BRANCH" == "master" ]]; then
  WARNINGS="$WARNINGS\n  WARNING: On main/master branch! Create a feature branch before coding."
fi

# Stale branch? (>3 days since last commit on this branch)
LAST_COMMIT_EPOCH=$(git log -1 --format=%ct 2>/dev/null || echo "0")
NOW_EPOCH=$(date +%s)
DAYS_SINCE=$(( (NOW_EPOCH - LAST_COMMIT_EPOCH) / 86400 ))
if [[ $DAYS_SINCE -gt 3 ]]; then
  WARNINGS="$WARNINGS\n  WARNING: Last commit was $DAYS_SINCE days ago. Stale branch?"
fi

# Housekeeping incomplete?
if [[ "$DONE" == "false" ]]; then
  WARNINGS="$WARNINGS\n  HOUSEKEEPING INCOMPLETE — Complete before starting next sprint:"

  # Check individual items
  MEM=$(echo "$FRONTMATTER" | grep 'memory_updated:' | sed 's/.*: *//' | tr -d '"')
  ISS=$(echo "$FRONTMATTER" | grep 'github_issues_closed:' | sed 's/.*: *//' | tr -d '"')
  SBL=$(echo "$FRONTMATTER" | grep 'sprint_backlog_written:' | sed 's/.*: *//' | tr -d '"')
  SEM=$(echo "$FRONTMATTER" | grep 'semgrep_passed:' | sed 's/.*: *//' | tr -d '"')
  TST=$(echo "$FRONTMATTER" | grep 'tests_passed:' | sed 's/.*: *//' | tr -d '"')
  DOC=$(echo "$FRONTMATTER" | grep 'documentation_updated:' | sed 's/.*: *//' | tr -d '"')

  [[ "$MEM" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] MEMORY.md not updated"
  [[ "$ISS" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] GitHub Issues not closed"
  [[ "$SBL" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Sprint Backlog not written"
  [[ "$SEM" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Semgrep scan not passed"
  [[ "$TST" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Tests not confirmed passing"
  [[ "$DOC" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Documentation not updated"
fi

if [[ -n "$WARNINGS" ]]; then
  OUTPUT="$OUTPUT\n$WARNINGS"
fi

echo -e "$OUTPUT"
exit 0
