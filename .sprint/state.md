---
current_sprint: "26"
sprint_goal: "Polish + Bug #5 true infinite-loop detection — alleinige internationale Spitze in IL-detection (psutil + forensics + confidence). Release v2.5.0."
branch: "feature/v2.5.0-polish"
started_at: "2026-05-23"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Refreshed 2026-05-22)

## Current Focus
Post-release stabilization for v2.0.x. The advanced-operators waves
(Sprints 14–20) and the Hardening v1.0.0 wave (Sprint 21) have all merged
to main. Active work this sprint is the v2.0.x timeout-diagnostics series
and bug fixes that surfaced through dogfooding in downstream projects.

Sprint 22 closed with v2.1.0 release on 2026-05-22.

## Recently Completed (since the last state-of-record update)
- **Sprints 14–20** — all seven advanced mutation operators merged to main:
  Regex (#55), Math (#56), Return Value (#57), Conditional Expression (#58),
  Statement Removal (#59), Collection (#60), or-Default (#61).
- **Sprint 21 / Hardening v1.0.0** — Windows Job Object orphan-process
  protection (#51–#54), 10 CLI flags Tier 1-3 (#63), hook fixes (#64),
  worker import fix H-06 (#62).
- **v2.0.0 release** — test-to-mutant mapping via injected pytest plugin
  (`fe194c2`), replacing the older subprocess-based stats collection.
- **v1.0.x bug-fix wave** — repeated-run cache invalidation, WinError 32/206
  fixes, `.pth` shadowing, package-copy issues, `--dry-run` cache poisoning.
- **v2.0.x timeout diagnostics** — `subprocess.run` timeouts everywhere,
  `capture_output=True` → DEVNULL (pipe deadlock fix), temp-file capture
  replacing DEVNULL, `last_output` persisted to DB for post-mortem inspection.

## Sprint 22 Backlog
- [x] Merge [PR #66](https://github.com/pgm1980/mutmut-win/pull/66) — skip
      `typing.cast()` first-arg mutations (Bug #4 from critique-model-service).
      Merged 2026-05-22; 5 new tests; full suite 564 passed / 3 skipped.
- [x] Sprint-22 quality gates: pytest 564 passed / 3 skipped on `src/` +
      `tests/`; semgrep `--config auto` 0 findings on `src/` + `tests/unit/` +
      `tests/integration/` (2026-05-22).
- [x] Bump `pyproject.toml` to v2.1.0 and sync `uv.lock`; annotated tag
      `v2.1.0`; GitHub release `v2.1.0` published 2026-05-22.
- [x] Housekeeping: 42 stale GitHub issues closed, `.sprint/state.md`
      refreshed, `MEMORY.md` populated, persistent memory entries written.

## Open Items Carried Over (real OPEN issues on GitHub)
- **#12 Worker crash recovery** (PARTIAL) — detection works, recovery
  strategy missing. Originally Sprint 3 / Epic 3.
- **#23 Performance benchmark vs mutmut** (UNCLEAR) — no `benchmarks/`
  directory yet. Originally Sprint 6 / Epic 6.
- **#38 End-to-end validation test (full pipeline)** (UNCLEAR) —
  `tests/e2e_projects/` exists, harness unclear. Originally Sprint 10 /
  Epic 9.
- **#49 Sprint-12 full E2E** (UNCLEAR) — same as #38 but with explicit
  result-comparison against upstream mutmut. Originally Sprint 12 / Epic 11.
- **#54 Deterministic Job Object kill-on-close test** (UNCLEAR) —
  Sprint 13 / Epic 12 leftover.
- **#65 Dogfooding** (PARTIAL) — `[tool.mutmut] paths_to_mutate` narrowed
  to `regex_mutation.py`. Sprint 21 / Epic 14 leftover.
- **#67 H-05: also_copy .venv-Symlink review** (NEW) — filed retroactively
  during 2026-05-22 housekeeping; originally an untracked Sprint 21 task.

## Housekeeping Notes
- Sprint nomenclature: Sprint 21 = Hardening v1.0.0 per
  `_docs/product backlog/product_backlog.md`. This sprint took the next
  free number (22). The earlier housekeeping pass briefly mislabelled this
  as "Sprint 21" before the conflict was caught and corrected.
- `MEMORY.md` was empty before the 2026-05-22 housekeeping pass; it now
  contains the project snapshot.
- 42 GitHub issues that had been fully delivered between Sprints 11 and
  Sprint 21 were left open until the 2026-05-22 housekeeping pass.
- Backlog docs (`_docs/product backlog/product_backlog.md` and the three
  `_docs/sprint backlogs/sprint_*_backlog.md` files) were re-synced with
  reality in this sprint (status columns, velocity, milestones).
- Branch policy: v1.x/v2.x bug fixes and hook-debugging have landed
  directly on `main`. Larger feature waves used `feature/<issue>-*`
  branches with merge commits. Stick to that split going forward.
