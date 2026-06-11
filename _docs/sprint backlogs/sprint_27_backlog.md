# Sprint Backlog — Sprint 27 (Full Source Audit, analysis-only)

**Projekt:** mutmut-win
**Sprint:** 27
**Sprint-Ziel:** Systematisches Audit aller `src/mutmut_win/`-Module auf latente Bugs — ausgelöst durch den W4.11-Downstream-Report (2 × S1), aber unabhängig davon. Analysis-only: Findings-Report, kein Bugfixing.
**Epic(s):** Epic 18 (Audit & Detection Quality II) — neu, wird bei Sprint-Abschluss im product_backlog ergänzt
**Branch:** `main` (read-only Analyse; nur Doku-Commits)
**Zeitraum:** 2026-06-11 – 2026-06-11
**Status:** ✅ Closed — Findings-Report geliefert (`_docs/audit/sprint_27_audit_findings.md`): 201 raw / ~180 unique Findings, davon 15 S1; 12 Top-Findings hauptsession-verifiziert; Semgrep 0 Findings; pip-audit nicht erhoben (SSL-Fehler Richtung pypi.org)

---

## Auftrag (User-Decision 2026-06-11)

Vollständige Quelltext-Analyse in 2–4 Analyse-Stages. Die real reporteten
Bugs BUG-1 (sole-genexp SyntaxError) und BUG-2 (300s-Timeout-Konstante) sind
**nicht** Teil des Audits (bereits dokumentiert, Fixing deferred), wohl aber
ihre Bug-Klassen-Geschwister.

## Stages

| Stage | Scope | Fokus-Bugklassen | Status |
|-------|-------|------------------|--------|
| A1 | mutation.py, node_mutation.py, regex_mutation.py, trampoline.py | Invalide Mutanten (Syntax/Präzedenz), equivalent-by-construction, Visitor-Crashes | ✅ 41 Findings (11 S1) |
| A2 | process/ (executor, worker, job_object, timeout, loop_monitor), runner.py | Races, Timeout-Logik, Windows-API, Ressourcen-Leaks, IL-Classifier | ✅ 54 Findings (2 S1) |
| A3 | orchestrator.py, file_setup.py, db.py, stats.py, test_mapping.py, code_coverage.py, type_checking.py, type_checker_filter.py, config.py, models.py | Datenintegrität, Pfad/Encoding, Score-Berechnung, Config-Lücken | ✅ 65 Findings (2 S1, inkl. destruktivem CM-001) |
| A4 | cli.py, browser.py, mutant_diff.py, exceptions.py, constants.py, _state.py, __init__.py, __main__.py + Semgrep/pip-audit-Baseline | Flag-Wiring, Rendering, Querschnitt, Konsolidierung | ✅ 41 Findings (1 S1, apply-Quell-Beschädigung) |

## Methodik (je Stage)

1. Parallele read-only Subagenten pro Modulgruppe (5-Sektionen-Prompts,
   Built-In-Tools — FS MCP/Serena nicht verfügbar, dokumentierte Ausnahme).
2. Hauptsession verifiziert JEDEN Verdachtsfall adversarial in-process
   (Operator auf adversariale Snippets anwenden, generierte Mutanten via
   `compile()` prüfen; Repro-Scratchpad unter gitignortem `_issues/`).
3. Verifizierte Findings → `_docs/audit/sprint_27_audit_findings.md`
   (Format: ID, Severity S1–S4, Datei:Zeile, Repro, Root Cause, Fix-Skizze).

**Severity-Skala** (angelehnt an Downstream-Report): S1 = blockiert
Läufe/erzeugt invaliden Code/Crash · S2 = verfälscht Ergebnisse/Score ·
S3 = Robustheit/Edge-Case · S4 = kosmetisch/Doku.

## Out of Scope

- Jegliches Bugfixing (separater Folge-Sprint nach User-Priorisierung)
- BUG-1/BUG-2 aus dem W4.11-Report (bereits reported + verifiziert)
- tests/ und benchmarks/ (nur als Evidenz herangezogen, nicht auditiert)

## Quality Gates Sprint-Ende

| Gate | Erwartung |
|------|-----------|
| Alle 29 src-Module von mind. einem Agent + Hauptsession-Review abgedeckt | Coverage-Tabelle im Audit-Doc |
| Jeder S1/S2-Fund in-process verifiziert (Repro-Beleg) | Verifiziert-Spalte im Audit-Doc |
| Semgrep + pip-audit Baseline | dokumentiert in A4 |
| Findings-Report committed | `_docs/audit/sprint_27_audit_findings.md` |
