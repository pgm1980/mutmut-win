# Sprint Backlog — Sprint 22 (v2.0.x Stabilization)

**Projekt:** mutmut-win
**Sprint:** 22
**Sprint-Ziel:** v2.0.x Stabilization — Timeout Diagnostics, Bug #4 fix, Housekeeping (post v2.0 Release)
**Epic(s):** Epic 15 (v2.0.x Stabilization)
**Branch:** `main` (Bug-Fix-Wave landete direkt auf main; PR #66 via `fix/bug-4-typing-cast-skip` → merge commit)
**Zeitraum:** 2026-04-10 (erster Timeout-Fix `6ad5fbf`) – 2026-05-22 (v2.1.0 Release)
**Status:** ✅ Closed mit v2.1.0 Release

---

## Ausgewählte Items

| # | Issue/PR | Typ | Titel | SP | Priorität | Status |
|---|----------|-----|-------|----|-----------|--------|
| 1 | PR #66 | Bug | Bug #4: skip typing.cast() first-arg mutations | 3 | Must | ✅ Done |
| 2 | — | Task | v2.0.x Timeout Diagnostics-Serie | 5 | Must | ✅ Done |
| 3 | — | Task | Housekeeping: 42 GitHub-Issues sync, MEMORY.md, sprint state | 3 | Should | ✅ Done |
| 4 | — | Task | v2.1.0 Tag + Release (consolidated changelog seit v1.0.7) | 2 | Should | ✅ Done |

**Gesamt:** 13 SP — **Erledigt:** 13 SP — **Velocity:** 100%

---

## Task Breakdown

### Item 1: Bug #4 typing.cast() skip (PR #66) — ✅ Done

**User Story:** Als User will ich nicht für unkillable equivalent-Mutanten in `typing.cast(type, obj)` First-Args bestraft werden, damit die gemeldete Mutation Score reale Test-Lücken zeigt, nicht Annotationsrauschen.

**Acceptance Criteria:**
- [x] `cast(...)` und `typing.cast(...)` werden in `MutationVisitor` erkannt
- [x] Subtree-Skip via `id()`-Tracking verhindert dass `operator_string` etc. auf der Typannotation feuern
- [x] Call-Level-Filter droppt `operator_arg_removal` / `operator_dict_arguments` Mutanten, die `args[0]` ändern
- [x] Zweites Argument bleibt mutierbar (Verhalten unverändert)
- [x] 5 neue Unit Tests in `tests/unit/test_typing_cast_skip.py`
- [x] Full suite 564 passed, 3 skipped
- [x] Ruff: All checks passed
- [x] mypy: keine neuen Errors (7 pre-existing in `mutation.py` bleiben)

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | `_is_cast_call(node)` Helper für CST-Detection (qualified + unqualified) | ✅ |
| 1.2 | `_SubtreeIdCollector` Visitor zum Markieren des no-mutate Subtrees | ✅ |
| 1.3 | `_skip_subtree_ids: set[int]` in `MutationVisitor` + Short-Circuit in `on_visit` | ✅ |
| 1.4 | Call-Level-Filter in `_create_mutations` | ✅ |
| 1.5 | 5 Unit Tests: qualified/unqualified/Name first-arg/second-arg-mutable/non-cast | ✅ |
| 1.6 | PR-Review + Merge mit `merge: ...` Commit-Format | ✅ |

**Bug-Quelle:** `pgm1980/critique-model-service` `_misc/mutmut-win-bugs.md` Bug #4 — vier unkillable Mutanten pro `cast()` Call beobachtet im Sprint-4-Lauf von critique-model-service.

---

### Item 2: v2.0.x Timeout Diagnostics-Serie — ✅ Done

**User Story:** Als User auf Windows will ich, dass Worker-Hangs diagnostizierbar sind (Output sichtbar, Subprocess-Timeouts erzwungen), damit ich nicht in undebuggbaren Endlosläufen feststecke.

**Commit-Kette:**

| Commit | Aktion | Status |
|--------|--------|--------|
| `6ad5fbf` | `timeout=` zu allen `subprocess.run()` Calls — Worker-Hang-Prevention | ✅ |
| `c0e6056` | `capture_output=True` → `DEVNULL` (Pipe-Deadlock-Fix bei stderr-spamming tests) | ✅ |
| `638a9be` | DEVNULL → Temp-File-Capture, damit Output für Diagnose verfügbar bleibt | ✅ |
| `77c7828` | `last_output` in SQLite-DB persistieren für Post-Mortem-Inspektion | ✅ |

**Acceptance Criteria:**
- [x] Kein `subprocess.run()` Call ohne `timeout=` Argument
- [x] Pipe-Deadlock-Fall (subprocess füllt stderr-Puffer schneller als geleert wird) deterministisch reproducible/lösbar
- [x] Worker-Output bei Timeout in DB verfügbar via `last_output` Feld in `mutation_results`
- [x] Keine Test-Regression durch die Diagnostics-Wave

---

### Item 3: Housekeeping (2026-05-22) — ✅ Done

**Trigger:** Sprint State (`.sprint/state.md`) zeigt "Sprint 14" mit Branch `feature/55-regex-mutations` — komplett veraltet. SessionStart-Hook warnt.

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Audit aller 48 offenen GitHub-Issues gegen v2.0.4-Codebase via Explore-Agent | ✅ |
| 3.2 | 40 DONE Issues schließen mit Code-Evidenz-Notiz | ✅ |
| 3.3 | #22 als Duplikat von #65 schließen | ✅ |
| 3.4 | #64 schließen (Hook-Fix verifiziert live in SessionStart dieser Session) | ✅ |
| 3.5 | `.sprint/state.md` von Sprint 14 → Sprint 22 (zwischenzeitlich fälschlich als 21) refresht | ✅ |
| 3.6 | `MEMORY.md` von leer → Projekt-Snapshot mit Architektur, offenen Items, Conventions | ✅ |
| 3.7 | Persistente Memory-Files in `~/.claude/projects/.../memory/` (state-drift, downstream-bugs, v2-focus) | ✅ |
| 3.8 | `uv.lock` synchronisiert mit `pyproject.toml` (1.0.10 → 2.1.0) | ✅ |
| 3.9 | 11 abgearbeitete `_issues/*.md` entfernt | ✅ |
| 3.10 | Backlog-Sync: product_backlog.md + sprint_14/15/21_backlog.md auf realen Stand | ✅ |
| 3.11 | Issue #67 (H-05 also_copy .venv-Symlink) retroaktiv erstellt | ✅ |

**Ergebnis:** GitHub Issues OPEN-Count von 48 → 7 (#12, #23, #38, #49, #54, #65, #67). Echte Open-Items sind alle echte Open-Items.

---

### Item 4: v2.1.0 Tag + Release — ✅ Done

**Tasks:**

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | `pyproject.toml` Version `2.0.4 → 2.1.0` (MINOR Bump für consolidated changelog seit v1.0.7) | ✅ |
| 4.2 | `uv.lock` Version-Eintrag synchron | ✅ |
| 4.3 | Annotated Tag `v2.1.0` mit Release-Summary | ✅ |
| 4.4 | Push commit + tag | ✅ |
| 4.5 | GitHub Release `v2.1.0` mit consolidated Changelog (v1.0.7 → v2.1.0) | ✅ |

**Tag-Sha:** `ac3e5bb` (annotated) → `8685f93` (commit)
**Release-URL:** https://github.com/pgm1980/mutmut-win/releases/tag/v2.1.0

---

## Quality Gates

| Gate | Befehl | Ergebnis | Status |
|------|--------|----------|--------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 564 passed, 3 skipped | ✅ |
| Linting | `uv run ruff check src/mutmut_win/mutation.py tests/unit/test_typing_cast_skip.py` | All checks passed | ✅ |
| Type Check | `uv run mypy src/mutmut_win/mutation.py` | 7 pre-existing Errors, 0 neue | ⚠️ Tech-Debt |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 findings (0 blocking) | ✅ |
| Architecture | `uv run lint-imports` | nicht in diesem Sprint geprüft | ⏭️ |
| Coverage | `uv run pytest --cov=src` | nicht in diesem Sprint gemessen | ⏭️ |
| Mutation Testing | `uv run mutmut-win run --paths-to-mutate src/mutmut_win/regex_mutation.py` | dogfooding eingeschränkt — siehe #65 | ⚠️ |

---

## Sprint Execution Log

| Zeitpunkt | Aktion | Ergebnis |
|-----------|--------|----------|
| 2026-04-10 | Sprint gestartet mit erstem Timeout-Fix `6ad5fbf` | Worker-Hang-Prevention live |
| 2026-04-11 – 04-13 | Timeout-Diagnostics-Serie (commits `c0e6056`, `638a9be`, `77c7828`, `0801719` v2.0.2 bump) | Diagnostics-Path komplett |
| 2026-05-22 | PR #66 (Bug #4 typing.cast skip) verifiziert + gemergt | 5 neue Tests, full suite grün |
| 2026-05-22 | Housekeeping-Pass: 42 Issues geschlossen, state.md / MEMORY.md / Backlogs synchronisiert | DoD-Items abgeschlossen |
| 2026-05-22 | v2.1.0 Tag + GitHub Release | Consolidated changelog seit v1.0.7 live |

---

## Carryover in zukünftige Sprints

| Issue | Titel | Status | Priorität |
|-------|-------|--------|-----------|
| #12 | Worker crash recovery | PARTIAL | Must |
| #23 | Performance benchmark vs mutmut | open | Could |
| #38 | E2E validation test (full pipeline) | UNCLEAR | Must |
| #49 | Sprint-12 Full E2E (simple_lib + my_lib) | UNCLEAR | Must |
| #54 | Deterministic Job Object kill-on-close Test | UNCLEAR | Must |
| #65 | Dogfooding mutmut-win on own code | PARTIAL | Must |
| #67 | H-05: also_copy .venv-Symlink review | NEW | Should |
