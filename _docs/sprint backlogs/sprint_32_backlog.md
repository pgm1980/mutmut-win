# Sprint 32 Backlog — v2.10.0 „Pipeline Hygiene"

**Sprint-Ziel:** Der letzte Audit-Sprint. Die Pipeline wird hygienisch:
Runner-Fehlschläge zeigen Output statt Schweigen und vergiften nie den
Stats-Cache, die DB übersteht Upgrades/Races/Exceptions, das Staging kann
weder entkommen (`..`) noch vergeistern (Deletion-Sync, Fingerprint),
Config/CLI validieren ehrlich, der JSON-Kanal ist rein — und das Projekt
wendet seine eigenen Regeln auf sich selbst an: Format-Gate, pytest-Kanon,
semgrep auf tests/, erstes echtes Dogfooding mit Mutation-Score.
Der Audit-Zyklus endet mit einem dokumentierten Schlussstrich statt Nebel.

**Basis:** Audit-Cluster **C8 + C9-Top** + 4 user-bestätigte Neuzugänge +
das seit Sprint 28 deferred Dogfooding-Gate. Schlüssel-Findings bei der
Planung am v2.9.0-Stand re-verifiziert (OS-006 leerer Cache-Overwrite,
FD-002 `..`-Escape; RN-002/FD-001/FD-006/CM-004/UI-006 aus den
Vorsprints am Code gesehen).

**Branch:** `feature/v2.10.0-pipeline-hygiene` · **Release:** v2.10.0
(nur auf explizites User-„Release")

**Planungs-CoT:** 12 Schritte — Schadensklassen-Ranking als Schnittkriterium,
Modul-kohärente Issues, Format-Commit ZUERST (Diff-Rauschen vor Logik),
Dogfooding als Schlussstein, C9-Rest als kuratierte Triage statt Versanden.

---

## Ausgewählte Items

| # | Issue | Typ | Titel | Findings | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----------|----|-----------|-------------|--------|
| 1 | [#98](https://github.com/pgm1980/mutmut-win/issues/98) | Hygiene+Gate | Selbst-Hygiene-Fundament + Dogfooding-Pilot (ZWEIPHASIG) | 3 Neuzugänge + Mutation-Gate | 5 | Must | **1a** (Phase 1: Format-Commit isoliert, pytest-Kanon, semgrep-Entscheid — definiert die Sprint-Gates) / **7** (Phase 2: Dogfooding nach #99) | 🔲 |
| 2 | [#99](https://github.com/pgm1980/mutmut-win/issues/99) | Bug | Runner-Diagnose & Stats-Wahrheit: Capture statt DEVNULL, Exit-Dekodierung, extra_paths, Cache nie vergiften | RN-001/002/003 (S2), OS-006/007 (S2), RN-008/009-Slices | 8 | Must | 2 (entsperrt Dogfooding) | 🔲 |
| 3 | [#100](https://github.com/pgm1980/mutmut-win/issues/100) | Bug | DB-Härtung: Lesepfad-Migration, Connection-Close, Migrations-Race, Surrogates | FD-001 (S2 ✅✅), FD-006 (S3 ✅✅, WinError 32 live), FD-007/011 (S3) | 5 | Must | 3 | 🔲 |
| 4 | [#101](https://github.com/pgm1980/mutmut-win/issues/101) | Bug | Staging-Hygiene: Containment, Deletion-Sync inkl. .meta-Orphans, Invalidierungs-Fingerprint, atomare .meta | FD-002/003 (S2), FD-004+OS-008, FD-005/009, CM-009≡FD-010 + OS-012-Reste | 8 | Must | 4 (schließt OS-012 KOMPLETT) | 🔲 |
| 5 | [#102](https://github.com/pgm1980/mutmut-win/issues/102) | Bug | Config-/CLI-Wahrheit: Override-Re-Validierung, Typo-Warnung, since-commit-Check, --debug real | CM-004/005/006 (S2), UI-005 (S2) + QX-023-Slice | 5 | Must | 5 | 🔲 |
| 6 | [#103](https://github.com/pgm1980/mutmut-win/issues/103) | Bug | CI-Output-Disziplin: reines JSON auf stdout, kein UnicodeEncodeError auf cp1252 | UI-006 (S2), QX-003 (S2) | 3 | Must | 6 (nach #102 — beide cli.py) | 🔲 |
| 7 | [#104](https://github.com/pgm1980/mutmut-win/issues/104) | Doku | C9-Rest-Triage: kuratierter Maintenance-Backlog + Audit-Schlussstrich | UI-007, QX-001/007, UI-010…016, QX-005/006/017–024, RN-006/007/010–013, FD-008 | 2 | Should | 8 (ZULETZT — dokumentiert den realen Endstand) | 🔲 |

**Gesamt geplant:** 36 SP (Must 34, Should 2)

**Scope-Ventil (großzügig — 36 SP ist Obergrenze):** #103 + #104 rutschen
bei Blowup (#104 notfalls in den Sprint-Abschluss integriert). #101 ist
intern teilbar: Kern = FD-002/005/009 + atomare .meta; zweite Hälfte =
Deletion-Sync + Fingerprint (wird bei Riss dokumentierter Rest).
v2.10.0 ist auch mit #98–#102 release-fähig.

---

## Sprint-Strategie

- **Ein Feature-Branch** `feature/v2.10.0-pipeline-hygiene`. Pro Issue
  TDD-Zyklus → Commit; Merge auf main bei Sprintende, Release v2.10.0 nur
  auf explizites User-„Release".
- **Format-Commit ZUERST und ISOLIERT (#98.1):** Der repo-weite
  `ruff format` über ~23 driftende Bestandsdateien ist der größte Diff des
  Sprints — er liegt VOR allen Logik-Items, sonst verschmilzt
  Format-Rauschen mit Logik-Diffs. Beweis der Reinheit: Diff ist
  whitespace/wrapping-only, volle Suite danach grün. Ab dann ist
  `ruff format --check src/ tests/` Gate.
- **Dogfooding als Schlussstein (#98.2, NACH #99):** Die Stats-Bugs
  (OS-006/RN-003) sind die seit Sprint 28 dokumentierte Blockade. Pilot:
  die zwei reinen Sprint-31-Module (`code_coverage.py`,
  `type_checking.py`). Akzeptanz = Lauf komplett + Score dokumentiert;
  ≥ 80 % auf den Piloten ODER surviving Mutants dokumentiert
  (CLAUDE.md-Regel). Was der Self-Run an Neuem ausgräbt, wird
  Maintenance-Issue — KEINE Sprint-Scope-Explosion (Timebox).
- **Design-CoTs (CLAUDE.md):** #101 ≥ 8 Schritte (Fingerprint-Signale:
  mtime+size+Config-Hash — welche Config-Teile; Speicherort; Full-Rebuild
  vs. Warnung. Deletion-Sync-Semantik: Quelle der Wahrheit, verwaltete vs.
  user-platzierte Artefakte). #99 ≥ 3 Schritte (Capture-Strategie:
  Tail-Capture à la `_read_last_lines` vs. capture_output —
  pytest-Output kann riesig sein).
- **Context7-Pflichten:** `sys.stdout.reconfigure(errors=…)`-Semantik
  (#103/QX-003), `difflib.get_close_matches` (#102/CM-005),
  `Path.replace`-Atomarität auf Windows (#101/CM-009).
- **Destruktiv-Disziplin (#101 Deletion-Sync):** wie #96 — Tests zuerst,
  nur verwaltete Artefakte unter mutants/, niemals außerhalb, sichtbares
  Log der gelöschten Anzahl.
- **CM-005 non-breaking:** Unbekannte Config-Keys WARNEN (mit
  difflib-Vorschlag), nicht verbieten — extra-Keys bleiben erlaubt.
- **Sequentiell in der Hauptsession.** #100/#101/#102 sind untereinander
  unabhängig — parallele Worktree-Subagenten wären möglich (CLAUDE.md
  isolation: worktree), aber bei drei kleinen Items überwiegt der
  Merge-/Verifikations-Overhead die Ersparnis. Option dokumentiert, falls
  vom User gewünscht.
- **Nach Sprint 32 ist der Audit-Zyklus formal beendet.** Der C9-Rest lebt
  als severity-sortierter Maintenance-Abschnitt im Product Backlog
  (epic-los) — kein still gebrochenes Sprint-Versprechen.

---

## Task Breakdown

### Item 1: #98 Selbst-Hygiene & Dogfooding (5 SP, zweiphasig)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | **Phase 1 (Sprint-Auftakt):** `ruff format src/ tests/` als isolierter Commit; Beweis: Diff format-only, Suite grün | 🔲 |
| 1.2 | pytest-Kanon: `collect_ignore_glob` in tests/conftest.py — `uv run pytest` läuft OHNE --ignore-Flag (Test: nackte Collection sammelt ohne Errors); CLAUDE.md-Kommandotabelle bleibt gültig | 🔲 |
| 1.3 | semgrep-Entscheid: explizite `.semgrepignore` (tests/ wird GESCANNT); Lauf auf src/ + tests/ dokumentiert; Entscheid im Backlog | 🔲 |
| 1.4 | **Phase 2 (nach #99):** Dogfooding-Pilot `uv run mutmut-win run --paths-to-mutate src/mutmut_win/code_coverage.py src/mutmut_win/type_checking.py` (Syntax prüfen) — Lauf komplett, Score erhoben | 🔲 |
| 1.5 | Score ≥ 80 % auf Piloten ODER surviving Mutants dokumentiert; Self-Run-Funde als Maintenance-Issues erfasst | 🔲 |
| 1.6 | Gates | 🔲 |

### Item 2: #99 Runner-Diagnose & Stats-Wahrheit (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Capture-CoT (≥ 3): Tail-Capture-Strategie für die drei Runner-Phasen | 🔲 |
| 2.2 | Failing Tests: Gate-Fehlschlag zeigt pytest-Tail + dekodierten Exit (2/4/5); extra_paths im Runner-PYTHONPATH; Stats-Fehlschlag lässt Cache unangetastet + lädt kein stale JSON; Test-Löschung triggert Obsolete-Cleanup | 🔲 |
| 2.3 | RN-001: DEVNULL → Tail-Capture in clean/stats/forced-fail + Exit-Klassen-Dekodierung in Fehlermeldungen | 🔲 |
| 2.4 | RN-002: extra_paths in `_mutants_env` (Worker-Paritität) | 🔲 |
| 2.5 | RN-003+OS-006: run_stats-returncode prüfen; bei Fehlschlag kein save_stats, kein load_stats, klare Meldung | 🔲 |
| 2.6 | OS-007: Obsolete-Cleanup auch bei verschwundenen Tests ohne neue | 🔲 |
| 2.7 | RN-008/009-Slices: stats_time nicht überschreiben; „in-process"-Doku-Reste tilgen | 🔲 |
| 2.8 | Gates | 🔲 |

### Item 3: #100 DB-Härtung (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing Tests: Prä-v2.5-DB-Fixture (ohne forensics/last_output-Spalten) → results/browse/export crashen nicht; Exception unter offener Connection → DB nicht gelockt (Folge-Connect ok); paralleles create_db → kein duplicate-column-Crash; Lone-Surrogate-Write verliert keinen Upsert | 🔲 |
| 3.2 | FD-001: Migration/Toleranz auf dem Lesepfad | 🔲 |
| 3.3 | FD-006: contextlib.closing/try-finally um ALLE Connections | 🔲 |
| 3.4 | FD-007: Race-tolerante Migration (try/except duplicate column) | 🔲 |
| 3.5 | FD-011: Surrogate-Sanitizing vor Write | 🔲 |
| 3.6 | Gates | 🔲 |

### Item 4: #101 Staging-Hygiene (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | **Design-CoT (≥ 8):** Invalidierungs-Fingerprint (Signale, Config-Anteile, Speicherort, Rebuild-Trigger) + Deletion-Sync-Semantik (verwaltete Artefakte, Quelle der Wahrheit) | 🔲 |
| 4.2 | Failing Tests ZUERST (destruktiv!): `..`-Eintrag erzeugt NICHTS außerhalb mutants/; `.` nestet nicht; gelöschte Quelle verschwindet aus Staging + .meta weg; Subset-/User-Dateien unangetastet | 🔲 |
| 4.3 | FD-002: Containment-Check (resolve + relative_to, #93-Muster) für also_copy/extra_paths-Ziele | 🔲 |
| 4.4 | FD-005: Nesting-Guard (`.`, mutants/ selbst) | 🔲 |
| 4.5 | FD-003 + OS-012-Rest: Deletion-Sync für verwaltete Staging-Dateien inkl. verwaister .meta | 🔲 |
| 4.6 | FD-004+OS-008: Fingerprint-Invalidierung (mtime+size+Config-Hash) statt mtime-only | 🔲 |
| 4.7 | FD-009: --force prüft rmtree-Erfolg, meldet ehrlich | 🔲 |
| 4.8 | CM-009/FD-010: .meta atomar (tmp + Path.replace) schreiben, tolerant laden (Warnung + Neuaufbau statt Block) | 🔲 |
| 4.9 | Gates + Audit-Register: OS-012 KOMPLETT geschlossen vermerken | 🔲 |

### Item 5: #102 Config-/CLI-Wahrheit (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Failing Tests: `--max-children 0` → Validierungsfehler statt Hänger; `paths_to_mutat`-Typo → Warnung mit Vorschlag; ungültige since-commit-Ref → klarer Fehler + Exit ≠ 0; gelöschte/Test-Dateien keine Mutationsziele; --debug zeigt Traceback | 🔲 |
| 5.2 | CM-004: Override-Merge → `MutmutConfig.model_validate` (Constraints greifen) | 🔲 |
| 5.3 | CM-005: Unbekannte [tool.mutmut]-Keys → Warnung + difflib.get_close_matches-Vorschlag (non-breaking) | 🔲 |
| 5.4 | CM-006: git-returncode prüfen; Filter auf existierende .py unter paths_to_mutate | 🔲 |
| 5.5 | UI-005+QX-023-Slice: --debug wirksam (voller Traceback im run-except) | 🔲 |
| 5.6 | Gates | 🔲 |

### Item 6: #103 CI-Output-Disziplin (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Failing Tests: `json.loads(stdout)` funktioniert bei --output json (CliRunner, mix_stderr=False); cp1252-stdout ohne UTF-8 → kein UnicodeEncodeError | 🔲 |
| 6.2 | UI-006: Prosa → stderr/unterdrückt bei --output json; stdout = exakt das JSON | 🔲 |
| 6.3 | QX-003: Encoding-toleranter Writer/ASCII-Fallback wenn stdout kein UTF-8 (Context7: sys.stdout.reconfigure) | 🔲 |
| 6.4 | Gates | 🔲 |

### Item 7: #104 C9-Rest-Triage (2 SP, Should, ZULETZT)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 7.1 | Verbleibende offene Findings inventarisieren (inkl. allem, was Sprint 32 doch noch liegen ließ + Dogfooding-Funde) | 🔲 |
| 7.2 | Kuratierter Maintenance-Abschnitt im Product Backlog: severity-sortiert, je 1 Zeile Real-Schaden + Modul | 🔲 |
| 7.3 | Audit-Register: Schlussstrich-Sektion (Bilanz: behoben vs. überführt; Zyklus formal beendet) | 🔲 |

---

## Out of Scope (bewusst, dokumentiert via #104)

- UI-007 (TUI-Ganzdatei-Diff — eigenes UX-Feature), QX-001
  (CLI-Importkette im Stats-Trampolin, ~1,4 s — Perf-Umbau), QX-007
  (Exit-33-Producer „no tests" — Laufzeit-Feature mit
  Testselektions-Semantik), UI-010…016-Rest, QX-005/006/017–024,
  RN-006/007/010–013, FD-008
- pip-audit-Baseline (Umgebungs-SSL, unverändert)

---

## Quality Gates Sprint-Ende (VERSCHÄRFT — Teil des Sprint-Inhalts)

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest` (**NEU: ohne --ignore-Flag**, Kanon in conftest) | 773 + neue ≥ 800 passed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Format | `uv run ruff format --check src/ tests/` (**NEUES GATE**) | 0 zu formatieren |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors (Baseline 20) |
| Security | `semgrep scan --config auto src/mutmut_win/ tests/` (**NEU: tests/ real gescannt**) | 0 blocking Findings |
| Architecture | lint-imports (läuft in der Suite) | KEPT |
| Mutation Testing | Dogfooding-Pilot (#98.2) | Lauf komplett; ≥ 80 % auf Piloten ODER surviving Mutants dokumentiert |

---

## Release v2.10.0 (nur auf explizites User-„Release")

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.10.0 (`uv lock --system-certs`) | 🔲 |
| Annotated Tag v2.10.0 | 🔲 |
| GitHub Release v2.10.0 (Changelog: Audit-Zyklus-Abschluss, Hygiene-Gates, Dogfooding-Premiere) | 🔲 |
| Auto-close #98–#104 via Merge-Commit | 🔲 |
| MEMORY.md + product_backlog.md update (inkl. Maintenance-Abschnitt aus #104) | 🔲 |
