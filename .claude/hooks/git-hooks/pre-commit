#!/bin/bash

# Git Pre-Commit Hook — Dispatcher
# Detects project language and runs appropriate quality checks.
# Install: git config core.hooksPath .claude/hooks/git-hooks
# Or:      cp .claude/hooks/git-hooks/pre-commit .git/hooks/pre-commit

set -uo pipefail

ERRORS=""
STAGED_FILES=$(git diff --cached --name-only --diff-filter=ACM)

if [[ -z "$STAGED_FILES" ]]; then
  exit 0
fi

# ── Python Project ─────────────────────────────────────────
if [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]]; then
  STAGED_PY=$(echo "$STAGED_FILES" | grep '\.py$' || true)
  if [[ -n "$STAGED_PY" ]]; then
    echo "Pre-commit: Python files detected — running ruff + mypy..."

    # Ruff lint
    if command -v uv &>/dev/null; then
      uv run ruff check $STAGED_PY 2>/dev/null
      if [[ $? -ne 0 ]]; then
        ERRORS="$ERRORS\n  FAIL: ruff check found lint errors"
      fi
    elif command -v ruff &>/dev/null; then
      ruff check $STAGED_PY 2>/dev/null
      if [[ $? -ne 0 ]]; then
        ERRORS="$ERRORS\n  FAIL: ruff check found lint errors"
      fi
    fi

    # mypy
    if command -v uv &>/dev/null; then
      uv run mypy $STAGED_PY --no-error-summary 2>/dev/null
      if [[ $? -ne 0 ]]; then
        ERRORS="$ERRORS\n  FAIL: mypy found type errors"
      fi
    elif command -v mypy &>/dev/null; then
      mypy $STAGED_PY --no-error-summary 2>/dev/null
      if [[ $? -ne 0 ]]; then
        ERRORS="$ERRORS\n  FAIL: mypy found type errors"
      fi
    fi
  fi
fi

# ── C# / .NET Project ─────────────────────────────────────
if ls *.slnx *.sln 2>/dev/null | head -1 > /dev/null 2>&1; then
  STAGED_CS=$(echo "$STAGED_FILES" | grep '\.cs$' || true)
  if [[ -n "$STAGED_CS" ]]; then
    echo "Pre-commit: C# files detected — running dotnet build..."
    dotnet build --nologo --verbosity quiet 2>&1
    if [[ $? -ne 0 ]]; then
      ERRORS="$ERRORS\n  FAIL: dotnet build failed (TreatWarningsAsErrors)"
    fi
  fi
fi

# ── Rust Project ───────────────────────────────────────────
if [[ -f "Cargo.toml" ]]; then
  STAGED_RS=$(echo "$STAGED_FILES" | grep '\.rs$' || true)
  if [[ -n "$STAGED_RS" ]]; then
    echo "Pre-commit: Rust files detected — running cargo clippy + check..."
    cargo clippy --all-targets -- -D warnings 2>/dev/null
    if [[ $? -ne 0 ]]; then
      ERRORS="$ERRORS\n  FAIL: cargo clippy found warnings"
    fi
  fi
fi

# ── Java Project ───────────────────────────────────────────
if [[ -f "pom.xml" ]] || [[ -f "build.gradle" ]] || [[ -f "build.gradle.kts" ]]; then
  STAGED_JAVA=$(echo "$STAGED_FILES" | grep '\.java$\|\.kt$' || true)
  if [[ -n "$STAGED_JAVA" ]]; then
    echo "Pre-commit: Java/Kotlin files detected — running compile check..."
    if [[ -f "pom.xml" ]]; then
      mvn compile -q 2>/dev/null
    elif [[ -f "build.gradle" ]] || [[ -f "build.gradle.kts" ]]; then
      ./gradlew compileJava -q 2>/dev/null
    fi
    if [[ $? -ne 0 ]]; then
      ERRORS="$ERRORS\n  FAIL: compile check failed"
    fi
  fi
fi

# ── Scala Project ──────────────────────────────────────────
if [[ -f "build.sbt" ]]; then
  STAGED_SCALA=$(echo "$STAGED_FILES" | grep '\.scala$' || true)
  if [[ -n "$STAGED_SCALA" ]]; then
    echo "Pre-commit: Scala files detected — running sbt compile..."
    sbt compile 2>/dev/null
    if [[ $? -ne 0 ]]; then
      ERRORS="$ERRORS\n  FAIL: sbt compile failed"
    fi
  fi
fi

# ── Semgrep (all languages) ───────────────────────────────
if command -v semgrep &>/dev/null; then
  # Only scan staged files that are source code
  STAGED_CODE=$(echo "$STAGED_FILES" | grep -E '\.(py|cs|rs|java|kt|scala|js|ts|go)$' || true)
  if [[ -n "$STAGED_CODE" ]]; then
    echo "Pre-commit: Running Semgrep security scan..."
    echo "$STAGED_CODE" | xargs semgrep scan --config auto --quiet 2>/dev/null
    if [[ $? -ne 0 ]]; then
      ERRORS="$ERRORS\n  FAIL: Semgrep found security issues"
    fi
  fi
fi

# ── Secret Detection (all languages) ──────────────────────
SECRETS_PATTERN='(AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|sk-[0-9a-zA-Z]{48}|ghp_[0-9a-zA-Z]{36}|password\s*=\s*["\x27][^"\x27]{8,}|api[_-]?key\s*=\s*["\x27][^"\x27]{8,})'
STAGED_CONTENT=$(git diff --cached -U0 | grep '^+[^+]' || true)
if echo "$STAGED_CONTENT" | grep -qiE "$SECRETS_PATTERN"; then
  ERRORS="$ERRORS\n  FAIL: Potential secrets/API keys detected in staged changes!"
fi

# ── Result ────────────────────────────────────────────────
if [[ -n "$ERRORS" ]]; then
  echo ""
  echo "PRE-COMMIT FAILED:"
  echo -e "$ERRORS"
  echo ""
  echo "Fix the issues above, then try again."
  exit 1
fi

echo "Pre-commit: All checks passed."
exit 0
