# Task Completion Checklist (as of v2.21.0)

Before declaring any task "done" (CLAUDE.md gates, harness hooks verify some of these):

1. `uv run ruff check .` → 0 findings; `uv run ruff format .` → clean.
2. `uv run mypy src/ scripts/` → zero errors.
3. `uv run pytest` → all green; no new skips without documented reason.
4. Coverage measured when tests changed: `uv run pytest --cov=src`.
5. `uv run lint-imports` → 0 violations (also runs inside the suite via
   tests/test_architecture.py).
6. `uv sync --locked --only-group security --no-install-project`, then
   `uv run --no-sync python -I scripts/semgrep_release_gate.py` → canonical pinned,
   two-phase fail-closed gate over the full Git-owned release scope: isolated rule
   materialization followed by a content-verified offline bundle scan. Mandatory for
   security-relevant code and before every sprint/release close; only exact,
   documented allowlist signatures may adjudicate false positives.
7. `uv run pip-audit` → no known vulnerabilities. Mandatory when dependencies changed
   and before sprint close.
8. Mutation testing on new/changed modules:
   `uv run mutmut-win run --paths-to-mutate <module> …` → score >= 80 %;
   below that, document the surviving mutants.
9. Docs updated when behavior/CLI/config changed: README.md, docstrings,
   relevant _docs/ documents.
10. Git hygiene: work on a feature branch (`feature/[ISSUE-NR]-…`), NEVER directly on
    main; Conventional Commit messages.
11. Sprint hygiene (`.sprint/state.md` YAML frontmatter): set tests_passed,
    semgrep_passed, documentation_updated, … truthfully; sprint backlog doc in
    `_docs/sprint backlogs/`; close GitHub issues; update MEMORY.md;
    only then `housekeeping_done: true`.

## Release (separate, explicit)
Only on an explicit maintainer "Release" decision, after ALL gates above plus the
dogfooding pilot: version bump on the release branch → final gates → merge to main →
annotated tag `vX.Y.Z` → GitHub release with notes. NO PyPI publishing. Deprecations
warn ≥ 1 minor release before removal.
