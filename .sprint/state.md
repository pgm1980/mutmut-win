---
current_sprint: "29"
sprint_goal: "v2.7.0 Runtime Reliability — letzte 2 S1-Hänger (Abbruch-/Fehlerpfade) eliminieren, Timeout-Architektur end-to-end reparieren, Prozess-Hygiene, import-linter-Contracts per ADR scharf schalten."
branch: "feature/v2.7.0-runtime-reliability"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 29 opened 2026-06-11)

## Current Focus
Sprint 29 — **v2.7.0 Runtime Reliability** — planned, implementation not
started. Basis: audit clusters **C3 + C4** plus the Sprint-28 lint-imports
follow-up. After this sprint **all 15 S1 audit findings are closed**.
Issues #79–#84 created. Branch `feature/v2.7.0-runtime-reliability`.

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
