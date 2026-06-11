# Sprint 34 Backlog — v2.12.0 „Maintenance 2: Final Sweep"

**Sprint-Ziel:** Letzter Sprint vor der geplanten Entwicklungspause.
Auftrag des Users: ALLE noch offenen Topics — der komplette
Maintenance-Pool (13 Einträge) plus die vier offenen Entscheidungen aus
MEMORY.md. Nach diesem Sprint ist der Pool leer, das
Entscheidungsregister geschlossen und das Projekt in einem sauberen,
dokumentierten Pausenzustand. Messziel: **Dogfooding-Pilot brutto
≥ 80 % HALTEN** (Regression-Gate; Sprint 33: 86,9 %) bei unverändert
grünen Gates.

**Basis:** Maintenance-Backlog vollständig (KEINE Auswahl — Final
Sweep). Eskalationsventil: Ein Item, das sich als unverhältnismäßig
erweist, wird zur dokumentierten, begründeten Won't-Fix-Entscheidung —
NIE stilles Liegenlassen.

**Branch:** `feature/v2.12.0-maintenance-2` · **Release:** v2.12.0
(nur auf explizites User-„Release") · **Danach:** Entwicklungspause
(dokumentiert)

**Planungs-CoT:** 11 Schritte (nextgen-cot) — Inventar-Verifikation
(BUG_REPORT_9.md existiert nicht mehr → moot; OS-012-Rest ist reine
Formalie), thematische Bündelung in 7 Issues, Reihenfolge-Begründung
(#114 vor #115 wegen cli-Fehlerpfaden), Risiken je Item (Forced-Fail-
Semantik, API-Oberfläche toter Exceptions, test-verdrahtete
Diff-Pins, Glob-Ambiguität bei show/apply, sitecustomize bleibt
funktional nötig), Score-Auswirkung (type_checking.py bekommt neue
Mutanten durch QX-023), Deprecation- statt Entfernungs-Entscheid für
--treat-timeout-as-kill, DoD inkl. Pausenzustand.

---

## Ausgewählte Items (= vollständiger Pool-Rest + Entscheidungsregister)

| # | Issue | Typ | Titel | Quelle | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|--------|----|-----------|-------------|--------|
| 1 | [#111](https://github.com/pgm1980/mutmut-win/issues/111) | Bug | RN-006 + RN-012: Forced-Fail-Wahrheit (-x, Timeout ≠ Erfolg, Marker) + PY_IGNORE_IMPORTMISMATCH konsistent | Audit S3 | 5 | Must | 1 | 🔲 |
| 2 | [#112](https://github.com/pgm1980/mutmut-win/issues/112) | Bug | RN-013: Arg-Koerzierung via shlex; test_selection akzeptiert str | Audit S3 | 3 | Must | 2 | 🔲 |
| 3 | [#113](https://github.com/pgm1980/mutmut-win/issues/113) | Bug | FD-008: Sanitiser entfernt `[tool.uv.sources.<pkg>]`-Subtables | Audit S3 | 3 | Must | 3 | 🔲 |
| 4 | [#114](https://github.com/pgm1980/mutmut-win/issues/114) | Bug | QX-005/006/023-Rest: Exception-Hygiene (Exit-4-Producer, tote Klassen, MutmutWinError-Catch, Domänenklasse in type_checking) | Audit S3+S4 | 5 | Must | 4 | 🔲 |
| 5 | [#115](https://github.com/pgm1980/mutmut-win/issues/115) | Bug | UI-012/014/015: EIN Namens-Resolver (dokumentiert), patch-fähige Diffs, Summary-Alignment | Audit S3+S4 | 5 | Should | 5 (nach #114) | 🔲 |
| 6 | [#116](https://github.com/pgm1980/mutmut-win/issues/116) | Bug | RN-010/011: sitecustomize ohne Getter-Seiteneffekt, normcase/realpath-Blocker | Audit S4 | 3 | Should | 6 | 🔲 |
| 7 | [#117](https://github.com/pgm1980/mutmut-win/issues/117) | Chore | Abschluss-Dossier: Deprecation `--treat-timeout-as-kill`, Release-Policy, formale Schließungen (OS-012-Rest, Shrink-Storm, BUG_REPORT_9 moot), Milestone-Cleanup, Pausenzustand | MEMORY.md-Register | 3 | Must | 7 | 🔲 |
| — | — | Gate | **Abschluss-Dogfooding: Pilot ≥ 80 % (Gate) + `--since-commit`-Lauf (informativ)** | — | — | 8 | 🔲 |

**Gesamt geplant:** 27 SP (Must 19, Should 8)

**Kein Scope-Ventil:** Der User-Auftrag ist der vollständige Rest.
Unverhältnismäßige Items eskalieren zur dokumentierten
Won't-Fix-Entscheidung mit Begründung im Product Backlog.

---

## Sprint-Strategie

- **Final-Sweep-Disziplin:** Jeder der 13 Pool-Einträge endet in genau
  einem von zwei Zuständen: „gefixt (Commit-Ref)" oder „formal
  geschlossen (dokumentierte Begründung)". Gleiches gilt für die vier
  MEMORY-Entscheidungen.
- **Reihenfolge:** Laufzeit-Items zuerst (#111–#113), dann
  API-Oberfläche (#114) VOR cli-Konsistenz (#115), Isoliertes (#116),
  Formales (#117) zuletzt.
- **#111-Designkern:** Der Forced-Fail-Check beweist künftig
  (a) schnell (`-x`), (b) hart (Timeout → ForcedFailError, nie Erfolg),
  (c) attribuierbar (Failure stammt nachweislich vom Trampolin-Marker,
  nicht von irgendeinem kaputten Test).
- **#114-Politik:** Verdrahten vor Löschen — Klassen mit natürlicher
  Raise-Stelle (InvalidConfigValueError, WorkerCrashError,
  MutationParseError, BadTestExecutionCommandsException) bekommen
  Producer; nur referenzlose Karteileichen ohne Stelle fliegen.
  mutmut-3.5.0-API-Namen bleiben. Opportunität: mypy-Baseline (20)
  darf nur SINKEN.
- **#115-Sicherheit:** Glob bei show/apply verlangt EINDEUTIGEN
  Treffer; Ambiguität → Fehler mit Kandidatenliste (kein apply-all).
- **Score-Transparenz:** QX-023 erzeugt neue Mutanten in
  type_checking.py — Pilot-Vorher/Nachher mit Mutantenzahl
  dokumentieren.
- **Deprecation statt Entfernung:** `--treat-timeout-as-kill` bleibt
  funktional, warnt aber; Entfernung erst in einem künftigen Major
  (v3) — kein Breaking Change in einem Maintenance-Release.

---

## Task Breakdown

### Item 1: #111 Runner-Phasen-Wahrheit (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | Failing Tests: forced-fail cmd enthält `-x`; Timeout → ForcedFailError (kein Erfolg); Failure-Attribution am Trampolin-Marker; PY_IGNORE_IMPORTMISMATCH in clean/stats/forced-fail/worker-Env | 🔲 |
| 1.2 | Implementierung runner.py (+ worker-Env) | 🔲 |
| 1.3 | Gates | 🔲 |

### Item 2: #112 Arg-Koerzierung (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing Tests: `'-m "not slow"'` → `['-m', 'not slow']` für BEIDE Felder; str+list konsistent; hypothesis-Property wo sinnvoll | 🔲 |
| 2.2 | Implementierung config.py (shlex, ein gemeinsamer Validator) | 🔲 |
| 2.3 | Gates | 🔲 |

### Item 3: #113 Sanitiser-Subtables (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing Tests: `[tool.uv.sources.<pkg>]`-Fixture wird entfernt; bestehende Sanitiser-Fälle bleiben | 🔲 |
| 3.2 | Implementierung file_setup.py | 🔲 |
| 3.3 | Gates | 🔲 |

### Item 4: #114 Exception-Hygiene (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | Inventar: Referenzen/Exports der 6 toten Klassen; natürliche Raise-Stellen bestimmen | 🔲 |
| 4.2 | Failing Tests: Exit-4-Klassifikation; Producer je verdrahteter Klasse; cli fängt MutmutWinError (fremde Exceptions → Traceback-Pfad); type_checking-Domänenklasse | 🔲 |
| 4.3 | Implementierung exceptions.py / worker / cli.py / type_checking.py | 🔲 |
| 4.4 | Gates (mypy-Baseline ≤ 20) | 🔲 |

### Item 5: #115 CLI/Output-Konsistenz (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Failing Tests: Resolver (exakt/Glob/ambig/no-match) über alle 5 Commands; Diff-Header mit echten Zeilennummern + a/b-Labels; „Suspicious: 1" | 🔲 |
| 5.2 | Implementierung (gemeinsamer Resolver; mutant_diff-Header via PositionProvider; cli-Format) + Doku der Matching-Regeln | 🔲 |
| 5.3 | Gates | 🔲 |

### Item 6: #116 sitecustomize-Hygiene (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Failing Tests: `_mutants_env` schreibt nichts; expliziter Setup-Schritt schreibt (injizierbarer Pfad); Blocker matcht Case-/realpath-Varianten | 🔲 |
| 6.2 | Implementierung runner.py | 🔲 |
| 6.3 | Gates | 🔲 |

### Item 7: #117 Abschluss-Dossier (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 7.1 | Deprecation-Hinweis `--treat-timeout-as-kill` (+ Test, --help, README) | 🔲 |
| 7.2 | Release-Policy-Abschnitt (README Development) | 🔲 |
| 7.3 | Formale Schließungen im Product Backlog (OS-012-Rest, Shrink-Storm, BUG_REPORT_9 moot) + Pool-Tabelle → 0 | 🔲 |
| 7.4 | GitHub: 5 stale Milestones schließen; MEMORY.md/state.md Pausenzustand | 🔲 |

### Abschluss: Doppel-Dogfooding + Doku

| Task | Beschreibung | Status |
|------|-------------|--------|
| A.1 | Pilot-Re-Run (code_coverage.py + type_checking.py, `--force --no-progress`, Flags einzeln) — Gate ≥ 80 %, Vorher/Nachher dokumentiert | 🔲 |
| A.2 | `--since-commit <Sprint-Start>`-Lauf über die geänderten Module — informativ, Survivors dokumentiert | 🔲 |
| A.3 | pip-audit-Versuch mit System-Trust (Ergebnis oder dokumentierte Umgebungs-Limitation) | 🔲 |
| A.4 | Implementation-complete-Commit; Release wartet auf User-„Release" | 🔲 |

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest` | 868 + neue, 0 failed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Format | `uv run ruff format --check src/ tests/` | 0 zu formatieren |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors (Baseline 20, darf nur sinken) |
| Security | `semgrep scan --config auto src/mutmut_win/ tests/` | 0 Findings |
| Architecture | lint-imports in-suite (inkl. Artefakt) | KEPT überall |
| Mutation | Pilot-Re-Run | **brutto ≥ 80 %** + dokumentiert; since-commit informativ |
| Dependency-Audit | pip-audit (ein Versuch, System-Trust) | Ergebnis oder dokumentierte Limitation |

---

## Release v2.12.0 (nur auf explizites User-„Release")

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.12.0 (`uv lock --system-certs`) | 🔲 |
| Annotated Tag v2.12.0 | 🔲 |
| GitHub Release (Changelog: Final Sweep, Pool 13 → 0, Deprecation-Hinweis, Pausenzustand) | 🔲 |
| Auto-close #111–#117 via Merge | 🔲 |
| MEMORY.md + product_backlog.md: Pool = 0, Entscheidungsregister = 0, **Entwicklungspause dokumentiert** | 🔲 |
