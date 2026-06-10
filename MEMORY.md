# mutmut-win — Project Memory

> Last refresh: 2026-06-11. Source of truth for sprint state is `.sprint/state.md`;
> source of truth for issues is the GitHub repo. This file is the human-readable
> at-a-glance snapshot.

## What it is
Windows-native Python mutation-testing tool. Port of upstream `mutmut 3.5.0`
adapted to Windows: native subprocess + Job Object orphan-protection, no POSIX
fork dependency, in-process pytest stats collection, libcst-based mutation
generation. Since v2.5.0: true infinite-loop detection (psutil-based
triple-check classifier with forensics + confidence) — no other mutation tool
on the market (Stryker, PIT, mutpy, cosmic-ray, cargo-mutants) has this.

- Python 3.12 – 3.14
- Stack: click (CLI), libcst (mutations), pydantic v2 (config), textual (TUI),
  coverage (coverage-guided), psutil (IL detection), SQLite (results),
  pytest (test runner).
- Distributed as `mutmut-win` on PyPI. Console script: `mutmut-win`.

## Where we are
- **Version**: **v2.5.1** released 2026-05-23 (hotfix on top of v2.5.0:
  psutil.Process instance caching for stable cpu_percent). Annotated tags
  `v2.5.0` + `v2.5.1` on `main`.
  [GitHub releases](https://github.com/pgm1980/mutmut-win/releases).
- **Sprint**: 26 — *Polish + True IL Detection* (closed with v2.5.0/v2.5.1).
  Sprints 23–26 all ran 2026-05-22/23 as a single wave; see
  `_docs/sprint backlogs/` for details.
- **GitHub Issues**: **0 open** — backlog fully cleared (verified 2026-06-11).
- **Tests**: 610 passed / 4 skipped (verified 2026-06-11,
  `uv run pytest --ignore=tests/e2e_projects`).
- **In flight**: nothing. Next sprint not yet planned.

## Open Decisions / Open Items
- **`--treat-timeout-as-kill` deprecation** — the Sprint-23 stopgap flag is
  superseded by true IL detection (v2.5.0). Deprecation explicitly deferred
  to Sprint 27+ (see sprint_26_backlog Out-of-Scope).
- **Hypothesis "shrink-storm" edge case** — pathological shrinking could be
  misclassified as infinite loop; threshold tuning only if observed in the
  wild (Sprint-26 Out-of-Scope decision).
- **`_bug_reporting/BUG_REPORT_9.md`** — uncommitted copy of the downstream
  critique-model-service living bug document (documents Bugs #1–#5 at
  v2.4.0 state). Decide: commit, move to gitignored `_issues/`, or delete.
- **Release cadence** — v2.2.0 → v2.5.1 shipped within two days
  (2026-05-22/23). Still no documented release policy; commit log + GitHub
  releases are the record.

## Architecture Cheatsheet
- `cli.py` / `browser.py` — UI layer (click + textual).
- `orchestrator.py` / `runner.py` / `mutant_diff.py` — coordination + execution.
- `config.py` / `models.py` / `constants.py` / `mutation.py` /
  `node_mutation.py` / `regex_mutation.py` / `trampoline.py` — domain layer.
- `process/` — Windows-specific subprocess + Job Object integration;
  `process/loop_monitor.py` (since v2.5.0) — `ProcessMonitor` sampling thread,
  pure `classify_samples()` triple-check classifier (CPU ≥ 70% AND output
  growth < 1 KB AND running_ratio ≥ 0.8 → `killed_by_infinite_loop`,
  exit code 38), `IlForensics`/`LoopClassification` Pydantic models.
- `db.py` — SQLite persistence (mutations, last_output, forensics JSON).
- `_state.py` — in-process globals populated by injected pytest plugin
  (`tests_by_mangled_function_name`, `current_test_name`,
  `record_trampoline_hit`).
- `import-linter` layers (in `pyproject.toml`):
  `cli|browser → orchestrator|runner|mutant_diff → config|models|constants|mutation|node_mutation|trampoline → process`.

## Recent History (one-liners)
- **Sprint 26 / v2.5.0 + v2.5.1** — true infinite-loop detection (#71:
  psutil ProcessMonitor + triple-check classifier + IlForensics persisted to
  DB, 5 new `[tool.mutmut]` keys, 2 new CLI flags), `--version` single source
  of truth via importlib.metadata (#72); hotfix v2.5.1 caches psutil.Process
  instances (fresh instances always returned cpu_percent 0.0).
- **Sprint 25 / v2.4.0** — final cleanup: `--extra-paths-to-copy` +
  `extra_paths` config for sibling packages (#69, downstream Bug #2),
  also_copy skips top-level venv/cache entries (#67, H-05), pytest-benchmark
  suite for mutation generation (#23).
- **Sprint 24 / v2.3.0** — Must-carryover cleanup: worker crash recovery
  (#12), full E2E pipeline validation on simple_lib + my_lib (#38, #49),
  deterministic Job Object kill-on-close test (#54), dogfooding expanded to
  full `src/mutmut_win/` (#65).
- **Sprint 23 / v2.2.0** — reliability wave for three downstream bugs: skip
  `or`-mutations on multi-line BooleanOperations (#68, Bug #1), skip
  default-parameter mutations (#70, Bug #3), `--treat-timeout-as-kill` flag
  (#71, Bug #5 stopgap).
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
- Filesystem ops: FS MCP server and Serena are **NOT available** for this
  project (FS MCP allowed-roots point elsewhere; Serena has no mutmut-win
  project registered — its memories belong to nextgen-cot-mcp-server).
  Use built-in tools (Read/Write/Edit/Glob/Grep); Bash file commands remain
  blocked by `.claude/settings.json`.
