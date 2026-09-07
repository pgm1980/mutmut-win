# mutmut-win

<!-- PUBLICATION_STATE_START -->
<!-- PUBLICATION_STATE: external-live-check-required -->
Publication status for v2.21.1 is external mutable state. These immutable bytes assert neither presence nor absence; verify the exact annotated tag and matching GitHub release before use.
<!-- PUBLICATION_STATE_END -->

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
| Timeout model | CPU-time limit (`RLIMIT_CPU`) | wall-clock budget = measured startup floor + scaled test time |
| Hung mutants | plain timeout | infinite-loop classifier with forensics + confidence |
| Type-checker filter | — | `type_check_command` kills mutants without running tests |
| CI output | text | `--output json` (clean stdout), `--min-score`, CI stats export |
| Config | `[tool.mutmut]` | same section, compatible — migration is trivial |
| Mutation engine | libcst | identical engine, ported from 3.5.0, + advanced & Phase-2 operators |

The mutation engine, configuration format, and workflow stay
mutmut-compatible: if you know mutmut, you know mutmut-win.

## Installation

mutmut-win is distributed via immutable Git release tags — PyPI publishing is
not part of the release sequence (see *Release policy* below). This source tree
defines the package version used by both commands below. Apply the canonical
external-publication verification contract at the top of this document before
using either command:

```bash
pip install "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.21.1"
```

or with [uv](https://docs.astral.sh/uv/):

```bash
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.21.1" --dev
```

Do not use the pinned dependency unless the required external tag/release
verification succeeds. The existing v2.21.0 tag remains immutable release
provenance and is never moved.

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
| `mutmut-win tests-for-mutant <MUTANT>` | Diagnostic observed-test hints for a mutant (not an exclusive selection) |
| `mutmut-win time-estimates [MUTANT_NAMES…]` | Estimated runtime per mutant |
| `mutmut-win export-cicd-stats` | Write `mutants/mutmut-cicd-stats.json` for CI gates |

`run` persists a new run attempt before staging or generation starts and
finalizes its exact mutant plan only after successful generation. `results`,
`browse`, and `export-cicd-stats` use that current run snapshot as their
authority. Historical rows remain available only as explicitly validated
reuse candidates; they cannot silently fill a failed, interrupted, or partial
current run. CI export therefore refuses an incomplete current snapshot and
removes a stale export rather than presenting it as fresh evidence.

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
| `--profile {basic,advanced,all}` | Operator profile (overrides `[tool.mutmut]`): `advanced` (default) = mutmut base + mutmut-win's extras; `basic` = strict mutmut parity (the 15 base operators); `all` = + aggressive operators |
| `--since-commit REF` | Mutate only files changed since a git ref (e.g. `HEAD~1`) — committed **and** uncommitted tracked changes; untracked files need a full run |
| `--min-score N` | Full-run CI gate: exit 1 below N percent/incomplete basis; incompatible with name, path, or `--since-commit` subsets (exit 2) |
| `--output json` | Pure JSON result on stdout; prose on stderr |
| `--max-children N` | Worker process count |
| `--force` | Delete `mutants/` and `.mutmut-cache/` first (clean slate) |
| `--rerun-all` | Execute every mutant even when a cached verdict could be reused |
| `--dry-run` | Count mutants without running tests |
| `--no-progress` | Suppress live progress lines (the final summary always prints) |
| `--debug` | Full tracebacks on errors |

Exit codes of `run`: `0` success, `1` runtime failure, failed
`--min-score` gate or aborted run (worker pool collapsed — the unchecked
remainder is reported and the score gate is skipped), `2` invalid
configuration or option value, `130` interrupted (Ctrl-C — partial
results are persisted, the score gate is skipped).

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

# Advanced
max_stack_depth = -1                  # stats-hit frame walk; -1 = unlimited (0 is rejected)

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
- `mutate_only_covered_lines` measures coverage via a subprocess bridge.
  Code exercised only in test-spawned subprocesses or pytest-xdist
  workers is invisible to it — such a run fails loudly instead of
  silently filtering every mutant.
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
  almost everything as "running"), so infinite-loop verdicts rest on CPU
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
| `killed_by_infinite_loop` | Classifier verdict: the suite never terminates under the mutant |
| `segfault` | The test process crashed under the mutant — also a detection |
| `survived` | **No test noticed the change — this is your test gap** |
| `timeout` | Budget exceeded without an infinite-loop verdict |
| `suspicious` | Unexpected pytest exit code (diagnostic tail is captured) |
| `no tests` | Reserved for a future runtime-authoritative mapper; the current collector never emits this verdict |
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

The denominator excludes `skipped`, historical or future-authoritative
`no tests`, and unchecked mutants. The current non-authoritative mapper never
creates new `no tests` verdicts: an unobserved mutant runs the full suite.
Always read the bucket counts next to the percentage.

**Mutation-surface limits:** the trampoline mechanism rewrites top-level
functions and top-level-class methods. The two kinds of nesting differ:

- A **function nested inside a function** (a closure) gets no trampoline
  of its own, but its body *is* mutated — folded into the enclosing
  top-level function's mutant set, so closure logic is covered.
- A **method of a class nested inside another class** is genuinely not
  mutated and contributes no mutants rather than appearing as `survived`.

Repeated same-named top-level functions or class methods remain distinct.
The first occurrence keeps its historical mutant name; occurrence 2 and later
use a reversible `ǁ<ordinal>` suffix before `__mutmut_…` (for example
`pkg.x_fǁ2__mutmut_1`). This is intentionally identity-affecting: cached
verdicts from the former colliding representation are not reused.

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
   forced-fail check proves the trampoline actually switches mutants —
   the failure must come from the trampoline's own exception, a hung or
   unrelated failure fails the gate.
3. **Map & budget**: a stats run records per-test durations and a diagnostic
   test↔function mapping. The current collector cannot prove completeness
   across subprocesses, threads and native launchers, so on-disk mappings are
   always loaded as non-authoritative: observed durations may order independent
   mutant tasks, but pytest's native item order is unchanged, every survivor
   receives the full selected suite, and no cached flag can create selective or
   `no tests` verdicts. A measured startup floor plus the full-suite time
   determines both budget and reuse identity.
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
backs up and atomically replaces the selected source file. Add `mutants/`,
`.mutmut-cache/` and `.mutmut-win-*.run.lock*` to `.gitignore`.

## Development

```bash
git clone https://github.com/pgm1980/mutmut-win.git
cd mutmut-win
uv lock --check
uv sync --locked --only-group build --no-install-project
uv sync --locked --extra dev --group build --group security --no-build-isolation

uv run --no-sync pytest              # full suite (unit + integration + architecture)
uv run --no-sync ruff check .        # lint
uv run --no-sync ruff format .       # format
uv run --no-sync mypy src/ scripts/  # type check
uv run --no-sync lint-imports        # layer contracts

uv sync --locked --only-group security --no-install-project
uv run --no-sync python -I scripts/semgrep_release_gate.py  # pinned, fail-closed security gate
```

mutmut-win runs its own mutation testing on itself (dogfooding) as part
of its release gates.

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
notes. PyPI publishing is not part of that sequence. Breaking changes wait for a major version; deprecations warn
for at least one minor release first (current example:
`--treat-timeout-as-kill`).
<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

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
184/188). v2.19.0 added the aggressive `all`-tier operators (arithmetic
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
artifact, and security contracts documented in the repository. Details:
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
