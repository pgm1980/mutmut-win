#!/bin/bash

# StatusLine — Permanent display in Claude Code UI
# Shows: Sprint | Branch | Build | Uncommitted | Housekeeping

set -uo pipefail

PARTS=""

# Sprint info
STATE_FILE=".sprint/state.md"
if [[ -f "$STATE_FILE" ]]; then
  FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE" 2>/dev/null)
  SPRINT=$(echo "$FRONTMATTER" | grep '^current_sprint:' | sed 's/current_sprint: *//' | tr -d '"')
  DONE=$(echo "$FRONTMATTER" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

  if [[ -n "$SPRINT" ]]; then
    if [[ "$DONE" == "false" ]]; then
      PARTS="S${SPRINT} [HK!]"
    else
      PARTS="S${SPRINT}"
    fi
  fi
fi

# Branch
BRANCH=$(git branch --show-current 2>/dev/null || echo "?")
PARTS="$PARTS | $BRANCH"

# Uncommitted changes
CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
if [[ "$CHANGES" -gt 0 ]]; then
  PARTS="$PARTS | ${CHANGES}mod"
fi

echo "$PARTS"
