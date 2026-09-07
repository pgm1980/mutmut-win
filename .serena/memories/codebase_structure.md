# Codebase Structure & Layer Architecture (v2.21.1 / Sprint 39)

> Active structural overview for the Windows/exact-CPython-3.14.7 release
> contract. Source files and import-linter contracts are authoritative; volatile
> LOC, module-size, file-count, and suite-count snapshots are intentionally
> omitted.

## Five-band layer architecture
Enforced TWICE: import-linter contracts in pyproject.toml ("Layer architecture
(ADR layer contracts v2)"; rationale in `_docs/architecture spec/adr_layer_contracts_v2.md`,
issue #84) AND inside the test suite — `tests/test_architecture.py` runs the real
import-linter gate plus layer-isolation tests. Never "fix" a violation by editing contracts.

Bands (high → low; `:` = intentionally collaborating siblings):
1. `cli : browser`
2. `orchestrator : runner : stats : mutant_diff`
3. `file_setup : mutation : node_mutation : regex_mutation : trampoline : test_mapping : db : type_checking : type_checker_filter : code_coverage`
4. `process`
5. `config : models : constants : exceptions : _state : hit_recording`

## Key modules
- **orchestrator.py** — heart of the pipeline. `MutationOrchestrator` (methods:
  run, dry_run, _generate_mutants, _maybe_purge_stale, _gather_coverage, …) plus module
  functions: _compute_startup_floor, _apply_timeouts, _assign_tests_to_tasks,
  _filter_with_type_checker, _build_tests_fingerprints / _split_reusable_tasks (v2.13
  result reuse), _split_no_test_tasks, _persist_skipped_mutants, _print_summary.
- **cli.py** — click CLI; commands: run, results, show, apply, browse,
  tests_for_mutant_cmd, time_estimates_cmd, export_cicd_stats_cmd.
- **file_setup.py** — mutants/ staging (mirrors whole project root minus skip
  list), fingerprinting, writing mutated files, sys.path handling.
- **node_mutation.py** — profile-tagged mutation-operator registry; the current
  registry and its regression tests define the authoritative operator surface.
- **mutation.py** — libcst MutationVisitor, combines operators, generates
  trampolines per function, merges mutants into one staged file.
- **runner.py** — pytest subprocess wrapper: clean run, stats run, forced-fail,
  coverage bridge.
- **process/** — worker loop and per-task pytest subprocess, spawn executor,
  Windows Job Object containment, output capture, generation supervision, run
  locking, suspended/atomic launch, and loop classification.
- **stats.py** — per-test timing + trampoline hit map persistence
  (mutants/mutmut-stats.json), CI stats export.
- **config.py** — pydantic config from `[tool.mutmut]` in pyproject.toml,
  CLI-flag overrides, validation (unknown keys → did-you-mean warning).
- **mutant_diff.py** — show/apply: unified diff, atomic apply with backup +
  staleness check (StaleStagingError).
- **browser.py** — textual TUI result browser.
- **db.py** — SQLite result cache.
- Foundation: models.py (pydantic domain models), constants.py (exit codes, statuses),
  exceptions.py, _state.py (trampoline global state), hit_recording.py (trampoline hit
  kernel; moved here from __main__ in v2.11, BWC re-exports remain in __main__.py).

## Tests
- `tests/unit/` and `tests/integration/` — unit, boundary, E2E-pipeline,
  process-lifecycle, supply-chain, and type-check coverage.
- `tests/e2e_projects/` — fixture projects (simple_lib, my_lib, config,
  mutate_only_covered_lines, py3_14_features, type_checking, stress_test). EXCLUDED
  from pytest collection (tests/conftest.py: collect_ignore_glob, issue #98) and from
  ruff (pyproject exclude) — upstream-style fixtures, not subject to project lint rules.
- `tests/test_architecture.py` — real import-linter gate + layer isolation.
- `benchmarks/` — pytest-benchmark (mutation generation throughput).

## Docs & process files
- `_docs/` — architecture spec (+ ADRs), design specs, historical sprint backlogs
  plus the active Sprint-39 backlog, `audit/` review archives, product backlog, and
  the maintained installation guide (Git-tag/GitHub-release channel; no PyPI
  publishing).
- `_config/` — development_process.md (Scrum process), fs_mcp_server.md (FS MCP policy).
- `.sprint/state.md` — YAML-frontmatter sprint state driving the `.claude/hooks/` chain
  (sprint-health, sprint-gate, verify-after-agent, statusline, …).
- `CLAUDE.md` — binding tool directives (German).
- GitHub Actions defines Windows/CPython-3.14.7 quality, security, test, audit,
  build, and installed-artifact jobs. Local gates remain authoritative when a new
  workflow cannot start for billing reasons; that remote state is `NOT_EXECUTED`,
  never PASS.
- Generated/ignored at root: mutants/, .mutmut-cache/, .benchmarks/, .hypothesis/.
