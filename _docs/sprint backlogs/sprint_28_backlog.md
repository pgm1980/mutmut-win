# Sprint Backlog — Sprint 28 (v2.6.0 Source Protection & Codegen Correctness)

**Projekt:** mutmut-win
**Sprint:** 28
**Sprint-Ziel:** W4.11-Downstream entblocken (BUG-1 + BUG-2 endgültig fixen), die beiden destruktiven Audit-Funde eliminieren (Quell-Schutz, Cluster C1) und die Clean-Run-Brecher der Codegen-Schicht (Cluster C2) strukturell schließen. Release v2.6.0.
**Epic(s):** Epic 19 (Source Protection & Codegen Correctness) — neu
**Branch:** `feature/v2.6.0-source-protection`
**Zeitraum:** 2026-06-11 –
**Status:** 🔲 in progress

**Grundlage:** Sprint-27-Audit (`_docs/audit/sprint_27_audit_findings.md`),
Fix-Cluster C1 + C2 + BUG-2-Quick-Win aus C4. Alle Finding-IDs unten
referenzieren dieses Dokument.

---

## Ausgewählte Items

| # | Issue | Typ | Titel | Findings | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|----------|----|-----------|-------------|--------|
| 1 | [#74](https://github.com/pgm1980/mutmut-win/issues/74) | Bug | BUG-2: `clean_run_timeout`-Config-Feld statt 300s-Konstante + präzise Fehlermeldung | BUG-2 (W4.11), Teil C4 | 2 | Must | 1 (kleinster, entblockt Downstream sofort) | 🔲 |
| 2 | [#78](https://github.com/pgm1980/mutmut-win/issues/78) | Bug | Sicherheitsnetz scharf schalten: validate-then-write + Operator-Crash-Guards | MT-007, NM-007, NM-009, MT-011, RX-001 | 3 | Must | 2 (schützt strukturell vor der ganzen BUG-1-Klasse — VOR den Operator-Fixes) | 🔲 |
| 3 | [#75](https://github.com/pgm1980/mutmut-win/issues/75) | Bug | Quell-Schutz: Absolutpfad-Guard für paths_to_mutate + apply-Fix (class-aware, Backup, atomar, newline-Erhalt) | CM-001, UI-001, UI-002, UI-003 | 5 | Must | 3 (destruktiv-verhindernd) | 🔲 |
| 4 | [#73](https://github.com/pgm1980/mutmut-win/issues/73) | Bug | Parenless-yield-Klasse: Safe-Unwrap-Helper für 5 Operatoren (schließt BUG-1) | NM-001…006, BUG-1 (W4.11) | 8 | Must | 4 | 🔲 |
| 5 | [#77](https://github.com/pgm1980/mutmut-win/issues/77) | Bug | Klassenkörper-Injektion: Mutants-Dict auf Modulebene (Enum/NamedTuple-Fix) | MT-004, MT-005 | 5 | Should | 5 | 🔲 |
| 6 | [#76](https://github.com/pgm1980/mutmut-win/issues/76) | Bug | Wrapper-Codegen: first-param statt `self`, kollisionsfreie Locals, *args-Methoden, Async-Gen-Passthrough | MT-001, MT-002, MT-003, MT-006 | 8 | Should | 6 (größtes Stück) | 🔲 |

**Gesamt geplant:** 31 SP (Must 18, Should 13)

**Scope-Ventil:** Bei Mid-Sprint-Blowup rutschen #76 (ganz) bzw. #77 nach
Sprint 29 — die Must-Items 1–4 entblocken den Downstream vollständig und
eliminieren alles Destruktive. Velocity-Referenz: Sprints 23–26 liefen mit
10–18 SP bei 100 %.

---

## Sprint-Strategie

- **Ein Feature-Branch** `feature/v2.6.0-source-protection`. Pro Issue:
  TDD-Zyklus (failing test → implement → green → ruff/mypy) → Commit.
  Merge-Commit auf main bei Sprintende, Release v2.6.0.
- **Reihenfolge mit Absicht:** #78 (Sicherheitsnetz) kommt VOR den
  Operator-Fixes — danach kann kein invalider Mutant mehr eine Datei
  blockieren, und jede Regression der späteren Items fällt sofort als
  Warnung auf statt als Clean-Run-Crash.
- **Neues Test-Asset:** Adversarial-Fixture-Modul (die A1-Verifikations-
  Snippets: multiline-or, genexp-sole-arg, Enum-mit-Methode,
  NamedTuple-mit-Methode, `__init_subclass__`, `def m(*args)`,
  kwonly-`args`-Param, async-gen, `1e400`, `a{4294967294}`) + Gate-Test:
  **jede generierte Mutanten-Datei kompiliert** (Vorschlag des
  W4.11-Reporters, §1.4) und **der Clean-Run-Pfad des Fixtures läuft grün**.
- **Dogfooding:** `uv run mutmut-win run --paths-to-mutate <geänderte Module>`
  auf node_mutation.py/mutation.py/trampoline.py-Änderungen, Score ≥ 80 %.

---

## Task Breakdown

### Item 1: #74 BUG-2 clean_run_timeout (2 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | Failing test: `[tool.mutmut] clean_run_timeout = 900` → Runner nutzt 900 (Config-Roundtrip) | 🔲 |
| 1.2 | `MutmutConfig`: `clean_run_timeout: int = Field(default=300, gt=0)` + `forced_fail_timeout: int = Field(default=120, gt=0)` | 🔲 |
| 1.3 | runner.py: `_RUNNER_TIMEOUT`/`_FORCED_FAIL_TIMEOUT`-Verwendungen (run_clean_test, run_stats, run_forced_fail) durch Config-Werte ersetzen | 🔲 |
| 1.4 | Timeout-Fehlermeldung: „Clean test run timed out after {N}s (configure [tool.mutmut].clean_run_timeout)" statt „Fix tests before mutating" | 🔲 |
| 1.5 | setup.cfg-Fallback um beide Keys ergänzen (Lücken-Muster A2-EW-015 nicht wiederholen) | 🔲 |
| 1.6 | Ruff + mypy clean | 🔲 |

### Item 2: #78 Sicherheitsnetz + Crash-Guards (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing test: Operator, der invaliden Code erzeugt (Fixture mit bekanntem NM-001-Pattern VOR dessen Fix) → Datei wird NICHT invalid geschrieben, Original kopiert, Warnung emittiert | 🔲 |
| 2.2 | file_setup.py: ast.parse-Validierung VOR dem Schreiben; bei SyntaxError Original-Quelle nach output_path + laute Warnung (`InvalidGeneratedSyntaxException`-Pfad nutzen oder Klasse entfernen) | 🔲 |
| 2.3 | NM-007-Guard: `operator_number` skippt non-finite Ergebnisse (`math.isfinite`) | 🔲 |
| 2.4 | RX-001-Guard: `_is_valid_regex` fängt `(re.error, OverflowError)` | 🔲 |
| 2.5 | MT-011-Guard: ValueError aus `mangle_function_name` in `create_mutants_for_file` fangen → Datei unverändert kopieren + Warnung | 🔲 |
| 2.6 | NM-009-Guard: `operator_dict_arguments` prüft existierende Keywords | 🔲 |
| 2.7 | Tests grün; Ruff + mypy clean | 🔲 |

### Item 3: #75 Quell-Schutz (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | Failing test: absoluter Eintrag in paths_to_mutate → ConfigError (bzw. Relativierung) — Original-Datei bleibt byte-identisch | 🔲 |
| 3.2 | `MutmutConfig`-Validator: absolute paths_to_mutate ablehnen oder gegen CWD relativieren (Guard-Muster aus copy_also_copy_files) | 🔲 |
| 3.3 | Failing test (Sandbox): apply auf `xǁBǁgreet__mutmut_1` bei existierendem `A.greet` → patcht B.greet | 🔲 |
| 3.4 | mutant_diff.py: class-aware Lookup (`find_top_level_function_or_method` mit class_name-Parameter) | 🔲 |
| 3.5 | apply: newline-Erhalt (`newline=""` + Original-Lineending-Detection), tmp-Datei + `os.replace`, `.bak`-Backup, mtime-Staleness-Warnung | 🔲 |
| 3.6 | Tests grün; Ruff + mypy clean | 🔲 |

### Item 4: #73 Safe-Unwrap-Helper (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | Failing tests: Adversarial-Fixture (alle 6 NM-Patterns + BUG-1-Repro aus W4.11 §1.3: single-line, multiline, kwarg-inline) → jede generierte Datei kompiliert | 🔲 |
| 4.2 | Helper `_safe_unwrap(node, arg)` in node_mutation.py: Genexp ohne eigene Parens → Parens ergänzen; Subtree mit ParenthesizedWhitespace ohne lpar → skip; non-atomic Argument → lpar/rpar setzen (NM-006) | 🔲 |
| 4.3 | Helper in operator_collection_neutralize + operator_math_methods verdrahten (BUG-1 + NM-004/005/006) | 🔲 |
| 4.4 | Multiline-Guard generalisieren für operator_or_default (Operanden-Ebene, NM-001), operator_remove_unary_ops (NM-002), operator_conditional_expression (NM-003) | 🔲 |
| 4.5 | Verifikation gegen W4.11-Repro-Formen (§1.2-Tabelle: Multiline-Assignment, mit if-Filter, Single-line, kwarg-inline) | 🔲 |
| 4.6 | Dogfooding-Lauf auf node_mutation.py; Tests grün; Ruff + mypy clean | 🔲 |

### Item 5: #77 Klassenkörper → Modulebene (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Failing tests: Enum-mit-Methode → `list(Color) == ['RED']` im Clean-Run; NamedTuple-mit-Methode → Import ok | 🔲 |
| 5.2 | trampoline.py/mutation.py: Mutants-Dict-Assignment auf Modulebene emittieren (Namens-Eindeutigkeit via Mangling bereits gegeben) | 🔲 |
| 5.3 | Regression: normale Klassen/Methoden-Dispatch unverändert (bestehende Suite) | 🔲 |
| 5.4 | Tests grün; Ruff + mypy clean | 🔲 |

### Item 6: #76 Wrapper-Codegen (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | Failing tests: `__init_subclass__`-Fixture (MT-001), kwonly-`args`/`**args`-Params (MT-002), `def m(*args)` (MT-003), async-gen asend/athrow (MT-006) — alle im Clean-Run korrekt | 🔲 |
| 6.2 | create_trampoline_wrapper: tatsächlichen Namen des ersten Parameters verwenden; Funktionen ohne benannten ersten Parameter wie NEVER_MUTATE behandeln | 🔲 |
| 6.3 | Kollisionsfreie Wrapper-Locals (`_mutmut_args`/`_mutmut_kwargs`) | 🔲 |
| 6.4 | Starred-aware Argument-Forwarding (kein blindes `args[1:]`) | 🔲 |
| 6.5 | Async-Generator: Objekt direkt zurückgeben statt `async for`-Wrapping | 🔲 |
| 6.6 | Dogfooding auf mutation.py/trampoline.py; Tests grün; Ruff + mypy clean | 🔲 |

---

## Out of Scope (Sprint 29+, aus dem Audit)

- **C3 Pool-Robustheit** (EW-001 Queue-Shutdown, EW-002 Worker-Liveness) —
  eigener Sprint, berührt Executor-Architektur
- **C4 Rest** (timeout_multiplier-Semantik, task.timeout_seconds-Wiring,
  WallClockTimeout entfernen/verdrahten) — zusammen mit C3
- **C5 IL-Detection ehrlich machen** (Forensik-Persistenz + Rendering,
  Windows-Realismus) — eigener Sprint
- **C6 tote Features** (Type-Checker-Filter, Coverage-guided) — eigener Sprint
- **C7–C9** Score-Integrität, Pipeline-Hygiene, UX — Folge-Sprints
- pip-audit-Baseline (SSL-Problem der Umgebung) — nachholen sobald möglich

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest --ignore=tests/e2e_projects` | 610 + ~25 neue = ≥ 630 passed |
| Adversarial-Gate | neuer Fixture-Test | jede generierte Mutanten-Datei kompiliert; Clean-Run des Fixtures grün |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors |
| Security | `semgrep scan --config auto src/ tests/unit/ tests/integration/` | 0 Findings |
| Architecture | `uv run lint-imports` | 0 Verletzungen |
| Mutation Testing | `uv run mutmut-win run --paths-to-mutate <geänderte Module>` | Score ≥ 80 % auf neuem Code |

---

## Release v2.6.0

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.6.0 | 🔲 |
| Annotated Tag v2.6.0 | 🔲 |
| GitHub Release v2.6.0 (Changelog: W4.11-Blocker geschlossen, Quell-Schutz, Codegen-Korrektheit; Hinweis an Downstream: Genexp-Workaround §1.5 rückbaubar) | 🔲 |
| Auto-close #73, #74, #75, #76, #77, #78 via Merge-Commit | 🔲 |
| MEMORY.md + product_backlog.md update | 🔲 |
