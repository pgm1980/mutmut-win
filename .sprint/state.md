---
current_sprint: "36"
sprint_goal: "v2.14.0 Maintenance 4: Fable-5 360° — alle 28 Findings der 360°-Analyse (9 Bugs A1–A9, 13 Anomalien B1–B13, 6 Optimierungen C1–C6; Issues #124–#132). Messziele: 28/28 geschlossen, Semgrep-Pro-Gate (>=1200 Regeln, 0 Findings), Mutation >=80% je geändertem Modul, Dogfooding-Vollpilot."
branch: "feature/v2.14.0-maintenance-4"
started_at: "2026-06-12"
housekeeping_done: false
memory_updated: true
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
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

## Sprint Context (auto-saved before compaction at 2026-06-12T23:21:52Z)

### Current Branch
feature/v2.14.0-maintenance-4

### Last 10 Commits
```
c9e33e8 fix(stats,runner,orchestrator): mapping invalidation, collection parity, honest budgets, type-check baseline (closes #130, closes #131)
e9dcb10 test(wave-3): kill wave-3-line mutation survivors (refs #126, #129)
2432bf2 fix(staging,cli): source/-layout naming, engine-version fingerprint, mirror truth, since-commit (closes #126, closes #128, closes #129)
52c5884 test(wave-2): kill wave-2-line mutation survivors (refs #127)
26ade60 fix(cli,executor): json purity, pool-collapse abort state, show-glob forensics (closes #127)
a8fdd85 test(wave-1): kill mutation survivors - gate 90.9% on changed code (refs #124, #125)
6302b46 fix(orchestrator,models): meta truth via exact ownership; pytest>=8.2 floor + run-start guard (closes #124, closes #125)
c9f526e chore(format): apply ruff format to benchmarks (pre-existing drift)
423166b docs(sprint-36): open sprint - Maintenance 4: Fable-5 360 analysis (issues #124-#132)
2e481fd docs(sprint-35): close sprint - v2.13.0 released, back in the development pause
```

### Recently Changed Files
```
README.md
src/mutmut_win/cli.py
src/mutmut_win/config.py
src/mutmut_win/constants.py
src/mutmut_win/file_setup.py
src/mutmut_win/models.py
src/mutmut_win/orchestrator.py
src/mutmut_win/process/executor.py
src/mutmut_win/process/worker.py
src/mutmut_win/runner.py
src/mutmut_win/stats.py
tests/e2e_projects/source_layout/pyproject.toml
tests/e2e_projects/source_layout/source/pkglib/__init__.py
tests/e2e_projects/source_layout/source/pkglib/calc.py
tests/e2e_projects/source_layout/tests/test_calc.py
tests/integration/test_source_layout_e2e.py
tests/unit/test_cli.py
tests/unit/test_config_cli_truth.py
tests/unit/test_exception_hygiene_114.py
tests/unit/test_file_setup.py
```

### Uncommitted Changes
```
 D hooks.md
 D seqthinking.md
 M tests/integration/test_source_layout_e2e.py
?? .serena/memories/sprint_36_progress.md
?? .sprint/.fs-mcp-versions/state.md.v1.854b6b52ed554bd28dab9241c93b9680
```
