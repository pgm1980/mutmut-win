---
current_sprint: "34"
sprint_goal: "v2.12.0 Maintenance 2: Final Sweep — kompletter Pool-Rest (13 Einträge, #111–#117) + MEMORY-Entscheidungsregister; danach Entwicklungspause. Messziel: Pilot brutto >= 80 % halten."
branch: "feature/v2.12.0-maintenance-2"
started_at: "2026-06-11"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 34 opened 2026-06-11)

## Current Focus
Sprint 34 — **v2.12.0 Maintenance 2: Final Sweep** —
**GESCHLOSSEN, v2.12.0 RELEASED 2026-06-12** (User-„Release"; Merge
`9789429`, Bump `932f90e`, annotated Tag v2.12.0,
[GitHub-Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.12.0),
#111–#117 via Merge auto-geschlossen — 0 offene Issues). Gates vor dem
Merge frisch verifiziert: 951 passed / 4 skipped, ruff/format 0, mypy
14 = Baseline (0 neue).

**PROJEKT IN ENTWICKLUNGSPAUSE (User-Entscheidung):**
0 offene Issues · 0 Pool-Einträge · 0 offene Entscheidungen ·
0 offene Milestones. Wiederaufnahme-Startpunkte: Pausen-Baseline der
Vollvermessung (7800 Mutanten, 68,3 % brutto; 2337 Survivors + 45
Timeouts, Sprint-34-Dogfooding-Protokoll) und die dort notierte
Stats-Fingerprint-Beobachtung. Kein neuer Sprint geplant —
nächster Sprint-State entsteht erst bei Wiederaufnahme.

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
