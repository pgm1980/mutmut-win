# Sprint Backlog — Sprint 15

**Projekt:** mutmut-win
**Sprint:** 15 von 20
**Sprint-Ziel:** Math-Methoden-Mutationen (ceil↔floor, min↔max, abs→x, sum→0)
**Epic(s):** Epic 13
**Branch:** `feature/56-math-methods`

---

## Ausgewählte Items

| # | Issue | Typ | Titel | SP | Priorität | Status |
|---|-------|-----|-------|----|-----------|--------|
| 1 | #56 | Story | Math-Methoden-Mutationen | 3 | Must | ✅ Done |

## Task Breakdown

### Item 1: Math-Methoden (#56)

**User Story:** Als Entwickler will ich dass mathematische Funktionen durch Gegenstücke/Neutralwerte ersetzt werden, damit ich erkennen kann ob Edge Cases wie min/max-Vertauschung getestet sind.

**Acceptance Criteria:**
- [x] `math.ceil(x)` ↔ `math.floor(x)`
- [x] `min(a,b)` ↔ `max(a,b)`
- [x] `abs(x)` → `x`
- [x] `round(x)` → `x`
- [x] `sum(iterable)` → `0`
- [x] Erkennt sowohl `abs()` (Name) als auch `math.ceil()` (Attribute)
- [x] Unit Tests
- [x] Ruff 0, mypy 0, alle Tests grün

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | `operator_math_methods()` in node_mutation.py | ✅ |
| 1.2 | Paarweise Swaps (ceil/floor, min/max) | ✅ |
| 1.3 | Neutralisierungen (abs, round, sum) | ✅ |
| 1.4 | Unit Tests | ✅ |
| 1.5 | Quality Gates | ✅ |
