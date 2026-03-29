# Software Design Specification — <Projektname>

**Version:** 0.1.0
**Datum:** <YYYY-MM-DD>
**Status:** Draft | Review | Approved
**Referenz:** [Architecture Specification](../architecture%20spec/architecture_specification.md)

---

## 1. Functional Requirements (FRs)

> Jedes FR beschreibt eine konkrete Systemfähigkeit.
> Format: **MUSS** = verpflichtend, **SOLL** = empfohlen, **KANN** = optional.
> Priorisierung: Must | Should | Could | Won't (MoSCoW).

### FR-01: <Feature-Bereich 1 — z.B. Core Operations>

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-01.1 | Das System MUSS <Fähigkeit A> unterstützen | Must | v0.1 |
| FR-01.2 | Das System MUSS <Fähigkeit B> unterstützen | Must | v0.1 |
| FR-01.3 | Das System SOLL <Fähigkeit C> unterstützen | Should | v0.2 |

### FR-02: <Feature-Bereich 2 — z.B. Data Management>

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-02.1 | | | |
| FR-02.2 | | | |

### FR-03: <Feature-Bereich 3 — z.B. Integration>

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-03.1 | | | |

### FR-04: <Feature-Bereich 4 — z.B. Configuration>

| ID | Anforderung | Priorität | Release |
|----|-------------|-----------|---------|
| FR-04.1 | | | |

> Weitere FR-Bereiche nach Bedarf ergänzen.
> Empfohlene Kategorien je nach Projekttyp:
> - **MCP Server**: Tools, Resources, Sampling, Notifications, Transport
> - **REST API**: Endpoints, Auth, Pagination, Webhooks
> - **CLI Tool**: Commands, Flags, Output Formats, Config
> - **Library**: Public API, Error Handling, Extensibility

---

## 2. Non-Functional Requirements (NFRs)

> Jedes NFR definiert eine Qualitätsanforderung mit messbarer Metrik.

### NFR-01: Security

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-01.1 | Alle Eingaben MÜSSEN validiert werden | 100% Input-Validierung |
| NFR-01.2 | Keine bekannten Vulnerabilities in Dependencies | pip-audit / dotnet audit / cargo audit: 0 Findings |
| NFR-01.3 | Semgrep MUSS vor jedem Release bestehen | 0 offene Security-Findings |
| NFR-01.4 | <Projektspezifisch: z.B. Secrets Management> | |

### NFR-02: Performance

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-02.1 | <Hot Path A> SOLL < <X>ms dauern | Benchmark-verifiziert |
| NFR-02.2 | <Hot Path B> SOLL < <Y>ms dauern | Benchmark-verifiziert |
| NFR-02.3 | Speicherverbrauch SOLL < <Z> MB im Normalbetrieb | Profiler-verifiziert |

### NFR-03: Zuverlässigkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-03.1 | Fehler DÜRFEN den Prozess NICHT zum Absturz bringen | Graceful Degradation |
| NFR-03.2 | <z.B. Datenintegrität bei Absturz> | |
| NFR-03.3 | <z.B. Retry-Strategie für externe Abhängigkeiten> | |

### NFR-04: Testbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-04.1 | Unit Tests MÜSSEN TDD-konform geschrieben werden | Red → Green → Refactor |
| NFR-04.2 | Code Coverage MUSS gemessen werden | ≥ <Ziel>% |
| NFR-04.3 | Mutation Testing MUSS durchgeführt werden | Score ≥ <Ziel>% |
| NFR-04.4 | Architekturregeln MÜSSEN als ausführbare Tests existieren | 0 Verletzungen |
| NFR-04.5 | Property-Based Tests MÜSSEN für Roundtrips/Invarianten existieren | Alle kritischen Pfade |

### NFR-05: Wartbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-05.1 | Code MUSS alle Linter-Prüfungen bestehen | 0 Findings |
| NFR-05.2 | Type Checking MUSS im strikten Modus bestehen | 0 Errors |
| NFR-05.3 | Module/Klassen SOLLEN < 300 Zeilen sein | Ausnahmen dokumentiert |
| NFR-05.4 | Funktionen/Methoden SOLLEN < 30 Zeilen sein | Ausnahmen dokumentiert |
| NFR-05.5 | Zirkuläre Abhängigkeiten DÜRFEN NICHT existieren | Architektur-Test-verifiziert |
| NFR-05.6 | Öffentliche APIs MÜSSEN dokumentiert sein | 100% Docstrings/Kommentare |

### NFR-06: Kompatibilität

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-06.1 | Das System MUSS auf <primäre Plattform> lauffähig sein | CI-verifiziert |
| NFR-06.2 | Das System SOLL auf <sekundäre Plattformen> lauffähig sein | Best-Effort |

### NFR-07: Konfigurierbarkeit

| ID | Anforderung | Metrik |
|----|-------------|--------|
| NFR-07.1 | Alle Limits MÜSSEN konfigurierbar sein mit sinnvollen Defaults | Kein Hardcoded Limit |
| NFR-07.2 | Konfigurationsfehler MÜSSEN beim Start erkannt werden (Fail-Fast) | Validierung beim Startup |

> Weitere NFR-Kategorien nach Bedarf:
> - **Skalierbarkeit**: Throughput, Concurrent Users
> - **Verfügbarkeit**: Uptime, MTTR
> - **Beobachtbarkeit**: Logging, Metrics, Tracing
> - **Internationalisierung**: i18n, l10n
> - **Barrierefreiheit**: a11y (bei UI-Projekten)

---

## 3. Interface-Spezifikationen

> Beschreibt die öffentlichen Schnittstellen (APIs, CLIs, Interfaces).
> Für jedes Interface: Name, Methoden/Endpoints, Parameter, Rückgabewerte, Fehler.

### 3.1 <Interface/API 1 — z.B. Core Service Interface>

**Typ:** <z.B. Python ABC, C# Interface, Rust Trait, REST Endpoint>
**Verantwortung:** <Was abstrahiert dieses Interface?>

```
<Methode/Endpoint-Signatur>
  Parameter: <Name: Typ — Beschreibung>
  Returns: <Rückgabetyp — Beschreibung>
  Errors/Exceptions: <Welche Fehler können auftreten?>
```

```
<Weitere Methoden...>
```

### 3.2 <Interface/API 2>

**Typ:**
**Verantwortung:**

```
<Signaturen>
```

### 3.3 <Interface/API 3>

**Typ:**
**Verantwortung:**

```
<Signaturen>
```

> Weitere Interfaces nach Bedarf ergänzen.
> Empfehlung: Mindestens ein Interface pro Schicht/Service.

---

## 4. Datenmodelle

> Beschreibt die zentralen Datenstrukturen des Systems.

### 4.1 <Modell 1 — z.B. Core Entity>

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| <field_name> | <type> | <Beschreibung> | <z.B. required, max_length=255> |
| | | | |

### 4.2 <Modell 2>

| Feld | Typ | Beschreibung | Validierung |
|------|-----|-------------|-------------|
| | | | |

> Für komplexe Modelle: Beziehungsdiagramm ergänzen.

---

## 5. Datenflüsse

> Beschreibt den Ablauf für die wichtigsten Use Cases.

### 5.1 <Hauptfluss 1 — z.B. Standard-Request-Verarbeitung>

```
1. <Eingang: z.B. Client sendet Request>
2. <Validierung: z.B. Input-Validierung>
3. <Verarbeitung: z.B. Business Logic>
4. <Persistierung: z.B. Daten speichern>
5. <Antwort: z.B. Response zurücksenden>
```

### 5.2 <Hauptfluss 2 — z.B. Fehlerbehandlung>

```
1. <Fehler tritt auf in Schritt X>
2. <Error Handler fängt Fehler>
3. <Logging>
4. <Fehlerantwort an Client>
```

### 5.3 <Hauptfluss 3 — z.B. Batch-Verarbeitung>

```
1. <Batch empfangen>
2. <Für jedes Item: Validierung + Verarbeitung>
3. <Bei Fehler: Rollback / Skip / Abort>
4. <Ergebnis zurückgeben>
```

---

## 6. Fehlerbehandlung

> Definiert die Fehler-Hierarchie und Behandlungsstrategien.

### 6.1 Fehler-Kategorien

| Kategorie | Basis-Typ | HTTP/Exit-Code | Behandlung |
|-----------|-----------|----------------|-----------|
| Validierungsfehler | <z.B. ValueError> | 400 | Sofort zurückgeben |
| Nicht gefunden | <z.B. NotFoundError> | 404 | Sofort zurückgeben |
| Berechtigungsfehler | <z.B. PermissionError> | 403 | Loggen + zurückgeben |
| Infrastrukturfehler | <z.B. IOError> | 500 | Retry (falls idempotent) |
| Unerwartete Fehler | <z.B. Exception> | 500 | Loggen + Graceful Error |

### 6.2 Custom Exceptions/Errors

```
<Exception/Error-Hierarchie in Pseudocode>

BaseError
├── ValidationError
│   ├── InvalidInputError
│   └── SchemaViolationError
├── NotFoundError
├── PermissionError
└── InfrastructureError
    ├── DatabaseError
    └── ExternalServiceError
```

---

## 7. Sicherheitskonzept

| Maßnahme | Beschreibung | Verifizierung |
|----------|-------------|---------------|
| Input-Validierung | <Wie werden Eingaben validiert?> | Semgrep + Unit Tests |
| Secrets Management | <Wie werden Secrets gespeichert?> | <z.B. Env Vars, nie im Code> |
| Dependency Audit | <Wie werden Dependencies geprüft?> | pip-audit / dotnet audit / cargo audit |
| <Weitere> | | |

---

## 8. Deployment & Operations

### 8.1 Build-Artefakte

| Artefakt | Format | Ziel |
|----------|--------|------|
| <z.B. Binary> | <z.B. Single-File, Container> | <z.B. Production> |
| <z.B. Package> | <z.B. wheel, NuGet, crate> | <z.B. Distribution> |

### 8.2 Konfigurationsparameter

| Parameter | Default | Beschreibung | Typ |
|-----------|---------|-------------|-----|
| <param> | <default> | <Beschreibung> | <string/int/bool> |

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | <Datum> | <Name/Agent> | Initiale Version |
