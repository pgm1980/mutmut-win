# Sprint Backlog — Sprint 24 (Must-Carryover)

**Projekt:** mutmut-win
**Sprint:** 24
**Sprint-Ziel:** Alle Must-priorisierten Carryover-Issues abarbeiten — Worker-Recovery, E2E-Validation-Harness, Job-Object-Test, Dogfooding. Release als v2.3.0.
**Epic(s):** Cross-cutting — addressed leftovers from Epic 3 (Process Mgmt), Epic 9 + 11 (E2E), Epic 12 (Hardening), Epic 14 (Hardening v1.0.0).
**Branch:** `feature/v2.3.0-must-carryover`
**Zeitraum:** 2026-05-23 –
**Status:** 🔲 in progress

---

## Ausgewählte Items

| # | Issue | Typ | Titel | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----|-----------|-------------|--------|
| 1 | #54 | Task | Deterministic Job-Object kill-on-close test | 2 | Must | 1 (klein, isoliert) | 🔲 |
| 2 | #38 + #49 | Task | E2E validation harness (simple_lib + my_lib) | 8 | Must | 2 (Fixtures vorhanden) | 🔲 |
| 3 | #65 | Task | Dogfooding mutmut-win on own code | 3 | Must | 3 (Discovery — kann blocked sein) | 🔲 |
| 4 | #12 | Task | Worker crash recovery — design + impl | 5 | Must | 4 (größtes Stück) | 🔲 |

**Gesamt geplant:** 18 SP

**Bewusst out of scope:**
- #67 H-05 also_copy .venv-Symlink (Should) — Sprint 25
- #69 Bug #2 sibling packages (Medium) — Sprint 25
- #23 Performance benchmark (Could) — Sprint 25
- True infinite-loop detection für #71 (deferred from Sprint 23)

**Risiko:** #65 Dogfooding könnte durch deferred #67 (also_copy .venv-Symlink) oder #69 (sibling packages) geblockt sein. Falls so: in Sprint 24 dokumentieren, paths_to_mutate auf narrow Config zurücksetzen, in Sprint 25 nach #67/#69 wieder aufnehmen.

---

## Sprint-Strategie

- **Ein Feature-Branch** `feature/v2.3.0-must-carryover`. Pro Issue: TDD-Zyklus (failing test → implement → green → ruff/mypy check) → commit. Bei Sprintende ein Merge-Commit auf main.
- **TDD-Pflicht**: jeder Fix beginnt mit einem fehlschlagenden Test, der die Repro aus dem Issue isoliert.
- **Reihenfolge** nach Komplexität (Confidence-Build): #54 → #38/#49 → #65 → #12.
- **Release v2.3.0** mit consolidated Changelog seit v2.2.0.

---

## Item 1 — Issue #54: Deterministic Job-Object kill-on-close Test

### Strategie
Job-Object-Integration existiert seit Hardening Sprint (`process/job_object.py` + `process/executor.py`). Was fehlt: ein deterministischer Test der beweist, dass Worker-Subprozesse sterben, wenn das Parent-Handle geschlossen wird.

Test-Idee:
1. Subprocess A startet, erstellt Job Object, weist Worker B (mit child sleep loop) zu.
2. A schließt Job Object handle (oder A wird gekillt).
3. Assert: B existiert nicht mehr innerhalb eines bounded timeouts (z.B. 2s).

### Acceptance Criteria
- [ ] `tests/integration/test_job_object_kill_on_close.py` — deterministischer Test.
- [ ] Test verifiziert: Parent-Tod → Worker tod innerhalb 2s.
- [ ] Test `@pytest.mark.integration` und `@pytest.mark.slow` markiert.
- [ ] Funktioniert in CI (Windows-only — graceful-skip auf Linux/macOS).
- [ ] Ruff + mypy clean, full suite grün.

---

## Item 2 — Issues #38 + #49: E2E Validation Harness

### Strategie
`tests/integration/test_e2e_reference.py` enthält bereits einen partiellen Harness (`test_my_lib_mutation_generation`). Den auf eine vollständige Pipeline erweitern: `mutmut-win run` als Subprozess auf simple_lib + my_lib starten, Ergebnis-DB inspizieren, gegen `expected_results.py` Snapshot vergleichen.

### Acceptance Criteria
- [ ] `tests/integration/test_e2e_validation.py` (oder Erweiterung des bestehenden) führt vollen `mutmut-win run` auf:
  - `tests/e2e_projects/simple_lib/` (klein, schneller smoke)
  - `tests/e2e_projects/my_lib/` (bereits expected_results)
- [ ] Ergebnis-DB wird gelesen; pro Mutant wird der status (killed/survived/timeout) gegen Erwartung verglichen.
- [ ] Tests `@pytest.mark.integration` und `@pytest.mark.slow`.
- [ ] Tolerance-Mechanismus für plattform-spezifische Exit-Codes (Segfault auf Windows ≠ -11 wie auf Linux).
- [ ] Full suite grün.

### TDD-Tasks
| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing test für simple_lib (volle Pipeline) | 🔲 |
| 2.2 | Helper: `run_mutmut_win_e2e(project_dir) → MutationRunResult` (subprocess) | 🔲 |
| 2.3 | Compare-Helper: status vs. expected_results, mit Platform-Tolerance | 🔲 |
| 2.4 | Extend für my_lib | 🔲 |
| 2.5 | Quality Gates | 🔲 |

---

## Item 3 — Issue #65: Dogfooding mutmut-win on own code

### Strategie
`pyproject.toml [tool.mutmut] paths_to_mutate` ist aktuell nur auf `regex_mutation.py` beschränkt. Erweitern auf `src/mutmut_win/` und einen Dogfooding-Lauf erfolgreich abschließen.

### Acceptance Criteria
- [ ] `pyproject.toml [tool.mutmut] paths_to_mutate = ["src/mutmut_win/"]`
- [ ] `uv run mutmut-win run --no-progress` läuft ohne SyntaxError / WinError 32 / ImportError durch
- [ ] Mindestens Mutation-Score wird angezeigt (auch wenn niedrig)
- [ ] Falls geblockt durch #67/#69: documentiere blocker in sprint_24_backlog.md, rolle paths_to_mutate auf narrow Config zurück, verschiebe Issue #65 nach Sprint 25.

### Discovery-Tasks
| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | paths_to_mutate erweitern, `mutmut-win run` versuchen | 🔲 |
| 3.2 | Failure-Analyse: welche Bugs treten auf? | 🔲 |
| 3.3 | Wenn fixable → fixen; wenn blocked → rollback + dokumentieren | 🔲 |

---

## Item 4 — Issue #12: Worker Crash Recovery

### Strategie
Status quo: Worker-Crashes werden erkannt (laut #12 PARTIAL-Audit), aber kein automatischer Restart implementiert. Sprint 24 liefert:

1. **Design**: max N restarts pro slot (N=3 default), exponential backoff (1s, 2s, 4s), nach N: slot wird als "exhausted" markiert und übersprungen.
2. **Implementation** in `process/executor.py`: restart-counter pro slot, backoff-Timer, exhaustion-flag.
3. **TDD**: simulated crash → verify slot restarts → 3 crashes in row → slot exhausted → orchestrator continues with remaining slots.

### Acceptance Criteria
- [ ] `process/executor.py` hat restart-Logik pro slot (max 3 attempts, exponential backoff)
- [ ] Slot-exhaustion wird in `MutationResult.status = "worker_exhausted"` reflektiert (oder als "suspicious")
- [ ] Test: einzelner Worker crash → recovery → continues
- [ ] Test: 4 crashes in row → slot exhausted, exits clean
- [ ] Test: andere slots nicht betroffen
- [ ] Full suite grün, Ruff + mypy clean

### TDD-Tasks
| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | Failing Test: Worker crash → recovery erwartet | 🔲 |
| 4.2 | Implementation: restart loop in SpawnPoolExecutor | 🔲 |
| 4.3 | Test: exhaustion threshold | 🔲 |
| 4.4 | Test: andere slots isoliert | 🔲 |
| 4.5 | Quality Gates | 🔲 |

---

## Quality Gates (Sprint-Ende)

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 578 + N neue = mindestens 585 passed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Type Check | `uv run mypy src/mutmut_win/` | Keine NEUEN Errors |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 Findings |

---

## Release v2.3.0

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.3.0 | 🔲 |
| Annotated Tag v2.3.0 | 🔲 |
| GitHub Release v2.3.0 mit Changelog seit v2.2.0 | 🔲 |
| Auto-close Issues #12, #38, #49, #54, #65 via merge commit refs | 🔲 |
| MEMORY.md + product_backlog.md update | 🔲 |
