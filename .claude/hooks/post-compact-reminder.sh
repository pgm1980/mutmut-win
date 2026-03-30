#!/bin/bash

# Post-Compact Reminder — PostCompact Hook
# After context compaction, reminds Claude of critical CLAUDE.md directives.
# Also injects current sprint state so Claude knows where it is.
#
# OUTPUT: Normal stdout → Claude AI context (system-reminder)
#         JSON systemMessage → visible to user in chat

set -uo pipefail

STATE_FILE=".sprint/state.md"

# Build reminder (→ Claude AI context)
REMINDER="CONTEXT COMPACTION OCCURRED — CLAUDE.md directives refreshed."
REMINDER="$REMINDER\n"
REMINDER="$REMINDER\nCRITICAL REMINDERS (from CLAUDE.md):"
REMINDER="$REMINDER\n  1. Serena for ALL code navigation (no Grep for classes/methods/functions)"
REMINDER="$REMINDER\n  2. FS MCP for ALL filesystem operations (no cat/cp/mv/rm/ls via Bash)"
REMINDER="$REMINDER\n  3. Context7 BEFORE using unfamiliar APIs"
REMINDER="$REMINDER\n  4. Semgrep scan on EVERY modified file before committing"
REMINDER="$REMINDER\n  5. Sequential Thinking (min 5 steps) for architecture decisions"
REMINDER="$REMINDER\n  6. Tests MUST pass before moving to next sprint"
REMINDER="$REMINDER\n  7. MEMORY.md MUST be updated after each sprint"
REMINDER="$REMINDER\n  8. GitHub Issues MUST be closed after sprint completion"
REMINDER="$REMINDER\n  9. Sprint Backlog document MUST exist for each sprint"
REMINDER="$REMINDER\n  10. Subagent prompts MUST contain 5 sections: KONTEXT, ZIEL, CONSTRAINTS, MCP-ANWEISUNGEN, OUTPUT"

USER_MSG="Context compacted."

# Inject sprint state if available
if [[ -f "$STATE_FILE" ]]; then
  FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$STATE_FILE")
  SPRINT=$(echo "$FRONTMATTER" | grep '^current_sprint:' | sed 's/current_sprint: *//' | tr -d '"')
  GOAL=$(echo "$FRONTMATTER" | grep '^sprint_goal:' | sed 's/sprint_goal: *//' | tr -d '"')
  BRANCH=$(echo "$FRONTMATTER" | grep '^branch:' | sed 's/branch: *//' | tr -d '"')
  DONE=$(echo "$FRONTMATTER" | grep '^housekeeping_done:' | sed 's/housekeeping_done: *//' | tr -d '"')

  REMINDER="$REMINDER\n"
  REMINDER="$REMINDER\nCURRENT SPRINT STATE:"
  REMINDER="$REMINDER\n  Sprint: $SPRINT — $GOAL"
  REMINDER="$REMINDER\n  Branch: $BRANCH"
  REMINDER="$REMINDER\n  Housekeeping done: $DONE"

  USER_MSG="Context compacted. Sprint $SPRINT ($GOAL)."

  if [[ "$DONE" == "false" ]]; then
    REMINDER="$REMINDER\n  WARNING: Housekeeping incomplete!"
    USER_MSG="$USER_MSG HK incomplete!"
  fi
fi

# Normal stdout → Claude AI context
echo -e "$REMINDER"

# JSON systemMessage → visible to user in chat
echo "{\"systemMessage\": \"🔄 $USER_MSG\"}"

exit 0
