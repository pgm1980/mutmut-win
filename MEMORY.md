# mutmut-win — Project Memory

> Last refresh: 2026-05-22. Source of truth for sprint state is `.sprint/state.md`;
> source of truth for issues is the GitHub repo. This file is the human-readable
> at-a-glance snapshot.

## What it is
Windows-native Python mutation-testing tool. Port of upstream `mutmut 3.5.0`
adapted to Windows: native subprocess + Job Object orphan-protection, no POSIX
fork dependency, in-process pytest stats collection, libcst-based mutation
generation.

- Python 3.12 – 3.14
- Stack: click (CLI), libcst (mutations), pydantic v2 (config), textual (TUI),
  coverage (coverage-guided), SQLite (results), pytest (test runner).
- Distributed as `mutmut-win` on PyPI. Console script: `mutmut-win`.

## Where we are
- **Version**: **v2.1.0** released 2026-05-22. `pyproject.toml` and `uv.lock`
  both at v2.1.0; annotated tag `v2.1.0` on `main` (`8685f93`).
  [GitHub release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.1.0).
- **Sprint**: 22 — *v2.0.x Stabilization* (closed with v2.1.0). Sprint 21
  was Hardening v1.0.0 per `_docs/product backlog/product_backlog.md`. See
  `.sprint/state.md` for the detailed backlog.
- **In flight**: nothing — Sprint 22 is closed. Next sprint will pick from
  the carryover below.

## Open Decisions / Open Items
- **#12 Worker crash recovery** — detection works, full recovery strategy
  still to be defined. Sprint 3 carryover, Must priority.
- **#23 Performance benchmarks** — `benchmarks/` directory not created yet.
  Decision needed: which workload to benchmark against upstream `mutmut`.
- **#38 / #49 E2E validation** — `tests/e2e_projects/` exists (5 fixture
  projects), but no comparison-harness that runs `mutmut-win run` and checks
  the result table against a frozen baseline. Sprint 10/12 carryover.
- **#54 Job Object kill-on-close test** — deterministic test missing.
  Sprint 13 carryover.
- **#65 Dogfooding** — `[tool.mutmut] paths_to_mutate` is currently narrowed
  to `regex_mutation.py` only. Decision needed: expand to full
  `src/mutmut_win/` and accept the runtime cost, or keep narrow and document.
- **#67 H-05 also_copy .venv-Symlink review** — filed retroactively in the
  2026-05-22 housekeeping pass; verify `copy_also_copy_files()` behaviour on
  inputs that contain or point at a `.venv` directory.
- **Release cadence** — last several releases bumped patch and minor
  versions rapidly (1.0.10 → 2.0.0 → 2.1.0 across ~7 weeks). No documented
  release policy; commit log + GitHub releases (now caught up through
  v2.1.0) are the record.

## Architecture Cheatsheet
- `cli.py` / `browser.py` — UI layer (click + textual).
- `orchestrator.py` / `runner.py` / `mutant_diff.py` — coordination + execution.
- `config.py` / `models.py` / `constants.py` / `mutation.py` /
  `node_mutation.py` / `regex_mutation.py` / `trampoline.py` — domain layer.
- `process/` — Windows-specific subprocess + Job Object integration.
- `db.py` — SQLite persistence (mutations + last_output for diagnostics).
- `_state.py` — in-process globals populated by injected pytest plugin
  (`tests_by_mangled_function_name`, `current_test_name`,
  `record_trampoline_hit`).
- `import-linter` layers (in `pyproject.toml`):
  `cli|browser → orchestrator|runner|mutant_diff → config|models|constants|mutation|node_mutation|trampoline → process`.

## Recent History (one-liners)
- **Sprint 22 / v2.1.0** — Bug #4 typing.cast() skip (PR #66), housekeeping
  (42 stale issues closed, MEMORY.md+state.md+backlogs synced), v2.1.0 tag
  and consolidated GitHub release covering everything since v1.0.7.
- **v2.0.x** — Timeout diagnostics: subprocess timeouts, DEVNULL fix,
  temp-file capture, DB-persisted `last_output`.
- **v2.0.0** — Test-to-mutant mapping via injected pytest plugin
  (`fe194c2`).
- **v1.0.x** — Cache-invalidation fixes, WinError 32/206 fixes, `.pth`
  shadow, package copy.
- **Sprint 21 / Hardening v1.0.0** — Job Objects (#52–#54), 10 CLI flags
  (#63), hook fixes H-01–H-07 (#64), worker import fix H-06 (#62).
- **Sprints 14–20** — seven advanced operators merged (Regex, Math,
  Return, Conditional, Statement Removal, Collection, or-Default).

## Conventions Reminders
- Tooling: `uv` only (not `pip`). `uv run <tool>` for everything.
- Lint: Ruff (no black/flake8/isort/pylint in parallel).
- Type-check: mypy strict.
- Test: pytest + hypothesis + pytest-benchmark + pytest-cov.
- Mutation testing: `uv run mutmut-win run --paths-to-mutate <dir>`.
- Security: Semgrep before every sprint close, pip-audit on dependency
  changes.
- Filesystem ops: FS MCP server (`execute_workflow`); Bash file commands
  blocked by `.claude/settings.json`.
