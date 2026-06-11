---
current_sprint: "28"
sprint_goal: "v2.6.0 Source Protection & Codegen Correctness — W4.11-Downstream entblocken (BUG-1 + BUG-2), destruktive Audit-Funde (C1) eliminieren, Clean-Run-Brecher der Codegen-Schicht (C2) strukturell fixen."
branch: "feature/v2.6.0-source-protection"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 28 opened 2026-06-11)

## Current Focus
Sprint 28 — **v2.6.0 Source Protection & Codegen Correctness** — planned,
implementation not yet started. Basis: Sprint-27 audit
(`_docs/audit/sprint_27_audit_findings.md`), fix clusters C1 + C2 plus the
BUG-2 quick win from C4. Issues #73–#78 created on GitHub. Branch
`feature/v2.6.0-source-protection` exists.

## Sprint 28 Backlog (31 SP — Must 18, Should 13)
1. **#74 (Must, 2 SP):** BUG-2 — `clean_run_timeout` + `forced_fail_timeout`
   config fields, precise timeout error message (incl. setup.cfg fallback).
2. **#78 (Must, 3 SP):** Arm the safety net — validate-then-write in
   file_setup + crash guards (NM-007 inf-float, RX-001 OverflowError,
   MT-011 ǁ-identifier, NM-009 duplicate keyword). Ordered BEFORE the
   operator fixes so no invalid mutant can ever block a file again.
3. **#75 (Must, 5 SP):** Source protection — reject/relativize absolute
   paths_to_mutate; apply: class-aware lookup, backup, atomic write,
   newline preservation.
4. **#73 (Must, 8 SP):** Safe-unwrap helper for the parenless-yield class
   (NM-001…006) — closes downstream BUG-1.
5. **#77 (Should, 5 SP):** Mutants dict to module level (Enum/NamedTuple
   clean-run breakers MT-004/005).
6. **#76 (Should, 8 SP):** Wrapper codegen (hardcoded self, args/kwargs
   collisions, *args methods, async-gen protocol — MT-001/002/003/006).

Scope valve: #76/#77 slip to Sprint 29 on mid-sprint blowup; Must items
alone fully unblock the W4.11 downstream and remove everything destructive.

## New test asset (cross-item)
Adversarial fixture module from the audit verification snippets +
gate test: every generated mutant file must compile AND the fixture's
clean run must stay green (W4.11 reporter proposal §1.4).

## Out of scope (Sprint 29+)
C3 pool robustness (EW-001/002), C4 rest (timeout_multiplier semantics,
task.timeout_seconds wiring), C5 IL detection honesty (forensics
persistence/rendering, Windows realism), C6 dead features (type-checker
filter, coverage-guided), C7–C9. pip-audit baseline still outstanding
(environment SSL issue).

## Process reminders
- TDD per item: failing test first; commit per issue.
- Dogfooding gate: mutation testing on changed engine modules, score ≥ 80%.
- Release v2.6.0 at sprint end: merge to main, bump, tag, GitHub release
  with downstream note (genexp workaround §1.5 can be reverted).
