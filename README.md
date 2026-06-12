# mutmut-win

**Windows-native mutation testing for Python.**

mutmut-win runs your test suite against automatically generated code
mutations ("mutants") and tells you which ones survive. A surviving mutant
is a change to your code that no test noticed — a measurable gap in your
test suite that line coverage cannot see.

Based on [mutmut 3.5.0](https://github.com/boxed/mutmut), rebuilt for
Windows: upstream mutmut explicitly blocks Windows
([mutmut#397](https://github.com/boxed/mutmut/issues/397)).

**Requirements:** Python ≥ 3.12, Windows 10/11 (primary target; the
POSIX code paths are kept functional for WSL/Linux CI).

---

## What it does

- **Mutates your code with 22 operators** — the full mutmut 3.5.0 set
  (arithmetic/comparison/boolean operators, strings, numbers,
  assignments, keywords, lambdas, argument removal, match/case, …) plus
  7 additional operators (regex patterns, math method swaps, return-value
  replacement, conditional expressions, statement removal, collection
  methods, or-defaults).
- **Runs only the tests that matter per mutant.** A stats run records
  which tests execute which function; each mutant then runs exactly its
  covering tests instead of the whole suite. Mutants no test covers are
  reported as `no tests` without burning any runtime.
- **Budgets time honestly.** Each task gets a self-calibrating timeout:
  a *measured* per-process startup floor (interpreter + imports +
  collection, derived from your own clean run) plus the scaled runtime of
  its assigned tests. The model is printed at the start of every run.
- **Detects infinite loops.** A psutil-based sampling classifier
  separates real non-termination (CPU pegged, no output progress, no I/O
  activity) from genuinely slow tests, with persisted forensics and a
  platform-aware confidence band — instead of lumping everything into
  "timeout".
- **Uses your type checker as a free kill filter.** With
  `type_check_command` configured, mutants that mypy/pyright already
  reject are counted as caught without running a single test.
- **Scores honestly.** Disjoint result buckets (killed, survived,
  timeout, suspicious, skipped, no tests, segfault, type-check-caught),
  a kill-class score formula that is identical across the run gate,
  `results`, and the CI export, and interrupted runs that say so
  (exit 130, no fake score).
- **Fits into CI.** `--min-score` gate, `--output json` with *pure* JSON
  on stdout (prose goes to stderr), `--since-commit` for incremental
  runs, and a machine-readable stats export.
- **Caches aggressively.** Results live in SQLite, per-file mutant
  staging is fingerprinted (source + configuration) — unchanged files
  are not regenerated, and verdicts of unchanged mutants (same source,
  same covering tests) are reused instead of re-run
  (`--rerun-all` opts out).

## Why mutmut-win over other tools

| | mutmut (upstream) | mutmut-win |
|---|---|---|
| Windows | blocked ([#397](https://github.com/boxed/mutmut/issues/397)) | native (spawn worker pool, job objects, no `fork`) |
| Orphan protection | — | Windows Job Objects: if the parent dies, the kernel reaps every worker and pytest child |
| Timeout model | CPU-time limit (`RLIMIT_CPU`) | wall-clock budget = measured startup floor + scaled test time |
| Hung mutants | plain timeout | infinite-loop classifier with forensics + confidence |
| Type-checker filter | — | `type_check_command` kills mutants without running tests |
| CI output | text | `--output json` (clean stdout), `--min-score`, CI stats export |
| Config | `[tool.mutmut]` | same section, compatible — migration is trivial |
| Mutation engine | libcst | identical engine, ported from 3.5.0, +7 operators |

The mutation engine, configuration format, and workflow stay
mutmut-compatible: if you know mutmut, you know mutmut-win.

## Installation

mutmut-win is distributed via the Git repository — PyPI publishing is
not part of the release sequence (see *Release policy* below). Install
a pinned release tag:

```bash
pip install "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.12.0"
```

or with [uv](https://docs.astral.sh/uv/):

```bash
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.12.0" --dev
```

## Quick start

1. Configure the source and test locations in `pyproject.toml`:

   ```toml
   [tool.mutmut]
   paths_to_mutate = ["src/"]
   tests_dir = ["tests/"]
   ```

2. Make sure your suite is green (`pytest`), then run:

   ```bash
   mutmut-win run
   ```

   The run validates the clean suite, collects per-test timing stats,
   verifies the mutation machinery with a forced-fail check, and then
   executes all mutants in parallel.

3. Inspect the outcome:

   ```bash
   mutmut-win results                # summary + surviving mutants
   mutmut-win show <mutant-name>     # per-mutant diff (+ IL forensics)
   mutmut-win browse                 # interactive TUI browser
   ```

## CLI commands

| Command | Purpose |
|---|---|
| `mutmut-win run [OPTIONS] [MUTANT_NAMES…]` | Run mutation testing (optionally filtered to names/globs like `src.mod.x_func*`) |
| `mutmut-win results [--all] [--treat-timeout-as-kill]` | Result summary from the cache DB (`--treat-timeout-as-kill` is **deprecated** — superseded by infinite-loop detection; removal in a future major) |
| `mutmut-win show <MUTANT>` | Unified diff of one mutant, plus infinite-loop forensics if any |
| `mutmut-win apply <MUTANT>` | Apply a mutant to the source file (backup + atomic write + staleness check) |
| `mutmut-win browse [--show-killed]` | TUI result browser (files → mutants → diff) |
| `mutmut-win tests-for-mutant <MUTANT>` | Tests mapped to a mutant |
| `mutmut-win time-estimates [MUTANT_NAMES…]` | Estimated runtime per mutant |
| `mutmut-win export-cicd-stats` | Write `mutants/mutmut-cicd-stats.json` for CI gates |

Mutant name matching is the same everywhere: an argument is either an
exact mutant name or a glob pattern (`*`, `?`, `[...]`). `run` and
`time-estimates` accept any number of matches; `show` and `apply`
operate on a single mutant — a pattern matching more than one fails
with the candidate list. `show` diffs are patch-capable for top-level
functions (`a/`–`b/` labels, hunk lines refer to the original file);
for class methods prefer `mutmut-win apply` over `patch`.

Frequently used `run` options (see `mutmut-win run --help` for all):

| Option | Effect |
|---|---|
| `--paths-to-mutate PATH` | Mutate only these paths. **Repeatable** — one path per flag |
| `--since-commit REF` | Mutate only files changed since a git ref (e.g. `HEAD~1`) |
| `--min-score N` | Exit 1 if the score is below N percent (CI gate) |
| `--output json` | Pure JSON result on stdout; prose on stderr |
| `--max-children N` | Worker process count |
| `--force` | Delete `mutants/` and `.mutmut-cache/` first (clean slate) |
| `--rerun-all` | Execute every mutant even when a cached verdict could be reused |
| `--dry-run` | Count mutants without running tests |
| `--no-progress` | Suppress live progress lines (the final summary always prints) |
| `--debug` | Full tracebacks on errors |

Exit codes of `run`: `0` success, `1` runtime failure or `--min-score`
gate failed, `2` invalid configuration or option value, `130` interrupted
(Ctrl-C — partial results are persisted, the score gate is skipped).

## Configuration

Everything lives in `pyproject.toml` under `[tool.mutmut]` (CLI flags
override per run). Unknown keys produce a warning with a did-you-mean
suggestion.

```toml
[tool.mutmut]
# What to mutate and where the tests are
paths_to_mutate = ["src/"]
tests_dir = ["tests/"]
do_not_mutate = ["**/migrations/*"]   # glob patterns to exclude

# Staging extras
also_copy = ["fixtures/"]             # extra files copied into mutants/
extra_paths = ["benchmarks/"]         # sibling packages: copied + on worker PYTHONPATH

# Execution
max_children = 8                      # workers (default: CPU count)
timeout_multiplier = 30               # scales the measured per-mutant test time
clean_run_timeout = 300               # budget (s) for the clean baseline / stats runs
forced_fail_timeout = 120             # budget (s) for the forced-fail verification

# Test selection passthrough
pytest_add_cli_args = []                  # extra pytest args for every run
pytest_add_cli_args_test_selection = []   # extra args for test-selection runs

# Filters
mutate_only_covered_lines = false     # only mutate lines your tests execute
type_check_command = ["mypy", "src/"] # mutants the checker rejects count as caught

# Advanced
max_stack_depth = -1                  # stats-hit frame walk; -1 = unlimited (0 is rejected)

# Infinite-loop detection (psutil-based; on by default)
infinite_loop_detection = true
infinite_loop_cpu_threshold = 70.0    # mean CPU% over the window
infinite_loop_output_threshold = 1024 # max output growth (bytes) in window
infinite_loop_running_ratio = 0.8     # POSIX-only process-status signal
infinite_loop_window_seconds = 10.0   # rolling sample window
```

Notes:

- `mutate_only_covered_lines` measures coverage via a subprocess bridge.
  Code exercised only in test-spawned subprocesses or pytest-xdist
  workers is invisible to it — such a run fails loudly instead of
  silently filtering every mutant.
- On Windows the process-status signal does not exist (psutil reports
  almost everything as "running"), so infinite-loop verdicts rest on CPU
  plus progress evidence and are capped at `medium` confidence.

## Result statuses and the score

| Status | Meaning |
|---|---|
| `killed` | A test failed under the mutant — detected ✅ |
| `caught by type check` | The type checker rejected the mutant (no test run needed) |
| `killed_by_infinite_loop` | Classifier verdict: the suite never terminates under the mutant |
| `segfault` | The test process crashed under the mutant — also a detection |
| `survived` | **No test noticed the change — this is your test gap** |
| `timeout` | Budget exceeded without an infinite-loop verdict |
| `suspicious` | Unexpected pytest exit code (diagnostic tail is captured) |
| `no tests` | The test mapping covers this mutant with zero tests |
| `skipped` | Excluded from this run |

```text
        killed + type-check-caught + IL-killed + segfault
score = ------------------------------------------------- × 100
        total − skipped − no tests − unchecked
```

The same formula backs `run --min-score`, `results`, and
`export-cicd-stats`. Informational queries (`results`,
`time-estimates`) exit 0 on an empty database; the CI export
(`export-cicd-stats`) exits 1 — an empty result set in a gate context
means the pipeline ran nothing.

## Typical workflows

**Local, incremental** — check what you just changed:

```bash
mutmut-win run --since-commit HEAD~1
mutmut-win results
```

**Targeted** — one module, fresh staging:

```bash
mutmut-win run --force --paths-to-mutate src/pkg/parser.py
```

**CI gate** — machine-readable, fail under threshold:

```bash
mutmut-win run --since-commit origin/main --min-score 80 --output json --no-progress
```

**Triage survivors** — inspect, write the missing test, re-run one mutant:

```bash
mutmut-win browse
mutmut-win show src.pkg.parser.x_parse__mutmut_4
mutmut-win run src.pkg.parser.x_parse__mutmut_4
```

## How it works

1. **Generate**: libcst parses each source file and emits all mutants of
   a function next to the original, behind a trampoline dispatcher, into
   a `mutants/` staging copy. Unchanged files (source + config
   fingerprint) are reused.
2. **Validate**: the unmutated suite must pass inside `mutants/`; a
   forced-fail check proves the trampoline actually switches mutants —
   the failure must come from the trampoline's own exception, a hung or
   unrelated failure fails the gate.
3. **Map & budget**: a stats run records per-test durations and the
   test↔function mapping; every mutant gets its covering tests and a
   wall-clock budget (measured startup floor + scaled test time).
4. **Execute**: a pool of spawn-based workers activates one mutant at a
   time via the `MUTANT_UNDER_TEST` environment variable and runs its
   tests; Windows Job Objects guarantee no process tree ever outlives
   the run. Results stream back over a queue and are persisted to
   SQLite as they arrive.

Your original sources are never modified; everything happens in the
`mutants/` staging directory (add `mutants/` and `.mutmut-cache/` to
`.gitignore`).

## Development

```bash
git clone https://github.com/pgm1980/mutmut-win.git
cd mutmut-win
uv sync --extra dev

uv run pytest              # full suite (unit + integration + architecture)
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy src/           # type check
uv run lint-imports        # layer contracts
```

mutmut-win runs its own mutation testing on itself (dogfooding) as part
of its release gates.

### Release policy

Releases are demand-driven — there is no calendar cadence. A release
happens only on an explicit maintainer "Release" decision after all
gates pass (tests, lint, format, types, semgrep, import-linter,
dogfooding pilot), and follows one fixed sequence: merge to `main` →
version bump (`pyproject.toml` + `uv.lock`) → annotated tag `vX.Y.Z` →
GitHub release with notes. PyPI publishing is not part of that
sequence. Breaking changes wait for a major version; deprecations warn
for at least one minor release first (current example:
`--treat-timeout-as-kill`).

## History and project status

mutmut-win started as a Windows port of mutmut 3.5.0's process layer
(v0.x–v1.0), grew 7 additional mutation operators (v1.0), per-task
timeouts, job-object process management and infinite-loop detection
(v2.5–v2.8), went through a full source audit with five hardening
releases covering score integrity, pipeline hygiene and runtime
truthfulness (v2.6–v2.10), and closed the audit's maintenance pool
completely in two demand-driven maintenance releases (v2.11–v2.12).
Details: the
[release notes](https://github.com/pgm1980/mutmut-win/releases).

**Status:** v2.12.0 is the current release. Active development is in a
documented pause with a clean slate — zero open issues, zero known
backlog entries. The issue tracker stays open; the resumption baseline
(a full self-run over the tool's own codebase) is recorded in the
repository docs.

## License

ISC License (same as mutmut).

## Credits

Based on [mutmut](https://github.com/boxed/mutmut) by Anders Hovmöller.
The CST-based mutation engine is ported directly from mutmut 3.5.0.
