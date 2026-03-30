# Software Design Specification — mutmut-win

**Version:** 0.1.0
**Datum:** 2026-03-29
**Status:** Approved
**Referenz:** [Architecture Specification](..%2Farchitecture%20spec%2Farchitecture_specification.md)
**Basis:** Brainstorming-Ergebnis: `_docs/specs/2026-03-29-mutmut-win-design.md`

---

## 1. Functional Requirements (FRs)

### FR-01: Mutation Testing Core

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-01.1 | Das System MUSS Mutanten für alle Python-Quelldateien in `paths_to_mutate` via CST (libcst) erzeugen | Must | v0.1 |
| FR-01.2 | Das System MUSS Mutationstests parallel mit konfigurierbarer Anzahl Worker-Prozesse ausführen (`max_workers`) | Must | v0.1 |
| FR-01.3 | Das System MUSS einen Wall-Clock-Timeout pro Mutationstest durchsetzen (`timeout_multiplier × estimated_time`) | Must | v0.1 |
| FR-01.4 | Das System MUSS die Ergebnisse survived, killed, timeout, no_tests, suspicious erkennen und persistieren | Must | v0.1 |
| FR-01.5 | Das System MUSS vor Mutationstests einen Clean-Test-Run durchführen (Test-Suite muss grün sein) | Must | v0.1 |
| FR-01.6 | Das System MUSS eine Stats-Phase durchführen um Test-Dauern für Timeout-Berechnung zu schätzen | Must | v0.1 |
| FR-01.7 | Das System MUSS Mutationsergebnisse in einer SQLite-Datenbank kompatibel mit mutmut 3.5.0 persistieren | Must | v0.1 |
| FR-01.8 | Das System SOLL nur Mutanten testen die noch kein Ergebnis haben (inkrementeller Modus) | Should | v0.1 |
| FR-01.9 | Das System SOLL das Filtern von Mutanten nach Name unterstützen (`mutmut-win run MUTANT_NAMES...`) | Should | v0.1 |
| FR-01.10 | Das System KANN Echtzeit-Fortschritt während des Mutation Testings anzeigen | Could | v0.2 |

### FR-02: Result Management

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-02.1 | Das System MUSS Mutationsergebnisse mit Anzahl pro Status ausgeben (`mutmut-win results`) | Must | v0.1 |
| FR-02.2 | Das System MUSS den Diff eines spezifischen Mutanten anzeigen (`mutmut-win show <NAME>`) | Must | v0.1 |
| FR-02.3 | Das System MUSS einen spezifischen Mutanten auf die Quelldatei anwenden (`mutmut-win apply <NAME>`) | Must | v0.1 |
| FR-02.4 | Das System MUSS alle Ergebnisse mit optionalem Filter ausgeben (`mutmut-win results [--all]`) | Must | v0.1 |
| FR-02.5 | Das System SOLL einen TUI-Browser für interaktive Ergebnisexploration bereitstellen (`mutmut-win browse`) | Should | v0.1 |

### FR-03: Konfiguration

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-03.1 | Das System MUSS Konfiguration aus `[tool.mutmut]` in `pyproject.toml` laden | Must | v0.1 |
| FR-03.2 | Das System MUSS sinnvolle Defaults verwenden wenn Konfiguration fehlt | Must | v0.1 |
| FR-03.3 | Das System MUSS Konfiguration beim Start validieren und bei Fehlern mit Fehlermeldung abbrechen (Fail-Fast) | Must | v0.1 |
| FR-03.4 | Das System MUSS `paths_to_mutate`, `do_not_mutate`, `also_copy`, `test_command` unterstützen | Must | v0.1 |
| FR-03.5 | Das System MUSS `max_workers` und `timeout_multiplier` als Windows-spezifische Erweiterungen unterstützen | Must | v0.1 |
| FR-03.6 | CLI-Flags SOLLEN `pyproject.toml`-Einstellungen überschreiben | Should | v0.1 |

### FR-04: Test-Integration

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-04.1 | Das System MUSS pytest als Test-Runner unterstützen | Must | v0.1 |
| FR-04.2 | Das System MUSS `MUTANT_UNDER_TEST`-Umgebungsvariable setzen wenn Tests für einen Mutanten laufen | Must | v0.1 |
| FR-04.3 | Das System MUSS den Trampoline-Mechanismus (mangle_function_name) unterstützen für parallele Ausführung | Must | v0.1 |
| FR-04.4 | Das System SOLL Coverage-gesteuertes Mutieren unterstützen (nur abgedeckte Zeilen mutieren) | Should | v0.1 |
| FR-04.5 | Das System SOLL Type-Checker-Integration unterstützen (Mutanten durch Type Checking abfangen) | Should | v0.1 |

### FR-05: Benutzerschnittstelle

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-05.1 | Das System MUSS Fortschritt und Ergebnisse in stdout ausgeben | Must | v0.1 |
| FR-05.2 | Das System MUSS `--help` auf allen Befehlen unterstützen | Must | v0.1 |
| FR-05.3 | Das System MUSS bei Ctrl+C "Stopping..." ausgeben und Teilergebnisse speichern | Must | v0.1 |
| FR-05.4 | Das System SOLL einen TUI-Browser (Textual-basiert) für interaktive Exploration bereitstellen | Should | v0.1 |

### FR-06: Windows-Kompatibilität

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-06.1 | Das System MUSS nativ auf Windows 10 und Windows 11 (64-bit) ohne WSL lauffähig sein | Must | v0.1 |
| FR-06.2 | Das System MUSS UTF-8-Encoding für alle Datei-I/O-Operationen verwenden | Must | v0.1 |
| FR-06.3 | Das System MUSS einen klaren `ImportError` auf Nicht-Windows-Plattformen ausgeben | Must | v0.1 |
| FR-06.4 | Das System MUSS `multiprocessing.set_start_method('spawn')` verwenden | Must | v0.1 |

---

## 2. Non-Functional Requirements (NFRs)

### NFR-01: Security

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-01.1 | Alle Konfigurationseingaben MÜSSEN via Pydantic validiert werden | 100% Input-Validierung |
| NFR-01.2 | Keine bekannten Vulnerabilities in Dependencies | pip-audit: 0 Findings vor Release |
| NFR-01.3 | Semgrep MUSS vor jedem Release bestehen | 0 offene Security-Findings |
| NFR-01.4 | Keine Pickle-Deserialisierung aus nicht-vertrauenswürdigen Quellen | Queue-Messages nur intern |
| NFR-01.5 | subprocess.run MUSS ohne `shell=True` aufgerufen werden | Semgrep S603 |

### NFR-02: Performance

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-02.1 | Mutation Testing SOLL N=max_workers Mutationen parallel ausführen | Benchmark-verifiziert |
| NFR-02.2 | Stats-Phase SOLL in < 30 Sekunden abgeschlossen sein (für typische Projekte) | Benchmark-verifiziert |
| NFR-02.3 | Speicherverbrauch pro Worker SOLL < 512 MB sein | Profiler-verifiziert |
| NFR-02.4 | Worker-Startup-Overhead SOLL nicht den Gesamtlauf dominieren | Pool-Lifecycle: spawn-once |

### NFR-03: Zuverlässigkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-03.1 | Ein Worker-Crash DARF den Gesamtlauf NICHT stoppen (Ersatz-Worker + suspicious-Markierung) | Graceful Degradation |
| NFR-03.2 | Ctrl+C MUSS Graceful Shutdown auslösen (Teilergebnisse speichern, Worker killen) | Functional Test |
| NFR-03.3 | Timeout-getötete Worker MÜSSEN durch Ersatz-Worker ersetzt werden | Functional Test |
| NFR-03.4 | Teilergebnisse MÜSSEN bei Unterbrechung gespeichert werden | Functional Test |
| NFR-03.5 | pytest-Init-Failure: max. 3 Neustarts pro Worker-Slot, dann Abbruch mit Fehlermeldung | Integration Test |

### NFR-04: Testbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-04.1 | Unit Tests MÜSSEN TDD-konform geschrieben werden | Red → Green → Refactor |
| NFR-04.2 | Code Coverage MUSS gemessen werden | ≥80% gesamt, ≥90% process/ |
| NFR-04.3 | Mutation Testing MUSS auf eigenen Code angewendet werden | mutmut-win auf mutmut-win |
| NFR-04.4 | Architekturregeln MÜSSEN als ausführbare Tests existieren | 0 import-linter-Verletzungen |
| NFR-04.5 | Property-Based Tests MÜSSEN für alle kritischen Roundtrips/Invarianten existieren | hypothesis |
| NFR-04.6 | E2E-Snapshot-Tests MÜSSEN für alle 5 mutmut-Testprojekte bestehen | 0 Divergenzen vs. mutmut |

**hypothesis Properties (Pflicht):**

| Property | Invariante |
|----------|------------|
| Config-Roundtrip | Beliebige gültige Werte → valid (nie unbehandelte Exception) |
| Config-Validation | Ungültige Werte (max_workers=0, timeout_multiplier=0.5) → ValidationError |
| MutationTask-Pickle | serialize(task) → deserialize → task (Roundtrip) |
| Exit-Code-Mapping | Jeder int → immer ein Status-String (nie KeyError) |
| Timeout-Formel | estimated_time > 0 → timeout > estimated_time (immer größer) |
| Name-Mangling | mangle(name) → demangle(mangle(name)) == name (Roundtrip) |

### NFR-05: Wartbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-05.1 | Code MUSS alle Ruff-Prüfungen bestehen | 0 Findings |
| NFR-05.2 | Type Checking MUSS im strikten mypy-Modus bestehen | 0 Errors |
| NFR-05.3 | Module/Klassen SOLLEN < 300 Zeilen sein | Ausnahmen dokumentiert |
| NFR-05.4 | Funktionen/Methoden SOLLEN < 30 Zeilen sein | Ausnahmen dokumentiert |
| NFR-05.5 | Zirkuläre Abhängigkeiten DÜRFEN NICHT existieren | import-linter: 0 Verletzungen |
| NFR-05.6 | Alle öffentlichen APIs MÜSSEN Google-Style Docstrings haben | 100% Abdeckung |

### NFR-06: Kompatibilität

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-06.1 | Das System MUSS auf Windows 10/11 (64-bit) mit Python ≥3.11 laufen | CI auf windows-latest |
| NFR-06.2 | Konfigurationsformat MUSS mit mutmut `[tool.mutmut]` kompatibel sein | Gleiche Key-Namen |
| NFR-06.3 | Ergebnis-Datenbankformat MUSS mit mutmut 3.5.0 SQLite-Schema kompatibel sein | E2E-Tests |

### NFR-07: Konfigurierbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-07.1 | Alle Limits MÜSSEN konfigurierbar sein mit sinnvollen Defaults | Kein Hardcoded Limit |
| NFR-07.2 | Konfigurationsfehler MÜSSEN beim Start erkannt werden (Fail-Fast) | Pydantic ValidationError → sys.exit |

---

## 3. Interface-Spezifikationen

### 3.1 CLI-Interface (Click)

**Typ:** Click CLI via `mutmut-win` Entry Point
**Verantwortung:** Benutzerschnittstelle, Argument-Parsing, Routing an Orchestrator

```
mutmut-win run [OPTIONS] [MUTANT_NAMES]...
  --max-workers INTEGER       Anzahl paralleler Worker (default: cpu_count // 2)
  --timeout-multiplier FLOAT  Timeout-Multiplikator (default: 10.0)
  MUTANT_NAMES                Optionale Liste spezifischer Mutanten
  Returns: exit 0 (killed), exit 1 (survived), exit 2 (error)

mutmut-win results [OPTIONS]
  --all / --no-all            Alle Status anzeigen inkl. killed (default: False)
  Returns: Tabelle aller Mutationsergebnisse

mutmut-win show MUTANT_NAME
  MUTANT_NAME                 Name des Mutanten (z.B. "my_lib__init__1")
  Returns: Diff der Mutation
  Errors: Exit 2 wenn Mutant nicht gefunden

mutmut-win apply MUTANT_NAME
  MUTANT_NAME                 Name des Mutanten
  Returns: Modifizierte Quelldatei auf Disk
  Errors: Exit 2 wenn Mutant nicht gefunden

mutmut-win browse [OPTIONS]
  --show-killed / --no-show-killed  Getötete Mutanten anzeigen (default: False)
  Returns: Startet Textual TUI
```

### 3.2 MutationOrchestrator

**Typ:** Python-Klasse (Application Layer)
**Verantwortung:** Koordination der drei Phasen (Vorbereitung, Mutation Testing, Ergebnisse)

```
class MutationOrchestrator:

  __init__(config: MutmutWinConfig) -> None
    Parameter: config — Geladene und validierte Konfiguration

  run(mutant_filter: list[str] | None = None) -> int
    Parameter: mutant_filter — Optionale Liste von Mutanten-Namen
    Returns: Exit-Code (0 = some killed, 1 = all survived, 2 = error)
    Raises: PrepPhaseError bei Clean-Test-Failure oder NoSourceFilesError

  shutdown() -> None
    Zweck: Graceful Shutdown — Worker killen, Ergebnisse speichern
    Seiteneffekt: Schreibt Teilergebnisse in DB
```

### 3.3 SpawnPoolExecutor

**Typ:** Python-Klasse (Process Management Layer)
**Verantwortung:** Worker-Pool-Lifecycle, Task-Queue-Management

```
class SpawnPoolExecutor:

  __init__(config: MutmutWinConfig,
           task_queue: Queue[MutationTask | None],
           event_queue: Queue[TaskStarted | TaskCompleted | TaskTimedOut]) -> None

  start(worker_count: int) -> None
    Zweck: max_workers Worker-Prozesse via multiprocessing spawn starten

  submit(task: MutationTask) -> None
    Zweck: Task in task_queue einreihen
    Raises: QueueFullError bei vollem Puffer (theoretisch)

  shutdown(wait: bool = True, timeout: float = 5.0) -> None
    Zweck: Sentinel-Werte senden, Worker joinen, Stragglers killen

  replace_worker(pid: int) -> None
    Zweck: Toten/getimeouten Worker durch neuen ersetzen

  active_worker_count: int  (Property)
```

### 3.4 WallClockTimeoutMonitor

**Typ:** Python-Klasse (Process Management Layer)
**Verantwortung:** Deadline-Überwachung, Worker-Kill bei Timeout

```
class WallClockTimeoutMonitor:

  __init__(event_queue: Queue[TaskTimedOut],
           executor: SpawnPoolExecutor,
           poll_interval: float = 0.5) -> None

  start() -> None
    Zweck: Monitor-Thread starten

  register(mutant_name: str, worker_pid: int, deadline: datetime) -> None
    Zweck: Neuen aktiven Task mit Deadline registrieren
    Thread-sicher: Ja (threading.Lock intern)

  complete(mutant_name: str) -> None
    Zweck: Task als abgeschlossen markieren (Timeout abbrechen)
    Thread-sicher: Ja

  stop() -> None
    Zweck: Monitor-Thread sauber beenden
```

### 3.5 PytestRunner

**Typ:** Python-Klasse (Infrastructure Layer)
**Verantwortung:** pytest-Ausführung kapseln (Clean Run, Stats Run, Mutation Run)

```
class PytestRunner:

  __init__(config: MutmutWinConfig) -> None

  run_clean() -> int
    Zweck: Test-Suite auf Original-Code ausführen
    Returns: pytest Exit-Code (0 = alle Tests grün)

  run_stats() -> dict[str, float]
    Zweck: Test-Dauern auf Original-Code messen
    Returns: {test_id: duration_seconds}

  run_for_mutant(mutant_name: str, tests: list[str]) -> tuple[int, float]
    Zweck: Tests für spezifischen Mutanten ausführen (via subprocess.run)
    Parameter: mutant_name — wird als MUTANT_UNDER_TEST env var gesetzt
    Returns: (exit_code, duration_seconds)
    Seiteneffekt: Keine Datei-I/O (Trampoline-Datei bereits geschrieben)
```

---

## 4. Datenmodelle

### 4.1 MutmutWinConfig (config.py)

| Feld | Typ | Default | Validierung |
|------|-----|---------|-------------|
| paths_to_mutate | list[str] | ["src/"] | min_length=1 |
| do_not_mutate | list[str] | [] | — |
| also_copy | list[str] | [] | — |
| test_command | str | "python -m pytest" | min_length=1 |
| runner | Literal["pytest"] | "pytest" | — |
| max_workers | int | cpu_count() ÷ 2, min 1 | ge=1 |
| timeout_multiplier | float | 10.0 | ge=1.0 |
| use_coverage | bool | False | — |
| pre_mutation_coverage | bool | False | — |
| coverage_data_file | str \| None | None | — |
| tests_dir | str | "tests" | — |

### 4.2 MutationTask (models.py)

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| mutant_name | str | Eindeutiger Mutanten-Name z.B. "my_lib__init__1" | min_length=1 |
| tests | list[str] | pytest Test-IDs für diesen Mutanten | min_length=1 |
| estimated_time | float | Geschätzte Testlaufzeit in Sekunden | ge=0.0 |
| timeout_seconds | float | Berechneter Timeout in Sekunden | ge=30.0 |

### 4.3 TaskStarted (models.py)

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| mutant_name | str | Mutanten-Name | min_length=1 |
| worker_pid | int | PID des Worker-Prozesses | ge=1 |
| timestamp | datetime | Start-Zeitstempel (UTC) | — |

### 4.4 TaskCompleted (models.py)

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| mutant_name | str | Mutanten-Name | min_length=1 |
| worker_pid | int | PID des Worker-Prozesses | ge=1 |
| exit_code | int | pytest Exit-Code | — |
| duration | float | Laufzeit in Sekunden | ge=0.0 |

### 4.5 TaskTimedOut (models.py)

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| mutant_name | str | Mutanten-Name | min_length=1 |
| worker_pid | int | PID des getimeouten Workers | ge=1 |

### 4.6 MutationStatus (constants.py)

```python
class MutationStatus(str, Enum):
    SURVIVED = "survived"
    KILLED = "killed"
    TIMEOUT = "timeout"
    NO_TESTS = "no_tests"
    SUSPICIOUS = "suspicious"
    SKIPPED = "skipped"
    CAUGHT_BY_TYPE_CHECK = "caught_by_type_check"
```

**Exit-Code-Mapping:**

| TaskCompleted exit_code | MutationStatus |
|------------------------|----------------|
| 0 | SURVIVED |
| 1, 3 | KILLED |
| 5, 33 | NO_TESTS |
| 2 | KILLED (interrupted → test found error) |
| 34 | SKIPPED |
| 37 | CAUGHT_BY_TYPE_CHECK |
| TaskTimedOut-Event | TIMEOUT |
| Kein Event nach Pool-Shutdown | SUSPICIOUS |

---

## 5. Datenflüsse

### 5.1 Hauptfluss: mutmut-win run

```
Phase 1: Vorbereitung (sequentiell, Hauptprozess)

1.  CLI parst Argumente → pyproject.toml laden → MutmutWinConfig via Pydantic validieren
    Fehler: ConfigValidationError → sys.exit(2) mit Fehlermeldung

2.  MutationOrchestrator.run() startet

3.  Clean Test Run:
    PytestRunner.run_clean() → subprocess.run(['python', '-m', 'pytest'])
    exit_code != 0 → CleanTestFailureError → sys.exit(2) mit Hinweis

4.  Mutanten erzeugen:
    Für jede Datei in paths_to_mutate:
      mutation.mutate_file_contents(source, encoding='utf-8')
      write_all_mutants_to_file() → Trampoline-Datei schreiben
    Trampoline-Datei enthält ALLE Mutanten als mangle-Funktionen
    MUTANT_UNDER_TEST-Env-Var selektiert welcher Mutant aktiv ist

5.  Stats Run:
    PytestRunner.run_stats() → subprocess.run mit --collect-only + timing
    Ergebnis: {test_id: duration_seconds}

6.  Forced Fail Test:
    subprocess.run mit MUTANT_UNDER_TEST=<dummy> um Trampoline zu verifizieren
    Muss fehlschlagen → Mechanismus bestätigt

Phase 2: Mutation Testing (parallel)

7.  MutationTask-Objekte erstellen:
    Für jeden Mutanten: timeout = max(30, (estimated_time + 5) * timeout_multiplier)

8.  SpawnPoolExecutor starten:
    max_workers Worker-Prozesse via multiprocessing.Process(target=worker_loop) spawnen
    task_queue und event_queue übergeben

9.  WallClockTimeoutMonitor.start() → Monitor-Thread läuft

10. task_queue mit allen MutationTasks füllen

11. Event-Consumer-Loop (Hauptprozess, blockierend):

    event = event_queue.get()

    TaskStarted:
      monitor.register(mutant_name, worker_pid, now + timeout)

    TaskCompleted:
      monitor.complete(mutant_name)
      status = exit_code_to_status(exit_code)
      db.save_result(mutant_name, status, exit_code, duration)
      print_progress()

    TaskTimedOut:
      executor.replace_worker(worker_pid)
      db.save_result(mutant_name, TIMEOUT, None, None)
      print_progress()

    Loop endet wenn alle Tasks abgearbeitet

12. Graceful Shutdown:
    N × sentinel (None) in task_queue
    Workers empfangen sentinel → Exit
    executor.shutdown(wait=True, timeout=5)
    monitor.stop()

Phase 3: Ergebnisse

13. Zusammenfassung drucken: survived/killed/timeout/suspicious Zähler
14. Return exit_code: 0 (any killed), 1 (all survived), 2 (error)
```

### 5.2 Worker-Prozess-Lifecycle

```
Worker Startup (spawn):
1. multiprocessing.set_start_method('spawn') bereits gesetzt
2. worker_loop(task_queue, event_queue, config) startet
3. Logging initialisieren
4. In Task-Loop eintreten

Per-Task-Ausführung:
5.  task = task_queue.get()  → blockiert bis Task verfügbar
    task == None → Sentinel: sauber beenden

6.  event_queue.put(TaskStarted(task.mutant_name, os.getpid(), datetime.now(UTC)))

7.  env = os.environ.copy()
    env['MUTANT_UNDER_TEST'] = task.mutant_name

8.  start_time = time.monotonic()
    result = subprocess.run(
        ['python', '-m', 'pytest'] + task.tests,
        env=env,
        timeout=task.timeout_seconds + 5,  # Sicherheitspuffer
        capture_output=True
    )
    duration = time.monotonic() - start_time

9.  event_queue.put(TaskCompleted(
        task.mutant_name, os.getpid(), result.returncode, duration
    ))

10. Loop zu Schritt 5

Worker Shutdown:
11. Empfange Sentinel → return
    ODER: Process.kill() durch Timeout-Monitor → harter Abbruch
```

### 5.3 Fehlerfall: Worker-Crash während Task-Ausführung

```
1.  Worker-Prozess stirbt unerwartet (kein Sentinel empfangen)
2.  Kein TaskCompleted-Event in event_queue
3.  Timeout-Monitor erkennt nach Deadline: Process.is_alive() == False
4.  Timeout-Monitor injiziert TaskTimedOut für hängenden Task
5.  Orchestrator verarbeitet TaskTimedOut → Status = SUSPICIOUS
    (nicht TIMEOUT, da Crash ≠ echtes Timeout)
    HINWEIS: Unterscheidung TIMEOUT vs. SUSPICIOUS über Event-Typ:
    - TaskTimedOut nach Deadline → TIMEOUT
    - Kein Event nach Pool-Shutdown → SUSPICIOUS
6.  executor.replace_worker(crashed_pid) → neuer Worker gestartet
7.  Lauf setzt fort
```

---

## 6. Fehlerbehandlung

### 6.1 Fehler-Kategorien

| Kategorie | Basis-Typ | Exit-Code | Behandlung |
|-----------|-----------|-----------|------------|
| Konfigurationsfehler | MutmutWinConfigError | 2 | Sofort sys.exit(2), Fehlermeldung |
| Clean-Test-Failure | PrepPhaseError | 2 | sys.exit(2), Hinweis auf Testfehler |
| Keine Quelldateien | PrepPhaseError | 2 | sys.exit(2), Hinweis auf paths_to_mutate |
| Worker-Crash | (intern) | — | SUSPICIOUS, Ersatz-Worker |
| Worker-Timeout | (intern) | — | TIMEOUT, Worker killen, Ersatz-Worker |
| Pool-Erschöpft | WorkerPoolError | 2 | sys.exit(2) nach 3 Neustarts pro Slot |
| KeyboardInterrupt | (Standard) | 130 | Graceful Shutdown, Teilergebnisse speichern |
| Unerwartete Fehler | MutmutWinError | 2 | Log ERROR + sys.exit(2) |

### 6.2 Custom Exceptions

```
MutmutWinError(Exception)               # Basis für alle mutmut-win-Ausnahmen
├── MutmutWinConfigError                  # Konfigurationsfehler
│   ├── ConfigNotFoundError               # Kein pyproject.toml gefunden
│   └── ConfigValidationError             # Pydantic ValidationError (wrapper)
├── PrepPhaseError                        # Fehler in Phase 1
│   ├── CleanTestFailureError             # Test-Suite nicht grün
│   ├── NoSourceFilesError                # Keine .py-Dateien in paths_to_mutate
│   └── ForcedFailError                   # Trampoline-Mechanismus funktioniert nicht
└── WorkerPoolError
    └── PoolExhaustedError                # Alle Worker-Slots nach 3 Retries erschöpft
```

---

## 7. Sicherheitskonzept

| Maßnahme | Beschreibung | Verifizierung |
|----------|-------------|---------------|
| Input-Validierung | Alle Konfigurationseingaben via Pydantic v2 validiert | Unit Tests + Pydantic |
| Filesystem-Scope | Dateioperationen nur in configured paths_to_mutate | Code Review + Semgrep |
| Subprocess ohne Shell | subprocess.run mit shell=False (S603) | Semgrep S603 |
| Pickle-Sicherheit | Queue-Messages sind ausschließlich intern erzeugte Pydantic-Models | Code Review |
| Dependency Audit | pip-audit vor jedem Release (CI) | CI-Pipeline |
| Static Analysis | Semgrep --config auto vor jedem Release | CI-Pipeline |
| Keine Netzwerkzugriffe | mutmut-win greift auf keine externen APIs zu | Code Review |

---

## 8. Deployment & Operations

### 8.1 Build-Artefakte

| Artefakt | Format | Ziel |
|----------|--------|------|
| Python Wheel | `mutmut_win-*.whl` | PyPI Distribution |
| Source Distribution | `mutmut_win-*.tar.gz` | PyPI Source |

### 8.2 Konfigurationsparameter

| Parameter | Default | Beschreibung | Typ |
|-----------|---------|-------------|-----|
| paths_to_mutate | ["src/"] | Verzeichnisse/Dateien die mutiert werden sollen | list[str] |
| do_not_mutate | [] | Muster für Dateien die nicht mutiert werden | list[str] |
| also_copy | [] | Zusätzliche Dateien die in Temp-Dir kopiert werden | list[str] |
| test_command | "python -m pytest" | Basisbefehl für Test-Ausführung | str |
| runner | "pytest" | Test-Runner (aktuell nur pytest) | str |
| max_workers | cpu_count()//2 | Anzahl paralleler Worker-Prozesse | int |
| timeout_multiplier | 10.0 | Timeout = max(30, (est+5) * multiplier) | float |
| use_coverage | False | Coverage-gesteuerte Mutation aktivieren | bool |
| pre_mutation_coverage | False | Coverage vor Mutation sammeln | bool |
| coverage_data_file | None | Pfad zur Coverage-Datei | str \| None |
| tests_dir | "tests" | Test-Verzeichnis für Discovery | str |

### 8.3 Trampoline-Mechanismus (Kernkonzept)

Das Trampoline-Muster ist der Schlüssel für paralleles Mutation Testing ohne Dateikonflikt:

```
Original Source (my_lib/__init__.py):
  def foo(x):
      return x + 1

Trampoline-Datei (einmalig in Phase 1 geschrieben, shared von allen Workern):
  def x_foo_1(x):       # Mutant 1: + → -
      return x - 1
  def x_foo_2(x):       # Mutant 2: return 0
      return 0

  def foo(x):           # Trampoline
      mut = os.environ.get('MUTANT_UNDER_TEST', '')
      if mut == 'my_lib__init__1': return x_foo_1(x)
      if mut == 'my_lib__init__2': return x_foo_2(x)
      return x + 1      # Original

Worker 1: MUTANT_UNDER_TEST=my_lib__init__1 → pytest → x_foo_1 aktiv
Worker 2: MUTANT_UNDER_TEST=my_lib__init__2 → pytest → x_foo_2 aktiv
→ Keine Datei-Konflikte, echter Parallelismus
```

---

### FR-11: In-Process Stats Collection

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-11.1 | Das System MUSS pytest.main() in-process für Stats-Collection verwenden | Must | v0.3 |
| FR-11.2 | Das System MUSS Trampoline-Hits via record_trampoline_hit() aufzeichnen | Must | v0.3 |
| FR-11.3 | Das System MUSS tests_by_mangled_function_name korrekt aufbauen | Must | v0.3 |
| FR-11.4 | Das System MUSS nur relevante Tests pro Mutant zuweisen | Must | v0.3 |

### FR-12: Completeness (remaining mutmut features)

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|--------|
| FR-12.1 | Das System MUSS Pfade raten wenn paths_to_mutate nicht gesetzt (guess_paths_to_mutate) | Must | v0.3 |
| FR-12.2 | Das System MUSS inkrementelle Stats-Updates unterstützen (ListAllTestsResult) | Should | v0.3 |
| FR-12.3 | Das System MUSS CLI-Command tests-for-mutant bereitstellen | Should | v0.3 |
| FR-12.4 | Das System MUSS CLI-Command time-estimates bereitstellen | Should | v0.3 |
| FR-12.5 | Das System MUSS CI/CD-Stats exportieren können | Should | v0.3 |
| FR-12.6 | Das System MUSS Type-Checker-Filterung vollständig implementieren | Must | v0.3 |

---

## 3a. Interface-Ergänzungen (v0.3.0)

### 3a.1 _state Module

**Typ:** Python-Modul (Domain Layer)
**Verantwortung:** Geteilte Modul-Level-Globals für Trampoline-Hit-Tracking während der Stats-Phase

```
# _state.py — shared globals (reset before each stats run)
tests_by_mangled_function_name: dict[str, list[str]]
    Mapping: mangled_function_name → list of test node ids that hit this trampoline

current_test_name: str | None
    Name of the currently running test (set by StatsCollector plugin)

def reset_state() -> None
    Zweck: Alle Globals zurücksetzen vor einem Stats-Lauf
    Seiteneffekt: Leert tests_by_mangled_function_name, setzt current_test_name auf None

def record_trampoline_hit(mangled_function_name: str) -> None
    Zweck: Registriert dass current_test_name die gegebene Trampoline-Funktion aufgerufen hat
    Seiteneffekt: Ergänzt current_test_name in tests_by_mangled_function_name[mangled_function_name]
    Thread-sicher: Nein (single-threaded stats phase)
```

### 3a.2 PytestRunner.run_stats() (aktualisiert)

```
run_stats() -> AllTestsMetadata
    Zweck: Test-Dauern UND Trampoline-Hits in-process via pytest.main() messen
    Ablauf:
      1. _state.reset_state()
      2. plugin = StatsCollector()  — pytest plugin, setzt current_test_name, misst Dauer
      3. pytest.main([...], plugins=[plugin])
      4. return AllTestsMetadata(
             test_durations=plugin.durations,            # {test_id: float}
             tests_by_mangled=_state.tests_by_mangled_function_name
         )
    Wichtig: pytest.main() läuft im selben Prozess → _state globals sind direkt zugänglich
```

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | 2026-03-29 | Claude Sonnet 4.6 | Initiale Version — Sprint 0 Phase 3 |
| 0.3.0 | 2026-03-30 | Claude Code Agent | FR-11–12: In-Process Stats Collection, Feature Completeness; Interface-Ergänzungen _state + PytestRunner.run_stats() |
