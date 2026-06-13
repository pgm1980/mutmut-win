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

## Definition of Done (Sprint-Gates) — Stand 2026-06-13

- [x] `uv run pytest` vollständig grün — **1118 passed / 5 skipped** (inkl. Regressionstests je Befund)
- [x] `uv run ruff check .` → 0 Findings (B13: `.claude/` excluded; bare `.` ist Teil des Gates)
- [x] `uv run mypy src/` → 14 Errors = bekannte Baseline, keine neuen
- [x] `uv run lint-imports` → Layer architecture (ADR layer contracts v2) **KEPT**
- [x] **Semgrep Pro/SAST**: 2918 Code rules geladen (1859 Pro), **1228 Rules run, 0 Findings**, kein Login-Hinweis (Token via winreg-Bridge)
- [x] `pip-audit` → **No known vulnerabilities** (nach Lock-Bumps urllib3 2.7.0, idna 3.18, pip 26.1.2, pytest 9.0.3; truststore-injiziert gegen TLS-Interception)
- [x] Mutation Score ≥ 80 % auf den Wave-Zeilen jedes geänderten Moduls (Zeilen-Gate via Staged-Slice-Diff + Token-Intersection; dokumentierte Äquivalente in den Commit-Messages):
  - Welle 1 (#124, #125): 90,9 %
  - Welle 2 (#127): 88,1 % (7 dokumentierte Äquivalente)
  - Welle 3 (#126, #128, #129): **91,4 %** nach Härtung `e9dcb10` (file_setup; _sync_tree 87,2 %, get_mutant_name 94,3 %, _mirror_is_stale 93,3 %)
  - Welle 4 (#130, #131): **87,0 % gesamt** nach Härtung `232b2eb` — alle Wave-Zeilen-Survivors getilgt (filter 92,6 %, warn 97,1 %, collect_tests 97,0 %, fingerprints 90,5 %)
  - Welle 5 (#132): **98,6 % Wave-Zeilen** nach Härtung (runner-Phasen 100 %, config 97,6 %; worker-Mapping 100 %)
- [ ] Dogfooding-Vollpilot — **läuft** (Ergebnis wird hier nachgetragen; Referenz S34: 7800 Mutanten / 68,3 %; Result-Reuse #119 aktiv = Produktverhalten)
- [x] Jeder Should-Punkt aus #132 gefixt ODER dokumentiert: B11/B12 als dokumentierte Limitation (README + Visitor-Kommentar), C3 Won't-Do (gezielte Teil-Collection bleibt Future Option), Rest gefixt — inkl. C1-Timing-Beleg (Benchmark: 5,5 ms batched vs. 775 ms per-row, 300 Rows)
- [ ] Sprint-Housekeeping (`.sprint/state.md`-Flags wahrheitsgemäß, MEMORY/Serena aktualisiert; Issues schließen sich via `closes #NNN` beim Merge/Push — User-Entscheidung)

### Implementierungs-Verlauf (Commits)

| Welle | Issues | Commits |
|---|---|---|
| 1 | #124, #125 | `a8fdd85`, `6302b46`, `c9f526e` (u. a.) |
| 2 | #127 | `52c5884`, `26ade60` (u. a.) |
| 3 | #126, #128, #129 | `2432bf2` + Härtung `e9dcb10` |
| 4 | #130, #131 | `c9e33e8` + Härtung `232b2eb` |
| 5 | #132 | `67b66d8` + Härtung (Job-Handle-Lifecycle, sorted-Warnung) |
| Gates | — | `9f73eee` (Dependency-Advisories) |

**Hinweis B7-Revision (in `67b66d8` dokumentiert):** Der ursprünglich geplante Config-Validator hätte den dokumentierten Bug-#69-Sibling-Use-Case gebrochen — die Staging-Kopie mappt `..`-Siblings bereits auf `mutants/<basename>` (A3-FD-002). Tatsächlicher Fix: PYTHONPATH-Parität in `worker._process_task` und `runner._mutants_env`.

**Legacy-Debt-Befund (außerhalb des Sprint-Scopes, für einen künftigen Tech-Debt-Sprint):** funktionsweite Alt-Survivor-Quoten u. a. `MutationOrchestrator.run` 60,7 %, `_process_task` 41,1 %, `worker_main` 49,2 %, `get_events` 62,5 %, `SpawnPoolExecutor.__init__` 35,3 %, `_print_summary` 22 %, `load_config` 76,5 %, `_load_setup_cfg` 67 %, `_run_stats_collection`-Failure-Pfad 60 %.

## Out of scope (bewusst)

- SCA via `semgrep ci --supply-chain` (Upload-Modus; Dependency-CVEs deckt `pip-audit`)
- Docker-MCP-Infrastruktur (Bind-Mount, webapi-Token) — außerhalb dieses Repos
- C3 (gezielte inkrementelle Stats-Re-Runs) ist optional in #132; bei Zeitdruck Won't-Do mit Begründung
- CLAUDE.md-Blueprint-Härtung (Engine-Nachweis-Direktive) — projektübergreifend, separat
