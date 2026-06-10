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

# Sprint State (Refreshed 2026-06-11)

## Current Focus
Sprint 26 is **closed** — released as v2.5.0 plus hotfix v2.5.1 on 2026-05-23
(merge 73bc1a0, hotfix a14e320). No sprint is currently in progress; the next
sprint has not been planned yet. The repo sits on `main` with all quality
gates green (re-verified 2026-06-11: 610 passed / 4 skipped) and **0 open
GitHub issues**.

## Recently Completed (Sprints 23–26, all 2026-05-22/23)
- **Sprint 23 / v2.2.0 — Reliability Wave** (branch `fix/v2.2.0-reliability-wave`,
  merge 54e42e3): skip `or`-mutations on multi-line BooleanOperations (#68,
  downstream Bug #1), skip default-parameter mutations (#70, Bug #3),
  `--treat-timeout-as-kill` flag as Bug-#5 stopgap (#71). Gates: 578/3 skipped.
- **Sprint 24 / v2.3.0 — Must-Carryover** (branch `feature/v2.3.0-must-carryover`,
  merge c2a58c1): worker crash recovery (#12), full E2E pipeline validation on
  simple_lib + my_lib (#38/#49), deterministic Job Object kill-on-close test
  (#54), dogfooding expanded to full `src/mutmut_win/` (#65). Gates: 585/3.
- **Sprint 25 / v2.4.0 — Final Cleanup** (branch `feature/v2.4.0-final-cleanup`,
  merge f4c318b): also_copy skips top-level venv/cache entries (#67, H-05),
  `--extra-paths-to-copy` + `extra_paths` config for sibling packages (#69,
  Bug #2), pytest-benchmark suite for mutation generation (#23). Gates: 594/3.
- **Sprint 26 / v2.5.0 — Polish + True IL Detection** (branch
  `feature/v2.5.0-polish`, merge 73bc1a0): `--version` single source of truth
  via importlib.metadata (#72); true infinite-loop detection (#71 re-opened) —
  `process/loop_monitor.py` with psutil ProcessMonitor thread, triple-check
  classifier (CPU ≥ 70 % AND output growth < 1 KB AND running_ratio ≥ 0.8 →
  `killed_by_infinite_loop`, exit code 38), `IlForensics` persisted as JSON,
  5 new `[tool.mutmut]` keys, 2 new CLI flags, graceful degradation without
  psutil. Gates: 608/5, semgrep 0 findings (c478c93).
- **v2.5.1 hotfix** (a14e320): cache psutil.Process instances per pid —
  fresh instances always returned cpu_percent 0.0, breaking IL detection for
  the canonical child-process case.

## Sprint 26 Backlog (closed)
- [x] #72 `--version` via importlib.metadata with PackageNotFoundError
      fallback (34ea930).
- [x] #71 true IL detection: loop_monitor module, models/db/config/worker/cli
      integration, unit + integration + graceful-degradation tests (b5246d8).
- [x] Quality gates: pytest 608 passed / 5 skipped, ruff 0, mypy clean,
      semgrep 0 findings (c478c93).
- [x] Release: version bump 2.5.0 (3894805), annotated tags v2.5.0 + v2.5.1,
      GitHub releases, issues #71/#72 auto-closed via merge commit.

## Open Items
- **None on GitHub** — issue backlog fully cleared (verified 2026-06-11).
- Deferred decisions (not tracked as issues):
  - Deprecation of `--treat-timeout-as-kill` (superseded by true IL
    detection) — Sprint 27+ candidate.
  - Hypothesis "shrink-storm" misclassification edge case — threshold tuning
    only if observed in the wild (Sprint-26 out-of-scope decision).
  - `_bug_reporting/BUG_REPORT_9.md` lies uncommitted in the worktree
    (downstream living bug document, v2.4.0 state) — decide commit/move/delete.

## Housekeeping Notes
- 2026-06-11 documentation-drift pass: MEMORY.md, product_backlog.md (v1.1.0),
  this file and the sprint-23–26 backlog status fields were re-synced with
  reality; README test/feature facts refreshed. The frontmatter above was
  already correct — only document bodies had drifted (they still described
  Sprint 22 / v2.1.0).
- Epic numbering conflict resolved in product_backlog v1.1.0: sprint_23 and
  sprint_26 backlogs both claimed "Epic 16"; Sprint 23 keeps 16 (older),
  Sprint 26 is Epic 17.
- Branch policy unchanged: small fixes land on `main`, feature waves use
  `feature/<version>-*` branches with merge commits. The frontmatter `branch`
  field still names the *last* sprint branch (`feature/v2.5.0-polish`), which
  is why the SessionStart hook warns on `main` — expected until the next
  sprint opens and rewrites the frontmatter.
- Tooling note: FS MCP server and Serena are not available for this project
  (see MEMORY.md Conventions) — built-in tools are the documented fallback.
