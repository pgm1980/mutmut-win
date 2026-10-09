# mutmut-win

**Windows-native mutation testing for Python.**

mutmut-win runs your test suite against automatically generated code
mutations ("mutants") and tells you which ones survive. A surviving mutant
is a change to your code that no test noticed — a measurable gap in your
test suite that line coverage cannot see.

Based on [mutmut 3.5.0](https://github.com/boxed/mutmut), rebuilt for
Windows: upstream mutmut explicitly blocks Windows
([mutmut#397](https://github.com/boxed/mutmut/issues/397)).

**Requirements:** exactly CPython 3.14.7 on Windows 10/11 or Windows Server
2016+, plus pytest ≥ 8.2 and < 10 in the target project (the worker hands tests
to pytest via the `@argfile` syntax, available since 8.2 — older versions abort
with a clear error before the first mutant). Other Python versions,
implementations, and operating systems (including WSL/Linux and macOS) are
explicitly unsupported. Internal non-Windows code paths do not constitute a
runtime-support commitment.

The workspace must be on a local Windows filesystem that exposes stable file
identity to Python. mutmut-win deliberately fails closed when `st_ino == 0` or
when a reparse/alias boundary cannot be proven to name the same object. Some
exFAT, SMB/network-share, OneDrive Files On-Demand, junction, or other reparse
layouts may therefore be rejected; Windows support does not imply that every
such filesystem topology is supported. Move the checkout to a local
identity-capable volume rather than disabling the safety check.

---

## What it does

- **Mutates your code across three operator profiles** — `basic` is the
  full mutmut 3.5.0 set (arithmetic/comparison/boolean operators, strings,
  numbers, assignments, keywords, lambdas, argument removal, match/case, …);
  the default `advanced` adds mutmut-win's extras (a full 14-sub-mutator
  regex-pattern suite, math method swaps, return-value replacement,
  conditional expressions, statement removal, collection methods, or-defaults)
  plus six Phase-2 operators — ROR full matrix, number-literal CRCR, condition
  negate/force, collection-literal emptying and match-guard.
- **Runs only a test basis it can prove safe.** A stats run records which tests
  execute which function, but the current collector cannot prove that hits
  from every subprocess, thread, or native launcher were observed. Its mapping
  is therefore never allowed to omit or reorder tests. Observed durations may
  schedule independent mutant tasks, while pytest keeps its native order and
  stops at the first failure; a survivor still traverses the full selected
  suite. Full-suite verdicts are reused only when
  the complete source/test/config/dependency context digest is unchanged.
- **Budgets time honestly.** Each task gets a self-calibrating timeout:
  a *measured* per-process startup floor (interpreter + imports +
  collection, derived from your own clean run) plus the scaled runtime of its
  authoritative assignment or, for diagnostic mappings, the complete suite.
  The model is printed at the start of every run.
- **Diagnoses timed-out work.** A psutil-based sampler records CPU, output
  and I/O activity with a platform-aware confidence band. A busy, quiet
  window may suggest a loop but also occurs during finite computation.
  Deadline breaches remain conservative timeouts, with process-tree cleanup
  and persisted diagnostics available through `show`.
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
  staging is fingerprinted by exact source/configuration content — unchanged
  files are not regenerated, and verdicts are reused only when source, the
  full selected test suite, helpers, external configured fixtures, the complete
  staged project, and the readable installed-distribution bytes share the same
  content digest. If that dependency inventory is incomplete, reuse is disabled
  (`--rerun-all` opts out).

## Why mutmut-win over other tools

| | mutmut (upstream) | mutmut-win |
|---|---|---|
| Windows | blocked ([#397](https://github.com/boxed/mutmut/issues/397)) | native (spawn worker pool, job objects, no `fork`) |
| Orphan protection | — | Windows Job Objects: if the parent dies, the kernel reaps every worker and pytest child |
| Timeout model | CPU-time limit (`RLIMIT_CPU`) | measured wall-clock budgets; full-suite fallback is at least 60 seconds |
| Hung mutants | plain timeout | timeout activity monitoring with forensics + confidence |
| Type-checker filter | — | `type_check_command` kills mutants without running tests |
| CI output | text | `--output json` (clean stdout), `--min-score`, CI stats export |
| Config | `[tool.mutmut]` | same section, compatible — migration is trivial |
| Mutation engine | libcst | identical engine, ported from 3.5.0, + advanced & Phase-2 operators |

The mutation engine, configuration format, and workflow stay
mutmut-compatible: if you know mutmut, you know mutmut-win.

## Installation

mutmut-win is distributed via immutable Git release tags — PyPI publishing is
not part of the release sequence (see *Release policy* below). This source tree
defines the package version used by both commands below. Publication state is
external, mutable state: verify that the exact annotated tag and its matching
GitHub release exist before using either command:

```bash
pip install "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v3.0.0"
```

or with [uv](https://docs.astral.sh/uv/):

```bash
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v3.0.0" --dev
```

Do not use the pinned dependency unless that verification succeeds. Published
tags are immutable release provenance and are never moved or deleted.

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
   verifies the mutation machinery (a name-consistency gate plus a
   forced-fail trampoline check), and then executes all mutants in
   parallel.

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
| `mutmut-win results [--all] [--treat-timeout-as-kill]` | Result summary from the cache DB (`--treat-timeout-as-kill` is **deprecated** — explicit timeout scoring policy; removal in a future major) |
| `mutmut-win show <MUTANT>` | Unified diff of one mutant, plus infinite-loop forensics if any |
| `mutmut-win apply <MUTANT>` | Apply a mutant to the source file (backup + atomic write + staleness check) |
| `mutmut-win browse [--show-killed]` | TUI result browser (files → mutants → diff) |
| `mutmut-win tests-for-mutant <MUTANT>` | Diagnostic observed-test hints for a mutant (not an exclusive selection) |
| `mutmut-win time-estimates [MUTANT_NAMES…]` | Estimated runtime per mutant |
| `mutmut-win export-cicd-stats` | Write `mutants/mutmut-cicd-stats.json` for CI gates |

All `browse` TUI actions (`r`/`f`/`m`/`a`/`t`) run their `mutmut-win`
sub-command inside a Windows Job Object with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`: if the TUI dies hard, the kernel
terminates the whole child process tree. When no Job Object can be
established the action is refused outright — there is no uncontained
fallback.

The browser's `m` (retest module) action derives the module boundary from
the loaded metadata mapping, not from the mutant name: for a mutant from
a package `__init__.py` the name is qualified by the *package*
(`__init__` is dropped from mutant names), so a name-derived glob would
retest every submodule of the package — in a one-package `src/` layout
effectively the whole project. `m` therefore retests package-`__init__`
modules via the exact, sorted mutant-name list of that one file (names
outside the current run plan included), and keeps the short `module.*`
glob for ordinary modules. Without a metadata mapping for the selected
mutant (DB-only, unmapped, or stale names) the action is refused with a
warning instead of guessing a scope — and an `__init__` name list that
would exceed the Windows command-line length limit is refused with a
pointer to a manual `mutmut-win run <mutant names>` subset.

`run` persists a new run attempt before staging or generation starts and
finalizes its exact mutant plan only after successful generation. `results`,
`browse`, and `export-cicd-stats` use that current run snapshot as their
authority. Historical rows remain available only as explicitly validated
reuse candidates; they cannot silently fill a failed, interrupted, or partial
current run. CI export therefore refuses an incomplete current snapshot and
removes a stale export rather than presenting it as fresh evidence.

Mutant name matching is the same everywhere: an argument is either an
exact mutant name or a glob pattern (`*`, `?`, `[...]`). Names and globs
are compared case-sensitively, also under Windows — mutant names carry
Python identifiers verbatim, so a differently spelled name is simply not
found. `run` and `time-estimates` accept any number of matches; `show`
and `apply` operate on a single mutant — a pattern matching more than
one fails with the candidate list. `show` diffs are patch-capable for
top-level functions (`a/`–`b/` labels, hunk lines refer to the original
file); for class methods prefer `mutmut-win apply` over `patch`.

Frequently used `run` options (see `mutmut-win run --help` for all):

| Option | Effect |
|---|---|
| `--paths-to-mutate PATH` | Mutate only these paths. **Repeatable** — one path per flag |
| `--profile {basic,advanced,all}` | Operator profile (overrides `[tool.mutmut]`): `advanced` (default) = mutmut base + mutmut-win's extras; `basic` = strict mutmut parity (the 15 base operators); `all` = + aggressive operators |
| `--since-commit REF` | Mutate only files changed since a git ref — a single branch, tag, or commit (e.g. `HEAD~1`); committed **and** uncommitted tracked changes; paths are evaluated relative to the project directory, so monorepo subprojects are supported; untracked files need a full run. The ref is resolved via `git rev-parse --verify --end-of-options <ref>^{commit}` (needs git ≥ 2.36; older git fails closed with exit 2) and only the canonical commit id reaches `git diff`; option-like values, pathspecs, blobs, trees, and range expressions (`A..B`, `A...B`) are rejected with exit 2 |
| `--min-score N` | Full-run CI gate: exit 1 below N percent/incomplete basis; incompatible with name, path, or `--since-commit` subsets and with `--dry-run` (exit 2) |
| `--output json` | Pure JSON result on stdout; prose on stderr |
| `--max-children N` | Worker process count |
| `--force` | Delete `mutants/` and `.mutmut-cache/` first (clean slate); read-only staging leaves are cleared through the identity-checked removal hook, hardlinked/redirected leaves are refused with exit 1 |
| `--rerun-all` | Execute every mutant even when a cached verdict could be reused |
| `--dry-run` | Count mutants without running tests |
| `--no-progress` | Suppress live progress lines (the final summary always prints) |
| `--basis-diagnostics ABSOLUTE_JSON_PATH` | Record execution-basis inputs and changes to a new file outside measured roots; opt-in and published after the run |
| `--debug` | Full tracebacks on errors |

Exit codes of `run`: `0` success, `1` runtime failure, failed
`--min-score` gate or aborted run (worker pool collapsed — the unchecked
remainder is reported and the score gate is skipped), `2` invalid
configuration or option value, `130` interrupted (Ctrl-C — partial results
are persisted, the score gate is skipped). `130` covers every Ctrl-C during
`run`, including phases before the worker pool starts; when no result JSON
exists yet (`--output json`), a JSON error object with `exit_code: 130` is
emitted on stdout instead.

**Degraded mutation surface:** when individual source files cannot be fully
mutated (unparsable syntax, engine-safety skips), the run reports them in
the `degraded_files` list and the JSON result. The run itself ends
diagnostically successfully (exit 0 without `--min-score`), but the
`--min-score` gate and CI/CD export are disabled because the mutation
surface is incomplete: a score over a partially mutated universe cannot
authorize a project-level quality claim. Verdicts of the unaffected files
remain valid and reusable — the degradation is file-scoped, not a
wholesale invalidation. Explicit user exclusions (`do_not_mutate_patterns`,
`do_not_mutate`) are *not* degradations: they are deliberate surface
reductions that never disable the gate.

### Execution-basis diagnostics

Inputs that are transiently locked or unreadable (antivirus scanners, indexers,
fresh publications) are re-read with short bounded delays before any verdict:
hashing retries Windows sharing violations on open, and incomplete basis or
staging snapshots are re-observed a bounded number of times. Inputs that stay
unobservable are reported as "could not be completely observed" (rerun with
`--basis-diagnostics`) — distinct from real drift, which keeps its terminal
"inputs changed" diagnosis.

To investigate a changing execution basis, create an evidence directory outside
your project and Python installation, then use a fresh absolute destination:

```powershell
mutmut-win run --basis-diagnostics C:\evidence\run-01.json
```

The report compares observed inputs at the start and end of a run. It includes
paths, environment variable names and file metadata; file contents and environment
values are represented by private comparison tokens. Recording adds CPU, memory
and elapsed time. The report is written after the run and does not determine
whether its mutation results are valid.

The timeout message shows the minimum and maximum budgets actually assigned to
pending tasks and the formula used. It reports the full-suite fallback whenever
test mapping is not authoritative. This corrects the display; task budgets and
timeout classification retain their existing behavior.

## Configuration

Everything lives in `pyproject.toml` under `[tool.mutmut]` (CLI flags
override per run). Unknown keys produce a warning with a did-you-mean
suggestion. A `setup.cfg` `[mutmut]` section is honored as fallback when
`pyproject.toml` has no `[tool.mutmut]` table; `[tool.mutmut]` itself must
be a table — an array of tables (`[[tool.mutmut]]`) or any other non-table
value is rejected as a configuration error (exit 2) instead of silently
falling back. Both files must be UTF-8:
a `pyproject.toml` or `setup.cfg` that exists but cannot be read (for
example a locked file) or decoded is a configuration error (exit 2),
never silent defaults.

Single-line `setup.cfg` list values are comma-separated. For
`do_not_mutate_patterns`, commas inside valid regex quantifiers
(`{m,n}`, `{m,}`, `{,n}`) are part of the pattern, not separators —
use the multi-line (indented continuation) form for patterns containing
any other commas.

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
max_children = 8                      # workers (default: CPU count; generation
                                       # uses at most 61 workers on Windows)
timeout_multiplier = 30               # scales the measured test time (or, for
                                       # full-suite fallback tasks, the clean-run
                                       # wall time); a budget that is not finite
                                       # or exceeds the ceiling (~23 days) fails
                                       # the run closed before dispatch
clean_run_timeout = 300               # budget (s) for the clean baseline / stats runs
forced_fail_timeout = 120             # budget (s) for the forced-fail verification
generation_timeout = 300              # max seconds without generation progress

# Test selection passthrough (put test paths/node IDs in tests_dir)
pytest_add_cli_args = []                  # validated extra pytest options for every phase
pytest_add_cli_args_test_selection = []   # validated -k/-m-style selection options

# Operator profile (which operators run)
mutation_profile = "advanced"         # advanced (default) = mutmut base + extras;
                                      # basic = strict mutmut parity (15 base ops);
                                      # all = + aggressive operators

# Filters
mutate_only_covered_lines = false     # only mutate lines your tests execute
type_check_command = ["mypy", "--output=json", "src/"] # JSON output is required
                                      # (mypy >= 1.11; pyright: --outputjson).
                                      # Checker-rejected mutants count as caught;
                                      # errors replicated from the original code
                                      # are subtracted, not counted as kills.
                                      # mutmut-win redirects MYPY_CACHE_DIR into
                                      # an ephemeral directory so the checker
                                      # never writes into mutants/; any checker
                                      # that still writes there fails the run
                                      # with a checker-specific diagnosis
                                      # (a --cache-dir argument in the command
                                      # overrides the redirect).

# Advanced
max_stack_depth = -1                  # stats-hit frame walk; -1 = unlimited
                                       # (0-3 rejected: 3 frames are mutmut
                                       # instrumentation; use >= 5)

# Infinite-loop detection (psutil-based; on by default)
infinite_loop_detection = true
infinite_loop_cpu_threshold = 70.0    # mean CPU% over the window
infinite_loop_output_threshold = 1024 # max output growth (bytes) in window
infinite_loop_running_ratio = 0.8     # process-status signal; inactive on Windows
infinite_loop_window_seconds = 10.0   # rolling sample window
```

Notes:

- **Staging mirrors your whole project tree.** `mutants/` is built from
  ALL files under the source roots (`src/`, `source/`, or the project
  root `.`) minus a fixed skip list (`.venv`, `.git`, caches,
  `mutants/` itself, …) — not just `paths_to_mutate` + `also_copy`.
  Tests must be able to import and read everything they normally can.
  Dotenv secrets, run-lock files, environments, build output and known
  internal review/tooling trees are excluded. Other root-level files (for
  example `uv.lock` and scratch files) are copied into `mutants/`, so projects
  with large root-level assets pay that copy on the first run
  (unchanged files are skipped afterwards). Keep secrets and bulk data
  out of the project root or source roots. A project that intentionally tests
  a normally excluded file can name it explicitly in `also_copy`. The
  `src.`/`source.` prefix is
  stripped from mutant names to match the import path — a project whose
  tests import a root *package* literally named `src`/`source`
  (`import src.foo`) is therefore not supported; the layout convention
  wins.
- **`extra_paths` never authorizes live imports.** Use a project-relative path
  or an explicit sibling such as `../benchmarks`; it is copied below
  `mutants/` and only that staged copy enters the test subprocesses'
  `PYTHONPATH`. External absolute paths, Windows root-/drive-relative paths and
  an inherited ambient `PYTHONPATH` are deliberately ignored. An absolute path
  inside the project is accepted and canonicalized to its staged relative
  location, including Windows case and 8.3 aliases.
- **Junction mutation roots are rejected early.** A `paths_to_mutate` entry
  naming a Junction, or a file/directory below one, is rejected before staging
  or generation. Configure the ordinary project-relative source location
  instead. This restriction also applies to absolute aliases before resolution.
- **Links and junctions below `also_copy`/`extra_paths` are skipped.**
  Directory junctions, symlinks and other reparse points *below* a configured
  entry are not walked and not copied into `mutants/` (a `RuntimeWarning`
  names each skipped path); previously mirrored link content is purged on the
  next run. The configured entry itself may be a link (issue #161), and a
  nested configured entry — for example `also_copy = ["tests/linked",
  "tests"]` — owns its subtree: the parent entry neither warns about nor
  removes it. Projects that deliberately keep linked test data should list
  the linked path as its own `also_copy` entry.
- `mutate_only_covered_lines` measures coverage via a subprocess bridge.
  The project's own coverage configuration is honored: `relative_files
  = true` keys are resolved against the staged `mutants/` tree before
  matching, and parallel data files (`parallel = true`, including
  `concurrency = multiprocessing` children) share one external data target.
  When the actual collector uses `multiprocessing`, the run explicitly
  falls back to mutating all configured source lines: a valid parent part
  cannot prove that every child saved its measurements. Missing child parts
  therefore cannot shrink the mutation population. Without that mode,
  parent measurements still select covered lines. Code exercised only in test-spawned subprocesses or
  pytest-xdist workers is invisible to it — such a run fails loudly
  instead of silently filtering every mutant. Follow-up runs restore every target to
  its unmutated bytes before the coverage phase, so coverage always
  measures original line numbers. The trade-off: in this mode no
  trampolined output survives between runs — every file is re-generated
  each run and verdict reuse (fast path) is unavailable for them. Subset
  runs (CLI `--paths-to-mutate`, `do_not_mutate`) likewise restore
  deselected targets to unmutated bytes and drop their generation
  sidecars, so the next full run re-generates them.
- Test observations that cannot prove complete coverage of subprocesses,
  threads, or xdist workers are never allowed to omit or reorder tests. Their
  durations may schedule independent mutant tasks, while pytest keeps the
  project's native order and stops at the first failure. A survivor still runs
  the complete configured suite; timeouts and reusable-verdict fingerprints
  remain bound to that full suite.
- Source, test, configuration, and project-import drift is terminal. If only
  ambient interpreter, environment, or external dependency metadata changes
  during a run, diagnostic results remain visible but their basis and reuse
  authority are revoked atomically; score gates and CI export then fail closed
  until a fresh full run completes.
- Every phase uses one immutable pytest config/root boundary selected from the
  staged `tests_dir` targets. `tests_dir` accepts paths or node IDs only;
  `-c`, root/confcut overrides, `--`, user `@argfiles`, NULs and line breaks are
  rejected. Test targets are placed after an internal end-of-options marker.
  Collected tests and `conftest.py` files must stay inside `mutants/` or an
  external directory explicitly named in `tests_dir` (whose complete bytes are
  included in the run basis). Naming one external test file authorizes only
  that file, not an adjacent or ancestor `conftest.py`; naming an external
  directory authorizes its own `conftest.py` tree but not routing ancestors.
  A staged pytest config cannot silently reach an undeclared external test tree
  through `testpaths`. Pytest versions are constrained to the audited 8.2.x and
  9.x config-discovery and collection semantics.
- A non-empty `type_check_command` still runs and can classify mutants, but
  its generic argv may reach executables, scripts, plugins, response files, or
  configuration outside the project. mutmut-win therefore treats that
  execution basis as conservatively incomplete: stats and verdict reuse are
  disabled, `--min-score` and `export-cicd-stats` fail closed, and JSON plus
  `results`/`browse` report the run as not release-ready. This applies equally
  to commands resolved through `PATH`, `python script.py`, `python -m ...`,
  `uv run ...`, and shell/npm wrappers.
- On Windows the process-status signal does not exist (psutil reports
  almost everything as "running"), so possible-loop diagnostics rest on CPU
  plus progress evidence and are capped at `medium` confidence.
- **Operator profiles** select how aggressively mutmut-win mutates. The
  default `advanced` is mutmut-win's historical extras set, extended since
  v2.17.0 with six high-yield operators (ROR full matrix, number-literal
  CRCR, condition negate/force, collection-literal emptying, match-guard);
  `basic` drops to strict mutmut parity (the 15 base operators only), and
  `all` adds the aggressive operators (rolled out across later releases).
  Each run prints the active profile and its operator count, e.g.
  `profile=advanced — 34 operators active`.

## Result statuses and the score

| Status | Meaning |
|---|---|
| `killed` | A test failed under the mutant — detected ✅ |
| `caught by type check` | The type checker rejected the mutant (no test run needed) |
| `killed_by_infinite_loop` | Historical sampling classification; counted as a timeout and never reused |
| `segfault` | The test process crashed under the mutant — also a detection |
| `survived` | **No test noticed the change — this is your test gap** |
| `timeout` | Budget exceeded; sampling may suggest a loop but cannot prove nontermination |
| `suspicious` | Unexpected pytest exit code, or pytest exited 0 without a verified test-call execution proof (neutralized phase, only skipped tests, or a proof publication failure — never counted as a kill); the diagnostic tail is captured |
| `no tests` | Pytest collected no tests under the mutant (exit 5); retained as diagnostic evidence, never a kill or reusable verdict |
| `skipped` | Excluded from this run |

```text
        killed + type-check-caught + segfault
score = ------------------------------------------------- × 100
        total − skipped − no tests − unchecked
```

The same formula backs `run --min-score`, `results`, and
`export-cicd-stats`. Informational queries (`results`,
`time-estimates`) exit 0 on an empty database; the CI export
(`export-cicd-stats`) exits 1 — an empty result set in a gate context
means the pipeline ran nothing.

The denominator excludes `skipped`, historical or future-authoritative
`no tests`, and unchecked mutants. The current non-authoritative mapper never
creates new `no tests` verdicts: an unobserved mutant runs the full suite.
Always read the bucket counts next to the percentage.

A worker can still report `no tests` when a collection hook removes the test
population under a mutant. The historical percentage above remains readable,
but any unresolved `no tests` makes the run diagnostic only: JSON reports
`execution_basis_complete: false`, current and historical verdict reuse is
revoked, every `--min-score` threshold fails, and CI/CD export is refused.
Without a threshold, the CLI explicitly reports incomplete test evidence.
Resolve the collection gap and rerun before using the results as CI evidence.

The deprecated `run --treat-timeout-as-kill` flag (see `results`) only
changes what the `--min-score` gate judges: the JSON `score` field and the
text summary always report the raw score, and the effective
timeouts-counted-as-kills value is printed as one dedicated stderr line
next to it.

**Mutation-surface limits:** the trampoline mechanism rewrites top-level
functions and top-level-class methods. The two kinds of nesting differ:

- **Module-level statements** (assignments, imports, conditional blocks,
  class definitions executed at import time) are not mutated and have no
  mutants: the trampoline rewrites function *bodies*, and module-level
  code runs exactly once at import — there is no function boundary to
  wrap. A module whose behavior is defined primarily by module-level
  constants or side effects will show fewer mutants than its line count
  suggests (M-141).
- A **function nested inside a function** (a closure) gets no trampoline
  of its own, but its body *is* mutated — folded into the enclosing
  top-level function's mutant set, so closure logic is covered.
- A **method of a class nested inside another class** is genuinely not
  mutated and contributes no mutants rather than appearing as `survived`.
- **Decorated functions and classes** are excluded wholesale, together with
  everything they contain (a method decorated solely with `@staticmethod` is
  the documented exception). For classes this is a conservative contract,
  not a current technical necessity: since M-039 the trampoline bindings
  are placed *inside* the class body (pre-bound during class creation), so
  the historical half-built-trampoline argument no longer applies to the
  generated code itself. The exclusion stays because a class decorator can
  still observe and mutate member behavior before, during, and after class
  creation in ways the trampoline dispatch cannot fully isolate; lifting
  the lock requires an explicit behavioral decision (per decision
  zurückgestellt).

Repeated same-named top-level functions or class methods remain distinct.
The first occurrence keeps its historical mutant name; occurrence 2 and later
use a reversible `ǁ<ordinal>` suffix before `__mutmut_…` (for example
`pkg.x_fǁ2__mutmut_1`). This is intentionally identity-affecting: cached
verdicts from the former colliding representation are not reused.

Function or class identifiers that are not NFKC-normal are always hex-encoded
into an ASCII `xq_…` (top-level) or `xqǁ<class>ǁ<function>…` (method) mutant
name — context-independently, even without a second definition. CPython's
tokenizer binds the NFKC form of every identifier, so `K` and fullwidth `Ｋ`
(U+FF2B) are the same compiled name; the legacy private names would collapse
and one definition would silently overwrite the other's trampoline bindings.
This is identity-affecting as well: cached verdicts of such functions from
earlier runs are explicitly orphaned and are never silently remapped onto the
new IDs.

## Typical workflows

**Local, incremental** — check what you just changed:

```bash
mutmut-win run --since-commit HEAD~1
mutmut-win results
```

`--since-commit` takes a **single** commit reference (branch, tag, or
commit). Range expressions are rejected with exit 2 — they were never
documented and let git reinterpret the value (option injection, pathspec,
tree-vs-worktree diffs). For the former range-style "everything since the
branches diverged" diff, compute the merge base yourself and pass the
resulting commit:

```bash
mutmut-win run --since-commit "$(git merge-base origin/main HEAD)"
```

**Targeted** — one module, fresh staging:

```bash
mutmut-win run --force --paths-to-mutate src/pkg/parser.py
```

**CI gate** — complete configured mutant universe, machine-readable, fail under threshold:

```bash
mutmut-win run --min-score 80 --output json --no-progress
```

Incremental `--since-commit`, targeted `--paths-to-mutate`, and named-mutant
runs are diagnostic subsets. They cannot be combined with `--min-score` or
presented as a project-wide score gate.

**Triage survivors** — inspect, write the missing test, re-run one mutant:

```bash
mutmut-win browse
mutmut-win show src.pkg.parser.x_parse__mutmut_4
mutmut-win run src.pkg.parser.x_parse__mutmut_4
```

## How it works

1. **Attempt & generate**: a durable run attempt is created before staging.
   libcst then parses each source file and emits all mutants of a function
   next to the original, behind a trampoline dispatcher, into a `mutants/`
   staging copy. Generation runs behind a dedicated supervisor with a hard
   no-progress timeout and process-tree cleanup. Unchanged files are reused
   only when exact source and mutation-universe content digests match; output,
   metadata, and the generation fingerprint are published transactionally.
2. **Validate**: the unmutated suite must pass inside `mutants/`; a
   name-consistency gate then proves that the runtime function names
   recorded by the stats run can address the generated mutants — a
   mutated tree imported under a root that mutant names do not strip (for
   example an `extra_paths` entry, or tests importing a literal `src`
   package) would otherwise silently run originals and report everything
   as `survived`, so the run fails closed before dispatch. Finally, a
   forced-fail check proves the trampoline wrapper is installed and reads
   `MUTANT_UNDER_TEST` — the failure must come from the trampoline's own
   exception, a hung or unrelated failure fails the gate. The global
   `fail` sentinel does not switch a concrete mutant; name dispatch is
   what the consistency gate proves.
3. **Map & budget**: a stats run records per-test durations and a diagnostic
   test↔function mapping. The current collector cannot prove completeness
   across subprocesses, threads and native launchers, so on-disk mappings are
   always loaded as non-authoritative: observed durations may order independent
   mutant tasks, but pytest's native item order is unchanged, every survivor
   receives the full selected suite, and no cached flag can create selective or
   `no tests` verdicts. Such tasks use the full-suite fallback budget
   `max(60 seconds, clean-run wall time × timeout_multiplier)`. Authoritative
   mappings use the measured startup floor plus scaled test time, with a
   minimum budget of five seconds. Result reuse separately binds the selected
   tests and execution basis.
4. **Plan & execute**: the exact generated universe is committed as the
   current run plan before dispatch. Spawn-based workers activate one mutant
   at a time via `MUTANT_UNDER_TEST` and run its tests. Subprocess output is
   drained continuously into a bounded in-memory tail, so a noisy or escaped
   child cannot grow a log file without limit or block a full pipe. Windows Job
   Objects provide mandatory kernel containment: ordinary subprocesses are born
   atomically inside the Job, while pool-worker interpreters are born there
   suspended, receive their bootstrap data through pre-populated seekable
   storage, and resume only after containment succeeds. Cleanup paths use tree
   termination and bounded joins.
   Results are accepted only for planned names and persisted atomically into
   the current SQLite snapshot.

Normal mutation runs never modify original sources; execution happens in the
`mutants/` staging directory. The explicit `apply` command is the exception: it
uses an audited compare-and-swap protocol — the selected source file is
displaced to a recovery sibling, the replacement is written to a private
temporary sibling and validated (identity, bytes, parent), then promoted onto
the target name. This two-rename sequence is *not* a single atomic visibility
switch: a concurrent reader between the two renames observes a briefly absent
original path. The displaced original is preserved under a deterministic
recovery name (or the known backup path) and its location is reported on any
failure. Add `mutants/`, `.mutmut-cache/` and `.mutmut-win-*.run.lock*` to
`.gitignore`.

**`.gitignore` limits of staging:** staging walks, staging copies, and the
combined ambient fingerprint of the run basis respect hierarchical
project-local `.gitignore` files, so correctly ignored build trees are neither
staged nor change the ambient basis. Pattern case follows the repository's
effective `core.ignorecase` (ASCII-only folding, exactly like Git's wildmatch;
read once per run — outside a Git worktree matching stays case-sensitive).
Explicitly configured entries are the
deliberate exception — `paths_to_mutate`, `also_copy`, and `extra_paths`
entries are force-included with git `add -f` semantics (an ignore file
*inside* such an entry still governs its contents). A git-ignored
`paths_to_mutate` root is therefore fully staged, non-`.py` resources
included, exactly matching the mutation surface; its bytes are also bound
into the run-basis evidence. Dotenv files stay out of staging even when
ignored, but their bytes keep binding the basis.

Basis hashing separates that staging selection from the terminal *core*
digest. The core binds the bytes of every effective project import root — the
project root or its package source, reached through `sys.path` or an editable
install — deliberately **without** gitignore pruning (decided M-061/B: import
roots that remain importable by the executed tests stay bound; only `src` and
`source` roots are removed from the child's `sys.path`, so a flat-layout
project root or an editable install stays importable in place). A git-ignored
build tree inside such a flat-layout or editable import root therefore still
hashes into the core digest: changing it counts as project (core) drift and
invalidates verdict reuse instead of being silently ignored, while pure
ambient churn never changes the core digest. Runtime environment trees are
never pruned in either digest: a project-internal `.venv`, `venv`, `.tox`,
`.nox`, or any active interpreter prefix strictly inside the project executes
in place and is fully bound, including unclaimed modules and `.pth` files.
The boundary is permitted only in the opposite direction: `src`/`source`
package roots — which the child no longer imports because the runner removes
them from its `sys.path` and executes the staged copy instead — keep gitignore
pruning in the ambient fingerprint, so an ignored artifact inside such an
isolated source tree changes neither the ambient digest nor verdict reuse.
That pruning is a stability property of the ambient digest, not a completeness
proof: bytes that stay importable in the child are covered by the core digest
alone, and only the core digest decides whether drift is terminal project
drift.

## Development

```bash
git clone https://github.com/pgm1980/mutmut-win.git
cd mutmut-win
uv lock --check
uv sync --locked --only-group build --no-install-project
uv sync --locked --extra dev --group build --group security --no-build-isolation

uv run --no-sync pytest -p no:cacheprovider      # full suite, no checkout cache
uv run --no-sync ruff check --no-cache .         # lint
uv run --no-sync ruff format --no-cache .        # format
uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/  # type check
uv run --no-sync lint-imports --no-cache  # layer contracts, no checkout-local cache

uv sync --locked --only-group security --no-install-project
uv run --no-sync python -I scripts/semgrep_release_gate.py  # pinned, fail-closed security gate
```

mutmut-win runs its own mutation testing on itself (dogfooding) as part
of its release gates.

### Temporary directories

A run creates one parent-managed runtime root (`mutmut-win-run-*`) in the
system temp; every worker's per-task runtime directory (pytest cache,
hypothesis storage, phase-guard markers) lives under it, and a normal
shutdown removes the whole tree after the worker-pool Job close — this
also covers workers that had to be hard-killed at the shutdown deadline
(M-146). Two documented exceptions can leave exactly one such root
behind: a hard abort of the *parent* process itself, and a failed pool
Job close (kept for forensics). Orphaned `mutmut-win-run-*` directories
are safe to delete while no mutmut-win run is active.

### Release policy

Releases are demand-driven — there is no calendar cadence. A release
happens only on an explicit maintainer "Release" decision after all
gates pass (tests and coverage, lint, format, types, lock and dependency
audit, the tracked fail-closed Semgrep wrapper, import-linter, reproducible
Wheel/sdist builds plus installed-artifact smoke tests, and a dogfooding
pilot). The fixed sequence is: explicit version decision and version bump
(`pyproject.toml` + `uv.lock`) on the release branch → final gates → merge to
`main` → repeat the final gates on the integrated commit → build and verify the
reproducible release artifacts → annotated tag `vX.Y.Z` → GitHub release with
notes. Final and integrated gates use a fresh absolute
`UV_PROJECT_ENVIRONMENT` and `HYPOTHESIS_STORAGE_DIRECTORY`, both outside the
checkout, plus the cacheless command forms above, so generated tool state cannot
conceal or perturb release inputs. PyPI
publishing is not part of that sequence. Breaking changes wait for a major version; deprecations warn
for at least one minor release first (current example:
`--treat-timeout-as-kill`).
<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

## Mutation operator boundaries

Python 3.14 template strings (`t"..."`) are parsed and preserved, but currently
have no dedicated literal-text or whole-template return-value mutation operator.
A `Template` exposes its static strings and interpolation values, expressions,
conversions and format specifications before rendering; applying the f-string
text operator does not by itself define an adequate template mutation contract.
Supported operators inside interpolation expressions still apply. Functions
with no applicable mutation site produce no mutants, so a successful run does
not establish that every template expression was tested by mutation.

The exact advanced-profile fixture `def value(x): return t"hello {x}!"` produces
zero mutants; replacing only `t` with `f` produces three (two text mutations and
one `return None`). These counts describe this fixture, not arbitrary strings,
expressions or profiles. The generated unmutated template preserves
`strings == ("hello ", "!")`, `values == (7,)` and expression `"x"` for `value(7)`.
The f-string control returns `"hello 7!"`.

## History and project status

mutmut-win started as a Windows port of mutmut 3.5.0's process layer
(v0.x–v1.0), grew 7 additional mutation operators (v1.0), per-task
timeouts, job-object process management and infinite-loop detection
(v2.5–v2.8), went through a full source audit with five hardening
releases covering score integrity, pipeline hygiene and runtime
truthfulness (v2.6–v2.10), and closed the audit's maintenance pool
completely in two demand-driven maintenance releases (v2.11–v2.12).
Two further maintenance releases followed: v2.13.0 added cross-run
result reuse — verdicts of unchanged mutants are reused instead of
re-run — alongside an external-QA hardening pass, and v2.14.0 closed
all 28 findings of a full 360° code analysis (9 bugs, 13 anomalies,
6 optimizations). v2.16.0 then introduced the three-operator-profile
model (`basic`/`advanced`/`all`, advanced as the behaviour-neutral
default), v2.17.0 landed the first six advanced Phase-2 operators
(ROR matrix, number CRCR, condition negate/force, collection-emptying,
match-guard — acceptance harness 152/152, 100 %), and v2.18.0 completed
the regex operator with the full 14-sub-mutator suite (anchors,
quantifiers, shorthands, character classes, groups/look-around — harness
184/188). Regex mutation binds the pattern argument positionally or via
`pattern=`, never mutates `(?#...)` comments, and honours statically
resolvable `re.VERBOSE`/`re.X` flags (including `flags=` keywords) by locking
`#` line comments. The scanner also tracks combined global inline flags and
scoped enable/disable groups such as `(?ix:...)` and `(?-x:...)`, restoring
the enclosing mode at the group boundary. Unknown flag expressions retain
flagless behaviour. v2.19.0 added the aggressive `all`-tier operators (arithmetic
operand deletion, exception swap, general-statement and member-assignment
removal, unary-operator insertion) and the mutmut-3.6.0 surface backports
(pragma `block`/`start`-`end`, regex `do_not_mutate_patterns`, and
`@staticmethod` mutation — harness 204/200, the 4 survivors are documented
regex `fullmatch` equivalents). v2.19.1 is a robustness patch from an external
360° re-test: a corrupt `.mutmut-cache` DB now surfaces a clean message instead
of a raw traceback (recover with `run --force`), and `setup.cfg` now honours the
`mutation_profile` / `do_not_mutate_patterns` keys. v2.20.0 continued that
hardening from the same re-test. Its initial switch from `multiprocessing.Pool`
to `concurrent.futures.ProcessPoolExecutor` fixed bootstrap-worker collapse but
did not bound every generation hang. The active adversarial hardening pass now
runs that per-file executor behind a separate generation supervisor: a hard
no-progress deadline, crash detection, worker/grandchild containment, and
bounded cleanup cover submit, bootstrap, execution, callback, and abort paths.
The same pass adds content-authoritative caches, current-run identity, bounded
subprocess output, conservative mapping fallback, and distinct IDs for repeated
same-named definitions. `do_not_mutate_patterns` also matches the qualified
`Class.method` name, not only the bare method name. v2.21.0 completes this
adversarial hardening pass, including the fail-closed release, dependency,
artifact, and security contracts documented in the repository. The current release
closes the externally reported run-startup blocker (MBR-2026-09-14-01): staging
walks, staging copies and the execution-basis fingerprint now respect
hierarchical `.gitignore` files (git `add -f` semantics for explicitly
configured entries; dotenv carve-out), so a correctly ignored build tree is
no longer enumerated, copied or hashed - a 120k-file Lean `.lake` tree went
from a 15-60 minute silent hang to seconds. The same release makes run
startup observable (phase progress lines, per-phase durations, `--debug`
step traces, and a stall watchdog that dumps the Python stack after 60
seconds without progress), retries `--force` cleanup through transient file
locks, absorbs transient Windows filter-driver interference at three narrow
atomic-publication points, publishes the pytest phase-guard execution proof
once per phase instead of once per test report, and documents
`clean_run_timeout` for large staged suites. The current remediation wave
additionally restores the exclusion guarantees of that surface: qualified
`do_not_mutate_patterns` stay effective even after a nested class was
skipped (the visitor's class stack is now identity-bound). The same wave
grounds the wholesale exclusion of decorated classes in the trampoline
architecture (private method copies live in the class body and stay visible
to class decorators that touch members during class creation; their lookup
names are pre-bound at class-creation time and rebound after the class
statement) instead of the inherited function-decorator rationale, and
computes `block` pragma extents from the token stream so column-0 comments
and multi-line string contents no longer end a block early. The trampoline
codegen itself is hardened next (issue #167): a method called while its own
class is being built — enum member creation invoking `__init__` or
`_generate_next_value_`, a class attribute computed from an own method, a
decorator defined in the class body — used to fail the import with NameError
because the wrapper's module-level lookup names were bound only after the
class statement; the class body now carries creation-time `global` bindings
that bypass the class namespace (no enum member, no NamedTuple field), while
the post-class capture and lookup stay byte-identical. The same codegen pass
fixes the generator verdict: a `yield` inside a lambda body no longer turns
the surrounding function into a generator (the wrapper returned a generator
object instead of the value, and async functions with such lambdas were
wrongly excluded wholesale), while `yield` in a lambda default still counts
because defaults are evaluated in the enclosing scope. The same wave makes
mutant identity NFKC-safe (M-041): every function or class identifier that is
not NFKC-normal now receives a deterministic ASCII `xq_` hex mutant name —
CPython's tokenizer binds NFKC forms, so `K` and fullwidth `Ｋ` used to
collapse onto the same private trampoline bindings and corrupt clean runs —
and cached verdicts of such functions are explicitly invalidated as orphans
rather than silently remapped to the new IDs. Details:
the [release notes](https://github.com/pgm1980/mutmut-win/releases).

**Status:** the codebase version and active installation references agree.
Publication authority is defined only by the canonical neutral contract at the
top of this file. Release readiness follows
only from the evidence regenerated on the final corrected tree; an older
dogfooding score or historical green gate is not sufficient. If GitHub CI
cannot start because of billing, its status is `NOT_EXECUTED`: an evidence gap,
neither PASS nor FAIL. The actually executed v2.21.0 CI was red, not a PASS.

## License

Original mutmut-win contributions are ISC-licensed; portions derived from
mutmut 3.5.0 retain its BSD 3-Clause terms, and the process-containment
backends adapted from CPython retain the Python Software Foundation License
Version 2. See `LICENSE` for the required notices and change summary; package
metadata uses the composite SPDX expression
`ISC AND BSD-3-Clause AND PSF-2.0`.

## Credits

Based on [mutmut](https://github.com/boxed/mutmut) by Anders Hovmöller.
The CST-based mutation engine is ported directly from mutmut 3.5.0.
