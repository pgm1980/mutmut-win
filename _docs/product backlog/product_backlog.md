# Product Backlog — mutmut-win

**Version:** 1.0.0
**Datum:** 2026-05-22
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
| #12 | Task | Worker-Recovery bei Crashes implementieren | Must | 3 | **Open (PARTIAL)** |

**Acceptance Criteria:**
- [x] SpawnPoolExecutor startet N Worker via multiprocessing.spawn
- [x] Two-Queue-Architektur (task_queue + event_queue)
- [x] WallClockTimeout erkennt und killt überfällige Worker
- [x] Ctrl+C führt zu sauberem Shutdown mit gespeicherten Teilergebnissen
- [ ] Max 3 Worker-Neustarts pro Slot (PARTIAL — detection done, recovery strategy pending #12)

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
| #23 | Task | Performance-Benchmark gegen mutmut (Linux-Vergleich) | Could | 2 | **Open** |

**Acceptance Criteria:**
- [x] Alle 5 E2E-Testprojekte laufen erfolgreich
- [x] Snapshot-Vergleich gegen mutmut-Referenzergebnisse
- [x] Segfault-Mutant Windows-spezifisch behandelt
- [ ] mutmut-win läuft auf eigenem Code (PARTIAL — siehe #65)

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
| #38 | Task | End-to-End-Validierungstest (volle Pipeline auf simple_lib) | Must | 5 | **Open (UNCLEAR — fixtures vorhanden, Harness fehlt)** |

**Acceptance Criteria:**
- [x] `mutant_diff.py` im Application Layer implementiert
- [x] `mutmut-win show <NAME>` zeigt echten unified diff
- [x] `mutmut-win apply <NAME>` schreibt CST-basierten mutierten Code in Quelldatei
- [x] Live-Fortschrittsanzeige während des Laufs aktiv
- [ ] E2E-Validierungstest auf simple_lib läuft durch (Clean → Mutants → Results) — siehe #38

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
| #49 | Task | Full E2E Validation — mutmut-win run auf simple_lib + my_lib, Ergebnisvergleich mit mutmut-Referenz | Must | 8 | **Open (UNCLEAR — siehe #38)** |
| #50 | Task | exceptions.py — MutmutProgrammaticFailException, BadTestExecutionCommandsException, InvalidGeneratedSyntaxException | Must | 3 | Done |

**Acceptance Criteria:**
- [x] `guess_paths_to_mutate()` ermittelt src/-Verzeichnisse automatisch wenn `paths_to_mutate` nicht konfiguriert
- [x] `ListAllTestsResult` in `stats.py` implementiert, inkrementelle Updates möglich
- [x] `tests-for-mutant` und `time-estimates` CLI-Commands funktionieren
- [x] `save_cicd_stats` + CLI-Command `export-cicd-stats` implementiert
- [x] Alle Type-Checker-Helpers in `type_checking.py` vollständig portiert
- [ ] E2E-Validierung: mutmut-win-Ergebnisse stimmen mit mutmut-Referenz überein (simple_lib + my_lib) — siehe #49
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
| #54 | Task | Deterministischer Test: Job Object kill-on-close Verhalten | Must | 2 | **Open** |

**Acceptance Criteria:**
- [x] `job_object.py` implementiert `create_kill_on_close_job()`, `assign_process_to_job()`, `close_job()`
- [x] SpawnPoolExecutor erstellt Job Object im `__init__`, weist Worker in `start()` zu, schließt in `shutdown()`
- [x] Bei Parent-Tod: ALLE Worker + deren pytest-Subprozesse werden vom OS gekillt
- [x] Graceful Degradation: Warning statt Crash wenn Job Object nicht erstellt werden kann
- [ ] Deterministischer Test beweist kill-on-close Verhalten (siehe #54)
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
| #65 | Task | Dogfooding: mutmut-win auf eigenem Code erfolgreich ausführen | Must | 3 | **Open (PARTIAL)** |
| #67 | Task | H-05: also_copy .venv-Symlink review (filed retroactively 2026-05-22) | Should | 2 | **Open** |

**Acceptance Criteria:**
- [x] `mutmut-win run --paths-to-mutate src/mutmut_win/regex_mutation.py` funktioniert
- [x] `mutmut-win run --min-score 80` gibt Exit 1 wenn Score < 80%
- [x] `mutmut-win run --output json` gibt valides JSON zurück
- [x] `mutmut-win run --since-commit HEAD~1` mutiert nur geänderte Dateien
- [x] `mutmut-win run --dry-run` zeigt Mutanten-Anzahl ohne Ausführung
- [x] Worker-Prozesse können mutmut_win importieren (Dogfooding-Import funktioniert)
- [x] Alle Hooks manuell verifiziert (SessionStart verifiziert live in Sprint 22)
- [x] sprint-gate.sh sucht in `_docs/sprint backlogs/` statt `find . -maxdepth 4`
- [ ] Vollständiger Dogfooding-Lauf auf gesamtem `src/mutmut_win/` (siehe #65)

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
| MVP | v0.1.0 | Epic 1–6 | #1–#23 | Done (außer #12, #23) |
| Pipeline | v0.2.0 | Epic 7–9 | #24–#38 | Done (außer #38) |
| Performance v0.3.0 | v0.3.0 | Epic 10–11 | #39–#50 | Done (außer #49) |
| Hardening v0.5.0 | v0.5.0 | Epic 12 | #51–#54 | Done (außer #54) |
| Advanced Operators v1.0.0 | v1.0.0 | Epic 13 | #55–#61 | Done |
| Hardening v1.0.0 | v1.0.0 | Epic 14 | #62–#65, #67 | Done (außer #65, #67) |
| Stabilization v2.1.0 | v2.1.0 | Epic 15 | PR #66 | Done |

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

**Total geplant:** 306 SP — **Total erledigt:** 281 SP (92%)

---

## Carryover (echte OPEN Issues, Stand 2026-05-22)

| Issue | Titel | Originalsprint | Priorität | Status |
|-------|-------|----------------|-----------|--------|
| #12 | Worker crash recovery | Sprint 3 | Must | PARTIAL — detection done, recovery strategy pending |
| #23 | Performance benchmark vs mutmut | Sprint 6 | Could | benchmarks/ Verzeichnis fehlt |
| #38 | E2E validation test (full pipeline) | Sprint 10 | Must | Fixtures vorhanden, Harness fehlt |
| #49 | Sprint-12 Full E2E (simple_lib + my_lib) | Sprint 12 | Must | Duplikat-Bereich zu #38 |
| #54 | Deterministischer Job-Object kill-on-close Test | Sprint 13 | Must | Job Object integriert, dedicated Test fehlt |
| #65 | Dogfooding: mutmut-win run on own code | Sprint 21 | Must | PARTIAL — pyproject paths_to_mutate auf regex_mutation.py beschränkt |
| #67 | H-05: also_copy .venv-Symlink review | Sprint 21 (retro) | Should | Neu eröffnet 2026-05-22 |

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | 2026-03-30 | Claude Code Agent | Initiales Backlog |
| 0.2.0 | 2026-03-30 | Claude Code Agent | Epic 7–9 (Sprints 8–10): File Setup Pipeline, Test Mapping + Stats, CLI show/apply + E2E; Release v0.2.0; Issues #24–#38 |
| 0.3.0 | 2026-03-30 | Claude Code Agent | Epic 10–11 (Sprints 11–12): In-Process Stats + Trampoline Tracking, Feature Completeness + E2E Validation; Release v0.3.0; Issues #39–#50 |
| 1.0.0 | 2026-05-22 | Claude Code Agent | Backlog-Sync: 59 Issues von Open→Done geflippt; Epic 15 (Sprint 22 v2.0.x Stabilization, PR #66, v2.1.0 Release) ergänzt; Release-Übersicht bis v2.1.0; Velocity-Tracking vollständig befüllt; Carryover-Tabelle ergänzt. Issue #67 (H-05) retroactively erstellt. |
