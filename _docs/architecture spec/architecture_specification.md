# Architecture Specification — mutmut-win

**Version:** 0.1.0
**Datum:** 2026-03-30
**Status:** Approved

---

## 1. Systemübersicht

**Kurzbeschreibung:** mutmut-win ist ein Windows-natives Mutation-Testing-Tool für Python, basierend auf mutmut 3.5.0. Es ersetzt alle Unix-only APIs durch Windows-kompatible Alternativen und bietet eine modulare, testbare Architektur.

**Architekturtyp:** Layered Architecture (4 Schichten) mit Worker-Pool-Pattern für parallele Ausführung.

### 1.1 Kontextdiagramm

```
┌─────────────────────────────────────────────────────────┐
│                    Systemkontext                         │
│                                                         │
│  ┌──────────┐    ┌───────────────────┐    ┌──────────┐  │
│  │Developer │───►│   mutmut-win      │───►│ pytest   │  │
│  │(CLI User)│    │   (CLI Tool)      │    │(Test     │  │
│  └──────────┘    └───────────────────┘    │ Runner)  │  │
│                         │    │            └──────────┘  │
│                         │    │                          │
│                         ▼    ▼                          │
│               ┌──────────┐  ┌──────────────┐            │
│               │ SQLite DB│  │Python Source │            │
│               │(Results) │  │(Target Code) │            │
│               └──────────┘  └──────────────┘            │
│                         │                               │
│                         ▼                               │
│               ┌──────────────────┐                      │
│               │ pyproject.toml   │                      │
│               │ ([tool.mutmut])  │                      │
│               └──────────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Qualitätsziele

| Priorität | Ziel | Maßnahme | Metrik |
|-----------|------|----------|--------|
| 1 | Korrektheit | E2E-Tests gegen mutmut-Snapshot-Ergebnisse | 100% Übereinstimmung mit mutmut-Referenzergebnissen |
| 2 | Testbarkeit | DI, Protocol-basierte Interfaces, TDD | Coverage ≥ 80%, Mutation Score ≥ 80% |
| 3 | Wartbarkeit | Schichtentrennung, Module < 300 Zeilen | 0 Architekturverletzungen, 0 Lint-Findings |
| 4 | Performance | Worker-Pool mit pytest-Caching | Vergleichbar mit mutmut auf Linux (±20%) |
| 5 | Security | Input-Validierung, Semgrep | 0 Semgrep-Findings |

### 1.3 Technologie-Stack

| Kategorie | Technologie | Version | Begründung |
|-----------|-------------|---------|------------|
| Runtime | Python | 3.14.3 | Projektvorgabe, aktuelle Features |
| Mutation Engine | libcst | ≥1.8.5 | CST-basiert, identisch mit mutmut |
| CLI | click | ≥8.0.0 | Kompatibel mit mutmut CLI-Patterns |
| TUI | textual | ≥1.0.0 | Result Browser (aus mutmut übernommen) |
| Config/Models | pydantic | ≥2.0.0 | Validierung, Type Safety (CLAUDE.md Vorgabe) |
| Testing | pytest + hypothesis | ≥8.3 / ≥6.119 | TDD, Property-Based Testing |
| Linting | ruff | aktuell | All-in-One (ersetzt flake8, isort, black) |
| Type Checking | mypy | aktuell | Strict Mode |
| Security | semgrep | aktuell | Statische Sicherheitsanalyse |
| Architecture | import-linter | ≥2.1 | Schichtentrennung durchsetzen |
| Package Manager | uv | aktuell | Schnell, reproduzierbar, Lockfile |

---

## 2. Architekturentscheidungen (ADRs)

### ADR-001: Prozess-Erzeugung — spawn + Worker-Pool

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

mutmut nutzt `os.fork()` zur Erzeugung von Kindprozessen pro Mutant. `os.fork()` existiert nicht auf Windows. Eine Alternative muss gefunden werden, die effizient mit tausenden Mutanten umgehen kann.

#### Optionen

##### Option A: multiprocessing spawn + Worker-Pool

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Medium |
| Kosten (Entwicklung + Betrieb) | Niedrig (stdlib) |
| Skalierbarkeit | Hoch (N Workers, Queue-basiert) |
| Wartbarkeit | Hoch (klare Verantwortlichkeiten) |
| Ecosystem-Reife | Hoch (stdlib, gut dokumentiert) |

**Vorteile:**
- Worker werden einmal gestartet und wiederverwendet → pytest-Init nur 1x pro Worker
- Standard-Library, keine externe Dependency
- Queue-basierte Kommunikation ist Pythonic und gut getestet
- Volle Kontrolle über Worker-Lifecycle

**Nachteile:**
- spawn erzeugt frischen Interpreter (schwerer als fork)
- Pickle-Serialisierung über Queues (alle Daten müssen pickle-bar sein)

##### Option B: subprocess.Popen pro Mutant

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Low |
| Kosten | Sehr hoch (Laufzeit) |
| Skalierbarkeit | Niedrig |
| Wartbarkeit | Hoch |
| Ecosystem-Reife | Hoch |

**Vorteile:**
- Einfachste Implementierung
- Vollständige Prozess-Isolation

**Nachteile:**
- Python-Startup + pytest-Import pro Mutant → bei 1000+ Mutanten extrem langsam
- Kein Caching von Test-Collection

##### Option C: concurrent.futures.ProcessPoolExecutor

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Low |
| Kosten | Niedrig |
| Skalierbarkeit | Medium |
| Wartbarkeit | Medium |
| Ecosystem-Reife | Hoch |

**Vorteile:**
- High-Level API, wenig Boilerplate
- Automatisches Load Balancing

**Nachteile:**
- Wenig Kontrolle über Worker-Lifecycle und Initialisierung
- Schwierig, custom pytest-Caching zu implementieren
- Keine direkte Queue-Kontrolle für Events

#### Trade-off-Analyse

Option A bietet den besten Kompromiss: Der Worker-Pool amortisiert den spawn-Overhead über alle Mutanten hinweg, ermöglicht pytest-Caching und gibt volle Kontrolle über Timeout-Handling und Error Recovery. Option B ist zu langsam, Option C zu eingeschränkt.

#### Entscheidung

Option A: `multiprocessing.set_start_method('spawn')` mit langlebigem Worker-Pool.

#### Konsequenzen

- **Wird einfacher:** Timeout-Handling, Worker-Recovery, pytest-Caching
- **Wird schwieriger:** Alle Queue-Daten müssen pickle-bar sein
- **Muss revisited werden:** Worker-Pool-Größe und Queue-Buffering bei sehr großen Projekten

#### Action Items

- [ ] `process/executor.py` implementieren (SpawnPoolExecutor)
- [ ] `process/worker.py` implementieren (Worker-Loop)
- [ ] Pickle-Barkeit aller Datentypen sicherstellen

---

### ADR-002: Timeout-Strategie — Wall-Clock-Timeout

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

mutmut nutzt `resource.setrlimit(RLIMIT_CPU)` für CPU-Zeit-Limits, die bei Überschreitung `SIGXCPU` auslösen. Weder `resource` noch `SIGXCPU` existieren auf Windows.

#### Optionen

##### Option A: Wall-Clock-Timeout via Monitor-Thread

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Low |
| Kosten | Keine (stdlib) |
| Skalierbarkeit | Hoch |
| Wartbarkeit | Hoch |
| Ecosystem-Reife | Hoch |

**Vorteile:**
- Einfach, zuverlässig, keine Dependencies
- Monitor-Thread im Hauptprozess, keine Windows-spezifischen APIs
- Injiziert TaskTimedOut-Events in die Event-Queue → einheitliches Event-Processing

**Nachteile:**
- Wall-Clock ≠ CPU-Zeit (I/O-Waits zählen mit)
- Bei hoher System-Last kann der Timeout zu früh auslösen
- Mitigation: Großzügiger Default-Multiplikator (10x)

##### Option B: Windows Job Objects

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | High |
| Kosten | Mittel (pywin32 Dependency) |
| Skalierbarkeit | Hoch |
| Wartbarkeit | Niedrig |
| Ecosystem-Reife | Mittel |

**Vorteile:**
- Echte CPU-Zeit-Limits (näher an RLIMIT_CPU)

**Nachteile:**
- Benötigt ctypes oder pywin32
- Komplexe Windows-API, schwer testbar
- Fragil bei verschiedenen Windows-Versionen

#### Trade-off-Analyse

Mutation Testing braucht keine präzisen CPU-Limits — es geht darum, Endlosschleifen zu erkennen. Wall-Clock-Timeout mit großzügigem Multiplikator ist dafür ausreichend und deutlich einfacher zu implementieren und testen.

#### Entscheidung

Option A: Wall-Clock-Timeout via Monitor-Thread.

Timeout-Berechnung: `max(30, (estimated_time + 5) * timeout_multiplier)`
- `estimated_time`: Summe der geschätzten Test-Dauern aus Stats-Phase
- `timeout_multiplier`: Konfigurierbar, Default 10
- Minimum: 30 Sekunden

#### Konsequenzen

- **Wird einfacher:** Implementierung, Testing, keine Windows-spezifischen APIs
- **Wird schwieriger:** Präzise CPU-Zeit-Messung (nicht möglich)
- **Muss revisited werden:** Multiplikator-Default bei User-Feedback zu False-Positives

#### Action Items

- [ ] `process/timeout.py` implementieren (WallClockTimeout)
- [ ] Timeout-Konfiguration in Config-Model aufnehmen
- [ ] Integration Tests für Timeout-Verhalten

---

### ADR-003: Inter-Process Communication — Zwei-Queue-Architektur

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

Worker-Prozesse müssen Tasks empfangen und Ergebnisse zurücksenden. Die Kommunikation muss zuverlässig, effizient und testbar sein.

#### Optionen

##### Option A: Zwei multiprocessing.Queue

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Low |
| Kosten | Keine (stdlib) |
| Skalierbarkeit | Hoch |
| Wartbarkeit | Hoch |
| Ecosystem-Reife | Hoch |

**Vorteile:**
- `task_queue` (main → worker) + `event_queue` (worker → main)
- Timeout-Monitor kann TaskTimedOut-Events in event_queue injizieren
- Pickle-basiert, funktioniert mit Pydantic Models

**Nachteile:**
- Queue-Größe muss beachtet werden
- Potential für Deadlocks bei falscher Nutzung

##### Option B: Pipes (multiprocessing.Pipe)

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Medium |
| Kosten | Keine |
| Skalierbarkeit | Medium |
| Wartbarkeit | Medium |
| Ecosystem-Reife | Hoch |

**Vorteile:**
- Direkte Kommunikation pro Worker

**Nachteile:**
- N Pipes verwalten statt 2 Queues
- Kein einheitlicher Event-Stream

#### Trade-off-Analyse

Zwei Queues sind die einfachste und robusteste Lösung. Der einheitliche Event-Stream ermöglicht es dem Orchestrator, alle Events (TaskStarted, TaskCompleted, TaskTimedOut) in einer einzigen Loop zu verarbeiten.

#### Entscheidung

Option A: Zwei `multiprocessing.Queue` — `task_queue` und `event_queue`.

#### Konsequenzen

- **Wird einfacher:** Event-Processing im Orchestrator, Timeout-Integration
- **Wird schwieriger:** Alle Datentypen müssen pickle-bar sein
- **Muss revisited werden:** Queue-Größe bei Projekten mit 10.000+ Mutanten

#### Action Items

- [ ] Queue-Datentypen in `models.py` definieren (MutationTask, TaskStarted, TaskCompleted, TaskTimedOut)
- [ ] Pickle-Roundtrip-Tests mit hypothesis

---

### ADR-004: Modulstruktur — Clean-Room Rewrite

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

mutmut 3.5.0 hat eine monolithische `__main__.py` mit ~1700 Zeilen. Für Testbarkeit und Wartbarkeit muss der Code in fokussierte Module aufgeteilt werden.

#### Entscheidung

Clean-Room Rewrite in folgende Module:

```
src/mutmut_win/
  __init__.py           # Package Root, Version
  py.typed              # PEP 561 Marker
  config.py             # Pydantic Config, load_config
  models.py             # Domain Models (MutationTask, Events, Results)
  constants.py          # Exit-Code-Mapping, Status-Konstanten
  mutation.py           # CST-Mutation Engine (aus mutmut)
  node_mutation.py      # Node-Level Mutationen (aus mutmut)
  trampoline.py         # Trampoline-Templates (aus mutmut)
  code_coverage.py      # Coverage-Sammlung (aus mutmut)
  type_checking.py      # Type-Checker-Integration (aus mutmut)
  process/
    __init__.py
    executor.py         # SpawnPoolExecutor
    timeout.py          # WallClockTimeout
    worker.py           # Worker-Loop
  runner.py             # PytestRunner
  orchestrator.py       # MutationOrchestrator
  cli.py                # Click CLI
  browser.py            # TUI Result Browser
```

#### Konsequenzen

- **Wird einfacher:** Testen, Verstehen, Erweitern einzelner Komponenten
- **Wird schwieriger:** Initiale Implementierung (mehr Dateien, mehr Interfaces)
- **Muss revisited werden:** Modulaufteilung wenn Module zu groß werden

---

### ADR-005: Konfiguration — Pydantic v2

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

mutmut nutzt eine Python Dataclass für Config. CLAUDE.md mandatiert Pydantic für alle Datenstrukturen.

#### Entscheidung

Pydantic v2 BaseModel für Config. Geladen aus `pyproject.toml` Sektion `[tool.mutmut]` (kompatibel mit mutmut).

#### Konsequenzen

- **Wird einfacher:** Validierung, Defaults, Serialisierung, Testing mit hypothesis
- **Wird schwieriger:** Nichts nennenswert
- **Muss revisited werden:** Bei Config-Erweiterungen

---

### ADR-006: Datenpersistenz — Kompatibles SQLite-Schema

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

mutmut speichert Ergebnisse in SQLite. Entscheidung: kompatibles oder neues Schema?

#### Entscheidung

Kompatibles SQLite-Schema (identisch mit mutmut). Der TUI-Browser liest aus dieser DB, und Kompatibilität minimiert den Implementierungsaufwand.

#### Konsequenzen

- **Wird einfacher:** TUI-Browser-Port, weniger Code
- **Wird schwieriger:** Schema-Optimierungen für Windows
- **Muss revisited werden:** Bei Schema-Änderungen in zukünftigen mutmut-Versionen

---

### ADR-007: E2E-Testing — mutmut-Testprojekte als Gold-Standard

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

Korrektheit ist das höchste Qualitätsziel. Wie validieren wir, dass mutmut-win identische Ergebnisse wie mutmut produziert?

#### Entscheidung

Übernahme aller 5 E2E-Testprojekte aus mutmut:
1. `my_lib` (~65 Mutanten)
2. `config` (~12 Mutanten)
3. `mutate_only_covered_lines` (~32 Mutanten)
4. `type_checking` (~11 Mutanten)
5. `py3_14_features` (~4 Mutanten)

Snapshot-basierte Vergleiche der Mutationsergebnisse gegen verifizierte Referenzdaten.

#### Konsequenzen

- **Wird einfacher:** Korrektheitsprüfung — Gold-Standard vorhanden
- **Wird schwieriger:** Segfault-Mutant (Windows-Exit-Code weicht ab)
- **Muss revisited werden:** Bei neuen mutmut-Versionen mit geänderten Testprojekten

---

### ADR-008: CLI-Framework — click

**Status:** Accepted
**Datum:** 2026-03-30

#### Entscheidung

click als CLI-Framework. Kompatibel mit mutmut-CLI-Patterns, exzellente Test-Unterstützung via CliRunner.

---

### ADR-009: Schichtarchitektur — 4 Layers mit import-linter

**Status:** Accepted
**Datum:** 2026-03-30

#### Entscheidung

4-Schichten-Architektur, durchgesetzt via import-linter:

1. **CLI Layer**: `cli.py`, `browser.py`
2. **Application Layer**: `orchestrator.py`, `runner.py`
3. **Domain Layer**: `config.py`, `models.py`, `constants.py`, `mutation.py`, `node_mutation.py`, `trampoline.py`
4. **Infrastructure Layer**: `process/`, `code_coverage.py`, `type_checking.py`

---

### ADR-010: Fehlerbehandlung — Custom Exception Hierarchy

**Status:** Accepted
**Datum:** 2026-03-30

#### Entscheidung

```
MutmutWinError (base)
├── ConfigError
├── WorkerError
├── OrchestratorError
└── MutationError
```

Worker kommunizieren Fehler über die Event-Queue. Keine Exceptions über Prozessgrenzen.

---

### ADR-011: Distribution — PyPI Package

**Status:** Accepted
**Datum:** 2026-03-30

#### Entscheidung

Distribution als PyPI-Package `mutmut-win`. Entry-Point: `mutmut-win` CLI-Befehl. Build-Backend: hatchling.

---

### ADR-012: File Setup Pipeline — mutants/ Directory Management

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

mutmut's trampoline mechanism requires source files to be copied to a `mutants/` directory, where the mutated (trampolined) versions replace the originals. sys.path must be manipulated so pytest imports from `mutants/` instead of the original source. This pipeline was missing in the initial port.

#### Entscheidung

New module `file_setup.py` handles all file operations: walking source files, copying to mutants/, writing mutated code, setting up sys.path. Ported 1:1 from mutmut's __main__.py with encoding='utf-8' added to all open() calls.

#### Konsequenzen

- **Wird einfacher:** Orchestrator bleibt schlank — Dateisystem-Logik ist isoliert in file_setup.py
- **Wird schwieriger:** sys.path-Manipulation muss Thread-sicher rückgängig gemacht werden
- **Muss revisited werden:** Bei mutmut-Versionswechseln mit geänderten mutants/-Layouts

#### Action Items

- [ ] `file_setup.py` implementieren (Domain Layer)
- [ ] Orchestrator-Integration: `_generate_mutants` delegiert an file_setup
- [ ] Unit-Tests mit temporären Verzeichnissen (tmp_path fixture)

---

### ADR-013: Test Mapping + Stats Caching

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

mutmut mappt Mutanten auf relevante Tests und cached Test-Laufzeiten in einer JSON-Datei. Ohne dieses Mapping laufen alle Tests für jeden Mutanten, was die Laufzeit dramatisch erhöht.

#### Entscheidung

Neues Modul `test_mapping.py` implementiert die Mutant-zu-Test-Zuordnung via mangled names. Neues Modul `stats.py` implementiert Load/Save/CollectOrLoad für `mutants/mutmut-stats.json`. Inkrementelles Caching: Stats werden nur neu gesammelt wenn Quelldateien sich geändert haben (Hash-Vergleich).

#### Konsequenzen

- **Wird einfacher:** Zielgerichtete Test-Ausführung pro Mutant (deutlich schneller)
- **Wird schwieriger:** Mangled-Name-Logik ist komplex und muss 1:1 mit mutmut übereinstimmen
- **Muss revisited werden:** Bei Änderungen an mutmut's Name-Mangling-Strategie

#### Action Items

- [ ] `test_mapping.py` implementieren (Domain Layer)
- [ ] `stats.py` implementieren (Application Layer)
- [ ] Orchestrator-Integration: Test-Assignment und Stats-Caching verdrahten
- [ ] Type-Checker-Filter in Orchestrator verdrahten

---

### ADR-014: Mutant Inspection + CLI — show/apply

**Status:** Accepted
**Datum:** 2026-03-30

#### Kontext

Die CLI-Commands `show` und `apply` sind als Stubs implementiert. `show` muss echte Diffs zwischen Original und mutiertem Code anzeigen. `apply` muss CST-basiert den mutierten Code in die Quelldatei schreiben.

#### Entscheidung

Neues Modul `mutant_diff.py` implementiert `find_mutant`, `read_mutants_module`, `read_orig_module`, `get_diff_for_mutant` (unified diff) und `apply_mutant` (CST-basierter Source-Ersatz). Live-Fortschrittsanzeige via `print_stats`.

#### Konsequenzen

- **Wird einfacher:** CLI-Commands sind vollständig und benutzbar
- **Wird schwieriger:** apply muss atomisch sein (kein halbes Schreiben)
- **Muss revisited werden:** Bei Encoding-Problemen mit Nicht-ASCII-Code

#### Action Items

- [ ] `mutant_diff.py` implementieren (Application Layer)
- [ ] `show`-Command: echten Diff anzeigen
- [ ] `apply`-Command: CST-basierten Ersatz implementieren
- [ ] E2E-Validierungstest auf simple_lib

---

## 3. Komponentenstruktur

### 3.1 Schichtenübersicht

```
┌─────────────────────────────────────────────┐
│          CLI Layer (Presentation)            │  ← cli.py, browser.py
├─────────────────────────────────────────────┤
│          Application Layer (Service)        │  ← orchestrator.py, runner.py,
│                                             │     stats.py, mutant_diff.py
├─────────────────────────────────────────────┤
│          Domain Layer (Core)                │  ← config, models, constants,
│                                             │     mutation, node_mutation,
│                                             │     trampoline, file_setup,
│                                             │     test_mapping
├─────────────────────────────────────────────┤
│          Infrastructure Layer               │  ← process/, code_coverage,
│                                             │     type_checking
└─────────────────────────────────────────────┘
```

### 3.2 CLI Layer

**Verantwortung:** User-Interface (CLI-Commands, TUI Result Browser)
**Enthält:** `cli.py` (Click commands), `browser.py` (Textual TUI)
**Abhängigkeiten:** Application Layer

### 3.3 Application Layer

**Verantwortung:** Orchestrierung des Mutation-Testing-Ablaufs
**Enthält:** `orchestrator.py` (MutationOrchestrator), `runner.py` (PytestRunner), `stats.py` (Stats Load/Save/CollectOrLoad), `mutant_diff.py` (Diff + Apply)
**Abhängigkeiten:** Domain Layer, Infrastructure Layer (via Interfaces)

### 3.4 Domain Layer

**Verantwortung:** Geschäftslogik, Modelle, Mutation Engine
**Enthält:** `config.py`, `models.py`, `constants.py`, `mutation.py`, `node_mutation.py`, `trampoline.py`, `file_setup.py` (mutants/ Directory Management), `test_mapping.py` (Mutant→Test Mapping)
**Abhängigkeiten:** Keine (eigenständig)

### 3.5 Infrastructure Layer

**Verantwortung:** Prozess-Management, Coverage-Sammlung, Type-Checking
**Enthält:** `process/` (executor, timeout, worker), `code_coverage.py`, `type_checking.py`
**Abhängigkeiten:** Domain Layer (implementiert Interfaces)

---

## 4. Abhängigkeitsregeln

```
CLI → Application → Domain ← Infrastructure
                      ↑
                      │
              (Domain kennt keine
               äußeren Schichten)
```

| Von | Darf zugreifen auf | Darf NICHT zugreifen auf |
|-----|-------------------|-------------------------|
| CLI | Application, Domain | Infrastructure (direkt) |
| Application | Domain, Infrastructure (via Interfaces) | CLI |
| Domain | Nichts (eigenständig) | Alle anderen Schichten |
| Infrastructure | Domain (implementiert Interfaces) | CLI, Application |

Diese Regeln werden als import-linter Contracts in `pyproject.toml` durchgesetzt.

---

## 5. Querschnittsthemen

### 5.1 Fehlerbehandlung

| Fehlertyp | Handling | Beispiel |
|-----------|----------|----------|
| Config-Fehler | Fail-Fast mit klarer Fehlermeldung | Ungültiger pyproject.toml-Wert |
| Worker-Crash | Detect via is_alive(), Ersatz-Worker starten | Worker stirbt bei segfault-Mutant |
| Timeout | kill() + TaskTimedOut Event | Endlosschleifen-Mutant |
| pytest-Init-Fehler | Max 3 Neustarts, dann Abbruch | Fehlende Test-Dependencies |
| KeyboardInterrupt | Graceful Shutdown, Teilergebnisse speichern | Ctrl+C |

### 5.2 Logging

**Framework:** logging (stdlib)
**Strategie:** Strukturiertes Logging mit konfiguriertem Level.

| Level | Verwendung |
|-------|-----------|
| ERROR | Worker-Crashes, unerwartete Fehler |
| WARNING | Timeout, suspicious results |
| INFO | Mutation-Fortschritt, Start/Stop |
| DEBUG | Queue-Operationen, Worker-Lifecycle |

### 5.3 Konfiguration

**Strategie:** `pyproject.toml` Sektion `[tool.mutmut]` → Pydantic Model → Defaults für fehlende Werte.

Hierarchie: CLI-Flags > pyproject.toml > Defaults

### 5.4 Security

**Strategie:**
- Input-Validierung via Pydantic (Config, CLI-Argumente)
- Keine Ausführung von untrusted Code (Mutanten werden nur in isolierten Worker-Prozessen getestet)
- `encoding='utf-8'` für alle File-I/O (verhindert CP1252-Probleme auf Windows)
- Semgrep-Scan vor jedem Release

---

## 6. Deployment

### 6.1 Deployment-Modell

**Typ:** PyPI Package mit CLI Entry-Point

### 6.2 Plattform-Support

| Plattform | Support-Level | Besonderheiten |
|-----------|--------------|----------------|
| Windows | Primär | Einzige unterstützte Plattform |
| Linux | Nicht unterstützt | Nutze mutmut |
| macOS | Nicht unterstützt | Nutze mutmut |

### 6.3 Build & Distribution

```bash
# Install dependencies
uv sync

# Test
uv run pytest

# Build
uv build

# Publish
uv publish
```

---

## 7. Risiken und technische Schulden

| # | Risiko / Schuld | Impact | Mitigation | Status |
|---|----------------|--------|------------|--------|
| 1 | Spawn-Performance langsamer als fork | Medium | Worker-Pool amortisiert Startup-Kosten | Mitigated |
| 2 | Wall-Clock ≠ CPU-Zeit bei hoher Last | Low | Großzügiger Timeout-Multiplikator (10x) | Mitigated |
| 3 | Segfault-Mutant Exit-Code auf Windows | Low | Separater erwarteter Wert in E2E-Tests | Mitigated |
| 4 | Queue-Serialisierung (pickle) | Low | Nur primitive Typen + Pydantic Models | Mitigated |
| 5 | mutmut-Schema-Änderungen | Medium | Schema kompatibel halten, Version prüfen | Open |
| 6 | Windows-Encoding (CP1252) | Medium | Explizites encoding='utf-8' überall | Mitigated |

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | 2026-03-30 | Claude Code Agent | Initiale Version |
| 0.2.0 | 2026-03-30 | Claude Code Agent | ADR-012–014: File Setup Pipeline, Test Mapping + Stats, Mutant Inspection + CLI; neue Module in Komponentenstruktur |
