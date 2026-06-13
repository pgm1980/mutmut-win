---
current_sprint: "36"
sprint_goal: "v2.14.0 Maintenance 4: Fable-5 360° — alle 28 Findings der 360°-Analyse (9 Bugs A1–A9, 13 Anomalien B1–B13, 6 Optimierungen C1–C6; Issues #124–#132). Messziele: 28/28 geschlossen, Semgrep-Pro-Gate (>=1200 Regeln, 0 Findings), Mutation >=80% je geändertem Modul, Dogfooding-Vollpilot."
branch: "feature/v2.14.0-maintenance-4"
started_at: "2026-06-12"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 36 opened 2026-06-12)

## Current Focus
Sprint 36 — **v2.14.0 Maintenance 4: Fable-5 360°** —
**GESCHLOSSEN, v2.14.0 RELEASED 2026-06-13** (User-„Release"; Merge
`5ef27c1`, Bump `43a7762` inkl. Versionspins, annotated Tag v2.14.0 auf
dem Bump-Commit,
[GitHub-Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.14.0),
#124–#132 via Merge auto-geschlossen). Gates vor dem Merge frisch
verifiziert: 1118 passed / 5 skipped, ruff 0 (bare `.`), ruff format
clean, mypy 14 = Baseline, import-linter KEPT, Semgrep Pro 1228 Regeln /
0 Findings, pip-audit clean. Dogfooding-Vollpilot 69,2 % (über S34-
Referenz 68,3 %). 28/28 Findings der Fable-5-360°-Analyse geschlossen
(C3 dokumentiertes Won't-Do; B11/B12 dokumentierte Limitationen).

**PROJEKT ZURÜCK IN DER ENTWICKLUNGSPAUSE (User-Entscheidung):**
0 offene Issues · 0 Backlog-Einträge · 0 offene Entscheidungen ·
0 offene Milestones. Wiederaufnahme-Startpunkte: Dogfooding-Pausen-
Baseline (7231 Mutanten / 69,2 %), der 360°-Report
(`_docs/audit/fable5_360_analysis_v2.13.0.md`, Serena-Memory
`fable5_360_findings`) und der dokumentierte Legacy-Tech-Debt-Befund
im Sprint-36-Backlog (funktionsweite Alt-Survivor-Quoten für einen
künftigen Tech-Debt-Sprint). Kein neuer Sprint geplant — nächster
Sprint-State entsteht erst bei Wiederaufnahme.

## Sprint 36 Ergebnis (Wellen)
1. **#124 (A1) + #125 (A2):** Result-Persistenz exakter Name→Datei-
   Lookup; pytest-Floor >= 8.2 + Run-Start-Guard. Commits `6302b46`,
   `a8fdd85`. Mutation-Zeilen-Gate 90,9 %.
2. **#127 (A6/A7/A9):** JSON-Reinheit, Pool-Kollaps-Abbruchzustand,
   show-Glob-Forensik. Commits `26ade60`, `52c5884`. Gate 88,1 %.
3. **#126/#128/#129 (A3/A4/A8/B6/C2/C4):** source/-Layout-Naming,
   Engine-Version-Fingerprint, Mirror-Truth, since-commit. Commit
   `2432bf2` + Härtung `e9dcb10`. Gate 91,4 %.
4. **#130/#131 (B1–B3/A5/B4):** Stats-Mapping-Invalidierung, collect-
   Scope-Parität, Timeout-Fallback, Type-Check-Baseline. Commit
   `c9e33e8` + Härtung `232b2eb`. Gate 87,0 %.
5. **#132 (B5/B7–B9/B11–B13/C1/C5/C6):** Phasen-Reaping, PYTHONPATH-
   Parität, IL-Konstanten-SSOT, setup.cfg-Parität, DB-Batching,
   Regex-Dedupe, plain-dict-Status. Commit `67b66d8` + Härtung
   `f50d2d4`. Gate 98,6 % Wave-Zeilen.
6. **Gates/Release:** Dependency-Advisories `9f73eee`; Doku
   `aeeb7c8`/`cc7f357`; Cleanup `244f602`; Merge `5ef27c1`; Bump
   `43a7762`.

## Out of scope (bewusst, dokumentiert)
SCA (`semgrep ci --supply-chain`), Docker-MCP-Infrastruktur
(Mount/webapi-Token), CLAUDE.md-Blueprint-Härtung (projektübergreifend),
C3 (gezielte inkrementelle Stats-Re-Runs — Won't-Do in #132).
