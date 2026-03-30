# 360-Grad Cross-Check v3 — Exhaustive Symbol-by-Symbol Comparison

**Date:** 2026-03-30  
**Scope:** mutmut 3.5.0 (`_references/mutmut-3.5.0_source/src/mutmut/`) vs. mutmut-win (`src/mutmut_win/`)  
**Method:** Every symbol read with Serena `find_symbol(include_body=true)` or full file read, compared line-by-line.

---

## Table of Contents

1. [Architecture Mapping](#1-architecture-mapping)
2. [__init__.py](#2-__init__py)
3. [trampoline_templates.py → trampoline.py](#3-trampoline_templatespy--trampolinepy)
4. [code_coverage.py](#4-code_coveragepy)
5. [type_checking.py](#5-type_checkingpy)
6. [node_mutation.py](#6-node_mutationpy)
7. [file_mutation.py → mutation.py](#7-file_mutationpy--mutationpy)
8. [__main__.py → Decomposed Modules](#8-__main__py--decomposed-modules)
   - 8.1 [constants.py (status_by_exit_code, emoji_by_status, etc.)](#81-constantspy)
   - 8.2 [exceptions.py](#82-exceptionspy)
   - 8.3 [config.py (Config, load_config, guess_paths_to_mutate)](#83-configpy)
   - 8.4 [models.py (SourceFileMutationData, etc.)](#84-modelspy)
   - 8.5 [_state.py (globals)](#85-_statepy)
   - 8.6 [__main__.py (record_trampoline_hit)](#86-__main__py)
   - 8.7 [file_setup.py (walk/copy/mutant generation)](#87-file_setuppy)
   - 8.8 [runner.py (PytestRunner)](#88-runnerpy)
   - 8.9 [stats.py (save/load/collect stats)](#89-statspy)
   - 8.10 [test_mapping.py](#810-test_mappingpy)
   - 8.11 [type_checker_filter.py](#811-type_checker_filterpy)
   - 8.12 [mutant_diff.py (show/apply/diff)](#812-mutant_diffpy)
   - 8.13 [cli.py (Click commands)](#813-clipy)
   - 8.14 [browser.py (ResultBrowser TUI)](#814-browserpy)
   - 8.15 [orchestrator.py (_run pipeline)](#815-orchestratorpy)
   - 8.16 [process/ (executor, worker, timeout)](#816-process)
   - 8.17 [db.py (SQLite persistence)](#817-dbpy)
9. [Removed/Unsupported Symbols](#9-removedunsupported-symbols)
10. [Summary Statistics](#10-summary-statistics)
11. [Findings List](#11-findings-list)
12. [Recommendations](#12-recommendations)

---

## 1. Architecture Mapping

The original mutmut 3.5.0 is a monolithic codebase with one massive `__main__.py` (~1700 lines) plus four focused modules. mutmut-win decomposes this into 20+ focused modules.

| Original File | mutmut-win Target(s) |
|---|---|
| `__init__.py` | `__init__.py`, `_state.py` |
| `__main__.py` | `cli.py`, `config.py`, `models.py`, `exceptions.py`, `constants.py`, `db.py`, `runner.py`, `stats.py`, `orchestrator.py`, `file_setup.py`, `mutant_diff.py`, `test_mapping.py`, `type_checker_filter.py`, `browser.py`, `__main__.py`, `process/executor.py`, `process/worker.py`, `process/timeout.py` |
| `file_mutation.py` | `mutation.py` |
| `node_mutation.py` | `node_mutation.py` |
| `trampoline_templates.py` | `trampoline.py` |
| `code_coverage.py` | `code_coverage.py` |
| `type_checking.py` | `type_checking.py` |

---

## 2. __init__.py

### Original (`__init__.py`)
| Symbol | Line | Status | Notes |
|---|---|---|---|
| `__version__` | 3 | EQUIVALENT | Original reads from `importlib.metadata.version("mutmut")`. mutmut-win hardcodes `"0.1.0"`. Both export a version string. |
| `duration_by_test` | 7 | MOVED | Moved to `_state.py`. Type changed from `defaultdict(float)` to `dict[str, float]` — **ABWEICHUNG** |
| `stats_time` | 8 | MOVED | Moved to `_state.py`. IDENTISCH semantics. |
| `config` | 9 | REMOVED | Global config removed. mutmut-win passes config as parameter. EQUIVALENT (architectural improvement). |
| `_stats` | 11 | MOVED | Moved to `_state.py`. IDENTISCH. |
| `tests_by_mangled_function_name` | 12 | MOVED | Moved to `_state.py`. IDENTISCH type. |
| `_covered_lines` | 13 | REMOVED | Not in `_state.py`. Coverage is handled locally in orchestrator. EQUIVALENT. |
| `_reset_globals()` | 14-23 | EQUIVALENT | Moved to `_state.py`. Does not reset `config` or `_covered_lines` (removed globals). Does not reassign `_stats`/`tests_by_mangled_function_name` with new instances but calls `.clear()` — functionally identical. |

### Findings for __init__.py

| # | Severity | Finding |
|---|---|---|
| F01 | LOW | `duration_by_test` changed from `defaultdict(float)` to plain `dict`. The `defaultdict(float)` auto-returns 0.0 for missing keys; plain dict will raise `KeyError`. Code that accesses it uses `.get()`, so this is safe in practice. |
| F02 | INFO | `__version__` hardcoded instead of reading from metadata. Acceptable for fork. |

---

## 3. trampoline_templates.py → trampoline.py

| Symbol | Original Line | mutmut-win Line | Status | Notes |
|---|---|---|---|---|
| `CLASS_NAME_SEPARATOR` | 1 | 3 | IDENTISCH | `'ǁ'` in both. |
| `create_trampoline_lookup()` | 3-11 | 6-28 | EQUIVALENT | Identical logic. mutmut-win adds type hints, docstrings, uses `!r` format specifier instead of `repr()`. Functionally identical. |
| `mangle_function_name()` | 13-19 | 31-49 | ABWEICHUNG | Original uses `assert` for validation. mutmut-win uses `raise ValueError`. **Behavioral difference**: ValueError is catchable differently than AssertionError, and assertions can be disabled with `-O`. mutmut-win is stricter. |
| `trampoline_impl` | 22-57 | 52-85 | ABWEICHUNG | **CRITICAL**: Original imports from `mutmut.__main__`, mutmut-win imports from `mutmut_win.__main__`. This is the correct adaptation for the fork. All other logic is line-for-line identical. |

### Findings for trampoline

| # | Severity | Finding |
|---|---|---|
| F03 | LOW | `mangle_function_name` uses `ValueError` instead of `assert`. Functionally safer; no behavioral issue. |
| F04 | INFO | `trampoline_impl` correctly changed import paths from `mutmut` to `mutmut_win`. |

---

## 4. code_coverage.py

| Symbol | Original Line | mutmut-win Line | Status | Notes |
|---|---|---|---|---|
| `get_covered_lines_for_file()` | 10-18 | 12-21 | IDENTISCH | Identical logic. |
| `gather_coverage()` | 23-50 | 27-55 | IDENTISCH | Identical logic. |
| `_unload_modules_not_in()` | 53-58 | 59-64 | ABWEICHUNG | Original skips `'mutmut.code_coverage'`, mutmut-win skips `'mutmut_win.code_coverage'`. Correct adaptation. |

### Findings for code_coverage

| # | Severity | Finding |
|---|---|---|
| F05 | INFO | Module self-reference correctly updated from `mutmut.code_coverage` to `mutmut_win.code_coverage`. |

---

## 5. type_checking.py

| Symbol | Original Line | mutmut-win Line | Status | Notes |
|---|---|---|---|---|
| `TypeCheckingError` | 8-12 | 11-17 | IDENTISCH | Same dataclass with same fields. |
| `run_type_checker()` | 16-39 | 21-53 | EQUIVALENT | Same logic. mutmut-win adds `# noqa: S603` for subprocess, chains exception with `from exc`, uses `cast("dict", ...)` string form. Early returns instead of `elif` chain. Functionally identical. |
| `parse_pyright_report()` | 42-54 | 56-68 | EQUIVALENT | Same logic, mutmut-win uses list comprehension instead of loop. |
| `parse_pyrefly_report()` | 56-68 | 71-82 | EQUIVALENT | Same logic, list comprehension. |
| `parse_mypy_report()` | 70-81 | 85-95 | EQUIVALENT | Same logic, list comprehension with filter. |
| `parse_ty_report()` | 83-96 | 98-110 | EQUIVALENT | Same logic, list comprehension with filter. |

### Findings for type_checking

No findings. All functions are logically identical.

---

## 6. node_mutation.py

| Symbol | Original Line | mutmut-win Line | Status | Notes |
|---|---|---|---|---|
| `OPERATORS_TYPE` | 8-12 | 11-15 | IDENTISCH | |
| `NON_ESCAPE_SEQUENCE` | 15 | 18 | IDENTISCH | |
| `operator_number()` | 17-23 | 21-29 | IDENTISCH | |
| `operator_string()` | 26-53 | 32-61 | EQUIVALENT | mutmut-win uses `value.startswith(('"""', "'''"))` tuple form vs two `startswith` with `or`. Functionally identical. |
| `operator_lambda()` | 56-60 | 64-69 | IDENTISCH | |
| `operator_dict_arguments()` | 63-76 | 72-87 | IDENTISCH | |
| `operator_arg_removal()` | 79-90 | 90-102 | IDENTISCH | |
| `supported_symmetric_str_methods_swap` | 93-106 | 105-118 | IDENTISCH | Same 14 pairs. |
| `supported_unsymmetrical_str_methods_swap` | 108-111 | 120-123 | IDENTISCH | |
| `operator_symmetric_string_methods_swap()` | 113-119 | 126-132 | IDENTISCH | |
| `operator_unsymmetrical_string_methods_swap()` | 121-133 | 135-149 | EQUIVALENT | mutmut-win merges the outer `if m.matches` with the inner `if old_call in {...}` using `and`. Logically identical. |
| `operator_remove_unary_ops()` | 137-139 | 152-155 | IDENTISCH | |
| `_keyword_mapping` | 141-148 | 158-165 | IDENTISCH | Same 6 entries. |
| `operator_keywords()` | 150-152 | 168-170 | IDENTISCH | |
| `operator_name()` | 155-162 | 173-181 | IDENTISCH | Same mapping: True↔False, deepcopy→copy. |
| `_operator_mapping` | 164-198 | 183-217 | IDENTISCH | Same 28 entries. |
| `operator_swap_op()` | 200-207 | 220-234 | EQUIVALENT | mutmut-win uses multi-line formatting and string-form `cast()`. Logically identical. |
| `operator_augmented_assignment()` | 210-213 | 237-239 | IDENTISCH | |
| `operator_assignment()` | 216-225 | 242-253 | EQUIVALENT | Uses `cst.Assign | cst.AnnAssign` union syntax instead of `Union[...]`. |
| `operator_match()` | 227-230 | 256-259 | IDENTISCH | |
| `mutation_operators` | 233-248 | 262-277 | IDENTISCH | Same 15 entries in same order. |
| `_simple_mutation_mapping()` | 251-255 | 280-284 | IDENTISCH | |

### Findings for node_mutation

No findings. All 21 symbols are identical or cosmetically equivalent.

---

## 7. file_mutation.py → mutation.py

| Symbol | Original Line | mutmut-win Line | Status | Notes |
|---|---|---|---|---|
| `NEVER_MUTATE_FUNCTION_NAMES` | 12 | 14 | IDENTISCH | `{"__getattribute__", "__setattr__", "__new__"}` |
| `NEVER_MUTATE_FUNCTION_CALLS` | 13 | 15 | IDENTISCH | `{"len", "isinstance"}` |
| `Mutation` | 15-19 | 18-22 | EQUIVALENT | Uses `cst.FunctionDef | None` instead of `Union[...]`. |
| `mutate_file_contents()` | 22-28 | 25-35 | EQUIVALENT | mutmut-win adds `# noqa: ARG001` for unused `filename` param. Logic identical. |
| `create_mutations()` | 30-42 | 38-52 | IDENTISCH | |
| `OuterFunctionProvider` | 44-63 | 55-77 | EQUIVALENT | mutmut-win adds `# noqa: N802` for `visit_Module`. Logic identical. |
| `OuterFunctionVisitor` | 66-73 | 80-88 | IDENTISCH | |
| `MutationVisitor.__init__()` | 83-88 | 100-107 | EQUIVALENT | Uses `set[int] | None` syntax. |
| `MutationVisitor.on_visit()` | 90-98 | 109-117 | IDENTISCH | |
| `MutationVisitor._create_mutations()` | 100-109 | 119-130 | EQUIVALENT | Same logic. Type ignore comment has specific error code. |
| `MutationVisitor._should_mutate_node()` | 111-121 | 132-145 | EQUIVALENT | Uses `not in` instead of `not ... in`. |
| `MutationVisitor._skip_node_and_children()` | 123-139 | 147-170 | EQUIVALENT | Decomposed into named boolean variables for readability. Same logic, same conditions, same return values. Uses `bool(...)` return instead of bare `return True`/`return False`. |
| `MODULE_STATEMENT` | 143 | 173 | EQUIVALENT | Uses `|` union syntax. |
| `trampoline_impl_cst` | 146-147 | 176-179 | IDENTISCH | |
| `combine_mutations_to_source()` | 150-192 | 182-232 | IDENTISCH | Same iteration logic, same node handling. |
| `function_trampoline_arrangement()` | 194-225 | 235-271 | IDENTISCH | Same mangling, same node construction. |
| `create_trampoline_wrapper()` | 228-291 | 274-340 | EQUIVALENT | mutmut-win uses list comprehension for `args` and `kwargs` initial population; removes vestigial `function.whitespace_after_type_parameters` call. Adds explicit `result_statement` type annotation. Logic identical. |
| `_get_local_name()` (nested) | 260-267 | 301-308 | IDENTISCH | |
| `get_statements_until_func_or_class()` | 294-302 | 343-353 | IDENTISCH | |
| `group_by_top_level_node()` | 304-310 | 356-364 | EQUIVALENT | Renames loop variable `m` to `mut` to avoid shadowing. |
| `pragma_no_mutate_lines()` | 312-316 | 367-373 | IDENTISCH | |
| `deep_replace()` | 318-320 | 376-378 | EQUIVALENT | Type ignore has specific error code `[return-value]`. |
| `ChildReplacementTransformer` | 322-335 | 381-396 | IDENTISCH | |
| `_is_generator()` | 337-340 | 399-402 | IDENTISCH | |
| `IsGeneratorVisitor` | 342-351 | 405-421 | EQUIVALENT | Adds return type annotations and `# noqa: N802`. Original returns implicit `None`; mutmut-win returns explicit `None`. |

### Findings for file_mutation/mutation

| # | Severity | Finding |
|---|---|---|
| F06 | INFO | Vestigial `function.whitespace_after_type_parameters` statement removed from `create_trampoline_wrapper`. This was a no-op line in the original. |

---

## 8. __main__.py → Decomposed Modules

### 8.1 constants.py

| Symbol | Original Location | mutmut-win Location | Status | Notes |
|---|---|---|---|---|
| `status_by_exit_code` | `__main__.py:72-91` | `constants.py:8-24` | **ABWEICHUNG** | **CRITICAL DIFF**: Original has Unix signal codes: `-24: 'killed'` (duplicate), `-24: 'timeout'` (SIGXCPU), `24: 'timeout'`, `152: 'timeout'`, `-11: 'segfault'`, `-9: 'segfault'`. mutmut-win removes ALL signal-based codes (`-24`, `24`, `152`, `-11`, `-9`). This is intentional for Windows but means **Unix signal-based exit codes will all map to `'suspicious'` (the default)**. |
| `emoji_by_status` | `__main__.py:93-104` | `constants.py:26-37` | EQUIVALENT | Same 10 entries. mutmut-win uses Unicode escape sequences instead of emoji literals. The `"killed"` entry has empty string `""` in mutmut-win vs `"🎉"` in original — **ABWEICHUNG**. |
| `exit_code_to_emoji` | `__main__.py:106-109` | `constants.py:39-42` | EQUIVALENT | mutmut-win wraps in a `defaultdict` with fallback to suspicious emoji. |
| `EXIT_CODE_TIMEOUT` | N/A | `constants.py:45` | NEW | New constant `36`. |
| `EXIT_CODE_SKIPPED` | N/A | `constants.py:46` | NEW | New constant `34`. |
| `EXIT_CODE_TYPE_CHECK` | N/A | `constants.py:47` | NEW | New constant `37`. |

### Findings for constants

| # | Severity | Finding |
|---|---|---|
| F07 | **HIGH** | `status_by_exit_code` missing Unix signal exit codes (`-24`, `24`, `152`, `-11`, `-9`). On Linux/macOS (WSL), pytest processes killed by SIGXCPU (exit 152) or SIGSEGV (exit -11/-9) will be classified as `"suspicious"` instead of `"timeout"` or `"segfault"`. This affects cross-platform behavior. |
| F08 | **MEDIUM** | `emoji_by_status["killed"]` is empty string `""` instead of `"🎉"`. The killed emoji will not display in TUI and CLI output. |

### 8.2 exceptions.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `MutmutProgrammaticFailException` | `__main__.py:176` | `exceptions.py:47` | EQUIVALENT — base class changed to `MutmutWinError` instead of `Exception`. |
| `CollectTestsFailedException` | `__main__.py:180` | REMOVED | Not present in mutmut-win. |
| `BadTestExecutionCommandsException` | `__main__.py:183-186` | `exceptions.py:51-62` | IDENTISCH logic. |
| `InvalidGeneratedSyntaxException` | `__main__.py:189-193` | `exceptions.py:65-78` | EQUIVALENT — parameter type `Path | str` widened to `object`. |

### Findings for exceptions

| # | Severity | Finding |
|---|---|---|
| F09 | **LOW** | `CollectTestsFailedException` removed. The incremental stats path that uses it is not yet implemented in mutmut-win. |

### 8.3 config.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `guess_paths_to_mutate()` | `__main__.py:112-127` | `config.py:25-61` | EQUIVALENT — Same heuristic. Uses `Path.cwd().name` and `Path(...).is_dir()` instead of `os.getcwd()` and `isdir()`. Error message references `pyproject.toml` instead of `setup.cfg`. |
| `Config` dataclass | `__main__.py:835-850` | `config.py:77-161` | EQUIVALENT — Replaced with Pydantic `MutmutConfig` model. Same fields. Adds `max_children` field (was separate), `timeout_multiplier` (hardcoded in original). |
| `Config.should_ignore_for_mutation()` | `__main__.py:852-857` | `config.py:163-177` | IDENTISCH logic. |
| `config_reader()` | `__main__.py:860-892` | `config.py:207-241` (`_load_setup_cfg`) | EQUIVALENT — Reads `setup.cfg` with ConfigParser. Same logic. |
| `load_config()` | `__main__.py:899-917` | `config.py:244-296` | EQUIVALENT — Reads pyproject.toml first, falls back to setup.cfg. Uses `tomllib` (stdlib) instead of conditional `toml`/`tomllib` import. Adds `_apply_default_also_copy()` step. |
| `ensure_config_loaded()` | `__main__.py:895-897` | REMOVED | No global config; config loaded per-call. |

### Findings for config

| # | Severity | Finding |
|---|---|---|
| F10 | **LOW** | `timeout_multiplier` new field (default 10.0). Original hardcodes `15` and `30` as multipliers in `timeout_checker` and `_run`. mutmut-win makes this configurable. |
| F11 | INFO | Pydantic validation provides stricter type checking vs original plain dataclass. |

### 8.4 models.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `SourceFileMutationData.__init__()` | `__main__.py:350-357` | `models.py:96-102` | EQUIVALENT — Pydantic model. Same fields. `key_by_pid`/`start_time_by_pid` removed (process management moved to orchestrator). |
| `SourceFileMutationData.load()` | `__main__.py:359-369` | `models.py:108-125` | EQUIVALENT — Same JSON loading. mutmut-win adds defensive type checks (`isinstance`). |
| `SourceFileMutationData.save()` | `__main__.py:386-393` | `models.py:127-140` | IDENTISCH logic — same JSON structure. |
| `SourceFileMutationData.register_pid()` | `__main__.py:371-374` | REMOVED | PID tracking moved to executor/orchestrator. |
| `SourceFileMutationData.register_result()` | `__main__.py:376-384` | REMOVED | Result registration handled by orchestrator. |
| `SourceFileMutationData.stop_children()` | `__main__.py:385` | REMOVED | Child process management handled by executor. |
| `FileMutationResult` | `__main__.py:209-213` | REMOVED | Replaced by return tuples in `create_mutants_for_file`. |
| `MutantGenerationStats` | `__main__.py:215-218` | REMOVED | Mutant generation stats handled inline in orchestrator. |
| `Stat` dataclass | `__main__.py:701-712` | REMOVED | Replaced by `MutationRunResult` and `CicdStats` in stats.py. |
| `MutationTask` | N/A | `models.py:17-40` | NEW — Task model for worker processes. |
| `TaskStarted/TaskCompleted/TaskTimedOut` | N/A | `models.py:43-78` | NEW — Event models for process communication. |
| `MutationResult` | N/A | `models.py:83-90` | NEW — Result model for DB persistence. |
| `MutationRunResult` | N/A | `models.py:143-170` | NEW — Summary model (replaces `Stat`). |

### Findings for models

| # | Severity | Finding |
|---|---|---|
| F12 | INFO | `register_pid`/`register_result`/`stop_children` removed from `SourceFileMutationData` — appropriate since fork-based PID management is replaced by spawn-based executor. |

### 8.5 _state.py

Covered in section 2. All original global variables are present except `config` and `_covered_lines`.

### 8.6 __main__.py (record_trampoline_hit)

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `record_trampoline_hit()` | `__main__.py:129-142` | `__main__.py:31-62` | EQUIVALENT | Same stack-walking logic. mutmut-win loads config lazily via `_get_max_stack_depth()` instead of accessing `mutmut.config.max_stack_depth` global. Checks for `pytest` and `unittest` (drops `hammett`). |

### Findings

| # | Severity | Finding |
|---|---|---|
| F13 | **LOW** | `record_trampoline_hit` no longer checks for `'hammett'` in frame filenames. HammettRunner is completely removed from mutmut-win (see F16). |

### 8.7 file_setup.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `walk_all_files()` | `__main__.py:145-152` | `file_setup.py:40-53` | EQUIVALENT — Takes `config` parameter instead of using global. Same logic. |
| `walk_source_files()` | `__main__.py:155-158` | `file_setup.py:56-67` | EQUIVALENT — Same. |
| `copy_src_dir()` | `__main__.py:196-208` | `file_setup.py:74-95` | IDENTISCH logic. |
| `copy_also_copy_files()` | `__main__.py:265-274` | `file_setup.py:98-114` | IDENTISCH logic. |
| `setup_source_paths()` | `__main__.py:249-260` | `file_setup.py:121-137` | EQUIVALENT — Uses `Path()` instead of `Path('.')`. Same bug fix for the while-loop index. |
| `strip_prefix()` | `__main__.py:468-472` | `file_setup.py:144-156` | ABWEICHUNG — Original has `strict=False` parameter that asserts on mismatch. mutmut-win removes the `strict` parameter entirely. |
| `get_mutant_name()` | `__main__.py:337-343` | `file_setup.py:159-188` | EQUIVALENT — mutmut-win adds `.replace("/", ".")` for cross-platform path handling. |
| `write_all_mutants_to_file()` | `__main__.py:345-349` | `file_setup.py:195-217` | EQUIVALENT — Takes `covered_lines` as parameter instead of reading global `mutmut._covered_lines`. |
| `create_mutants_for_file()` | `__main__.py:276-333` | `file_setup.py:220-296` | EQUIVALENT — Returns `(mutant_names, warnings)` tuple instead of `FileMutationResult` dataclass. Same mtime comparison logic, same syntax validation. |
| `create_mutants()` | `__main__.py:220-230` | REMOVED | Replaced by `MutationOrchestrator._generate_mutants()` with `multiprocessing.Pool.imap_unordered`. |
| `create_file_mutants()` | `__main__.py:232-243` | REMOVED | Logic inlined into `_create_mutants_worker()` in orchestrator. |
| `store_lines_covered_by_tests()` | `__main__.py:262-264` | REMOVED | Handled in orchestrator `_generate_mutants`. |

### Findings for file_setup

| # | Severity | Finding |
|---|---|---|
| F14 | LOW | `strip_prefix` removed `strict` parameter. In the original, `strict` was only ever called with default `False`, so this is safe. |
| F15 | INFO | `get_mutant_name` adds `.replace("/", ".")` for cross-platform path normalization. Good Windows fix. |

### 8.8 runner.py (PytestRunner)

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `TestRunner` (ABC) | `__main__.py:500-513` | REMOVED | Abstract base class removed; only `PytestRunner` kept. |
| `HammettRunner` | `__main__.py:618-642` | REMOVED | Hammett support dropped entirely. |
| `PytestRunner.__init__()` | `__main__.py:549-554` | `runner.py:37-38` | EQUIVALENT — Takes `config` parameter instead of reading global. |
| `PytestRunner.execute_pytest()` (in-process) | `__main__.py:557-567` | REMOVED | **CRITICAL**: Original runs pytest **in-process** via `pytest.main()`. mutmut-win runs pytest in **subprocess** via `subprocess.run()`. |
| `PytestRunner.run_stats()` | `__main__.py:569-583` | `runner.py:93-147` | ABWEICHUNG | Original uses in-process pytest with StatsCollector plugin. mutmut-win also uses in-process pytest for stats (imports `pytest` and calls `pytest.main()`). Logic is equivalent but structured differently. **Tests_dir is appended differently**: original appends to `_pytest_add_cli_args_test_selection`, mutmut-win appends `config.tests_dir` directly to the pytest args. |
| `PytestRunner.run_tests()` | `__main__.py:585-591` | `runner.py:149-168` | ABWEICHUNG | **CRITICAL**: Original calls `pytest.main()` in-process. mutmut-win delegates to `run_clean_test()` which runs pytest as subprocess. For the main mutation testing run, workers in `process/worker.py` run pytest as subprocess. The `run_tests()` method on PytestRunner is only used for coverage gathering compatibility. |
| `PytestRunner.run_forced_fail()` | `__main__.py:593-596` | `runner.py:170-198` | ABWEICHUNG | Original runs pytest in-process. mutmut-win runs as subprocess with `MUTANT_UNDER_TEST=fail` in env. |
| `PytestRunner.list_all_tests()` | `__main__.py:598-617` | REMOVED from PytestRunner | Replaced by `collect_tests()` which uses subprocess + `--collect-only`. |
| `StatsCollector` (inner class) | `__main__.py:570-579` | `runner.py:109-131` | EQUIVALENT — Same pytest hooks. mutmut-win drops `pytest_runtest_logstart` hook. |
| `ListAllTestsResult` | `__main__.py:527-541` | `stats.py:188-238` | EQUIVALENT — Same API. mutmut-win takes `stats: MutmutStats` parameter instead of reading global. |

### Findings for runner

| # | Severity | Finding |
|---|---|---|
| F16 | INFO | `HammettRunner` removed entirely. No Hammett support in mutmut-win. |
| F17 | **HIGH** | `PytestRunner` fundamentally changed from in-process pytest execution to subprocess-based execution. This is the core Windows adaptation: `os.fork()` is unavailable on Windows, so mutation testing uses `multiprocessing.Process(spawn)` + subprocess pytest. This changes timing behavior and isolation characteristics. |
| F18 | **MEDIUM** | `run_stats()` still runs pytest in-process (correctly — needed for the StatsCollector plugin hooks). But `run_tests()` now just delegates to `run_clean_test()` (subprocess). For actual mutation test execution, the `process/worker.py` handles individual mutants via subprocess. |
| F19 | LOW | `pytest_runtest_logstart` hook removed from StatsCollector. This hook was only initializing `duration_by_test[nodeid] = 0` — benign since `pytest_runtest_makereport` uses `+=` which handles missing keys via `.get()`. |

### 8.9 stats.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `run_stats_collection()` | `__main__.py:926-955` | `stats.py:148-177` (`_run_stats_collection`) | EQUIVALENT — Calls `runner.run_stats()`, reads from `_state`, saves. Less error handling (no `CatchOutput`, no `exit(1)`). |
| `collect_or_load_stats()` | `__main__.py:958-979` | `stats.py:118-145` | ABWEICHUNG | Original has incremental stats update (listing all tests, finding new tests, re-running stats for new tests). mutmut-win just loads or collects — **no incremental stats support yet**. |
| `load_stats()` | `__main__.py:982-993` | `stats.py:63-93` | EQUIVALENT — Returns `MutmutStats` dataclass instead of populating globals. Same JSON format. |
| `save_stats()` | `__main__.py:996-1002` | `stats.py:96-115` | EQUIVALENT — Takes `stats` parameter instead of reading globals. Sorts set values for deterministic output. |
| `save_cicd_stats()` | `__main__.py:1004-1015` | `stats.py:289-316` | EQUIVALENT — Takes list of `(name, status)` pairs instead of `source_file_mutation_data_by_path`. Adds `caught_by_type_check` and `score` fields. |
| `collect_stat()` | `__main__.py:715-726` | REMOVED | Replaced by `compute_cicd_stats()`. |
| `calculate_summary_stats()` | `__main__.py:729-742` | REMOVED | Replaced by `MutationRunResult`. |
| `print_stats()` | `__main__.py:745-748` | REMOVED from stats | Replaced by `_print_live_progress` in orchestrator. |
| `CicdStats` | N/A | `stats.py:242-286` | NEW — Replaces `Stat` dataclass for CI/CD export. |

### Findings for stats

| # | Severity | Finding |
|---|---|---|
| F20 | **MEDIUM** | Incremental stats update not implemented. When tests are added/removed, a full stats re-collection is needed instead of the original's targeted re-run for new tests only. |
| F21 | INFO | `save_cicd_stats` output JSON now includes `caught_by_type_check` and `score` fields not present in original. This is an enhancement. |

### 8.10 test_mapping.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `mangled_name_from_mutant_name()` | `__main__.py:645-647` | `test_mapping.py:19-31` | IDENTISCH |
| `orig_function_and_class_names_from_key()` | `__main__.py:650-660` | `test_mapping.py:34-65` | IDENTISCH logic |
| `is_mutated_method_name()` | `__main__.py:460-461` | `test_mapping.py:68-82` | IDENTISCH |
| `tests_for_mutant_names()` | `__main__.py:1308-1317` | `test_mapping.py:85-121` | EQUIVALENT — Takes `tests_by_mangled_function_name` as parameter instead of reading global. Same fnmatch logic. |

### Findings for test_mapping

No findings. All functions are logically identical.

### 8.11 type_checker_filter.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `MutatedMethodLocation` | `__main__.py:425-429` | `type_checker_filter.py:46-57` | IDENTISCH |
| `FailedTypeCheckMutant` | `__main__.py:432-436` | `type_checker_filter.py:60-73` | IDENTISCH |
| `MutatedMethodsCollector` | `__main__.py:439-456` | `type_checker_filter.py:76-115` | IDENTISCH logic |
| `group_by_path()` | `__main__.py:420-424` | `type_checker_filter.py:118-134` | IDENTISCH |
| `is_mutated_method_name()` | `__main__.py:460-461` | `type_checker_filter.py:30-43` | IDENTISCH (duplicated from test_mapping.py) |
| `filter_mutants_with_type_checker()` | `__main__.py:395-419` | `orchestrator.py:_filter_with_type_checker` | EQUIVALENT — Same CST-based logic: change cwd to mutants, run type checker, parse errors, map to mutant methods. mutmut-win handles `mutant is None` gracefully (continue) instead of raising Exception. |

### Findings for type_checker_filter

| # | Severity | Finding |
|---|---|---|
| F22 | **LOW** | `is_mutated_method_name` duplicated in both `test_mapping.py` and `type_checker_filter.py`. Should be deduplicated. |
| F23 | **LOW** | When type checker error cannot be mapped to a mutant method, original raises Exception; mutmut-win silently continues. This means some type-checker errors could be missed if they occur outside mutated methods. However, the original's behavior was arguably a bug (crashing on errors in non-mutated code). |

### 8.12 mutant_diff.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `find_mutant()` | `__main__.py:1357-1366` | `mutant_diff.py:30-50` | EQUIVALENT — Takes `config` parameter. |
| `read_mutants_module()` | `__main__.py:1330-1332` | `mutant_diff.py:53-62` | EQUIVALENT — Adds explicit `encoding="utf-8"`. |
| `read_orig_module()` | `__main__.py:1335-1337` | `mutant_diff.py:65-73` | EQUIVALENT — Adds explicit `encoding="utf-8"`. |
| `find_top_level_function_or_method()` | `__main__.py:1340-1350` | `mutant_diff.py:76-97` | EQUIVALENT — Adds skip for `SimpleStatementLine`. |
| `read_original_function()` | `__main__.py:1353-1358` | `mutant_diff.py:100-122` | IDENTISCH logic |
| `read_mutant_function()` | `__main__.py:1361-1367` | `mutant_diff.py:125-148` | IDENTISCH logic |
| `get_diff_for_mutant()` | `__main__.py:1370-1389` | `mutant_diff.py:151-181` | ABWEICHUNG — Original takes `source` and `path` optional parameters. mutmut-win takes only `config`. No `source` parameter means cannot generate diff from in-memory source. Original prints status header; mutmut-win does not. |
| `apply_mutant()` | `__main__.py:1405-1418` | `mutant_diff.py:184-218` | EQUIVALENT — Takes `config` parameter. Uses `cast("cst.Module", ...)` for type safety. |

### Findings for mutant_diff

| # | Severity | Finding |
|---|---|---|
| F24 | LOW | `get_diff_for_mutant` lost `source` and `path` optional parameters. The browser's diff loading uses a different `_get_diff_for_mutant` function that does whole-file diff instead of CST-based function diff. |

### 8.13 cli.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `cli()` group | `__main__.py:920-922` | `cli.py:25-27` | IDENTISCH |
| `run` command | `__main__.py:1165-1169` + `_run` | `cli.py:30-51` | ABWEICHUNG — Completely redesigned. Original calls `_run()` directly. mutmut-win creates `MutationOrchestrator` and delegates to `orchestrator.run()`. |
| `results` command | `__main__.py:1320-1328` | `cli.py:54-87` | ABWEICHUNG — Original reads from SourceFileMutationData meta files. mutmut-win reads from SQLite database. Output format differs (summary + surviving mutants vs. per-file listing). |
| `show` command | `__main__.py:1392-1395` | `cli.py:90-105` | EQUIVALENT — Same flow: load config, get diff, print. |
| `apply` command | `__main__.py:1398-1403` | `cli.py:108-123` | EQUIVALENT |
| `browse` command | `__main__.py:1503-1508` | `cli.py:126-133` | EQUIVALENT |
| `tests_for_mutant` command | `__main__.py:1140-1147` | `cli.py:136-156` | EQUIVALENT — Reads from stats cache. |
| `print_time_estimates` command | `__main__.py:1119-1138` | `cli.py:159-203` | EQUIVALENT — Reads from DB + stats cache. |
| `export_cicd_stats` command | `__main__.py:1018-1036` | `cli.py:206-225` | EQUIVALENT — Reads from DB instead of meta files. |

### Findings for cli

| # | Severity | Finding |
|---|---|---|
| F25 | INFO | `results` command now reads from SQLite instead of meta files. Output format changed from per-file to aggregate summary. |

### 8.14 browser.py (ResultBrowser TUI)

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `ResultBrowser` class | `__main__.py:1510-1700` | `browser.py:133-370` | EQUIVALENT | Same Textual App with same bindings (q/r/f/m/a). Differences: |

Detailed differences:
- Missing `t` binding for "View tests for mutant" (original has it, mutmut-win does not)
- `_get_diff_for_mutant` uses whole-file diff instead of CST-based function diff
- Data loading uses `_load_source_file_data()` from meta files OR fallback to SQLite DB
- Columns use `_STATUS_COLUMNS` module constant instead of inline definition
- `compose()`, `on_mount()`, `on_data_table_row_highlighted()` logic is equivalent
- Status description match-case block is identical
- `_run_subprocess_command` uses `python -m mutmut_win` instead of parsing `sys.argv`

### Findings for browser

| # | Severity | Finding |
|---|---|---|
| F26 | **MEDIUM** | Missing `t` binding ("View tests for mutant"). Users cannot view which tests exercise a specific mutant from the TUI. |
| F27 | LOW | `_get_diff_for_mutant` in browser does whole-file diff instead of CST-based per-function diff. This may show much larger diffs than the original. |

### 8.15 orchestrator.py

| Symbol | Original Location | mutmut-win Location | Status |
|---|---|---|---|
| `_run()` | `__main__.py:1172-1305` | `orchestrator.py:MutationOrchestrator.run()` | **MAJOR REDESIGN** |

The original `_run()` function is a ~130-line monolithic pipeline using `os.fork()`:
1. Generate mutants (with multiprocessing.Pool)
2. Type-check filter
3. Collect/load stats
4. Clean test run (in-process)
5. Forced fail test
6. Sort mutants by estimated time
7. Fork child processes for each mutant
8. `os.wait()` to collect results
9. Timeout via SIGXCPU (CPU time limit)

mutmut-win `MutationOrchestrator.run()` replaces this with:
1. Generate mutants (same Pool-based approach via `_create_mutants_worker`)
2. Filter by names (fnmatch)
3. Type-check filter (same CST-based logic)
4. Clean test run (subprocess)
5. Collect/load stats
6. Forced fail test (subprocess)
7. Assign tests to tasks, compute timeouts
8. Sort by estimated time
9. `SpawnPoolExecutor.start(tasks)` + event loop
10. Results persisted to SQLite

Key differences in behavior:
- **No `os.fork()`**: Uses `multiprocessing.Process(spawn)` via `SpawnPoolExecutor`
- **No `resource.setrlimit(RLIMIT_CPU)`**: Uses `WallClockTimeout` thread-based monitor
- **No `gc.freeze()`**: Not needed since spawn creates fresh processes
- **No `set_start_method('fork')`**: Uses `spawn` context explicitly
- **No `START_TIMES_BY_PID_LOCK`**: Lock-free design using queue-based events
- **No `CatchOutput`**: Subprocess-based execution naturally captures output
- **SQLite persistence**: Results saved to `.mutmut-cache/mutmut-cache.db` in addition to meta files
- **Result ordering**: Original uses `os.wait()` (any-child); mutmut-win uses event queue

### Findings for orchestrator

| # | Severity | Finding |
|---|---|---|
| F28 | INFO | Core architectural change from fork-based to spawn-based execution. This is the primary Windows adaptation and the main purpose of the fork. |
| F29 | **MEDIUM** | `timeout_checker` thread in original uses `(estimated_time + 1) * 15` as timeout multiplier. mutmut-win uses `config.timeout_multiplier` (default 10.0) via `_apply_timeouts()`. Different timeout calculation may cause different mutants to time out. |
| F30 | LOW | Original has CPU-time limit (`RLIMIT_CPU`) as a secondary timeout mechanism. mutmut-win only has wall-clock timeout. A mutant that spins on I/O (low CPU, high wall-clock) would be handled differently. |

### 8.16 process/ (executor, worker, timeout)

These are entirely new modules with no direct original counterpart. They replace `os.fork()` + `os.wait()` + `resource.setrlimit()` + `signal.SIGXCPU`.

| Module | Purpose | Status |
|---|---|---|
| `process/executor.py` | `SpawnPoolExecutor` — manages spawned worker processes | NEW |
| `process/worker.py` | `worker_main` — runs pytest subprocess per mutant | NEW |
| `process/timeout.py` | `WallClockTimeout` — background deadline monitor | NEW |

### 8.17 db.py

Entirely new module. Original mutmut uses JSON meta files only. mutmut-win adds SQLite persistence.

| Symbol | Status |
|---|---|
| `DEFAULT_DB_PATH` | NEW — `.mutmut-cache/mutmut-cache.db` |
| `create_db()` | NEW |
| `save_result()` | NEW |
| `load_results()` | NEW |

---

## 9. Removed/Unsupported Symbols

| Symbol | Original Location | Reason |
|---|---|---|
| `HammettRunner` | `__main__.py:618-642` | Hammett testing framework not supported |
| `TestRunner` ABC | `__main__.py:500-513` | Replaced by concrete `PytestRunner` |
| `CollectTestsFailedException` | `__main__.py:180` | Not used (no incremental stats) |
| `CatchOutput` | `__main__.py:783-834` | Not needed (subprocess-based execution) |
| `status_printer()` / `print_status` | `__main__.py:664-682` | Replaced by `_print_live_progress` |
| `spinner` | `__main__.py:662` | Removed (no spinner in subprocess mode) |
| `run_forced_fail_test()` | `__main__.py:750-761` | Inlined in orchestrator |
| `change_cwd()` context manager | `__main__.py:516-521` | Replaced by explicit `os.chdir()` with try/finally |
| `collected_test_names()` | `__main__.py:524-525` | Replaced by `stats.duration_by_test.keys()` |
| `unused()` | `__main__.py:464-465` | Removed |
| `timeout_checker()` | `__main__.py:1152-1163` | Replaced by `WallClockTimeout` class |
| `stop_all_children()` | `__main__.py:1149-1151` | Replaced by `SpawnPoolExecutor.shutdown()` |
| `START_TIMES_BY_PID_LOCK` | `__main__.py:1151` | Not needed (event-based, not lock-based) |
| `estimated_worst_case_time()` | `__main__.py:1107-1109` | Logic inlined in `_apply_timeouts()` |
| `collect_source_file_mutation_data()` | `__main__.py:1038-1070` | Logic inlined in orchestrator |
| `set_start_method('fork')` | `__main__.py:1150` | Replaced by `get_context("spawn")` |
| Signal codes in exit_code map | `__main__.py:86-90` | Unix signals not available on Windows |

---

## 10. Summary Statistics

| Category | Count |
|---|---|
| **IDENTISCH** (logic-identical) | 52 |
| **EQUIVALENT** (cosmetic/style differences, same behavior) | 41 |
| **ABWEICHUNG** (behavioral difference) | 14 |
| **FEHLT** (removed, no equivalent) | 16 |
| **NEU** (new, no original counterpart) | 12 |
| **Total symbols compared** | 135 |

---

## 11. Findings List

| # | Severity | Module | Finding |
|---|---|---|---|
| F01 | LOW | `_state.py` | `duration_by_test` changed from `defaultdict(float)` to `dict`. Safe in practice. |
| F02 | INFO | `__init__.py` | `__version__` hardcoded instead of metadata. |
| F03 | LOW | `trampoline.py` | `mangle_function_name` uses `ValueError` instead of `assert`. |
| F04 | INFO | `trampoline.py` | Import paths correctly changed to `mutmut_win`. |
| F05 | INFO | `code_coverage.py` | Module self-reference correctly updated. |
| F06 | INFO | `mutation.py` | Vestigial no-op line removed. |
| F07 | **HIGH** | `constants.py` | Unix signal exit codes removed (`-24`, `24`, `152`, `-11`, `-9`). SIGXCPU/SIGSEGV exits mapped to `"suspicious"` instead of `"timeout"`/`"segfault"` on Linux/macOS. |
| F08 | **MEDIUM** | `constants.py` | `emoji_by_status["killed"]` is empty string instead of `"🎉"`. |
| F09 | LOW | `exceptions.py` | `CollectTestsFailedException` removed (no incremental stats). |
| F10 | LOW | `config.py` | `timeout_multiplier` is new configurable field. |
| F11 | INFO | `config.py` | Pydantic validation is stricter than original. |
| F12 | INFO | `models.py` | PID-tracking methods removed (appropriate for spawn-based). |
| F13 | LOW | `__main__.py` | `record_trampoline_hit` no longer checks for `'hammett'`. |
| F14 | LOW | `file_setup.py` | `strip_prefix` removed `strict` parameter. |
| F15 | INFO | `file_setup.py` | Cross-platform path normalization added to `get_mutant_name`. |
| F16 | INFO | `runner.py` | `HammettRunner` removed. |
| F17 | **HIGH** | `runner.py` | PytestRunner changed from in-process to subprocess execution. |
| F18 | MEDIUM | `runner.py` | `run_tests()` delegates to subprocess; in-process only for stats. |
| F19 | LOW | `runner.py` | `pytest_runtest_logstart` hook removed from StatsCollector. |
| F20 | **MEDIUM** | `stats.py` | Incremental stats update not implemented. |
| F21 | INFO | `stats.py` | CI/CD stats adds `caught_by_type_check` and `score`. |
| F22 | LOW | `type_checker_filter.py` | `is_mutated_method_name` duplicated across modules. |
| F23 | LOW | `type_checker_filter.py` | Type-checker errors outside mutated methods silently skipped. |
| F24 | LOW | `mutant_diff.py` | `get_diff_for_mutant` lost `source`/`path` parameters. |
| F25 | INFO | `cli.py` | `results` reads from SQLite instead of meta files. |
| F26 | **MEDIUM** | `browser.py` | Missing `t` binding for "View tests for mutant". |
| F27 | LOW | `browser.py` | Diff uses whole-file comparison instead of CST function diff. |
| F28 | INFO | `orchestrator.py` | Fork-to-spawn architectural change (primary purpose of fork). |
| F29 | **MEDIUM** | `orchestrator.py` | Different timeout multiplier (configurable 10x vs. hardcoded 15x). |
| F30 | LOW | `orchestrator.py` | CPU-time limit replaced by wall-clock timeout only. |

---

## 12. Recommendations

### HIGH Priority

1. **F07 — Restore signal exit codes for cross-platform support**: Even though mutmut-win targets Windows, it may run under WSL or on Linux CI. Add the signal-based exit codes back, possibly guarded by `platform.system()`.

2. **F08 — Fix empty killed emoji**: `emoji_by_status["killed"]` should be `"\U0001f389"` (🎉), not `""`.

### MEDIUM Priority

3. **F20 — Implement incremental stats**: When tests are added or removed, the full stats re-collection is expensive. Port the `list_all_tests` → `clear_out_obsolete_test_names` → `run_stats_collection(new_tests)` flow from the original.

4. **F26 — Add `t` binding to TUI**: Port the "View tests for mutant" feature to the ResultBrowser.

5. **F29 — Validate timeout multiplier**: The default timeout multiplier changed from effectively 15x (hardcoded) to 10x (configurable). This may cause more timeouts. Consider raising the default to 15x or documenting the change.

### LOW Priority

6. **F22 — Deduplicate `is_mutated_method_name`**: Extract to a shared utility module.
7. **F27 — Improve browser diff**: Use CST-based per-function diff (from `mutant_diff.py`) instead of whole-file diff.
8. **F23 — Consider warning on unmapped type-checker errors**: Instead of silently skipping, emit a warning when a type error cannot be attributed to a specific mutant method.
