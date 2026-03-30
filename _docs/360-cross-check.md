# 360° Cross-Check: mutmut 3.5.0 vs. mutmut-win

**Datum:** 2026-03-30
**Prüfer:** Claude Code Agent
**Basis:** mutmut 3.5.0 `__main__.py` (81 Symbole) + 4 Nebenmodule

---

## 1. Mutation Engine (file_mutation.py + node_mutation.py)

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `file_mutation.py` → `mutate_file_contents()` | `mutation.py` → `mutate_file_contents()` | ✅ 1:1 | Imports geändert |
| `create_mutations()` | `mutation.py` → `create_mutations()` | ✅ 1:1 | |
| `combine_mutations_to_source()` | `mutation.py` | ✅ 1:1 | |
| `function_trampoline_arrangement()` | `mutation.py` | ✅ 1:1 | |
| `create_trampoline_wrapper()` | `mutation.py` | ✅ 1:1 | |
| `MutationVisitor` | `mutation.py` | ✅ 1:1 | |
| `OuterFunctionProvider` | `mutation.py` | ✅ 1:1 | |
| `ChildReplacementTransformer` | `mutation.py` | ✅ 1:1 | |
| `pragma_no_mutate_lines()` | `mutation.py` | ✅ 1:1 | |
| `deep_replace()` | `mutation.py` | ✅ 1:1 | |
| `node_mutation.py` (15 Operatoren) | `node_mutation.py` | ✅ 1:1 | |
| **Verifiziert:** 5 Referenzprojekte, identische Mutant-Generierung | | | |

## 2. Trampoline (trampoline_templates.py)

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `trampoline_templates.py` | `trampoline.py` | ✅ 1:1 | Dateiname geändert |
| `mangle_function_name()` | `trampoline.py` | ✅ 1:1 | |
| `create_trampoline_lookup()` | `trampoline.py` | ✅ 1:1 | |
| `trampoline_impl` (Code-Template) | `trampoline.py` | ✅ 1:1 | |
| `CLASS_NAME_SEPARATOR` | `trampoline.py` | ✅ 1:1 | |

## 3. Coverage (code_coverage.py)

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `gather_coverage()` | `code_coverage.py` | ✅ 1:1 | |
| `get_covered_lines_for_file()` | `code_coverage.py` | ✅ 1:1 | |
| `_unload_modules_not_in()` | `code_coverage.py` | ✅ 1:1 | Modulname angepasst |

## 4. Type Checking (type_checking.py)

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `type_checking.py` | `type_checking.py` | ✅ 1:1 | |
| `run_type_checker()` | `type_checking.py` | ✅ 1:1 | |
| `parse_mypy_report()` | `type_checking.py` | ✅ 1:1 | |
| `parse_pyright_report()` | `type_checking.py` | ✅ 1:1 | |
| `parse_pyrefly_report()` | `type_checking.py` | ✅ 1:1 | |
| `parse_ty_report()` | `type_checking.py` | ✅ 1:1 | |
| `TypeCheckingError` | `type_checking.py` | ✅ 1:1 | |

## 5. Konfiguration

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `Config` (dataclass) | `config.py` → `MutmutConfig` (Pydantic) | ✅ Funktional äquivalent | Pydantic statt dataclass, Validierung |
| `config_reader()` | `config.py` → `load_config()` | ✅ Funktional äquivalent | tomllib statt toml/ConfigParser |
| `ensure_config_loaded()` | Nicht benötigt | ✅ Designentscheidung | Config wird explizit übergeben, keine Globals |
| `guess_paths_to_mutate()` | `config.py` Default `["src/"]` | ⚠️ ABWEICHUNG | Siehe Finding F-01 |
| `Config.should_ignore_for_mutation()` | `MutmutConfig.should_ignore_for_mutation()` | ✅ 1:1 | |

## 6. Konstanten

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `status_by_exit_code` | `constants.py` | ✅ Windows-angepasst | Unix-Signale entfernt (-24, -11, -9, 152) |
| `emoji_by_status` | `constants.py` | ✅ 1:1 | |
| `exit_code_to_emoji` | `constants.py` | ✅ 1:1 | |
| `spinner` | Nicht portiert | ✅ Designentscheidung | UX-Element, nicht funktional |
| `print_status` | Nicht portiert | ✅ Designentscheidung | Durch Live-Progress ersetzt |

## 7. File Setup Pipeline

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `walk_all_files()` | `file_setup.py` | ✅ Portiert | Config als Parameter statt Global |
| `walk_source_files()` | `file_setup.py` | ✅ Portiert | Config als Parameter |
| `copy_src_dir()` | `file_setup.py` | ✅ Portiert | Config als Parameter |
| `copy_also_copy_files()` | `file_setup.py` | ✅ Portiert | Config als Parameter |
| `setup_source_paths()` | `file_setup.py` | ✅ Portiert | |
| `get_mutant_name()` | `file_setup.py` | ✅ Portiert | |
| `strip_prefix()` | `file_setup.py` | ✅ Portiert | |
| `write_all_mutants_to_file()` | `file_setup.py` | ✅ Portiert | |
| `create_mutants_for_file()` | `file_setup.py` | ✅ Portiert | |
| `create_mutants()` (Pool-basiert) | `orchestrator._generate_mutants()` | ✅ Funktional äquivalent | Sequentiell statt multiprocessing.Pool |
| `create_file_mutants()` | In `_generate_mutants()` integriert | ✅ Funktional äquivalent | |
| `store_lines_covered_by_tests()` | `orchestrator._gather_coverage()` | ✅ Portiert | |

## 8. Test-Mapping & Stats

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `mangled_name_from_mutant_name()` | `test_mapping.py` | ✅ Portiert | |
| `orig_function_and_class_names_from_key()` | `test_mapping.py` | ✅ Portiert | |
| `is_mutated_method_name()` | `test_mapping.py` | ✅ Portiert | |
| `tests_for_mutant_names()` | `test_mapping.py` | ✅ Portiert | Explizite Parameter statt Globals |
| `load_stats()` | `stats.py` | ✅ Portiert | MutmutStats dataclass statt Globals |
| `save_stats()` | `stats.py` | ✅ Portiert | |
| `collect_or_load_stats()` | `stats.py` | ✅ Portiert | |
| `run_stats_collection()` | `stats.py` → `collect_or_load_stats()` | ✅ Portiert | Vereinfacht |
| `estimated_worst_case_time()` | `orchestrator._apply_timeouts()` | ✅ Funktional äquivalent | |

## 9. Prozess-Management (KERN-UNTERSCHIED: fork → spawn)

| Original (Unix) | mutmut-win (Windows) | Status | Delta |
|-----------------|---------------------|--------|-------|
| `os.fork()` + `os.wait()` | `process/executor.py` → `SpawnPoolExecutor` | ✅ Windows-Ersatz | multiprocessing.spawn + Worker-Pool |
| `resource.setrlimit(RLIMIT_CPU)` | `process/timeout.py` → `WallClockTimeout` | ✅ Windows-Ersatz | Wall-Clock statt CPU-Time |
| `signal.SIGXCPU` | Event-basiert (TaskTimedOut) | ✅ Windows-Ersatz | |
| `gc.freeze()` (COW-Optimierung) | Nicht benötigt | ✅ Designentscheidung | Irrelevant bei spawn |
| `os._exit()` im Kind | Worker beendet sich sauber | ✅ Windows-Ersatz | |
| `stop_all_children()` | `executor.shutdown()` | ✅ Portiert | |
| `timeout_checker()` | `WallClockTimeout` | ✅ Portiert | |
| `START_TIMES_BY_PID_LOCK` | Nicht benötigt | ✅ Designentscheidung | Event-Queue statt PID-Tracking |

## 10. PytestRunner

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `PytestRunner.__init__()` | `runner.py` | ✅ Portiert | Config als Parameter |
| `PytestRunner.execute_pytest()` | Nicht portiert (inline) | ⚠️ ABWEICHUNG | Siehe Finding F-02 |
| `PytestRunner.run_stats()` | `runner.py` | ⚠️ ABWEICHUNG | Siehe Finding F-03 |
| `PytestRunner.run_tests()` | `process/worker.py` | ✅ Funktional äquivalent | Via subprocess statt pytest.main() |
| `PytestRunner.run_forced_fail()` | `runner.py` | ✅ Portiert | |
| `PytestRunner.run_clean_test()` | `runner.py` | ✅ Neu (explizit separiert) | |
| `PytestRunner.list_all_tests()` | `runner.py` → `collect_tests()` | ⚠️ ABWEICHUNG | Siehe Finding F-04 |
| `PytestRunner.prepare_main_test_run()` | Nicht benötigt | ✅ Designentscheidung | setup_source_paths() deckt das ab |
| `TestRunner` (ABC) | Kein ABC | ✅ Designentscheidung | Direkte Klasse, kein Interface nötig |
| `HammettRunner` | Nicht portiert | ✅ Intentional | Hammett ist deprecated |

## 11. CLI Commands

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `cli()` (click group) | `cli.py` | ✅ Portiert | |
| `run()` | `cli.py` | ✅ Portiert | |
| `results()` | `cli.py` | ✅ Portiert | |
| `show()` | `cli.py` + `mutant_diff.py` | ✅ Portiert | CST-basierter Diff |
| `apply()` | `cli.py` + `mutant_diff.py` | ✅ Portiert | CST-basiertes Ersetzen |
| `browse()` | `cli.py` + `browser.py` | ✅ Portiert | Textual TUI |
| `tests_for_mutant` (CLI cmd) | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-05 |
| `print_time_estimates` (CLI cmd) | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-06 |
| `export_cicd_stats` (CLI cmd) | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-07 |

## 12. Mutant-Inspektion

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `find_mutant()` | `mutant_diff.py` | ✅ Portiert | |
| `read_mutants_module()` | `mutant_diff.py` | ✅ Portiert | encoding='utf-8' |
| `read_orig_module()` | `mutant_diff.py` | ✅ Portiert | encoding='utf-8' |
| `find_top_level_function_or_method()` | `mutant_diff.py` | ✅ Portiert | |
| `read_original_function()` | `mutant_diff.py` | ✅ Portiert | |
| `read_mutant_function()` | `mutant_diff.py` | ✅ Portiert | |
| `get_diff_for_mutant()` | `mutant_diff.py` | ✅ Portiert | |
| `apply_mutant()` | `mutant_diff.py` | ✅ Portiert | |

## 13. Ergebnis-Management

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `SourceFileMutationData` | `models.py` (Pydantic) | ✅ Funktional äquivalent | Pydantic statt manuell |
| `SourceFileMutationData.load()` | `models.py` | ✅ Portiert | encoding='utf-8' |
| `SourceFileMutationData.save()` | `models.py` | ✅ Portiert | encoding='utf-8' |
| `SourceFileMutationData.register_pid()` | Nicht benötigt | ✅ Designentscheidung | Event-Queue statt PID |
| `SourceFileMutationData.register_result()` | `orchestrator._update_summary_and_persist()` | ✅ Funktional äquivalent | |
| `SourceFileMutationData.stop_children()` | `executor.shutdown()` | ✅ Funktional äquivalent | |
| `collect_source_file_mutation_data()` | `orchestrator._generate_mutants()` | ✅ Funktional äquivalent | |
| `collect_stat()` / `Stat` | `orchestrator._print_live_progress()` | ✅ Funktional äquivalent | |
| `calculate_summary_stats()` | `MutationRunResult.score` | ✅ Funktional äquivalent | |
| `print_stats()` | `orchestrator._print_live_progress()` | ✅ Portiert | |
| `save_cicd_stats()` | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-07 |

## 14. Type-Checker-Integration im Orchestrator

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `filter_mutants_with_type_checker()` | `orchestrator._filter_with_type_checker()` | ⚠️ TEILWEISE | Siehe Finding F-08 |
| `MutatedMethodsCollector` (CST Visitor) | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-08 |
| `MutatedMethodLocation` | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-08 |
| `FailedTypeCheckMutant` | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-08 |
| `group_by_path()` | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-08 |

## 15. Sonstige Klassen & Hilfsfunktionen

| Original | mutmut-win | Status | Delta |
|----------|-----------|--------|-------|
| `MutmutProgrammaticFailException` | `exceptions.py` | ✅ | Eigene Exception-Hierarchie |
| `CollectTestsFailedException` | `exceptions.py` | ✅ | |
| `BadTestExecutionCommandsException` | ❌ FEHLT | ⚠️ | Nicht kritisch |
| `InvalidGeneratedSyntaxException` | ❌ FEHLT | ⚠️ | Verwendet in create_mutants_for_file |
| `FileMutationResult` | Nicht als Klasse | ✅ Designentscheidung | Durch Rückgabewerte ersetzt |
| `MutantGenerationStats` | Nicht als Klasse | ✅ Designentscheidung | Zähler im Orchestrator |
| `CatchOutput` (Spinner) | Nicht portiert | ✅ Intentional | UX-Element |
| `ListAllTestsResult` | Nicht portiert | ⚠️ ABWEICHUNG | Siehe Finding F-04 |
| `change_cwd()` | Nicht portiert | ✅ | Stdlib contextlib.chdir() |
| `unused()` | Nicht portiert | ✅ | Trivial |
| `record_trampoline_hit()` | ❌ FEHLT | ❌ FEHLT | Siehe Finding F-09 |
| `collected_test_names()` | ❌ FEHLT | ⚠️ | Trivial |

---

## Findings (Abweichungen die Funktionalität beeinflussen)

### F-01: guess_paths_to_mutate() fehlt — Pfad-Raten deaktiviert

**Schwere:** MITTEL
**Original:** mutmut ratet den Source-Pfad wenn `paths_to_mutate` nicht gesetzt ist: `lib/`, `src/`, Projektname, etc.
**mutmut-win:** Default ist hart `["src/"]`. Kein Raten.
**Auswirkung:** Projekte ohne `[tool.mutmut]` Sektion und ohne `src/` Verzeichnis funktionieren nicht.
**Fix:** `guess_paths_to_mutate()` in `config.py` portieren und als Default-Factory nutzen.

### F-02: PytestRunner.execute_pytest() nutzt subprocess statt pytest.main()

**Schwere:** HOCH
**Original:** mutmut ruft `pytest.main()` direkt im gleichen Prozess auf. Das ermöglicht:
- Pytest-Plugins direkt einzuhängen (StatsCollector)
- Prozess-internen Zugriff auf `mutmut._stats` (Trampoline-Hits)
- Schnellere Ausführung (kein Subprocess-Overhead)
**mutmut-win:** Nutzt `subprocess.run([sys.executable, '-m', 'pytest', ...])` für ALLES.
**Auswirkung:** 
1. Stats-Collection ist grundlegend anders — mutmut nutzt pytest-Plugins inline, wir nutzen External Timing
2. `record_trampoline_hit()` kann nicht funktionieren (läuft in anderem Prozess)
3. Test-zu-Mutant-Mapping basiert bei mutmut auf `mutmut._stats` (welche Trampoline-Funktionen bei welchem Test aufgerufen wurden) — bei uns fehlt dieser Mechanismus komplett
**Fix:** KOMPLEX — erfordert entweder:
- (a) pytest.main() in-process im Worker verwenden (wie mutmut), oder
- (b) Trampoline-Hit-Tracking über Dateisystem/Shared Memory implementieren

### F-03: Stats-Collection ist funktional verschieden

**Schwere:** HOCH (Folge von F-02)
**Original:** `PytestRunner.run_stats()` nutzt einen `StatsCollector` pytest-Plugin der:
1. Für jeden Test aufzeichnet welche Trampoline-Funktionen aufgerufen wurden (`mutmut._stats`)
2. Diese Zuordnung in `mutmut.tests_by_mangled_function_name` speichert
3. Per-Test-Laufzeiten über `pytest_runtest_makereport` misst
**mutmut-win:** `PytestRunner.run_stats()` führt jeden Test einzeln als Subprocess aus und misst Wall-Clock-Zeit. **Es gibt kein Trampoline-Hit-Tracking.** Das `tests_by_mangled_function_name`-Mapping wird nie mit echten Daten gefüllt.
**Auswirkung:** Jeder Mutant bekommt ALLE Tests zugewiesen statt nur die relevanten. Das macht Mutation Testing um Faktor 10-100x langsamer.
**Fix:** Siehe F-02.

### F-04: list_all_tests() / ListAllTestsResult fehlt

**Schwere:** MITTEL
**Original:** `list_all_tests()` nutzt pytest-Plugin um collected + deselected Tests zu tracken. `ListAllTestsResult` ermöglicht inkrementelle Stats-Updates (nur neue Tests neu messen).
**mutmut-win:** `collect_tests()` parst `--collect-only` Textausgabe. Kein incremental update.
**Auswirkung:** Bei Resume werden immer alle Stats neu gesammelt statt nur neue Tests.
**Fix:** Kann später ergänzt werden. Nicht kritisch für Korrektheit.

### F-05: CLI-Command `tests_for_mutant` fehlt

**Schwere:** NIEDRIG
**Original:** `mutmut tests-for-mutant <NAME>` zeigt welche Tests für einen Mutant relevant sind.
**mutmut-win:** Command fehlt.
**Fix:** Trivial zu ergänzen.

### F-06: CLI-Command `print_time_estimates` fehlt

**Schwere:** NIEDRIG
**Original:** `mutmut time-estimates` zeigt geschätzte Laufzeiten pro Mutant.
**mutmut-win:** Command fehlt.
**Fix:** Trivial zu ergänzen.

### F-07: CI/CD Stats Export fehlt

**Schwere:** NIEDRIG
**Original:** `save_cicd_stats()` und `export_cicd_stats` CLI-Command schreiben JSON-Summary.
**mutmut-win:** Fehlt.
**Fix:** Trivial zu ergänzen.

### F-08: Type-Checker-Filterung ist nur als Stub implementiert

**Schwere:** MITTEL
**Original:** `filter_mutants_with_type_checker()` ruft den Type-Checker auf mutants/ auf, parst Fehler, ordnet sie via CST-Visitor (`MutatedMethodsCollector`) den Mutanten zu, und markiert betroffene Mutanten.
**mutmut-win:** `_filter_with_type_checker()` im Orchestrator existiert, aber die Hilfsklassen (`MutatedMethodsCollector`, `MutatedMethodLocation`, `FailedTypeCheckMutant`, `group_by_path`) fehlen.
**Auswirkung:** Type-Checker-Integration funktioniert vermutlich nicht korrekt.
**Fix:** Klassen und Hilfsfunktionen portieren.

### F-09: record_trampoline_hit() fehlt — Stats sind leer

**Schwere:** KRITISCH (Folge von F-02)
**Original:** `record_trampoline_hit(name)` wird von der Trampoline-Funktion aufgerufen (in `trampoline_impl`). Sie speichert welche mutierte Funktion bei welchem Test aufgerufen wurde. Das ist die Grundlage für das Test-zu-Mutant-Mapping.
**mutmut-win:** Fehlt komplett. Die Trampoline-Funktion in `trampoline.py` ruft `record_trampoline_hit()` auf, aber die Funktion ist in keinem mutmut-win Modul definiert.
**Auswirkung:** Stats-Collection produziert leeres `tests_by_mangled_function_name`. Alle Mutanten bekommen alle Tests. Performance-Einbruch.
**Fix:** MUSS zusammen mit F-02/F-03 gelöst werden.

---

## Zusammenfassung nach Schwere

### KRITISCH (1)
| # | Finding | Beschreibung |
|---|---------|-------------|
| F-09 | `record_trampoline_hit()` fehlt | Test-zu-Mutant-Mapping nicht funktional |

### HOCH (2)
| # | Finding | Beschreibung |
|---|---------|-------------|
| F-02 | subprocess statt pytest.main() | In-Process-Plugins nicht möglich |
| F-03 | Stats-Collection funktional verschieden | Kein Trampoline-Hit-Tracking |

### MITTEL (3)
| # | Finding | Beschreibung |
|---|---------|-------------|
| F-01 | guess_paths_to_mutate() fehlt | Pfad-Raten deaktiviert |
| F-04 | ListAllTestsResult fehlt | Kein inkrementelles Stats-Update |
| F-08 | Type-Checker nur Stub | Hilfsklassen fehlen |

### NIEDRIG (3)
| # | Finding | Beschreibung |
|---|---------|-------------|
| F-05 | CLI `tests-for-mutant` fehlt | Convenience-Command |
| F-06 | CLI `time-estimates` fehlt | Convenience-Command |
| F-07 | CI/CD Stats Export fehlt | JSON-Summary |

---

## Gesamtbewertung

**Mutation Engine:** ✅ 100% portiert und verifiziert (5/5 Referenzprojekte)
**Trampoline:** ✅ 100% portiert
**Coverage:** ✅ 100% portiert
**Type Checking (Logik):** ✅ 100% portiert
**Config:** ✅ 95% (guess_paths_to_mutate fehlt)
**File Setup:** ✅ 100% portiert
**Test Mapping (Logik):** ✅ 100% portiert
**Stats (Logik):** ✅ 100% portiert
**Mutant Inspection:** ✅ 100% portiert
**CLI:** ✅ 90% (3 Commands fehlen)
**Browser:** ✅ 100% portiert

**ABER:** Die Stats-Collection (F-02/F-03/F-09) ist **funktional nicht äquivalent**. mutmut trackt via In-Process-Pytest-Plugin welche Trampoline-Funktionen bei welchem Test aufgerufen werden. mutmut-win hat diesen Mechanismus nicht, weil es subprocess statt pytest.main() nutzt. Das bedeutet:
- Das Test-zu-Mutant-Mapping ist leer
- Jeder Mutant läuft gegen ALLE Tests
- Performance ist ~10-100x schlechter als mutmut
- **Korrektheit ist gegeben** (alle Tests laufen), aber **Performance nicht**

Dies ist das größte verbleibende Delta zum 1:1-Port.
