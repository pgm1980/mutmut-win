# Entwicklungsprozess — Scrum-basiert

## Übersicht

```
Sprint 0: [Brainstorming + Innovation → Architecture → Software Design]
                ↓
Product Backlog: [DoD, Epics, Features, User Stories, Acceptance Criteria → GitHub Issues + Milestones]
                ↓
Sprint 1–N: [Sprint Planning → Implementation (vertikal/E2E) → Unit Tests + Integrationstests → Increment, GitHub Issues schließen]
                ↓
Epic abgeschlossen: [Milestone erreicht → GitHub Tag]
```

## Zuordnungsmodell

| Scrum-Artefakt     | GitHub-Konstrukt    | Bedeutung                              |
|--------------------|---------------------|----------------------------------------|
| Epic               | Milestone           | MVP / Meilenstein, enthält N Sprints   |
| Feature            | Issue (Sammlung)    | Gruppe zusammengehöriger User Stories  |
| User Story         | Issue               | Einzelne implementierbare Einheit      |
| Sprint Increment   | `feature/*`-Branch  | Funktionsfähiges, testbares Ergebnis   |

---

## Sprint 0 — Architektur & Softwaredesign

**Ziel**: Problemraum verstehen, Innovationen erarbeiten, Architekturentscheidungen treffen, Anforderungen spezifizieren.

**Phasen**:
1. **Brainstorming & Innovation**: Ideen und Innovationen erarbeiten
2. **Architektur**: ADRs (Architecture Decision Records) definieren
3. **Softwaredesign**: FRs (Functional Requirements) und NFRs (Non-Functional Requirements) spezifizieren

**Ergebnisse**:
- `architecture_specification.md` — enthält alle ADRs
- `software_design_specification.md` — enthält alle FRs und NFRs
- Erkenntnisse aus der Brainstorming-Phase fließen in beide Dokumente ein

**Skill-Zuordnung**:

| Situation                                         | Skill                                                                         |
|---------------------------------------------------|-------------------------------------------------------------------------------|
| Ideenfindung, Konzeptentwicklung, Innovation      | `brainstorming`                                                               |
| Architekturentscheidungen, technische Machbarkeit | `feature-development` (Phase 2+4: Codebase Exploration + Architecture Design) |
| Mehrere unabhängige Bereiche explorieren          | `dispatching-parallel-agents` (je ein Agent pro Bereich)                      |
| Komplexe Problemanalyse, Abwägungen               | Sequential Thinking                                                           |
| Aktuelle Framework-/Library-Dokumentation         | Context7                                                                      |

**Definition of Done**:
- [ ] Brainstorming abgeschlossen, Innovationen dokumentiert
- [ ] `architecture_specification.md` liegt vor mit allen ADRs
- [ ] `software_design_specification.md` liegt vor mit allen FRs und NFRs
- [ ] Architektur und Design mit User abgestimmt

---

## Nach Sprint 0 / Vor Sprint 1 — Product Backlog

**Ziel**: Allumfassendes Product Backlog erstellen und in GitHub abbilden.

**Inhalte**:
- **Definition of Done** (übergreifend, gilt für alle Sprints)
- **Epics** mit Acceptance Criteria
- **Features** mit Acceptance Criteria (jeweils Sammlung von User Stories)
- **User Stories** mit spezifischen **Acceptance Criteria**

**User-Story-Template**:
```
Als [ROLLE]
möchte ich [FUNKTIONALITÄT]
damit [NUTZEN]

Akzeptanzkriterien:
- [ ] [Kriterium 1 — beobachtbares Verhalten]
- [ ] [Kriterium 2 — Grenzfall]
- [ ] [Kriterium 3 — Fehlerfall]
```

**Ergebnisse**:
- `product_backlog.md`  — enthält DoD sowie alle Epics, Features, User Stories und Acceptance Criteria je User Story

**GitHub-Erstellung**:
- Jede User Story → GitHub Issue
- Jedes Feature → GitHub Issue (verweist auf zugehörige User Story Issues)
- Jedes Epic → GitHub Milestone

**Skill-Zuordnung**:

| Situation                         | Skill                         |
------------------------------------|-------------------------------|
| Backlog-Struktur planen           | `writing-plans`               |
| Teilbereiche parallel ausarbeiten | `dispatching-parallel-agents` |

---

## Sprint 1–N — Implementierung

**Ziel**: Sprint Backlog erstellen, Code schreiben, Tests schreiben, lauffähiges Increment produzieren.

**Ablauf**:
1. **Sprint Planning**: Sprint Backlog aus Product Backlog ableiten, PBIs auf Tasks runterbrechen
2. **Implementierung**: Vertikal / End-to-End — jeder Sprint produziert ein funktionsfähiges, testbares Increment
3. **Testing**: Unit Tests + Integrationstests am Ende jedes Sprints
4. **Increment**: Entspricht einem Feature im Product Backlog und einem `feature/*`-Branch in GitHub

**Ergebnisse**:
- `sprint_backlog.md`  — alle Product Backlog Items (PBIs), die in dem jeweiligen Sprint implementiert werden
- Funktionsfähiges, fehlerfreies Increment

**Skill-Zuordnung**:

| Situation                               | Skill                                                               |
|-----------------------------------------|---------------------------------------------------------------------|
| Sprint-Planung, Task-Breakdown          | `writing-plans`                                                     |
| Plan aus anderer Session ausführen      | `executing-plans` (lädt Plan, Batches mit Review-Checkpoints)       |
| **Immer** — Code schreiben              | `test-driven-development` (Red → Green → Refactor, keine Ausnahmen) |
| MCP-Server-spezifische Entwicklung      | `mcp-builder`                                                       |
| Feature-Entwicklung mit Discovery       | `feature-development`                                               |
| Unabhängige Tasks parallel bearbeiten   | `subagent-driven-development` (1 Agent pro Task, 2-Stage Review)    |
| Bug oder unerwartetes Verhalten         | `systematic-debugging` (4-Phasen Root-Cause-Analyse)                |
| Behauptung "fertig" oder "funktioniert" | `verification-before-completion` (Evidence before assertions)       |

**Definition of Done** (pro Sprint):
- [ ] Alle Tasks des Sprints implementiert
- [ ] Alle Tests grün (Unit + Integration)
- [ ] `verification-before-completion` ausgeführt — Evidence liegt vor
- [ ] Code kompiliert ohne Fehler und Warnungen (TreatWarningsAsErrors)
- [ ] Semgrep-Scan bestanden (keine offenen Security-Findings)
- [ ] Increment ist lauffähig
- [ ] Conventional Commit Messages verwendet

---

## Sprint 1–N (parallel): Review & Sprint-Abschluss

**Skill-Zuordnung**:

| Situation                            | Skill                                                                       |
|--------------------------------------|-----------------------------------------------------------------------------|
| Schneller Sanity-Check nach Task     | `requesting-code-review` (1 Agent, schnell)                                 |
| Umfassendes Pre-Merge Review         | `pr-review` (6 spezialisierte Agents)                                       |
| Review-Feedback erhalten             | `receiving-code-review` (technische Verifikation, kein blindes Akzeptieren) |
| Sprint-Abschluss: Branch integrieren | `finishing-a-development-branch` (Merge / PR / Keep / Discard)              |

**Test-Pyramide**:

| Ebene                 | Wann                         | Verantwortung              |
|-----------------------|------------------------------|----------------------------|
| **Unit Tests**        | Während Implementation (TDD) | `test-driven-development`  |
| **Integration Tests** | Nach Feature-Completion      | Sprint DoD                 |
| **E2E Tests**         | Nach Increment               | Review-Phase               |

**Definition of Done** (Review):
- [ ] Code-Review bestanden (`requesting-code-review` oder `pr-review`)
- [ ] Review-Feedback verarbeitet (`receiving-code-review`)
- [ ] Branch integriert (`finishing-a-development-branch`)
- [ ] Bei Epic-Abschluss: GitHub Tag gesetzt

---

## Releases & Tagging

- Ein **Epic** umfasst eine bestimmte Anzahl an Sprints
- Ein **Epic** entspricht einem **MVP**
- Nach Erreichen eines **Milestones** → GitHub **Tag** erstellen (SemVer)