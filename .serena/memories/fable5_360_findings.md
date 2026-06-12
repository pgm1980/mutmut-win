# Fable-5 360° Analysis (2026-06-12) — Findings Inventory

Full report: `_docs/audit/fable5_360_analysis_v2.13.0.md` (line refs pinned to `main @ 2e481fd`, v2.13.0).
Result: **9 confirmed bugs (A) · 13 anomalies (B) · 6 optimizations (C)** · 1 refuted suspicion (job_object ctypes const — NOT a bug).
Machine gates at analysis time: Semgrep initially CE (320 rules, 0 findings); after Pro activation re-scanned with **SAST, 1228 rules — still 0 findings**. mypy = 14 baseline. ruff red only in `.claude/skills/` (B13).

## A — Confirmed bugs
| ID | Sev | Finding | Location |
|---|---|---|---|
| A1 | High | `_update_source_data` prefix mismatch: meta files NEVER get exit codes/durations on src-layouts (norm_path keeps `src.`, mutant names are stripped; also unanchored startswith → `util` vs `utils` cross-match). Empirically verified: real .meta all-null vs DB 212 killed/44 survived. `browse` shows everything "not checked" | orchestrator.py:1301, file_setup.py:495 |
| A2 | High | Worker passes tests via `@argfile` — pytest feature exists only since **8.2** (docs: "Added in version 8.2"); declared floor `pytest>=6.2.5`. Target venvs with older pytest → suspicious flood for every covered mutant | process/worker.py:172, pyproject.toml |
| A3 | High | `get_mutant_name` strips only `src.`, not `source.` — though source/ is a supported staging root everywhere else → source/-layouts: ALL mutants "no tests" (name ≠ orig.__module__). Mirror case: root package literally named `src` | file_setup.py:495 |
| A4 | Med | `--since-commit`: (a) test-file exclusion compares parts[0] vs full tests_dir → broken for nested tests_dir (e.g. `tests/unit/` — this project!), changed test files become mutation targets; (b) `ref..HEAD` misses uncommitted working-tree changes | cli.py:273, cli.py:255 |
| A5 | Med | README example `type_check_command = ["mypy", "src/"]` guaranteed to abort: mypy parser requires `--output=json` (mypy ≥1.11), pyright needs `--outputjson`; no config-load validation/hint | README.md:186, type_checking.py:92 |
| A6 | Med | `--output json` stdout polluted: `--force` echo + config warnings print BEFORE redirect_stdout (cli.py:333); child-process prints (worker recovery/monitor, pool workers) bypass the Python-level redirect via OS fd 1 | cli.py:220, config.py:483, worker.py:115 |
| A7 | Med | Pool collapse (all workers dead) → loop breaks, `was_interrupted` stays False → exit 0 without gate; `--min-score` computed over checked remainder (unchecked leaves denominator) → CI false-green | executor.py:187, orchestrator, cli |
| A8 | Med | Engine version missing from config fingerprint + staging fast-path → after mutmut-win upgrade old mutant universe persists silently (v2.13 f-string mutants never appear on unchanged files) until source change/--force | file_setup.py:345 |
| A9 | Low | `show <glob>` loses IL forensics panel (DB lookup uses raw pattern instead of resolved name) | cli.py:562 |

## B — Anomalies
B1 Med — in-place edited tests don't refresh test↔function mapping (only new/removed node IDs trigger; "re-run for them" message misleading — `tests` param unused, always full run) (stats.py:160). B2 Med — collect_tests scope mismatch: no cwd/tests_dir/pytest_add_cli_args → permanent full re-collection w/ marker filters or missing testpaths; strict utf-8 pipe decode (runner.py:187). B3 Med — empty mapping + durations present → full-suite run budgeted with single-test mean → timeout flood (orchestrator.py:788). B4 Med — type-check filter w/o baseline subtraction: pre-existing in-function type error replicates into every mutant copy → all falsely "caught" (inherited). B5 — phase timeouts (`_run_phase`) kill only direct child, no job object/psutil sweep for grandchildren. B6 — staging stale gaps: backdated restores of non-mutated files survive `>` mtime check (file_setup.py:179); deleted test files under "." root run forever (no deletion sync, copytree never deletes). B7 — extra_paths with `..`: PYTHONPATH points at real sibling, staged copy unused (worker.py:192). B8 — EXIT_CODE_INFINITE_LOOP + status string duplicated (constants.py:80 vs loop_monitor.py:511). B9 — setup.cfg path: no extra_paths/infinite_loop_* keys, no unknown-key warning. B10 — meta load tolerates only decode errors; valid JSON w/ wrong types (duration: null) → unhandled TypeError. B11 — nested-class methods silently never mutated (mutation.py:83, inherited, no warning). B12 — results/export count legacy interrupted/not-checked rows in denominator (README claims formula identity). B13 — `uv run ruff check .` red: 23 findings all in `.claude/skills/` — ruff exclude missing `.claude/`.

## C — Optimizations
C1 save_result: 2 connections + schema check PER mutant; _persist_skipped loads whole DB + per-name saves → one connection per run + executemany. C2 copy_also_copy_files re-copies tests/ fully every run (mtime sync like copy_src_dir). C3 implement unused `tests` param: targeted incremental stats re-run. C4 copy_src_dir: "." walk copies src/source twice; extend skip_dirs (node_modules, .import_linter_cache, .benchmarks, .serena, .claude). C5 dedupe regex duplicate mutants. C6 status_by_exit_code defaultdict mutates on lookup → plain dict + .get.

## Suggested priority waves (report §8)
1: A1+A2 → 2: A6+A7 → 3: A3+A8+A4 → 4: A5+B13, B1–B4 → 5: rest B + C bundled.
Bugfix sprint planning started 2026-06-12 (post-analysis; will end the development pause).
