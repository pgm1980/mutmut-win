# Architecture Specification — <Projektname>

**Version:** 0.1.0
**Datum:** <YYYY-MM-DD>
**Status:** Draft | Review | Approved

---

## 1. Systemübersicht

**Kurzbeschreibung:** <1-2 Sätze: Was macht das System?>

**Architekturtyp:** <z.B. Layered Architecture, Hexagonal, Microservices, MCP Server, CLI Tool, REST API>


### 1.1 Kontextdiagramm

```
┌───────────────────────────────────────────────────┐
│                 Systemkontext                     │
│                                                   │
│  ┌──────────┐    ┌──────────────┐    ┌─────────┐  │
│  │ Akteur A │───→│  <System>    │───→│ Ext. B  │  │
│  └──────────┘    └──────────────┘    └─────────┘  │
│                         │                         │
│                         ▼                         │
│                  ┌──────────────┐                 │
│                  │ Ext. System C│                 │
│                  └──────────────┘                 │
└───────────────────────────────────────────────────┘
```

### 1.2 Qualitätsziele

| Priorität | Ziel | Maßnahme | Metrik |
|-----------|------|----------|--------|
| 1 | <z.B. Security> | <z.B. Input-Validierung auf allen Schnittstellen> | <z.B. 0 Semgrep Findings> |
| 2 | <z.B. Performance> | <z.B. Async I/O, Caching> | <z.B. p95 < 100ms> |
| 3 | <z.B. Testbarkeit> | <z.B. DI, Interface-basiert> | <z.B. Coverage > 80%> |
| 4 | <z.B. Wartbarkeit> | <z.B. Schichtentrennung> | <z.B. 0 Architekturverletzungen> |

### 1.3 Technologie-Stack

| Kategorie | Technologie | Version | Begründung |
|-----------|-------------|---------|------------|
| Runtime | <z.B. Python / .NET / JVM> | <Version> | <Begründung> |
| Framework | <z.B. FastMCP / ASP.NET / Spring> | <Version> | <Begründung> |
| Testing | <z.B. pytest / xUnit / JUnit> | <Version> | <Begründung> |
| Linting | <z.B. Ruff / Roslyn / Spotless> | <Version> | <Begründung> |
| Security | <z.B. Semgrep> | aktuell | Statische Analyse |

---

## 2. Architekturentscheidungen (ADRs)

> Jede signifikante Architekturentscheidung wird als ADR dokumentiert.
> Empfehlung: Mindestens ADRs für Architekturstil, Datenhaltung, Fehlerbehandlung,
> Testing-Strategie, Deployment-Strategie.

### ADR-001: <Titel der Entscheidung>

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Datum:** <YYYY-MM-DD>

#### Kontext

<Welches Problem oder welche Anforderung erfordert eine Entscheidung? Welche Kräfte wirken?>

#### Optionen

##### Option A: <Name>

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | Low / Medium / High |
| Kosten (Entwicklung + Betrieb) | <Bewertung> |
| Skalierbarkeit | <Bewertung> |
| Wartbarkeit | <Bewertung> |
| Ecosystem-Reife (Libraries, Docs, Community) | <Bewertung> |

**Vorteile:**
- <Vorteil 1>
- <Vorteil 2>

**Nachteile:**
- <Nachteil 1>
- <Nachteil 2>

##### Option B: <Name>

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | |
| Kosten (Entwicklung + Betrieb) | |
| Skalierbarkeit | |
| Wartbarkeit | |
| Ecosystem-Reife (Libraries, Docs, Community) | |

**Vorteile:**
-

**Nachteile:**
-

##### Option C: <Name> (optional)

<Gleiches Format>

#### Trade-off-Analyse

<Kernabwägungen zwischen den Optionen mit klarer Argumentation.
Welche Qualitätsziele (Sektion 1.2) werden durch welche Option besser/schlechter erfüllt?>

#### Entscheidung

<Welche Option wurde gewählt?>

#### Konsequenzen

- **Wird einfacher:** <Was wird durch diese Entscheidung einfacher?>
- **Wird schwieriger:** <Was wird durch diese Entscheidung schwieriger?>
- **Muss revisited werden:** <Welche Aspekte müssen später erneut bewertet werden?>

#### Action Items

- [ ] <Umsetzungsschritt 1>
- [ ] <Umsetzungsschritt 2>
- [ ] <Follow-up / Validierung>

---

### ADR-002: <Titel>

**Status:**
**Datum:**

#### Kontext

#### Optionen

##### Option A: <Name>

| Dimension | Bewertung |
|-----------|-----------|
| Komplexität | |
| Kosten (Entwicklung + Betrieb) | |
| Skalierbarkeit | |
| Wartbarkeit | |
| Ecosystem-Reife | |

**Vorteile:**
-

**Nachteile:**
-

##### Option B: <Name>

<Gleiches Format>

#### Trade-off-Analyse

#### Entscheidung

#### Konsequenzen

- **Wird einfacher:**
- **Wird schwieriger:**
- **Muss revisited werden:**

#### Action Items

- [ ]

> Weitere ADRs nach Bedarf ergänzen.

---

## 3. Komponentenstruktur

> Beschreibt die logischen Schichten/Module und ihre Verantwortlichkeiten.

### 3.1 Schichtenübersicht

```
┌─────────────────────────────────────────┐
│            Presentation / API            │  ← Externe Schnittstelle
├─────────────────────────────────────────┤
│            Application / Service         │  ← Orchestrierung, Use Cases
├─────────────────────────────────────────┤
│            Domain / Core                 │  ← Geschäftslogik, Modelle
├─────────────────────────────────────────┤
│            Infrastructure                │  ← DB, externe APIs, I/O
└─────────────────────────────────────────┘
```

### 3.2 <Schicht 1 — z.B. API Layer>

**Verantwortung:** <Was tut diese Schicht?>
**Enthält:** <Welche Module/Klassen/Dateien?>
**Abhängigkeiten:** <Welche anderen Schichten werden genutzt?>

### 3.3 <Schicht 2 — z.B. Service Layer>

**Verantwortung:**
**Enthält:**
**Abhängigkeiten:**

### 3.4 <Schicht 3 — z.B. Domain Layer>

**Verantwortung:**
**Enthält:**
**Abhängigkeiten:**

### 3.5 <Schicht 4 — z.B. Infrastructure Layer>

**Verantwortung:**
**Enthält:**
**Abhängigkeiten:**

---

## 4. Abhängigkeitsregeln

> Definiert welche Schicht auf welche andere zugreifen darf.

```
API → Service → Domain ← Infrastructure
                  ↑
                  │
          (Domain kennt keine
           äußeren Schichten)
```

| Von | Darf zugreifen auf | Darf NICHT zugreifen auf |
|-----|-------------------|-------------------------|
| API / Presentation | Service, Domain | Infrastructure (direkt) |
| Service / Application | Domain, Infrastructure (via Interfaces) | API |
| Domain / Core | Nichts (eigenständig) | Alle anderen Schichten |
| Infrastructure | Domain (implementiert Interfaces) | API, Service |

> Diese Regeln werden als ausführbare Tests durchgesetzt:
> - **Python**: import-linter Contracts
> - **C#**: ArchUnitNET Tests
> - **Java/Scala**: ArchUnit Tests
> - **Rust**: Module Visibility (`pub(crate)`, `pub(super)`)

---

## 5. Querschnittsthemen

### 5.1 Fehlerbehandlung

**Strategie:** <z.B. Exception Hierarchy, Result Types, Error Codes>

| Fehlertyp | Handling | Beispiel |
|-----------|----------|----------|
| Validierungsfehler | <z.B. Sofort zurückgeben, kein Retry> | <z.B. Ungültiger Input> |
| Infrastrukturfehler | <z.B. Retry mit Backoff> | <z.B. DB-Timeout> |
| Geschäftslogik-Fehler | <z.B. Domain Exception> | <z.B. Ungültiger Zustandsübergang> |
| Unerwartete Fehler | <z.B. Log + Graceful Degradation> | <z.B. NullReference> |

### 5.2 Logging

**Framework:** <z.B. Serilog, logging (stdlib), Log4j, tracing (Rust)>
**Strategie:** Strukturiertes Logging mit korrelierter Trace-ID.

| Level | Verwendung |
|-------|-----------|
| ERROR | Unerwartete Fehler, die manuelle Intervention erfordern |
| WARN | Erwartete Probleme, die automatisch behandelt werden |
| INFO | Geschäftsereignisse (Start, Stop, wichtige Operationen) |
| DEBUG | Technische Details für Entwickler |

### 5.3 Konfiguration

**Strategie:** <z.B. Hierarchisch: CLI > Env > Config-File > Defaults>

### 5.4 Security

**Strategie:** <z.B. Input-Validierung, Least Privilege, Encryption at Rest>

---

## 6. Deployment

### 6.1 Deployment-Modell

**Typ:** <z.B. Single Binary, Container, Package, MCP Server via stdio>

### 6.2 Plattform-Support

| Plattform | Support-Level | Besonderheiten |
|-----------|--------------|----------------|
| Windows | Primär / Sekundär | |
| Linux | Primär / Sekundär | |
| macOS | Primär / Sekundär | |

### 6.3 Build & Distribution

```bash
# Build
<build-command>

# Test
<test-command>

# Package/Publish
<publish-command>
```

---

## 7. Risiken und technische Schulden

| # | Risiko / Schuld | Impact | Mitigation | Status |
|---|----------------|--------|------------|--------|
| 1 | | High / Medium / Low | | Open / Mitigated |
| 2 | | | | |

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | <Datum> | <Name/Agent> | Initiale Version |
