# Sprint Backlog — Sprint 23 (v2.0.x Reliability Wave)

**Projekt:** mutmut-win
**Sprint:** 23
**Sprint-Ziel:** Drei kritische Bugs aus v2.0.4-Dogfooding fixen — `multi-line if/or SyntaxError`, `Hypothesis timeout vs. kill`, `default param trampoline equivalents`. Release als v2.2.0.
**Epic(s):** Epic 16 (v2.0.x Reliability — neu, retroaktiv im product_backlog ergänzen)
**Branch:** `fix/v2.2.0-reliability-wave`
**Zeitraum:** 2026-05-22 –
**Status:** 🔲 in progress

---

## Ausgewählte Items

| # | Issue | Typ | Titel | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----|-----------|-------------|--------|
| 1 | #70 | Bug | Default-Parameter trampoline equivalents (Option A: skip-the-mutation) | 3 | Must | 1 (einfachster Fix, Pattern aus Bug #4 bekannt) | 🔲 |
| 2 | #71 | Bug | Hypothesis infinite-loop → TIMEOUT statt KILLED (sub-status `killed_by_timeout`) | 5 | Must | 2 | 🔲 |
| 3 | #68 | Bug | Multi-line `if A or B or C:` produziert unimportable SyntaxError-Mutant | 8 | Must | 3 (komplexester AST-Fix) | 🔲 |

**Gesamt geplant:** 16 SP

---

## Sprint-Strategie

- **Ein Feature-Branch** `fix/v2.2.0-reliability-wave`. Pro Bug: TDD-Zyklus (failing test → implement → green → ruff/mypy check) → commit. Bei Sprintende ein Merge-Commit auf main.
- **TDD-Pflicht**: jeder Fix beginnt mit einem fehlschlagenden Test, der die Repro aus dem Issue isoliert.
- **Keine andere Refactoring** im Scope. Nur die drei Bugs + minimale Test-Infrastruktur.
- **Release v2.2.0** mit consolidated Changelog seit v2.1.0.

---

## Item 1 — Bug #70 (Default Parameter Equivalents, Option A)

### Strategie
Mirror des Bug #4 typing.cast() Fix-Patterns. In `MutationVisitor`:
1. Beim Visit eines `cst.Param`-Knotens dessen `.default`-Subtree als no-mutate markieren via `_skip_subtree_ids` (existiert seit Bug #4).
2. Damit fallen alle Mutationen auf Werte in Default-Argumenten weg (Number/String/Boolean Mutations).

### Acceptance Criteria
- [ ] `MutationVisitor` erkennt `cst.Param` und markiert dessen `.default` als no-mutate.
- [ ] Test: `def f(x: int = 30): return x` → keine Mutation auf `30`, aber Body-Mutationen weiterhin generiert.
- [ ] Test: String-Default `def f(url: str = "https://..."): ...` → keine String-Mutation auf `"https://..."`.
- [ ] Test: Body-Mutationen NICHT betroffen (Regression-Schutz).
- [ ] Full suite weiterhin grün.

### TDD-Tasks
| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | Failing Test in `tests/unit/test_default_param_skip.py` | 🔲 |
| 1.2 | Implementation: `_skip_subtree_ids` Erweiterung um `Param.default` | 🔲 |
| 1.3 | Tests grün; full suite check | 🔲 |
| 1.4 | Ruff + mypy clean auf geänderten Files | 🔲 |

---

## Item 2 — Bug #71 (Hypothesis Timeout-vs-Kill)

### Strategie
Zwei Aspekte:
1. **Result-Model**: `MutationResult.outcome` braucht einen neuen Wert oder Sub-Status `killed_by_timeout`. Alternative ist ein neues Boolean-Feld `treated_as_kill: bool` oder ein Set von `documented_kill_reasons`.
2. **CLI / Result-View**: Flag `--treat-timeout-as-kill` (Sprint-23-minimale Variante), das die Score-Berechnung anpasst und in `results`/`show` als KILLED gerendert wird.

Echte Infinite-Loop-Detection (CPU pegged, no progress) ist ein größerer Eingriff in `process/executor.py` und wird auf Sprint 24 vertagt. **Sprint 23 liefert nur den User-controlled Switch**.

### Acceptance Criteria
- [ ] CLI-Flag `--treat-timeout-as-kill` (Boolean, default False).
- [ ] Wenn aktiviert: Score-Berechnung in `cli.py results` und `cli.py run` zählt TIMEOUT zur KILLED-Quote.
- [ ] Result-Tabelle in `results` zeigt eine getrennte Spalte oder Footnote, dass N Mutanten als kill-by-timeout gezählt wurden.
- [ ] Default-Verhalten (ohne Flag) bleibt unverändert.
- [ ] Test: Mock-Run mit 5 KILLED + 3 TIMEOUT. Ohne Flag → 5/8 Score. Mit Flag → 8/8 Score.

### TDD-Tasks
| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing Test in `tests/unit/test_treat_timeout_as_kill.py` | 🔲 |
| 2.2 | CLI-Flag in `cli.py` + Score-Compute-Helper | 🔲 |
| 2.3 | Result-View Anpassung (results-Command Output) | 🔲 |
| 2.4 | Tests grün; full suite check | 🔲 |
| 2.5 | Ruff + mypy clean | 🔲 |

---

## Item 3 — Bug #68 (Multi-Line if/or SyntaxError)

### Strategie
In `node_mutation.py` beim `or`-Removal-Operator:
1. Inspizieren ob die zugehörige `cst.BooleanOperation` über mehrere Zeilen geht (libcst kennt Whitespace-Nodes mit `parenthesized_whitespace.last_line.indent` etc.).
2. Wenn ja → Mutation skippen (Subtree-Skip via `_skip_subtree_ids` für die BooleanOperation).
3. Alternative wäre, beim Generieren der Mutation die hanging continuation lines zu reflowen — komplizierter und fehleranfälliger. Wir nehmen den Skip-Ansatz, analog zu Bug #4/#70.

### Acceptance Criteria
- [ ] Mutator skippt `or`-Removal bei multi-line `BooleanOperation`.
- [ ] Test mit Repro aus Bug Report (`if (\n    A\n    or B\n    or C\n):`) → kein syntaktisch invalider Mutant generiert.
- [ ] Single-line `if A or B:` → `or`-Mutation weiterhin generiert (Regression-Schutz).
- [ ] Validierung: jeder generierte Mutant aus dem Repro-File parst als gültiges Python (via `ast.parse` Roundtrip-Check).
- [ ] Full suite grün.

### TDD-Tasks
| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing Test in `tests/unit/test_multiline_or_skip.py` mit Repro-Pattern + ast.parse check | 🔲 |
| 3.2 | Implementation: Multi-line-Detection in `node_mutation.py` | 🔲 |
| 3.3 | Tests grün; full suite check | 🔲 |
| 3.4 | Ruff + mypy clean | 🔲 |

---

## Quality Gates (Sprint-Ende)

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 564 + 3 neue Tests = 567+ passed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Type Check | `uv run mypy src/mutmut_win/mutation.py src/mutmut_win/node_mutation.py src/mutmut_win/cli.py` | Keine NEUEN Errors |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 Findings |
| Architecture | `uv run lint-imports` | 0 Verletzungen |

---

## Release v2.2.0

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.2.0 | 🔲 |
| Annotated Tag v2.2.0 | 🔲 |
| GitHub Release v2.2.0 mit Changelog seit v2.1.0 | 🔲 |
| Auto-close Issues #68, #70, #71 via merge commit references | 🔲 |
| MEMORY.md + product_backlog.md update | 🔲 |

---

## Out of Scope (carryover für Sprint 24+)

- **Bug #69 (sibling packages)** — Medium, struktureller Fix in File-Setup-Pipeline. Vertagt.
- **Echte Infinite-Loop-Detection** für #71 (CPU pegged + no progress monitoring) — größerer Eingriff in `process/executor.py`, Sprint 23 liefert nur den User-controlled Switch.
- **Bug #70 Option B** (default values at call-site injection) — strukturell unmöglich ohne Major Refactor, deferred indefinitely.
