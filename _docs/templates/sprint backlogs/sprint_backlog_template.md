# Sprint Backlog — Sprint <N>

**Projekt:** <Projektname>
**Sprint:** <N> von <Total>
**Zeitraum:** <Start-Datum> – <End-Datum>
**Sprint-Ziel:** <1 Satz: Was wird in diesem Sprint erreicht?>
**Epic(s):** <Welche Epics werden bearbeitet?>
**Branch:** `feature/<issue-nr>-<kurzbeschreibung>`

---

## Sprint Planning

### Kapazität

| Ressource | Verfügbarkeit | Story Points |
|-----------|--------------|-------------|
| <z.B. Claude Code Agent> | <z.B. 100%> | <SP Budget> |

### Ausgewählte Items

| # | Issue | Typ | Titel | SP | Priorität | Status |
|---|-------|-----|-------|----|-----------|--------|
| 1 | #<Nr> | Story | <Titel> | <SP> | Must | 🔲 Open |
| 2 | #<Nr> | Story | <Titel> | <SP> | Must | 🔲 Open |
| 3 | #<Nr> | Task | <Titel> | <SP> | Must | 🔲 Open |
| 4 | #<Nr> | Task | <Titel> | <SP> | Should | 🔲 Open |

**Gesamt:** <Total SP>

---

## Task Breakdown

> Jedes Sprint-Item wird in konkrete, umsetzbare Tasks zerlegt.

### Item 1: <Titel> (#<Nr>)

**User Story:** Als <Rolle> will ich <Fähigkeit>, damit <Nutzen>.

**Acceptance Criteria:**
- [ ] <Kriterium 1>
- [ ] <Kriterium 2>
- [ ] <Kriterium 3>

**Tasks:**

| Task | Beschreibung | Geschätzt | Status |
|------|-------------|-----------|--------|
| 1.1 | <z.B. Interface definieren> | <z.B. 15min> | 🔲 |
| 1.2 | <z.B. Tests schreiben (TDD Red)> | | 🔲 |
| 1.3 | <z.B. Implementierung (TDD Green)> | | 🔲 |
| 1.4 | <z.B. Refactoring (TDD Refactor)> | | 🔲 |
| 1.5 | <z.B. Integration Tests> | | 🔲 |

---

### Item 2: <Titel> (#<Nr>)

**User Story:**

**Acceptance Criteria:**
- [ ]

**Tasks:**

| Task | Beschreibung | Geschätzt | Status |
|------|-------------|-----------|--------|
| 2.1 | | | 🔲 |
| 2.2 | | | 🔲 |

---

> Weitere Items nach Bedarf.

---

## Sprint Execution Log

> Chronologisches Protokoll der Sprint-Durchführung. Wird während des Sprints befüllt.

| Zeitpunkt | Aktion | Ergebnis | Notizen |
|-----------|--------|----------|---------|
| <Datum/Uhrzeit> | Sprint gestartet | Branch erstellt | |
| | Item 1 — TDD Red | Tests geschrieben, <N> Tests failing | |
| | Item 1 — TDD Green | Implementierung, alle Tests grün | |
| | Item 1 — Refactor | Code vereinfacht | |
| | Quality Gate | Build ✅ Tests ✅ Lint ✅ Types ✅ | |
| | Commit | `feat(scope): description` | |

---

## Quality-Gate Ergebnisse

> Wird am Ende des Sprints ausgefüllt. Alle Gates müssen ✅ sein für "Done".

| Gate | Befehl | Ergebnis | Status |
|------|--------|----------|--------|
| Build | `<build-command>` | 0 Warnings, 0 Errors | ⬜ |
| Tests | `<test-command>` | <N>/<N> grün | ⬜ |
| Coverage | `<coverage-command>` | <X>% Line Coverage | ⬜ |
| Linting | `<lint-command>` | 0 Findings | ⬜ |
| Type Check | `<typecheck-command>` | 0 Errors | ⬜ |
| Security | `semgrep scan --config auto .` | 0 Findings | ⬜ |
| Dependency Audit | `<audit-command>` | 0 Advisories | ⬜ |
| Architecture | `<arch-test-command>` | 0 Verletzungen | ⬜ |
| Mutation Testing | `<mutation-command>` | Score ≥ <Ziel>% | ⬜ |

---

## Sprint Review

### Ergebnis

| Metrik | Geplant | Erreicht |
|--------|---------|----------|
| Story Points | <Geplant> | <Erreicht> |
| Items | <Geplant> | <Abgeschlossen> |
| Velocity | | <SP/Sprint> |

### Demo-Zusammenfassung

<Was wurde implementiert? Was kann gezeigt werden?>

### Nicht abgeschlossene Items

| Issue | Grund | Aktion |
|-------|-------|--------|
| #<Nr> | <z.B. Komplexer als geschätzt> | <z.B. → Sprint N+1> |

---

## Sprint Retrospective

### Was lief gut?
- <Punkt 1>
- <Punkt 2>

### Was kann verbessert werden?
- <Punkt 1>
- <Punkt 2>

### Aktionspunkte für nächsten Sprint
- [ ] <Aktion 1>
- [ ] <Aktion 2>

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | <Datum> | <Name/Agent> | Sprint Planning |
| 0.2.0 | <Datum> | <Name/Agent> | Sprint Review + Retro |
