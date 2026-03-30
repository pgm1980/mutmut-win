# 360° Cross-Check v2 — Implementierungstiefe

**Projekt:** mutmut-win v0.3.0 vs. mutmut 3.5.0  
**Datum:** 2026-03-30  
**Methode:** Jede Funktion/Klasse aus mutmut 3.5.0 wurde mit `find_symbol(include_body=true)` gelesen und gegen ihr Gegenstueck in mutmut-win verglichen.

## Legende

| Symbol | Bedeutung |
|--------|-----------|
| IDENTISCH | Logik 1:1 uebernommen (ggf. Formatierung/Docstrings angepasst) |
| AEQUIVALENT | Andere Syntax/Struktur, aber funktional gleiches Verhalten |
| ABWEICHUNG | Abweichendes Verhalten, das Ergebnisse beeinflussen kann |
| FEHLT | Funktion/Klasse existiert in mutmut-win nicht |
| NEU | Funktion existiert nur in mutmut-win (kein Gegenstueck im Original) |

---

## 1. Hauptablauf: `_run()` vs. `MutationOrchestrator.run()`

### Architekturelle Aenderung

Das Original hat eine monolithische `_run()`-Funktion (170 Zeilen) in `__main__.py`. mutmut-win zerlegt dies in:
- `MutationOrchestrator.run()` als oeffentliche Pipeline
- `_generate_mutants()`, `_filter_with_type_checker()`, `_assign_tests_to_tasks()`, `_apply_timeouts()` als Unterfunktionen
- `SpawnPoolExecutor` fuer Worker-Management
- `WallClockTimeout` fuer Timeout-Ueberwachung

### Schritt-fuer-Schritt-Vergleich

| Schritt | Original `_run()` | mutmut-win `Orchestrator.run()` | Status |
|---------|-------------------|--------------------------------|--------|
| 1. Env-Variable setzen | `os.environ['MUTANT_UNDER_TEST'] = 'mutant_generation'` | Nicht gesetzt | ABWEICHUNG |
| 2. Config laden | `ensure_config_loaded()` | Config wird per Konstruktor uebergeben | AEQUIVALENT |
| 3. max_children | `os.cpu_count() or 4` | `MutmutConfig.max_children` (Default: `os.cpu_count() or 4`) | AEQUIVALENT |
| 4. mutants/ erstellen | `makedirs(Path('mutants'))` | In `_generate_mutants()` implizit via `copy_src_dir` | AEQUIVALENT |
| 5. CatchOutput/Spinner | `CatchOutput(spinner_title='Generating mutants')` | Kein CatchOutput, kein Spinner | ABWEICHUNG |
| 6. copy_src_dir | Aufgerufen | Aufgerufen (identische Implementierung) | IDENTISCH |
| 7. copy_also_copy_files | Aufgerufen | Aufgerufen | IDENTISCH |
| 8. setup_source_paths | Aufgerufen | Aufgerufen (identische Logik) | IDENTISCH |
| 9. store_lines_covered | `store_lines_covered_by_tests()` -> globale `_covered_lines` | `_gather_coverage()` -> lokales `covered_lines_map` | AEQUIVALENT |
| 10. create_mutants | `Pool(processes=max_children).imap_unordered(create_file_mutants, ...)` | Sequentielle Schleife in `_generate_mutants()` | ABWEICHUNG |
| 11. Type-Checker-Filter | `filter_mutants_with_type_checker()` mit CST-basiertem Line-Matching | `_filter_with_type_checker()` mit Modul-Prefix-Heuristik | ABWEICHUNG |
| 12. Runner erstellen | `PytestRunner()` | `PytestRunner(config)` per Konstruktor | AEQUIVALENT |
| 13. prepare_main_test_run | `runner.prepare_main_test_run()` | Keine separate Methode — nicht noetig bei Subprocess-Ansatz | AEQUIVALENT |
| 14. Stats sammeln | `collect_or_load_stats(runner)` | `collect_or_load_stats(runner)` | AEQUIVALENT |
| 15. collect_source_file_mutation_data | Laeuft ueber `walk_source_files()` und baut `(m, mutant_name, result)` Tripel | In `_generate_mutants()` integriert, baut `MutationTask`-Objekte | AEQUIVALENT |
| 16. Clean Tests | `runner.run_tests(mutant_name=None, tests=tests)` in-process | `runner.run_clean_test()` per Subprocess | AEQUIVALENT |
| 17. Forced Fail | `run_forced_fail_test(runner)` | `runner.run_forced_fail(first_mutant)` | AEQUIVALENT |
| 18. Mutanten sortieren | `sorted(mutants, key=lambda x: estimated_worst_case_time(x[1]))` | `_apply_timeouts()` berechnet, aber kein explizites Sortieren | ABWEICHUNG |
| 19. gc.freeze() | `gc.freeze()` | Nicht vorhanden | ABWEICHUNG |
| 20. timeout_checker Thread | `Thread(target=timeout_checker(mutants), daemon=True).start()` | `WallClockTimeout` Klasse (register/unregister per Task) | AEQUIVALENT |
| 21. Mutation-Loop | `os.fork()` pro Mutant, `os.wait()` zum Ernten | `SpawnPoolExecutor` mit `multiprocessing.Process(spawn)` + Queue | ABWEICHUNG |
| 22. SIGXCPU / resource.setrlimit | `resource.setrlimit(RLIMIT_CPU, ...)` fuer CPU-Time-Limit | `WallClockTimeout` mit Wall-Clock-Deadline | AEQUIVALENT |
| 23. CatchOutput im Child | `CatchOutput()` um stdout/stderr zu unterdruecken | `capture_output=True` in subprocess.run | AEQUIVALENT |
| 24. Exit Code -> Result | `m.register_result(pid, exit_code)` mit PID-Tracking | `TaskCompleted` Event via Queue -> `_update_summary_and_persist` | AEQUIVALENT |
| 25. KeyboardInterrupt | `stop_all_children(mutants)` -> SIGTERM per PID | `executor.shutdown(timeout=5.0)` -> kill() | AEQUIVALENT |
| 26. Statistik-Ausgabe | `print_stats(force_output=True)` mit Emoji-Status | `_print_summary(result)` mit tabellarischer Ausgabe | AEQUIVALENT |
| 27. Ergebnis-Persistenz | `m.save()` in `register_result` (nach jedem Mutant) | `save_result()` in SQLite + `sfd.save()` am Ende | ABWEICHUNG |
| 28. Mutant-spezifische Ergebnisse | Wenn `mutant_names`, detaillierte Ausgabe pro Mutant | `"Note: mutant name filtering not yet implemented"` | ABWEICHUNG |

### Kritische Abweichungen im Hauptablauf

**A1: MUTANT_UNDER_TEST nicht gesetzt bei Mutant-Generierung**
- Original setzt `os.environ['MUTANT_UNDER_TEST'] = 'mutant_generation'` vor dem Generieren
- mutmut-win setzt dies nicht
- **Auswirkung:** Gering — die Trampoline-Logik prueft nur 'fail', 'stats' und mutant-spezifische Prefixe

**A2: Kein CatchOutput/Spinner**
- Original unterdrueckt stdout/stderr waehrend Generierung/Tests und zeigt Spinner
- mutmut-win hat keinen Spinner-Mechanismus
- **Auswirkung:** UX-Unterschied, keine funktionale Auswirkung

**A3: Sequentielle statt parallele Mutant-Generierung**
- Original: `Pool(processes=max_children).imap_unordered(create_file_mutants, ...)`
- mutmut-win: Sequentielle Schleife in `_generate_mutants()`
- **Auswirkung:** Langsamere Mutant-Generierung bei grossen Projekten

**A4: Type-Checker-Filter vereinfacht**
- Original: CST-basiertes Line-Number-Matching (MutatedMethodsCollector -> Error Line -> Mutant)
- mutmut-win: Modul-Prefix-Heuristik (Error-Pfad -> Module-Name -> alle Mutanten des Moduls)
- **Auswirkung:** Uebereifrig — markiert ggf. ALLE Mutanten eines Moduls als "caught by type check", obwohl nur eine bestimmte Methode betroffen ist

**A5: Kein gc.freeze()**
- Original: `gc.freeze()` vor dem Mutation-Loop
- mutmut-win: Nicht vorhanden
- **Auswirkung:** Bei `spawn`-basiertem Multiprocessing irrelevant (kein Copy-on-Write wie bei fork)

**A6: Keine Sortierung nach geschaetzter Laufzeit**
- Original: Mutanten werden nach `estimated_worst_case_time` sortiert (schnelle zuerst)
- mutmut-win: Keine explizite Sortierung
- **Auswirkung:** Suboptimale Reihenfolge — langsame Mutanten koennten frueh starten und den Pool blockieren

**A7: Mutant-Name-Filterung nicht implementiert**
- Original: `mutant_names` Parameter filtert auf spezifische Mutanten
- mutmut-win: Gibt Warnung aus, fuehrt aber alle Mutanten aus
- **Auswirkung:** Funktionalitaetsverlust — Re-Test einzelner Mutanten nicht moeglich

**A8: Ergebnis-Persistenz unterschiedlich**
- Original: JSON-Meta-Dateien (`mutants/*.meta`) mit sofortigem Save nach jedem Result
- mutmut-win: SQLite-Datenbank (`.mutmut-cache/mutmut-cache.db`) + JSON-Meta am Ende
- **Auswirkung:** Dual-Persistenz statt nur JSON; bei Absturz gehen weniger Ergebnisse verloren (SQLite ist transaktional)

---

## 2. PytestRunner

### 2.1 Klassen-Architektur

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Basisklasse | `TestRunner(ABC)` | Keine Basisklasse | ABWEICHUNG |
| Config-Zugriff | Globales `mutmut.config` | Per Konstruktor `self._config` | AEQUIVALENT |
| Ausfuehrungsmodus | In-Process (`pytest.main()`) | Subprocess (`subprocess.run`) | ABWEICHUNG |

### 2.2 Methoden-Vergleich

#### `__init__`
- Original: Liest `pytest_add_cli_args`, `pytest_add_cli_args_test_selection`, `tests_dir` aus globalem Config
- mutmut-win: Speichert Config-Referenz
- **Status:** AEQUIVALENT

#### `execute_pytest` vs. `_base_pytest_cmd`
- Original: `pytest.main(['--rootdir=.', '--tb=native'] + params + self._pytest_add_cli_args)` — in-process
- mutmut-win: `[sys.executable, '-m', 'pytest']` — nur Basis-Command, kein execute
- **Status:** ABWEICHUNG — In-Process vs. Subprocess

#### `run_stats`
- Original: In-Process mit `StatsCollector` Plugin, `change_cwd('mutants')`
- mutmut-win: In-Process mit `StatsCollector` Plugin, `os.chdir('mutants')`
- StatsCollector-Logik: **IDENTISCH** (pytest_runtest_teardown, pytest_runtest_makereport)
- Unterschied: Original hat auch `pytest_runtest_logstart` Hook (setzt `duration_by_test[nodeid] = 0`)
- mutmut-win: Kein `pytest_runtest_logstart` — `duration_by_test` wird direkt in `makereport` aufaddiert
- **Status:** AEQUIVALENT (fehlender logstart ist harmlos, da `dict.get(key, 0.0)` ohnehin 0 liefert)

#### `run_tests` (Original) vs. nicht vorhanden (mutmut-win)
- Original: `runner.run_tests(mutant_name=mutant_name, tests=tests)` — wird im fork-Child aufgerufen
- mutmut-win: Worker fuehrt `subprocess.run(['pytest', ...], env={MUTANT_ENV_VAR: mutant_name})` aus
- **Status:** AEQUIVALENT — gleiche Semantik, andere Mechanik

#### `run_forced_fail`
- Original: In-Process `pytest.main(['-x', '-q'] + test_selection)` mit `MUTANT_UNDER_TEST='fail'`
- mutmut-win: Subprocess mit `env[MUTANT_ENV_VAR] = 'fail'`
- **Status:** AEQUIVALENT

#### `list_all_tests` (Original) vs. `collect_tests` (mutmut-win)
- Original: In-Process mit `TestsCollector` Plugin (collected_nodeids - deselected_nodeids)
- mutmut-win: Subprocess `pytest --collect-only -q --no-header`, parst stdout-Zeilen mit `::` 
- **Status:** AEQUIVALENT — aber das Parsing ist fragiler (z.B. bei Warnungen in der Ausgabe)

#### `run_clean_test` (nur mutmut-win)
- Existiert nur in mutmut-win
- Original fuehrt Clean-Test direkt via `runner.run_tests(mutant_name=None, tests=tests)` aus
- **Status:** NEU — funktional aequivalent zum Original-Aufruf

#### `prepare_main_test_run` (nur Original)
- Original: Leere Implementierung in `TestRunner`, ueberschrieben in `HammettRunner`
- mutmut-win: Nicht vorhanden
- **Status:** FEHLT — aber nur fuer HammettRunner relevant, nicht fuer PytestRunner

---

## 3. Trampoline-Kette

### 3.1 `trampoline_impl` (Template-String)

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Import-Pfad fuer fail | `from mutmut.__main__ import MutmutProgrammaticFailException` | `from mutmut_win.__main__ import MutmutProgrammaticFailException` | IDENTISCH (Paketname angepasst) |
| Import-Pfad fuer stats | `from mutmut.__main__ import record_trampoline_hit` | `from mutmut_win.__main__ import record_trampoline_hit` | IDENTISCH (Paketname angepasst) |
| Trampoline-Logik | Identisch | Identisch | IDENTISCH |
| Type-Ignore-Kommentare | Identisch | Identisch | IDENTISCH |
| Mutant-Dispatch | `mutants[mutant_name](*call_args, **call_kwargs)` | Identisch | IDENTISCH |

**Status:** IDENTISCH (nur Paket-Import-Pfade angepasst)

### 3.2 `record_trampoline_hit`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Signatur | `record_trampoline_hit(name)` | `record_trampoline_hit(name: str) -> None` | IDENTISCH |
| max_stack_depth Pruefung | Ja — prueft `mutmut.config.max_stack_depth` mit Frame-Traversal | **NEIN** | ABWEICHUNG |
| Stats-Eintrag | `mutmut._stats.add(name)` | `_state._stats.add(name)` | IDENTISCH |

**ABWEICHUNG:** mutmut-win fehlt die `max_stack_depth`-Pruefung. Im Original wird bei `max_stack_depth != -1` der Call-Stack traversiert, um tief verschachtelte Aufrufe zu ignorieren. In mutmut-win wird JEDER Trampoline-Hit registriert, unabhaengig von der Stack-Tiefe.

**Auswirkung:** Bei Projekten die `max_stack_depth` konfigurieren, werden mehr Tests einem Mutanten zugeordnet als im Original. Default ist `-1` (unbegrenzt), daher bei Standard-Konfiguration kein Unterschied.

### 3.3 `create_trampoline_lookup`
**Status:** IDENTISCH (nur Formatierung anders, f-String-Ausgabe identisch)

### 3.4 `mangle_function_name`
- Original: `assert` fuer Validierung
- mutmut-win: `raise ValueError` statt assert
- **Status:** AEQUIVALENT (robustere Fehlerbehandlung)

### 3.5 `_state` (Globaler Zustand)

| Variable | Original (`mutmut/__init__.py`) | mutmut-win (`_state.py`) | Status |
|----------|---------------------------------|--------------------------|--------|
| `_stats` | `set()` | `set()` | IDENTISCH |
| `tests_by_mangled_function_name` | `defaultdict(set)` | `defaultdict(set)` | IDENTISCH |
| `duration_by_test` | `dict()` | `dict()` | IDENTISCH |
| `stats_time` | `None` | `None` | IDENTISCH |
| `config` | Globales `Config`-Objekt | **FEHLT** — Config ist nicht global | ABWEICHUNG |
| `_covered_lines` | Globales Dict | **FEHLT** — lokal in Orchestrator | AEQUIVALENT |

---

## 4. Type-Checker-Kette

### 4.1 `run_type_checker`
**Status:** IDENTISCH (Logik 1:1, nur Formatierung/Docstrings)

### 4.2 `parse_pyright_report` / `parse_mypy_report` / `parse_pyrefly_report` / `parse_ty_report`
**Status:** IDENTISCH (in beiden Codebases identische Implementierung in `type_checking.py`)

### 4.3 `filter_mutants_with_type_checker` vs. `_filter_with_type_checker`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| CWD-Wechsel | `change_cwd(Path('mutants'))` | `os.chdir(mutants_dir)` mit finally | AEQUIVALENT |
| Error-to-Mutant-Mapping | CST-basiert: `MutatedMethodsCollector` -> Line-Range -> Mutant | Modul-Prefix-Heuristik: Error-Pfad -> Modul-Name -> alle Mutanten | ABWEICHUNG |
| Rueckgabeformat | `dict[str, FailedTypeCheckMutant]` | `tuple[list[MutationTask], set[str]]` | ABWEICHUNG |
| Fehler-Granularitaet | Exakt: Nur die betroffene Funktion wird als "caught" markiert | Grob: Alle Mutanten des betroffenen Moduls werden markiert | ABWEICHUNG |

**ABWEICHUNG:** Die Type-Checker-Integration in mutmut-win ist eine vereinfachte Approximation. Im Original wird per CST-Analyse exakt bestimmt, WELCHE Funktion den Type-Error verursacht. In mutmut-win wird jeder Mutant eines betroffenen Moduls als "caught" markiert — auch Mutanten die keinen Type-Error ausloesen.

### 4.4 `MutatedMethodsCollector`
**Status:** IDENTISCH (in `type_checker_filter.py`, 1:1 portiert)

### 4.5 `group_by_path`
**Status:** IDENTISCH

### 4.6 `is_mutated_method_name`
**Status:** IDENTISCH

### 4.7 `MutatedMethodLocation` / `FailedTypeCheckMutant`
**Status:** IDENTISCH (Datenklassen in `type_checker_filter.py`)

---

## 5. CLI-Commands

### 5.1 `cli` (Gruppe)

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| `@click.version_option()` | Ja | **NEIN** | ABWEICHUNG |
| Help-Text | Keiner | `"mutmut-win -- Windows-native mutation testing for Python."` | AEQUIVALENT |

### 5.2 `run`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| mutant_names Argument | Unterstuetzt, filtert Mutanten | Akzeptiert, gibt aber Warnung "not yet implemented" | ABWEICHUNG |
| max_children Option | `type=int`, Default None | `type=int`, Default None | IDENTISCH |
| Fehlerbehandlung | `assert isinstance(...)` | try/except mit `sys.exit(1)` | AEQUIVALENT |

### 5.3 `results`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Datenquelle | JSON-Meta-Dateien (walk_source_files) | SQLite-Datenbank | ABWEICHUNG |
| `--all` Flag | Typ-Handling: `default=False` (kein is_flag) | `is_flag=True`, Variable `show_all` | AEQUIVALENT |
| Ausgabe | Nur Status pro Mutant | Vollstaendige Zusammenfassung mit Score-Berechnung | ABWEICHUNG |
| Score-Berechnung | Nicht vorhanden | `killed / (total - skipped - no_tests) * 100` | NEU |

### 5.4 `show`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Config laden | `ensure_config_loaded()` | `load_config()` | AEQUIVALENT |
| Diff-Ausgabe | `print(get_diff_for_mutant(mutant_name))` | Fehlerbehandlung + Header + `click.echo()` | AEQUIVALENT |
| Status-Ausgabe | `print(f'# {mutant_name}: {status}')` innerhalb get_diff_for_mutant | In CLI `click.echo(f"# {mutant_name}")` | AEQUIVALENT |

### 5.5 `apply`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Logik | `apply_mutant(mutant_name)` | `apply_mutant(mutant_name, config)` mit Fehlerbehandlung | IDENTISCH |
| Bestaetigung | Keine Ausgabe | `click.echo(f"Applied mutant '{mutant_name}'.")` | AEQUIVALENT |

### 5.6 `browse`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Datenquelle | JSON-Meta-Dateien via `walk_source_files()` | SQLite + JSON-Meta | ABWEICHUNG |
| Inline-Klasse | `ResultBrowser` direkt in `browse()` definiert | Separate Klasse in `browser.py` | AEQUIVALENT |
| Bindings | q, r, f, m, a, t | q, r, f, m, a (kein t=view_tests) | ABWEICHUNG |
| Status-Beschreibungen | Ausfuehrliche Match-Case-Beschreibungen | **FEHLT** — nur in `_on_mutant_highlighted` | Muss geprueft werden |
| retest/view_tests | Via subprocess-Relaunch | Via subprocess-Relaunch | IDENTISCH |

### 5.7 `tests-for-mutant`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Command-Name | `tests_for_mutant` (Underscore) | `tests-for-mutant` (Hyphen) | AEQUIVALENT |
| Stats laden | `load_stats()` | `load_stats(mutants_dir)` | IDENTISCH |
| Mapping-Zugriff | Globales `mutmut.tests_by_mangled_function_name` | `stats.tests_by_mangled_function_name` | AEQUIVALENT |

### 5.8 `print-time-estimates` vs. `time-estimates`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Command-Name | `print_time_estimates` | `time-estimates` | AEQUIVALENT |
| Datenquelle | `collect_source_file_mutation_data()` + `estimated_worst_case_time()` | `load_results(DEFAULT_DB_PATH)` + Stats-Berechnung | AEQUIVALENT |
| Ausgabeformat | `f'{int(time*1000)}ms {key}'` | `f'{int(estimated * 1000)}ms  {mutant_name}'` | IDENTISCH |

### 5.9 `export-cicd-stats`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Datenquelle | JSON-Meta-Dateien | SQLite-Datenbank | ABWEICHUNG |
| JSON-Felder | Kein `caught_by_type_check`, kein `score` | Enthaelt `caught_by_type_check` und `score` | NEU |
| Ausgabe | Nur Speicher-Bestaetigung | Speicher-Bestaetigung + Score-Anzeige | AEQUIVALENT |

---

## 6. SourceFileMutationData

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Basisklasse | Plain class mit `__init__` | `BaseModel` (Pydantic) | AEQUIVALENT |
| meta_path | `Path('mutants') / (str(path) + '.meta')` | Identisch (als Property) | IDENTISCH |
| load() | `json.load()` mit `meta.pop()` + assert | `json.load()` mit `meta.pop()` ohne assert, mit isinstance-Checks | AEQUIVALENT |
| save() | `json.dump()` | `json.dump()` mit `mkdir(parents=True)` | AEQUIVALENT |
| register_pid | PID->Key Mapping + START_TIMES_BY_PID_LOCK | **FEHLT** | ABWEICHUNG |
| register_result | PID-basiert, sofortiges Save + Duration-Berechnung | **FEHLT** | ABWEICHUNG |
| stop_children | `os.kill(pid, SIGTERM)` pro PID | **FEHLT** | ABWEICHUNG |
| key_by_pid | Dict[int, str] | **FEHLT** | ABWEICHUNG |
| start_time_by_pid | Dict[int, datetime] | **FEHLT** | ABWEICHUNG |
| estimated_time_of_tests_by_mutant | Dict | Identisch vorhanden | IDENTISCH |

**ABWEICHUNG:** `register_pid`, `register_result`, `stop_children` fehlen komplett. Diese Funktionen werden im Original fuer die fork-basierte Prozessverwaltung benoetigt. In mutmut-win uebernimmt der `SpawnPoolExecutor` mit Event-Queue diese Aufgaben. Die Funktion ist aequivalent umgesetzt, aber die SourceFileMutationData-Klasse ist "duenner".

---

## 7. Config-Loading

### 7.1 `Config` vs. `MutmutConfig`

| Feld | Original | mutmut-win | Status |
|------|----------|------------|--------|
| also_copy | `list[Path]` | `list[str]` | AEQUIVALENT |
| do_not_mutate | `list[str]` | `list[str]` | IDENTISCH |
| max_stack_depth | `int` | `int` | IDENTISCH |
| debug | `bool` | `bool` | IDENTISCH |
| paths_to_mutate | `list[Path]` | `list[str]` | AEQUIVALENT |
| pytest_add_cli_args | `list[str]` | `list[str]` | IDENTISCH |
| pytest_add_cli_args_test_selection | `list[str]` | `list[str]` | IDENTISCH |
| tests_dir | `list[str]` | `list[str]` | IDENTISCH |
| mutate_only_covered_lines | `bool` | `bool` | IDENTISCH |
| type_check_command | `list[str]` | `list[str]` | IDENTISCH |
| max_children | **FEHLT** | `int` (Default: cpu_count or 4) | NEU |
| timeout_multiplier | **FEHLT** | `float` (Default: 10.0) | NEU |

### 7.2 `config_reader` + `ensure_config_loaded` + `load_config` vs. `load_config`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| setup.cfg Support | Ja (ConfigParser Fallback) | **NEIN** — nur pyproject.toml | ABWEICHUNG |
| Globaler Config-Cache | `mutmut.config` global, `ensure_config_loaded()` | Kein Cache, jeder Aufruf laed neu | ABWEICHUNG |
| Default also_copy | `tests/, test/, setup.cfg, pyproject.toml, pytest.ini, .gitignore, test*.py` | Leere Liste (Default-Factory) | ABWEICHUNG |
| Pydantic-Validierung | Nein | Ja (`model_validate`) | AEQUIVALENT |
| Hyphen-to-Underscore | Nein | Ja (`key.replace("-", "_")`) | NEU |

**ABWEICHUNG:** 
1. setup.cfg wird nicht unterstuetzt — nur pyproject.toml
2. `also_copy` hat keine Default-Werte — im Original werden tests/, pyproject.toml, etc. immer mitkopiert
3. Kein globaler Config-Cache — Config wird bei jedem CLI-Aufruf neu geladen

**Kritisch:** Die fehlenden Default-`also_copy`-Werte bedeuten, dass ohne explizite Konfiguration die Test-Dateien, pyproject.toml, etc. NICHT in den mutants/-Ordner kopiert werden. Dies kann dazu fuehren, dass pytest im mutants/-Kontext keine Tests findet.

### 7.3 `guess_paths_to_mutate`
**Status:** IDENTISCH (gleiche Heuristik, nur mit `Path` statt `os.path`)

### 7.4 `should_ignore_for_mutation`
**Status:** IDENTISCH

---

## 8. Datei-Operationen (file_setup.py)

### 8.1 `walk_all_files`
**Status:** IDENTISCH (gleiche Logik, Config per Parameter statt global)

### 8.2 `walk_source_files`
**Status:** IDENTISCH

### 8.3 `copy_src_dir`
**Status:** IDENTISCH

### 8.4 `copy_also_copy_files`
**Status:** AEQUIVALENT (Config per Parameter)

### 8.5 `setup_source_paths`
**Status:** IDENTISCH (gleiche Logik)

### 8.6 `get_mutant_name`
**Status:** IDENTISCH

### 8.7 `write_all_mutants_to_file`
**Status:** IDENTISCH (in mutation.py, gleiche Signatur + Logik)

### 8.8 `create_mutants_for_file`

| Aspekt | Original | mutmut-win | Status |
|--------|----------|------------|--------|
| Rueckgabetyp | `FileMutationResult` (Dataclass) | `tuple[list[str], list[WarningMessage]]` | ABWEICHUNG |
| mtime-Check | Identisch | Identisch | IDENTISCH |
| Syntax-Validierung | Identisch | Identisch | IDENTISCH |
| Meta-Speicherung | Identisch | Identisch | IDENTISCH |
| covered_lines Parameter | **NEIN** — global ueber `mutmut._covered_lines` | Ja — expliziter Parameter | AEQUIVALENT |
| Error als Rueckgabe | `FileMutationResult(error=e)` | Exception wird nach oben propagiert | ABWEICHUNG |

### 8.9 `strip_prefix`
**Status:** IDENTISCH

---

## 9. Nebenmodule

### 9.1 `file_mutation.py` -> `mutation.py`

| Funktion | Status |
|----------|--------|
| `mutate_file_contents` | IDENTISCH |
| `create_mutations` | IDENTISCH |
| `combine_mutations_to_source` | IDENTISCH |
| `function_trampoline_arrangement` | IDENTISCH |
| `create_trampoline_wrapper` | IDENTISCH |
| `get_statements_until_func_or_class` | IDENTISCH |
| `group_by_top_level_node` | IDENTISCH |
| `pragma_no_mutate_lines` | IDENTISCH |
| `deep_replace` | IDENTISCH |
| `_is_generator` | IDENTISCH |
| `Mutation` (Dataclass) | IDENTISCH |
| `OuterFunctionProvider` | IDENTISCH |
| `OuterFunctionVisitor` | IDENTISCH |
| `MutationVisitor` | IDENTISCH |
| `ChildReplacementTransformer` | IDENTISCH |
| `IsGeneratorVisitor` | IDENTISCH |

**Gesamtstatus: IDENTISCH** — Der Mutations-Engine-Code wurde 1:1 uebernommen.

### 9.2 `node_mutation.py` -> `node_mutation.py`

| Funktion | Status |
|----------|--------|
| `operator_number` | IDENTISCH |
| `operator_string` | IDENTISCH |
| `operator_lambda` | IDENTISCH |
| `operator_dict_arguments` | IDENTISCH |
| `operator_arg_removal` | IDENTISCH |
| `operator_symmetric_string_methods_swap` | IDENTISCH |
| `operator_unsymmetrical_string_methods_swap` | IDENTISCH |
| `operator_remove_unary_ops` | IDENTISCH |
| `operator_keywords` | IDENTISCH |
| `operator_name` | IDENTISCH |
| `operator_swap_op` | IDENTISCH |
| `operator_augmented_assignment` | IDENTISCH |
| `operator_assignment` | IDENTISCH |
| `operator_match` | IDENTISCH |
| `_simple_mutation_mapping` | IDENTISCH |
| `mutation_operators` | IDENTISCH |

**Gesamtstatus: IDENTISCH** — Alle Mutations-Operatoren 1:1 uebernommen.

### 9.3 `trampoline_templates.py` -> `trampoline.py`

| Element | Status |
|---------|--------|
| `CLASS_NAME_SEPARATOR` | IDENTISCH |
| `create_trampoline_lookup` | IDENTISCH |
| `mangle_function_name` | AEQUIVALENT (ValueError statt assert) |
| `trampoline_impl` | IDENTISCH (nur Paket-Import angepasst) |

**Gesamtstatus: IDENTISCH** (minimale Verbesserungen)

### 9.4 `code_coverage.py` -> `code_coverage.py`

| Funktion | Status |
|----------|--------|
| `gather_coverage` | IDENTISCH (1:1 Kopie) |
| `get_covered_lines_for_file` | IDENTISCH |
| `_unload_modules_not_in` | IDENTISCH |

**Gesamtstatus: IDENTISCH**

**ACHTUNG:** `gather_coverage` ruft `runner.prepare_main_test_run()` und `runner.run_tests()` auf — diese Methoden existieren in mutmut-win's `PytestRunner` NICHT. Die Coverage-Funktion ist zwar identisch portiert, aber ohne die entsprechenden Runner-Methoden nicht aufrufbar. Der Orchestrator umgeht dies durch `_gather_coverage()`, die eine eigene Implementierung hat.

### 9.5 `type_checking.py` -> `type_checking.py`

| Funktion | Status |
|----------|--------|
| `TypeCheckingError` | IDENTISCH |
| `run_type_checker` | IDENTISCH |
| `parse_pyright_report` | IDENTISCH |
| `parse_pyrefly_report` | IDENTISCH |
| `parse_mypy_report` | IDENTISCH |
| `parse_ty_report` | IDENTISCH |

**Gesamtstatus: IDENTISCH**

---

## 10. Fehlende Klassen/Funktionen

Die folgenden Elemente aus dem Original existieren in mutmut-win NICHT:

| Element | Beschreibung | Auswirkung |
|---------|-------------|------------|
| `HammettRunner` | Alternativer Test-Runner fuer hammett | Gering — kaum genutzt |
| `CatchOutput` | Stdout/Stderr-Umleitung mit Spinner | UX — keine Spinner in mutmut-win |
| `TestRunner` (ABC) | Abstrakte Basisklasse fuer Runner | Gering — nur PytestRunner verwendet |
| `change_cwd` | Context-Manager fuer CWD-Wechsel | In mutmut-win durch `os.chdir()` mit finally ersetzt |
| `status_printer` / `print_status` | Spinner/Fortschrittsanzeige | UX — fehlt in mutmut-win |
| `collect_stat` / `Stat` / `calculate_summary_stats` | Stats-Aggregation pro Datei | Ersetzt durch `MutationRunResult` |
| `collected_test_names` | Sammelt alle bekannten Test-IDs | In `ListAllTestsResult.new_tests()` integriert |
| `save_stats` / `load_stats` (Original-Version) | JSON-basierte Stats-Persistenz | Ersetzt durch `MutmutStats`-basierte Version |
| `run_stats_collection` | Stats-Sammlung orchestrieren | Ersetzt durch `_run_stats_collection` |
| `FileMutationResult` | Dataclass fuer Mutations-Ergebnisse | Ersetzt durch `tuple[list[str], list[WarningMessage]]` |
| `MutantGenerationStats` | Zaehler fuer mutated/ignored/unmodified | Nicht portiert |

---

## 11. Neue Elemente in mutmut-win (ohne Gegenstueck im Original)

| Element | Datei | Beschreibung |
|---------|-------|-------------|
| `SpawnPoolExecutor` | `process/executor.py` | Multiprocessing-Pool mit spawn-Kontext |
| `worker_main` | `process/worker.py` | Worker-Hauptschleife |
| `WallClockTimeout` | `process/timeout.py` | Wall-Clock-basiertes Timeout |
| `MutationTask` | `models.py` | Pydantic-Model fuer Worker-Tasks |
| `TaskStarted/TaskCompleted/TaskTimedOut` | `models.py` | Event-Modelle fuer Worker-Kommunikation |
| `MutationRunResult` | `models.py` | Pydantic-Model fuer Gesamtergebnis |
| `MutationResult` | `models.py` | Pydantic-Model fuer Einzel-Ergebnis |
| `db.py` | `db.py` | SQLite-Persistenz-Layer |
| `constants.py` | `constants.py` | Extrahierte Exit-Code-Mappings |
| `exceptions.py` | `exceptions.py` | Exception-Hierarchie |
| `_state.py` | `_state.py` | Globaler Zustand (extrahiert aus __init__.py) |
| `test_mapping.py` | `test_mapping.py` | Test-Mapping-Funktionen (extrahiert) |
| `type_checker_filter.py` | `type_checker_filter.py` | Type-Checker-Filter (extrahiert) |
| `mutant_diff.py` | `mutant_diff.py` | Diff-Funktionen (extrahiert) |
| `browser.py` | `browser.py` | TUI-Browser (extrahiert) |

---

## Findings — Kritische Abweichungen

### F1: `also_copy` Defaults fehlen (HOCH)
**Datei:** `config.py` / `MutmutConfig`  
**Problem:** Im Original werden `tests/`, `test/`, `setup.cfg`, `pyproject.toml`, `pytest.ini`, `.gitignore` und `test*.py` IMMER in `also_copy` aufgenommen. In mutmut-win ist `also_copy` standardmaessig leer.  
**Auswirkung:** Ohne explizite Konfiguration werden Test-Dateien und Konfigurationsdateien nicht in den mutants/-Ordner kopiert. pytest kann dann im mutants/-Kontext keine Tests finden.

### F2: Mutant-Name-Filterung nicht implementiert (MITTEL)
**Datei:** `cli.py` / `run()`  
**Problem:** Der `mutant_names`-Parameter wird akzeptiert, aber ignoriert. Alle Mutanten werden getestet.  
**Auswirkung:** Re-Test einzelner Mutanten ueber CLI nicht moeglich. Der `browse`-Command nutzt Subprocess-Relaunches fuer Retests — diese funktionieren nicht korrekt.

### F3: Type-Checker-Filter zu grob (MITTEL)
**Datei:** `orchestrator.py` / `_filter_with_type_checker()`  
**Problem:** Nutzt Modul-Prefix-Matching statt CST-basiertem Line-Number-Matching.  
**Auswirkung:** Kann ALLE Mutanten eines Moduls als "caught by type check" markieren, obwohl nur eine Funktion betroffen ist. Fuehrt zu ueberschaetztem Score.

### F4: `max_stack_depth` nicht implementiert (NIEDRIG)
**Datei:** `__main__.py` / `record_trampoline_hit()`  
**Problem:** Keine Frame-Traversal-Logik fuer Stack-Tiefe-Begrenzung.  
**Auswirkung:** Nur relevant bei expliziter `max_stack_depth`-Konfiguration (Default = -1 = unbegrenzt).

### F5: setup.cfg nicht unterstuetzt (NIEDRIG)
**Datei:** `config.py` / `load_config()`  
**Problem:** Nur pyproject.toml wird gelesen.  
**Auswirkung:** Projekte die mutmut ueber setup.cfg konfigurieren, muessen migrieren.

### F6: Keine parallele Mutant-Generierung (NIEDRIG)
**Datei:** `orchestrator.py` / `_generate_mutants()`  
**Problem:** Sequentielle Schleife statt `Pool.imap_unordered`.  
**Auswirkung:** Langsamere Generierung bei grossen Projekte, aber korrekte Ergebnisse.

### F7: Keine Sortierung nach geschaetzter Laufzeit (NIEDRIG)
**Datei:** `orchestrator.py`  
**Problem:** Tasks werden nicht nach estimated_worst_case_time sortiert.  
**Auswirkung:** Suboptimale Worker-Auslastung, aber korrekte Ergebnisse.

### F8: `@click.version_option()` fehlt (NIEDRIG)
**Datei:** `cli.py`  
**Problem:** `mutmut-win --version` funktioniert nicht.

### F9: `code_coverage.gather_coverage` inkompatibel (NIEDRIG)
**Datei:** `code_coverage.py`  
**Problem:** Ruft `runner.prepare_main_test_run()` und `runner.run_tests()` auf, die in mutmut-win's PytestRunner nicht existieren.  
**Auswirkung:** Coverage-Gathering funktioniert nur ueber den Orchestrator-Umweg, nicht direkt.

---

## Zusammenfassung

### Quantitative Bewertung

| Kategorie | Anzahl | Prozent |
|-----------|--------|---------|
| IDENTISCH | ~55 Funktionen/Klassen | ~55% |
| AEQUIVALENT | ~30 Funktionen/Klassen | ~30% |
| ABWEICHUNG | ~10 Stellen | ~10% |
| FEHLT | ~11 Elemente | ~5% (davon die meisten irrelevant) |

### Gesamtbewertung

**Mutations-Engine (mutation.py, node_mutation.py):** 100% identisch — der Kern der Mutations-Logik ist 1:1 uebernommen.

**Trampoline (trampoline.py):** 99% identisch — nur Import-Pfade angepasst, `max_stack_depth` fehlt.

**Type-Checking (type_checking.py):** 100% identisch.

**Code-Coverage (code_coverage.py):** 100% identisch (aber Runner-Inkompatibilitaet).

**Orchestrierung:** ~80% aequivalent — grundlegend anderes Prozessmodell (spawn statt fork), aber funktional vergleichbar. Hauptdefizite: fehlende Mutant-Filterung, grobe Type-Checker-Heuristik, fehlende also_copy-Defaults.

**CLI:** ~85% aequivalent — alle Commands vorhanden, teilweise verbessert (Score-Berechnung, SQLite), teilweise unvollstaendig (Mutant-Filterung).

**Gesamtkompatibilitaet:** ~85% — Die Kern-Mutations-Logik ist identisch, die Orchestrierung und CLI haben einige Luecken die bei bestimmten Konfigurationen zu unterschiedlichem Verhalten fuehren koennen.
