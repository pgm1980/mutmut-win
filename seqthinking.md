# Sequential Thinking — Neue Mutationsoperatoren für mutmut-win v1.0.0

**Datum:** 2026-03-30
**Zweck:** Detailanalyse (15 Steps je Kandidat) für 7 neue Mutationsoperatoren,
inspiriert von Stryker.NET und cargo-mutants.

---

## Kandidat 1: Regex-Mutationen

**Empfehlung:** IMPLEMENTIEREN in v1.0.0 | **Score:** 27/30 | **Prioritat:** #1

**Konzept:** Regex-Pattern in `re.compile()`, `re.match()`, `re.search()` etc. werden intern mutiert: Quantifier (+, *, ?, {n}), Character-Classes (\d/\D, \w/\W), Anchors (^, $), Alternativen (a|b).

**Wert:** Regex ist die am schlechtesten getestete Code-Kategorie in den meisten Python-Projekten. Kein anderes Python-Mutation-Testing-Tool hat Regex-Mutationen — Alleinstellungsmerkmal.

**Implementierung:** ~200 LOC in neuem Modul `regex_mutation.py` + ~30 LOC in `node_mutation.py`. Pragmatischer String-Manipulations-Ansatz (kein voller Regex-Parser). Nur direkte `re.*()` Aufrufe, keine Datenfluss-Analyse.

**Mutationen pro Pattern:** 2-7 (Quantifier, Character-Classes, Anchors). Bei 20 Patterns: ~50-140 zusatzliche Mutanten.

**Risiken:** F-Strings und VERBOSE-Regex werden ubersprungen (v1.0.0 Scope). Max 5 Mutanten pro Pattern gegen Explosion. Alle generierten Regex werden via `re.compile()` auf Validitat gepruft.

**Scoring-Detail:**

| Dimension | Score |
|-----------|-------|
| Wert fur den User | 5/5 |
| Implementierungskomplexitat | 3/5 |
| Alleinstellungsmerkmal | 5/5 |
| False-Positive-Risiko | 4/5 |
| Performance-Impact | 5/5 |
| Architektur-Fit | 5/5 |

---

## Kandidat 2: Statement Removal

**Empfehlung:** IMPLEMENTIEREN in v1.0.0 (eingeschrankter Scope) | **Score:** 23/30 | **Prioritat:** #3

**Konzept:** Ganze Statements durch `pass` ersetzen. Pruft ob der Code uberhaupt notig ist (vs. bestehende Operatoren die prufen ob der Code korrekt ist). Zwei Sub-Operatoren: Void-Call Removal (`foo()` -> `pass`) und Raise Removal (`raise X` -> `pass`).

**Wert:** Findet untestete Seiteneffekte (`cache.invalidate()`, `db.commit()`) und fehlende Fehlerfall-Tests (`raise ValueError` -> `pass` uberlebt = Fehlerfall nicht getestet).

**Scope-Einschrankung v1.0.0:**
- NUR void function calls (Ruckgabewert ignoriert) + raise Statements
- NICHT: Zuweisungen (bereits durch operator_assignment), Imports, Definitionen
- NICHT: Block Removal (if/for/try -> pass) = v1.1+ Feature
- Exclusion-Liste: print, logger.*, logging.*, warnings.warn, typing.*

**Mutanten-Anstieg:** +20-45% (200-500 zusatzliche bei 100 Funktionen). Akzeptabel.

**Architektur:** Neuer Statement-Level-Mutations-Typ auf `cst.SimpleStatementLine`. Passt in bestehende `mutation_operators` Liste und `deep_replace` Mechanik ohne Refactoring.

**Scoring-Detail:**

| Dimension | Score |
|-----------|-------|
| Wert fur den User | 5/5 |
| Implementierungskomplexitat | 4/5 |
| Alleinstellungsmerkmal | 3/5 |
| False-Positive-Risiko | 3/5 |
| Performance-Impact | 4/5 |
| Architektur-Fit | 4/5 |

---

## Kandidat 3: Return Value Replacement

**Empfehlung:** IMPLEMENTIEREN in v1.0.0 | **Score:** 25/30 | **Prioritat:** #2

**Konzept:** `return complex_expression()` -> `return None` fur non-literal Returns. Bestehende Operatoren decken bereits Literals ab (Zahlen +1, Booleans flip, Strings XX). Die Lucke: Ruckgabewerte die Funktionsaufrufe, Comprehensions oder Attribute-Zugriffe sind.

**Implementierung:** ~20 LOC. Neuer Operator auf `cst.Return`. Uberspringt Literals (bereits abgedeckt). Ersetzt alles andere durch `None`.

**v1.0.0 Scope:** `return expr` -> `return None` (fur non-literal expr).
**v1.1 Scope:** Type-Hint-basierte Defaults (-> list -> return [], -> dict -> return {}, etc.)

**Scoring:** Wert 4/5, Komplexitat 5/5, USP 3/5, FP 4/5, Perf 4/5, Architektur 5/5

---

## Kandidat 4: Conditional Expression (Ternary)

**Empfehlung:** IMPLEMENTIEREN in v1.0.0 | **Score:** 25/30 | **Prioritat:** #4

**Konzept:** `x if condition else y` -> `x` (immer true-Branch) oder `y` (immer false-Branch). Entfernt die Entscheidung komplett statt sie umzukehren (orthogonal zu Boolean-Mutations).

**Implementierung:** ~10 LOC. Operator auf `cst.IfExp`. Zwei Mutanten pro Ternary.

**False Positives:** Sehr niedrig. Wenn eine Seite uberlebt, wird dieser Pfad nie getestet.

**Scoring:** Wert 4/5, Komplexitat 5/5, USP 3/5, FP 4/5, Perf 4/5, Architektur 5/5

---

## Kandidat 5: Null-Coalescing / or-Default

**Empfehlung:** IMPLEMENTIEREN in v1.0.0 (eingeschrankt) | **Score:** 21/30 | **Prioritat:** #6

**Konzept:** `x or default` -> `x` (Fallback entfernen) oder `default` (immer Fallback). Python-Idiom fur Null-Coalescing.

**Einschrankung:** NUR in Zuweisungskontexten (`val = x or default`), NICHT in if-Bedingungen (`if a or b` -> hohe False-Positive-Rate da bestehender or->and Operator das besser abdeckt).

**Implementierung:** ~30 LOC. Operator auf `cst.BooleanOperation` mit Kontext-Prufung (Zuweisung).

**Scoring:** Wert 3/5, Komplexitat 4/5, USP 3/5, FP 2/5, Perf 5/5, Architektur 4/5

---

## Kandidat 6: Collection-Methoden

**Empfehlung:** IMPLEMENTIEREN in v1.0.0 | **Score:** 23/30 | **Prioritat:** #5

**Konzept:** Collection-Operationen neutralisieren (Stryker LINQ-Aquivalent):
- `sorted(items)` -> `items` (Sortierung entfernen)
- `reversed(items)` -> `items` (Umkehrung entfernen)
- `min(a,b)` / `max(a,b)` -> siehe Math-Methoden
- `[x for x in items if pred(x)]` -> `[x for x in items]` (Comprehension-Filter entfernen)

**Zwei Sub-Operatoren:**
1. Builtin-Call-Neutralisierung (sorted, reversed -> Argument unverandert)
2. Comprehension-Filter-Entfernung (if-Klausel in ListComp/SetComp/GeneratorExp)

**Implementierung:** ~60 LOC fur beide Sub-Operatoren.

**Scoring:** Wert 4/5, Komplexitat 3/5, USP 4/5, FP 4/5, Perf 4/5, Architektur 4/5

---

## Kandidat 7: Math-Methoden

**Empfehlung:** IMPLEMENTIEREN in v1.0.0 | **Score:** 26/30 | **Prioritat:** #2 (gleichauf mit Return Value)

**Konzept:** Mathematische Funktionen durch Gegenstucke oder Neutralwerte ersetzen:

| Original | Mutation(en) |
|----------|-------------|
| `abs(x)` | `x`, `-abs(x)` |
| `math.ceil(x)` | `math.floor(x)` |
| `math.floor(x)` | `math.ceil(x)` |
| `min(a, b)` | `max(a, b)` |
| `max(a, b)` | `min(a, b)` |
| `round(x)` | `x` |
| `sum(iterable)` | `0` |
| `pow(x, y)` | `x` |
| `math.sqrt(x)` | `x` |

**Implementierung:** ~50-60 LOC. Paarweise Swaps + Neutralisierungen. Erkennt sowohl `abs()` (Name) als auch `math.ceil()` (Attribute).

**False Positives:** Niedrig. `min(a,b)` -> `max(a,b)` uberlebt nur wenn Grenzfalle fehlen.

**Scoring:** Wert 4/5, Komplexitat 4/5, USP 4/5, FP 4/5, Perf 5/5, Architektur 5/5

---

## Gesamtranking v1.0.0

| # | Kandidat | Score | LOC | Prioritat | USP |
|---|----------|-------|-----|-----------|-----|
| 1 | **Regex-Mutationen** | 27/30 | ~200 | Hochste | Kein Python-Tool hat das |
| 2 | **Math-Methoden** | 26/30 | ~60 | Hoch | Stryker-inspiriert |
| 3 | **Return Value Replacement** | 25/30 | ~20 | Hoch | Sehr einfach, hoher Wert |
| 4 | **Conditional Expression** | 25/30 | ~10 | Mittel | Stryker-inspiriert |
| 5 | **Statement Removal** | 23/30 | ~80 | Mittel | Qualitativ besser als Cosmic Ray |
| 6 | **Collection-Methoden** | 23/30 | ~60 | Mittel | LINQ-Aquivalent |
| 7 | **or-Default** | 21/30 | ~30 | Niedrig | Hohe FP-Rate |

**Gesamt neue LOC:** ~460 (alle 7 Operatoren)
**Gesamt neue Mutanten:** +40-80% gegenuber aktuellem Stand

**Empfehlung fur v1.0.0:** Alle 7 implementieren. Die Gesamt-LOC (~460) sind moderat, und jeder Operator hat einen klaren Mehrwert. Die or-Default-Mutation wird auf Zuweisungskontexte eingeschrankt um die FP-Rate zu kontrollieren.

