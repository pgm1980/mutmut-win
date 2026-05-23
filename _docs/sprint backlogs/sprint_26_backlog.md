# Sprint Backlog — Sprint 26 (v2.5.0 Polish + True IL Detection)

**Projekt:** mutmut-win
**Sprint:** 26
**Sprint-Ziel:** Polish + Bug #5 true infinite-loop detection — alleinige internationale Spitze in IL-detection. Release v2.5.0.
**Epic(s):** Epic 16 (Detection Quality) — neu
**Branch:** `feature/v2.5.0-polish`
**Zeitraum:** 2026-05-23 –
**Status:** 🔲 in progress

---

## Ausgewählte Items

| # | Issue | Typ | Titel | SP | Priorität | Status |
|---|-------|-----|-------|----|-----------|--------|
| 1 | #72 (neu) | Bug | `--version` reportet 2.0.4 statt pyproject — single source of truth via importlib.metadata | 1 | Must | 🔲 |
| 2 | #71 (re-open) | Feature | Bug #5 true infinite-loop detection — psutil + forensics + confidence | 13 | Must | 🔲 |

**Gesamt:** 14 SP

---

## Architektur-Entscheidung Item 2 (#71 Bug #5)

Nach 10-Schritt Maxential CoT + 4-stufiger Tree-of-Thoughts Analyse (best path score 0.94):

**Gewählte Variante:** Forensic psutil-Detector mit Polling-Thread im Worker.

### Decision Rule
Während subprocess.Popen()-Laufzeit pollt MonitorThread alle 0.5 s:
- `cpu_pct` = Summe CPU% des process-tree
- `output_bytes` = current log file size (st_size)
- `status` = psutil.Process.status() (running/sleeping/disk-sleep/...)

Rolling window: deque(maxlen=20) = letzte 10 s.

Bei TimeoutExpired:
```
killed_by_infinite_loop (exit_code 38, neu)  WENN
    mean(cpu_pct) ≥ infinite_loop_cpu_threshold (default 70%)
  AND output_growth_in_window < infinite_loop_output_threshold (default 1 KB)
  AND running_ratio ≥ infinite_loop_running_ratio (default 0.8)
SONST: timeout (exit_code 36, bestehend)
```

### Forensics (Marktneuheit)
`IlForensics` Pydantic-Model in `models.py`:
- cpu_pct_mean, cpu_pct_max
- output_growth_bytes
- running_ratio
- samples_collected
- last_output_tail (last 5 lines of pytest output)
- confidence: "high" | "medium" | "low" (based on threshold-margin)

Persisted as JSON column on `mutant` table. Rendered by `mutmut-win show <mutant>`.

### Konfiguration
`pyproject.toml [tool.mutmut]`:
```toml
infinite_loop_detection = true              # default on
infinite_loop_cpu_threshold = 70.0
infinite_loop_output_threshold = 1024
infinite_loop_running_ratio = 0.8
infinite_loop_window_seconds = 10.0
```
CLI: `--no-infinite-loop-detection`, `--infinite-loop-cpu-threshold X`.

### Dependency
psutil >= 5.9 als regular dep (mit graceful import fallback im Code: try/except ImportError → disable detection).

### Cross-Validation gegen Bug-Report-Patterns
| Szenario | CPU | Output growth | Status | Verdict |
|----------|-----|---------------|--------|---------|
| Hypothesis-IL (Bug #5 case) | high | none | running | **killed_by_infinite_loop** ✓ |
| Slow DB-test | low | none | sleeping | timeout ✓ |
| Slow Hypothesis (genuine many examples) | medium-high | growing | running | timeout ✓ (output = progress signal) |
| Async event-loop spinning | high | none | running | **killed_by_infinite_loop** ✓ |
| Network retry-storm | low | growing slowly | sleeping | timeout ✓ |

---

## Task Breakdown

### Item 1: `--version` Single Source of Truth (#72)

| Task | Status |
|------|--------|
| 1.1 Failing test: `mutmut-win --version` matches `importlib.metadata.version("mutmut-win")` | 🔲 |
| 1.2 Refactor `__init__.py`: `__version__ = importlib.metadata.version("mutmut-win")` with PackageNotFoundError fallback for editable installs | 🔲 |
| 1.3 Verify CLI `--version` reports 2.5.0 after pyproject bump | 🔲 |
| 1.4 Ruff + mypy clean | 🔲 |

### Item 2: Bug #5 True IL Detection (#71)

| Task | Status |
|------|--------|
| 2.1 Add `psutil>=5.9` to `pyproject.toml` dependencies | 🔲 |
| 2.2 New module `src/mutmut_win/process/loop_monitor.py`: `ProcessMonitor` thread + `LoopClassification` + `IlForensics` | 🔲 |
| 2.3 `models.py`: extend `MutationResult` with `forensics: IlForensics | None` field | 🔲 |
| 2.4 `db.py`: schema migration (`forensics` JSON column on mutant table) + load/save | 🔲 |
| 2.5 `config.py`: 5 new `MutmutConfig` fields with defaults | 🔲 |
| 2.6 `worker.py` integration: spawn ProcessMonitor in `_process_task`, replace `subprocess.run` with `Popen` + `wait(timeout)`, invoke `monitor.classify()` on TimeoutExpired | 🔲 |
| 2.7 `cli.py`: `--no-infinite-loop-detection` + `--infinite-loop-cpu-threshold` flags, results-command renders forensics | 🔲 |
| 2.8 Unit tests (`tests/unit/test_loop_monitor.py`): 5 tests covering Mock-psutil scenarios (CPU pegged, slow test, ambiguous, all-sleeping, edge-thresholds) | 🔲 |
| 2.9 Integration test (`tests/integration/test_il_detection.py`): real `python -c "while True: pass"` subprocess → classification == infinite_loop with confidence=high | 🔲 |
| 2.10 graceful degradation test: simulate `import psutil` ImportError → no crash, fallback to plain timeout | 🔲 |
| 2.11 Full suite + ruff + mypy + semgrep gates | 🔲 |

---

## Out of Scope

- Hypothesis-pathological "shrink-storm" edge case (würde IL falsch klassifizieren) — Tuning via thresholds, falls real beobachtet
- Deprecation des `--treat-timeout-as-kill` Flag (Sprint 27+)
- Stack-Sampling (py-spy-style) — overkill für v2.5
- Per-Mutation timeout-budgets — orthogonal feature

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 594 + ~10 neue = ≥604 passed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Type Check | `uv run mypy src/mutmut_win/` | Keine NEUEN Errors |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 Findings |
| Architecture | `uv run lint-imports` | 0 Verletzungen |

---

## Release v2.5.0

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.5.0 | 🔲 |
| Annotated Tag v2.5.0 | 🔲 |
| GitHub Release v2.5.0 with detailed changelog incl. IL-detection feature + market positioning | 🔲 |
| Auto-close #71, #72 via merge commit | 🔲 |
| MEMORY.md + product_backlog.md update | 🔲 |

---

## Sprint-Strategie

Ein Feature-Branch `feature/v2.5.0-polish`. Item 1 zuerst (klein, confidence build), dann Item 2 in TDD-Sequenz (Tasks 2.1 → 2.11). Bei Sprintende Merge-Commit auf main.

Item 2 ist groß — ggf. splitten wenn mid-sprint scope blow-up: 2.2-2.6 (core) und 2.7-2.10 (CLI/test) als separate Commits auf demselben Branch.
