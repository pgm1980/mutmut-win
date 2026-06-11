# Sprint 31 Backlog — v2.9.0 „Feature Truth & Score Integrity"

**Sprint-Ziel:** Die beiden tot beworbenen Features (Type-Check-Filter,
Coverage-Gating) werden ehrlich — repariert end-to-end oder sauber
deaktiviert — und die Score-Pipeline wird lückenlos wahr: vollständige
Buckets, korrekte Exit-Code-Map, CI-erkennbarer Abbruch, kommunizierender
JSON-Kanal.

**Basis:** Audit-Cluster **C6 + C7** (`_docs/audit/sprint_27_audit_findings.md`).
Alle Findings wurden bei der Planung am v2.8.0-Stand re-verifiziert
(type_checking.py, orchestrator Step 1b/Summary, constants, code_coverage.py,
cli run/results). OS-002 ist bereits zu (#86, Sprint 30).

**Branch:** `feature/v2.9.0-score-integrity` · **Release:** v2.9.0 (nur auf
explizites User-„Release")

**Planungs-CoT:** 12 Schritte (Sequential Thinking, abgeschlossen) — Kette
Map→Buckets→Härtung→E2E→Abbruch→Entscheide, Exit-2-Abwägung (A/B/C),
Summen-Invariante, Timebox-Logik für Coverage, Scope-Ventil.

---

## Ausgewählte Items

| # | Issue | Typ | Titel | Findings | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----------|----|-----------|-------------|--------|
| 1 | [#91](https://github.com/pgm1980/mutmut-win/issues/91) | Bug | Status-Wahrheit: Exit-Code-Map + vollständige Summary-Buckets + vollständiges results-Rendering | EW-020 (S4), QX-025 (S4), EW-004 (S2), UI-009 (S3) | 5 | Must | 1 (Fundament — alle Folge-Items konsumieren die Map) | 🔲 |
| 2 | [#92](https://github.com/pgm1980/mutmut-win/issues/92) | Bug | type_checking.py härten: Checker-Erkennung (Windows-Formen), Subprozess-Robustheit, Severity-Filter | CM-008 (S2), CM-010 (S3), CM-011 (S3) | 5 | Must | 2 (pur, unabhängig; VOR #93 — dessen E2E braucht die Erkennung) | 🔲 |
| 3 | [#93](https://github.com/pgm1980/mutmut-win/issues/93) | Bug | Type-Check-Filter end-to-end: kanonisches Matching, Task-Schnittmenge, DB-Persistenz, Leerheits-Guard | CM-002 (S2), OS-003 (S2), OS-009 (S2), OS-010 (S2) | 8 | Must | 3 (NACH #91+#92) | 🔲 |
| 4 | [#94](https://github.com/pgm1980/mutmut-win/issues/94) | Bug | Ctrl-C-Ehrlichkeit: was_interrupted, unchecked-Bucket, Exit 130, Gate-Skip | OS-005 (S2) | 3 | Must | 4 (im Modellfenster von #91) | 🔲 |
| 5 | [#95](https://github.com/pgm1980/mutmut-win/issues/95) | Spike+Fix | Coverage: timeboxed Spike → Entscheid → Einbau ODER ehrliche Deaktivierung | CM-003/OS-011 (S2), CM-013 (S3) | 5 | Must (der ENTSCHEID, nicht der Einbau) | 5 | 🔲 |
| 6 | [#96](https://github.com/pgm1980/mutmut-win/issues/96) | Bug | DB-Orphan-Zeilen: results meldet Vereinigungsmenge aller Läufe ever | OS-012 (S2, Orphan-Teil) | 5 | Should | 6 | 🔲 |
| 7 | [#97](https://github.com/pgm1980/mutmut-win/issues/97) | Bug | CI-Kanal: score im JSON, 0-Mutanten-Kommunikation beim Gate | OS-014 (S3), OS-026 (S4) | 2 | Should | 7 (ZULETZT — serialisiert die finale Modellform) | 🔲 |

**Gesamt geplant:** 33 SP (Must 26, Should 7)

**Scope-Ventil:** #96/#97 rutschen bei Blowup nach Sprint 32. #95 weicht bei
Timebox-Riss im JA-Pfad auf die ehrliche Deaktivierung aus (Einbau dann als
eigenes Sprint-32-Item) — der Sprint ist in jedem Ausgang abschließbar.

---

## Sprint-Strategie

- **Ein Feature-Branch** `feature/v2.9.0-score-integrity`. Pro Issue
  TDD-Zyklus → Commit; Merge auf main bei Sprintende, Release v2.9.0 nur auf
  explizites User-„Release".
- **Reihenfolge mit Absicht:** Exit-Code-Map zuerst — Summary, results,
  Browser, CICD und DB konsumieren sie; jede spätere Korrektur müsste sonst
  doppelt angefasst werden. Härtung (#92) vor End-to-End (#93), weil der
  E2E-Test eine Erkennung braucht, die das Test-Env-mypy (uv-Pfadform!)
  überhaupt erkennt. #97 zuletzt — das JSON ist ein CI-Vertrag und friert
  die Modellform ein.
- **Design-Entscheide mit CoT-Pflicht (CLAUDE.md):**
  - #91 Exit-2-Semantik (≥3 Schritte): Default-Richtung `2 → killed`
    (Collection-Error durch Mutant = beobachtbare Verhaltensänderung;
    Worker-Ctrl-C ist bei uns strukturell vom Orchestrator-Pfad getrennt),
    Forensik über persistiertes `last_output` statt neuem Status. Option B
    (eigener Status) bleibt bis zur Implementierung offen.
  - #95 Coverage-Entscheid (≥8 Schritte): Kernfrage ist das
    Zeilen-Referenzsystem (Coverage misst trampolinisierte mutants/-Kopien,
    der Generator filtert gegen Original-Zeilen). Spike klärt empirisch.
  - #96 Orphan-Design (≥8 Schritte): Tendenz Purge-bei-Voll-Lauf mit
    striktem Subset-Guard (destruktiv → Tests zuerst); Alternativen
    run_epoch-Spalte / Live-Schnittmenge im Entscheid dokumentieren.
- **Context7-Pflicht:** #92 mypy `--output=json`-Feldsemantik +
  pyright `--outputjson`-Schema VOR Implementierung; #95 coverage-API
  (data_file-Laden, lines()-Semantik).
- **Score-Korrekturen kommunizieren:** CM-002 entfernt Phantom-caught
  (Score kann sinken), EW-020/QX-025/EW-004 holen echte Kills in den
  Numerator (Score kann steigen). Changelog weist das als „score
  corrections" aus — Bugfixes, keine Breaking Changes, aber CI-Gates
  können kippen.
- **Summen-Invariante als Test:** Summe aller Buckets (+ unchecked) ==
  total_mutants — strukturelle Absicherung gegen künftige
  Schwarzloch-Regressionen; `_increment_summary` bekommt einen Catch-All
  (zählt suspicious + warnt) statt stiller Lücken.
- **OS-012 mtime-Teil** (Restore mit altem Timestamp übersieht
  Invalidierung) ist explizit NICHT in #96 — C8-Territorium
  (Cache-Hygiene), im Audit-Register vermerkt.

---

## Task Breakdown

### Item 1: #91 Status-Wahrheit (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | Design-CoT (≥3): Exit-2-Semantik final (Default: `2 → killed`, Forensik via last_output) | 🔲 |
| 1.2 | Failing Tests: constants-Map (kein doppelter Key, 0xC0000005 → Kill-Klasse, Exit-2-Entscheid kodiert); Summen-Invariante über alle Status | 🔲 |
| 1.3 | constants.py: `-24`-Dublette auflösen, 0xC0000005/3221225477 mappen, Exit-2-Entscheid umsetzen, Kommentare ehrlich (POSIX-Codes als solche markiert) | 🔲 |
| 1.4 | MutationRunResult: segfault/interrupted-Buckets (BWC-Defaults); Score-Numerator killed + type_check_caught + segfault; `_increment_summary` vollständig + Catch-All (suspicious + Warnung) | 🔲 |
| 1.5 | cli `results`: generisches Rendering aus Status-Liste (UI-009-Wurzel: handgepflegter Block) — alle Buckets > 0 sichtbar | 🔲 |
| 1.6 | Drei-Kanal-Konsistenz-Fixtures (#86) um segfault/Collection-Fälle erweitern; CICD-Export additiv ergänzen | 🔲 |
| 1.7 | Gates | 🔲 |

### Item 2: #92 type_checking.py härten (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | **Context7**: mypy-JSON-Felder (severity-Werte, Pfadform) + pyright-outputjson-Schema verifizieren | 🔲 |
| 2.2 | Failing Tests: Erkennung für `mypy.exe`, `.venv\Scripts\mypy.exe`, `uv run mypy`, `python -m mypy`; Crash-returncode → klare Meldung statt stiller 0-Filter; Warnings zählen nicht als Errors | 🔲 |
| 2.3 | Checker-Erkennung über Token-Basenames (Path.stem, casefold) statt Listen-Mitgliedschaft | 🔲 |
| 2.4 | subprocess.run: timeout (Modul-Konstante) + returncode-Prüfung (Checker-Crash ≠ „0 Findings") + `errors="replace"` | 🔲 |
| 2.5 | parse_pyright_report: severity=="error"-Filter (Vorbild parse_mypy_report) | 🔲 |
| 2.6 | Gates | 🔲 |

### Item 3: #93 Type-Check end-to-end (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing Unit-Tests fürs Matching: kanonische Namensfunktion — Checker-Pfadformen (relativ zu mutants/, absolut, Windows-Case) → exakt die Task-Namensform | 🔲 |
| 3.2 | `_filter_with_type_checker`: Pfad-Normalisierung (resolve + normcase + mutants-relativ) durch EINE gemeinsame Funktion mit der Task-Erzeugung | 🔲 |
| 3.3 | OS-009: `caught ∩ task_names` VOR Verbuchung | 🔲 |
| 3.4 | OS-003: `save_result(..., "caught by type check", 37)` je caught; `summary.type_check_caught` statt `killed` inkrementieren (Score-Property zählt beide — Emoji-Zeilen-Test anpassen) | 🔲 |
| 3.5 | OS-010: Leerheits-Guard nach Step 1b — 100 %-caught ist ein legitimer Erfolgslauf (Summary korrekt, kein IndexError) | 🔲 |
| 3.6 | E2E-Integrationstest (`@integration @slow`): Mini-Projekt + echtes mypy → caught == exakt erwarteter Mutant; results + CICD zeigen den Type-Check-Kill (Drei-Kanal) | 🔲 |
| 3.7 | Gates | 🔲 |

### Item 4: #94 Ctrl-C-Ehrlichkeit (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | Failing Tests: Interrupt-Lauf → `was_interrupted=True`, `unchecked == total - verarbeitete`, Score-Nenner ohne unchecked, Exit 130, min-score-Gate übersprungen | 🔲 |
| 4.2 | MutationRunResult: `was_interrupted: bool = False` + `unchecked: int = 0`; Summen-Invariante hält | 🔲 |
| 4.3 | Orchestrator-Interrupt-Pfad: Felder setzen; Summary druckt „checked N of M (interrupted)" | 🔲 |
| 4.4 | cli run: Exit 130 bei Interrupt; Gate-Skip mit klarer Meldung | 🔲 |
| 4.5 | Gates | 🔲 |

### Item 5: #95 Coverage-Entscheid (5 SP, timeboxed)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | **Context7**: coverage-API (Coverage(data_file=...), .load(), lines()) | 🔲 |
| 5.2 | Spike-Skript (`_issues/`): Subprozess-Brücke + Zeilen-Referenzsystem empirisch klären (trampolinisierte Kopie vs. Original-Zeilen) | 🔲 |
| 5.3 | **Entscheid-CoT (≥8)**: tragfähig? Aufwand? → JA/NEIN | 🔲 |
| 5.4a | JA: Brücke einbauen + CM-013 (normcase/resolve-Keying) + Tests | 🔲 |
| 5.4b | NEIN: ehrliche Deaktivierung — früher klarer Fehler bei gesetztem Flag, README/Config-Doku, Negativergebnis im Audit-Register (#89-Muster) | 🔲 |
| 5.5 | Gates | 🔲 |

### Item 6: #96 DB-Orphans (5 SP, Should)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | **Design-CoT (≥8)**: Purge-bei-Voll-Lauf (Tendenz) vs. run_epoch vs. Live-Schnittmenge | 🔲 |
| 6.2 | Failing Tests ZUERST (destruktive Operation!): Voll-Lauf purgt Orphans; Subset-Lauf (--mutant-names/--since-commit/paths-Override) purgt NICHTS | 🔲 |
| 6.3 | Implementierung + results-Verifikation (keine Geisterzeilen mehr) | 🔲 |
| 6.4 | mtime-Teil als C8-Verweis im Audit-Register dokumentieren | 🔲 |
| 6.5 | Gates | 🔲 |

### Item 7: #97 CI-Kanal (2 SP, Should, ZULETZT)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 7.1 | Failing Tests: `--output json` enthält score (+ neue Felder additiv); 0-Mutanten-Gate kommuniziert „failed closed" | 🔲 |
| 7.2 | MutationRunResult: computed_field/Serializer für score — NUR additiv (CI-Vertrag) | 🔲 |
| 7.3 | Gates | 🔲 |

---

## Out of Scope (Roadmap unverändert)

- C8+C9-Top (Sprint 32 / v2.10.0) — inkl. der 3 vorgemerkten
  Pipeline-Hygiene-Punkte (format-Gate, pytest-Kanon, semgrep-tests-Ignore)
  und des OS-012-mtime-Teils
- Mutation-Testing-Gate auf eigenen Code: deferred bis C8 (Stats-Mapping)
- pip-audit-Baseline (Umgebungs-SSL)

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 719 + neue ≥ 745 passed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors (26 pre-existing) |
| Security | `semgrep scan --config auto src/mutmut_win/` | 0 Findings |
| Architecture | lint-imports (läuft in der Suite) | KEPT |
| Mutation Testing | — | deferred bis C8 (Sprint 32) |

---

## Release v2.9.0 (nur auf explizites User-„Release")

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.9.0 (`uv lock --system-certs`) | 🔲 |
| Annotated Tag v2.9.0 | 🔲 |
| GitHub Release v2.9.0 (Changelog inkl. „score corrections"-Sektion) | 🔲 |
| Auto-close #91–#97 via Merge-Commit | 🔲 |
| MEMORY.md + product_backlog.md update | 🔲 |
