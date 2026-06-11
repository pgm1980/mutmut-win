---
current_sprint: "33"
sprint_goal: "v2.11.0 Maintenance 1: Runtime & Self-Run — Startup-Sockel im Timeout-Modell (DOG-001), no-tests-Producer (QX-007), Trampolin-Importkette entkoppeln (QX-001, Architektur-Skip fliegt); Ziel: Dogfooding-Pilot brutto >= 80 %."
branch: "feature/v2.11.0-maintenance-1"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: true
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 33 opened 2026-06-11)

## Current Focus
Sprint 33 — **v2.11.0 Maintenance 1: Runtime & Self-Run** —
**IMPLEMENTIERUNG KOMPLETT** (alle 6 Issues, 31/31 SP, Commits
`28a718f`..`4b87423`). **Messziel erreicht: Pilot 24,2 % → 86,9 %
brutto, 0 Timeouts statt 175** (Zwischengate + Abschluss identisch).
QX-001-Architektur-Skip entfernt — Layer-Gate lief grün im frischen
Artefakt. Maintenance-Pool 26 → 13. Gates: 868 passed, ruff/format 0,
mypy 0 neue, semgrep 0 (voller Sweep), lint-imports KEPT überall.
Release v2.11.0 wartet auf explizites User-„Release"
(Merge → Auto-Close #105–#110 → housekeeping_done).

## Sprint 33 Backlog (31 SP — Must 18, Should 13)
1. **#105 (Must, 5 SP):** DOG-001 — gemessener Startup-Sockel
   (clean_wall − Σdurations, geclamps, transparent); Design-CoT ≥8.
   Dogfooding bewies: 175/244 Pseudo-Timeouts mit fertiger Summary.
2. **#106 (Must, 5 SP):** QX-007 — no-tests-Producer; Designkern:
   tests=[] doppeldeutig (Vollsuite-Fallback bleibt für „keine Stats",
   exit 33 nur bei „gemappt-aber-leer"); à la #93 persistiert.
3. **#110 (Should, 3 SP):** QX-017/018 (max_stack_depth-0-Falle!),
   QX-019-Rest, DOG-002 (Hint pro Lauf).
4. **Zwischengate:** Pilot-Re-Run → brutto ≥ 80 % erwartet.
5. **#107 (Must, 8 SP):** QX-001+QX-020 — Trampolin-Hit-Recording in
   Kernel-Modul, Codegen-Zeile, BWC-Re-Export; Design-CoT ≥8;
   Beweisziel: Architektur-Skip-Marker ENTFERNT.
6. **#108 (Should, 5 SP):** UI-007 — Browser-Diff aus mutant_diff
   (Single Source), DB-Fallback-Namensform.
7. **#109 (Should, 5 SP):** UI-010/011/013/016 Robustheit.
8. **Abschluss:** Dogfooding-Lauf dokumentiert; Pool gepflegt.

Reihenfolge: 105 → 106 → 110 → Re-Run-Gate → 107 → 108 → 109 →
Abschluss-Lauf. Scope-Ventil: #108/#109/#110 zurück in den Pool;
v2.11.0 mit #105–#107 + Re-Run-Beleg release-fähig.

## Out of scope (bleibt im Maintenance-Pool, unversprochen)
RN-006/010/011/012/013, FD-008, QX-005/006/020-Rest/023-Rest,
UI-012/014/015, OS-012-Restgrenze (dokumentiert). pip-audit (Umgebungs-SSL).

## Sprint Context (auto-saved before compaction at 2026-06-11T16:44:02Z)

### Current Branch
feature/v2.11.0-maintenance-1

### Last 10 Commits
```
be6858b chore(sprint-33): open v2.11.0 maintenance-1 sprint
aabfdd7 docs(sprint-32): close sprint - v2.10.0 released, audit cycle ended
060ea16 chore: bump version to 2.10.0
95d0da1 merge: Sprint 32 v2.10.0 - Pipeline Hygiene (closes #98, #99, #100, #101, #102, #103, #104)
e8127da docs(sprint-32): implementation complete - gates recorded, docs synced
4d1e908 feat: dogfooding premiere - first complete self-run, score documented (closes #98)
3528022 docs: C9 remainder triage + audit cycle closure (closes #104)
06c9c6c test: isolate cwd in runner/worker tests - first dogfooding find (refs #98)
ebb1fd9 fix: CI output discipline - pure JSON stdout, emoji-safe encoding (closes #103)
c3fe810 fix: config/CLI truth - re-validated overrides, typo warnings, since-commit check, real --debug (closes #102)
```

### Recently Changed Files
```
.semgrepignore
.sprint/state.md
MEMORY.md
_docs/audit/sprint_27_audit_findings.md
_docs/product backlog/product_backlog.md
_docs/sprint backlogs/sprint_31_backlog.md
_docs/sprint backlogs/sprint_32_backlog.md
_docs/sprint backlogs/sprint_33_backlog.md
pyproject.toml
src/mutmut_win/cli.py
src/mutmut_win/config.py
src/mutmut_win/db.py
src/mutmut_win/file_setup.py
src/mutmut_win/models.py
src/mutmut_win/mutation.py
src/mutmut_win/orchestrator.py
src/mutmut_win/process/worker.py
src/mutmut_win/runner.py
src/mutmut_win/stats.py
tests/conftest.py
```
