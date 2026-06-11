# Product Backlog — mutmut-win

**Version:** 2.2.0
**Datum:** 2026-06-11
**Status:** Active

---

## Release-Übersicht

| Release | Codename | Sprints | Status | Highlights |
|---------|----------|---------|--------|------------|
| v0.1.0 | MVP | Sprint 1–6 | Done | Windows-native Mutation Testing |
| v0.2.0 | Pipeline | Sprint 8–10 | Done | File Setup Pipeline, Test Mapping, CLI show/apply, E2E-Validierung |
| v0.3.0 | Performance | Sprint 11–12 | Done | In-Process Stats, Trampoline Tracking, Feature Completeness |
| v0.5.0 | Hardening (orphan-protect) | Sprint 13 | Done | Windows Job Object Orphan Protection |
| v0.6.0 | Stress-Test | — | Done | Synthetic 1127-mutant stress test, line-buffered stdout, progress counter fix |
| v1.0.0 | Advanced Operators + Hardening | Sprint 14–21 | Done | 7 neue Mutationsoperatoren + 10 CLI-Flags + Hook-Fixes |
| v2.0.0 | In-Process Test Mapping | (zwischen Sprints) | Done | Test-to-mutant mapping via injected pytest plugin |
| v2.0.1–v2.0.4 | Timeout Diagnostics | (kontinuierlich) | Done | Subprocess timeouts, DEVNULL-fix, temp-file capture, last_output in DB |
| v2.1.0 | Stabilization + Bug #4 | Sprint 22 | Done | typing.cast() skip, housekeeping pass, backlog sync |
| v2.2.0 | Reliability Wave | Sprint 23 | Done | Multi-line-`or`-Skip (#68), Default-Param-Skip (#70), `--treat-timeout-as-kill` (#71) |
| v2.3.0 | Must-Carryover Cleanup | Sprint 24 | Done | Worker-Crash-Recovery (#12), E2E-Harness (#38/#49), Job-Object-Test (#54), Dogfooding full src (#65) |
| v2.4.0 | Final Cleanup | Sprint 25 | Done | `--extra-paths-to-copy` (#69), also_copy venv-Skip (#67), Benchmark-Suite (#23) |
| v2.5.0 / v2.5.1 | Polish + True IL Detection | Sprint 26 | Done | Echte Infinite-Loop-Detection (psutil + Forensics + Confidence, #71), `--version`-Fix (#72); v2.5.1 Hotfix psutil-Process-Caching |
| — | Full Source Audit | Sprint 27 | Done | Analysis-only: 201 Findings (15 S1) über alle 29 Module, 9 Fix-Cluster — `_docs/audit/sprint_27_audit_findings.md` |
| v2.6.0 | Source Protection & Codegen Correctness | Sprint 28 | Done | W4.11-Blocker (BUG-1 #73, BUG-2 #74), Quell-Schutz (#75), Codegen-Fixes (#76–#78) — released 2026-06-11 |
| v2.7.0 | Runtime Reliability | Sprint 29 | Done | Audit C3+C4: letzte 2 S1-Hänger (#79, #80), Prozess-Hygiene (#82), Timeout-Architektur (#81), Job-Object-Polish (#83), lint-imports-ADR (#84) — released 2026-06-11; **alle 15 S1 geschlossen** |
| v2.8.0 | IL Detection Honesty | Sprint 30 | Done | Audit C5: Forensik-Persistenz (#85) + CICD-Bucket (#86) + Rendering (#87), Classifier-Ehrlichkeit Windows (#88), io_counters-Progress-Veto (#89), Test-Ehrlichkeit (#90) — released 2026-06-11 |
| v2.9.0 | Feature Truth & Score Integrity | Sprint 31 | Done | Audit C6+C7: Status-Wahrheit (#91), Type-Checking-Härtung (#92) + end-to-end (#93), Ctrl-C-Ehrlichkeit (#94), Coverage REAKTIVIERT (#95), DB-Orphan-Purge (#96), CI-Kanal (#97) — released 2026-06-11 mit „score corrections"-Sektion |
| v2.10.0 | Pipeline Hygiene | Sprint 32 | Done | Audit C8+C9-Top (LETZTER Audit-Sprint): Selbst-Hygiene+Dogfooding-Premiere (#98), Runner/Stats-Wahrheit (#99), DB-Härtung (#100), Staging-Hygiene (#101), Config/CLI (#102), CI-Output (#103), C9-Rest-Triage (#104) — released 2026-06-11; **Audit-Zyklus beendet** |
| v2.11.0 | Maintenance 1: Runtime & Self-Run | Sprint 33 | Done | Maintenance-Pool-Auswahl: Startup-Sockel (#105), no-tests-Producer (#106), Trampolin-Entkopplung (#107), Browser-Diff (#108), Robustheit (#109), Kleinkram (#110) — released 2026-06-11; **Pilot 24,2 % → 86,9 % brutto, 0 Timeouts statt 175; Architektur-Skip im Artefakt entfernt** |
| v2.12.0 | Maintenance 2: Final Sweep | Sprint 34 | Planned | VOLLSTÄNDIGER Pool-Rest (13 Einträge) + Entscheidungsregister: Runner-Wahrheit (#111), Arg-Koerzierung (#112), Sanitiser-Subtables (#113), Exception-Hygiene (#114), CLI-Konsistenz (#115), sitecustomize (#116), Abschluss-Dossier (#117) — danach **Entwicklungspause**; Messziel: Pilot ≥ 80 % halten |

---

## Definition of Done (DoD)

### Quality-Gates

- [ ] **Build**: `uv sync` — 0 Errors
- [ ] **Tests**: `uv run pytest` — alle grün
- [ ] **Coverage**: `uv run pytest --cov=src` — ≥ 80% Line Coverage
- [ ] **Linting**: `uv run ruff check .` — 0 Findings
- [ ] **Formatting**: `uv run ruff format .` — formatiert
- [ ] **Type Check**: `uv run mypy src/` — 0 Errors (strict)
- [ ] **Security**: `semgrep scan --config auto .` — 0 Findings
- [ ] **Dependency Audit**: `uv run pip-audit` — 0 Advisories
- [ ] **Architecture**: `uv run lint-imports` — 0 Verletzungen
- [ ] **Property Tests**: hypothesis-basierte Roundtrip/Invarianten-Tests vorhanden
- [ ] **Mutation Testing**: `uv run mutmut-win run --paths-to-mutate <geänderte Module>` — Score ≥ 80% auf neuem Code
- [ ] **E2E-Validierung**: `uv run mutmut-win run` auf simple_lib Testprojekt — erfolgreich

### Prozess-Gates

- [ ] **Code Review**: Mindestens 1 Review bestanden
- [ ] **MEMORY.md**: Projektgedächtnis aktualisiert
- [ ] **GitHub Issues**: Alle Sprint-Issues geschlossen
- [ ] **Commit, Push**: Conventional Commit, Branch pushed

---

## Epics und Sprint-Zuordnung

### Epic 1: Project Foundation & Domain Models

**Beschreibung:** Projekt-Setup (pyproject.toml, Verzeichnisstruktur, Dependencies) und Domain-Modelle (Config, Models, Constants)
**Sprint:** 1
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #1 | Story | Als Entwickler will ich ein konfiguriertes Python-Projekt mit uv, damit die Entwicklung starten kann | Must | 3 | Done |
| #2 | Story | Als User will ich Config aus pyproject.toml laden, damit ich mutmut-win konfigurieren kann | Must | 5 | Done |
| #3 | Story | Als Entwickler will ich typisierte Domain-Modelle, damit alle Datenstrukturen validiert sind | Must | 5 | Done |
| #4 | Task | Architecture-Contracts (import-linter) einrichten | Must | 2 | Done |

**Acceptance Criteria:**
- [x] pyproject.toml mit allen Dependencies und Tool-Configs
- [x] Pydantic Config-Model validiert [tool.mutmut] Sektion
- [x] Alle Domain-Modelle mit Type Hints und Docstrings
- [x] import-linter Contracts für 4-Schichten-Architektur
- [x] hypothesis Property-Tests für Config und Models

---

### Epic 2: Mutation Engine Port

**Beschreibung:** Port der CST-basierten Mutation Engine aus mutmut 3.5.0 mit Windows-Anpassungen
**Sprint:** 2
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #5 | Story | Als User will ich Python-Code CST-basiert mutieren können, damit Mutations erzeugt werden | Must | 8 | Done |
| #6 | Story | Als User will ich Trampoline-basiertes Mutant-Switching, damit Mutanten effizient geladen werden | Must | 5 | Done |
| #7 | Story | Als User will ich Coverage-gestütztes Mutieren, damit nur relevante Code-Bereiche mutiert werden | Should | 5 | Done |
| #8 | Story | Als User will ich Type-Checker-Integration, damit Type-Error-Mutanten erkannt werden | Should | 3 | Done |

**Acceptance Criteria:**
- [x] mutation.py mit encoding='utf-8' portiert
- [x] node_mutation.py 1:1 übernommen
- [x] trampoline.py 1:1 übernommen
- [x] code_coverage.py mit encoding='utf-8' portiert
- [x] type_checking.py 1:1 übernommen
- [x] Unit-Tests für alle Mutations-Operatoren

---

### Epic 3: Windows Process Management

**Beschreibung:** Spawn-basierter Worker-Pool mit Timeout-Monitor (Kern des Windows-Ports)
**Sprint:** 3
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #9 | Story | Als User will ich parallele Mutation-Test-Ausführung via Worker-Pool, damit Tests schnell laufen | Must | 8 | Done |
| #10 | Story | Als User will ich Wall-Clock-Timeouts, damit Endlosschleifen erkannt werden | Must | 5 | Done |
| #11 | Story | Als User will ich Graceful Shutdown bei Ctrl+C, damit Teilergebnisse gespeichert werden | Must | 3 | Done |
| #12 | Task | Worker-Recovery bei Crashes implementieren | Must | 3 | Done (Sprint 24, v2.3.0 — ce0b736) |

**Acceptance Criteria:**
- [x] SpawnPoolExecutor startet N Worker via multiprocessing.spawn
- [x] Two-Queue-Architektur (task_queue + event_queue)
- [x] WallClockTimeout erkennt und killt überfällige Worker
- [x] Ctrl+C führt zu sauberem Shutdown mit gespeicherten Teilergebnissen
- [x] Worker überlebt unbehandelte Exceptions pro Task (Sprint 24, ce0b736) — **Korrektur 2026-06-11 (Sprint-27-Audit A2-EW-002):** die ursprünglich spezifizierte Slot-Restart-Logik (max 3 Neustarts, Backoff, Exhaustion) wurde NICHT implementiert; harter Worker-Tod (OS-Kill, nativer Crash) hängt den Lauf weiterhin. Siehe `_docs/audit/sprint_27_audit_findings.md`, Fix-Cluster C3.

---

### Epic 4: Orchestrator & Test Runner

**Beschreibung:** Orchestrierung des Mutation-Testing-Ablaufs und pytest-Integration
**Sprint:** 4
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #13 | Story | Als User will ich einen vollständigen Mutation-Testing-Lauf orchestriert haben | Must | 8 | Done |
| #14 | Story | Als User will ich einen Clean-Test-Run vor Mutation Testing | Must | 3 | Done |
| #15 | Story | Als User will ich Ergebnisse in SQLite persistiert haben | Must | 5 | Done |
| #16 | Task | PytestRunner implementieren (Test-Ausführung abstrahieren) | Must | 3 | Done |

**Acceptance Criteria:**
- [x] MutationOrchestrator koordiniert den gesamten Ablauf
- [x] Clean Test, Stats, Forced Fail vor Mutation Testing
- [x] SQLite-Schema kompatibel mit mutmut
- [x] Fortschrittsanzeige während des Laufs

---

### Epic 5: CLI & TUI Browser

**Beschreibung:** Click-basierte CLI und Textual-basierter TUI Result Browser
**Sprint:** 5
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #17 | Story | Als User will ich `mutmut-win run` ausführen können, damit Mutation Testing läuft | Must | 5 | Done |
| #18 | Story | Als User will ich `mutmut-win results/show/apply`, damit ich Ergebnisse verwalten kann | Must | 5 | Done |
| #19 | Story | Als User will ich `mutmut-win browse` für einen interaktiven TUI Browser | Should | 5 | Done |

**Acceptance Criteria:**
- [x] Alle 5 CLI-Commands implementiert
- [x] CLI-Tests via click.testing.CliRunner
- [x] TUI Browser aus mutmut portiert
- [x] Entry-Point in pyproject.toml konfiguriert

---

### Epic 6: E2E Tests & Integration

**Beschreibung:** E2E-Tests gegen mutmut-Testprojekte und Gesamtintegration
**Sprint:** 6
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #20 | Story | Als Entwickler will ich E2E-Tests gegen mutmut-Referenzprojekte, damit Korrektheit validiert ist | Must | 8 | Done |
| #21 | Task | 5 E2E-Testprojekte aus mutmut übernehmen und anpassen | Must | 3 | Done |
| #22 | Task | Mutation Testing auf eigenen Code (Meta-Test) | Should | 3 | Done (Duplikat von #65) |
| #23 | Task | Performance-Benchmark gegen mutmut (Linux-Vergleich) | Could | 2 | Done (Sprint 25, v2.4.0 — a52322b; benchmarks/-Suite + Baseline, Linux-Vergleich out of scope) |

**Acceptance Criteria:**
- [x] Alle 5 E2E-Testprojekte laufen erfolgreich
- [x] Snapshot-Vergleich gegen mutmut-Referenzergebnisse
- [x] Segfault-Mutant Windows-spezifisch behandelt
- [x] mutmut-win läuft auf eigenem Code (Sprint 24, #65 — paths_to_mutate = full src/mutmut_win/)

---

### Epic 7: File Setup Pipeline

**Beschreibung:** Port der File-Setup-Pipeline aus mutmut's __main__.py — kopiert Quelldateien nach mutants/, schreibt mutierte Trampoline-Dateien, richtet sys.path ein
**Sprint:** 8
**Release:** v0.2.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #24 | Story | Als Entwickler will ich walk_source_files + walk_all_files, damit Quelldateien navigierbar sind | Must | 3 | Done |
| #25 | Story | Als Entwickler will ich copy_src_dir + copy_also_copy_files, damit mutants/ befüllt wird | Must | 5 | Done |
| #26 | Story | Als Entwickler will ich setup_source_paths (sys.path-Manipulation), damit pytest aus mutants/ importiert | Must | 5 | Done |
| #27 | Story | Als Entwickler will ich write_all_mutants_to_file + create_mutants_for_file, damit mutierte Dateien auf Disk geschrieben werden | Must | 8 | Done |
| #28 | Task | Orchestrator-Integration: _generate_mutants delegiert an file_setup | Must | 3 | Done |

**Acceptance Criteria:**
- [x] `file_setup.py` im Domain Layer implementiert
- [x] Quelldateien werden korrekt nach mutants/ kopiert (Pfad-Struktur erhalten)
- [x] sys.path wird für mutants/-Import eingerichtet und nach dem Lauf wiederhergestellt
- [x] Mutierte Trampoline-Dateien werden korrekt auf Disk geschrieben
- [x] also_copy-Dateien werden kopiert
- [x] Unit-Tests mit tmp_path-Fixture, hypothesis für Pfad-Invarianten

---

### Epic 8: Test Mapping + Stats Caching

**Beschreibung:** Mutant-zu-Test-Mapping via mangled names und inkrementelles Stats-Caching in mutants/mutmut-stats.json
**Sprint:** 9
**Release:** v0.2.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #29 | Story | Als Entwickler will ich mangled_name_from_mutant_name + orig_function_and_class_names_from_key, damit Mutant-Namen decodiert werden | Must | 5 | Done |
| #30 | Story | Als Entwickler will ich tests_for_mutant_names, damit nur relevante Tests pro Mutant ausgeführt werden | Must | 8 | Done |
| #31 | Story | Als Entwickler will ich Stats load/save/collect_or_load, damit Test-Laufzeiten gecacht werden | Must | 5 | Done |
| #32 | Task | Type-Checker-Filter in Orchestrator verdrahten | Should | 3 | Done |
| #33 | Task | Orchestrator-Integration: Test-Assignment und Stats-Caching aktivieren | Must | 3 | Done |

**Acceptance Criteria:**
- [x] `test_mapping.py` im Domain Layer implementiert
- [x] `stats.py` im Application Layer implementiert
- [x] Stats werden in mutants/mutmut-stats.json mit encoding='utf-8' gespeichert
- [x] Inkrementelles Caching via Hash-Vergleich funktioniert
- [x] Mutanten laufen nur gegen relevante Tests (deutliche Laufzeit-Reduktion)
- [x] Type-Checker-Filter im Orchestrator aktiv
- [x] hypothesis Property-Tests für Name-Mangling-Roundtrips

---

### Epic 9: CLI show/apply + E2E-Validierung

**Beschreibung:** Vollständige Implementierung der `show`- und `apply`-Commands sowie End-to-End-Validierung der gesamten Pipeline
**Sprint:** 10
**Release:** v0.2.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #34 | Story | Als Entwickler will ich find_mutant + read_mutants_module + read_orig_module, damit Mutant-Dateien gelesen werden können | Must | 3 | Done |
| #35 | Story | Als User will ich get_diff_for_mutant (unified diff), damit ich sehe was ein Mutant verändert | Must | 5 | Done |
| #36 | Story | Als User will ich apply_mutant (CST-basierter Source-Ersatz), damit ich einen Mutanten in den Quellcode schreiben kann | Must | 5 | Done |
| #37 | Story | Als User will ich Live-Fortschrittsanzeige (print_stats), damit ich den Lauf-Fortschritt sehe | Should | 3 | Done |
| #38 | Task | End-to-End-Validierungstest (volle Pipeline auf simple_lib) | Must | 5 | Done (Sprint 24, v2.3.0 — b688f1f) |

**Acceptance Criteria:**
- [x] `mutant_diff.py` im Application Layer implementiert
- [x] `mutmut-win show <NAME>` zeigt echten unified diff
- [x] `mutmut-win apply <NAME>` schreibt CST-basierten mutierten Code in Quelldatei
- [x] Live-Fortschrittsanzeige während des Laufs aktiv
- [x] E2E-Validierungstest auf simple_lib läuft durch (Clean → Mutants → Results) — Sprint 24, b688f1f

---

### Epic 10: In-Process Stats + Trampoline Tracking

**Beschreibung:** Implementierung der Two-Phase Execution mit in-process pytest.main() für Stats und korrektem Trampoline-Hit-Tracking via _state globals — kritisch für korrekte Test-Zuordnung pro Mutant
**Sprint:** 11
**Release:** v0.3.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #39 | Story | Als Entwickler will ich _state.py module mit shared globals für Trampoline-Tracking | Must | 3 | Done |
| #40 | Story | Als Entwickler will ich record_trampoline_hit + MutmutProgrammaticFailException re-exports in __main__.py | Must | 3 | Done |
| #41 | Story | Als Entwickler will ich PytestRunner.run_stats() Rewrite mit pytest.main() + StatsCollector Plugin | Must | 8 | Done |
| #42 | Story | Als Entwickler will ich stats.py Update — collect_or_load_stats nutzt _state globals nach run_stats() | Must | 5 | Done |
| #43 | Task | Orchestrator — reale Test-Zuordnung aus Stats-Daten verdrahten | Must | 5 | Done |

**Acceptance Criteria:**
- [x] `_state.py` im Domain Layer mit `tests_by_mangled_function_name`, `current_test_name`, `reset_state()`, `record_trampoline_hit()`
- [x] `__main__.py` re-exportiert `record_trampoline_hit` und `MutmutProgrammaticFailException`
- [x] `PytestRunner.run_stats()` verwendet `pytest.main()` in-process mit `StatsCollector`-Plugin
- [x] Stats-Daten enthalten korrekte Test-Zuordnung via mangled names
- [x] Orchestrator weist nur relevante Tests pro Mutant zu (deutliche Laufzeit-Reduktion)
- [x] hypothesis Property-Tests für `record_trampoline_hit` State-Invarianten

---

### Epic 11: Feature Completeness + E2E Validation

**Beschreibung:** Port aller verbleibenden mutmut-Funktionen für 100% Feature-Parität und vollständige E2E-Validierung auf Referenzprojekten
**Sprint:** 12
**Release:** v0.3.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #44 | Story | Als User will ich guess_paths_to_mutate() in config.py, damit paths_to_mutate automatisch ermittelt wird | Must | 3 | Done |
| #45 | Story | Als Entwickler will ich ListAllTestsResult + inkrementelle Stats, damit Stats-Updates effizient sind | Should | 5 | Done |
| #46 | Story | Als User will ich CLI-Commands tests-for-mutant und time-estimates, damit ich Test-Zuordnung und Zeitschätzungen abrufen kann | Should | 5 | Done |
| #47 | Story | Als User will ich CI/CD-Stats-Export (save_cicd_stats + CLI), damit ich Mutation-Testing in CI/CD integrieren kann | Should | 5 | Done |
| #48 | Story | Als Entwickler will ich Type-Checker-Helpers vollständig (MutatedMethodsCollector, MutatedMethodLocation, FailedTypeCheckMutant, group_by_path) | Must | 5 | Done |
| #49 | Task | Full E2E Validation — mutmut-win run auf simple_lib + my_lib, Ergebnisvergleich mit mutmut-Referenz | Must | 8 | Done (Sprint 24, v2.3.0 — b688f1f) |
| #50 | Task | exceptions.py — MutmutProgrammaticFailException, BadTestExecutionCommandsException, InvalidGeneratedSyntaxException | Must | 3 | Done |

**Acceptance Criteria:**
- [x] `guess_paths_to_mutate()` ermittelt src/-Verzeichnisse automatisch wenn `paths_to_mutate` nicht konfiguriert
- [x] `ListAllTestsResult` in `stats.py` implementiert, inkrementelle Updates möglich
- [x] `tests-for-mutant` und `time-estimates` CLI-Commands funktionieren
- [x] `save_cicd_stats` + CLI-Command `export-cicd-stats` implementiert
- [x] Alle Type-Checker-Helpers in `type_checking.py` vollständig portiert
- [x] E2E-Validierung: mutmut-win-Ergebnisse stimmen mit mutmut-Referenz überein (simple_lib + my_lib) — Sprint 24, b688f1f
- [x] `exceptions.py` enthält alle fehlenden Exception-Klassen

---

### Epic 12: Hardening — Orphan-Prozess-Schutz (Sprint 13)

**Beschreibung:** Windows Job Objects für zuverlässigen Orphan-Prozess-Schutz. Verhindert CPU-Überhitzung wenn der Hauptprozess unerwartet stirbt.
**Sprint:** 13
**Release:** v0.5.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #51 | Story | Als User will ich dass Worker-Prozesse automatisch sterben wenn mutmut-win crasht | Must | 5 | Done |
| #52 | Task | `process/job_object.py` — ctypes Win32 Job Object Wrapper | Must | 3 | Done |
| #53 | Task | `executor.py` Integration (create/assign/close) + Graceful Degradation | Must | 3 | Done |
| #54 | Task | Deterministischer Test: Job Object kill-on-close Verhalten | Must | 2 | Done (Sprint 24, v2.3.0 — 6df3283) |

**Acceptance Criteria:**
- [x] `job_object.py` implementiert `create_kill_on_close_job()`, `assign_process_to_job()`, `close_job()`
- [x] SpawnPoolExecutor erstellt Job Object im `__init__`, weist Worker in `start()` zu, schließt in `shutdown()`
- [x] Bei Parent-Tod: ALLE Worker + deren pytest-Subprozesse werden vom OS gekillt
- [x] Graceful Degradation: Warning statt Crash wenn Job Object nicht erstellt werden kann
- [x] Deterministischer Test beweist kill-on-close Verhalten (Sprint 24, tests/integration — 6df3283)
- [x] DoD aktualisiert: E2E-Lauf darf keine Orphan-Prozesse hinterlassen

---

### Epic 13: Erweiterte Mutationsoperatoren (Sprint 14-20)

**Beschreibung:** 7 neue Mutationsoperatoren inspiriert von Stryker.NET und cargo-mutants. Bringt mutmut-win auf Stryker-Niveau mit Regex-Mutation als Alleinstellungsmerkmal.
**Sprint:** 14-20 (je 1 Operator pro Sprint)
**Release:** v1.0.0

| Issue | Typ | Titel | Sprint | Priorität | SP | Status |
|-------|-----|-------|--------|-----------|-----|--------|
| #55 | Story | Regex-Mutationen (Quantifier, CharClass, Anchors) | 14 | Must | 8 | Done |
| #56 | Story | Math-Methoden (ceil↔floor, min↔max, abs→x, sum→0) | 15 | Must | 3 | Done |
| #57 | Story | Return Value Replacement (return expr → return None) | 16 | Must | 2 | Done |
| #58 | Story | Conditional Expression (x if c else y → x / y) | 17 | Must | 2 | Done |
| #59 | Story | Statement Removal (void calls + raise → pass) | 18 | Must | 5 | Done |
| #60 | Story | Collection-Methoden (sorted→identity, filter entfernen) | 19 | Must | 3 | Done |
| #61 | Story | or-Default (x or default → x / default) | 20 | Should | 2 | Done |

**Acceptance Criteria:**
- [x] Alle 7 Operatoren in `mutation_operators` registriert
- [x] Regex-Mutator in separatem Modul `regex_mutation.py`
- [x] Statement Removal mit Exclusion-Liste (print, logger, warnings)
- [x] or-Default nur in Zuweisungskontexten
- [x] Alle generierten Regex via `re.compile()` auf Validität geprüft
- [x] Unit Tests + hypothesis Property-Tests für jeden Operator
- [x] mutmut-win run auf eigenem Code (Dogfooding) nach jedem Sprint — eingeschränkt, siehe #65
- [x] Mutation Score des neuen Operators gemessen

---

### Epic 14: Hardening — CLI-Flags, Dogfooding, Hooks (Sprint 21)

**Beschreibung:** 10 CLI-Flags für Automation/CI/CD, Dogfooding-Fix (Worker ModuleNotFoundError), Hook-Debugging.
**Sprint:** 21
**Release:** v1.0.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #62 | Bug | H-06: Worker ModuleNotFoundError bei editable install + spawn | Must | 5 | Done |
| #63 | Feature | H-07: 10 CLI-Flags Tier 1-3 (--paths-to-mutate, --min-score, --output json, --since-commit, etc.) | Must | 8 | Done |
| #64 | Bug | H-01–H-04: Hooks feuern nicht automatisch in Claude Desktop | Must | 5 | Done |
| #65 | Task | Dogfooding: mutmut-win auf eigenem Code erfolgreich ausführen | Must | 3 | Done (Sprint 24, v2.3.0 — a0b5f61) |
| #67 | Task | H-05: also_copy .venv-Symlink review (filed retroactively 2026-05-22) | Should | 2 | Done (Sprint 25, v2.4.0 — f23e150) |

**Acceptance Criteria:**
- [x] `mutmut-win run --paths-to-mutate src/mutmut_win/regex_mutation.py` funktioniert
- [x] `mutmut-win run --min-score 80` gibt Exit 1 wenn Score < 80%
- [x] `mutmut-win run --output json` gibt valides JSON zurück
- [x] `mutmut-win run --since-commit HEAD~1` mutiert nur geänderte Dateien
- [x] `mutmut-win run --dry-run` zeigt Mutanten-Anzahl ohne Ausführung
- [x] Worker-Prozesse können mutmut_win importieren (Dogfooding-Import funktioniert)
- [x] Alle Hooks manuell verifiziert (SessionStart verifiziert live in Sprint 22)
- [x] sprint-gate.sh sucht in `_docs/sprint backlogs/` statt `find . -maxdepth 4`
- [x] Vollständiger Dogfooding-Lauf auf gesamtem `src/mutmut_win/` (Sprint 24, #65)

---

### Epic 15: v2.0.x Stabilization (Sprint 22)

**Beschreibung:** Post-Release-Stabilisierung nach v2.0.0: Timeout-Diagnostics für Worker-Hangs auf Windows, Bug-Fix-Wave aus Downstream-Dogfooding, Housekeeping & Backlog-Sync.
**Sprint:** 22
**Release:** v2.1.0

| Issue/PR | Typ | Titel | Priorität | SP | Status |
|----------|-----|-------|-----------|-----|--------|
| PR #66 | Bug | Bug #4: skip typing.cast() first-arg mutations (eliminate unkillable equivalents) | Must | 3 | Done |
| — | Task | v2.0.x Timeout Diagnostics-Serie (subprocess timeouts, DEVNULL → temp-file, DB last_output) | Must | 5 | Done (commits 6ad5fbf / c0e6056 / 638a9be / 77c7828) |
| — | Task | Housekeeping: 42 GitHub-Issues sync, MEMORY.md, sprint state refresh | Should | 3 | Done |
| — | Task | v2.1.0 Tag + Release | Should | 2 | Done |

**Acceptance Criteria:**
- [x] `typing.cast()` und `cast()` First-Arg Mutations werden in MutationVisitor übersprungen (Subtree-Skip + Call-Level-Filter)
- [x] 5 neue Unit Tests in `tests/unit/test_typing_cast_skip.py`
- [x] Full suite 564 passed, 3 skipped
- [x] `semgrep --config auto` 0 Findings auf src/ + tests/unit/ + tests/integration/
- [x] uv.lock synchron mit pyproject.toml (v2.1.0)
- [x] Annotated Tag `v2.1.0` auf HEAD, GitHub Release v2.1.0 published

---

### Epic 16: v2.0.x Reliability Wave (Sprint 23)

**Beschreibung:** Drei kritische Bugs aus dem v2.0.4-Dogfooding im Downstream-Projekt critique-model-service (Living-Document-Bug-Report): Multi-line-`or` SyntaxError-Mutanten (Bug #1), Default-Parameter trampoline equivalents (Bug #3), Hypothesis-Timeout-vs-Kill (Bug #5, Stopgap). Der vierte Downstream-Bug (#69, Bug #2 sibling packages) wurde aus Sprint 23 deferred und in Sprint 25 geliefert.
**Sprint:** 23 (+ #69 in Sprint 25)
**Release:** v2.2.0 (#69: v2.4.0)

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #68 | Bug | Multi-line `if A or B or C:` produziert unimportable SyntaxError-Mutant (Bug #1) | Must | 8 | Done (fb82914) |
| #70 | Bug | Default-Parameter trampoline equivalents — skip-the-mutation (Bug #3) | Must | 3 | Done (d74eaba) |
| #71 | Bug | Hypothesis infinite-loop → TIMEOUT statt KILLED — `--treat-timeout-as-kill` Stopgap (Bug #5) | Must | 5 | Done (770240f; echter Fix in Epic 17) |
| #69 | Bug | Sibling packages not copied to mutants/ workdir (Bug #2) | Medium | 5 | Done (Sprint 25 — 852a276) |

**Acceptance Criteria:**
- [x] Mutator skippt `or`-Removal bei multi-line `BooleanOperation`; generierte Mutanten parsen via `ast.parse`
- [x] `MutationVisitor` skippt Mutationen auf `Param.default`-Subtrees (Body-Mutationen unverändert)
- [x] CLI-Flag `--treat-timeout-as-kill` passt Score-Berechnung in `run` und `results` an
- [x] `--extra-paths-to-copy` Flag + `extra_paths` Config-Feld; Pfade werden kopiert und im Worker-PYTHONPATH aufgelöst
- [x] Sprint-23-Gates: 578 passed / 3 skipped, semgrep 0 findings (ca26e65)

---

### Epic 17: Polish + True Infinite-Loop Detection (Sprint 26)

**Beschreibung:** Echte Infinite-Loop-Detection statt Timeout-Heuristik — endgültiger Fix für Bug #5: psutil-basierter ProcessMonitor-Thread + Triple-Check-Classifier (CPU/Output/Status) + `IlForensics` mit Confidence-Band, als JSON in der DB persistiert. Alleinstellungsmerkmal am Markt (kein anderes Mutation-Tool hat explainable IL-Detection). Plus `--version` Single Source of Truth.
**Sprint:** 26
**Release:** v2.5.0 (+ Hotfix v2.5.1)
**Hinweis:** Im sprint_26_backlog ursprünglich als „Epic 16 (Detection Quality)" angekündigt; die Nummer 16 war bereits durch Sprint 23 vergeben → hier als Epic 17 geführt.

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #71 | Feature | Bug #5 true infinite-loop detection — psutil + forensics + confidence (re-opened) | Must | 13 | Done (b5246d8; Hotfix a14e320) |
| #72 | Bug | `--version` reportet 2.0.4 statt pyproject — single source of truth via importlib.metadata | Must | 1 | Done (34ea930) |

**Acceptance Criteria:**
- [x] `process/loop_monitor.py`: `ProcessMonitor`-Thread (0,5-s-Polling, rolling window) + purer `classify_samples()`-Classifier
- [x] Triple-Check-Rule: mean(CPU) ≥ 70 % AND Output-Growth < 1 KB AND running_ratio ≥ 0,8 → `killed_by_infinite_loop` (exit code 38)
- [x] `IlForensics`-Pydantic-Model als JSON-Spalte persistiert; gerendert von `mutmut-win show`
- [x] 5 neue `[tool.mutmut]`-Keys (`infinite_loop_*`) + CLI-Flags `--no-infinite-loop-detection` / `--infinite-loop-cpu-threshold`
- [x] Graceful Degradation ohne psutil (ImportError → legacy Timeout-Pfad)
- [x] `__version__` via `importlib.metadata` mit PackageNotFoundError-Fallback für editable installs
- [x] Sprint-26-Gates: 608 passed / 5 skipped, semgrep 0 findings (c478c93)
- [x] v2.5.1-Hotfix: psutil.Process-Instanzen pro PID gecacht (frische Instanzen liefern immer cpu_percent = 0.0)

**Korrektur 2026-06-11 (Sprint-27-Audit):** Die AC „IlForensics … gerendert
von `mutmut-win show`" war zum Release-Zeitpunkt NICHT erfüllt — es existiert
kein Rendering-Code (A4-UI-004), und die Forensik wird nie persistiert
(A2-JT-004). Nacharbeit in Fix-Cluster C5 (Sprint 29+).

---

### Epic 18: Full Source Audit (Sprint 27)

**Beschreibung:** Analysis-only-Audit aller 29 `src/mutmut_win/`-Module in 4 Stages (Engine, Process, Pipeline/Persistenz, UI/Querschnitt) — ausgelöst durch den W4.11-Downstream-Report. 12 read-only Subagenten, jeder S1/S2-Verdacht in-process verifiziert, 12 Top-Findings hauptsession-nachverifiziert.
**Sprint:** 27
**Release:** — (kein Code-Increment; Findings-Report)

| Item | Typ | Titel | Status |
|------|-----|-------|--------|
| A1 | Audit | Mutations-Engine (41 Findings, 11 S1) | Done |
| A2 | Audit | Process & Execution (54 Findings, 2 S1) | Done |
| A3 | Audit | Pipeline & Persistenz (65 Findings, 2 S1) | Done |
| A4 | Audit | UI & Querschnitt (41 Findings, 1 S1) | Done |

**Ergebnis:** `_docs/audit/sprint_27_audit_findings.md` — 201 raw / ~180
unique Findings (15 S1), 9 Fix-Cluster C1–C9. Semgrep 0 Findings; pip-audit
nicht erhoben (SSL). Wichtigste Meta-Befunde: #12-Restart-Logik war nie
implementiert (Epic-3-AC korrigiert); Sprint-26-Forensics-AC war nie erfüllt
(Epic-17-Korrektur oben).

---

### Epic 19: Source Protection & Codegen Correctness (Sprint 28)

**Beschreibung:** Fixing-Sprint 1 aus dem Audit: W4.11-Blocker schließen (BUG-1/BUG-2), destruktive Bugs eliminieren (Cluster C1), Clean-Run-Brecher + parenless-yield-Klasse der Codegen-Schicht fixen (Cluster C2). Detail: `_docs/sprint backlogs/sprint_28_backlog.md`.
**Sprint:** 28
**Release:** v2.6.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #74 | Bug | BUG-2: clean_run_timeout-Config-Feld + präzise Fehlermeldung | Must | 2 | Done (bbe59d2) |
| #78 | Bug | Sicherheitsnetz scharf schalten (validate-then-write) + Operator-Crash-Guards | Must | 3 | Done (af7a431) |
| #75 | Bug | Quell-Schutz: Absolutpfad-Guard + apply class-aware/Backup/atomar/newline | Must | 5 | Done (07b29fe) |
| #73 | Bug | Parenless-yield-Klasse: Safe-Unwrap-Helper für 5 Operatoren (BUG-1) | Must | 8 | Done (2a14182) |
| #77 | Bug | Mutants-Dict auf Modulebene (Enum/NamedTuple Clean-Run-Brecher) | Should | 5 | Done (5dc8c48) |
| #76 | Bug | Wrapper-Codegen: self/args/kwargs/*args/async-gen | Should | 8 | Done (5031032) |

**Acceptance Criteria (Sprint-Ebene):**
- [x] Adversarial-Fixture-Gate: jede generierte Mutanten-Datei kompiliert; Fixture-Clean-Run grün
- [x] W4.11-Repro-Formen (§1.2/§1.3) erzeugen keine invaliden Mutanten mehr
- [x] `clean_run_timeout = 900` wirkt nachweislich (Config-Roundtrip-Test)
- [x] Absolute paths_to_mutate können keine Quelldatei mehr überschreiben
- [x] apply patcht die korrekte Klasse, mit Backup + atomarem Write + Newline-Erhalt
- [x] Quality Gates: pytest 672 passed (≥ 630 ✓), ruff 0, mypy 0 neue, semgrep 0 — **Abweichungen dokumentiert:** lint-imports vorbestehend rot (gegen Sprint-Start-Stand verifiziert → Sprint 29); Mutation-Score-Gate deferred bis C8-Fix (Backlog-Gates-Tabelle)

---

### Epic 20: Runtime Reliability (Sprint 29)

**Beschreibung:** Fixing-Sprint 2 aus dem Audit (Cluster C3 + C4 + lint-imports-Nachtrag): die letzten beiden S1-Findings — beide Abbruch-/Fehlerpfad-Hänger (Queue-Shutdown, Worker-Tod) —, die dreifach gebrochene Timeout-Architektur (Multiplier als absolute Sekunden, ungelesene per-Task-Budgets, toter Monitor), Prozess-Hygiene und die seit Sprints nicht zur Realität passenden import-linter-Contracts (ADR). Detail: `_docs/sprint backlogs/sprint_29_backlog.md`.
**Sprint:** 29
**Release:** v2.7.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #79 | Bug | Shutdown-Hänger: Queues schließen + finally um Event-Loop (EW-001 S1) | Must | 3 | Done (4257f3c) |
| #80 | Bug | Worker-Liveness in get_events + synthetisches Completion (EW-002 S1) | Must | 5 | Done (0a06b3d) |
| #82 | Bug | Prozess-Hygiene: kill-tree, Log-Sweep, sys.executable-Worker | Must | 5 | Done (a2f6037 — Design-Upgrade: per-Task-Job-Objects, da ppid-Scans tote Zwischenglieder nicht überbrücken) |
| #81 | Bug | Per-Task-Timeouts end-to-end; toten Timeout-Monitor entfernen; IL-Fenster durchreichen | Must | 8 | Done (a955b89, −464 Zeilen) |
| #83 | Bug | Job-Object-Polish: use_last_error, argtypes, Least-Privilege | Should | 3 | Done (c781d62/3b9512e, Worktree-Subagent) |
| #84 | Task | import-linter-Contracts per ADR an reale Architektur angleichen | Should | 3 | Done (243206a — KEPT, Gate läuft in pytest) |

**Acceptance Criteria (Sprint-Ebene):**
- [x] Abbruch (Ctrl+C/Crash) mit gefüllter Task-Queue → Prozess endet binnen Frist, keine Orphans (Watchdog-Integration-Test: alt 30-s-Hänger, neu Sofort-Exit)
- [x] Hart gekillter Worker → Lauf endet regulär, betroffene Tasks als „suspicious/worker died", Rest abgearbeitet
- [x] `timeout_multiplier` wirkt nachweislich multiplikativ pro Task (`task.timeout_seconds` wird im Worker gelesen; hypothesis-Property)
- [x] `WallClockTimeout`/`TaskTimedOut` entfernt; README-Architektur-Sektion korrigiert
- [x] `uv run lint-imports` → KEPT (0 Verletzungen) mit ADR-begründeten Contracts; Gate läuft jetzt IN der pytest-Suite
- [x] Nach Sprint 29: alle 15 S1-Audit-Findings geschlossen ✓

---

### Epic 21: IL Detection Honesty (Sprint 30)

**Beschreibung:** Fixing-Sprint 3 aus dem Audit (Cluster C5): Das v2.5-Flaggschiff-Feature löst sein Versprechen ein — Forensik wird persistiert und gerendert, der CI/CD-Export zählt IL-Kills, der auf Windows zum Single-Check degenerierte Triple-Check wird ehrlich (echtes Output-Signal via PYTHONUNBUFFERED, status-neutral auf win32, Confidence-Cap). Detail: `_docs/sprint backlogs/sprint_30_backlog.md`.
**Sprint:** 30
**Release:** v2.8.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #85 | Bug | Forensik-Persistenz: save_result erhält event.forensics (JT-004) | Must | 2 | Done |
| #86 | Bug | CICD-Export: killed_by_infinite_loop-Bucket (OS-002) | Must | 2 | Done |
| #87 | Bug | Rendering: show-Forensik-Panel + Browser-IL-Awareness (UI-004/008) | Must | 5 | Done |
| #88 | Bug | Classifier-Ehrlichkeit Windows: Output-Signal, neutraler Status, Confidence-Cap, Guards (JT-001/002/009/010/011/015/018, JT-012/014) | Must | 8 | Done |
| #89 | Spike | io_counters-Delta als Sleeping-Ersatz (timeboxed, Entscheid-Gate) | Should | 5 | Done (negativ als Sleeping-Ersatz, eingebaut als Progress-Veto) |
| #90 | Bug | Test-/Doku-Ehrlichkeit: Windows-realistische Fixtures, nüchterne Prosa (JT-016) | Should | 3 | Done |

**Acceptance Criteria (Sprint-Ebene):**
- [x] `mutmut-win show <il-mutant>` zeigt das Forensik-Panel (Verdict, Confidence, CPU, Output-Growth, Ratio, Samples, Tail); NULL-Forensik (Prä-v2.8) bleibt sauber
- [x] run-Gate, `results` und `export-cicd-stats` melden auf identischer Datenlage EINEN Score (IL-Kills überall gezählt)
- [x] Browser zeigt IL-Kills mit Emoji/Spalte, filtert sie als Kills, Detail-Text korrekt
- [x] Auf win32 stammt kein „high"-Confidence-Verdict mehr aus einem Zwei-Signal-Check; Forensik weist genutzte Signale + Sampler-Fehler aus
- [x] #89-Entscheid dokumentiert (Einbau ODER Negativergebnis im Audit-Doc) — BEIDES: Veto eingebaut, Negativergebnis dokumentiert
- [x] Quality Gates: pytest ≥ 700 (719), ruff 0, mypy 0 neue, semgrep 0, lint-imports KEPT (in-suite)

---

### Epic 22: Feature Truth & Score Integrity (Sprint 31)

**Beschreibung:** Fixing-Sprint 4 aus dem Audit (Cluster C6+C7): Die beiden
tot beworbenen Features werden ehrlich — der Type-Check-Filter (auf drei
Ebenen gebrochen: Windows-Erkennung bricht den Lauf ab, Matching trifft nie,
Kills erreichen die DB nicht) wird end-to-end repariert; Coverage-Gating
(`mutate_only_covered_lines`, seit dem Subprozess-Rewrite ohne Brücke) wird
per timeboxed Spike entschieden: Einbau oder ehrliche Deaktivierung. Die
Score-Pipeline wird lückenlos wahr: vollständige Buckets + Summen-Invariante,
korrekte Exit-Code-Map (−24-Dublette, 0xC0000005, Exit-2-Collection-Kills),
CI-erkennbarer Ctrl-C-Abbruch, Orphan-Bereinigung, score im JSON-Kanal.
Detail: `_docs/sprint backlogs/sprint_31_backlog.md`.
**Sprint:** 31
**Release:** v2.9.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #91 | Bug | Status-Wahrheit: Exit-Code-Map + Summary-Buckets + results-Rendering (EW-020, QX-025, EW-004, UI-009) | Must | 5 | Done |
| #92 | Bug | type_checking.py härten: Erkennung, Robustheit, Severity (CM-008/010/011) | Must | 5 | Done |
| #93 | Bug | Type-Check-Filter end-to-end: Matching, Schnittmenge, Persistenz, Guard (CM-002, OS-003/009/010) | Must | 8 | Done |
| #94 | Bug | Ctrl-C-Ehrlichkeit: was_interrupted, unchecked, Exit 130, Gate-Skip (OS-005) | Must | 3 | Done |
| #95 | Spike+Fix | Coverage: Spike → Entscheid → Einbau ODER ehrliche Deaktivierung (CM-003/OS-011, CM-013) | Must | 5 | Done (JA-Pfad: reaktiviert) |
| #96 | Bug | DB-Orphan-Zeilen: results = Vereinigungsmenge aller Läufe (OS-012-Orphan-Teil) | Should | 5 | Done |
| #97 | Bug | CI-Kanal: score im JSON, 0-Mutanten-Gate-Kommunikation (OS-014, OS-026) | Should | 2 | Done |

**Acceptance Criteria (Sprint-Ebene):**
- [x] Ein Windows-üblicher Type-Checker-Aufruf (`mypy.exe`, `uv run mypy`) bricht den Lauf nicht mehr ab; der E2E-Test fängt mit echtem mypy exakt den erwarteten Mutanten
- [x] Type-Check-Kills erscheinen in results UND CICD-Export (Drei-Kanal-Konsistenz erweitert); Subset-Läufe zählen keine fremden caught
- [x] Kein Status zählt in den Nenner ohne sichtbares Bucket — Summen-Invariante (Buckets + unchecked == total) als Test
- [x] Ctrl-C-Lauf ist in CI erkennbar: Exit 130, was_interrupted, min-score-Gate übersprungen mit Meldung
- [x] `mutate_only_covered_lines` lügt nicht mehr still: funktioniert ODER erklärt sich mit klarem Fehler (Entscheid + ggf. Negativergebnis im Audit-Register dokumentiert)
- [x] Quality Gates: pytest ≥ 745, ruff 0, mypy 0 neue, semgrep 0, lint-imports KEPT

---

### Epic 23: Pipeline Hygiene (Sprint 32)

**Beschreibung:** Letzter Fixing-Sprint des Audit-Zyklus (Cluster C8 +
C9-Top + 4 user-bestätigte Neuzugänge + Dogfooding-Gate): Runner-Fehlschläge
zeigen Output und vergiften nie den Stats-Cache; die DB übersteht
Upgrades/Races/Exceptions; das Staging kann weder via `..` entkommen noch
vergeistern (Deletion-Sync inkl. .meta-Orphans = OS-012 komplett,
Fingerprint-Invalidierung); Config/CLI validieren ehrlich; der JSON-Kanal
ist rein; das Projekt wendet seine eigenen Regeln auf sich an (Format-Gate,
pytest-Kanon, semgrep auf tests/, erstes echtes Dogfooding mit
Mutation-Score). Abschluss: C9-Rest-Triage in einen kuratierten
Maintenance-Abschnitt. Detail: `_docs/sprint backlogs/sprint_32_backlog.md`.
**Sprint:** 32
**Release:** v2.10.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #98 | Hygiene+Gate | Selbst-Hygiene-Fundament (Format/pytest-Kanon/semgrep) + Dogfooding-Pilot — zweiphasig | Must | 5 | Done |
| #99 | Bug | Runner-Diagnose & Stats-Wahrheit (RN-001/002/003, OS-006/007) | Must | 8 | Done |
| #100 | Bug | DB-Härtung: Lesepfad-Migration, Connection-Close, Race, Surrogates (FD-001/006/007/011) | Must | 5 | Done |
| #101 | Bug | Staging-Hygiene: Containment, Deletion-Sync, Fingerprint, atomare .meta (FD-002/003/004/005/009, OS-008, CM-009) | Must | 8 | Done |
| #102 | Bug | Config-/CLI-Wahrheit (CM-004/005/006, UI-005) | Must | 5 | Done |
| #103 | Bug | CI-Output-Disziplin (UI-006, QX-003) | Must | 3 | Done |
| #104 | Doku | C9-Rest-Triage + Audit-Schlussstrich | Should | 2 | Done |

**Acceptance Criteria (Sprint-Ebene):**
- [x] Fehlgeschlagene Runner-Phasen zeigen pytest-Output + dekodierten Exit; der Stats-Cache wird bei Fehlschlag NIE überschrieben oder stale geladen
- [x] Prä-v2.5-Caches crashen results/browse nicht; keine gelockte DB unter Exception (WinError 32); Migrations-Race tolerant
- [x] `..`-Einträge können mutants/ nicht verlassen; gelöschte Quellen verschwinden aus Staging samt .meta (OS-012 komplett); Restore/Config-Wechsel invalidieren; --force meldet ehrlich; korrupte .meta blockt keine Läufe mehr
- [x] `--max-children 0` ist Validierungsfehler; Config-Typos warnen mit Vorschlag; ungültige --since-commit-Ref bricht ab statt Exit 0; --debug zeigt Tracebacks
- [x] `json.loads(stdout)` funktioniert bei --output json; kein UnicodeEncodeError auf cp1252
- [x] Hygiene-Gates verankert: ruff format --check, pytest ohne Flag, semgrep inkl. tests/; Dogfooding-Pilot gelaufen, Score dokumentiert
- [x] Audit-Zyklus formal beendet: C9-Rest als kuratierter Maintenance-Abschnitt, Register mit Schlussbilanz
- [x] Quality Gates: pytest ≥ 800, ruff 0, format-check 0, mypy 0 neue, semgrep 0 blocking, lint-imports KEPT

---

### Epic 24: Maintenance 1 — Runtime & Self-Run (Sprint 33)

**Beschreibung:** Erster bedarfsgetriebener Maintenance-Sprint. Leitmotiv:
die drei S2-Blocker zwischen Projekt und breitem Dogfooding — gemessener
Startup-Sockel im Timeout-Modell (DOG-001; 175/244 Pseudo-Timeouts im
Piloten), no-tests-Producer (QX-007; ungemappte Mutanten laufen heute die
Vollsuite), Trampolin-Importketten-Entkopplung (QX-001; entfernt den
Architektur-Skip im Build-Artefakt). Messziel: Dogfooding-Pilot brutto
≥ 80 % (vorher 24,2 %). Detail: `_docs/sprint backlogs/sprint_33_backlog.md`.
**Sprint:** 33
**Release:** v2.11.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #105 | Bug | DOG-001: additiver Startup-Sockel im Timeout-Modell | Must | 5 | Done (`28a718f`) |
| #106 | Bug | QX-007: no-tests-Producer (exit 33) statt Vollsuite | Must | 5 | Done (`6430d18`) |
| #107 | Bug | QX-001+QX-020: Trampolin-Importkette → Kernel-Modul; Architektur-Skip fliegt | Must | 8 | Done (`4659d36`) |
| #108 | Bug | UI-007: Browser-Diff = show-Diff (Single Source) | Should | 5 | Done (`fbed4cd`) |
| #109 | Bug | Browser/CLI-Robustheit (UI-010/011/013/016) | Should | 5 | Done (`4b87423`) |
| #110 | Bug | Hygiene-Kleinkram (QX-017/018, QX-019-Rest, DOG-002) | Should | 3 | Done (`ce907d0`) |

**Acceptance Criteria (Sprint-Ebene):**
- [x] Dogfooding-Pilot (gleiche Module wie Sprint 32) erreicht brutto ≥ 80 % — **86,9 %** (Zwischengate UND Abschluss, 0 Timeouts)
- [x] Mutanten ohne gemappte Tests werden als `no tests` verbucht (nie dispatcht); Vollsuite-Fallback nur ohne Stats, weiterhin laut
- [x] Der QX-001-Architektur-Skip ist ENTFERNT — lint-imports hält auch im Trampolin-Artefakt
- [x] Score-Verschiebungen im Changelog ausgewiesen — Release-Notes-Abschnitt „Score shift, stated plainly" (no_tests verlässt den Nenner, Vollsuite-Zufallskills den Zähler)
- [x] Quality Gates: pytest 868, ruff 0, format-check 0, mypy 0 neue, semgrep 0 (src+tests), lint-imports KEPT überall (inkl. Artefakt)

---

### Epic 25: Maintenance 2 — Final Sweep (Sprint 34)

**Beschreibung:** Letzter Sprint vor der geplanten Entwicklungspause
(User-Auftrag 2026-06-11: „alle noch offenen Topics, danach Entwicklung
vorerst abschließen"). Inhalt: der VOLLSTÄNDIGE Maintenance-Pool-Rest
(13 Einträge, 7×S3 + 6×S4) plus die vier offenen Entscheidungen aus
MEMORY.md (--treat-timeout-as-kill, Release-Policy, Shrink-Storm,
BUG_REPORT_9). Jedes Item endet als „gefixt (Commit-Ref)" oder „formal
geschlossen (dokumentierte Begründung)". Detail:
`_docs/sprint backlogs/sprint_34_backlog.md`.
**Sprint:** 34
**Release:** v2.12.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #111 | Bug | RN-006 + RN-012: Runner-Phasen-Wahrheit (Forced-Fail, IMPORTMISMATCH) | Must | 5 | Done (`8251509`) |
| #112 | Bug | RN-013: Arg-Koerzierung via shlex (beide Felder, str+list) | Must | 3 | Done (`36d70e6`) |
| #113 | Bug | FD-008: Sanitiser entfernt `[tool.uv.sources.<pkg>]`-Subtables | Must | 3 | Done (`a72861f`) |
| #114 | Bug | QX-005/006/023-Rest: Exception-Hygiene | Must | 5 | Done (`2f3e7da`) |
| #115 | Bug | UI-012/014/015: Resolver, patch-fähige Diffs, Alignment | Should | 5 | Done (`b08a9a4`) |
| #116 | Bug | RN-010/011: sitecustomize-Hygiene | Should | 3 | Done (`9fa333f`) |
| #117 | Chore | Abschluss-Dossier: Deprecation, Release-Policy, formale Schließungen, Pausenzustand | Must | 3 | Done (`fa590ac`) |

**Acceptance Criteria (Sprint-Ebene):**
- [x] Maintenance-Pool-Tabelle = 0 Einträge (12/13 gefixt via #111–#116, OS-012-Rest formal geschlossen via #117)
- [x] MEMORY.md „Open Decisions" = alle 4 entschieden/geschlossen
- [x] Dogfooding-Pilot (gleiche Module) hält brutto ≥ 80 % — **85,1 %** (6 Kaltstart-Timeouts re-run-verifiziert als Kills → 87,6 % effektiv); `--since-commit`-Läufe dokumentiert (inkl. Stats-Cache-Lehrstück)
- [x] Quality Gates: pytest 951 grün, ruff 0, format-check 0, mypy **14 = neue Baseline** (vorher 20, 0 neue), semgrep 0 (voller Sweep), lint-imports KEPT inkl. Artefakt
- [x] Pausenzustand dokumentiert (MEMORY.md, state.md; Release Notes bei v2.12.0)

---
## Maintenance-Backlog (Audit-Reste, epic-los)

> Ergebnis der C9-Rest-Triage (#104, Sprint 32): Die nach fünf
> Fixing-Sprints (28–32) bewusst nicht behobenen Findings — nichts davon
> korrumpiert Daten, blockiert Läufe oder belügt CI. Severity-sortiert;
> Kandidatenpool für bedarfsgetriebene Maintenance, KEIN Sprint-Versprechen.
>
> **Sprint 33 (v2.11.0) hat 13 Einträge abgeräumt** (DOG-001, QX-007,
> QX-001, QX-020, QX-017, QX-018, QX-019, DOG-002, UI-007, UI-010,
> UI-011, UI-013, UI-016 → Issues #105–#110).
>
> **Sprint 34 (v2.12.0, „Final Sweep") hat den Rest-Pool geleert: 0
> Einträge.** Verbleib der 13 letzten Einträge:
> RN-006 + RN-012 → #111 · RN-013 → #112 · FD-008 → #113 ·
> QX-005 + QX-006 + QX-023-Rest → #114 · UI-012 + UI-014 + UI-015 →
> #115 · RN-010 + RN-011 → #116. **OS-012-Restgrenze → formal
> geschlossen (#117):** Die Deletion-Sync-Grenze (Flat-Layout „." bewusst
> ausgenommen) ist seit #101 dokumentiertes Verhalten und bleibt es —
> kein Code-Defekt, Won't-Fix mit Begründung.

### Geschlossenes Entscheidungsregister (Sprint 34, #117)

Die vier offenen Entscheidungen aus MEMORY.md sind entschieden:

| Entscheidung | Ausgang |
|--------------|---------|
| `--treat-timeout-as-kill`-Deprecation | **Deprecate-now, remove-in-v3**: Warnung bei Nutzung (run + results), Help/README markiert, funktional in 2.x — echte IL-Detection (v2.5.0/v2.8.0) ersetzt den Stopgap |
| Hypothesis „Shrink-Storm" | **Monitor-only bestätigt**: seit Sprint 26 nie beobachtet (kein Issue, kein Dogfooding-Fund); Schwellen-Tuning nur bei realem Auftreten |
| `_bug_reporting/BUG_REPORT_9.md` | **Gegenstandslos**: Datei existiert nicht mehr im Working Tree (verifiziert 2026-06-11); dokumentierte Bugs #1–#5 sind seit v2.2.0–v2.4.0 behoben |
| Release-Policy | **Dokumentiert** (README „Release policy"): bedarfsgetrieben, fester Ablauf Gates → Merge → Bump → Tag → GitHub-Release, nur auf explizites User-„Release"; kein PyPI-Schritt |

---

## Priorisierung

| Priorität | Bedeutung | Anteil |
|-----------|-----------|--------|
| **Must** | Ohne diese Features ist das Release wertlos | ~75% |
| **Should** | Wichtig, aber Release funktioniert ohne sie | ~20% |
| **Could** | Nice-to-have, wenn Zeit übrig | ~5% |

---

## Milestone-Zuordnung (GitHub)

| Milestone | Release | Epics | Issues | Status |
|-----------|---------|-------|--------|--------|
| MVP | v0.1.0 | Epic 1–6 | #1–#23 | Done (#12/#23 in Sprint 24/25 nachgeliefert) |
| Pipeline | v0.2.0 | Epic 7–9 | #24–#38 | Done (#38 in Sprint 24 nachgeliefert) |
| Performance v0.3.0 | v0.3.0 | Epic 10–11 | #39–#50 | Done (#49 in Sprint 24 nachgeliefert) |
| Hardening v0.5.0 | v0.5.0 | Epic 12 | #51–#54 | Done (#54 in Sprint 24 nachgeliefert) |
| Advanced Operators v1.0.0 | v1.0.0 | Epic 13 | #55–#61 | Done |
| Hardening v1.0.0 | v1.0.0 | Epic 14 | #62–#65, #67 | Done (#65/#67 in Sprint 24/25 nachgeliefert) |
| Stabilization v2.1.0 | v2.1.0 | Epic 15 | PR #66 | Done |
| Reliability v2.2.0 | v2.2.0 | Epic 16 | #68, #70, #71 | Done |
| Must-Carryover v2.3.0 | v2.3.0 | Epic 3/9/11/12/14 (Carryover) | #12, #38, #49, #54, #65 | Done |
| Final Cleanup v2.4.0 | v2.4.0 | Epic 6/14/16 (Carryover) | #23, #67, #69 | Done |
| Polish + IL Detection v2.5.0 | v2.5.0 / v2.5.1 | Epic 17 | #71 (re-open), #72 | Done |
| Full Source Audit | — | Epic 18 | — (Findings-Report) | Done |
| Source Protection v2.6.0 | v2.6.0 | Epic 19 | #73–#78 | Done |
| Runtime Reliability v2.7.0 | v2.7.0 | Epic 20 | #79–#84 | Done |
| IL Detection Honesty v2.8.0 | v2.8.0 | Epic 21 | #85–#90 | Done |
| Feature Truth & Score Integrity v2.9.0 | v2.9.0 | Epic 22 | #91–#97 | Done |
| Pipeline Hygiene v2.10.0 | v2.10.0 | Epic 23 | #98–#104 | Done |
| Maintenance 1 v2.11.0 | v2.11.0 | Epic 24 | #105–#110 | Done |
| Maintenance 2 v2.12.0 | v2.12.0 | Epic 25 | #111–#117 | Planned |

---

## Velocity Tracking

| Sprint | Geplant (SP) | Erledigt (SP) | Velocity | Notizen |
|--------|-------------|---------------|----------|---------|
| Sprint 1 | 15 | 15 | 100% | Foundation + Domain |
| Sprint 2 | 21 | 21 | 100% | Mutation Engine |
| Sprint 3 | 19 | 16 | 84% | Process Management (#12 carryover, 3 SP) |
| Sprint 4 | 19 | 19 | 100% | Orchestrator |
| Sprint 5 | 15 | 15 | 100% | CLI + TUI |
| Sprint 6 | 16 | 14 | 88% | E2E + Integration (#23 carryover, 2 SP) |
| Sprint 8 | 24 | 24 | 100% | File Setup Pipeline |
| Sprint 9 | 24 | 24 | 100% | Test Mapping + Stats |
| Sprint 10 | 21 | 16 | 76% | CLI show/apply + E2E (#38 carryover, 5 SP) |
| Sprint 11 | 24 | 24 | 100% | In-Process Stats + Trampoline Tracking |
| Sprint 12 | 34 | 26 | 76% | Feature Completeness (#49 carryover, 8 SP) |
| Sprint 13 | 13 | 11 | 85% | Hardening: Job Object (#54 carryover, 2 SP) |
| Sprint 14 | 8 | 8 | 100% | Regex-Mutationen |
| Sprint 15 | 3 | 3 | 100% | Math-Methoden |
| Sprint 16 | 2 | 2 | 100% | Return Value Replacement |
| Sprint 17 | 2 | 2 | 100% | Conditional Expression |
| Sprint 18 | 5 | 5 | 100% | Statement Removal |
| Sprint 19 | 3 | 3 | 100% | Collection-Methoden |
| Sprint 20 | 2 | 2 | 100% | or-Default |
| Sprint 21 | 23 | 18 | 78% | Hardening v1.0.0 (#65, #67 carryover, 5 SP) |
| Sprint 22 | 13 | 13 | 100% | v2.0.x Stabilization (PR #66 + Housekeeping + Release) |
| Sprint 23 | 16 | 16 | 100% | v2.0.x Reliability Wave (#68, #70, #71-Stopgap) |
| Sprint 24 | 18 | 18 | 100% | Must-Carryover (#12, #38, #49, #54, #65) |
| Sprint 25 | 10 | 10 | 100% | Final Cleanup (#23, #67, #69) |
| Sprint 26 | 14 | 14 | 100% | Polish + True IL Detection (#71 re-open, #72) |
| Sprint 27 | — | — | — | Full Source Audit (analysis-only, kein SP-Tracking) |
| Sprint 28 | 31 | 31 | 100% | v2.6.0 Source Protection & Codegen Correctness (#73–#78) |
| Sprint 29 | 27 | 27 | 100% | v2.7.0 Runtime Reliability (#79–#84) |
| Sprint 30 | 25 | 25 | 100% | v2.8.0 IL Detection Honesty (#85–#90) |
| Sprint 31 | 33 | 33 | 100% | v2.9.0 Feature Truth & Score Integrity (#91–#97) |
| Sprint 32 | 36 | 36 | 100% | v2.10.0 Pipeline Hygiene (#98–#104) |
| Sprint 33 | 31 | 31 | 100% | v2.11.0 Maintenance 1 (#105–#110) — Pilot 24,2 % → 86,9 % brutto |
| Sprint 34 | 27 | 27 | 100% | v2.12.0 Maintenance 2: Final Sweep (#111–#117) — Pool 13 → 0, Entscheidungsregister 4 → 0, mypy-Baseline 20 → 14, Pilot 85,1 % gehalten |

**Total geplant:** 364 SP — **Total erledigt:** 339 SP (93%)

> Hinweis: Die 25 SP Carryover-Differenz aus den Sprints 3–21 wurde in Sprint 24/25
> erneut eingeplant und dort erledigt — diese SP erscheinen daher in beiden Zeilen.

---

## Carryover (Stand 2026-06-11)

**Keine offenen Issues.** Alle sieben Carryover-Items des 2026-05-22-Housekeepings
(#12, #23, #38, #49, #54, #65, #67) wurden in Sprint 24 (v2.3.0) und Sprint 25
(v2.4.0) geliefert; die Downstream-Bugs #68–#71 in Sprint 23 (v2.2.0) und
Sprint 26 (v2.5.0). GitHub-Issue-Count: 0 open (verifiziert 2026-06-11).

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | 2026-03-30 | Claude Code Agent | Initiales Backlog |
| 0.2.0 | 2026-03-30 | Claude Code Agent | Epic 7–9 (Sprints 8–10): File Setup Pipeline, Test Mapping + Stats, CLI show/apply + E2E; Release v0.2.0; Issues #24–#38 |
| 0.3.0 | 2026-03-30 | Claude Code Agent | Epic 10–11 (Sprints 11–12): In-Process Stats + Trampoline Tracking, Feature Completeness + E2E Validation; Release v0.3.0; Issues #39–#50 |
| 1.0.0 | 2026-05-22 | Claude Code Agent | Backlog-Sync: 59 Issues von Open→Done geflippt; Epic 15 (Sprint 22 v2.0.x Stabilization, PR #66, v2.1.0 Release) ergänzt; Release-Übersicht bis v2.1.0; Velocity-Tracking vollständig befüllt; Carryover-Tabelle ergänzt. Issue #67 (H-05) retroactively erstellt. |
| 1.1.0 | 2026-06-11 | Claude Code Agent | Doku-Drift-Sync nach Sprints 23–26: Release-Übersicht bis v2.5.1; Epic 16 (Sprint 23 Reliability) + Epic 17 (Sprint 26 IL Detection) ergänzt (Epic-Nummern-Konflikt „16" zwischen sprint_23/sprint_26-Backlog zugunsten von Sprint 23 aufgelöst); 7 Carryover-Issues + #68–#72 auf Done; Milestones, Velocity (Sprints 23–26, Total 364/339 SP) und Carryover-Sektion aktualisiert. |
| 1.2.0 | 2026-06-11 | Claude Code Agent | Sprint-27-Audit eingearbeitet: Epic 18 (Full Source Audit, Done) + Epic 19 (Sprint 28 v2.6.0, Planned, #73–#78); Audit-Korrekturen an Epic-3-AC (#12 Restart-Logik nie implementiert) und Epic-17-AC (Forensics-Rendering nie erfüllt); Release-Übersicht, Milestones, Velocity ergänzt. |
| 1.3.0 | 2026-06-11 | Claude Code Agent | Sprint 28 geschlossen: Epic 19 Done (Commit-Refs), v2.6.0 released, Velocity 31/31, Gate-Abweichungen (lint-imports vorbestehend, Dogfooding deferred) dokumentiert. |
| 1.4.0 | 2026-06-11 | Claude Code Agent | Sprint 29 geplant: Epic 20 (Runtime Reliability, #79–#84, 27 SP); Audit-Rest-Roadmap als Release-Zeilen v2.8.0–v2.10.0 (C5, C6+C7, C8+C9) fixiert — Findings-Restbestand ~158 nach Sprint 28. |
| 1.5.0 | 2026-06-11 | Claude Code Agent | Sprint 29 geschlossen (Epic 20 Done, v2.7.0 released, alle 15 S1 zu, Velocity 27/27); Sprint 30 geplant: Epic 21 (IL Detection Honesty, #85–#90, 25 SP) mit Planungs-CoT (Wertschöpfungskette, Confidence-Cap-Kompatibilitätsfenster, JT-013 obsolet). |
| 1.6.0 | 2026-06-11 | Claude Code Agent | Sprint 30 geschlossen (Epic 21 Done, v2.8.0 released, Velocity 25/25): C5 komplett — Forensik persistiert+gerendert, Ein-Score-Konsistenz, Classifier plattform-ehrlich (Confidence-Cap medium auf win32), io_counters als Progress-Veto (Sleeping-Ersatz widerlegt+dokumentiert). 3 Pipeline-Hygiene-Neuzugänge für C8 vorgemerkt (format-Gate, pytest-Kanon, semgrep-tests-Ignore). |
| 1.7.0 | 2026-06-11 | Claude Code Agent | Sprint 31 geplant: Epic 22 (Feature Truth & Score Integrity, #91–#97, 33 SP) mit 12-Schritt-Planungs-CoT — C6/C7-Befunde am v2.8.0-Stand re-verifiziert; Kette Map→Härtung→E2E→Abbruch→Entscheide; Exit-2-Default „killed"; Coverage als timeboxed Entscheid (Zeilen-Referenzsystem-Frage); Scope-Ventil #96/#97. |
| 1.8.0 | 2026-06-11 | Claude Code Agent | Sprint 31 geschlossen (Epic 22 Done, v2.9.0 released, Velocity 33/33): C6+C7 komplett — Type-Check-Filter end-to-end repariert (E2E mit echtem mypy), Coverage via Subprozess-Brücke REAKTIVIERT (Spike + 8-Schritt-CoT), Status-/Score-Pipeline lückenlos (Summen-Invariante, Exit-2/NTSTATUS-Kills, Interrupt-Ehrlichkeit, Orphan-Purge, score im JSON). Release mit ⚠-Score-corrections-Sektion. mypy-Baseline 26→20. |
| 1.9.0 | 2026-06-11 | Claude Code Agent | Sprint 32 geplant: Epic 23 (Pipeline Hygiene, #98–#104, 36 SP) mit 12-Schritt-Planungs-CoT — letzter Audit-Sprint (C8+C9-Top + Neuzugänge + Dogfooding-Premiere); Format-Commit als Sprint-Auftakt, verschärfte Gates als Sprint-Inhalt, C9-Rest-Triage statt Versanden; OS-006/FD-002 am v2.9.0-Stand re-verifiziert. Branch-Aufräumen: 37 lokale + 2 Remote-Branches entfernt. |
| 2.0.0 | 2026-06-11 | Claude Code Agent | Sprint 32 geschlossen (Epic 23 Done, v2.10.0 released, Velocity 36/36) — **AUDIT-ZYKLUS BEENDET**: C1–C8 komplett + C9-Top über 5 Releases an einem Tag; verschärfte Gates verankert (format-check, nackter pytest, semgrep auf tests/); Dogfooding-Premiere (85,5 % über bewertbare Mutanten, 4 Anläufe = 4 Funde); Maintenance-Backlog (26 Einträge) als einziger Arbeitsvorrat. |
| 2.1.0 | 2026-06-11 | Claude Code Agent | Sprint 33 geplant: Epic 24 (Maintenance 1: Runtime & Self-Run, #105–#110, 31 SP) per 10-Schritt-CoT — bedarfsgetriebene Pool-Auswahl (3×S2 + Bündel), Messziel Pilot brutto ≥ 80 %, Pool-Rest (20) bewusst unversprochen. |
| 2.2.0 | 2026-06-11 | Claude Code Agent | Sprint 33 implementiert (Epic 24 Done, Velocity 31/31): Pilot 24,2 % → **86,9 % brutto** (0 Timeouts statt 175), Architektur-Skip im Artefakt entfernt, Maintenance-Pool 26 → 13. Release v2.11.0 ausstehend. |
| 2.3.0 | 2026-06-11 | Claude Code Agent | Sprint 33 geschlossen (v2.11.0 released, Merge schloss #105–#110 automatisch): annotated Tag + GitHub-Release mit ausgewiesener Score-Verschiebung (no_tests verlässt den Nenner, Vollsuite-Zufallskills den Zähler); Milestone/Epic auf Done, MEMORY.md + state.md synchronisiert. |
| 2.4.0 | 2026-06-11 | Claude Code Agent | Sprint 34 geplant: Epic 25 (Maintenance 2: Final Sweep, #111–#117, 27 SP) per 11-Schritt-CoT — User-Auftrag „alle offenen Topics, danach Entwicklungspause": kompletter Pool-Rest (13) + MEMORY-Entscheidungsregister (4); kein Auswahl-Ventil, Eskalation nur zu dokumentierter Won't-Fix-Entscheidung; Messziel Pilot ≥ 80 % halten. |
| 2.5.0 | 2026-06-11 | Claude Code Agent | Sprint 34 implementiert (Epic 25 Done, Velocity 27/27): **Maintenance-Pool 13 → 0, Entscheidungsregister 4 → 0**, mypy-Baseline 20 → 14, 5 stale GitHub-Milestones geschlossen; Gates: 951 passed (+83), ruff/format 0, semgrep 0 (voller Sweep), lint-imports KEPT; Pilot **85,1 % brutto gehalten** (6 Kaltstart-Timeouts re-run-verifiziert als Kills). Release v2.12.0 ausstehend; danach Entwicklungspause. |
