#!/bin/bash

# Sprint State Save — PreCompact Hook
# Saves current sprint context before context compaction.
# Updates the "Sprint Context" section in .sprint/state.md
# so Claude retains sprint awareness after compaction.

set -uo pipefail
# NOTE: -e deliberately omitted — git commands may fail in young repos (few commits)

STATE_FILE=".sprint/state.md"

# No sprint state → nothing to save
if [[ ! -f "$STATE_FILE" ]]; then
  exit 0
fi

# Gather current context
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
LAST_COMMITS=$(git log -10 --oneline 2>/dev/null || echo "no commits")
UNCOMMITTED=$(git status --short 2>/dev/null | head -15)
CHANGED_FILES=$(git diff --name-only HEAD~5..HEAD 2>/dev/null | head -20 || git diff --name-only --root HEAD 2>/dev/null | head -20)
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Build new context section
CONTEXT="## Sprint Context (auto-saved before compaction at $TIMESTAMP)

### Current Branch
$CURRENT_BRANCH

### Last 10 Commits
\`\`\`
$LAST_COMMITS
\`\`\`

### Recently Changed Files
\`\`\`
$CHANGED_FILES
\`\`\`"

if [[ -n "$UNCOMMITTED" ]]; then
  CONTEXT="$CONTEXT

### Uncommitted Changes
\`\`\`
$UNCOMMITTED
\`\`\`"
fi

# Replace everything after the closing --- (the context section)
# Keep frontmatter + prompt, replace context
python -c "
import sys

state_file = sys.argv[1]
new_context = sys.argv[2]

with open(state_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Split on frontmatter boundaries
parts = content.split('---')
if len(parts) >= 3:
    # parts[0] = empty before first ---
    # parts[1] = YAML frontmatter
    # parts[2+] = body content
    body = '---'.join(parts[2:])

    # Find existing Sprint Context section and replace, or append
    import re
    pattern = r'## Sprint Context.*'
    if re.search(pattern, body, re.DOTALL):
        # Replace existing context section
        body = re.sub(pattern, new_context, body, flags=re.DOTALL)
    else:
        # Append context section
        body = body.rstrip() + '\n\n' + new_context + '\n'

    result = '---' + parts[1] + '---' + body

    with open(state_file, 'w', encoding='utf-8') as f:
        f.write(result)

" "$STATE_FILE" "$CONTEXT"

echo "Sprint state saved before compaction (branch: $CURRENT_BRANCH, $(echo "$LAST_COMMITS" | wc -l | tr -d ' ') recent commits)"
exit 0
