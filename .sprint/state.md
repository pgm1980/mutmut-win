---
current_sprint: "33"
sprint_goal: "v2.11.0 Maintenance 1: Runtime & Self-Run — Startup-Sockel im Timeout-Modell (DOG-001), no-tests-Producer (QX-007), Trampolin-Importkette entkoppeln (QX-001, Architektur-Skip fliegt); Ziel: Dogfooding-Pilot brutto >= 80 %."
branch: "feature/v2.11.0-maintenance-1"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 33 opened 2026-06-11)

## Current Focus
Sprint 33 — **v2.11.0 Maintenance 1: Runtime & Self-Run** — geplant,
Implementierung noch nicht gestartet (wartet auf „Go"). Erster
bedarfsgetriebener Maintenance-Sprint nach dem Audit-Zyklus; Auswahl
aus dem Maintenance-Backlog nach Schaden/Nutzen, Pool-Rest (20)
unversprochen. Issues #105–#110. Branch `feature/v2.11.0-maintenance-1`.

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
