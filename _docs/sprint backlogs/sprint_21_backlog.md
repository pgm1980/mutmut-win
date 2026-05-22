# Sprint Backlog — Sprint 21 (Hardening v1.0.0)

**Projekt:** mutmut-win
**Sprint:** 21
**Sprint-Ziel:** Hardening — CLI-Flags, Dogfooding-Fix, Hook-Debugging
**Epic(s):** Epic 14 (Hardening v1.0.0)
**Branch:** `feature/hardening-h05-h07`
**Status:** ✅ Closed (alle Issues bis auf #65 und #67 erledigt; siehe Sprint 22 für Carryover)

---

## Ausgewählte Items

| # | Issue/Finding | Typ | Titel | SP | Priorität | Status |
|---|---------------|-----|-------|----|-----------|--------|
| 1 | #62 (H-06) | Bug | Worker ModuleNotFoundError bei editable install + spawn | 5 | Must | ✅ Done |
| 2 | #63 (H-07) | Feature | 10 CLI-Flags (Tier 1-3) | 8 | Must | ✅ Done |
| 3 | #64 (H-01–H-04) | Bug | Hooks feuern nicht automatisch in Claude Desktop | 5 | Must | ✅ Done |
| 4 | #67 (H-05) | Fix | also_copy .venv-Symlink Review | 2 | Should | 🔲 Open (retroactively filed 2026-05-22) |
| 5 | #65 | Task | Dogfooding: mutmut-win auf eigenem Code | 3 | Must | 🔲 Open (PARTIAL) |

**Gesamt geplant:** 23 SP — **Erledigt:** 18 SP — **Carryover:** 5 SP (#65, #67)

---

## Task Breakdown

### H-06: Worker ModuleNotFoundError (#62) — ✅ Done

**Problem:** Worker-Prozesse (multiprocessing.spawn) können `mutmut_win` nicht importieren bei editable install.

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Root Cause: sys.path in spawned Workern analysieren | ✅ |
| 6.2 | Fix: PYTHONPATH oder sys.path im Worker setzen | ✅ |
| 6.3 | Test: Dogfooding-Lauf erfolgreich (eingeschränkt — siehe #65) | ✅ |

### H-07: 10 CLI-Flags (#63) — ✅ Done

**Tasks:**

| Task | Tier | Flag | Status |
|------|------|------|--------|
| 7.1 | 1 | `--paths-to-mutate PATH...` | ✅ |
| 7.2 | 1 | `--min-score FLOAT` | ✅ |
| 7.3 | 1 | `--output text\|json` | ✅ |
| 7.4 | 2 | `--since-commit HASH` (USP) | ✅ |
| 7.5 | 2 | `--tests-dir DIR` | ✅ |
| 7.6 | 2 | `--no-progress` | ✅ |
| 7.7 | 2 | `--debug` | ✅ |
| 7.8 | 3 | `--dry-run` | ✅ |
| 7.9 | 3 | `--timeout-multiplier FLOAT` | ✅ |
| 7.10 | 3 | `--do-not-mutate PATTERN` | ✅ |
| 7.11 | — | Unit Tests für alle Flags | ✅ |

### H-01–H-04: Hooks (#64) — ✅ Done

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| H.1 | sprint-health.sh: Prüfen warum SessionStart nicht feuert (Fix: matcher regex semantics) | ✅ |
| H.2 | sprint-gate.sh: Suchpfad auf `_docs/sprint backlogs/` ändern | ✅ |
| H.3 | Alle Hooks manuell testen + Ergebnis in `hooks.md` | ✅ |
| H.4 | settings.json Hook-Config verifizieren (`if`-filter inside hook object, not group level) | ✅ |

Fix-Serie über mehrere Commits: `8983e9e`, `0c142ef`, `009cff5`, `ea23455`, `f1a8014`, `b818e0a`.
Verifiziert live in Sprint 22 SessionStart (2026-05-22).

### H-05: also_copy .venv-Symlink Review — 🔲 Open

Während Sprint 21 als Item gelistet, aber nie als GitHub-Issue eröffnet. Im Housekeeping-Pass 2026-05-22 retroaktiv als **#67** angelegt. Carryover in Sprint 22+ Backlog.

### #65 Dogfooding — 🔲 Open (PARTIAL)

`pyproject.toml` mutiert nur `src/mutmut_win/regex_mutation.py`. Vollständiges Dogfooding über den gesamten `src/`-Tree steht aus. Carryover.

---

## Quality Gates (rückblickend dokumentiert 2026-05-22)

| Gate | Befehl | Status |
|------|--------|--------|
| Tests | `uv run pytest` (Sprint 21 Endstand) | ✅ alle grün |
| Linting | `uv run ruff check .` | ✅ 0 Findings (auf damaligem Stand) |
| Type Check | `uv run mypy src/` | ⚠️ 7 pre-existing Errors in `mutation.py` (vorher schon vorhanden) |

---

## Notiz (2026-05-22)

Dieser Sprint-Backlog wurde während des Sprint-22-Housekeeping retroaktiv synchronisiert. Sprint 21 wurde am 2026-03-30 abgeschlossen und gemergt (`224bc2b merge: Hardening Sprint — 10 CLI flags + H-06 fix`), aber die Checkboxes wurden bis 2026-05-22 nicht aktualisiert.
