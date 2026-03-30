# Product Backlog — <Projektname>

**Version:** 0.1.0
**Datum:** <YYYY-MM-DD>
**Status:** Draft | Active | Frozen

---

## Release-Übersicht

| Release | Codename | Sprints | Status | Highlights |
|---------|----------|---------|--------|------------|
| v0.1.0 | | Sprint 1–N | Planned | <MVP / Kernfunktionalität> |
| v0.2.0 | | Sprint N–M | Planned | <Feature Set 2> |
| v1.0.0 | | Sprint M–X | Planned | <Production Ready> |

---

## Definition of Done (DoD)

> Wird projektspezifisch angepasst. Alle Punkte müssen erfüllt sein bevor ein Sprint/Feature als "Done" gilt.

### Sprachunabhängige Quality-Gates

- [ ] **Build**: 0 Warnings, 0 Errors
- [ ] **Tests**: Alle Unit + Integration Tests grün
- [ ] **Coverage**: ≥ <Ziel>% Line Coverage
- [ ] **Linting**: 0 Findings (alle Regeln aktiv)
- [ ] **Type Checking**: 0 Errors (strict mode)
- [ ] **Security Scan**: Semgrep — 0 offene Findings
- [ ] **Dependency Audit**: 0 bekannte Vulnerabilities
- [ ] **Architecture Tests**: 0 Schichtverletzungen
- [ ] **Property-Based Tests**: Roundtrips/Invarianten verifiziert
- [ ] **Mutation Testing**: Score ≥ <Ziel>% auf neuem/geändertem Code
- [ ] **Performance**: Benchmarks auf Hot Paths durchgeführt (falls relevant)

### E2E-Validierung (PFLICHT — NICHT VERHANDELBAR)

- [ ] **Echter E2E-Lauf**: Das Increment MUSS mindestens einmal auf einem echten Projekt (nicht gemockt!) End-to-End ausgeführt werden
- [ ] **Kein reines Unit-Test-Vertrauen**: Unit-Tests mit gemocktem subprocess, I/O oder externen Systemen decken KEINE Integrationsfehler auf (cwd, PYTHONPATH, sys.path, Dateipfade, Encoding, Prozess-Isolation). Der echte E2E-Lauf ist unverzichtbar und ersetzt keinen Unit-Test, sondern ergänzt ihn.
- [ ] **Ergebnis dokumentiert**: E2E-Testergebnis im Sprint-Backlog oder Protokoll-Datei festgehalten

> **Erfahrungswert:** 471 Unit-Tests, 3 Cross-Check-Audits, 12 Sprints — und ein kritischer Bug (subprocess ohne `cwd`, fehlendes `PYTHONPATH`) wurde erst beim ersten echten End-to-End-Lauf auf einem realen Projekt gefunden. Alle Unit-Tests hatten subprocess.run() gemockt und den realen Integrationspfad nie getestet.

### Prozess-Gates

- [ ] **Code Review**: Mindestens 1 Review (Agent oder Mensch) bestanden
- [ ] **MEMORY.md**: Projektgedächtnis aktualisiert
- [ ] **GitHub Issues**: Alle Sprint-Issues geschlossen
- [ ] **Commit, Push, Tag**: Conventional Commit, Branch pushed, ggf. Version-Tag

### Sprachspezifische Ergänzungen

> Hier die für die jeweilige Sprache spezifischen DoD-Punkte einfügen:

<!--
PYTHON:
- [ ] Ruff: `uv run ruff check .` — 0 Findings
- [ ] mypy: `uv run mypy src/` — 0 Errors (strict)
- [ ] pytest: `uv run pytest` — alle grün
- [ ] pytest-cov: `uv run pytest --cov=src` — ≥ 80%
- [ ] hypothesis: Property-Based Tests vorhanden
- [ ] mutmut: `uv run mutmut run` — Score ≥ 80%
- [ ] import-linter: `uv run lint-imports` — 0 Verletzungen
- [ ] pip-audit: `uv run pip-audit` — 0 Advisories

C#/.NET:
- [ ] dotnet build: 0 Warnings (TreatWarningsAsErrors)
- [ ] dotnet test: alle grün
- [ ] Coverlet: Coverage ≥ 80%
- [ ] FluentAssertions: kein Assert.Equal etc.
- [ ] ArchUnitNET: 0 Schichtverletzungen
- [ ] FsCheck: Property-Based Tests vorhanden
- [ ] Stryker.NET: Mutation Score ≥ 80%
- [ ] Semgrep: 0 Findings

JAVA/SCALA:
- [ ] Gradle/Maven build: 0 Warnings
- [ ] JUnit/ScalaTest: alle grün
- [ ] JaCoCo: Coverage ≥ 80%
- [ ] ArchUnit: 0 Schichtverletzungen
- [ ] jqwik/ScalaCheck: Property-Based Tests
- [ ] PIT: Mutation Score ≥ 80%
- [ ] SpotBugs/ErrorProne: 0 Findings

RUST:
- [ ] cargo build: 0 Warnings (deny warnings)
- [ ] cargo test: alle grün
- [ ] cargo tarpaulin: Coverage ≥ 80%
- [ ] cargo clippy: 0 Warnings (all lints)
- [ ] proptest: Property-Based Tests vorhanden
- [ ] cargo mutants: Mutation Score ≥ 80%
-->

---

## Epics und Sprint-Zuordnung

> Ein Epic gruppiert zusammengehörige Features. Jeder Sprint implementiert 1-3 Epics.

### Epic 1: <Epic-Name — z.B. "Core Infrastructure">

**Beschreibung:** <Was wird in diesem Epic erreicht?>
**Sprint:** <Sprint-Nummer(n)>
**Release:** <Ziel-Release>

| Issue | Typ | Titel | Priorität | Story Points | Status |
|-------|-----|-------|-----------|-------------|--------|
| #1 | Story | <Als X will ich Y, damit Z> | Must | <SP> | Open |
| #2 | Story | | Must | | Open |
| #3 | Task | <Technische Aufgabe> | Must | | Open |
| #4 | Bug | <Fehlerbeschreibung> | Must | | Open |

**Acceptance Criteria (Epic-Level):**
- [ ] <Kriterium 1>
- [ ] <Kriterium 2>

---

### Epic 2: <Epic-Name>

**Beschreibung:**
**Sprint:**
**Release:**

| Issue | Typ | Titel | Priorität | Story Points | Status |
|-------|-----|-------|-----------|-------------|--------|
| #N | Story | | | | Open |

**Acceptance Criteria:**
- [ ] <Kriterium>

---

> Weitere Epics nach Bedarf ergänzen.

---

## Priorisierung

> MoSCoW-Priorisierung für das gesamte Backlog:

| Priorität | Bedeutung | Anteil |
|-----------|-----------|--------|
| **Must** | Ohne diese Features ist das Release wertlos | ~60% |
| **Should** | Wichtig, aber das Release funktioniert ohne sie | ~20% |
| **Could** | Nice-to-have, wenn Zeit übrig | ~15% |
| **Won't** | Explizit ausgeschlossen für dieses Release | ~5% |

---

## Milestone-Zuordnung (GitHub)

| Milestone | Release | Epics | Issues | Status |
|-----------|---------|-------|--------|--------|
| <Milestone 1> | v0.1.0 | Epic 1–N | #1–#X | Open |
| <Milestone 2> | v0.2.0 | Epic N–M | #X–#Y | Open |

---

## Velocity Tracking

| Sprint | Geplant (SP) | Erledigt (SP) | Velocity | Notizen |
|--------|-------------|---------------|----------|---------|
| Sprint 1 | | | | |
| Sprint 2 | | | | |

---

## Änderungshistorie

| Version | Datum | Autor | Änderung |
|---------|-------|-------|----------|
| 0.1.0 | <Datum> | <Name/Agent> | Initiales Backlog |
