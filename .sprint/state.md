---
current_sprint: "29"
sprint_goal: "v2.7.0 Runtime Reliability — letzte 2 S1-Hänger (Abbruch-/Fehlerpfade) eliminieren, Timeout-Architektur end-to-end reparieren, Prozess-Hygiene, import-linter-Contracts per ADR scharf schalten."
branch: "feature/v2.7.0-runtime-reliability"
started_at: "2026-06-11"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 29 — CLOSED with v2.7.0 release 2026-06-11)

## Current Focus
Sprint 29 — **v2.7.0 Runtime Reliability** — all six items implemented
and committed (27/27 SP). **All 15 S1 audit findings are now closed.**

| Issue | Commit | Delivered |
|-------|--------|-----------|
| #79 shutdown hang | 4257f3c | queues cancel_join_thread+close, graceful-join-then-kill, idempotent shutdown, orchestrator finally |
| #80 worker liveness | 0a06b3d | poll+sweep protocol, synthetic completions, late-flush single-count, all-dead abort, no 'unknown' DB rows |
| #83 job-object polish | c781d62/3b9512e | use_last_error, argtypes/restype, least-privilege mask (parallel worktree subagent, verified by main session) |
| #82 process hygiene | a2f6037 | per-task kill-on-close job (design upgrade: ppid scans cannot bridge dead intermediates — empirically shown), startup artifact sweep, sys.executable worker |
| #81 timeout architecture | a955b89 | worker enforces task.timeout_seconds; dead WallClockTimeout/TaskTimedOut REMOVED (−464 lines); IL window wired; tail-read logs; README architecture fixed |
| #84 lint-imports ADR | 243206a | five-band contract (shared kernel below process), KEPT 0 broken, gate now runs inside pytest |

Gates: 681 passed / 4 skipped; ruff clean; mypy 0 new (26 known);
semgrep 0 findings; lint-imports KEPT and self-enforcing via the suite.

## Released
v2.7.0 published 2026-06-11 (merge 7ef982f, bump d46f4db, tag v2.7.0,
https://github.com/pgm1980/mutmut-win/releases/tag/v2.7.0); issues
#79–#84 auto-closed, verified 0 open. Next: Sprint 30 = audit cluster
C5 (IL detection honesty, v2.8.0) per the remainder roadmap.

## Findings bookkeeping
Audit total ~180 unique; Sprint 28 closed 22 (incl. 13/15 S1); ~158 remain.
This sprint takes ~17 (C3+C4, incl. the last 2 S1). Remainder roadmap is
fixed in product_backlog: Sprint 30 = C5 (v2.8.0, IL detection honesty),
Sprint 31 = C6+C7 (v2.9.0, dead features + score integrity), Sprint 32 =
C8+C9-top (v2.10.0, pipeline hygiene — re-enables the dogfooding gate).
Unassigned S4 noise stays in the audit register, fixed opportunistically.

## Sprint 29 Backlog (27 SP — Must 21, Should 6)
1. **#79 (Must, 3 SP):** shutdown hang — close/cancel_join_thread on both
   queues, try/finally around the orchestrator event loop (EW-001 S1,
   EW-017).
2. **#80 (Must, 5 SP):** worker liveness in get_events — timeout+is_alive
   sweep, synthetic completion for dead workers' tasks, no more "unknown"
   DB rows (EW-002 S1, EW-012). Stretch: one respawn per slot.
3. **#82 (Must, 5 SP):** process hygiene — kill-tree early-return fix,
   startup sweep for stale logs/argfiles, worker via sys.executable
   (EW-007/008, QX-008).
4. **#81 (Must, 8 SP):** per-task timeouts end-to-end — worker reads
   task.timeout_seconds, multiplier truly multiplies, REMOVE dead
   WallClockTimeout/TaskTimedOut, pass IL window/poll through, tail-read
   logs, fix README architecture section (JT-003, EW-009/013/014).
5. **#83 (Should, 3 SP):** job-object polish — use_last_error, argtypes,
   least-privilege mask, assign-race documentation (JT-005/006/017).
6. **#84 (Should, 3 SP):** import-linter contract realignment via ADR
   (sequential-thinking ≥10 steps), ':'-siblings + base layer, gate
   actually runs at sprint close.

Scope valve: #83/#84 slip to Sprint 30 on blowup.

## Test strategy note (C3 is multi-process)
Hang regressions need real pool runs: integration tests with %TEMP%
sandboxes, hard outer watchdog timeouts (regression = test FAIL, not CI
hang), and real worker kills via taskkill.

## Design decisions fixed at planning time
- #81: worker-side proc.wait(timeout) IS the architecture; the dead
  monitor gets deleted, not wired (3 documented landmines).
- #84 is ADR-mandatory per CLAUDE.md.
