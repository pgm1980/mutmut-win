---
current_sprint: "28"
sprint_goal: "v2.6.0 Source Protection & Codegen Correctness — W4.11-Downstream entblocken (BUG-1 + BUG-2), destruktive Audit-Funde (C1) eliminieren, Clean-Run-Brecher der Codegen-Schicht (C2) strukturell fixen."
branch: "feature/v2.6.0-source-protection"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: true
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 28 — implementation complete 2026-06-11)

## Current Focus
All six Sprint-28 items are implemented and committed on
`feature/v2.6.0-source-protection` (31/31 SP, six TDD cycles):

| Issue | Commit | Delivered |
|-------|--------|-----------|
| #74 BUG-2 | bbe59d2 | clean_run_timeout + forced_fail_timeout config fields, precise timeout messages, setup.cfg fallback |
| #78 safety net | af7a431 | validate-then-write (contains the whole Bug-#68/BUG-1 class) + 4 operator crash guards |
| #75 source protection | 07b29fe | absolute-paths validator + write guard; apply: class-aware, byte-exact, backup, atomic, staleness check |
| #73 BUG-1 | 2a14182 | _safe_unwrap for 5 operators; Bug-#68 skip guard replaced by parenthesizing (MORE valid mutants) |
| #77 Enum/NamedTuple | 5dc8c48 | mutants dict emitted at module level after the class |
| #76 wrapper codegen | 5031032 | real first-param name, _mutmut_args/_mutmut_kwargs, *args forwarding, sync wrapper for async generators, __init_subclass__/__class_getitem__ in NEVER_MUTATE |

**Both W4.11 downstream blockers (BUG-1 + BUG-2) are closed.** The genexp
workaround (§1.5 marker comments) can be reverted downstream after release.

## Gates (sprint end, 2026-06-11)
- pytest: **672 passed / 4 skipped** (62 new tests; was 610 at sprint start)
- ruff: clean; mypy: 0 NEW errors (26 pre-existing audit-known)
- semgrep `--config auto src/ tests/unit/ tests/integration/`: 0 findings
- lint-imports: **pre-existing broken** (6 violations, identical on the
  sprint-start tree — verified against 015cf32; contracts have not matched
  code reality for sprints and the gate evidently never ran in sprints
  23–26). New audit follow-up → Sprint 29.
- mutation-testing dogfooding: deferred — empty test mapping (audit C8)
  forces full-suite-per-mutant runs; re-do after the C8 fixes. Compensated
  by the 62 targeted tests + the adversarial compile gate.

## Pending (needs user approval — outward-facing)
Release v2.6.0: bump pyproject+uv.lock, merge to main (auto-closes
#73–#78), annotated tag, push, GitHub release with downstream note.
`housekeeping_done`/`github_issues_closed` stay false until then.

## Out of scope (Sprint 29+ from the audit)
C3 pool robustness, C4 rest (timeout_multiplier semantics), C5 IL-detection
honesty, C6 dead features (type-checker filter, coverage), C7 score
integrity, C8 pipeline hygiene (incl. stats-mapping fixes that unblock the
dogfooding gate), lint-imports contract realignment, pip-audit baseline
(environment SSL issue).
