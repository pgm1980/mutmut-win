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
| 1 | [#111](https://github.com/pgm1980/mutmut-win/issues/111) | Bug | RN-006 + RN-012: Forced-Fail-Wahrheit (-x, Timeout ≠ Erfolg, Marker) + PY_IGNORE_IMPORTMISMATCH konsistent | Audit S3 | 5 | Must | 1 | ✅ `8251509` |
| 2 | [#112](https://github.com/pgm1980/mutmut-win/issues/112) | Bug | RN-013: Arg-Koerzierung via shlex; test_selection akzeptiert str | Audit S3 | 3 | Must | 2 | ✅ `36d70e6` |
| 3 | [#113](https://github.com/pgm1980/mutmut-win/issues/113) | Bug | FD-008: Sanitiser entfernt `[tool.uv.sources.<pkg>]`-Subtables | Audit S3 | 3 | Must | 3 | ✅ `a72861f` |
| 4 | [#114](https://github.com/pgm1980/mutmut-win/issues/114) | Bug | QX-005/006/023-Rest: Exception-Hygiene (Exit-4-Producer, tote Klassen, MutmutWinError-Catch, Domänenklasse in type_checking) | Audit S3+S4 | 5 | Must | 4 | ✅ `2f3e7da` |
| 5 | [#115](https://github.com/pgm1980/mutmut-win/issues/115) | Bug | UI-012/014/015: EIN Namens-Resolver (dokumentiert), patch-fähige Diffs, Summary-Alignment | Audit S3+S4 | 5 | Should | 5 (nach #114) | ✅ `b08a9a4` |
| 6 | [#116](https://github.com/pgm1980/mutmut-win/issues/116) | Bug | RN-010/011: sitecustomize ohne Getter-Seiteneffekt, normcase/realpath-Blocker | Audit S4 | 3 | Should | 6 | ✅ `9fa333f` |
| 7 | [#117](https://github.com/pgm1980/mutmut-win/issues/117) | Chore | Abschluss-Dossier: Deprecation `--treat-timeout-as-kill`, Release-Policy, formale Schließungen (OS-012-Rest, Shrink-Storm, BUG_REPORT_9 moot), Milestone-Cleanup, Pausenzustand | MEMORY.md-Register | 3 | Must | 7 | ✅ `fa590ac` |
| — | — | Gate | **Abschluss-Dogfooding: Pilot ≥ 80 % (Gate) + `--since-commit`-Lauf (informativ)** | — | — | 8 | ✅ **85,1 % brutto** (Gate gehalten; 6 Kaltstart-Timeouts im Re-Run 6/6 gekillt → 87,6 % effektiv) |

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
| 1.1 | Failing Tests: forced-fail cmd enthält `-x`; Timeout → ForcedFailError (kein Erfolg); Failure-Attribution am Trampolin-Marker; PY_IGNORE_IMPORTMISMATCH in clean/stats/forced-fail/worker-Env | ✅ (17 Tests, test_phase_truth_111.py) |
| 1.2 | Implementierung runner.py (+ worker-Env) | ✅ (zusätzlich `--tb=line` + COLUMNS gegen Summary-Truncation) |
| 1.3 | Gates | ✅ |

### Item 2: #112 Arg-Koerzierung (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing Tests: `'-m "not slow"'` → `['-m', 'not slow']` für BEIDE Felder; str+list konsistent; hypothesis-Property wo sinnvoll | ✅ (9 Tests inkl. Round-Trip-Property) |
| 2.2 | Implementierung config.py (shlex, ein gemeinsamer Validator) | ✅ (shlex mit `escape=""` — Windows-Backslashes bleiben literal) |
| 2.3 | Gates | ✅ |

### Item 3: #113 Sanitiser-Subtables (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing Tests: `[tool.uv.sources.<pkg>]`-Fixture wird entfernt; bestehende Sanitiser-Fälle bleiben | ✅ (10 Tests — erste Sanitiser-Tests überhaupt) |
| 3.2 | Implementierung file_setup.py | ✅ (eine Regex für beide Header-Formen, EOF ohne Newline gedeckt) |
| 3.3 | Gates | ✅ |

### Item 4: #114 Exception-Hygiene (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | Inventar: Referenzen/Exports der 6 toten Klassen; natürliche Raise-Stellen bestimmen | ✅ (verdrahtet: InvalidConfigValueError, WorkerError, MutationParseError, BadTestExecutionCommandsException; gelöscht: WorkerCrashError/WorkerInitError — Event-Recovery by design; behalten mit Begründung: InvalidGeneratedSyntaxException) |
| 4.2 | Failing Tests: Exit-4-Klassifikation; Producer je verdrahteter Klasse; cli fängt MutmutWinError (fremde Exceptions → Traceback-Pfad); type_checking-Domänenklasse | ✅ (19 Tests; + CoverageCollectionError für die nackten #95-Raises) |
| 4.3 | Implementierung exceptions.py / worker / cli.py / type_checking.py | ✅ (TypeCheckCommandError; Dispatch-Umbau eliminiert beide casts) |
| 4.4 | Gates (mypy-Baseline ≤ 20) | ✅ **Baseline 20 → 14** |

### Item 5: #115 CLI/Output-Konsistenz (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Failing Tests: Resolver (exakt/Glob/ambig/no-match) über alle 5 Commands; Diff-Header mit echten Zeilennummern + a/b-Labels; „Suspicious: 1" | ✅ (13 Tests; Legacy-Überbreiten-Labels mitgefixt) |
| 5.2 | Implementierung (gemeinsamer Resolver; mutant_diff-Header via PositionProvider; cli-Format) + Doku der Matching-Regeln | ✅ (match_mutant_names + resolve_mutant/AmbiguousMutantNameError; README + Help-Texte) |
| 5.3 | Gates | ✅ (7 Format-Pins mitgezogen) |

### Item 6: #116 sitecustomize-Hygiene (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Failing Tests: `_mutants_env` schreibt nichts; expliziter Setup-Schritt schreibt (injizierbarer Pfad); Blocker matcht Case-/realpath-Varianten | ✅ (8 Tests inkl. exec-Verifikation des generierten Blockers) |
| 6.2 | Implementierung runner.py | ✅ (write_pth_blocker(mutants_dir=None), Orchestrator ruft 1× pro Lauf) |
| 6.3 | Gates | ✅ (semgrep-exec-Findings mit dokumentierter nosemgrep-Begründung nach Projektkonvention) |

### Item 7: #117 Abschluss-Dossier (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 7.1 | Deprecation-Hinweis `--treat-timeout-as-kill` (+ Test, --help, README) | ✅ (Warnung in run + results; 5 Tests) |
| 7.2 | Release-Policy-Abschnitt (README Development) | ✅ |
| 7.3 | Formale Schließungen im Product Backlog (OS-012-Rest, Shrink-Storm, BUG_REPORT_9 moot) + Pool-Tabelle → 0 | ✅ (**Pool = 0**, Entscheidungsregister = 0) |
| 7.4 | GitHub: 5 stale Milestones schließen; MEMORY.md/state.md Pausenzustand | ✅ (0 offene Milestones; Pausenzustand beim Sprint-Close) |

### Abschluss: Doppel-Dogfooding + Doku

| Task | Beschreibung | Status |
|------|-------------|--------|
| A.1 | Pilot-Re-Run (code_coverage.py + type_checking.py, `--force --no-progress`, Flags einzeln) — Gate ≥ 80 %, Vorher/Nachher dokumentiert | ✅ **85,1 % brutto (Gate gehalten)**; 6 Kaltstart-Timeouts im Namens-Re-Run 6/6 gekillt → 87,6 % effektiv; keine neuen Pool-Funde |
| A.2 | `--since-commit <Sprint-Start>`-Lauf über die geänderten Module — informativ, Survivors dokumentiert | ✅ **68,3 % brutto über 12 Module** (7800 Mutanten, 5122+1 Kills, 2337 Survivors, 45 Timeouts, 295 no tests; 65,8 min) — erste Vollvermessung dieser Module, dokumentierte Baseline für eine spätere Wiederaufnahme; Stats-Phase nach Test-Fix `6101548` grün (2607 Mappings) |
| A.3 | pip-audit-Versuch mit System-Trust (Ergebnis oder dokumentierte Umgebungs-Limitation) | ✅ dokumentiert gescheitert: `--system-certs` deckt nur uvs eigene Fetches; pip-audits requests/certifi-Kette erhält weiter `CERTIFICATE_VERIFY_FAILED` — Limitation bleibt (Status seit Sprint 28 unverändert) |
| A.4 | Implementation-complete-Commit; Release wartet auf User-„Release" | ✅ `0f64b48`; Release ausgelöst 2026-06-12 |

---

## Dogfooding-Protokoll Sprint 34

Pilot identisch zu Sprint 32/33 (Vergleichbarkeit): `code_coverage.py` +
`type_checking.py`, `--force --no-progress`, Flag je Pfad wiederholt.

| Lauf | Total | Killed | Survived | Timeout | No tests | Score brutto | Dauer |
|------|-------|--------|----------|---------|----------|--------------|-------|
| Sprint-33-Referenz (v2.11.0) | 244 | 212 | 32 | 0 | 0 | 86,9 % | 158,9 s |
| **Abschluss-Pilot (v2.12.0-dev)** | 241 | 205 | 30 | 6 | 0 | **85,1 %** | 89,2 s |
| Namens-Re-Run der 6 Timeouts | 6 | 6 | 0 | 0 | 0 | 100 % | 132,6 s |
| `--since-commit` OHNE `--force` (Lehrstück) | 7559 | 211 | 30 | 0 | **7318** | 87,6 % (nur Pilot-Module bewertbar) | 154,7 s |
| **`--since-commit --force` (alle 12 geänderten Module)** | 7800 | 5122 (+1 Segfault) | 2337 | 45 | 295 | **68,3 %** | 3949,3 s |

- **Gate gehalten:** 85,1 % brutto ≥ 80 %. Mutantenzahl 244 → 241 durch
  den #114-Umbau von `type_checking.py` (Dispatch-Restrukturierung).
- **Die 6 Timeouts waren Kaltstart-Grenzfälle, keine Regression:** Der
  Sockel ist selbstkalibrierend je Lauf (#105) — der Pilot maß auf
  leiser Maschine clean 21,8 s → Sockel 5,1 s (Clamp-Untergrenze nah);
  erste Tasks je Worker überschritten ihn knapp. Der gezielte Re-Run
  (ausgelastete Maschine: clean 73,1 s → Sockel 56,4 s) killte alle 6.
  Effektive Detektion damit 211/241 = 87,6 %.
- **Survivors (30, dokumentiert):** 17× `code_coverage`
  (Fehlermeldungs-Texte/Randfälle in `gather_coverage`, 1×
  `_normalized_key`), 13× `type_checking` (8× `run_type_checker`-
  Meldungs-/Toleranz-Varianten, 5× Report-Parser-Toleranzen) — dieselben
  akzeptierten Klassen wie Sprint 32/33 (32 → 30 durch #114).
- **Bedienungs-Lektion (kein Code-Fund):** Nach Konfig-/Staging-Wechsel
  gehört `--force` zum Lauf. Der `--since-commit`-Lauf ohne `--force`
  übernahm den Pilot-Stats-Cache (inkrementelle Nachsammlung der 32
  neuen Tests scheiterte mit exit 2; #99-Schutz hielt den Cache), und
  die 7318 Mutanten der nicht kartierten Module wurden als `no tests`
  verbucht — **ehrlich und ohne Laufzeitverschwendung statt 7318
  Vollsuite-Läufen (vor #106 wären das Tage gewesen).**
- **Beobachtung (dokumentiert, kein Blocker):** Die inkrementelle
  Stats-Nachsammlung („Found N new tests") prüft Test-Neuheit, nicht
  Staging-Zugehörigkeit des Caches; ihr Scheitern war laut und der
  Fallback korrekt. Verhalten seit #99/#106 wie designt; bei
  Wiederaufnahme der Entwicklung wäre ein Stats-Fingerprint analog zum
  Mutanten-Fingerprint (#101) der saubere Schnitt.
- **Dogfooding-Fund (gefixt, `6101548`):** Der erste `--force`-Anlauf
  scheiterte in der Stats-Phase an genau EINEM Test:
  `test_get_max_stack_depth_caches_value` war unter
  Selbst-Instrumentierung nicht isolationsfest — im voll
  trampolinisierten Staging feuert schon die `MutmutConfig`-
  Konstruktion im Patch-Kontext Trampolin-Hits, die den Depth-Cache
  durch den halb konfigurierten Mock vergifteten. Produktionscode
  korrekt; Test jetzt instrumentierungsfest (Objekt vor Patch bauen,
  Mock atomar armieren, Reset danach). Im Pilot-Staging (config.py
  nicht trampolinisiert) war die Lücke unsichtbar.
- **Vollvermessung als Pausen-Baseline:** Der 68,3-%-Lauf ist die
  ERSTE Mutationsmessung über cli/orchestrator/runner/file_setup/
  mutant_diff/worker/executor/config/exceptions/test_mapping (bisher
  nur die zwei Pilot-Module vermessen: 85–88 %). Die 2337 Survivors
  und 45 Timeouts sind als ehrliche Test-Lücken-Baseline dokumentiert —
  KEINE Pool-Einträge (Pool ist geschlossen); sie sind der natürliche
  Startpunkt, falls die Entwicklung wieder aufgenommen wird.

---

## Quality Gates — Ergebnis Sprint-Abschluss

| Gate | Befehl | Ergebnis |
|------|--------|----------|
| Tests | `uv run pytest` | ✅ 951 passed, 4 skipped (+83 zu Sprint 33; 270,7 s) |
| Linting | `uv run ruff check src/ tests/` | ✅ 0 Findings |
| Format | `uv run ruff format --check src/ tests/` | ✅ 113 Dateien, 0 zu formatieren |
| Type Check | `uv run mypy src/mutmut_win/` | ✅ **14 Errors = neue Baseline (vorher 20, 0 neue)** |
| Security | `semgrep scan --config auto src/mutmut_win/ tests/` | ✅ 0 Findings (115 Dateien, voller Sweep) |
| Architecture | lint-imports in-suite (inkl. Artefakt) | ✅ KEPT (test_architecture 5/5 in der Suite) |
| Mutation | Pilot-Re-Run | ✅ **85,1 % brutto** (Gate ≥ 80 %), Re-Run-verifiziert 87,6 % effektiv |
| Dependency-Audit | `uv run --system-certs pip-audit` | ⚠️ Umgebungs-Limitation dokumentiert (TLS-Interception, certifi-Kette) — kein Befund-Status erzielbar |

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

## Release v2.12.0 (ausgelöst durch explizites User-„Release" am 2026-06-12)

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.12.0 (`uv lock --system-certs`) | ✅ `932f90e` |
| Annotated Tag v2.12.0 | ✅ |
| GitHub Release (Changelog: Final Sweep, Pool 13 → 0, Deprecation-Hinweis, Pausenzustand) | ✅ [Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.12.0) |
| Auto-close #111–#117 via Merge | ✅ (verifiziert: 0 offene Issues) |
| MEMORY.md + product_backlog.md: Pool = 0, Entscheidungsregister = 0, **Entwicklungspause dokumentiert** | ✅ |

Vor dem Merge frisch verifizierte Gates: 951 passed / 4 skipped (231 s),
ruff 0, format-check 0, mypy 14 = Baseline (0 neue).
