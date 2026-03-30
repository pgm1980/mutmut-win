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
REMINDER="$REMINDER\nPROJEKT-STANDARDS (NICHT VERHANDELBAR):"
REMINDER="$REMINDER\n  - FS MCP Server für ALLE Filesystem-Operationen (KEIN cat, cp, mv, rm, find, grep via Bash)"
REMINDER="$REMINDER\n  - Serena für Code-Navigation (KEIN Grep für Klassen/Funktionen/Variablen)"
REMINDER="$REMINDER\n  - Context7 VOR Nutzung neuer APIs konsultieren"
REMINDER="$REMINDER\n  - Semgrep-Scan auf JEDE geänderte Datei"
REMINDER="$REMINDER\n  - Ruff Lint + Format auf JEDE geänderte Datei — 0 Findings"
REMINDER="$REMINDER\n  - mypy strict — 0 Errors"
REMINDER="$REMINDER\n  - pytest + hypothesis für alle Tests — kein unittest.TestCase"
REMINDER="$REMINDER\n  - Kein # noqa ohne Kommentar-Begründung direkt darüber"
REMINDER="$REMINDER\n  - Kein # type: ignore ohne spezifischen Error-Code und Begründung"
REMINDER="$REMINDER\n  - Type Hints für ALLE öffentlichen APIs — strict Mode"
REMINDER="$REMINDER\n  - Google-Style Docstrings für alle öffentlichen Klassen/Funktionen"
REMINDER="$REMINDER\n  - Pydantic-Models für alle Datenstrukturen — keine rohen Dicts"
REMINDER="$REMINDER\n  - Alle neuen Module: Package-Struktur muss der src/-Verzeichnisstruktur entsprechen"
REMINDER="$REMINDER\n  - uv run für ALLE Ausführungen (nicht python direkt)"
REMINDER="$REMINDER\n  - mutmut-win Mutation Testing auf JEDEN neuen/geänderten Code"
REMINDER="$REMINDER\n  - Mutation Score >= 80% auf neuem Code"
REMINDER="$REMINDER\n  - Subagent-Prompts MÜSSEN 5 Sektionen enthalten: KONTEXT, ZIEL, CONSTRAINTS, MCP-ANWEISUNGEN, OUTPUT"

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
