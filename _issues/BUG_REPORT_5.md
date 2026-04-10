# BUG REPORT 5: mutmut-win 1.0.10 — [tool.uv.sources] Stripping + Empty venv in mutants/

**Reporter:** Claude Code Agent (pgm1980/nextgen-cot-mcp-server)
**Date:** 2026-04-10
**Version:** mutmut-win 1.0.10 (git tag v1.0.10, commit `6337d7e`, reports as version 1.0.7)
**Severity:** Blocker (prevents mutation testing for projects with git-based uv dependencies)
**Environment:** Windows 11 Pro, Python 3.14.3, uv (latest), hatchling build-backend

---

## Summary

mutmut-win 1.0.10 creates an empty `.venv` in the `mutants/` directory and fails to install any dependencies into it. When the clean test suite runs, it uses this empty venv and fails because neither the project nor pytest are importable. This makes mutation testing impossible.

Additionally, `[tool.uv.sources]` sections in `pyproject.toml` are reordered (moved to the end of the file). While not a bug per se (the content is preserved), the reordering combined with the empty venv creates a situation where `uv sync` cannot resolve git-based dependencies during the mutmut-win-controlled setup phase.

---

## Bug 1: Empty venv in mutants/ (Blocker)

### Symptoms

```
Running clean test suite…
Error: Clean test run failed with exit code 1. Fix tests before mutating.
```

### Root Cause

mutmut-win creates `mutants/.venv` using `python -m venv` (or similar) but does **not** run `uv sync` or `pip install` to populate it. The resulting venv is empty:

```
$ mutants/.venv/Scripts/python -c "import nextgen_cot_mcp_server"
ModuleNotFoundError: No module named 'nextgen_cot_mcp_server'

$ mutants/.venv/Scripts/pip list
Package    Version
---------- -------
(empty - no packages installed)
```

When mutmut-win runs the clean test suite using this venv's Python, it fails because:
1. `pytest` is not installed
2. The project package is not installed
3. No dependencies (pydantic, structlog, etc.) are available

### Expected Behavior

mutmut-win should either:
- Run `uv sync` in the `mutants/` directory after creating the venv (preferred for uv-based projects)
- Or use the parent project's venv Python instead of creating a new empty one
- Or at minimum run `pip install -e .` in the mutants/ directory

### Comparison with Working Projects

In other projects where mutmut-win 1.0.10 works correctly, the `mutants/.venv` is either:
- Not created (mutmut-win reuses the parent venv)
- Properly populated with all dependencies

The difference may be related to the build backend (hatchling), the project structure (`src/` layout with editable install), or the presence of git-based dependencies in `[tool.uv.sources]`.

---

## Bug 2: [tool.uv.sources] Section Reordering

### Symptoms

The `[tool.uv.sources]` section is moved from its original position to the end of `mutants/pyproject.toml`:

**Root pyproject.toml (line 224):**
```toml
[tool.uv.sources]
mutmut-win = { git = "https://github.com/pgm1980/mutmut-win.git", rev = "v1.0.10" }

[tool.mutmut]
paths_to_mutate = ["src/nextgen_cot_mcp_server/"]
tests_dir = ["tests/"]
```

**mutants/pyproject.toml (line 228, moved to end):**
```toml
[tool.mutmut]
paths_to_mutate = ["src/nextgen_cot_mcp_server/"]
tests_dir = ["tests/"]

[tool.uv.sources]
mutmut-win = { git = "https://github.com/pgm1980/mutmut-win.git", rev = "v1.0.10" }
```

### Impact

The content is preserved (no data loss), but the reordering may interfere with uv's TOML parsing in edge cases. When combined with Bug 1 (empty venv), `uv sync` is never called, so the sources section is never used.

### Expected Behavior

Section order should be preserved during copy, or at minimum not cause any behavioral difference.

---

## Bug 3: Version String Not Updated

### Symptoms

```
$ uv run mutmut-win --version
mutmut-win, version 1.0.7
```

Despite being installed from git tag `v1.0.10` (commit `6337d7e`).

### Impact

Minor (cosmetic), but makes it difficult to verify which version is actually installed.

---

## Bug 4: "No test-to-mutant mappings found" Warning

### Symptoms

```
Collecting test timing statistics…
Warning: no test-to-mutant mappings found. Tests may not cover any mutated code.
```

### Impact

Without test-to-mutant mappings, mutmut-win runs **ALL** tests for **EVERY** mutant instead of only the relevant subset. This causes:
- ~5% CPU usage instead of ~95%
- ~47 mutants in 5+ minutes instead of hundreds in 15 minutes
- Full codebase runs (4110 mutants) estimated at 12-15 hours instead of ~1 hour

### Expected Behavior

The timing statistics phase should produce mappings that allow targeted test runs per mutant.

---

## Reproduction Steps

```bash
# 1. Clean state
rm -rf mutants/ .mutmut-cache/

# 2. Verify project tests pass
uv run pytest  # 915 passed

# 3. Run mutation testing
uv run mutmut-win run --paths-to-mutate src/nextgen_cot_mcp_server/domain/errors.py --max-children 6

# 4. Output:
#   Running clean test suite…
#   Error: Clean test run failed with exit code 1.

# 5. Verify empty venv
mutants/.venv/Scripts/python -c "import pytest"
# ModuleNotFoundError: No module named 'pytest'
```

---

## Workaround

A wrapper script (`scripts/run_mutmut.py`) was created that:
1. Runs mutmut-win in a background thread
2. Continuously watches for `mutants/pyproject.toml` creation
3. Injects `[tool.uv.sources]` if missing
4. Copies `uv.lock` to `mutants/`

This partially works (clean test suite passes, mutations run) but:
- Test-to-mutant mappings are still missing (all tests run per mutant)
- CPU utilization remains at ~5% instead of ~95%
- Performance is 10-20x slower than in projects where mutmut-win works natively

---

## Project Configuration

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "nextgen-cot-mcp-server"
version = "0.1.0"
requires-python = ">=3.14"

[dependency-groups]
dev = [
    "pytest>=8.3",
    # ... 10 more dev deps ...
    "mutmut-win",
]

[tool.uv.sources]
mutmut-win = { git = "https://github.com/pgm1980/mutmut-win.git", rev = "v1.0.10" }

[tool.mutmut]
paths_to_mutate = ["src/nextgen_cot_mcp_server/"]
tests_dir = ["tests/"]
```

### Key Differences from Working Projects

| Factor | This Project | Working Projects |
|--------|-------------|-----------------|
| Build backend | hatchling | hatchling |
| Source layout | `src/` layout | `src/` layout |
| Git dependency | mutmut-win via `[tool.uv.sources]` | mutmut-win via `[tool.uv.sources]` |
| Test count | 915 | ~100-400 |
| Source files | 64 | ~15-30 |
| Python version | 3.14.3 | 3.14.3 |

The working projects appear to have fewer source files and tests. The issue may be related to project scale or to specific file patterns in this project.
