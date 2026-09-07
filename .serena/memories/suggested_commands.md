# Suggested Commands (v2.21.1 / Sprint 39 contract)

Release evidence is collected only on Windows with exactly CPython 3.14.7.

## Setup
- `uv sync --locked --all-extras --all-groups --no-build-isolation` — install the
  complete locked development environment.

## Run the tool
- `uv run mutmut-win <subcommand>` — canonical entry point.
- `uv run python -m mutmut_win` — also works (thin wrapper).
- Subcommands: run, results, show, apply, browse, tests-for-mutant, time-estimates,
  export-cicd-stats. There is NO `html` report command (that was upstream mutmut).

## Testing
- `uv run pytest` — full suite: unit + integration + architecture.
- `uv run pytest tests/unit/` | `tests/integration/` — partial runs.
- `uv run pytest -m "not slow"` — skip long-running tests.
- `uv run pytest --cov=src --cov-report=html` — coverage (pytest alone measures none).
- `uv run pytest --benchmark-only` — benchmarks only.

## Lint / Types / Architecture / Security
- `uv run ruff check .` (+ `--fix`) — lint; `uv run ruff format .` — format.
- `uv run mypy src/ scripts/` — strict, zero-error gate.
- `uv run lint-imports` — layer contracts (also enforced in the test suite).
- `uv sync --locked --only-group security --no-install-project` followed by
  `uv run --no-sync python -I scripts/semgrep_release_gate.py` — canonical pinned,
  two-phase fail-closed gate over the full Git-owned release scope: isolated rule
  materialization followed by a content-verified offline bundle scan.
- `uv sync --locked --only-group release --no-install-project` followed by
  `uv run --no-sync python -I scripts/release_native_gate.py` — canonical wrapper
  for the exactly three manifest-bound native ZIP tools actionlint 1.7.12,
  ShellCheck 0.11.0, and Gitleaks 8.30.1 plus separately `uv.lock`-bound
  Zizmor 1.30.0 offline with `--strict-collection --no-config --no-ignores` in
  both `regular` and `pedantic` personas. Git for Windows comes from the
  system-wide HKLM installation contract rather than caller PATH. Zizmor is not a fourth native manifest asset; use a freshly locked/synced bootstrap environment.
- Export the complete locked dependency set, then run pip-audit against that exact
  export — dependency vulnerability audit.

## Mutation testing (dogfooding — the tool tests itself)
- `uv run mutmut-win run --paths-to-mutate src/mutmut_win/<module>.py` — targeted;
  the flag is REPEATABLE (one path per flag), required gate for new/changed code.
- `uv run mutmut-win run --since-commit HEAD~1` — incremental.
- `uv run mutmut-win results` | `show <mutant>` | `browse` — inspect outcomes.
- `uv run mutmut-win run --force …` — clean slate (deletes mutants/ + .mutmut-cache/).
- `--rerun-all` — opt out of result reuse; `--dry-run` — count only;
  `--output json --no-progress --min-score N` — CI mode.
- Exit codes of `run`: 0 ok · 1 runtime failure or min-score gate · 2 invalid
  config/option · 130 interrupted (partial results persisted, no score gate).
- Mutant names: `src.pkg.module.x_<func>__mutmut_<n>`; glob patterns allowed
  (`run`/`time-estimates` accept many matches, `show`/`apply` exactly one).

## Git / GitHub
- GitHub Flow; Conventional Commits (`type(scope): description`); branches
  `feature/[ISSUE-NR]-kurzbeschreibung`; annotated SemVer tags `vX.Y.Z`; `gh` CLI for
  GitHub operations.
- Publish only an annotated Git tag plus matching GitHub-release artifacts;
  PyPI publishing is outside the product and release contract.

## Session tooling policy (from CLAUDE.md, harness-enforced)
- FS MCP server (`execute_workflow`) for filesystem operations; Serena for code
  navigation (activate by project NAME `mutmut-win`, not by Windows path); Context7
  before using new/changed APIs.
- Filesystem bash commands (cat, ls, grep, find, cp, mv, rm, mkdir, sed, awk, …) are
  hard-blocked via `.claude/settings.json`. Bash stays allowed for `uv run …`, `git`
  and `gh`; Semgrep gate authority belongs only to the canonical wrapper above.
- FS MCP allowed directories cover the project tree only (not user-profile paths).
