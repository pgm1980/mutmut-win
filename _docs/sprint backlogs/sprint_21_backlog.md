# Sprint Backlog — Sprint 21 (Hardening)

**Projekt:** mutmut-win
**Sprint:** 21
**Sprint-Ziel:** Hardening — CLI-Flags, Dogfooding-Fix, Hook-Debugging
**Epic(s):** Epic 14 (Hardening v1.0.0)
**Branch:** `feature/hardening-h05-h07`

---

## Ausgewählte Items

| # | Issue/Finding | Typ | Titel | SP | Priorität | Status |
|---|---------------|-----|-------|----|-----------|--------|
| 1 | H-06 | Bug | Worker ModuleNotFoundError bei editable install + spawn | 5 | Must | 🔲 |
| 2 | H-07 | Feature | 10 CLI-Flags (Tier 1-3) | 8 | Must | 🔲 |
| 3 | H-01–H-04 | Bug | Hooks feuern nicht automatisch in Claude Desktop | 5 | Must | 🔲 |
| 4 | H-05 | Fix | also_copy .venv-Symlink Review | 2 | Should | 🔲 |
| 5 | — | Task | Dogfooding: mutmut-win auf eigenem Code | 3 | Must | 🔲 |

**Gesamt:** 23 SP

---

## Task Breakdown

### H-06: Worker ModuleNotFoundError

**Problem:** Worker-Prozesse (multiprocessing.spawn) können `mutmut_win` nicht importieren bei editable install.

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Root Cause: sys.path in spawned Workern analysieren | 🔲 |
| 6.2 | Fix: PYTHONPATH oder sys.path im Worker setzen | 🔲 |
| 6.3 | Test: Dogfooding-Lauf erfolgreich | 🔲 |

### H-07: 10 CLI-Flags

**Tasks:**

| Task | Tier | Flag | Status |
|------|------|------|--------|
| 7.1 | 1 | `--paths-to-mutate PATH...` | 🔲 |
| 7.2 | 1 | `--min-score FLOAT` | 🔲 |
| 7.3 | 1 | `--output text\|json` | 🔲 |
| 7.4 | 2 | `--since-commit HASH` (USP) | 🔲 |
| 7.5 | 2 | `--tests-dir DIR` | 🔲 |
| 7.6 | 2 | `--no-progress` | 🔲 |
| 7.7 | 2 | `--debug` | 🔲 |
| 7.8 | 3 | `--dry-run` | 🔲 |
| 7.9 | 3 | `--timeout-multiplier FLOAT` | 🔲 |
| 7.10 | 3 | `--do-not-mutate PATTERN` | 🔲 |
| 7.11 | — | Unit Tests für alle Flags | 🔲 |

### H-01–H-04: Hooks

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| H.1 | sprint-health.sh: Prüfen warum SessionStart nicht feuert | 🔲 |
| H.2 | sprint-gate.sh: Suchpfad auf _docs/sprint backlogs/ ändern | 🔲 |
| H.3 | Alle Hooks manuell testen + Ergebnis in hooks.md | 🔲 |
| H.4 | settings.json Hook-Config verifizieren | 🔲 |
