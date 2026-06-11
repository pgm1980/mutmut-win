---
current_sprint: "32"
sprint_goal: "v2.10.0 Pipeline Hygiene — letzter Audit-Sprint: Runner-Diagnose + Stats-Cache-Wahrheit, DB-Härtung, Staging-Hygiene (Containment/Deletion-Sync/Fingerprint), Config-/CLI-Validierung, reiner JSON-Kanal, Selbst-Hygiene-Gates + Dogfooding-Premiere, C9-Rest-Triage."
branch: "feature/v2.10.0-pipeline-hygiene"
started_at: "2026-06-11"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 32 opened 2026-06-11)

## Current Focus
Sprint 32 — **v2.10.0 Pipeline Hygiene** — **implementation complete**
(alle 7 Items, 36/36 SP). Der LETZTE Audit-Sprint; der Zyklus ist mit
Schlussbilanz im Register beendet. Commits auf
`feature/v2.10.0-pipeline-hygiene`:

| Issue | Commits | Inhalt |
|-------|---------|--------|
| #98 | `804e402`+`a92c5fb` (Ph. 1), `06c9c6c`+`4d1e908` (Ph. 2) | Format-Commit isoliert (21 Dateien), pytest-Kanon (conftest — `uv run pytest` nackt), semgrep scannt tests/ real (101 Dateien; 11 Test-Idiome begründet unterdrückt); **Dogfooding-Premiere**: Pilot 5 komplett, 244 Mutanten, 85,5 % über bewertbare (type_checking 96,4 %), 4 Vorlauf-Funde + 2 neue Maintenance-Einträge (DOG-001 Timeout-Startup-Sockel S2, DOG-002 Hint-pro-Worker S4), 1 echte Testlücke gefixt |
| #99 | `af0b826` | Runner: DEVNULL→Tail-Capture + Exit-Dekodierung, extra_paths im PYTHONPATH (RN-002 ✅✅), Stats-Fehlschlag vergiftet nie den Cache (Plugin-JSON = Wahrheit, heilt Partial-Writes), Obsolete-Cleanup bei Löschung |
| #100 | `55bc61e` | DB: Lesepfad-Migration (Prä-v2.5 ✅✅), contextlib.closing überall (WinError 32 ✅✅), Race-tolerante Migration, Surrogate-sichere Writes |
| #101 | `d4a8e87` | Staging: `..`-Containment (#69-Use-Case erhalten), Deletion-Sync inkl. .meta (OS-012 KOMPLETT), Quellen-Fingerprint in .meta (Erstansatz von eigener Suite korrigiert!), Config-Fingerprint fürs Fast-Path-Gating, atomare+tolerante .meta, --force ehrlich |
| #102 | `c3fe810` | Config/CLI: Override-Re-Validierung (--max-children 0 war Hänger), Typo-Warnung mit difflib, since-commit-returncode+Filter, --debug real |
| #103 | `ebb1fd9` | CI: json.loads(stdout) funktioniert (Prosa→stderr), kein UnicodeEncodeError auf cp1252 |
| #104 | `3528022` | Maintenance-Backlog (26 Einträge inkl. 2 Dogfooding-Funde), Audit-Schlussbilanz, QX-001-Skip im Trampolin-Artefakt |

Gates (VERSCHÄRFT, alle ✅): **821 passed / 4 skipped** (nackt), ruff 0,
**format-check 0** (neu), mypy 20 pre-existing / 0 neue, **semgrep 0 auf
src+tests** (101 Dateien, neu), lint-imports KEPT, **Mutation-Pilot
dokumentiert** (erstmals).

## Release — DONE 2026-06-11
v2.10.0 released: Merge (closes #98–#104, 0 offene Issues verifiziert),
Bump `060ea16`, annotated Tag `v2.10.0`, GitHub Release
https://github.com/pgm1980/mutmut-win/releases/tag/v2.10.0. Suite auf
gemergtem main erneut 821 passed / 4 skipped. Sprint 32 vollständig
abgeschlossen — der AUDIT-ZYKLUS ist beendet (Register geschlossen).

## Nach v2.10.0
Audit-Zyklus formal beendet (Register geschlossen). Weiterarbeit aus dem
**Maintenance-Backlog** (Product Backlog, severity-sortiert, 26 Einträge)
— bedarfsgetrieben, Top-Kandidaten: DOG-001 (Timeout-Startup-Sockel, S2),
UI-007 (TUI-Diff, S2), QX-001 (Trampolin-Importkette, S2; Vorarbeit:
Architektur-Skip-Marker existiert). pip-audit bleibt umgebungsblockiert.
