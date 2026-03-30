# Product Backlog — mutmut-win

**Version:** 0.1.0
**Datum:** 2026-03-30
**Status:** Active

---

## Release-Übersicht

| Release | Codename | Sprints | Status | Highlights |
|---------|----------|---------|--------|------------|
| v0.1.0 | MVP | Sprint 1–6 | Planned | Windows-native Mutation Testing |
| v0.2.0 | Pipeline | Sprint 8–10 | Planned | File Setup Pipeline, Test Mapping, CLI show/apply, E2E-Validierung |

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
- [ ] **Mutation Testing**: `uv run mutmut run` — Score ≥ 80% auf neuem Code

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

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | 2026-03-30 | Claude Code Agent | Initiales Backlog |
| 0.2.0 | 2026-03-30 | Claude Code Agent | Epic 7–9 (Sprints 8–10): File Setup Pipeline, Test Mapping + Stats, CLI show/apply + E2E; Release v0.2.0; Issues #24–#38 |
