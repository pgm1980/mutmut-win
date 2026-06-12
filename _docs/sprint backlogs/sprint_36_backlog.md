# Sprint 36 Backlog — v2.14.0 „Maintenance 4: Fable-5 360°"

| | |
|---|---|
| **Sprint-Ziel** | Alle 28 Findings der Fable-5 360°-Analyse schließen (9 Bugs A1–A9, 13 Anomalien B1–B13, 6 Optimierungen C1–C6) |
| **Quelle** | `_docs/audit/fable5_360_analysis_v2.13.0.md` (Zeilanker auf `main @ 2e481fd`) · Serena-Memory `fable5_360_findings` |
| **Branch** | `feature/v2.14.0-maintenance-4` |
| **Milestone** | v2.14.0 - Maintenance 4: Fable-5 360 (#6) |
| **Issues** | #124–#132 (9 Issues, ~47 SP: Must ≈ 36, Should ≈ 11) |
| **Start** | 2026-06-12 |
| **Danach** | Release v2.14.0 auf User-„Release", zurück in die Entwicklungspause (0-Backlog-Disziplin) |

## Planungsentscheidungen (User, 2026-06-12)

1. **Ein Sprint für alle 28 Findings** (statt Wellen-Split) — Must/Should-Priorisierung im Sprint.
2. **A2-Strategie: pytest-Floor ≥ 8.2 + Laufzeit-Guard** — ehrliche Dependency (Resolver erzwingt
   Kompatibilität im Ziel-venv), zusätzlicher erklärender Abbruch vor dem ersten Mutanten;
   keine Dual-Codepfade. Floor-Bump gilt als Bugfix (die 6.2.5-Kompatibilität war faktisch falsch).
3. **Semgrep-Gate ab sofort Pro-basiert**: Engine-Nachweis Pflicht („Rules run" ≥ ~1200, kein
   Login-Hinweis). Historische CE-Gates sind im Audit-Report (Abschnitt 3) dokumentiert.

## Items

| Issue | Inhalt | Befunde | SP | Prio |
|---|---|---|---|---|
| **#124** | Result-Persistenz: `_update_source_data` exakter Name→Datei-Lookup statt Prefix-Heuristik; toleranter Meta-Load | A1, B10 | 5 | Must |
| **#125** | pytest-Floor ≥ 8.2 + Laufzeit-Guard für `@argfile` (Design-CoT ≥ 8) | A2 | 5 | Must |
| **#126** | Naming-Invariante `source/`-Layouts: Root-Strip aus single source of truth; neues source/-e2e-Fixture | A3 | 5 | Must |
| **#127** | CI-Vertrauen: JSON-Reinheit (stdout-Disziplin inkl. Kindprozesse), Pool-Kollaps als Abbruchzustand (Design-CoT ≥ 8), show-Glob-Forensik | A6, A7, A9 | 5 | Must |
| **#128** | `--since-commit`: Pfad-Komponenten-Vergleich für tests_dir; Working-Tree-Änderungen einbeziehen | A4 | 3 | Must |
| **#129** | Engine-Version in Fingerprints (Upgrade-Invalidierung); Staging-Stale-Lücken; also_copy-Sync; skip_dirs | A8, B6, C2, C4 | 5 | Must (A8), Rest Should |
| **#130** | Stats-/Mapping-Subsystem: Test-Datei-Fingerprints + Mapping-Invalidierung (Design-CoT ≥ 8), collect_tests-Scope-Parität, Timeout-Fallback | B1, B2, B3 | 8 | Must |
| **#131** | Type-Check: README-Fix + Config-Hinweis (JSON-Flag), Baseline-Abzug gegen ungemutetes Staging | A5, B4 | 3 | Must |
| **#132** | Härtung & Performance gebündelt: Phasen-Reaping, extra_paths-PYTHONPATH, IL-Konstanten, setup.cfg-Parität, Nested-Class-Warnung, Nenner-Doku, ruff-exclude, DB-Batching, Regex-Dedupe, dict statt defaultdict (+C3 optional) | B5, B7–B9, B11–B13, C1, C5, C6 | 8 | Should |

## Definition of Done (Sprint-Gates)

- [ ] `uv run pytest` vollständig grün (inkl. neuer Regressionstests je A-Befund)
- [ ] `uv run ruff check .` → 0 Findings (B13-Fix macht das Gate wieder ehrlich)
- [ ] `uv run mypy src/` → keine NEUEN Errors über der 14er-Baseline
- [ ] `uv run lint-imports` → Contracts halten
- [ ] **Semgrep Pro/SAST mit Engine-Nachweis**: ≥ 1200 Regeln gelaufen, 0 Findings, kein Login-Hinweis
- [ ] `uv run pip-audit` → keine bekannten Vulnerabilities
- [ ] Mutation Score ≥ 80 % auf jedem geänderten Modul (`mutmut-win run --paths-to-mutate …`)
- [ ] Dogfooding-Vollpilot am Sprint-Ende (Vergleichsbasis: Sprint-34-Baseline 7800 Mutanten / 68,3 %)
- [ ] Jeder Should-Punkt aus #132 gefixt ODER mit dokumentierter Begründung als Won't-Fix vermerkt
- [ ] Sprint-Housekeeping (`.sprint/state.md`-Flags wahrheitsgemäß, MEMORY/Serena aktualisiert, Issues geschlossen)

## Out of scope (bewusst)

- SCA via `semgrep ci --supply-chain` (Upload-Modus; Dependency-CVEs deckt `pip-audit`)
- Docker-MCP-Infrastruktur (Bind-Mount, webapi-Token) — außerhalb dieses Repos
- C3 (gezielte inkrementelle Stats-Re-Runs) ist optional in #132; bei Zeitdruck Won't-Do mit Begründung
- CLAUDE.md-Blueprint-Härtung (Engine-Nachweis-Direktive) — projektübergreifend, separat
