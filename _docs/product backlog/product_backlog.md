# Product Backlog — mutmut-win

**Version:** 0.6.0
**Datum:** 2026-03-30
**Status:** Active

---

## Release-Übersicht

| Release | Codename | Sprints | Status | Highlights |
|---------|----------|---------|--------|------------|
| v0.1.0 | MVP | Sprint 1–6 | Done | Windows-native Mutation Testing |
| v0.2.0 | Pipeline | Sprint 8–10 | Done | File Setup Pipeline, Test Mapping, CLI show/apply, E2E-Validierung |
| v0.3.0 | Performance | Sprint 11–12 | Done | In-Process Stats, Trampoline Tracking, Feature Completeness |
| v0.5.0 | Hardening | Sprint 13 | Done | Windows Job Object Orphan Protection |
| v0.6.0 | Stress-Test | — | Done | Synthetic 1127-mutant stress test, line-buffered stdout, progress counter fix |
| v1.0.0 | Advanced Operators | Sprint 14–20 | Planned | 7 neue Mutationsoperatoren (Regex, Math, Return, Conditional, Statement, Collection, or-Default) |

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
| #1 | Story | Als Entwickler will ich ein konfiguriertes Python-Projekt mit uv, damit die Entwicklung starten kann | Must | 3 | Open |
| #2 | Story | Als User will ich Config aus pyproject.toml laden, damit ich mutmut-win konfigurieren kann | Must | 5 | Open |
| #3 | Story | Als Entwickler will ich typisierte Domain-Modelle, damit alle Datenstrukturen validiert sind | Must | 5 | Open |
| #4 | Task | Architecture-Contracts (import-linter) einrichten | Must | 2 | Open |

**Acceptance Criteria:**
- [ ] pyproject.toml mit allen Dependencies und Tool-Configs
- [ ] Pydantic Config-Model validiert [tool.mutmut] Sektion
- [ ] Alle Domain-Modelle mit Type Hints und Docstrings
- [ ] import-linter Contracts für 4-Schichten-Architektur
- [ ] hypothesis Property-Tests für Config und Models

---

### Epic 2: Mutation Engine Port

**Beschreibung:** Port der CST-basierten Mutation Engine aus mutmut 3.5.0 mit Windows-Anpassungen
**Sprint:** 2
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #5 | Story | Als User will ich Python-Code CST-basiert mutieren können, damit Mutations erzeugt werden | Must | 8 | Open |
| #6 | Story | Als User will ich Trampoline-basiertes Mutant-Switching, damit Mutanten effizient geladen werden | Must | 5 | Open |
| #7 | Story | Als User will ich Coverage-gestütztes Mutieren, damit nur relevante Code-Bereiche mutiert werden | Should | 5 | Open |
| #8 | Story | Als User will ich Type-Checker-Integration, damit Type-Error-Mutanten erkannt werden | Should | 3 | Open |

**Acceptance Criteria:**
- [ ] mutation.py mit encoding='utf-8' portiert
- [ ] node_mutation.py 1:1 übernommen
- [ ] trampoline.py 1:1 übernommen
- [ ] code_coverage.py mit encoding='utf-8' portiert
- [ ] type_checking.py 1:1 übernommen
- [ ] Unit-Tests für alle Mutations-Operatoren

---

### Epic 3: Windows Process Management

**Beschreibung:** Spawn-basierter Worker-Pool mit Timeout-Monitor (Kern des Windows-Ports)
**Sprint:** 3
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #9 | Story | Als User will ich parallele Mutation-Test-Ausführung via Worker-Pool, damit Tests schnell laufen | Must | 8 | Open |
| #10 | Story | Als User will ich Wall-Clock-Timeouts, damit Endlosschleifen erkannt werden | Must | 5 | Open |
| #11 | Story | Als User will ich Graceful Shutdown bei Ctrl+C, damit Teilergebnisse gespeichert werden | Must | 3 | Open |
| #12 | Task | Worker-Recovery bei Crashes implementieren | Must | 3 | Open |

**Acceptance Criteria:**
- [ ] SpawnPoolExecutor startet N Worker via multiprocessing.spawn
- [ ] Two-Queue-Architektur (task_queue + event_queue)
- [ ] WallClockTimeout erkennt und killt überfällige Worker
- [ ] Ctrl+C führt zu sauberem Shutdown mit gespeicherten Teilergebnissen
- [ ] Max 3 Worker-Neustarts pro Slot

---

### Epic 4: Orchestrator & Test Runner

**Beschreibung:** Orchestrierung des Mutation-Testing-Ablaufs und pytest-Integration
**Sprint:** 4
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #13 | Story | Als User will ich einen vollständigen Mutation-Testing-Lauf orchestriert haben | Must | 8 | Open |
| #14 | Story | Als User will ich einen Clean-Test-Run vor Mutation Testing | Must | 3 | Open |
| #15 | Story | Als User will ich Ergebnisse in SQLite persistiert haben | Must | 5 | Open |
| #16 | Task | PytestRunner implementieren (Test-Ausführung abstrahieren) | Must | 3 | Open |

**Acceptance Criteria:**
- [ ] MutationOrchestrator koordiniert den gesamten Ablauf
- [ ] Clean Test, Stats, Forced Fail vor Mutation Testing
- [ ] SQLite-Schema kompatibel mit mutmut
- [ ] Fortschrittsanzeige während des Laufs

---

### Epic 5: CLI & TUI Browser

**Beschreibung:** Click-basierte CLI und Textual-basierter TUI Result Browser
**Sprint:** 5
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #17 | Story | Als User will ich `mutmut-win run` ausführen können, damit Mutation Testing läuft | Must | 5 | Open |
| #18 | Story | Als User will ich `mutmut-win results/show/apply`, damit ich Ergebnisse verwalten kann | Must | 5 | Open |
| #19 | Story | Als User will ich `mutmut-win browse` für einen interaktiven TUI Browser | Should | 5 | Open |

**Acceptance Criteria:**
- [ ] Alle 5 CLI-Commands implementiert
- [ ] CLI-Tests via click.testing.CliRunner
- [ ] TUI Browser aus mutmut portiert
- [ ] Entry-Point in pyproject.toml konfiguriert

---

### Epic 6: E2E Tests & Integration

**Beschreibung:** E2E-Tests gegen mutmut-Testprojekte und Gesamtintegration
**Sprint:** 6
**Release:** v0.1.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #20 | Story | Als Entwickler will ich E2E-Tests gegen mutmut-Referenzprojekte, damit Korrektheit validiert ist | Must | 8 | Open |
| #21 | Task | 5 E2E-Testprojekte aus mutmut übernehmen und anpassen | Must | 3 | Open |
| #22 | Task | Mutation Testing auf eigenen Code (Meta-Test) | Should | 3 | Open |
| #23 | Task | Performance-Benchmark gegen mutmut (Linux-Vergleich) | Could | 2 | Open |

**Acceptance Criteria:**
- [ ] Alle 5 E2E-Testprojekte laufen erfolgreich
- [ ] Snapshot-Vergleich gegen mutmut-Referenzergebnisse
- [ ] Segfault-Mutant Windows-spezifisch behandelt
- [ ] mutmut-win läuft auf eigenem Code

---

### Epic 7: File Setup Pipeline

**Beschreibung:** Port der File-Setup-Pipeline aus mutmut's __main__.py — kopiert Quelldateien nach mutants/, schreibt mutierte Trampoline-Dateien, richtet sys.path ein
**Sprint:** 8
**Release:** v0.2.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #24 | Story | Als Entwickler will ich walk_source_files + walk_all_files, damit Quelldateien navigierbar sind | Must | 3 | Open |
| #25 | Story | Als Entwickler will ich copy_src_dir + copy_also_copy_files, damit mutants/ befüllt wird | Must | 5 | Open |
| #26 | Story | Als Entwickler will ich setup_source_paths (sys.path-Manipulation), damit pytest aus mutants/ importiert | Must | 5 | Open |
| #27 | Story | Als Entwickler will ich write_all_mutants_to_file + create_mutants_for_file, damit mutierte Dateien auf Disk geschrieben werden | Must | 8 | Open |
| #28 | Task | Orchestrator-Integration: _generate_mutants delegiert an file_setup | Must | 3 | Open |

**Acceptance Criteria:**
- [ ] `file_setup.py` im Domain Layer implementiert
- [ ] Quelldateien werden korrekt nach mutants/ kopiert (Pfad-Struktur erhalten)
- [ ] sys.path wird für mutants/-Import eingerichtet und nach dem Lauf wiederhergestellt
- [ ] Mutierte Trampoline-Dateien werden korrekt auf Disk geschrieben
- [ ] also_copy-Dateien werden kopiert
- [ ] Unit-Tests mit tmp_path-Fixture, hypothesis für Pfad-Invarianten

---

### Epic 8: Test Mapping + Stats Caching

**Beschreibung:** Mutant-zu-Test-Mapping via mangled names und inkrementelles Stats-Caching in mutants/mutmut-stats.json
**Sprint:** 9
**Release:** v0.2.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #29 | Story | Als Entwickler will ich mangled_name_from_mutant_name + orig_function_and_class_names_from_key, damit Mutant-Namen decodiert werden | Must | 5 | Open |
| #30 | Story | Als Entwickler will ich tests_for_mutant_names, damit nur relevante Tests pro Mutant ausgeführt werden | Must | 8 | Open |
| #31 | Story | Als Entwickler will ich Stats load/save/collect_or_load, damit Test-Laufzeiten gecacht werden | Must | 5 | Open |
| #32 | Task | Type-Checker-Filter in Orchestrator verdrahten | Should | 3 | Open |
| #33 | Task | Orchestrator-Integration: Test-Assignment und Stats-Caching aktivieren | Must | 3 | Open |

**Acceptance Criteria:**
- [ ] `test_mapping.py` im Domain Layer implementiert
- [ ] `stats.py` im Application Layer implementiert
- [ ] Stats werden in mutants/mutmut-stats.json mit encoding='utf-8' gespeichert
- [ ] Inkrementelles Caching via Hash-Vergleich funktioniert
- [ ] Mutanten laufen nur gegen relevante Tests (deutliche Laufzeit-Reduktion)
- [ ] Type-Checker-Filter im Orchestrator aktiv
- [ ] hypothesis Property-Tests für Name-Mangling-Roundtrips

---

### Epic 9: CLI show/apply + E2E-Validierung

**Beschreibung:** Vollständige Implementierung der `show`- und `apply`-Commands sowie End-to-End-Validierung der gesamten Pipeline
**Sprint:** 10
**Release:** v0.2.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #34 | Story | Als Entwickler will ich find_mutant + read_mutants_module + read_orig_module, damit Mutant-Dateien gelesen werden können | Must | 3 | Open |
| #35 | Story | Als User will ich get_diff_for_mutant (unified diff), damit ich sehe was ein Mutant verändert | Must | 5 | Open |
| #36 | Story | Als User will ich apply_mutant (CST-basierter Source-Ersatz), damit ich einen Mutanten in den Quellcode schreiben kann | Must | 5 | Open |
| #37 | Story | Als User will ich Live-Fortschrittsanzeige (print_stats), damit ich den Lauf-Fortschritt sehe | Should | 3 | Open |
| #38 | Task | End-to-End-Validierungstest (volle Pipeline auf simple_lib) | Must | 5 | Open |

**Acceptance Criteria:**
- [ ] `mutant_diff.py` im Application Layer implementiert
- [ ] `mutmut-win show <NAME>` zeigt echten unified diff
- [ ] `mutmut-win apply <NAME>` schreibt CST-basierten mutierten Code in Quelldatei
- [ ] Live-Fortschrittsanzeige während des Laufs aktiv
- [ ] E2E-Validierungstest auf simple_lib läuft durch (Clean → Mutants → Results)
- [ ] Alle Sprints 8–10 DoD-Kriterien erfüllt

---

### Epic 10: In-Process Stats + Trampoline Tracking

**Beschreibung:** Implementierung der Two-Phase Execution mit in-process pytest.main() für Stats und korrektem Trampoline-Hit-Tracking via _state globals — kritisch für korrekte Test-Zuordnung pro Mutant
**Sprint:** 11
**Release:** v0.3.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #39 | Story | Als Entwickler will ich _state.py module mit shared globals für Trampoline-Tracking | Must | 3 | Open |
| #40 | Story | Als Entwickler will ich record_trampoline_hit + MutmutProgrammaticFailException re-exports in __main__.py | Must | 3 | Open |
| #41 | Story | Als Entwickler will ich PytestRunner.run_stats() Rewrite mit pytest.main() + StatsCollector Plugin | Must | 8 | Open |
| #42 | Story | Als Entwickler will ich stats.py Update — collect_or_load_stats nutzt _state globals nach run_stats() | Must | 5 | Open |
| #43 | Task | Orchestrator — reale Test-Zuordnung aus Stats-Daten verdrahten | Must | 5 | Open |

**Acceptance Criteria:**
- [ ] `_state.py` im Domain Layer mit `tests_by_mangled_function_name`, `current_test_name`, `reset_state()`, `record_trampoline_hit()`
- [ ] `__main__.py` re-exportiert `record_trampoline_hit` und `MutmutProgrammaticFailException`
- [ ] `PytestRunner.run_stats()` verwendet `pytest.main()` in-process mit `StatsCollector`-Plugin
- [ ] Stats-Daten enthalten korrekte Test-Zuordnung via mangled names
- [ ] Orchestrator weist nur relevante Tests pro Mutant zu (deutliche Laufzeit-Reduktion)
- [ ] hypothesis Property-Tests für `record_trampoline_hit` State-Invarianten

---

### Epic 11: Feature Completeness + E2E Validation

**Beschreibung:** Port aller verbleibenden mutmut-Funktionen für 100% Feature-Parität und vollständige E2E-Validierung auf Referenzprojekten
**Sprint:** 12
**Release:** v0.3.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #44 | Story | Als User will ich guess_paths_to_mutate() in config.py, damit paths_to_mutate automatisch ermittelt wird | Must | 3 | Open |
| #45 | Story | Als Entwickler will ich ListAllTestsResult + inkrementelle Stats, damit Stats-Updates effizient sind | Should | 5 | Open |
| #46 | Story | Als User will ich CLI-Commands tests-for-mutant und time-estimates, damit ich Test-Zuordnung und Zeitschätzungen abrufen kann | Should | 5 | Open |
| #47 | Story | Als User will ich CI/CD-Stats-Export (save_cicd_stats + CLI), damit ich Mutation-Testing in CI/CD integrieren kann | Should | 5 | Open |
| #48 | Story | Als Entwickler will ich Type-Checker-Helpers vollständig (MutatedMethodsCollector, MutatedMethodLocation, FailedTypeCheckMutant, group_by_path) | Must | 5 | Open |
| #49 | Task | Full E2E Validation — mutmut-win run auf simple_lib + my_lib, Ergebnisvergleich mit mutmut-Referenz | Must | 8 | Open |
| #50 | Task | exceptions.py — MutmutProgrammaticFailException, BadTestExecutionCommandsException, InvalidGeneratedSyntaxException | Must | 3 | Open |

**Acceptance Criteria:**
- [ ] `guess_paths_to_mutate()` ermittelt src/-Verzeichnisse automatisch wenn `paths_to_mutate` nicht konfiguriert
- [ ] `ListAllTestsResult` in `stats.py` implementiert, inkrementelle Updates möglich
- [ ] `tests-for-mutant` und `time-estimates` CLI-Commands funktionieren
- [ ] `save_cicd_stats` + CLI-Command `export-cicd-stats` implementiert
- [ ] Alle Type-Checker-Helpers in `type_checking.py` vollständig portiert
- [ ] E2E-Validierung: mutmut-win-Ergebnisse stimmen mit mutmut-Referenz überein (simple_lib + my_lib)
- [ ] `exceptions.py` enthält alle fehlenden Exception-Klassen

---

### Epic 12: Hardening — Orphan-Prozess-Schutz (Sprint 13)

**Beschreibung:** Windows Job Objects für zuverlässigen Orphan-Prozess-Schutz. Verhindert CPU-Überhitzung wenn der Hauptprozess unerwartet stirbt.
**Sprint:** 13
**Release:** v0.5.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #51 | Story | Als User will ich dass Worker-Prozesse automatisch sterben wenn mutmut-win crasht | Must | 5 | Open |
| #52 | Task | `process/job_object.py` — ctypes Win32 Job Object Wrapper | Must | 3 | Open |
| #53 | Task | `executor.py` Integration (create/assign/close) + Graceful Degradation | Must | 3 | Open |
| #54 | Task | Deterministischer Test: Job Object kill-on-close Verhalten | Must | 2 | Open |

**Acceptance Criteria:**
- [ ] `job_object.py` implementiert `create_kill_on_close_job()`, `assign_process_to_job()`, `close_job()`
- [ ] SpawnPoolExecutor erstellt Job Object im `__init__`, weist Worker in `start()` zu, schließt in `shutdown()`
- [ ] Bei Parent-Tod: ALLE Worker + deren pytest-Subprozesse werden vom OS gekillt
- [ ] Graceful Degradation: Warning statt Crash wenn Job Object nicht erstellt werden kann
- [ ] Deterministischer Test beweist kill-on-close Verhalten
- [ ] DoD aktualisiert: E2E-Lauf darf keine Orphan-Prozesse hinterlassen

---

### Epic 13: Erweiterte Mutationsoperatoren (Sprint 14-20)

**Beschreibung:** 7 neue Mutationsoperatoren inspiriert von Stryker.NET und cargo-mutants. Bringt mutmut-win auf Stryker-Niveau mit Regex-Mutation als Alleinstellungsmerkmal.
**Sprint:** 14-20 (je 1 Operator pro Sprint)
**Release:** v1.0.0

| Issue | Typ | Titel | Sprint | Priorität | SP | Status |
|-------|-----|-------|--------|-----------|-----|--------|
| #55 | Story | Regex-Mutationen (Quantifier, CharClass, Anchors) | 14 | Must | 8 | Open |
| #56 | Story | Math-Methoden (ceil↔floor, min↔max, abs→x, sum→0) | 15 | Must | 3 | Open |
| #57 | Story | Return Value Replacement (return expr → return None) | 16 | Must | 2 | Open |
| #58 | Story | Conditional Expression (x if c else y → x / y) | 17 | Must | 2 | Open |
| #59 | Story | Statement Removal (void calls + raise → pass) | 18 | Must | 5 | Open |
| #60 | Story | Collection-Methoden (sorted→identity, filter entfernen) | 19 | Must | 3 | Open |
| #61 | Story | or-Default (x or default → x / default) | 20 | Should | 2 | Open |

**Acceptance Criteria:**
- [ ] Alle 7 Operatoren in `mutation_operators` registriert
- [ ] Regex-Mutator in separatem Modul `regex_mutation.py`
- [ ] Statement Removal mit Exclusion-Liste (print, logger, warnings)
- [ ] or-Default nur in Zuweisungskontexten
- [ ] Alle generierten Regex via `re.compile()` auf Validität geprüft
- [ ] Unit Tests + hypothesis Property-Tests für jeden Operator
- [ ] mutmut-win run auf eigenem Code (Dogfooding) nach jedem Sprint
- [ ] Mutation Score des neuen Operators gemessen

---

### Epic 14: Hardening — CLI-Flags, Dogfooding, Hooks (Sprint 21)

**Beschreibung:** 10 CLI-Flags für Automation/CI/CD, Dogfooding-Fix (Worker ModuleNotFoundError), Hook-Debugging.
**Sprint:** 21
**Release:** v1.0.0

| Issue | Typ | Titel | Priorität | SP | Status |
|-------|-----|-------|-----------|-----|--------|
| #62 | Bug | H-06: Worker ModuleNotFoundError bei editable install + spawn | Must | 5 | Open |
| #63 | Feature | H-07: 10 CLI-Flags Tier 1-3 (--paths-to-mutate, --min-score, --output json, --since-commit, etc.) | Must | 8 | Open |
| #64 | Bug | H-01–H-04: Hooks feuern nicht automatisch in Claude Desktop | Must | 5 | Open |
| #65 | Task | Dogfooding: mutmut-win auf eigenem Code erfolgreich ausführen | Must | 3 | Open |

**Acceptance Criteria:**
- [ ] `mutmut-win run --paths-to-mutate src/mutmut_win/regex_mutation.py` funktioniert
- [ ] `mutmut-win run --min-score 80` gibt Exit 1 wenn Score < 80%
- [ ] `mutmut-win run --output json` gibt valides JSON zurück
- [ ] `mutmut-win run --since-commit HEAD~1` mutiert nur geänderte Dateien
- [ ] `mutmut-win run --dry-run` zeigt Mutanten-Anzahl ohne Ausführung
- [ ] Worker-Prozesse können mutmut_win importieren (Dogfooding funktioniert)
- [ ] Alle Hooks manuell verifiziert und Ergebnis in hooks.md dokumentiert
- [ ] sprint-gate.sh sucht in `_docs/sprint backlogs/` statt `find . -maxdepth 4`

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
| MVP | v0.1.0 | Epic 1–6 | #1–#23 | Open |
| Pipeline | v0.2.0 | Epic 7–9 | #24–#38 | Open |
| Performance v0.3.0 | v0.3.0 | Epic 10–11 | #39–#50 | Open |
| Hardening v0.5.0 | v0.5.0 | Epic 12 | #51–#54 | Open |
| Advanced Operators v1.0.0 | v1.0.0 | Epic 13 | #55–#61 | Done |
| Hardening v1.0.0 | v1.0.0 | Epic 14 | #62–#65 | Open |

---

## Velocity Tracking

| Sprint | Geplant (SP) | Erledigt (SP) | Velocity | Notizen |
|--------|-------------|---------------|----------|---------|
| Sprint 1 | 15 | | | Foundation + Domain |
| Sprint 2 | 21 | | | Mutation Engine |
| Sprint 3 | 19 | | | Process Management |
| Sprint 4 | 19 | | | Orchestrator |
| Sprint 5 | 15 | | | CLI + TUI |
| Sprint 6 | 16 | | | E2E + Integration |
| Sprint 8 | 24 | | | File Setup Pipeline |
| Sprint 9 | 24 | | | Test Mapping + Stats |
| Sprint 10 | 21 | | | CLI show/apply + E2E Validation |
| Sprint 11 | 24 | | | In-Process Stats + Trampoline Tracking |
| Sprint 12 | 34 | | | Feature Completeness + E2E Validation |
| Sprint 13 | 13 | | | Hardening: Job Object Orphan Protection |
| Sprint 14 | 8 | | | Regex-Mutationen (Alleinstellungsmerkmal) |
| Sprint 15 | 3 | | | Math-Methoden (ceil↔floor, min↔max) |
| Sprint 16 | 2 | | | Return Value Replacement |
| Sprint 17 | 2 | | | Conditional Expression |
| Sprint 18 | 5 | | | Statement Removal |
| Sprint 19 | 3 | | | Collection-Methoden |
| Sprint 20 | 2 | | | or-Default |
| Sprint 21 | 23 | | | Hardening: CLI-Flags + Dogfooding + Hooks |

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | 2026-03-30 | Claude Code Agent | Initiales Backlog |
| 0.2.0 | 2026-03-30 | Claude Code Agent | Epic 7–9 (Sprints 8–10): File Setup Pipeline, Test Mapping + Stats, CLI show/apply + E2E; Release v0.2.0; Issues #24–#38 |
| 0.3.0 | 2026-03-30 | Claude Code Agent | Epic 10–11 (Sprints 11–12): In-Process Stats + Trampoline Tracking, Feature Completeness + E2E Validation; Release v0.3.0; Issues #39–#50 |
