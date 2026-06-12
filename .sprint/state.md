---
current_sprint: "35"
sprint_goal: "v2.13.0 Maintenance 3: External QA — alle 15 Findings des externen 360°-QA-Reports (6 Medium, 9 Low; #118–#123) inkl. Result-Reuse-Feature (RUN-001) und skipped-Producer (SCO-002); danach zurück in die Entwicklungspause. Messziele: 15/15 geschlossen, Pilot >= 80 %, Reuse-Demo (Lauf B dispatcht 0)."
branch: "feature/v2.13.0-maintenance-3"
started_at: "2026-06-12"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 35 opened 2026-06-12)

## Current Focus
Sprint 35 — **v2.13.0 Maintenance 3: External QA** — Unterbrechung der
Entwicklungspause auf User-Entscheid: Ein externer 360°-QA-Report gegen
v2.12.0 lieferte 15 Findings (6 Medium, 9 Low), alle am Code
verifiziert (Archiv: `_docs/audit/external_qa_report_v2.12.0.md`,
Repro-Projekte unversioniert unter `_bug_reports/`).
6 Issues (#118–#123, 29 SP), Reihenfolge 118 → 120 → 119 → 122 → 121
→ 123 (Purge-Fix vor Reuse-Feature vor skipped-Producer), dann
Abschluss-Dogfooding inkl. **Reuse-Demo** (unveränderter Lauf B
dispatcht 0 Tasks). User-Entscheidungen: RUN-001 als FEATURE
(Result-Reuse + --rerun-all), skipped bekommt echten Producer
(Filter-Subset-Läufe, nie Verdicts überschreiben).
Release v2.13.0 nur auf explizites User-„Release"; danach
**zurück in die Entwicklungspause**.

## Sprint 35 Backlog (29 SP — Must 24, Should 5)
1. **#118 (Must, 1 SP):** Intake + DOC-001 — User-Hotfix committen,
   .gitignore, Report-Archiv.
2. **#120 (Must, 5 SP):** RUN-002 (Pfad-Subset-Purge!), CLI-002
   (Pfad-Existenz → exit 2), CLI-001 (min-score-Range), CFG-001
   (Config-Fehler → exit 2 kompakt).
3. **#119 (Must, 8 SP):** RUN-001 — Result-Reuse: Fast-Path +
   Config-Fingerprint + tests_fingerprint (neue DB-Spalte, #100-
   Migration) + wiederverwendbares Verdict; --rerun-all; laute Summary.
   Design-CoT ≥ 8.
4. **#122 (Must, 5 SP):** SCO-002-Producer (skipped für gefilterte
   Staging-Mutanten ohne DB-Row), SCO-001 (Export-Nenner-Zeile),
   SCO-003 (results rendert Type-check separat).
5. **#121 (Must, 5 SP):** MUT-001 (FormattedString raus aus
   Return-Skip; Literal-Part-Mutation per Design-Entscheid), MUT-002
   (Funktions-Granularität + ehrliche Warnung).
6. **#123 (Should, 5 SP):** CLI-003 (StaleStagingError), CFG-002
   (no-match-Warnung), DOC-002 (Staging-Doku), WIN-001
   (WER-Unterdrückung, win32, Unit-Pin).

## Out of scope (bewusst, dokumentiert)
do_not_copy-Feature (DOC-002 bleibt Doku-Fix — Won't-Do im Issue);
WIN-001-Live-Crash-Verifikation (Reporter-Begründung übernommen);
die 2337-Survivor-Pausen-Baseline aus Sprint 34 (kein Report-Finding).
