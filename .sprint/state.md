---
current_sprint: "34"
sprint_goal: "v2.12.0 Maintenance 2: Final Sweep — kompletter Pool-Rest (13 Einträge, #111–#117) + MEMORY-Entscheidungsregister; danach Entwicklungspause. Messziel: Pilot brutto >= 80 % halten."
branch: "feature/v2.12.0-maintenance-2"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 34 opened 2026-06-11)

## Current Focus
Sprint 34 — **v2.12.0 Maintenance 2: Final Sweep** — der LETZTE Sprint
vor der geplanten Entwicklungspause (User-Auftrag: alle offenen Topics).
Inhalt: vollständiger Maintenance-Pool (13 Einträge → 0) + alle 4
offenen MEMORY-Entscheidungen. 7 Issues (#111–#117, 27 SP), Reihenfolge
111 → 112 → 113 → 114 → 115 → 116 → 117 → Doppel-Dogfooding
(Pilot-Gate ≥ 80 % + informativer --since-commit-Lauf).
KEIN Auswahl-Ventil: unverhältnismäßige Items werden dokumentierte
Won't-Fix-Entscheidungen, nichts bleibt still liegen.
Release v2.12.0 nur auf explizites User-„Release"; danach Pausenzustand
in MEMORY.md/state.md/Release Notes dokumentieren.

## Sprint 34 Backlog (27 SP — Must 19, Should 8)
1. **#111 (Must, 5 SP):** RN-006+RN-012 — Forced-Fail-Wahrheit
   (-x, Timeout ≠ Erfolg, Marker-Attribution); PY_IGNORE_IMPORTMISMATCH
   in allen 4 Phasen.
2. **#112 (Must, 3 SP):** RN-013 — shlex-Koerzierung beider
   pytest_add_cli_args-Felder (str+list).
3. **#113 (Must, 3 SP):** FD-008 — Sanitiser: [tool.uv.sources.<pkg>]-
   Subtables.
4. **#114 (Must, 5 SP):** QX-005/006/023-Rest — Exception-Hygiene;
   mypy-Baseline darf nur sinken.
5. **#115 (Should, 5 SP):** UI-012/014/015 — Resolver (exakt+Glob,
   dokumentiert), patch-fähige Diffs, Alignment. NACH #114.
6. **#116 (Should, 3 SP):** RN-010/011 — sitecustomize-Hygiene.
7. **#117 (Must, 3 SP):** Abschluss-Dossier — Deprecation
   --treat-timeout-as-kill, Release-Policy, formale Schließungen
   (OS-012-Rest, Shrink-Storm, BUG_REPORT_9 moot), 5 stale Milestones
   schließen, Pausenzustand.

## Out of scope (bewusst, dokumentiert)
Die 32 akzeptierten Pilot-Survivors (gather_coverage-Fehlertexte,
type_checking-Report-Toleranzen) — dokumentierte Test-Lücken, kein
offenes Topic. mypy-Baseline-Abbau über type_checking hinaus. PyPI-
Publish. Entfernung (statt Deprecation) von --treat-timeout-as-kill.
