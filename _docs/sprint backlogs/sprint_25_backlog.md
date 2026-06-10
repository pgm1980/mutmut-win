# Sprint Backlog — Sprint 25 (Final Cleanup)

**Projekt:** mutmut-win
**Sprint:** 25
**Sprint-Ziel:** Die letzten drei offenen Carryover-Issues abarbeiten — H-05 also_copy .venv-Skip (#67), sibling packages support (#69), Performance benchmark suite (#23). Release als v2.4.0.
**Epic(s):** Cross-cutting — addressed leftovers from Epic 14 (Sprint 21 retro), Sprint 23 (deferred #69), Epic 6 (carryover #23).
**Branch:** `feature/v2.4.0-final-cleanup`
**Zeitraum:** 2026-05-23 – 2026-05-23
**Status:** ✅ Closed mit v2.4.0 Release (merge f4c318b, alle 3 Items geliefert — 10/10 SP, Velocity 100%)

---

## Ausgewählte Items

| # | Issue | Typ | Titel | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----|-----------|-------------|--------|
| 1 | #67 | Fix | H-05 also_copy .venv-Symlink review | 2 | Should | 1 (klein) | ✅ |
| 2 | #69 | Bug | sibling packages not copied to mutants/ workdir | 5 | Medium | 2 | ✅ |
| 3 | #23 | Feature | Performance benchmark vs mutmut | 3 | Could | 3 | ✅ |

**Gesamt geplant:** 10 SP

---

## Sprint-Strategie

- **Ein Feature-Branch** `feature/v2.4.0-final-cleanup`. Pro Issue: TDD-Zyklus → commit. Merge-Commit auf main bei Sprintende.
- **Release v2.4.0** mit consolidated Changelog seit v2.3.0.
- **Nach Sprint 25**: keine Carryover mehr — Repo ist sauber für die nächste Feature-Welle.

---

## Item 1 — Issue #67: H-05 also_copy .venv-Symlink review

### Strategie
`copy_also_copy_files()` in `file_setup.py` muss `.venv/` Verzeichnisse skippen (oder dokumentieren dass der Aufrufer das tun muss). Aktuelle WinError-32-Fixes haben self-copy gelöst, aber Symlink-Behandlung ist nicht explizit getestet.

### Acceptance Criteria
- [x] Code-Audit: `copy_also_copy_files()` Verhalten auf `.venv`-haltige Inputs
- [x] Explizite Skip-Logik für `.venv/`, `venv/`, `env/` Verzeichnisse (oder Pattern via config)
- [x] Regression-Test mit also_copy auf Projekt mit `.venv/` darin
- [x] Ruff + mypy clean

---

## Item 2 — Issue #69: Sibling packages support

### Strategie
Aus den drei vorgeschlagenen Optionen (#69 Issue body): Option B "neuer `--extra-paths-to-copy` Flag + `[tool.mutmut].extra_paths` config" — am explizitesten, am einfachsten umsetzbar.

### Implementation
1. `MutmutConfig` (Pydantic) bekommt neues Feld `extra_paths: list[str] = []`
2. CLI `--extra-paths-to-copy PATH...` (repeatable)
3. File-Setup-Pipeline kopiert diese Pfade in `mutants/`
4. Worker setzt PYTHONPATH so dass diese Pfade aufgelöst werden können

### Acceptance Criteria
- [x] Config-Feld `extra_paths` (List[str])
- [x] CLI-Flag `--extra-paths-to-copy PATH...`
- [x] File-Setup kopiert die Pfade
- [x] Worker PYTHONPATH enthält sie
- [x] Test: also_copy + extra_paths funktioniert für sibling `benchmarks/`-Layout
- [x] Ruff + mypy clean

---

## Item 3 — Issue #23: Performance benchmark suite

### Strategie
Minimaler `benchmarks/` Ordner mit einem pytest-benchmark-Test, der die Mutation-Generation auf my_lib misst. Workload: ein fester source-file mit ~50 Funktionen, gemessen wird `mutate_file_contents()`.

Vergleich gegen mutmut 3.5.0 ist out-of-scope für Sprint 25 (würde mutmut als parallel install brauchen) — wir liefern die Infrastruktur + eine Baseline-Messung.

### Acceptance Criteria
- [x] `benchmarks/test_mutation_generation_benchmark.py`
- [x] pytest-benchmark misst `mutate_file_contents()` auf my_lib + simple_lib fixtures
- [x] Command in pyproject documented: `uv run pytest benchmarks/ --benchmark-only`
- [x] Ruff + mypy clean

---

## Quality Gates (Sprint-Ende)

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 585 + N neue = ≥ 590 passed |
| Linting | `uv run ruff check src/ tests/ benchmarks/` | 0 Findings |
| Type Check | `uv run mypy src/` | Keine NEUEN Errors |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 Findings |

**Ergebnis (Sprint-Ende, 8be779a):** pytest 594 passed / 3 skipped, ruff 0 Findings, mypy clean, semgrep 0 Findings.

---

## Release v2.4.0

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.4.0 | ✅ |
| Annotated Tag v2.4.0 | ✅ |
| GitHub Release v2.4.0 mit Changelog seit v2.3.0 | ✅ |
| Auto-close Issues #23, #67, #69 | ✅ |
| MEMORY.md + product_backlog.md final update | ✅ |

---

## Nach Sprint 25

- **0 Carryover-Issues offen** → Repo ist sauber
- Neue Feature-Wellen können auf grüner Wiese starten
- Open für Sprint 26+: bug reports from real-world usage (downstream)
