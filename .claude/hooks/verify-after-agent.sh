#!/bin/bash
# SubagentStop Hook: Automatische Verifikation nach Agent-Rückkehr
# Führt Lint, Type-Check, Tests und Semgrep auf geänderte Dateien aus.
#
# OUTPUT: Normal stdout → Claude AI context
#         JSON systemMessage → visible to user in chat

set -uo pipefail

INPUT=$(cat)
RESULTS=""
HAS_ERRORS=false

# --- 1. Ruff Lint prüfen ---
LINT_OUTPUT=$(uv run ruff check . 2>&1)
LINT_EXIT=$?

if [ $LINT_EXIT -eq 0 ]; then
  RESULTS="RUFF: OK (0 Findings)"
else
  RESULTS="RUFF: FAILED"
  HAS_ERRORS=true
  LINT_ERRORS=$(echo "$LINT_OUTPUT" | head -20)
  RESULTS="$RESULTS\n$LINT_ERRORS"
fi

# --- 2. mypy Type-Check ---
if [ "$HAS_ERRORS" = false ]; then
  MYPY_OUTPUT=$(uv run mypy src/ 2>&1)
  MYPY_EXIT=$?

  if [ $MYPY_EXIT -eq 0 ]; then
    RESULTS="$RESULTS\nMYPY: OK (0 Errors)"
  else
    RESULTS="$RESULTS\nMYPY: FAILED"
    HAS_ERRORS=true
    MYPY_ERRORS=$(echo "$MYPY_OUTPUT" | head -20)
    RESULTS="$RESULTS\n$MYPY_ERRORS"
  fi
fi

# --- 3. Tests prüfen ---
if [ "$HAS_ERRORS" = false ]; then
  TEST_OUTPUT=$(uv run pytest --tb=short -q 2>&1)
  TEST_EXIT=$?

  if [ $TEST_EXIT -eq 0 ]; then
    RESULTS="$RESULTS\nTESTS: OK (alle grün)"
  else
    RESULTS="$RESULTS\nTESTS: FAILED"
    HAS_ERRORS=true
    TEST_ERRORS=$(echo "$TEST_OUTPUT" | grep -E "FAILED|ERROR" | head -10)
    RESULTS="$RESULTS\n$TEST_ERRORS"
  fi
fi

# --- 4. Semgrep auf geänderte Dateien ---
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null | grep '\.py$' || true)
if [ -n "$CHANGED_FILES" ]; then
  SEMGREP_OUTPUT=$(echo "$CHANGED_FILES" | xargs semgrep scan --config auto --quiet 2>&1)
  SEMGREP_EXIT=$?

  if [ $SEMGREP_EXIT -eq 0 ] && [ -z "$SEMGREP_OUTPUT" ]; then
    RESULTS="$RESULTS\nSEMGREP: OK"
  else
    RESULTS="$RESULTS\nSEMGREP: FINDINGS"
    HAS_ERRORS=true
    SEMGREP_FINDINGS=$(echo "$SEMGREP_OUTPUT" | head -20)
    RESULTS="$RESULTS\n$SEMGREP_FINDINGS"
  fi
else
  RESULTS="$RESULTS\nSEMGREP: SKIP (no changed .py files)"
fi

# --- Output ---
if [ "$HAS_ERRORS" = true ]; then
  # Normal stdout → Claude AI context
  echo "VERIFICATION FAILED after subagent return:"
  echo -e "$RESULTS"
  echo "ACTION REQUIRED: Fix errors before continuing."

  # JSON systemMessage → visible to user in chat
  echo "{\"systemMessage\": \"❌ Subagent verification FAILED — ruff/mypy/pytest/semgrep issues found\"}"
else
  # Normal stdout → Claude AI context
  echo "VERIFICATION PASSED after subagent return:"
  echo -e "$RESULTS"

  # JSON systemMessage → visible to user in chat
  echo "{\"systemMessage\": \"✅ Subagent verification passed (ruff + mypy + pytest + semgrep)\"}"
fi

exit 0
