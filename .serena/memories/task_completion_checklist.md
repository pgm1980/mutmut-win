# Task Completion Checklist (v2.21.1 / Sprint 39 contract)

The supported release runtime is Windows with exactly CPython 3.14.7. Other
Python versions, implementations, and operating systems are not release gates.

Before declaring any task "done" (CLAUDE.md gates, harness hooks verify some of these):

Set `UV_PROJECT_ENVIRONMENT` to a fresh absolute directory outside the checkout
before every sync or gate below. Set `HYPOTHESIS_STORAGE_DIRECTORY` to a
separate absolute directory outside the checkout; Hypothesis 6.151.9 writes
cache bytes but no `.gitignore` of its own. The checkout must contain neither
`.venv`, tool-cache directories with their own `.gitignore`, nor `.hypothesis`
cache bytes.

1. `uv run --no-sync ruff check --no-cache .` → 0 findings;
   `uv run --no-sync ruff format --no-cache --check .` → no drift.
2. `uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/` →
   zero errors without reading or writing a checkout-local cache.
3. `uv run --no-sync pytest -q --cov=mutmut_win --cov-report=term-missing -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning` passes from the
   external project environment; no new skips, thread warnings or checkout-local
   cache controls.
4. `uv run --no-sync lint-imports --no-cache` → 0 violations (also runs without
   a checkout-local cache inside the suite via
   tests/test_architecture.py).
5. `uv sync --locked --only-group security --no-install-project`, then
   `uv run --no-sync python -I scripts/semgrep_release_gate.py` → canonical pinned,
   two-phase fail-closed gate over the full Git-owned release scope: isolated rule
   materialization followed by a content-verified offline bundle scan. Mandatory for
   security-relevant code and before every sprint/release close; zero unexpected
   findings, errors, skipped rules, or fixpoint timeouts. Exact documented allowlist
   signatures remain visible.
6. `uv sync --locked --only-group release --no-install-project`, then
   `uv run --no-sync python -I scripts/release_native_gate.py` → the exactly three
   manifest-bound native ZIP tools actionlint 1.7.12, ShellCheck 0.11.0, and
   Gitleaks 8.30.1 pass together with separately `uv.lock`-bound Zizmor 1.30.0
   offline under `--strict-collection --no-config --no-ignores` in both `regular`
   and `pedantic` personas. Git for Windows is resolved only from its system-wide
   HKLM installation contract, never caller PATH. Zizmor is not a fourth native manifest asset. The local bootstrap environment must be freshly locked/synced.
7. A complete locked dependency export is audited with pip-audit → no known
   vulnerabilities. Mandatory when dependencies change and before sprint close.
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
integrated final gates → reproducible double-build and installed-artifact smokes →
annotated tag `vX.Y.Z` → GitHub release with notes. NO PyPI publishing. A billing-
blocked CI run is `NOT_EXECUTED`, never PASS. Deprecations warn ≥ 1 minor release
before removal. Wheel- and sdist-smoke virtual environments must live beneath
`RUNNER_TEMP`, never in the release checkout.

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->
