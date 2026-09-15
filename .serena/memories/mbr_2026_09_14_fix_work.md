# MBR-2026-09-14-01 — v2.21.3 Fix Work (branch `fix/v2.21.3-lake-basis`)

LIVE work state. Base: main @ f726891 (v2.21.2 + evidence commit).

## The reported bug (lean4-lsp-mcp-server, mutmut-win 2.21.2)
`mutmut-win run` hung 15-60 min silently after force-cleanup. ROOT CAUSE (probe-proven
via reporter, see bug_reporting/MBR-2026-09-14-01_PROBE_ANSWERS.md): gitignored
`tests/test_project/.lake` (120k files / 6.5 GB) was enumerated/copied/hashed by FIVE+
walks per run; `.gitignore` was never respected. Lock hypothesis (orphaned .run.lock)
was REFUTED by code analysis (non-blocking, bounded 0.5 s retry) + mosaic counterproof.

## Fixes implemented (all unit-green, ruff/mypy/import-linter clean)
- **Fix B (primary)**: new module `gitignore_boundary.py` (pathspec>=1.1.1,<2 —
  MPL-2.0, pure-Python, zero mandatory deps, Py3.14, Trusted Publishing). Hierarchical
  .gitignore resolution, dir-PRUNING, git semantics: explicit entries force-included
  (git add -f; entry itself ignored → subtree immune), ignored subtrees inside
  configured trees pruned, excluded-dir ancestors pin subtree, fail-closed on
  unreadable .gitignore (excludes nothing). Integrated into: stats `_hash_context_tree`
  (project + configured trees; dotenv carve-out: .env* stays basis input even when
  ignored), `_iter_automatic_staging_inputs`, `_iter_configured_staging_inputs`,
  `copy_also_copy_files` + `_sync_tree` (deletion pass purges pre-fix staged leftovers;
  fully-pruned dirs not materialized), `copy_src_dir` own walk, `walk_all_files`.
  E2E proven: profile hint 138 s → 0.09 s after hint; .lake never staged.
- **Fix A**: `--force` cleanup retry (`_remove_force_cleanup_root`, delays (1.0, 2.0))
  before the fail-closed refusal (cli.py, `_FORCE_CLEANUP_RETRY_DELAYS`).
- **Fix C**: prelude observability — phase prints ("Fingerprinting execution basis…",
  "…fingerprinted in N s"), `--debug` step traces, new `stall_watchdog.py`
  (StallWatchdog: faulthandler repeat-dump on 60 s no-progress, Fileno-Fallback on
  sys.__stderr__, never kills, close() before pipeline; armed in
  orchestrator._run_with_identity).
- **Atomic-write hardening** (pre-existing bugs unmasked by mutation runs — family:
  Windows filter-driver interference under sentinel republication churn in the pytest
  phase guard): three NARROW retries in atomic_file.py — sibling validation
  (`_SIBLING_VALIDATION_RETRY_DELAYS`), replace (`_REPLACE_RETRY_DELAYS`), parent
  capture (`_PARENT_CAPTURE_RETRY_DELAYS`, long ~16 s ladder). fstat-nlink check
  relaxed to path-view-only (field data: fstat transiently reports 2 links on fresh
  O_EXCL inode while lstat says 1 — CX221-071 kin; O_EXCL + identity + leaf-nlink
  carry the contract). SECURITY: blanket retrying UnsafeAtomicWriteError was REJECTED
  by pinned substitution test (test_runner_sidecar_safety) — attack tripwires must
  fire immediately; only the three narrow points retry. Churn repro: 1/5000 → 0/20000.
- **Config**: `clean_run_timeout = 2700` in [tool.mutmut] (default 300 s aborted every
  full dogfood at the clean phase; staged unit tree needs ~30 min).
- Governance: dependency-export pin updated (pathspec), PEP-758 bare multi-excepts
  parenthesized + `# fmt: skip` (ruff format REMOVES parens on py314! semgrep 1.175
  parser needs them), .serena/project.yml LF-normalized, workspace caches cleaned.

## BLOCKER RESOLVED (2026-09-15 night session)
Root cause chain FULLY established: (a) external reporter-blocker = gitignore-blind
walks (Fix B, shipped). (b) Mutation-run deaths = phase-guard published its execution
proof ONCE PER TEST REPORT (~1700 full atomic-publication chains per phase), which
under ACTIVE Defender real-time scanning (was ON the whole time — user disabled it
only AFTER the analysis) plus a CONCURRENT mosaic mutmut-win run on the same machine
caused IO starvation: errno-less resolve failures, 60s-open stalls (watchdog dumps),
10x suite slowdown. FIX SHIPPED: guard template in process/worker.py now publishes
ONCE per phase (first qualifying call report, flag only set on success; later reports
no-op; first publication keeps FULL strict contract — pinned substitution tripwire
test unchanged and green). New pinned test: test_generated_phase_proof_publishes_
once_per_phase (note: runpy.run_path returns a COPY of globals — patch
mutmut_win.atomic_file.atomic_write_bytes BEFORE plugin publish, filter by marker
path; marker never exists before first hook call).
Runtime-dir-vanishing after run end = NORMAL TemporaryDirectory with-exit cleanup
(there was NEVER an external reaper; canaries of all ages survived).
clean_run_timeout=2700 documented; under contention the staged suite needs up to 45min.
ALL temporary diagnostics removed (parent-probe, sibling-diag stays as permanent
exhaustion telemetry, watcher scripts deleted). Gates green on atomic/worker/sidecar
clusters. v2.21.3 version bump + uv.lock done; README/install-guides pinned to 2.21.3;
RELEASE_2_21_3.md dossier drafted (gate/mutation/release sections pending).
REMAINING: Phase 2 mutation run (needs QUIET machine — mosaic must finish; Defender
now OFF so odds are good), Phase 3 gates, Phase 5 release chain.
311 mutants (255+56; REPEATED --paths-to-mutate flags — one path per flag!).

## Test files added
tests/unit/test_gitignore_boundary.py (14), test_gitignore_staging_integration.py (10),
test_mbr_startup_fixes.py (9), test_atomic_transient_retry.py (11).
Full suite: 2577 passed / 43 skipped (only remaining red: commit-gate test, green
after commit by design).

## Release path after blocker
Mutation score ≥ 80 % → full suite + gates → docs (bug report closure, README,
sprint state, dossier) → semgrep + native gates → commit/PR → release chain (user GO).
