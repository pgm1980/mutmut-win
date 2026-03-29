# mutmut-win — Brainstorming & Design Specification

**Datum**: 2026-03-29
**Status**: Approved (Brainstorming Phase)
**Basis**: mutmut 3.5.0 (https://github.com/boxed/mutmut)
**Referenz-Issue**: https://github.com/boxed/mutmut/issues/397
**Referenz-PR**: https://github.com/boxed/mutmut/pull/404

---

## 1. Projektziel

Eigenständiger Fork von mutmut 3.5.0 als separates Package **mutmut-win**, das Mutation Testing
**nativ unter Windows** ermöglicht. mutmut selbst bleibt für Unix/Linux zuständig —
mutmut-win deckt ausschließlich Windows ab.

### Scope

- **Vollständiger Port** aller mutmut 3.5.0 Features: Mutation Engine, TUI-Browser, Type-Checker-Integration, Coverage-Support, Config
- **Clean-Room Rewrite** der Prozess-Steuerung und Modulstruktur
- **Mutation Engine** (CST-basiert) wird 1:1 aus mutmut übernommen — plattformunabhängig

### Nicht im Scope

- Unix/Linux/macOS-Unterstützung (dafür gibt es mutmut)
- Neue Mutations-Operatoren über mutmut 3.5.0 hinaus
- Upstream-PR an boxed/mutmut

---

## 2. Problemanalyse

mutmut 3.5.0 nutzt folgende Unix-only APIs:

| API | Verwendung | Windows-Problem |
|---|---|---|
| `os.fork()` | Kindprozess pro Mutant | Existiert nicht auf Windows |
| `os.wait()` / `os.waitstatus_to_exitcode()` | Ergebnis-Einsammlung | Existiert nicht auf Windows |
| `resource.setrlimit(RLIMIT_CPU)` | CPU-Zeit-Timeout | `resource`-Modul existiert nicht auf Windows |
| `signal.SIGXCPU` | Timeout-Signal | Existiert nicht auf Windows |
| `gc.freeze()` | COW-Optimierung für fork | Irrelevant bei spawn |
| `open()` ohne `encoding=` | Datei-I/O | Windows nutzt CP1252 statt UTF-8 |

Zusätzlich: Zeile 8-10 in `__main__.py` blockiert Windows explizit mit `sys.exit(1)`.

---

## 3. Architektur-Entscheidungen

### 3.1 Prozess-Strategie: spawn + Worker-Pool

**Entscheidung**: `multiprocessing.set_start_method('spawn')` mit einem Worker-Pool.

**Begründung**: `fork()` existiert nicht auf Windows. `spawn` startet einen frischen Python-Interpreter
pro Worker. Um den Overhead zu minimieren, werden N Worker-Prozesse erstellt die pytest einmal
initialisieren und dann Tasks aus einer Queue holen.

**Worker-Lifecycle**:
1. Init: Config empfangen, pytest importieren, Test-Collection cachen
2. Loop: Task aus Queue → MUTANT_UNDER_TEST setzen → Tests ausführen → Ergebnis zurück → Repeat
3. Shutdown: Queue leer → sauberer Exit, oder: vom Timeout-Monitor gekillt

### 3.2 Timeout-Strategie: Wall-Clock-Timeout

**Entscheidung**: Monitor-Thread im Hauptprozess prüft Wall-Clock-Deadlines.

**Begründung**: `resource.RLIMIT_CPU` existiert nicht auf Windows. Wall-Clock-Timeout ist die
einzige plattformübergreifende Alternative. Der Timeout-Monitor läuft als Thread im Hauptprozess
und killt Worker-Prozesse bei Deadline-Überschreitung.

**Timeout-Berechnung**:
```
timeout = max(30, (estimated_time + 5) * timeout_multiplier)
```
- `estimated_time`: Summe der geschätzten Test-Dauern (aus Stats-Phase)
- `timeout_multiplier`: Konfigurierbar via `[tool.mutmut]`, Default 10 (großzügig wegen Wall-Clock statt CPU-Zeit)
- Minimum: 30 Sekunden

### 3.3 Kommunikation: Zwei-Queue-Architektur

```
Hauptprozess                    Worker-Prozesse (N Stück)
     │                                │
     ├── task_queue ──────────────────►│  Queue[MutationTask]
     │                                │
     │◄──────────────── event_queue ──┤  Queue[TaskStarted | TaskCompleted]
     │                                │
     │◄── TaskTimedOut (Monitor) ─────┘  (vom Timeout-Monitor injiziert)
```

Alle Daten über Queues sind pickle-bar (primitive Typen + Pydantic Models).

### 3.4 Clean-Room Rewrite

**Entscheidung**: Die 1700-Zeilen `__main__.py` wird in fokussierte Module aufgeteilt.

**Begründung**: Bessere Testbarkeit, Wartbarkeit und Verständlichkeit. Der eigenständige Fork
erlaubt maximale Freiheit beim Refactoring.

---

## 4. Modulstruktur

```
src/mutmut_win/
  __init__.py                  # Package Root, Version
  py.typed                     # PEP 561 Marker

  # Domain
  config.py                    # Config (Pydantic), config_reader, load_config
  models.py                    # SourceFileMutationData, MutantTask, MutationResult
  constants.py                 # status_by_exit_code, emoji_by_status (Windows-angepasst)

  # Mutation Engine (übernommen aus mutmut 3.5.0)
  mutation.py                  # mutate_file_contents, write_all_mutants_to_file
  node_mutation.py             # Node-Level CST-Mutationen
  trampoline.py                # Trampoline-Templates, mangle_function_name
  code_coverage.py             # Coverage-Sammlung
  type_checking.py             # Type-Checker-Integration

  # Prozess-Steuerung (NEU — Kern des Refactorings)
  process/
    __init__.py
    executor.py                # ProcessExecutor Protocol + SpawnPoolExecutor
    timeout.py                 # WallClockTimeout (Monitor-Thread)
    worker.py                  # Worker-Loop-Logik

  # Test Runner
  runner.py                    # TestRunner ABC, PytestRunner

  # Orchestrierung
  orchestrator.py              # MutationOrchestrator — Hauptablauf

  # CLI + UI
  cli.py                       # Click CLI (run, results, show, apply, browse)
  browser.py                   # TUI Result Browser (textual)
  result_browser_layout.tcss   # TUI Stylesheet
```

---

## 5. Datenfluss

### Phase 1: Vorbereitung (sequentiell, Hauptprozess)

```
Config laden → Mutants erzeugen → Clean Test → Stats sammeln → Forced Fail
```

### Phase 2: Mutation Testing (parallel, Pool)

```
Orchestrator
├── Erstellt MutationTask-Objekte
├── Füllt task_queue
├── Startet max_workers Worker-Prozesse (spawn)
├── Startet Timeout-Monitor-Thread
└── Event-Consumer-Loop:
     ├── TaskStarted  → registriert Timeout-Countdown
     ├── TaskCompleted → speichert Ergebnis, print_stats()
     └── TaskTimedOut  → speichert timeout, startet Ersatz-Worker
```

### Phase 3: Ergebnisse (sequentiell, Hauptprozess)

```
Stats drucken → Ergebnisse anzeigen → Optional: TUI Browser
```

### Datentypen über Queues

**task_queue** (Hauptprozess → Worker):
- `MutationTask(mutant_name: str, tests: list[str], estimated_time: float, timeout_seconds: float)`

**event_queue** (Worker → Hauptprozess):
- `TaskStarted(mutant_name: str, worker_pid: int, timestamp: datetime)`
- `TaskCompleted(mutant_name: str, worker_pid: int, exit_code: int, duration: float)`
- `TaskTimedOut(mutant_name: str, worker_pid: int)` — vom Timeout-Monitor

---

## 6. Error Handling

| Fall | Erkennung | Reaktion |
|---|---|---|
| Worker-Timeout | Timeout-Monitor (Wall-Clock) | `Process.kill()` → TaskTimedOut → Ersatz-Worker |
| Worker-Crash | `Process.is_alive()` → False | Task als "suspicious", Ersatz-Worker |
| Verlorener Task | Post-hoc: Mutant ohne Ergebnis | Als "suspicious" markieren |
| Ctrl+C | `KeyboardInterrupt` | Alle Worker killen, Teilergebnisse speichern |
| pytest-Init-Failure | Worker stirbt sofort | Max 3 Neustarts pro Slot, dann Abbruch |

### Exit-Code-Mapping (Windows)

Timeout-Erkennung läuft über das Event-System, nicht über Exit-Codes:

```
TaskCompleted + exit_code 0     → survived
TaskCompleted + exit_code 1,3   → killed
TaskCompleted + exit_code 5,33  → no tests
TaskCompleted + exit_code 2     → interrupted
TaskCompleted + exit_code 34    → skipped
TaskCompleted + exit_code 37    → caught by type check
TaskTimedOut (vom Monitor)      → timeout
Kein Event nach Pool-Shutdown   → suspicious
```

### Graceful Shutdown

```
KeyboardInterrupt
  → Orchestrator.shutdown()
    → Alle Worker: Process.kill()
    → Alle Worker: Process.join(timeout=5)
    → Queues schließen
    → Bisherige Ergebnisse speichern
    → "Stopping..." + Zusammenfassung
```

---

## 7. Testing-Strategie

### Verifizierte E2E-Tests aus mutmut

mutmut liefert 5 E2E-Testprojekte mit Snapshot-Ergebnissen (exakte Exit-Codes pro Mutant):

| Testprojekt | Mutanten | Was es testet |
|---|---|---|
| my_lib | ~65 | Kern-Mutationen, async, Klassen, Segfault, Signatures |
| config | ~12 | Config-Features, paths_to_mutate, do_not_mutate, also_copy |
| mutate_only_covered_lines | ~32 | Coverage-gesteuertes Mutieren |
| type_checking | ~11 | Type-Checker-Integration |
| py3_14_features | ~4 | Python 3.14 Features |

**Übernahme-Strategie**:
1. E2E-Projekte 1:1 übernehmen
2. Snapshot-Tests mit direkten Dict-Vergleichen (ohne inline_snapshot Dependency)
3. Segfault-Mutant (`ctypes.string_at(0)`) separat behandeln (Windows-Exit-Code abweichend)
4. Alle anderen Exit-Codes sind pytest-Codes → plattformunabhängig

### Test-Pyramide

- **Unit Tests (~70%)**: Isoliert, mocked, schnell — config, models, executor (Mock-Tasks), timeout, worker, orchestrator
- **Integration Tests (~20%)**: Echte Prozesse, kleines Testprojekt, @pytest.mark.slow + @pytest.mark.integration
- **E2E Tests (~10%)**: CLI-Befehle auf übernommenen Testprojekten, Snapshot-Vergleich

### hypothesis-Properties

- Config: Beliebige Werte → valid oder ValidationError
- MutationTask: pickle Roundtrip
- Exit-Code-Mapping: Alle int → immer ein Status-String
- Timeout-Berechnung: Positive estimated_time → timeout > estimated_time
- Name-Mangling: mangle → demangle Roundtrip

### Coverage & Mutation Testing

- Coverage-Ziel: >80% gesamt, >90% für process/ Package
- Meta-Test: mutmut-win auf eigenen Code anwenden

---

## 8. Herkunft der Module

| Modul | Herkunft | Änderungen |
|---|---|---|
| mutation.py | mutmut file_mutation.py | encoding='utf-8' |
| node_mutation.py | mutmut node_mutation.py | Keine |
| trampoline.py | mutmut trampoline_templates.py | Keine |
| code_coverage.py | mutmut code_coverage.py | encoding='utf-8' |
| type_checking.py | mutmut type_checking.py | Keine |
| browser.py | mutmut __main__.py (ResultBrowser) | Extrahiert, encoding='utf-8' |
| **config.py** | **Neu** | Pydantic Model statt Dataclass |
| **models.py** | **Neu** | SourceFileMutationData refactored |
| **constants.py** | **Neu** | Windows-angepasste Exit-Codes |
| **process/executor.py** | **Neu** | SpawnPoolExecutor |
| **process/timeout.py** | **Neu** | WallClockTimeout |
| **process/worker.py** | **Neu** | Worker-Loop-Logik |
| **orchestrator.py** | **Neu** | Extrahiert aus _run() |
| **runner.py** | **Neu** | PytestRunner refactored |
| **cli.py** | **Neu** | Click CLI extrahiert |

---

## 9. Dependencies

```toml
[project]
dependencies = [
    "click>=8.0.0",
    "coverage>=7.3.0",
    "libcst>=1.8.5",
    "pydantic>=2.0.0",
    "pytest>=6.2.5",
    "setproctitle>=1.1.0",
    "textual>=1.0.0",
]
```

---

## 10. Risiken & Mitigationen

| Risiko | Mitigation |
|---|---|
| Spawn-Performance langsamer als fork | Worker-Pool wiederverwendet pytest-Init |
| Ergebnis-Abweichungen vs. mutmut | E2E-Snapshot-Tests als Gold-Standard |
| Segfault-Mutant anders auf Windows | Separater erwarteter Wert oder Skip |
| Worker-State-Pollution zwischen Tasks | Trampoline-Mechanismus ist stateless (env-var) |
| Queue-Serialisierung | Nur primitive Typen + Pydantic Models |
| Endlosschleifen durch Mutationen | WallClockTimeout mit großzügigem Multiplikator |

---

## 11. CLI-Interface

```
mutmut-win run [--max-children N] [MUTANT_NAMES...]
mutmut-win results [--all]
mutmut-win show <MUTANT_NAME>
mutmut-win apply <MUTANT_NAME>
mutmut-win browse [--show-killed]
```

Config über `[tool.mutmut]` in pyproject.toml — kompatibel mit mutmut.
