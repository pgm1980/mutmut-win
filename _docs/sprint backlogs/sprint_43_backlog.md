# Sprint 43 Backlog

| | |
|---|---|
| **Ziel** | v2.21.5 |
| **Baseline** | `main` = `5a491a0e6b9b2d1bd8beaf8258a314e0074ed665` (nur Doku-Änderungen: `.sprint/state.md`, `MEMORY.md`, Sprint-42-Backlog); Codebaum identisch mit Review-Stand `4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b` (Tag `v2.21.4`) — per `git diff 4d7f950 HEAD --stat` belegt |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v2.21.5-remediation-r0` |
| **Start** | 2026-09-23 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot.

## Auslöser

Zwei unabhängige Reviews, zwei Kreuzreviews und ein Abschlussbericht haben
146 Mechanismusgruppen mit tragendem Defekt in v2.21.4 erhoben (9 high,
56 medium, 81 low). Das Handover `HANDOVER_GLM-5.3.md` (ungetrackt, nicht
committet) ordnet sie in 51 Arbeitspakete und 5 Phasen R0–R4. Sprint 43
deckt R0 ab: Vorbereitung, Stand-Abgleich, Baseline und gemeinsame
Testinfrastruktur. Jeder Befund wird vor jedem Fix mit Serena am Code
verifiziert und durch einen vorher rot laufenden Regressionstest belegt.

## Arbeitsumfang (R0 / AP-00, Issue #141)

- [x] Stand-Abgleich gegen den Review-Stand sowie externe Gate-Umgebungen (UV_PROJECT_ENVIRONMENT, HYPOTHESIS_STORAGE_DIRECTORY außerhalb des Checkouts)
- [x] Baseline aller Gates auf unverändertem Stand (ruff check/format, mypy strict, lint-imports, Vollsuite pytest mit P-17-Behandlung der fragilen Tests)
- [x] Serena-Onboarding auf den Hauptmodulen der Sanierung
- [x] Testhilfen Q-01 bis Q-04 (Fault-Injection, Windows-FS-Zustände, Plugin-Lader, Prozessbaum) mit eigenen Tests
- [x] Q-05 Mutation-Gate-Matrix für Engine-Module dokumentieren
- [x] 51 AP-Issues mit Gruppen-Checklisten, 5 Milestones und Sprintzuschnitt R0 bis R4 anlegen
- [x] P-08-Entscheidungsliste gesammelt dem Nutzer vorlegen (R1-Entscheidungen M-008, M-003, M-144 Stufe 2 in den Issues #143/#145/#149)
- [x] Phasengate R0: kanonisches Semgrep-Gate und pip-audit mit echter Ausgabe belegen
- [x] Sprintabschluss R0: Backlog finalisieren, MEMORY.md aktualisieren, Issues mit Verifikationsergebnis schließen

## Baseline-Protokoll (Stand `5a491a0`, unverändert)

- `uv run --no-sync ruff check --no-cache .` → **All checks passed!**
- `uv run --no-sync ruff format --no-cache --check .` → **188 files already formatted**
- `uv run --no-sync mypy --no-incremental --cache-dir=nul src/` → **Success: no issues found in 40 source files** (vorbestehende Warnung zu ungenutzter `module = ['tests.*']`-Sektion)
- `uv run --no-sync lint-imports --no-cache` → **Layer architecture (ADR layer contracts v2) KEPT; Contracts: 1 kept, 0 broken**
- `uv run --no-sync pytest -p no:cacheprovider` → **3 failed, 2600 passed, 43 skipped in 45:31**; alle drei Fehlschläge in `tests/unit/test_release_supply_chain.py` waren umgebungs- bzw. metadata-bedingt (fehlendes `hatchling` aus der build-Gruppe in der frischen externen Umgebung; zwischenzeitlich unvollständiges state.md-Schema während des Laufs) und sind mit korrigierter Umgebung bzw. vertragsgerechter `state.md` behoben; die fragilen Tests aus P-17 (`test_il_detection.py`, Grandchild-Test) sind in diesem Lauf grün.

## Q-05: Mutation-Gate-Matrix (Engine-Self-Mutation)

Regel (P-05): Module der Werkzeugmaschinerie werden nur per gezieltem Gate
mutiert — `uv run --no-sync mutmut-win run --paths-to-mutate <Modul>` mit
genau den Contract-Tests des Moduls als einzigem `--tests-dir`. Ein
suitenweiter Lauf ist kein Beweis. Startpunkt; jedes AP passt die Zuordnung
an seinen konkreten Fix an (neue Testdateien ergänzen die Listen).

| Engine-Modul | Contract-Testdateien (einziger `--tests-dir`) |
|---|---|
| `gitignore_boundary.py` | `tests/unit/test_gitignore_boundary.py` |
| `config.py` | `tests/unit/test_config.py`, `test_config_cli_truth.py`, `test_hygiene_110.py` |
| `hit_recording.py` | `tests/unit/test_hit_recording.py` |
| `stats.py` | `tests/unit/test_stats.py`, `test_stats_truth.py`, `test_stats_basis_diagnostics.py`, `test_basis_diagnostics.py`, `test_dependency_basis_220.py` |
| `basis_diagnostics.py` | `tests/unit/test_basis_diagnostics.py`, `test_basis_diagnostics_hash_contract.py`, `test_basis_diagnostics_transition_contract.py`, `test_stats_basis_diagnostics.py` |
| `type_checking.py` | `tests/unit/test_type_checking.py`, `test_type_checker_filter.py`, `test_type_check_baseline_131.py` |
| `db.py` | `tests/unit/test_db.py`, `test_db_hardening.py`, `test_db_state_boundary_220.py`, `test_run_identity_220.py`, `test_db_purge.py`, `test_corrupt_cache.py`, `test_review_cache_integrity.py`, `test_result_reuse_119.py` |
| `process/worker.py` | `tests/unit/test_process_worker.py`, `test_runner_sidecar_safety.py`, `test_surface_hardening_220.py`, `test_worker_crash_recovery.py`, `test_hardening_132.py` |
| `process/loop_monitor.py` | `tests/unit/test_loop_monitor.py`, `test_cicd_il_bucket.py` |
| `process/executor.py` | `tests/unit/test_process_executor.py`, `test_pool_collapse_127.py` |
| `process/job_object.py` | `tests/unit/test_job_object.py` + `tests/integration/test_job_object_kill_on_close.py` |
| `process/generation_supervisor.py` | `tests/unit/test_generation_supervisor_teardown.py` + `tests/integration/test_generation_supervisor.py` |
| `runner.py` | `tests/unit/test_runner.py`, `test_runner_diagnostics.py`, `test_runner_argfile_221.py`, `test_runner_sidecar_safety.py` |
| `file_setup.py` | `tests/unit/test_file_setup.py`, `test_gitignore_staging_integration.py`, `test_mutant_safety_net.py`, `test_atomic_spawn.py`, `test_staging_hygiene.py` |
| `orchestrator.py` | `tests/unit/test_orchestrator.py`, `test_per_task_timeouts.py`, `test_timeout_model.py`, `test_timeout_display.py` |
| `atomic_file.py` | `tests/unit/test_atomic_write_safety_220.py`, `test_atomic_transient_retry.py` |
| `process/run_lock.py` | `tests/unit/test_run_lock.py` |
| `mutation.py` (Trampolin) | `tests/unit/test_trampoline.py`, `test_mutation.py`, `test_duplicate_definitions_220.py`, `test_class_body_injection.py` |
| `mutation.py` (Visitor/Fläche) | `tests/unit/test_mutation.py`, `test_mutation_surface_121.py`, `test_do_not_mutate_patterns.py`, `test_multiline_or_skip.py`, `test_closure_117.py` |
| `node_mutation.py` | `tests/unit/test_node_mutation.py`, `test_math_mutations.py`, `test_safe_unwrap.py`, `test_all_tier_operators.py`, `test_advanced_operators.py`, `test_return_conditional.py`, `test_statement_collection_or.py` |
| `regex_mutation.py` | `tests/unit/test_regex_mutation.py`, `test_robustness_123.py` |
| `models.py` | `tests/unit/test_models.py`, `test_status_truth.py` |
| `cli.py` | `tests/unit/test_cli.py`, `test_cli_consistency_115.py`, `test_cli_basis_diagnostics.py`, `test_cli_containment_contract.py`, `test_ci_output_discipline.py`, `test_score_status_122.py` |
| `browser.py` | `tests/unit/test_browser_diff.py`, `test_browser_il.py`, `test_browser_evidence_invalidation_220.py` |
| `mutant_diff.py` | `tests/unit/test_mutant_diff.py`, `test_show_forensics.py` |
| `code_coverage.py` | `tests/unit/test_code_coverage.py` |
| `pytest_boundary.py` | `tests/unit/test_pytest_boundary_security_220.py`, `test_pytest_target_argfile_221.py`, `test_windows_path_alias_221.py` |
| `process/output_capture.py` | `tests/unit/test_bounded_output_capture_220.py` |

## Konventionen dieses Sprints

- Die Berichtsdateien (ASTRA_*, CLAUDE_*, HANDOVER_GLM-5.3.md, OVERLAP_CANDIDATES.json, Review-Abschlussbericht.md) bleiben ungetrackt und werden nicht committet.
- Keine Produktänderung in R0; das gezielte Mutation-Gate entfällt deshalb begründet (P-04(7)).
- Die Testinfrastruktur (Q-01 bis Q-04) ist selbst getestet (27 Eigentests) und Ruff-sauber; sie verändert kein Produktverhalten.
