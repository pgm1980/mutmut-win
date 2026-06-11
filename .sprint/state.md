---
current_sprint: "27"
sprint_goal: "Full Source Audit (analysis-only): alle src/mutmut_win/-Module in 4 Stages systematisch auf Bugs untersuchen (Engine, Process, Pipeline/Persistenz, UI/Querschnitt). Kein Bugfixing — Findings-Report als Increment."
branch: "main"
started_at: "2026-06-11"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 27 closed 2026-06-11)

## Current Focus
Sprint 27 — **Full Source Audit** — is **closed**. Deliverable:
`_docs/audit/sprint_27_audit_findings.md` with **201 raw / ~180 unique
findings (15 × S1)** across all 29 `src/mutmut_win/` modules, organized
into 9 fix clusters (C1–C9). No source changes were made
(analysis-only mandate). Next: user prioritizes fixing sprints (28+);
recommended order C1 (source-protection, destructive bugs) → C2
(codegen correctness) → C3/C4 (pool robustness / timeout architecture).

## Method & verification
12 read-only subagents over 4 stages; every S1/S2 suspicion verified
in-process; main session independently re-verified 12 top findings (all
confirmed; scripts under gitignored `_issues/`). Baselines: pytest
610 passed / 4 skipped; semgrep `--config auto src/` 0 findings;
pip-audit NOT obtained (SSL CERTIFICATE_VERIFY_FAILED towards pypi.org
in this environment — retry when cert chain works).

## Headline findings (full list in the audit doc)
- **Destructive (C1):** absolute `paths_to_mutate` overwrite original
  sources with trampoline code (A3-CM-001); `apply` patches the wrong
  function on cross-class name collisions (A4-UI-001).
- **Clean-run breakers (C2):** trampoline wrapper hardcodes `self`
  (A1-MT-001), `args`/`kwargs` local collisions (MT-002), mutants-dict
  becomes an Enum member (MT-004) / breaks NamedTuple (MT-005); the
  Bug-#68/BUG-1 "parenless yield" root pattern exists in 5 operators
  (NM-001…005).
- **Hangs (C3):** Ctrl+C/crash → interpreter-exit hang (EW-001,
  demonstrated); hard worker death → event loop hangs forever (EW-002) —
  the Sprint-24 #12 restart logic was never implemented (product_backlog
  AC corrected accordingly).
- **Timeout architecture broken thrice (C4):** `timeout_multiplier` used
  as absolute seconds (flat 60 s), computed per-task budgets never read,
  `WallClockTimeout` dead code (JT-003, found independently by 3 agents).
- **Flagship features hollow (C5/C6):** IlForensics never persisted
  (JT-004) and never rendered (UI-004); IL triple-check degenerates to a
  CPU-only check on Windows (JT-001/002); type-checker filter never
  matches (CM-002); coverage-guided mutation yields 0 mutants (CM-003).

## Known external issues (W4.11 downstream report, fix later)
- BUG-1: `operator_collection_neutralize` sole-genexp SyntaxError
  (verified; part of fix cluster C2).
- BUG-2: hard-coded `_RUNNER_TIMEOUT = 300` without config field
  (verified; part of fix cluster C4).

## Housekeeping
- Sprint-26 AC "results renders forensics" was never true (A4-UI-004) —
  flagged in audit doc; backlog statement stands corrected there.
- product_backlog Epic-3 AC for #12 corrected (restart logic not
  implemented — only in-worker except).
- pip-audit baseline outstanding (environment SSL issue), tracked in
  audit doc.
