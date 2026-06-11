# Sprint Backlog — Sprint 30 (v2.8.0 IL Detection Honesty)

**Projekt:** mutmut-win
**Sprint:** 30
**Sprint-Ziel:** Das v2.5-Flaggschiff-Feature (Infinite-Loop-Detection) löst erstmals sein Versprechen ein: Forensik wird persistiert UND gerendert, der CI/CD-Export zählt IL-Kills, und der auf Windows degenerierte Triple-Check wird ehrlich (echtes Output-Signal, neutraler Status, Confidence ohne Inflation). Release v2.8.0.
**Epic(s):** Epic 21 (IL Detection Honesty) — neu
**Branch:** `feature/v2.8.0-il-honesty`
**Zeitraum:** 2026-06-11 –
**Status:** 🔲 in progress

**Grundlage:** Sprint-27-Audit Cluster **C5** (`_docs/audit/sprint_27_audit_findings.md`).
Planungs-Analyse: Sequential-Thinking-Session (Zuschnitt, Wertschöpfungskette
persist → count → render → be-honest, Cut-Regeln). Hinweis: A2-JT-013 ist
obsolet (timeout.py wurde in Sprint 29 entfernt).

---

## Ausgewählte Items

| # | Issue | Typ | Titel | Findings | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----------|----|-----------|-------------|--------|
| 1 | [#85](https://github.com/pgm1980/mutmut-win/issues/85) | Bug | Forensik-Persistenz: `save_result` erhält `event.forensics`; 38-Konstante statt Literal | JT-004 (S2), QX-019-Slice | 2 | Must | 1 (alles Weitere braucht Daten) | 🔲 |
| 2 | [#86](https://github.com/pgm1980/mutmut-win/issues/86) | Bug | CICD-Export: `killed_by_infinite_loop`-Bucket; ein Score über alle drei Kanäle | OS-002 (S2) | 2 | Must | 2 (Confidence-Builder, unabhängig) | 🔲 |
| 3 | [#87](https://github.com/pgm1980/mutmut-win/issues/87) | Bug | Rendering: `show`-Forensik-Panel + Browser-IL-Awareness (Emoji/Spalte/Filter/match aus constants abgeleitet) | UI-004 (S2), UI-008 (S2) | 5 | Must | 3 | 🔲 |
| 4 | [#88](https://github.com/pgm1980/mutmut-win/issues/88) | Bug | Classifier-Ehrlichkeit Windows: PYTHONUNBUFFERED-Output-Signal, neutraler Status, Confidence-Cap, alle Guards + Hygiene in einem Durchgang | JT-001/002 (S2), JT-009/010/011/015/018 (S3/S4), JT-012/014 (S4) | 8 | Must | 4 (NACH #85/#87: Verhaltensänderungen durch sichtbare Forensik debugbar) | 🔲 |
| 5 | [#89](https://github.com/pgm1980/mutmut-win/issues/89) | Spike | io_counters-Delta als Windows-Ersatz fürs Sleeping-Signal (timeboxed: Spike → Entscheid → Einbau ODER dokumentiertes Negativergebnis) | JT-001-Folge | 5 | Should | 5 | 🔲 |
| 6 | [#90](https://github.com/pgm1980/mutmut-win/issues/90) | Bug | Test-/Doku-Ehrlichkeit: Windows-realistische Fixtures, isolierter running_ratio-Test (POSIX-markiert), nüchterne Prosa | JT-016 (S4), EW-022-Doku | 3 | Should | 6 (ZULETZT — Fixtures spiegeln die finale Semantik) | 🔲 |

**Gesamt geplant:** 25 SP (Must 17, Should 8)

**Scope-Ventil:** #89/#90 rutschen bei Blowup nach Sprint 31. Die Must-Items
allein liefern persist + count + render + ehrliche Confidence.

---

## Sprint-Strategie

- **Ein Feature-Branch** `feature/v2.8.0-il-honesty`. Pro Issue TDD-Zyklus →
  Commit; Merge auf main bei Sprintende, Release v2.8.0.
- **Reihenfolge mit Absicht:** Persistenz vor Rendering (Rendering braucht
  Zeilen); beide vor dem Classifier-Umbau (#88), damit Verhaltensänderungen
  über die dann funktionierende Forensik-Pipeline beobachtbar sind statt
  blind. #90 zuletzt — Fixtures müssen die FINALE Semantik kodieren.
- **#88 ist Design-pflichtig (CLAUDE.md):** ≥ 10-Schritt-Sequential-Thinking-
  Session VOR der Implementierung (Signal-Gewichtung, Confidence-Semantik,
  BWC der Forensik-Felder, Plattform-Flag-Mechanik). Context7 für
  psutil-Detailfragen (io_counters/status-Semantik) PFLICHT vor Nutzung.
- **Kompatibilitäts-Fenster (Planungs-Erkenntnis):** Das Confidence-Capping
  ist NUR JETZT non-breaking — Forensik wurde nie persistiert, niemand kann
  von alten Confidence-Werten abhängen. Späteres Ändern wäre Breaking.
- **#89-Gate:** Spike mit echten Proben (sleep-wait vs busy-loop vs
  schreibender Prozessbaum); Negativergebnis wird im Audit-Doc dokumentiert —
  kein stilles Versanden.
- **#85-Rendering-Robustheit:** `show` muss mit `forensics IS NULL`
  (Prä-v2.8-Zeilen) sauber umgehen.

---

## Task Breakdown

### Item 1: #85 Forensik-Persistenz (2 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | Failing Test: TaskCompleted mit forensics-Dict → `load_results` liefert Forensik (Verdict-Felder + confidence im Roundtrip) | 🔲 |
| 1.2 | `_update_summary_and_persist`: `save_result(..., forensics=event.forensics)` | 🔲 |
| 1.3 | worker.py: `EXIT_CODE_INFINITE_LOOP`-Konstante statt Literal 38 (Import aus constants) | 🔲 |
| 1.4 | Gates (ruff/mypy/Suite) | 🔲 |

### Item 2: #86 CICD-IL-Bucket (2 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing Test: `[(killed),(killed_by_infinite_loop),(survived)]` → CICD-Score == results-Score (66,7 %) | 🔲 |
| 2.2 | `compute_cicd_stats`: IL-Case → killed (+ explizites `killed_by_infinite_loop`-Zählfeld im JSON) | 🔲 |
| 2.3 | Drei-Kanal-Konsistenztest (run-Gate, results, export) auf identischer Datenlage | 🔲 |
| 2.4 | Gates | 🔲 |

### Item 3: #87 Rendering (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing Tests: `show` rendert Panel (verdict/confidence/cpu/output/ratio/samples/tail) bei vorhandener Forensik; bleibt still/sauber bei NULL | 🔲 |
| 3.2 | cli `show`: Forensik-Block aus DB-Zeile rendern | 🔲 |
| 3.3 | Browser: `killed_by_infinite_loop` in Emoji-Map/Spalten/Filter/match — abgeleitet aus `constants.py` statt duplizierter Literal-Map (UI-008-Wurzel) | 🔲 |
| 3.4 | Failing Browser-Tests: IL-Mutant erscheint als Kill (Filter), Spaltensumme == Total, Detail-Text korrekt | 🔲 |
| 3.5 | Gates | 🔲 |

### Item 4: #88 Classifier-Ehrlichkeit (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | **≥ 10-Schritt-CoT-Design** (Signal-Matrix, Confidence-Semantik, Forensik-Felderweiterung `sampler_errors`/`status_signal_used`, Plattform-Mechanik) | 🔲 |
| 4.2 | Failing Tests entlang des Designs (deterministische Sample-Fixtures, win32-Pfad) | 🔲 |
| 4.3 | Worker-Env: `PYTHONUNBUFFERED=1` für den pytest-Subprozess (Output-Signal real) | 🔲 |
| 4.4 | classify_samples: running_ratio plattformneutral; Confidence-Cap „medium" bei 2-Signal-Verdict | 🔲 |
| 4.5 | Guards: Mindest-Sample-Floor (JT-009); `output_threshold gt=0` (JT-010); run()-Catch-All + `sampler_errors`-Forensikfeld (JT-011); stat-Fehler → unknown statt 0 (JT-015); window<timeout/2-Hinweis (JT-018) | 🔲 |
| 4.6 | Hygiene: `super().__init__(daemon=True)` (JT-012); Snapshot VOR Log-Tail-Read (JT-014) | 🔲 |
| 4.7 | Gates + Audit-Doc-Nachtrag (welche Findings damit zu) | 🔲 |

### Item 5: #89 io_counters-Spike (5 SP, timeboxed)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Spike-Skript (gitignored `_issues/`): io_counters-Deltas für sleep-wait / busy-loop / IO-schreibenden Baum messen | 🔲 |
| 5.2 | Entscheid (kurze CoT ≥ 3): Signal tauglich? Schwellen? | 🔲 |
| 5.3a | JA-Pfad: als viertes Signal in classify + Forensik + Tests | 🔲 |
| 5.3b | NEIN-Pfad: Negativergebnis im Audit-Doc dokumentieren | 🔲 |

### Item 6: #90 Test-/Doku-Ehrlichkeit (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Fixtures auf Windows-realistisch (status „running"); status-abhängige Tests plattform-markiert; isolierter running_ratio-Test (POSIX-Semantik) | 🔲 |
| 6.2 | Integration-IL-Tests gegen finale Semantik reviewen | 🔲 |
| 6.3 | Doku nüchtern: Modul-Docstring-Marketing raus; README-IL-Absatz an reale Signal-Lage angleichen | 🔲 |
| 6.4 | Gates | 🔲 |

---

## Out of Scope (Roadmap unverändert)

- C6+C7 (Sprint 31 / v2.9.0), C8+C9-Top (Sprint 32 / v2.10.0)
- OS-014 (`--output json` ohne score) — C7
- pip-audit-Baseline (Umgebungs-SSL)

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 681 + neue ≥ 700 passed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 Findings |
| Architecture | lint-imports (läuft in der Suite) | KEPT |
| Mutation Testing | — | deferred bis C8 (Sprint 32) |

---

## Release v2.8.0

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.8.0 (`uv lock --system-certs`) | 🔲 |
| Annotated Tag v2.8.0 | 🔲 |
| GitHub Release v2.8.0 (Changelog: Forensik sichtbar, Score konsistent, Confidence ehrlich) | 🔲 |
| Auto-close #85–#90 via Merge-Commit | 🔲 |
| MEMORY.md + product_backlog.md update | 🔲 |
