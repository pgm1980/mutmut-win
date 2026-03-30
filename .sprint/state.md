---
current_sprint: "14"
sprint_goal: "Regex-Mutationen — Alleinstellungsmerkmal (kein Python-Tool hat das)"
branch: "feature/55-regex-mutations"
started_at: "2026-03-30"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: false
semgrep_passed: false
tests_passed: false
documentation_updated: true
---

# Sprint State

## Current Focus
- Sprint 11: In-Process Stats + Trampoline Tracking — critical fix for correct test-per-mutant assignment

## Sprint Plan (v0.3.0)

### Sprint 11: In-Process Stats + Trampoline Tracking (Tier 1 Critical)
- [ ] `_state.py`: tests_by_mangled_function_name, current_test_name, reset_state(), record_trampoline_hit()
- [ ] `__main__.py`: re-export record_trampoline_hit + MutmutProgrammaticFailException
- [ ] `PytestRunner.run_stats()` rewrite: pytest.main() in-process with StatsCollector plugin
- [ ] `stats.py` update: collect_or_load_stats uses _state globals after run_stats()
- [ ] Orchestrator: real test assignment from stats data
- Issues: #39, #40, #41, #42, #43

### Sprint 12: Feature Completeness + E2E Validation (Tier 2)
- [ ] `guess_paths_to_mutate()` in config.py
- [ ] `ListAllTestsResult` + incremental stats in stats.py
- [ ] CLI commands: tests-for-mutant, time-estimates
- [ ] CI/CD stats export: save_cicd_stats + export-cicd-stats CLI
- [ ] Type-checker helpers: MutatedMethodsCollector, MutatedMethodLocation, FailedTypeCheckMutant, group_by_path
- [ ] Full E2E validation: mutmut-win run on simple_lib + my_lib, result comparison
- [ ] exceptions.py: MutmutProgrammaticFailException, BadTestExecutionCommandsException, InvalidGeneratedSyntaxException
- Issues: #44, #45, #46, #47, #48, #49, #50

## Context: 360° Cross-Check Gaps Found
- **Critical (F-02/F-03/F-09):** In-process stats (pytest.main()), trampoline hit tracking (_state), record_trampoline_hit re-export
- **Medium (F-01/F-04–F-08):** guess_paths_to_mutate, ListAllTestsResult, CLI commands, CI/CD stats export, type-checker helpers
