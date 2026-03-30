#!/bin/bash

# Sprint Housekeeping Reminder — Stop Hook
# Warns about incomplete housekeeping when session ends.
#
# OUTPUT: Normal stdout → Claude AI context
#         JSON systemMessage → visible to user in chat

set -uo pipefail

STATE_FILE=".sprint/state.md"

# No sprint state → check basic hygiene only
if [[ ! -f "$STATE_FILE" ]]; then
  CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$CHANGES" -gt 0 ]]; then
    echo "WARNING: $CHANGES uncommitted files."
    echo "{\"systemMessage\": \"⚠️ $CHANGES uncommitted files — consider committing before ending session.\"}"
  fi
  exit 0
fi

# Parse state
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
SPRINT=$(echo "$FRONTMATTER" | grep '^current_sprint:' | sed 's/current_sprint: *//' | tr -d '"')
DONE=$(echo "$FRONTMATTER" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

WARNINGS=""
USER_MSG=""

# Uncommitted changes
CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [[ "$CHANGES" -gt 0 ]]; then
  WARNINGS="$WARNINGS\n  - $CHANGES uncommitted files!"
  USER_MSG="$USER_MSG $CHANGES uncommitted files."
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
  USER_MSG="$USER_MSG Sprint $SPRINT HK incomplete."
fi

if [[ -n "$WARNINGS" ]]; then
  # Normal stdout → Claude AI context
  echo "SESSION END — Open items:"
  echo -e "$WARNINGS"

  # JSON systemMessage → visible to user in chat
  echo "{\"systemMessage\": \"🛑 Session End:$USER_MSG\"}"
fi

# Never block exit
exit 0
