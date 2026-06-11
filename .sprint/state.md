---
current_sprint: "34"
sprint_goal: "v2.12.0 Maintenance 2: Final Sweep — kompletter Pool-Rest (13 Einträge, #111–#117) + MEMORY-Entscheidungsregister; danach Entwicklungspause. Messziel: Pilot brutto >= 80 % halten."
branch: "feature/v2.12.0-maintenance-2"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: true
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 34 opened 2026-06-11)

## Current Focus
Sprint 34 — **v2.12.0 Maintenance 2: Final Sweep** —
**IMPLEMENTIERUNG KOMPLETT** (alle 7 Issues #111–#117, 27/27 SP,
Commits `8251509`..`fa590ac`). **Maintenance-Pool 13 → 0,
Entscheidungsregister 4 → 0, mypy-Baseline 20 → 14, 5 stale
GitHub-Milestones geschlossen.** Gates: 951 passed (+83), ruff/format
0, semgrep 0 (voller Sweep), lint-imports KEPT inkl. Artefakt;
Pilot **85,1 % brutto gehalten** (6 Kaltstart-Timeouts im Re-Run 6/6
gekillt → 87,6 % effektiv; 30 dokumentierte Survivors). pip-audit
bleibt umgebungsblockiert (TLS-Interception). Bedienungs-Lektion:
`--since-commit` nach Konfig-Wechsel braucht `--force` (Stats-Cache);
der #106-Producer verbuchte 7318 unkartierte Mutanten ehrlich als
`no tests` statt Vollsuite. Abschluss-Vollvermessung (12 Module,
erstmalig): **7800 Mutanten, 68,3 % brutto** — 2337 Survivors + 45
Timeouts als ehrliche Pausen-Baseline dokumentiert; 1 Dogfooding-
Test-Fund gefixt (`6101548`, instrumentierungsfester Depth-Cache-Test).
Release v2.12.0 wartet auf explizites User-„Release"
(Merge → Auto-Close #111–#117 → housekeeping_done);
**danach Entwicklungspause** (Pausenzustand dokumentiert).

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
