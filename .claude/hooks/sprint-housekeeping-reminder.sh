#!/bin/bash

# Sprint Housekeeping Reminder — Stop Hook (runs alongside ralph-stop-hook)
# Warns about incomplete housekeeping when session ends.

set -uo pipefail
# NOTE: -e deliberately omitted — git/parse commands may fail in edge cases

STATE_FILE=".sprint/state.md"

# No sprint state → check basic hygiene only
if [[ ! -f "$STATE_FILE" ]]; then
  # Still check for uncommitted changes
  CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$CHANGES" -gt 0 ]]; then
    echo "WARNING: $CHANGES uncommitted files. Consider committing before ending session."
  fi
  exit 0
fi

# Parse state
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
SPRINT=$(echo "$FRONTMATTER" | grep '^current_sprint:' | sed 's/current_sprint: *//' | tr -d '"')
DONE=$(echo "$FRONTMATTER" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

WARNINGS=""

# Uncommitted changes
CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [[ "$CHANGES" -gt 0 ]]; then
  WARNINGS="$WARNINGS\n  - $CHANGES uncommitted files!"
fi

# Housekeeping incomplete
if [[ "$DONE" == "false" ]]; then
  WARNINGS="$WARNINGS\n  - Sprint $SPRINT housekeeping incomplete (see .sprint/state.md)"

  MEM=$(echo "$FRONTMATTER" | grep 'memory_updated:' | sed 's/.*: *//' | tr -d '"')
  ISS=$(echo "$FRONTMATTER" | grep 'github_issues_closed:' | sed 's/.*: *//' | tr -d '"')
  SBL=$(echo "$FRONTMATTER" | grep 'sprint_backlog_written:' | sed 's/.*: *//' | tr -d '"')

  [[ "$MEM" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] MEMORY.md"
  [[ "$ISS" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] GitHub Issues"
  [[ "$SBL" == "false" ]] && WARNINGS="$WARNINGS\n    - [ ] Sprint Backlog"
fi

if [[ -n "$WARNINGS" ]]; then
  echo "SESSION END — Open items:"
  echo -e "$WARNINGS"
fi

# Never block exit
exit 0
