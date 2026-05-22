---
current_sprint: "21"
sprint_goal: "v2.0.x Stabilization — Timeout Diagnostics, Dogfooding & Bug Fixes (post v2.0 release)"
branch: "main"
started_at: "2026-04-10"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: false
---

# Sprint State (Refreshed 2026-05-22)

## Current Focus
Post-release stabilization for v2.0.x. The advanced-operators / hardening waves
(Sprints 14–20 + Hardening Sprint) have all merged to main. Active work is the
v2.0.x timeout-diagnostics series and bug fixes that surfaced through dogfooding
in downstream projects.

## Recently Completed (since the last state-of-record update)
- **Sprints 14–20** — all seven advanced mutation operators merged to main:
  Regex (#55), Math (#56), Return Value (#57), Conditional Expression (#58),
  Statement Removal (#59), Collection (#60), or-Default (#61).
- **Hardening Sprint** — Windows Job Object orphan-process protection (#52–#54),
  10 CLI flags Tier 1-3 (#63).
- **v2.0.0 release** — test-to-mutant mapping via injected pytest plugin (`fe194c2`),
  replacing the older subprocess-based stats collection.
- **v1.0.x bug-fix wave** — repeated-run cache invalidation, WinError 32/206 fixes,
  `.pth` shadowing, package-copy issues, `--dry-run` cache poisoning.
- **Hook fixes H-01 – H-07** — corrected matcher regex semantics, `if`-filter
  placement inside hook object, dual-output `systemMessage` for user visibility.
- **v2.0.x timeout diagnostics** — `subprocess.run` timeouts everywhere,
  `capture_output=True` → DEVNULL (pipe deadlock fix), temp-file capture replacing
  DEVNULL, `last_output` persisted to DB for post-mortem inspection.

## Sprint 21 Backlog
- [x] Merge [PR #66](https://github.com/pgm1980/mutmut-win/pull/66) — skip
      `typing.cast()` first-arg mutations (Bug #4 from critique-model-service).
      Merged 2026-05-22; 5 new tests; full suite 564 passed / 3 skipped.
- [x] Sprint-21 quality gates: pytest 564 passed / 3 skipped on `src/` +
      `tests/`; semgrep `--config auto` 0 findings on `src/` + `tests/unit/` +
      `tests/integration/` (2026-05-22).
- [ ] Issue #65 — full dogfooding: extend `[tool.mutmut] paths_to_mutate` beyond
      `regex_mutation.py` and reach a green run on the whole src tree.
- [ ] Issue #12 — worker crash recovery beyond detection (define and implement
      recovery strategy).
- [ ] Issue #23 — performance benchmarks vs upstream mutmut (create `benchmarks/`
      with pytest-benchmark suite).
- [ ] Issues #38 / #49 — end-to-end validation pipeline on
      `tests/e2e_projects/simple_lib` + `my_lib` with result-comparison harness.
- [ ] Issue #54 — deterministic test for Job Object kill-on-close behaviour.
- [ ] Bump `pyproject.toml` to v2.0.5 and sync `uv.lock` (next release packaging).

## Housekeeping Notes
- Sprint nomenclature continues the linear numbering from the v0.3.0 era for
  historical traceability — the project is on v2.0.x, sprint 21 is the next
  unused integer.
- `MEMORY.md` was empty before this session; it now indexes the
  `memory/` folder.
- 40 GitHub issues that had been fully delivered between Sprints 11 and the
  Hardening wave were left open. They were verified against the v2.0.4
  codebase and closed in this housekeeping pass.
- Branch policy: the v1.x/v2.x bug-fix and hook-debugging history shows that
  small fixes have been landing directly on `main`. Larger feature work
  (advanced operators, hardening) used `feature/<issue>-*` branches and merge
  commits. Stick to that split going forward.

## Open Items Carried Over
- #12 Worker crash recovery (PARTIAL)
- #23 Performance benchmark vs mutmut (UNCLEAR — no benchmarks/ yet)
- #38 End-to-end validation test (UNCLEAR — e2e_projects exist, harness unclear)
- #49 Sprint-12 full E2E (UNCLEAR — same as #38)
- #54 Deterministic Job Object kill-on-close test (UNCLEAR)
- #65 Dogfooding (PARTIAL — config narrowed to one module)
