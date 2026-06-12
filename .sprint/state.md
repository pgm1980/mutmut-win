---
current_sprint: "36"
sprint_goal: "v2.14.0 Maintenance 4: Fable-5 360° — alle 28 Findings der 360°-Analyse (9 Bugs A1–A9, 13 Anomalien B1–B13, 6 Optimierungen C1–C6; Issues #124–#132). Messziele: 28/28 geschlossen, Semgrep-Pro-Gate (>=1200 Regeln, 0 Findings), Mutation >=80% je geändertem Modul, Dogfooding-Vollpilot."
branch: "feature/v2.14.0-maintenance-4"
started_at: "2026-06-12"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 36 opened 2026-06-12)

## Current Focus
Sprint 36 — **v2.14.0 Maintenance 4: Fable-5 360°** — beendet die
Entwicklungspause. Grundlage: Fable-5 360°-Code-Analyse vom 2026-06-12
(`_docs/audit/fable5_360_analysis_v2.13.0.md`, Zeilanker `main @ 2e481fd`;
Serena-Memory `fable5_360_findings`). 9 Issues #124–#132 im Milestone
„v2.14.0 - Maintenance 4: Fable-5 360" (#6), ~47 SP (Must ≈ 36, Should ≈ 11).
Backlog: `_docs/sprint backlogs/sprint_36_backlog.md`.

## Planungsentscheidungen (User, 2026-06-12)
- Ein Sprint für alle 28 Findings (Must/Should-Split statt Wellen-Sprints).
- A2: pytest-Floor >= 8.2 + Laufzeit-Guard (keine Dual-Codepfade).
- Semgrep-Gate ab jetzt Pro-basiert mit Engine-Nachweis: „Rules run" >= ~1200,
  kein „semgrep login"-Hinweis. Host-CLI 1.166.0 eingeloggt (User-Env-Var;
  Sessions erben erst nach Desktop-Neustart — Workaround: winreg-Bridge,
  siehe Memory `semgrep-ce-vs-pro-infrastruktur`).

## Reihenfolge-Empfehlung (Report §8, Wellen)
1. #124 (A1) + #125 (A2) — Kernversprechen
2. #127 (A6/A7/A9) — CI-Vertrauen
3. #126 (A3) + #129 (A8) + #128 (A4) — Korrektheitsschulden
4. #131 (A5/B4) + #130 (B1–B3) — Doku/Gates + Stats-Subsystem
5. #132 — Härtung/Performance gebündelt (Should)

## Gates (DoD-Kurzform)
pytest grün · ruff 0 · mypy <= 14 Baseline · import-linter · Semgrep Pro
(>=1200 Regeln, 0 Findings) · pip-audit · Mutation >= 80 % je geändertem
Modul · Regressionstest je A-Befund · Dogfooding-Vollpilot (Referenz:
Sprint-34-Baseline 7800 Mutanten / 68,3 %).

## Out of scope
SCA (`semgrep ci`), Docker-MCP-Infrastruktur (Mount/webapi-Token),
CLAUDE.md-Blueprint-Härtung (projektübergreifend), C3 optional in #132.
