# Sprint 35 Backlog — v2.13.0 „Maintenance 3: External QA"

**Sprint-Ziel:** Unterbrechung der Entwicklungspause auf User-Entscheid:
Ein externer 360°-QA-Report gegen v2.12.0 (paralleles Testmanagement-
Projekt; archiviert als
`_docs/audit/external_qa_report_v2.12.0.md`) lieferte 15 Findings
(6 Medium, 9 Low) — **alle 15 von der Hauptsession am Code verifiziert,
keine Falschmeldung**. Jedes Finding endet in diesem Sprint als Fix;
Doku-Lösungen nur, wo das Finding selbst ein Doku-Finding ist
(DOC-001, DOC-002). Danach kehrt das Projekt in die dokumentierte
Pause zurück.

**User-Entscheidungen (2026-06-12):** (1) Sprint öffnen. (2) RUN-001
als FEATURE (Result-Reuse, Option b) statt Doku-Rückzug. (3) Intake:
`_bug_reports/` → .gitignore, nur der Report nach `_docs/audit/`.
(4) SCO-002: `skipped` bekommt einen echten Producer.

**Branch:** `feature/v2.13.0-maintenance-3` · **Release:** v2.13.0
(nur auf explizites User-„Release") · **Danach:** zurück in die
Entwicklungspause

**Planungs-CoT:** 10 Schritte (nextgen-cot) — Bündelung nach
Vertragsthemen, Reihenfolge-Begründung (Purge-Fix #120 VOR
Reuse-Feature #119, Reuse VOR skipped-Producer #122), RUN-001-
Design-Skizze (Fast-Path + Config-Fingerprint + tests_fingerprint +
wiederverwendbare Verdicts; timeout/suspicious/no-tests/unchecked nie),
SCO-002-Producer-Entscheid (Filter-Subset-Läufe, nie Verdicts
überschreiben), Risiken (DB-Migration, Score-Verschiebung durch
f-String-Surface, is_full_run-Normalisierung), Messziele inkl.
Reuse-Demo.

---

## Ausgewählte Items (= alle 15 Report-Findings)

| # | Issue | Findings | SP | Priorität | Reihenfolge | Status |
|---|-------|----------|----|-----------|-------------|--------|
| 1 | [#118](https://github.com/pgm1980/mutmut-win/issues/118) | DOC-001 + Report-Intake | 1 | Must | 1 | 🔲 |
| 2 | [#120](https://github.com/pgm1980/mutmut-win/issues/120) | RUN-002, CLI-002, CLI-001, CFG-001 | 5 | Must | 2 (vor #119: Purge-Semantik) | 🔲 |
| 3 | [#119](https://github.com/pgm1980/mutmut-win/issues/119) | RUN-001 → **Result-Reuse-Feature** | 8 | Must | 3 (Design-CoT ≥ 8) | 🔲 |
| 4 | [#122](https://github.com/pgm1980/mutmut-win/issues/122) | SCO-002-Producer, SCO-001, SCO-003 | 5 | Must | 4 (nach #119: Reuse-Interaktion) | 🔲 |
| 5 | [#121](https://github.com/pgm1980/mutmut-win/issues/121) | MUT-001, MUT-002 | 5 | Must | 5 | 🔲 |
| 6 | [#123](https://github.com/pgm1980/mutmut-win/issues/123) | CLI-003, CFG-002, DOC-002, WIN-001 | 5 | Should | 6 | 🔲 |
| — | — | Gate: Abschluss-Dogfooding (Pilot ≥ 80 %) + **Reuse-Demo** (Lauf B dispatcht 0) | — | — | 7 | 🔲 |

**Gesamt geplant:** 29 SP (Must 24, Should 5)

**Kein Auswahl-Ventil** (Final-Sweep-Disziplin). Zwei vorab fixierte
Begrenzungen: MUT-001-Literal-Part-Mutation nur bei positivem
Design-Entscheid (Format-Specs dürfen nicht brechen); DOC-002 bleibt
Doku-Fix (do_not_copy-Feature = bewusstes Won't-Do im Issue).

---

## Sprint-Strategie

- **Report = Arbeitsvorrat:** Die Repro-Projekte des Reports
  (refproj/operators/statuses/edgecases, inkl. eigener venvs) bleiben
  unversioniert (`_bug_reports/` in .gitignore) als manuelle Referenz;
  unsere Fixes bekommen EIGENE In-Repo-Regressionstests.
- **#119-Designkern (Detail-CoT ≥ 8 bei Implementierung):**
  Reuse-Bedingung = Datei nahm Fast Path (Quell-Fingerprint #101)
  ∧ Config-Fingerprint unverändert ∧ zugeordnete Testmenge unverändert
  (neue DB-Spalte `tests_fingerprint`, #100-tolerante Migration)
  ∧ Verdict ∈ {killed, survived, segfault, killed_by_infinite_loop,
  caught by type check}. timeout/suspicious (umgebungssensitiv),
  no tests (#106 verdiktet je Lauf frisch) und unchecked nie.
  `--rerun-all` als Opt-out; Reuse-Ausweis in der Summary.
- **#122-Producer-Semantik:** `skipped` = „existiert in der Staging,
  vom Namens-Filter dieses Laufs ausgeschlossen, KEINE bestehende
  DB-Row" — echte Verdicts werden nie überschrieben (#96-Regel).
- **#120-Normalisierung:** `--paths-to-mutate`-Override zählt als
  Subset-Lauf (Purge aus), außer er ist set-gleich (normcase) mit der
  konfigurierten Fläche. Zu selten purgen ist safe, zu oft war der Bug.
- **Score-Verschiebungen kommunizieren** (Changelog v2.13.0): neue
  f-String-Return-Mutanten vergrößern die Surface; `skipped` wird
  erreichbar (Nenner-Formel unverändert — skipped wurde schon immer
  subtrahiert).

---

## Task Breakdown

### Item 1: #118 Intake + DOC-001 (1 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | User-Hotfix committen (README + CLAUDE.md: Git-Installationskanal) | 🔲 |
| 1.2 | `.gitignore` + Report-Archiv `_docs/audit/external_qa_report_v2.12.0.md` | 🔲 |

### Item 2: #120 CLI/Config-Vertrag (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing Tests: Pfad-Subset-Lauf erhält fremde DB-Rows; nonexistenter Pfad → exit 2; min-score 150/−5 → exit 2; kaputte TOML → exit 2 kompakt (kein Traceback) | 🔲 |
| 2.2 | Implementierung: is_full_run-Normalisierung; Upfront-Validierungen; run via `_load_config_or_exit` | 🔲 |
| 2.3 | Gates | 🔲 |

### Item 3: #119 Result-Reuse (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | **Design-CoT (≥ 8):** Reuse-Bedingungsmatrix, tests_fingerprint-Quelle, Migrationspfad, Accounting/Sum-Invariante, Interrupt-Verhalten | 🔲 |
| 3.2 | Failing Tests: Bedingungsmatrix (Unit); E2E unverändert → 0 dispatcht + identische Buckets + Reuse-Zeile; Datei geändert → nur deren Mutanten; Test geändert → betroffene re-run; --rerun-all; Alt-DB lesbar, Reuse aus | 🔲 |
| 3.3 | DB-Migration (tests_fingerprint) nach #100-Muster | 🔲 |
| 3.4 | Orchestrator-Implementierung + Summary-Ausweis | 🔲 |
| 3.5 | Gates | 🔲 |

### Item 4: #122 Score/Status (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | Failing Tests: Subset-Lauf → skipped-Rows nur ohne Bestands-Row; Drei-Kanal-Konsistenz mit skipped > 0; Export-Zeile scoreable-Nenner; results mit Type-check-Zeile | 🔲 |
| 4.2 | Implementierung: skipped-Producer im Orchestrator; cli-Export-Zeile; results-Rendering (Pins wandern) | 🔲 |
| 4.3 | Gates | 🔲 |

### Item 5: #121 Mutationsoberfläche (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Failing Tests: f-string-only-Funktion erhält Return-None-Mutant + Trampolin; U+01C1-Datei mutiert Nachbarfunktion, Warnung nennt Mangling-Limitation | 🔲 |
| 5.2 | Design-Entscheid Literal-Part-Mutation (FormattedStringText) — Umsetzung nur bei sauberem Spec-Schutz | 🔲 |
| 5.3 | Implementierung node_mutation/mutation/file_setup | 🔲 |
| 5.4 | Gates | 🔲 |

### Item 6: #123 Robustheit & Windows (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Failing Tests: apply-Staleness → Einzeiler exit 1; do_not_mutate-no-match → Warnung; Worker-Spawn-Pin (SetErrorMode/creationflags win32) | 🔲 |
| 6.2 | Implementierung: StaleStagingError; Warnung; WER-Unterdrückung; README-Staging-Absatz (DOC-002) | 🔲 |
| 6.3 | Gates | 🔲 |

### Abschluss: Dogfooding + Doku

| Task | Beschreibung | Status |
|------|-------------|--------|
| A.1 | Pilot (gleiche Module, `--force`) — Gate ≥ 80 % | 🔲 |
| A.2 | **Reuse-Demo:** Pilot-Lauf B unverändert → 0 dispatchte Tasks, identische Buckets (RUN-001-Report-Repro) | 🔲 |
| A.3 | pip-audit-Versuch (Ergebnis oder dokumentierte Limitation) | 🔲 |
| A.4 | Implementation-complete-Commit; Release wartet auf User-„Release" | 🔲 |

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest` | 951 + neue, 0 failed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Format | `uv run ruff format --check src/ tests/` | 0 zu formatieren |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors (Baseline 14, darf nur sinken) |
| Security | `semgrep scan --config auto src/mutmut_win/ tests/` | 0 Findings |
| Architecture | lint-imports in-suite (inkl. Artefakt) | KEPT überall |
| Mutation | Pilot ≥ 80 % + **Reuse-Demo (0 dispatcht bei Lauf B)** | dokumentiert |
| Report-Abdeckung | — | **15/15 Findings geschlossen** |

---

## Release v2.13.0 (nur auf explizites User-„Release")

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.13.0 (`uv lock --system-certs`) | 🔲 |
| README/Install-Guide-Versionspins auf v2.13.0 | 🔲 |
| Annotated Tag v2.13.0 | 🔲 |
| GitHub Release (Changelog: External QA, Result-Reuse, Score-Verschiebungen, skipped erreichbar) | 🔲 |
| Auto-close #118–#123 via Merge | 🔲 |
| MEMORY.md + product_backlog.md + state.md: **zurück in die Entwicklungspause** | 🔲 |
