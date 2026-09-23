# Sprint 43 Backlog — R0: Vorbereitung, Stand-Abgleich und Baseline

| | |
|---|---|
| **Ziel** | R0 der Sanierung v2.21.4: Baseline-Gates, gemeinsame Testinfrastruktur Q-01 bis Q-05, P-08-Entscheidungsliste |
| **Baseline** | `main` = `5a491a0e6b9b2d1bd8beaf8258a314e0074ed665` (nur docs: `.sprint/state.md`, `MEMORY.md`, Sprint-42-Backlog); Codebaum identisch mit Review-Stand `4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b` (Tag `v2.21.4`) — verifiziert via `git diff 4d7f950 HEAD --stat` (nur die drei Doku-Dateien) |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `chore/141-remediation-baseline` (Issue #141) |
| **Start** | 2026-09-23 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |
| **Sprintzuschnitt** | R0=43, R1=44 (AP-00b, AP-01…AP-08, AP-08b), R2=45 (AP-09…AP-32 inkl. 29b), R3=46 (AP-33…AP-46), R4=47 (AP-47); je Phase ein GitHub-Milestone (#7–#11) und 51 AP-Issues (#141–#191) |

## Auslöser

Zwei unabhängige Reviews, zwei Kreuzreviews und ein Abschlussbericht haben
146 Mechanismusgruppen mit tragendem Defekt in v2.21.4 erhoben (9 high,
56 medium, 81 low). Das Handover `HANDOVER_GLM-5.3.md` ordnet sie in 51
Arbeitspakete und 5 Phasen. Jeder Befund wird vor jedem Fix mit Serena am
Code verifiziert und durch einen vorher rot laufenden Regressionstest belegt
— nichts aus den Berichten wird ungeprüft übernommen.

## Arbeitsumfang

- [x] Stand-Abgleich: `main` liegt einen Doku-Commit über dem Review-Stand; Codebaum identisch (s. o.). Alle Berichtsorte werden per Serena-Symbolverortung neu lokalisiert, nie blind nach Zeilennummer geändert.
- [x] Externe Gate-Umgebungen: `UV_PROJECT_ENVIRONMENT` und `HYPOTHESIS_STORAGE_DIRECTORY` zeigen auf absolute Verzeichnisse außerhalb des Checkouts (`%TEMP%\opencode\uv-env-r0`, `...\hypothesis-r0`); im Checkout entsteht keine `.venv`, kein Werkzeug-Cache, kein `.hypothesis`.
- [x] Baseline der schnellen Gates (auf `5a491a0`, unverändertem Stand):
      - `ruff check --no-cache .` → **All checks passed!**
      - `ruff format --no-cache --check .` → **188 files already formatted**
      - `mypy --no-incremental --cache-dir=nul src/` → **Success: no issues found in 40 source files**
      - `lint-imports --no-cache` → **Layer architecture KEPT, 1 kept, 0 broken**
- [ ] Baseline `pytest -p no:cacheprovider` (läuft; Vollsuite >60 min, serial; Ergebnis wird hier nachgetragen; bekannte fragile Tests per P-17: `tests/integration/test_il_detection.py`, Grandchild-Test `tests/unit/test_job_object.py::test_kill_on_close_kills_grandchild` bis AP-00b/AP-08b mit dokumentierter serieller Wiederholung)
- [x] Serena-Onboarding auf den Hauptmodulen (worker, executor, file_setup, stats, orchestrator, cli, config, mutation, node_mutation, atomic_file, gitignore_boundary, db, process/run_lock, browser, process/job_object).
- [x] Q-01 Fault-Injection-Harness `tests/unit/atomic_fault_util.py` mit Eigentests (`tests/unit/test_atomic_fault_util.py`, 7 Tests).
- [x] Q-02 Windows-Dateisystem-Fixtures `tests/unit/windows_fs_util.py` + conftest-Fixtures (readonly, junction, byte-range-lock, sharing violation, Langname, Surrogat) mit Eigentests (`tests/unit/test_windows_fs_util.py`, 8 Tests).
- [x] Q-03 runpy-Lader für generierte Plugin-Quelltexte `tests/unit/guard_plugin_util.py` (Phase-Guard inkl. produktgetreuer Boundary-Env, Stats-Plugin) mit Eigentests (`tests/unit/test_guard_plugin_util.py`, 5 Tests).
- [x] Q-04 Prozessbaum-Testhilfen `tests/unit/process_tree_util.py` (wait_for_pid_file mit Frist, atomarer PID-Snippet, tree_handles, tree_cpu_seconds, assert_tree_terminated) mit Eigentests (`tests/unit/test_process_tree_util.py`, 7 Tests).
- [x] Q-05 Mutation-Gate-Matrix dokumentiert (unten); jedes AP verfeinert sie für seine Module.
- [x] 51 AP-Issues (#141–#191) mit Gruppen-Checklisten und 5 Milestones angelegt.
- [x] P-08-Entscheidungsliste dem Nutzer vorgelegt (R1: M-003, M-008, M-144 Stufe 2; R2/R3-Entscheidungen gesammelt im Handover P-08).
- [ ] Sprintabschluss R0 nach P-16: Phasengate (ruff/format/mypy/lint-imports/pytest, Mutation-Gate entfällt mangels src-Änderung — begründet —, kanonisches Semgrep-Gate, pip-audit), MEMORY.md, Issues.

## Q-05: Mutation-Gate-Matrix (Engine-Self-Mutation)

Regel (P-05): Module der Werkzeugmaschinerie werden nur per gezieltem Gate
mutiert — `uv run --no-sync mutmut-win run --paths-to-mutate <Modul>` mit
genau den Contract-Tests des Moduls als einzigem `--tests-dir`. Ein
suitenweiter Lauf ist kein Beweis. Startpunkt; jedes AP passt die Zuordnung
an seinen konkreten Fix an (neue Testdateien ergänzen die Listen):

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
| `code_coverage.py` | `tests/unit/test_code_coverage.py`, `test_coverage_gating.py` (integration) |
| `pytest_boundary.py` | `tests/unit/test_pytest_boundary_security_220.py`, `test_pytest_target_argfile_221.py`, `test_windows_path_alias_221.py` |
| `process/output_capture.py` | `tests/unit/test_bounded_output_capture_220.py` |

## Abgrenzungen / Konventionen dieses Sprints

- Die Berichtsdateien (ASTRA_*, CLAUDE_*, HANDOVER_GLM-5.3.md, OVERLAP_CANDIDATES.json, Review-Abschlussbericht.md) bleiben ungetrackt und werden nicht committet.
- Keine Produktänderung in R0; Mutation-Gate entfällt deshalb begründet (P-04(7)).
- Die neue Testinfrastruktur (Q-01 bis Q-04) ist selbst getestet (27 Eigentests) und Ruff- sauber; sie verändert kein Produktverhalten.
