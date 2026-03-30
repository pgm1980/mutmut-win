# Software Design Specification — mutmut-win

**Version:** 0.6.0
**Datum:** 2026-03-30
**Status:** Approved
**Referenz:** [Architecture Specification](../architecture%20spec/architecture_specification.md)

---

## 1. Functional Requirements (FRs)

### FR-01: Mutation Engine

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-01.1 | Das System MUSS Python-Quelldateien CST-basiert mutieren können (identisch mit mutmut 3.5.0) | Must | v0.1 |
| FR-01.2 | Das System MUSS alle mutmut 3.5.0 Mutations-Operatoren unterstützen | Must | v0.1 |
| FR-01.3 | Das System MUSS Mutanten in eine Trampoline-Datei schreiben können | Must | v0.1 |
| FR-01.4 | Das System MUSS Name-Mangling für Trampoline-Funktionen unterstützen | Must | v0.1 |
| FR-01.5 | Das System MUSS `encoding='utf-8'` für alle File-I/O verwenden | Must | v0.1 |

### FR-02: Prozess-Management

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-02.1 | Das System MUSS Worker-Prozesse via `multiprocessing.spawn` erzeugen | Must | v0.1 |
| FR-02.2 | Das System MUSS einen konfigurierbaren Worker-Pool verwalten (Default: CPU-Count) | Must | v0.1 |
| FR-02.3 | Das System MUSS Tasks über eine Queue an Worker verteilen | Must | v0.1 |
| FR-02.4 | Das System MUSS Events (Started, Completed, TimedOut) über eine Event-Queue empfangen | Must | v0.1 |
| FR-02.5 | Das System MUSS Timeouts via Wall-Clock-Monitor erkennen und Worker killen | Must | v0.1 |
| FR-02.6 | Das System MUSS Ersatz-Worker nach Timeout oder Crash starten | Must | v0.1 |
| FR-02.7 | Das System MUSS bei KeyboardInterrupt alle Worker sauber beenden | Must | v0.1 |

### FR-03: Test-Ausführung

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-03.1 | Das System MUSS pytest als Test-Runner verwenden | Must | v0.1 |
| FR-03.2 | Das System MUSS einen Clean-Test-Run vor Mutation Testing durchführen | Must | v0.1 |
| FR-03.3 | Das System MUSS Test-Statistiken (Laufzeiten) sammeln können | Must | v0.1 |
| FR-03.4 | Das System MUSS einen Forced-Fail-Test ausführen können (Validierung) | Must | v0.1 |
| FR-03.5 | Das System SOLL Coverage-gestütztes Mutieren unterstützen | Should | v0.1 |

### FR-04: Ergebnisse & Persistenz

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-04.1 | Das System MUSS Ergebnisse in SQLite speichern (kompatibel mit mutmut-Schema) | Must | v0.1 |
| FR-04.2 | Das System MUSS Exit-Codes auf Mutant-Status mappen (survived, killed, timeout, etc.) | Must | v0.1 |
| FR-04.3 | Das System MUSS Fortschritt während des Laufs anzeigen | Must | v0.1 |
| FR-04.4 | Das System MUSS bei Abbruch Teilergebnisse speichern | Must | v0.1 |

### FR-05: CLI

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-05.1 | Das System MUSS `mutmut-win run` mit optionalen Mutant-Namen unterstützen | Must | v0.1 |
| FR-05.2 | Das System MUSS `mutmut-win results` zum Anzeigen der Ergebnisse unterstützen | Must | v0.1 |
| FR-05.3 | Das System MUSS `mutmut-win show <NAME>` zum Anzeigen eines Mutanten unterstützen | Must | v0.1 |
| FR-05.4 | Das System MUSS `mutmut-win apply <NAME>` zum Anwenden eines Mutanten unterstützen | Must | v0.1 |
| FR-05.5 | Das System MUSS `mutmut-win browse` für den TUI Result Browser unterstützen | Must | v0.1 |
| FR-05.6 | Das System MUSS `--max-children N` zur Konfiguration der Worker-Anzahl unterstützen | Must | v0.1 |

### FR-06: Konfiguration

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-06.1 | Das System MUSS Konfiguration aus `[tool.mutmut]` in pyproject.toml lesen | Must | v0.1 |
| FR-06.2 | Das System MUSS `paths_to_mutate` unterstützen | Must | v0.1 |
| FR-06.3 | Das System MUSS `tests_dir` unterstützen | Must | v0.1 |
| FR-06.4 | Das System MUSS `do_not_mutate` (Exclude-Pattern) unterstützen | Must | v0.1 |
| FR-06.5 | Das System SOLL `timeout_multiplier` unterstützen (Default: 10) | Should | v0.1 |
| FR-06.6 | Das System SOLL `also_copy` unterstützen | Should | v0.1 |

### FR-07: Type-Checker-Integration

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-07.1 | Das System SOLL Mutanten optional gegen einen Type-Checker prüfen können | Should | v0.1 |
| FR-07.2 | Das System SOLL Mutanten die den Type-Check nicht bestehen als "caught by type check" markieren | Should | v0.1 |

### FR-08: File Setup Pipeline

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-08.1 | Das System MUSS Quelldateien nach mutants/ kopieren | Must | v0.2 |
| FR-08.2 | Das System MUSS mutierte Dateien mit Trampolines auf Disk schreiben | Must | v0.2 |
| FR-08.3 | Das System MUSS sys.path für mutants/-Import einrichten | Must | v0.2 |
| FR-08.4 | Das System MUSS qualifizierte Mutant-Namen konstruieren | Must | v0.2 |
| FR-08.5 | Das System MUSS also_copy-Dateien kopieren | Must | v0.2 |

### FR-09: Test-Mapping + Stats

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-09.1 | Das System MUSS Mutanten auf relevante Tests mappen | Must | v0.2 |
| FR-09.2 | Das System MUSS Stats cachen (mutants/mutmut-stats.json) | Must | v0.2 |
| FR-09.3 | Das System MUSS inkrementelle Stats-Collection unterstützen | Should | v0.2 |
| FR-09.4 | Das System MUSS Type-Checker-Filter im Orchestrator verdrahten | Should | v0.2 |

### FR-10: Mutant-Inspektion + CLI

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-10.1 | Das System MUSS `show` mit echtem Diff implementieren | Must | v0.2 |
| FR-10.2 | Das System MUSS `apply` mit CST-basiertem Ersetzen implementieren | Must | v0.2 |
| FR-10.3 | Das System MUSS Live-Fortschrittsanzeige bieten | Should | v0.2 |

### FR-13: Orphan-Prozess-Schutz (Hardening)

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-13.1 | Das System MUSS Worker-Prozesse via Windows Job Object gruppieren | Must | v0.5 |
| FR-13.2 | Das System MUSS `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` setzen, damit bei Parent-Tod alle Worker + Subprozesse automatisch gekillt werden | Must | v0.5 |
| FR-13.3 | Das System MUSS Graceful Degradation bieten wenn Job Object nicht erstellt werden kann (Warning statt Crash) | Must | v0.5 |
| FR-13.4 | Das System MUSS bei normalem Shutdown den Job Handle sauber schließen | Must | v0.5 |

### FR-14: Erweiterte Mutationsoperatoren (v1.0.0)

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-14.1 | Das System MUSS Regex-Pattern in `re.*()` Aufrufen mutieren können (Quantifier, Character-Classes, Anchors) | Must | v1.0 |
| FR-14.2 | Das System MUSS mathematische Funktionen mutieren können (ceil↔floor, min↔max, abs→x, round→x, sum→0) | Must | v1.0 |
| FR-14.3 | Das System MUSS non-literal Return Values durch `None` ersetzen können | Must | v1.0 |
| FR-14.4 | Das System MUSS Conditional Expressions (`x if c else y`) zu `x` oder `y` vereinfachen können | Must | v1.0 |
| FR-14.5 | Das System MUSS Void-Funktionsaufrufe und raise-Statements durch `pass` ersetzen können | Must | v1.0 |
| FR-14.6 | Das System MUSS Collection-Operationen neutralisieren können (sorted→identity, Comprehension-Filter entfernen) | Must | v1.0 |
| FR-14.7 | Das System MUSS `x or default` zu `x` oder `default` vereinfachen können (nur in Zuweisungskontexten) | Should | v1.0 |
| FR-14.8 | Das System MUSS generierte Regex-Mutationen via `re.compile()` auf Validität prüfen | Must | v1.0 |
| FR-14.9 | Das System SOLL eine Exclusion-Liste für Statement Removal führen (print, logger, warnings) | Should | v1.0 |

---

## 2. Non-Functional Requirements (NFRs)

### NFR-01: Security

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-01.1 | Alle Config-Eingaben MÜSSEN via Pydantic validiert werden | 100% Input-Validierung |
| NFR-01.2 | Keine bekannten Vulnerabilities in Dependencies | pip-audit: 0 Findings |
| NFR-01.3 | Semgrep MUSS vor jedem Release bestehen | 0 offene Security-Findings |
| NFR-01.4 | Alle File-I/O MUSS `encoding='utf-8'` verwenden | Kein implicit CP1252 |

### NFR-02: Performance

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-02.1 | Worker-Startup SOLL < 5s dauern (pytest-Init einmalig) | Benchmark-verifiziert |
| NFR-02.2 | Mutation-Generierung SOLL < 100ms pro Datei dauern | Benchmark-verifiziert |
| NFR-02.3 | Gesamtlaufzeit SOLL ±20% von mutmut auf Linux sein (gleiches Projekt) | Vergleichsmessung |

### NFR-03: Zuverlässigkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-03.1 | Worker-Crashes DÜRFEN den Hauptprozess NICHT zum Absturz bringen | Graceful Recovery |
| NFR-03.2 | Ctrl+C MUSS immer einen sauberen Shutdown auslösen | Teilergebnisse gespeichert |
| NFR-03.3 | Maximal 3 Worker-Neustarts pro Slot bevor Abbruch | Konfigurierbar |

### NFR-04: Testbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-04.1 | Unit Tests MÜSSEN TDD-konform geschrieben werden | Red → Green → Refactor |
| NFR-04.2 | Code Coverage MUSS gemessen werden | ≥ 80% Line Coverage |
| NFR-04.3 | Mutation Testing MUSS durchgeführt werden | Score ≥ 80% auf neuem Code |
| NFR-04.4 | Architekturregeln MÜSSEN als import-linter Contracts existieren | 0 Verletzungen |
| NFR-04.5 | Property-Based Tests MÜSSEN für Roundtrips/Invarianten existieren | Alle kritischen Pfade |
| NFR-04.6 | E2E-Tests MÜSSEN gegen mutmut-Referenzergebnisse validieren | 100% Übereinstimmung |

### NFR-05: Wartbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-05.1 | Code MUSS alle Ruff-Prüfungen bestehen | 0 Findings |
| NFR-05.2 | mypy strict MUSS bestehen | 0 Errors |
| NFR-05.3 | Module SOLLEN < 300 Zeilen sein | Ausnahmen dokumentiert |
| NFR-05.4 | Funktionen SOLLEN < 30 Zeilen sein | Ausnahmen dokumentiert |
| NFR-05.5 | Zirkuläre Abhängigkeiten DÜRFEN NICHT existieren | import-linter verifiziert |
| NFR-05.6 | Öffentliche APIs MÜSSEN Google-Style Docstrings haben | 100% |

### NFR-06: Kompatibilität

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-06.1 | Das System MUSS auf Windows 10/11 lauffähig sein | CI-verifiziert |
| NFR-06.2 | Das System MUSS Python ≥ 3.12 unterstützen (Ziel: 3.14) | CI-verifiziert |
| NFR-06.3 | Config-Format MUSS kompatibel mit mutmut [tool.mutmut] sein | E2E-Test-verifiziert |
| NFR-06.4 | SQLite-Schema MUSS kompatibel mit mutmut sein | Schema-Test |

### NFR-07: Konfigurierbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-07.1 | Worker-Anzahl MUSS konfigurierbar sein (Default: CPU-Count) | Kein Hardcoded Limit |
| NFR-07.2 | Timeout-Multiplikator MUSS konfigurierbar sein (Default: 10) | Konfigurierbar |
| NFR-07.3 | Config-Fehler MÜSSEN beim Start erkannt werden (Fail-Fast) | Pydantic ValidationError |

---

## 3. Interface-Spezifikationen

### 3.1 ProcessExecutor Protocol

**Typ:** Python Protocol
**Verantwortung:** Abstraktion der Prozess-Ausführung für Mutation Tests.

```python
class ProcessExecutor(Protocol):
    def start(self, tasks: list[MutationTask], config: MutmutConfig) -> None:
        """Start worker pool and begin processing tasks."""
        ...

    def shutdown(self, timeout: float = 10.0) -> None:
        """Gracefully shut down all workers."""
        ...

    def get_events(self) -> Iterator[TaskEvent]:
        """Yield events from the event queue."""
        ...
```

### 3.2 MutationOrchestrator

**Typ:** Python Class
**Verantwortung:** Koordiniert den gesamten Mutation-Testing-Ablauf.

```python
class MutationOrchestrator:
    def run(self, config: MutmutConfig) -> MutationRunResult:
        """Execute full mutation testing pipeline.

        1. Generate mutants
        2. Run clean test
        3. Collect stats
        4. Run forced fail
        5. Execute mutation tests (parallel)
        6. Persist results
        """
        ...

    def resume(self, config: MutmutConfig) -> MutationRunResult:
        """Resume a previously interrupted run."""
        ...
```

### 3.3 CLI Commands

**Typ:** Click CLI
**Verantwortung:** User-facing commands.

```
mutmut-win run [--max-children N] [MUTANT_NAMES...]
mutmut-win results [--all]
mutmut-win show <MUTANT_NAME>
mutmut-win apply <MUTANT_NAME>
mutmut-win browse [--show-killed]
```

### 3.4 Worker Interface

**Typ:** Module-Level Function (runs in child process)
**Verantwortung:** Executes mutation tests in worker process.

```python
def worker_main(
    task_queue: Queue[MutationTask | None],
    event_queue: Queue[TaskEvent],
    config: MutmutConfig,
) -> None:
    """Worker entry point. Runs in spawned child process.

    1. Initialize pytest
    2. Loop: get task, run test, report result
    3. Exit on None sentinel
    """
    ...
```

### 3.5 FileSetup Interface

**Typ:** Module-Level Functions (Domain Layer)
**Verantwortung:** Manages mutants/ directory lifecycle.

```python
def walk_source_files(paths_to_mutate: list[str]) -> Iterator[Path]:
    """Yield all Python source files under paths_to_mutate."""
    ...

def walk_all_files(paths_to_mutate: list[str]) -> Iterator[Path]:
    """Yield all files (source + non-Python) under paths_to_mutate."""
    ...

def copy_src_dir(src: Path, dest: Path) -> None:
    """Copy source tree to mutants/ preserving structure."""
    ...

def copy_also_copy_files(also_copy: list[str], mutants_dir: Path) -> None:
    """Copy additional files listed in also_copy config."""
    ...

def setup_source_paths(mutants_dir: Path) -> list[str]:
    """Prepend mutants/ to sys.path, return original sys.path for restore."""
    ...

def write_all_mutants_to_file(
    source_file: Path,
    mutants_dir: Path,
    source_mutation_data: SourceFileMutationData,
) -> None:
    """Write trampolined mutant file to mutants/ directory."""
    ...

def create_mutants_for_file(
    source_file: Path,
    config: MutmutConfig,
) -> SourceFileMutationData:
    """Generate all mutants for a single source file."""
    ...
```

### 3.6 TestMapping Interface

**Typ:** Module-Level Functions (Domain Layer)
**Verantwortung:** Maps mutants to relevant test functions.

```python
def mangled_name_from_mutant_name(mutant_name: str) -> str:
    """Convert mutant_name to mangled function name used in trampoline."""
    ...

def orig_function_and_class_names_from_key(key: str) -> tuple[str, str | None]:
    """Extract original function name and optional class name from mutant key."""
    ...

def tests_for_mutant_names(
    mutant_names: list[str],
    stats: MutmutStats,
) -> dict[str, list[str]]:
    """Return mapping of mutant_name -> list[test_id] for targeted test runs."""
    ...
```

### 3.7 Stats Interface

**Typ:** Module-Level Functions (Application Layer)
**Verantwortung:** Caches test timing data in mutants/mutmut-stats.json.

```python
def load_stats(mutants_dir: Path) -> MutmutStats | None:
    """Load stats from mutants/mutmut-stats.json, return None if missing."""
    ...

def save_stats(stats: MutmutStats, mutants_dir: Path) -> None:
    """Persist stats to mutants/mutmut-stats.json with encoding='utf-8'."""
    ...

def collect_or_load_stats(
    config: MutmutConfig,
    mutants_dir: Path,
    runner: PytestRunner,
) -> MutmutStats:
    """Load stats if up-to-date (hash match), else collect fresh and save."""
    ...
```

### 3.8 MutantDiff Interface

**Typ:** Module-Level Functions (Application Layer)
**Verantwortung:** Diff generation and source application for mutants.

```python
def find_mutant(
    mutant_name: str,
    mutants_dir: Path,
) -> MutantLocation:
    """Locate a mutant's trampolined file and function offset."""
    ...

def read_mutants_module(mutant_file: Path) -> str:
    """Read trampolined mutant file with encoding='utf-8'."""
    ...

def read_orig_module(source_file: Path) -> str:
    """Read original source file with encoding='utf-8'."""
    ...

def get_diff_for_mutant(mutant_name: str, mutants_dir: Path) -> str:
    """Return unified diff string between original and mutated source."""
    ...

def apply_mutant(mutant_name: str, mutants_dir: Path) -> None:
    """Write CST-based mutated source back to original source file."""
    ...
```

---

## 4. Datenmodelle

### 4.1 MutmutConfig

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| paths_to_mutate | list[str] | Pfade zu mutierenden Quelldateien | min_length=1 |
| tests_dir | str | Verzeichnis mit Tests | Muss existieren |
| do_not_mutate | list[str] | Exclude-Pattern | Optional |
| also_copy | list[str] | Zusätzlich zu kopierende Dateien | Optional |
| max_children | int | Anzahl Worker-Prozesse | ≥ 1, Default: cpu_count() |
| timeout_multiplier | float | Multiplikator für Timeout-Berechnung | > 0, Default: 10.0 |
| use_type_checker | str \| None | Type-Checker-Befehl | Optional |

### 4.2 MutationTask

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| mutant_name | str | Eindeutiger Mutant-Identifier | required |
| tests | list[str] | Auszuführende Tests | min_length=1 |
| estimated_time | float | Geschätzte Laufzeit (Sekunden) | ≥ 0 |
| timeout_seconds | float | Deadline für diesen Task | > 0 |

### 4.3 TaskEvent (Union Type)

**TaskStarted:**

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| mutant_name | str | Gestarteter Mutant |
| worker_pid | int | PID des Workers |
| timestamp | datetime | Startzeitpunkt |

**TaskCompleted:**

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| mutant_name | str | Abgeschlossener Mutant |
| worker_pid | int | PID des Workers |
| exit_code | int | pytest Exit-Code |
| duration | float | Laufzeit in Sekunden |

**TaskTimedOut:**

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| mutant_name | str | Timeout-Mutant |
| worker_pid | int | PID des gekillten Workers |

### 4.4 MutationResult

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| mutant_name | str | Mutant-Identifier |
| status | str | survived, killed, timeout, suspicious, etc. |
| exit_code | int \| None | pytest Exit-Code |
| duration | float \| None | Laufzeit |

### 4.5 SourceFileMutationData

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| filename | str | Quelldatei-Pfad |
| mutants | dict[str, str] | Mutant-Name → mutierter Code |
| hash | str | Hash der Originaldatei |

### 4.6 MutmutStats

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| test_times | dict[str, float] | test_id → Laufzeit in Sekunden |
| file_hashes | dict[str, str] | Quelldatei-Pfad → SHA256-Hash |
| collected_at | datetime | Zeitstempel der Erhebung |

### 4.7 MutantLocation

| Feld | Typ | Beschreibung |
|------|-----|-------------|
| mutant_name | str | Mutant-Identifier |
| source_file | Path | Originale Quelldatei |
| mutant_file | Path | Trampolined Datei in mutants/ |
| function_name | str | Mutierte Funktion |
| class_name | str \| None | Umgebende Klasse (optional) |

---

## 5. Datenflüsse

### 5.1 Hauptfluss: Mutation Testing Run

```
1. CLI parst Argumente, lädt Config
2. Orchestrator.run() wird aufgerufen
3. Mutation Engine generiert Mutanten (CST-basiert)
4. Clean Test: pytest läuft auf Original-Code (muss grün sein)
5. Stats-Phase: Test-Laufzeiten messen
6. Forced-Fail-Test: Validierung des Trampoline-Mechanismus
7. Worker-Pool wird gestartet (N spawn-Prozesse)
8. Tasks werden in task_queue gefüllt
9. Event-Consumer-Loop:
   a. TaskStarted → Timeout-Countdown starten
   b. TaskCompleted → Ergebnis speichern, Fortschritt anzeigen
   c. TaskTimedOut → Ergebnis speichern, Ersatz-Worker starten
10. Ergebnisse in SQLite persistieren
11. Zusammenfassung anzeigen
```

### 5.2 Fehlerfluss: Worker-Crash

```
1. Worker stirbt unerwartet (is_alive() = False)
2. Timeout-Monitor erkennt inaktiven Worker
3. Task wird als "suspicious" markiert
4. Ersatz-Worker wird gestartet (max 3 pro Slot)
5. Bei Überschreitung: Slot wird deaktiviert, Warnung ausgegeben
```

### 5.3 Fehlerfluss: Graceful Shutdown

```
1. KeyboardInterrupt empfangen
2. Orchestrator.shutdown() aufgerufen
3. Alle Worker: Process.kill()
4. Alle Worker: Process.join(timeout=5)
5. Queues leeren und schließen
6. Bisherige Ergebnisse in SQLite speichern
7. "Stopping..." + Zusammenfassung ausgeben
```

---

## 6. Fehlerbehandlung

### 6.1 Fehler-Kategorien

| Kategorie | Basis-Typ | Exit-Code | Behandlung |
|-----------|-----------|-----------|------------|
| Config-Fehler | ConfigError | 2 | Sofort Fehlermeldung, Exit |
| Clean-Test-Failure | OrchestratorError | 1 | Abbruch mit Hinweis |
| Worker-Crash | WorkerError | - | Retry (max 3x), dann suspicious |
| Timeout | - | - | Kill Worker, TaskTimedOut Event |
| Mutation-Fehler | MutationError | 2 | Datei überspringen, Warnung |
| Unerwarteter Fehler | MutmutWinError | 1 | Loggen, Graceful Exit |

### 6.2 Custom Exceptions

```
MutmutWinError (base)
├── ConfigError
│   └── InvalidConfigValueError
├── WorkerError
│   ├── WorkerCrashError
│   └── WorkerInitError
├── OrchestratorError
│   ├── CleanTestFailedError
│   └── ForcedFailError
└── MutationError
    └── MutationParseError
```

---

## 7. Sicherheitskonzept

| Maßnahme | Beschreibung | Verifizierung |
|----------|-------------|---------------|
| Input-Validierung | Pydantic validiert alle Config-Werte | Unit Tests + Semgrep |
| File-I/O Encoding | `encoding='utf-8'` explizit auf allen `open()` Calls | Ruff + Code Review |
| Worker-Isolation | Mutanten laufen in eigenen Prozessen | Architektur-Design |
| Dependency Audit | Regelmäßige pip-audit Prüfung | Sprint DoD |
| No Pickle Untrusted | Queue-Daten sind intern erzeugt, nicht von extern | Code Review |

---

## 8. Deployment & Operations

### 8.1 Build-Artefakte

| Artefakt | Format | Ziel |
|----------|--------|------|
| mutmut-win | wheel + sdist | PyPI |

### 8.2 Konfigurationsparameter

| Parameter | Default | Beschreibung | Typ |
|-----------|---------|-------------|-----|
| paths_to_mutate | ["src/"] | Zu mutierende Pfade | list[str] |
| tests_dir | "tests/" | Test-Verzeichnis | str |
| max_children | cpu_count() | Worker-Anzahl | int |
| timeout_multiplier | 10.0 | Timeout-Faktor | float |
| do_not_mutate | [] | Exclude-Pattern | list[str] |
| also_copy | [] | Zusätzliche Kopien | list[str] |
| use_type_checker | None | Type-Checker-Befehl | str? |

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | 2026-03-30 | Claude Code Agent | Initiale Version |
| 0.2.0 | 2026-03-30 | Claude Code Agent | FR-08–10: File Setup Pipeline, Test Mapping + Stats, Mutant Inspektion + CLI; Interface-Specs 3.5–3.8; Data Models 4.6–4.7 |
| 0.3.0 | 2026-03-30 | Claude Code Agent | FR-11–12: In-Process Stats Collection, Feature Completeness |
| 0.5.0 | 2026-03-30 | Claude Code Agent | FR-13: Orphan-Prozess-Schutz (Windows Job Objects) |
| 0.6.0 | 2026-03-30 | Claude Code Agent | FR-14: 7 neue Mutationsoperatoren für v1.0.0 |
