---
current_sprint: "32"
sprint_goal: "v2.10.0 Pipeline Hygiene — letzter Audit-Sprint: Runner-Diagnose + Stats-Cache-Wahrheit, DB-Härtung, Staging-Hygiene (Containment/Deletion-Sync/Fingerprint), Config-/CLI-Validierung, reiner JSON-Kanal, Selbst-Hygiene-Gates + Dogfooding-Premiere, C9-Rest-Triage."
branch: "feature/v2.10.0-pipeline-hygiene"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 32 opened 2026-06-11)

## Current Focus
Sprint 32 — **v2.10.0 Pipeline Hygiene** — geplant, Implementierung noch
nicht gestartet (wartet auf „Go"). Basis: Audit-Cluster **C8 + C9-Top** +
4 Neuzugänge + Dogfooding-Gate (deferred seit Sprint 28). Der LETZTE
Audit-Sprint — danach ist der Zyklus formal beendet, C9-Rest wird
kuratierter Maintenance-Backlog. Issues #98–#104 angelegt. Branch
`feature/v2.10.0-pipeline-hygiene`.

## Sprint 32 Backlog (36 SP — Must 34, Should 2)
1. **#98 (Must, 5 SP, ZWEIPHASIG):** Phase 1 als SPRINT-AUFTAKT:
   isolierter repo-weiter Format-Commit (~23 Dateien), pytest-Kanon via
   conftest (`uv run pytest` ohne Flag), semgrep-Entscheid (tests/ wird
   gescannt). Phase 2 als SCHLUSSSTEIN (nach #99): Dogfooding-Pilot auf
   code_coverage.py + type_checking.py, Score dokumentiert.
2. **#99 (Must, 8 SP):** Runner/Stats: DEVNULL → Tail-Capture + Exit-
   Dekodierung (RN-001), extra_paths im Runner-PYTHONPATH (RN-002 ✅✅),
   Stats-Fehlschlag vergiftet nie den Cache (OS-006 re-verifiziert,
   RN-003), Obsolete-Cleanup bei Test-Löschung (OS-007). Capture-CoT ≥3.
3. **#100 (Must, 5 SP):** DB: Lesepfad-Migration (FD-001 ✅✅ Prä-v2.5-
   Crash), Connection-Close (FD-006 ✅✅ WinError 32 live), Migrations-
   Race (FD-007), Surrogates (FD-011).
4. **#101 (Must, 8 SP):** Staging: `..`-Containment (FD-002, Sandbox-
   bestätigt), Deletion-Sync inkl. .meta-Orphans (FD-003 — schließt
   OS-012 KOMPLETT), Fingerprint-Invalidierung (FD-004+OS-008),
   Nesting-Guard (FD-005), --force ehrlich (FD-009), .meta atomar+
   tolerant (CM-009). Design-CoT ≥8. Destruktiv → Tests zuerst.
5. **#102 (Must, 5 SP):** Config/CLI: Override-Re-Validierung (CM-004:
   --max-children 0 = Hänger heute), Typo-Warnung mit difflib (CM-005),
   since-commit-returncode (CM-006: falscher CI-Erfolg heute), --debug
   real (UI-005).
6. **#103 (Must, 3 SP):** CI-Output: json.loads(stdout) muss
   funktionieren (UI-006 — vervollständigt #97), kein UnicodeEncodeError
   auf cp1252 (QX-003). Nach #102 (beide cli.py).
7. **#104 (Should, 2 SP, ZULETZT):** C9-Rest-Triage → kuratierter
   Maintenance-Abschnitt im Product Backlog + Audit-Schlussstrich.

Reihenfolge: 98.1 → 99 → 100 → 101 → 102 → 103 → 98.2 → 104.
Scope-Ventil: #103+#104 rutschen; #101 teilbar (Kern vs.
Deletion-Sync+Fingerprint). v2.10.0 auch mit #98–#102 release-fähig.

## Planungs-Erkenntnisse (12-Schritt-CoT)
- Format-Commit MUSS vor allen Logik-Items liegen (Diff-Rauschen).
- Dogfooding-Blockade seit Sprint 28 ist exakt OS-006/RN-003 → #99 zuerst.
- Verschärfte Gates sind Sprint-INHALT: format --check neu, semgrep auf
  tests/ neu, pytest ohne Flag, Mutation-Pilot dokumentiert.
- C9-Rest (UI-007, QX-001/007, S4-Sammel) bewusst raus — via #104
  ehrlich überführt statt still versandet.
- UI-015 (Alignment) raus aus #103: Kosmetik mit Test-Rattenschwanz.
- OS-006 + FD-002 bei Planung am v2.9.0-Stand re-verifiziert.

## Branch-Aufräumen (2026-06-11, User-Auftrag)
37 lokale gemergte Branches gelöscht (git branch -d, alle in main),
2 Remote-Branches entfernt (origin/feature/v2.6.0-source-protection,
origin/feature/v2.7.0-runtime-reliability), --prune. Übrig: nur main
(+ dieser Sprint-Branch). Historie/Tags unberührt.

## Out of scope
C9-Rest (via #104 dokumentiert), pip-audit (Umgebungs-SSL).
