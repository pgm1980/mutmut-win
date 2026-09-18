# MBR-2026-09-14-01 — v2.21.3 Fix Work

LIVE work state. Base: main @ fcb1593 (v2.21.3 merge). Active branch:
`fix/v2.21.3-evidence-closure`.

## The reported bug (lean4-lsp-mcp-server, mutmut-win 2.21.2)
`mutmut-win run` hung 15-60 min silently after force-cleanup. ROOT CAUSE: gitignored
`tests/test_project/.lake` (120k files / 6.5 GB) was enumerated/copied/hashed by FIVE+
walks per run; `.gitignore` was never respected. Lock hypothesis was REFUTED (non-blocking,
bounded 0.5 s retry).

## Fixes shipped in v2.21.3
- **Fix B (primary)**: `gitignore_boundary.py` (pathspec>=1.1.1,<2). Hierarchical
  .gitignore resolution, dir-PRUNING, git semantics, fail-closed on unreadable files,
  dotenv carve-out. Integrated into stats `_hash_context_tree`, staging iterators,
  `copy_also_copy_files`/`_sync_tree`, `copy_src_dir`, `walk_all_files`.
- **Fix A**: `--force` cleanup retry (delays 1.0, 2.0) before the fail-closed refusal.
- **Fix C**: prelude observability + `stall_watchdog.py` (faulthandler repeat-dump after
  60 s without progress, never kills, fileno fallback on `sys.__stderr__`).
- **Atomic-write hardening**: three narrow retries in `atomic_file.py`; attack tripwires
  still fire immediately (pinned by `test_runner_sidecar_safety`).
- **Publish-once phase guard** in `process/worker.py`.
- **Config**: `clean_run_timeout = 5400` (raised from 2700 in daf5f34 — note: older
  memory text said 2700, that value is obsolete).

RELEASED 2026-09-15T13:56:42Z. Annotated tag v2.21.3 -> merge fcb1593 (tree
b956fd29d0f6ba439e9d37709927950f74b00e51, byte-identical to candidate a6bd52e).
PR #138 merged 2026-09-15T13:55:05Z.

## Mutation testing — METHOD CHANGED, read this before resuming
The suite-wide gate (`--tests-dir tests/unit/`) is NOT USABLE for these two modules.
Measured 2026-09-17: 311 mutants, 3068 test-to-mutant mappings across 2480 tests,
**~1500 s per mutant** — even trivial `StallWatchdog.__enter__` mutants. 2 of 311
completed in 2.5 h; projected >100 h. Cause: coarse mapping pulls a large share of the
2.6k-test suite into every mutant, and the clean run alone takes ~33 min.

Canonical method now: **targeted gates, one contract test file per gate**, kills unioned
across gates (a mutant killed in ANY gate is dead). Runtime drops from hours to ~1 min.

```
uv run --no-sync mutmut-win run --paths-to-mutate src/mutmut_win/stall_watchdog.py \
  --tests-dir tests/unit/test_mbr_startup_fixes.py --force --no-progress
uv run --no-sync mutmut-win run --paths-to-mutate src/mutmut_win/gitignore_boundary.py \
  --tests-dir tests/unit/test_gitignore_boundary.py --force --no-progress
uv run --no-sync mutmut-win run --paths-to-mutate src/mutmut_win/gitignore_boundary.py \
  --tests-dir tests/unit/test_gitignore_staging_integration.py --force --no-progress
```

Use a LEAN external env for mutation runs: `uv sync --all-extras` WITHOUT `--all-groups`.
With security+release groups installed (131 packages incl. semgrep), the execution-basis
fingerprint hashes every file of every distribution and the prelude stalls indefinitely
(the stall watchdog makes this visible). Lean (61 packages): fingerprint 14-23 s.
Use a SEPARATE full env (`--all-extras --all-groups`) for pytest/gates — it needs
hatchling for the wheel/sdist test.

### FINAL RESULTS (2026-09-18, after the fix below) — both modules over the 80 % target
- `stall_watchdog.py`: **53/56 = 94.6 %**. Three survivors, all documented equivalents:
  `_stream_with_fileno(sys.stderr)` is bit-identical to the ternary when `file=None`,
  the matching `__init__` variant likewise, and `not self._armed` is indistinguishable
  from the conjunction because a missing target means the watchdog was never armed.
- `gitignore_boundary.py`: union of both gates **188/229 = 82.1 %** (229 instead of 255
  mutants because `enter_forced` was removed). 41 survivors, led by `descend_forced` (15).

Operational note: `--force` cannot remove `mutants/` while any shell holds its cwd inside
it (Windows directory handle). The run then fail-closes with "refusing to run with stale
state" — correct behaviour, but check your cwd first.

### Baseline before the fix (2026-09-17, released v2.21.3 code)
- `stall_watchdog.py`: **44/56 killed = 78.6 %**, 0 timeout, 0 suspicious. Reproduced
  identically before and after the repo cleanup.
  12 survivors: `_stream_with_fileno` x3 (fileno fallback chain has no direct unit test),
  `__init__` x4 (the `file=` parameter is repo-wide unused), `progress` x3 (the test
  asserts only `call_count`, not the `repeat` argument), `arm` x1 (`target is None`
  defensive path unreachable in the suite), `__enter__` x1 (context-manager return value
  is never bound anywhere).
- `gitignore_boundary.py` vs `test_gitignore_boundary.py`: **126/255 = 49.4 %**.
  Low by construction — the unit tests never call `descend`, `descend_forced` or
  `enter_forced`. The union with the staging gate is the meaningful number.
- `gitignore_boundary.py` vs `test_gitignore_staging_integration.py`: **118/255 = 46.3 %**.
  Union with the unit gate: **158/255 = 62.0 %**. One clean run failed transiently on
  `TestRunBasisEvidence::test_ignored_tree_does_not_change_the_digest`; it did not
  reproduce on retry nor when run alone inside `mutants/`. Transient, not a digest defect.

## Defect found 2026-09-17, FIXED on `fix/v2.21.3-evidence-closure` (PR #139)
Still present in the published v2.21.3; its release body documents it with a workaround.
`gitignore_boundary._excludes` computes `relative = _relative_to_base(candidate, level.base)`
but then matches patterns against `probes`, which derive from `candidate` (the
walk-root-relative path). The level-relative path is discarded. Verified at code level.
- Root `.gitignore` (base == "") is unaffected — which is why every fixture passes.
- Nested `.gitignore`: an anchored pattern (`/dist/`) no longer matches -> under-pruning
  (harmless direction, but exactly the bug class v2.21.3 set out to fix).
- Dangerous direction: an unanchored pattern matching an ANCESTOR path component
  (entry `logs` in `logs/.gitignore`) wrongly excludes `logs/app.txt`, dropping it from
  the execution-basis hash and from staging. Violates the module docstring's fail-closed
  promise.
- No test covers nested `.gitignore` semantics at all.
Also dead code: `enter_forced` has no caller and no test (26 unkillable mutants, ~8.4
percentage points of the gitignore score); `_root` is written but never read;
`StallWatchdog.timeout` getter is never read.

## Repo cleanup 2026-09-17 (user-driven)
Deleted permanently: `.claude/` (hooks, skills, settings), `bug_reporting/` (all
dossiers), `_config/fs_mcp_server.md`, `_config/mutmut-win-install.md`,
`_docs/basis_diagnostics.md`, `_docs/installation/`, `_docs/audit/`, `_misc/`,
`.opencode/`. Install guide now at `_docs/mutmut-win-install.md`.
CLAUDE.md slimmed (757 -> 695 lines) and de-contaminated.

**Release evidence now lives ONLY in the GitHub release body** — there is no
`bug_reporting/RELEASE_<version>.md` any more and none should be created.

**No test may require a documentation file.** `test_release_supply_chain.py` was
decoupled from README.md, CLAUDE.md, MEMORY.md, `_docs/**` and `.serena/memories/**`
(3380 -> ~2750 lines). `.sprint/state.md` stays readable by tests — it is the sprint
control document. The PUBLICATION_STATE contract was removed from tests and documents.

## Test files added in v2.21.3
`tests/unit/test_gitignore_boundary.py` (14), `test_gitignore_staging_integration.py` (10),
`test_mbr_startup_fixes.py` (9), `test_atomic_transient_retry.py` (11).
Full suite on the cleaned tree: 2584 passed / 43 skipped / 10 failed (all ten in
`test_release_supply_chain.py`, all caused by the cleanup, all repaired since).
