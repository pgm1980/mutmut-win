# Sprint 36 Progress (live tracking)

Sprint 36 "v2.14.0 Maintenance 4: Fable-5 360°" — opened 2026-06-12, branch
`feature/v2.14.0-maintenance-4`, issues #124–#132, backlog
`_docs/sprint backlogs/sprint_36_backlog.md`, findings inventory in memory
`fable5_360_findings`, sprint state `.sprint/state.md`.

## AUTONOMY MANDATE (user directive 2026-06-13)
All remaining waves run AUTONOMOUSLY — the user cannot supervise. Scope:
A1–A9, B1–B12, C1–C5 (B13 + C6 stay in scope as part of the approved #132
bundle per sprint backlog; any Won't-Do gets documented in the issue).
Do NOT stop to ask between waves. Per wave: TDD red→green, gates (ruff 0,
format, mypy ≤14 baseline, pytest green, semgrep PRO ≥1200 rules/0
findings via registry bridge, mutation ≥80 % on changed functions —
harden survivors like wave 1), commit "(closes #NNN)", update THIS memory.
Sprint end: full-suite gates + pip-audit + dogfooding full pilot
(reference: 7800 mutants / 68.3 %), sprint housekeeping (.sprint/state.md
flags truthful, backlog doc, MEMORY.md), then REPORT and WAIT — merge to
main and release happen ONLY on the user's explicit decision (release
policy). No push without user request.

## Mode (user directive 2026-06-12)
- Wave implementation in the MAIN session (not subagent-driven).
- Serena for ALL code analysis/editing (symbol tools first).
- MAXential CoT / ToT sharpening at Claude's discretion; Design-CoT ≥ 8 mandatory
  for #125 guard (DONE, 12 steps), #127 abort state, #130 mapping invalidation.
- Semgrep gate in PRO mode (registry bridge: winreg HKCU SEMGREP_APP_TOKEN →
  subprocess env; sessions don't inherit the var until Desktop restart).
- uv needs system TLS certs on this host: `UV_SYSTEM_CERTS=1` (or
  `uv ... --system-certs`) — bundled roots fail with UnknownIssuer.
- TDD red→green per fix; mutation ≥ 80 % on changed modules; commits per wave
  with "(closes #NNN)".

## Wave status
- **Wave 1 (#124 A1+B10, #125 A2): DONE** (2026-06-12). Commits: `6302b46`
  (fixes, closes #124+#125 on merge), `a8fdd85` (mutation hardening),
  `c9f526e` (pre-existing benchmarks format drift, chore).
  - Design-CoT: 12 steps (MAXential). TDD red→green verified both phases.
  - Gates: suite 1025→1031 passed / 5 skipped, ruff 0, format clean,
    mypy 14 = baseline, import-linter KEPT, semgrep PRO 1228 rules /
    0 findings. **Mutation gate: 110/121 = 90.9 % on changed/new code**
    (_update_source_data 4/4, _reset 6/6, guard 36/39, load 60/67,
    _discard 4/5; side effect: untouched save 66.7→81 %). First run was
    63.6 % on changed code → survivor classes killed via verbatim
    diagnostic pins, full-field asserts, exact+hypothesis meta roundtrip,
    two-digit version tests. Remaining 11 survivors classified in commit
    a8fdd85 (equivalents / documented won't-kill; 2 classes additionally
    covered by tests effective from the next full run).
- **Wave 2 (#127 A6+A7+A9): IMPLEMENTED & COMMITTED `26ade60`**
  (2026-06-13). Design-CoT: 10 steps (MAXential, incl. the MagicMock-
  truthiness trap → identity check `is True` at the orchestrator seam).
  - A6: json redirect scope now starts before --force/config-load
    (ExitStack in cli.run); child-side prints born on stderr (worker ×3,
    meta-corruption warning, executor abort); config warnings → stderr.
  - A7: executor `aborted`/`abort_reason` state; additive
    `MutationRunResult.run_aborted`; `_executor_aborted()` seam; ABORTED
    summary line; CLI exit 1 fail-closed (JSON echoed first, 130 keeps
    precedence); README exit codes updated.
  - A9: show resolves once (resolve_mutant + render_function_diff);
    resolved name used for header/diff/forensics lookup.
  - Adapted pinned-behavior tests: corruption/config/abort prose
    stdout→stderr flips; show seam patches → resolve_mutant/render.
  - Gates: suite 1050 passed / 5 skipped, ruff 0, format clean, mypy 14 =
    baseline, import-linter KEPT, semgrep PRO 1228 / 0. **Mutation
    line-level gate: 52/59 = 88.1 %** (function-wide measurement separated
    via staged-slice diff vs wave-2 tokens: 425 of 449 survivors are
    PRE-EXISTING debt of run/_process_task etc. — documented legacy, see
    commit 52c5884). Hardening commits: 52c5884. Remaining 7 touching
    survivors are documented equivalents (getattr default before `is
    True`; 6× print flush variants — capsys-indistinguishable).
    LEGACY DEBT NOTE for the final report: biggest functions sit at
    run 60.7 %, _process_task 41.1 %, worker_main 49.2 %, get_events
    62.5 %, __init__ 35.3 %, _print_summary 22 %, load_config 76.5 % —
    candidate for a dedicated tech-debt sprint, NOT wave-2 scope.
- **Wave 3 (#126, #129, #128): IMPLEMENTED & COMMITTED `2432bf2`**
  (2026-06-13). Design-CoT: 9 steps. SOURCE_ROOT_NAMES SSOT (source/-
  layout fixed, e2e fixture source_layout proves kills, 4.8 s);
  engine_version in config fingerprint; mirror rule split by .meta
  ownership (equality for plain mirrors — backdated restores sync;
  strictly-newer for generator-owned); _sync_tree with deletions replaces
  copytree for also_copy; shared _STAGING_SKIP_DIRS; since-commit nested
  tests_dir + ref-only diff (working tree included). One legacy test
  rewritten to the new mirror semantics. Gates: 1062 passed / 5 skipped,
  ruff 0, format clean, mypy 14 = baseline, semgrep PRO 1228/0. Mutation
  gate on file_setup functions RUNNING — record score when done.
- **Wave 3 hardening: COMMITTED `e9dcb10`** — line-level 73.5 % before
  kills; _mirror_is_stale direct pins, also_copy single-file branch,
  deletion-sync arg pin; 5 documented equivalents (hash key strings,
  subsumed condition, perf dedup, set/frozenset, .META on NTFS).
- **Wave 4 (#130 B1+B2+B3, #131 B4+A5): IMPLEMENTED & COMMITTED `c9e33e8`**
  (2026-06-13). Design-CoT: 9 steps. B1 test-file fingerprints in stats
  cache (full re-collection on in-place edits, legacy heals once, success
  path re-saves to persist fingerprints, stats_time preserved); B2
  collect_tests stats-phase parity (cwd=mutants + env + both arg lists +
  tests_dir, errors=replace; project-root fallback); B3 unassigned tasks
  always get the full-suite budget (mean only sorts; two pinned tests
  rewritten); B4 type-check baseline subtraction via __mutmut_orig
  (offset,text) signatures + stderr notice; A5 README example fixed +
  pre-run JSON-flag warning (_warn_missing_json_flag). Suite 1072
  passed / 5 skipped, statics clean. Combined wave-3/4 mutation gate
  RUNNING (background) — record when done.
- **Wave 3+4 gates CLOSED**: wave-3 line gate 91.4 % (commit `e9dcb10`);
  wave-4 hardening commit `232b2eb` → re-gate 87.0 % overall with ALL
  wave-line survivors killed (filter 92.6, warn 97.1, collect_tests 97.0,
  fingerprints 90.5, apply_timeouts 87.8, save/load_stats ≥80).
  _run_stats_collection 60 % rest = untouched failure-path legacy
  (documented). Equivalents documented in the two commit messages.
- **Wave 5 (#132): IMPLEMENTED & COMMITTED `67b66d8`** (2026-06-13).
  B5 phases now Popen + kill-on-close job + tree sweep (incl.
  run_coverage_collection); shared test mock tests/unit/phase_mock_util.py.
  B7 REVISED: no validator (the '..'-sibling IS the Bug-#69 use case,
  staged under basename per A3-FD-002) — instead PYTHONPATH parity in
  worker._process_task + runner._mutants_env. B8 IL constants single-
  sourced (constants.STATUS_KILLED_BY_INFINITE_LOOP; loop_monitor
  re-exports). B9 setup.cfg full parity + unknown-key warning from
  model_fields. C1 db.save_results batch (benchmark: 5.5 ms vs 775 ms
  per-row, 300 rows); orchestrator mass persists batched. C5 regex
  dedupe. C6 plain dicts + .get. B11/B12 README+comment, B13 ruff
  excludes .claude/ (bare `ruff check .` now a gate), C3 Won't-Do
  documented. Suite 1118 passed / 5 skipped; statics clean.
  **Wave-5 gate CLOSED**: function-wide 61.2 % → wave-line 82.4 % →
  after hardening commit (sentinel job-handle lifecycle tests for both
  phase functions incl. close-once semantics; word-exact sorted
  unknown-key warning with 4 typo keys) re-gate = **98.6 % wave lines**
  (runner 100 %, config 97.6 %). Documented equivalents: EXTRA_PATHS
  lookup (ConfigParser optionxform lowercases the key), unsorted
  no-test batch (PK upsert + order-independent meta update).
- **Sprint gates so far**: Semgrep PRO 1228 rules / 0 findings
  (registry token bridge); pip-audit clean after lock bumps
  urllib3 2.7.0 / idna 3.18 / pip 26.1.2 / pytest 9.0.3 (`9f73eee`,
  truststore-injected against TLS interception); bare `ruff check .` 0;
  mypy 14 baseline; import-linter KEPT; full suite 1118/5 skipped.
- **Dogfooding full pilot RUNNING** (background, started 2026-06-13
  after all wave gates; reference S34: 7800 mutants / 68.3 %; result
  reuse #119 active by design — note in report). After it: write
  results into sprint_36_backlog DoD, set .sprint/state.md flags
  truthfully, REPORT AND WAIT (no merge/release/push without user).

## Gates checklist per wave
ruff 0 · mypy ≤14 baseline · pytest green · semgrep PRO (≥1200 rules, 0
findings) · mutation ≥80 % changed modules · regression test per A-finding.
