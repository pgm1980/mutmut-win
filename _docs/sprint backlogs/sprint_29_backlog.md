# Sprint Backlog — Sprint 29 (v2.7.0 Runtime Reliability)

**Projekt:** mutmut-win
**Sprint:** 29
**Sprint-Ziel:** Die letzten beiden S1-Findings des Audits (beide Abbruch-/Fehlerpfad-Hänger) eliminieren, die dreifach gebrochene Timeout-Architektur end-to-end reparieren, Prozess-Hygiene herstellen und die import-linter-Contracts per ADR an die reale Architektur angleichen. Release v2.7.0.
**Epic(s):** Epic 20 (Runtime Reliability) — neu
**Branch:** `feature/v2.7.0-runtime-reliability`
**Zeitraum:** 2026-06-11 – 2026-06-11
**Status:** ✅ Closed mit v2.7.0 Release (merge 7ef982f, bump d46f4db, Tag v2.7.0 — alle 6 Items, 27/27 SP, Velocity 100 %; Issues #79–#84 auto-closed). **Alle 15 S1-Audit-Findings sind geschlossen.**

**Grundlage:** Sprint-27-Audit (`_docs/audit/sprint_27_audit_findings.md`),
Fix-Cluster **C3 + C4** + lint-imports-Nachtrag aus Sprint 28. Nach diesem
Sprint sind **alle 15 S1-Findings** des Audits geschlossen.

---

## Findings-Restbestand (Kontext)

Audit gesamt: ~180 unique Findings. Nach Sprint 28 (22 erledigt, 13/15 S1)
verbleiben ~158. Dieser Sprint adressiert C3+C4 (~17 Findings, inkl. der
letzten 2 S1). Roadmap für den Rest: Sprint 30 = C5 (IL-Detection ehrlich,
v2.8.0), Sprint 31 = C6+C7 (tote Features + Score-Integrität, v2.9.0),
Sprint 32 = C8+C9-Top (Pipeline-Hygiene + UX, v2.10.0) — siehe
product_backlog Release-Übersicht. Nicht zugeordnete S4 bleiben im
Audit-Register und werden opportunistisch miterledigt.

---

## Ausgewählte Items

| # | Issue | Typ | Titel | Findings | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----------|----|-----------|-------------|--------|
| 1 | [#79](https://github.com/pgm1980/mutmut-win/issues/79) | Bug | Shutdown-Hänger: Queues nie geschlossen + fehlendes finally um die Event-Loop | EW-001 (S1), EW-017 | 3 | Must | 1 (klein, entschärft jeden Abbruch sofort) | ✅ 4257f3c |
| 2 | [#80](https://github.com/pgm1980/mutmut-win/issues/80) | Bug | Worker-Liveness in get_events: harter Worker-Tod hängt den Lauf nicht mehr | EW-002 (S1), EW-012 | 5 | Must | 2 (letzter S1) | ✅ 0a06b3d |
| 3 | [#82](https://github.com/pgm1980/mutmut-win/issues/82) | Bug | Prozess-Hygiene: kill-tree-Fix, Log-Sweep, Worker via sys.executable | EW-007, EW-008, QX-008 | 5 | Must | 3 | ✅ a2f6037 (Design-Upgrade: per-Task-Job-Object — ppid-Scan kann tote Zwischenglieder nicht überbrücken, empirisch belegt) |
| 4 | [#81](https://github.com/pgm1980/mutmut-win/issues/81) | Bug | Per-Task-Timeouts end-to-end; WallClockTimeout-Totcode entfernen; IL-Fenster durchreichen | JT-003 (≡EW-003/QX-002), EW-009, EW-013/JT-008, EW-014 | 8 | Must | 4 (größtes Stück) | ✅ a955b89 (−464 Zeilen toter Code) |
| 5 | [#83](https://github.com/pgm1980/mutmut-win/issues/83) | Bug | Job-Object-Polish: use_last_error, argtypes, Least-Privilege, Assign-Race-Doku | JT-005, JT-006, JT-017, EW-018/JT-007 (Doku) | 3 | Should | 5 | ✅ c781d62/3b9512e (paralleler Worktree-Subagent, Hauptsession-verifiziert) |
| 6 | [#84](https://github.com/pgm1980/mutmut-win/issues/84) | Task | import-linter-Contracts per ADR an die reale Architektur angleichen | Sprint-28-Nachtrag | 3 | Should | 6 | ✅ 243206a (ADR + Contract KEPT + Gate läuft in pytest) |

**Gesamt geplant:** 27 SP (Must 21, Should 6)

**Scope-Ventil:** #83/#84 rutschen bei Blowup nach Sprint 30 — die
Must-Items allein schließen beide S1 und die Timeout-Architektur.

---

## Sprint-Strategie

- **Ein Feature-Branch** `feature/v2.7.0-runtime-reliability`. Pro Issue:
  TDD-Zyklus → Commit. Merge-Commit auf main bei Sprintende, Release v2.7.0.
- **Test-Strategie C3 (neu, weil Multi-Prozess):** Hänger-Regressionen
  brauchen echte Pool-Läufe — deterministische Integration-Tests
  (`@pytest.mark.integration`, ggf. `slow`) mit Mini-Fixture-Suiten in
  %TEMP%-Sandboxen und **hartem Außen-Timeout** im Test selbst
  (`subprocess`-getriebener Pool + watchdog), damit eine Regression als
  Test-FAIL statt als CI-Hänger endet. Kill-Szenarien via
  `proc.kill()`/`taskkill` auf echte Worker-PIDs.
- **#81-Designentscheidung (vorab fixiert):** Der Worker-seitige
  `proc.wait(timeout=task.timeout_seconds)` ist die funktionierende
  Architektur; `WallClockTimeout`/`TaskTimedOut` werden ENTFERNT statt
  verdrahtet (toter Code mit drei dokumentierten Landminen — EW-013/JT-008;
  ein zweiter Monitor wäre eine Doppelstruktur). README-Architektur-Sektion
  („Wall-Clock Timeout via monitor thread") wird entsprechend korrigiert.
- **#84 ist ADR-pflichtig** (CLAUDE.md): Architektur-Entscheidung mit
  Sequential-Thinking-Analyse (≥ 10 Schritte), Optionen: models/constants
  (+config?) als Basis-Layer UNTER process; `:`-Siblings für gewollte
  Same-Layer-Importe (cli:browser, orchestrator:runner:mutant_diff,
  mutation:node_mutation:trampoline). Contract muss danach im Sprint-Gate
  WIRKLICH laufen.

---

## Task Breakdown

### Item 1: #79 Shutdown-Hänger (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | Failing Integration-Test: Pool mit gefüllter task_queue, Abbruch → Prozess endet binnen Frist (Watchdog), keine Orphans | ✅ |
| 1.2 | `shutdown()`: `cancel_join_thread()` + `close()` auf beiden Queues; Kill→Join-Reihenfolge an Docstring angleichen (EW-017) | ✅ |
| 1.3 | `orchestrator.run()`: try/finally um die Event-Loop → shutdown läuft auch im Exception-Pfad | ✅ |
| 1.4 | Ruff + mypy clean; full suite | ✅ |

### Item 2: #80 Worker-Liveness (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing Integration-Test: Worker hart killen (taskkill) → Lauf endet, betroffener Task als „suspicious/worker died", übrige Tasks abgearbeitet | ✅ |
| 2.2 | `get_events()`: `event_queue.get(timeout=N)`-Schleife + `is_alive()`-Sweep toter Worker | ✅ |
| 2.3 | Synthetisches Completion-Event für in-flight Tasks toter Worker (Status „suspicious", aussagekräftige last_output-Notiz) | ✅ |
| 2.4 | EW-012: „unknown"-Recovery-Events nicht mehr als Mutant-Zeile persistieren (zählen + loggen) | ✅ |
| 2.5 | Stretch (wenn Zeit): ein Respawn-Versuch pro Slot | ✅ |
| 2.6 | Gates | ✅ |

### Item 3: #82 Prozess-Hygiene (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing Tests: kill-tree bei bereits beendetem Parent killt Kinder trotzdem (Sandbox-Prozessbaum); Startup-Sweep entfernt mutmut_out_*/mutmut_tests_*-Altlasten | ✅ |
| 3.2 | `_kill_proc_tree`: Early-Return entfernen, Kinder immer enumerieren+killen (TOCTOU-bewusst: zweiter Sweep) | ✅ |
| 3.3 | Pool-Start: Altlasten-Sweep in mutants/ | ✅ |
| 3.4 | Worker: `[sys.executable, "-m", "pytest", …]` statt bare `"pytest"` (QX-008) | ✅ |
| 3.5 | Gates | ✅ |

### Item 4: #81 Timeout-Architektur (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | Failing Tests: Worker nutzt `task.timeout_seconds` (Mock-Popen prüft wait-timeout); Multiplier wirkt multiplikativ end-to-end (Config-Roundtrip auf Task-Ebene) | ✅ |
| 4.2 | worker.py: flat-60s-Berechnung entfernen, `task["timeout_seconds"]` lesen (Fallback 60 nur wenn Feld fehlt — BWC alte Queues) | ✅ |
| 4.3 | `WallClockTimeout` + `TaskTimedOut`-Orchestrator-Zweig + Modell entfernen; zugehörige Unit-Tests entfernen/ersetzen; `process/__init__`-Exporte bereinigen | ✅ |
| 4.4 | EW-009: `infinite_loop_window_seconds`/Poll-Intervall an ProcessMonitor durchreichen (Forensik berichtet echtes Fenster) | ✅ |
| 4.5 | EW-014: `_read_last_lines` als Tail-Read (seek ans Ende, letzter Block) statt read_text | ✅ |
| 4.6 | README-Architektur-Sektion korrigieren (Timeout-Mechanik beschreibt jetzt Worker-seitiges wait) | ✅ |
| 4.7 | Gates | ✅ |

### Item 5: #83 Job-Object-Polish (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Failing Test: provozierter Win32-Fehler liefert echten Fehlercode in der OSError-Message (nicht 0) | ✅ |
| 5.2 | `WinDLL("kernel32", use_last_error=True)` + argtypes/restype (wintypes.HANDLE/BOOL/DWORD) | ✅ |
| 5.3 | Zugriffs-Maske auf PROCESS_SET_QUOTA \| PROCESS_TERMINATE; Docstrings (RuntimeError, CloseHandle-Fehlerpfad) | ✅ |
| 5.4 | Assign-Race-Kommentar (EW-018/JT-007): dokumentieren, dass der Launcher-Schutz aktuell an uvs eigenem Job hängt | ✅ |
| 5.5 | Gates | ✅ |

### Item 6: #84 import-linter-ADR (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Sequential-Thinking-Analyse (≥ 10 Schritte): Layer-Schnitt-Optionen bewerten | ✅ |
| 6.2 | ADR-Dokument `_docs/architecture spec/adr_layer_contracts_v2.md` | ✅ |
| 6.3 | pyproject-Contracts gemäß ADR (Basis-Layer + `:`-Siblings); `uv run lint-imports` → 0 Verletzungen | ✅ |
| 6.4 | lint-imports in die Sprint-Gate-Checkliste als WIRKLICH ausgeführtes Gate | ✅ |

---

## Out of Scope (Roadmap Sprints 30–32)

- **C5 IL-Detection** (Sprint 30 / v2.8.0): JT-001/002/004, UI-004/008,
  OS-002, JT-009/010/011, EW-010, JT-015/016/018
- **C6 tote Features + C7 Score-Integrität** (Sprint 31 / v2.9.0):
  CM-002/003/008/010/011, OS-003/009/010, EW-004, OS-005/012/014, UI-009,
  QX-007/025
- **C8 Pipeline-Hygiene + C9-Top** (Sprint 32 / v2.10.0): OS-006/007/008/013,
  FD-001…011, CM-004/005/006/009, RN-001…005, EW-005/006/015/023, QX-001/003,
  Regex-Polish F6 — schaltet das Dogfooding-Gate wieder frei
- pip-audit-Baseline (Umgebungs-SSL; `--system-certs`-Hinweis in MEMORY.md)

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung | Ergebnis (2026-06-11) |
|------|--------|-----------|------------------------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 672 + neue ≥ 690 passed | ✅ **681 passed / 4 skipped** (netto: +29 neue Tests, −14 mit dem toten Monitor entfernt; inkl. lint-imports-Gate-Test) |
| Hänger-Regression | neue Integration-Tests (#79/#80) mit Watchdog | enden in Frist, kein CI-Hänger | ✅ Watchdog-Test fiel von 30-s-Timeout (rot, EW-001 live) auf Sofort-Exit |
| Linting | `uv run ruff check src/ tests/` | 0 Findings | ✅ All checks passed |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors | ✅ 26 vorbestehende Altlasten unverändert, 0 neue (worker/executor/job_object sogar 0 gesamt) |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 Findings | ✅ 0 Findings |
| Architecture | `uv run lint-imports` | **0 Verletzungen (nach #84 wieder scharf)** | ✅ **KEPT (1 kept, 0 broken)** + Gate läuft jetzt IN der pytest-Suite (test_import_linter_contracts_hold) |
| Mutation Testing | — | weiterhin deferred bis C8 (Sprint 32) | ⏭️ wie geplant deferred |

---

## Release v2.7.0

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.7.0 (`uv lock --system-certs`) | ✅ d46f4db (`mutmut-win --version` → 2.7.0 verifiziert) |
| Annotated Tag v2.7.0 | ✅ |
| GitHub Release v2.7.0 (Changelog: beide S1-Hänger zu, echte per-Task-Timeouts, Prozess-Hygiene, Contracts scharf) | ✅ https://github.com/pgm1980/mutmut-win/releases/tag/v2.7.0 |
| Auto-close #79–#84 via Merge-Commit | ✅ verifiziert: 0 offene Issues |
| MEMORY.md + product_backlog.md update | ✅ |
