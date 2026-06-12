# Codebase Structure & Layer Architecture (as of v2.13.0, 2026-06-12)

~9.7k LOC across 29 modules in `src/mutmut_win/` (one subpackage: `process/`).

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

## Key modules (approx. sizes)
- **orchestrator.py** (~1360) — heart of the pipeline. `MutationOrchestrator` (methods:
  run, dry_run, _generate_mutants, _maybe_purge_stale, _gather_coverage, …) plus module
  functions: _compute_startup_floor, _apply_timeouts, _assign_tests_to_tasks,
  _filter_with_type_checker, _build_tests_fingerprints / _split_reusable_tasks (v2.13
  result reuse), _split_no_test_tasks, _persist_skipped_mutants, _print_summary.
- **cli.py** (~710) — click CLI; commands: run, results, show, apply, browse,
  tests_for_mutant_cmd, time_estimates_cmd, export_cicd_stats_cmd.
- **file_setup.py** (~700) — mutants/ staging (mirrors whole project root minus skip
  list), fingerprinting, writing mutated files, sys.path handling.
- **node_mutation.py** (~680) — the mutation operators (22 upstream + 7 own).
- **mutation.py** (~615) — libcst MutationVisitor, combines operators, generates
  trampolines per function, merges mutants into one staged file.
- **runner.py** (~540) — pytest subprocess wrapper: clean run, stats run, forced-fail,
  coverage bridge.
- **process/** — worker.py (~555, worker loop + per-task pytest subprocess + IL
  classification), executor.py (~295, spawn pool, two queues task/event),
  job_object.py (~210, Windows Job Object API), loop_monitor.py (~515, sampling
  classifier: CPU/output/status evidence → verdict + confidence + forensics).
- **stats.py** (~445) — per-test timing + trampoline hit map persistence
  (mutants/mutmut-stats.json), CI stats export.
- **config.py** (~490) — pydantic config from `[tool.mutmut]` in pyproject.toml,
  CLI-flag overrides, validation (unknown keys → did-you-mean warning).
- **mutant_diff.py** (~430) — show/apply: unified diff, atomic apply with backup +
  staleness check (StaleStagingError).
- **browser.py** (~450) — textual TUI result browser.
- **db.py** (~230) — SQLite result cache.
- Foundation: models.py (pydantic domain models), constants.py (exit codes, statuses),
  exceptions.py, _state.py (trampoline global state), hit_recording.py (trampoline hit
  kernel; moved here from __main__ in v2.11, BWC re-exports remain in __main__.py).

## Tests
- `tests/unit/` (~73 files), `tests/integration/` (~10 files, e2e pipeline validation,
  pool shutdown, type-check e2e).
- `tests/e2e_projects/` — fixture projects (simple_lib, my_lib, config,
  mutate_only_covered_lines, py3_14_features, type_checking, stress_test). EXCLUDED
  from pytest collection (tests/conftest.py: collect_ignore_glob, issue #98) and from
  ruff (pyproject exclude) — upstream-style fixtures, not subject to project lint rules.
- `tests/test_architecture.py` — real import-linter gate + layer isolation.
- `benchmarks/` — pytest-benchmark (mutation generation throughput).
- Suite size @ v2.13.0: 1016 passed / 5 skipped.

## Docs & process files
- `_docs/` — architecture spec (+ ADRs), design specs, `sprint backlogs/` (sprints
  14–35), `audit/` (external_qa_report_v2.12.0.md = QA archive), product backlog,
  mutmut-win-install.md (git-tag install channel).
- `_config/` — development_process.md (Scrum process), fs_mcp_server.md (FS MCP policy).
- `.sprint/state.md` — YAML-frontmatter sprint state driving the `.claude/hooks/` chain
  (sprint-health, sprint-gate, verify-after-agent, statusline, …).
- `CLAUDE.md` — binding tool directives (German).
- No GitHub Actions CI — quality gates run locally (hooks + release gates).
- Generated/ignored at root: mutants/, .mutmut-cache/, .benchmarks/, .hypothesis/.
