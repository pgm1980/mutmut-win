# Sprint Backlog — Sprint 14

**Projekt:** mutmut-win
**Sprint:** 14 von 20
**Zeitraum:** 2026-03-30 – 2026-03-30
**Sprint-Ziel:** Regex-Mutationen implementieren — Alleinstellungsmerkmal (kein Python-Tool hat das)
**Epic(s):** Epic 13 (Erweiterte Mutationsoperatoren)
**Branch:** `feature/55-regex-mutations`

---

## Sprint Planning

### Kapazität

| Ressource | Verfügbarkeit | Story Points |
|-----------|--------------|-------------|
| Claude Code Agent (Opus 4.6) | 100% | 8 |

### Ausgewählte Items

| # | Issue | Typ | Titel | SP | Priorität | Status |
|---|-------|-----|-------|----|-----------|--------|
| 1 | #55 | Story | Regex-Mutationen (Quantifier, CharClass, Anchors) | 8 | Must | 🔲 Open |

**Gesamt:** 8 SP

---

## Task Breakdown

### Item 1: Regex-Mutationen (#55)

**User Story:** Als Entwickler will ich dass Regex-Pattern in `re.*()` Aufrufen mutiert werden, damit ich erkennen kann ob meine Tests die Regex-Logik ausreichend abdecken.

**Acceptance Criteria:**
- [ ] Quantifier-Mutationen: `\d+` → `\d`, `\d*` → `\d+`, `{3}` → `{2}`/`{4}`
- [ ] Character-Class-Mutationen: `\d` → `\D`, `\w` → `\W`, `\s` → `\S`
- [ ] Anchor-Mutationen: `^pattern` → `pattern`, `pattern$` → `pattern`
- [ ] Erkennung von `re.compile()`, `re.match()`, `re.search()`, `re.findall()`, `re.sub()`, `re.split()`, `re.fullmatch()`
- [ ] Alle generierten Regex via `re.compile()` auf Validität geprüft (unviable = gefiltert)
- [ ] F-Strings und VERBOSE-Regex werden übersprungen
- [ ] Max 5 Mutanten pro Pattern (gegen Explosion)
- [ ] Unit Tests + hypothesis Property-Test (valid regex in → valid/filtered regex out)
- [ ] Ruff 0 Findings, mypy 0 Errors
- [ ] mutmut-win run auf eigenem Code (Dogfooding)

**Tasks:**

| Task | Beschreibung | Geschätzt | Status |
|------|-------------|-----------|--------|
| 1.1 | `regex_mutation.py` — `mutate_regex_pattern()` Kernfunktion | 30min | 🔲 |
| 1.2 | `_mutate_quantifiers()` — +, *, ?, {n}, {n,m} | 20min | 🔲 |
| 1.3 | `_mutate_char_classes()` — \d/\D, \w/\W, \s/\S | 15min | 🔲 |
| 1.4 | `_mutate_anchors()` — ^, $, \b | 10min | 🔲 |
| 1.5 | `_validate_regex()` — re.compile() Viability-Check | 10min | 🔲 |
| 1.6 | `operator_regex()` in node_mutation.py — CST-Integration | 20min | 🔲 |
| 1.7 | Erkennung von re.*() Aufrufen (re.compile, re.match, etc.) | 15min | 🔲 |
| 1.8 | Unit Tests: Quantifier, CharClass, Anchor, Viability | 30min | 🔲 |
| 1.9 | hypothesis Property-Test: valid regex → valid/filtered output | 15min | 🔲 |
| 1.10 | Integration Test: re.compile() in Code → Mutanten generiert | 15min | 🔲 |
| 1.11 | Ruff + mypy + pytest Quality Gates | 10min | 🔲 |
| 1.12 | Dogfooding: mutmut-win run auf regex_mutation.py | 15min | 🔲 |

---

## Sprint Execution Log

| Zeitpunkt | Aktion | Ergebnis | Notizen |
|-----------|--------|----------|---------|
| | Sprint gestartet | Branch feature/55-regex-mutations erstellt | |

---

## Quality-Gate Ergebnisse

| Gate | Befehl | Ergebnis | Status |
|------|--------|----------|--------|
| Tests | `uv run pytest` | | ⬜ |
| Coverage | `uv run pytest --cov=src` | | ⬜ |
| Linting | `uv run ruff check .` | | ⬜ |
| Type Check | `uv run mypy src/` | | ⬜ |
| Security | `semgrep scan --config auto .` | | ⬜ |
| Architecture | `uv run lint-imports` | | ⬜ |
| Mutation Testing | `uv run mutmut-win run --paths-to-mutate src/mutmut_win/regex_mutation.py` | | ⬜ |
