# mutmut-win — Project Memory

> Last refresh: 2026-06-11. Source of truth for sprint state is `.sprint/state.md`;
> source of truth for issues is the GitHub repo. This file is the human-readable
> at-a-glance snapshot.

## What it is
Windows-native Python mutation-testing tool. Port of upstream `mutmut 3.5.0`
adapted to Windows: native subprocess + Job Object orphan-protection, no POSIX
fork dependency, in-process pytest stats collection, libcst-based mutation
generation. Since v2.5.0 (made honest in v2.8.0): infinite-loop detection —
a psutil-based sampling classifier (CPU + progress signals, process status on
POSIX only) with persisted forensics and a platform-aware confidence band.

- Python 3.12 – 3.14
- Stack: click (CLI), libcst (mutations), pydantic v2 (config), textual (TUI),
  coverage (coverage-guided), psutil (IL detection), SQLite (results),
  pytest (test runner).
- Distributed as `mutmut-win` on PyPI. Console script: `mutmut-win`.

## Where we are
- **Version**: **v2.11.0** released 2026-06-11
  ([release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.11.0),
  bump 493f120) — Maintenance 1: Runtime & Self-Run. Pilot 24.2% ->
  86.9% gross, 0 timeouts; QX-001 architecture skip removed; score
  shift documented in the notes (no_tests leaves the denominator).
  Maintenance pool: 13 entries.
- **Version**: **v2.5.1** released 2026-05-23 (hotfix on top of v2.5.0:
  psutil.Process instance caching for stable cpu_percent). Annotated tags
  `v2.5.0` + `v2.5.1` on `main`.
  [GitHub releases](https://github.com/pgm1980/mutmut-win/releases).
- **Version**: **v2.10.0** released 2026-06-11
  ([release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.10.0),
  bump 060ea16) — **THE AUDIT CYCLE IS CLOSED**: C1–C8 complete + C9
  top, 31 issues (#73–#103+#104), all 15 S1 fixed across
  v2.6.0–v2.10.0 (five releases, one day). 0 open issues. Remainders
  live in the severity-sorted **maintenance backlog** (product backlog,
  13 entries after Sprint 33 cleared 13 incl. DOG-001/002). Earlier same day:
  v2.9.0 (C6+C7, "score corrections"), v2.8.0 (C5), v2.7.0 (all S1),
  v2.6.0 (W4.11 blockers — nextgen-cot-mcp-server can upgrade its pin
  and revert the §1.5 genexp workaround).
- **Sprint**: 34 — *v2.12.0 Maintenance 2: Final Sweep* — implementation
  complete 2026-06-11 (7 issues #111–#117, 27/27 SP, commits
  8251509..fa590ac on `feature/v2.12.0-maintenance-2`): THE LAST SPRINT
  before the planned development pause. **Maintenance pool 13 → 0,
  open-decisions register 4 → 0.** Forced-fail proves the right thing
  (#111: -x, timeout never success, MutmutProgrammaticFailException
  attribution via --tb=line + COLUMNS; PY_IGNORE_IMPORTMISMATCH
  single-sourced for all phases + worker); shlex arg coercion for both
  pytest arg fields, Windows-safe escape="" (#112); sanitiser covers
  [tool.uv.sources.<pkg>] subtables (#113); exception hygiene (#114:
  exit-4 producer at the clean gate, InvalidConfigValueError/
  WorkerError/MutationParseError wired, WorkerCrashError/WorkerInitError
  deleted as unproducible, TypeCheckCommandError + CoverageCollectionError
  replace bare Exceptions, cli catches MutmutWinError — foreign bugs
  propagate as tracebacks; **mypy baseline 20 → 14**); one name-matching
  rule (#115: match_mutant_names backs run/show/apply/time-estimates,
  resolve_mutant requires a unique match with candidate list,
  patch-capable diffs via PositionProvider, summary alignment incl.
  legacy labels); sitecustomize as explicit injectable setup step +
  normcase/realpath blocker (#116); closure dossier (#117:
  --treat-timeout-as-kill deprecated-now/remove-in-v3, release policy in
  the README, OS-012-Rest/shrink-storm/BUG_REPORT_9 formally closed,
  5 stale GitHub milestones closed). Gates: 951 passed (+83),
  ruff/format 0, semgrep 0 (full sweep), lint-imports KEPT incl.
  artifact; pilot **85.1% gross HELD** (6 cold-start timeouts
  re-run-verified as kills → 87.6% effective; 30 survivors = the
  documented accepted classes); pip-audit still environment-blocked
  (TLS interception). **Closing full self-run** (--since-commit
  --force, first-ever measurement over all 12 changed modules): 7800
  mutants, 68.3% gross, 2337 survivors + 45 timeouts documented as the
  honest pause baseline (NOT pool entries); two dogfooding finds —
  the --force-after-config-change lesson (7318 honest 'no tests'
  instead of days of full-suite runs, #106 working as designed) and
  one instrumentation-unsafe test fixed (6101548). Release v2.12.0
  pending user approval — **development pauses afterwards**.
- **Sprint**: 33 — *v2.11.0 Maintenance 1: Runtime & Self-Run* —
  implementation complete 2026-06-11 (6 issues, 31/31 SP, commits
  28a718f..4b87423 on `feature/v2.11.0-maintenance-1`): FIRST
  demand-driven maintenance sprint (pool selection, no promise for the
  rest). **Pilot 24.2% -> 86.9% GROSS, 0 timeouts instead of 175** —
  verified twice (mid-gate after #105/#106/#110 AND closing run,
  deterministically identical 212/32/0 over 244). Measured startup
  floor in the timeout model (#105: clamp(clean_wall − Σdurations,
  5, 60) + clean-wall-scaled full-suite fallback, floor printed with
  its inputs); no-tests producer (#106: mapped-but-empty → exit 33
  persisted, never dispatched; empty mapping keeps the loud full-suite
  fallback); hygiene batch (#110: max_stack_depth 0-trap rejected,
  depth cache in _state covered by _reset_globals, MUTANT_ENV_VAR
  single-sourced in constants, IL hint once per RUN); **trampoline
  decoupled (#107): hit recording in bottom-band kernel module
  `hit_recording`, template imports exceptions/hit_recording instead
  of __main__ (~1.4s CLI chain per test process gone), QX-001
  architecture skip REMOVED — the layer gate ran green INSIDE the
  fresh artifact (closing run, 840 tests)**; browser diff single-source
  (#108: render_function_diff shared with `show`, DB fallback searches
  the local def name); robustness (#109: empty-table guard, ConfigError
  exit 2 in show/apply, DOCUMENTED empty-DB convention — informational
  0 / CI gate 1, summary always prints — --no-progress gates only live
  lines). Maintenance pool 26 -> 13 (13 findings cleared). Gates: 868
  passed bare (+47), ruff 0, format-check 0, mypy 0 new (baseline 20),
  semgrep 0 (full src+tests sweep), lint-imports KEPT everywhere incl.
  artifact, pilot documented. **Released as v2.11.0 on 2026-06-11 —
  sprint fully closed (31/31 SP; merge auto-closed #105–#110, 0 open
  issues; gates re-verified pre-merge: 868 passed).**
- **Sprint**: 32 — *v2.10.0 Pipeline Hygiene* — implementation complete
  2026-06-11 (7 items, 36/36 SP, commits 804e402..4d1e908 on
  `feature/v2.10.0-pipeline-hygiene`): THE LAST AUDIT SPRINT — cycle
  formally closed with a final tally in the register. Self-hygiene
  (#98.1: isolated repo-wide format commit, bare-pytest canon via
  conftest, semgrep really scans tests/ now — 101 files, 11 test
  idioms suppressed with reasons); runner diagnostics + stats truth
  (#99: DEVNULL->tail capture with exit decoding, extra_paths on the
  runner PYTHONPATH, a failed stats run can never poison the cache —
  the plugin JSON is the single source of truth); DB hardening (#100:
  read-path migration for pre-v2.5 caches, contextlib.closing
  everywhere, race-tolerant migrations, surrogate-safe writes);
  staging hygiene (#101: '..' containment keeping the Bug-#69 sibling
  case, deletion sync incl. .meta orphans = OS-012 fully closed,
  source fingerprint in .meta — the first inequality-based attempt
  was caught by our own suite, config fingerprint gates the fast
  path, atomic+tolerant .meta, honest --force); config/CLI truth
  (#102: re-validated overrides — '--max-children 0' was an accepted
  hang, difflib typo warnings, since-commit returncode+filtering,
  real --debug); CI output discipline (#103: json.loads(stdout) works,
  prose to stderr; no UnicodeEncodeError on cp1252); C9 triage (#104:
  26-entry severity-sorted maintenance backlog, audit register closed).
  **DOGFOODING PREMIERE (#98.2)**: pilot 5 ran complete (244 mutants,
  85.5% over assessable, type_checking 96.4%); pilots 1-4 were finds
  themselves (stale-staging ghosts, 42 cwd-dependent tests = RN-010
  live, QX-001 caught by our own architecture gate, an obsolete env
  pin) — plus two new maintenance entries (DOG-001 timeout startup
  floor S2, DOG-002 per-worker hint spam S4) and one real test gap
  fixed. Gates (TIGHTENED, all green): 821 passed bare, ruff 0,
  format-check 0 (new), mypy 0 new (baseline 20), semgrep 0 on
  src+tests (new), lint-imports KEPT, mutation pilot documented
  (first ever). **Released as v2.10.0 on 2026-06-11 — sprint fully
  closed (36/36 SP, 0 open issues); audit cycle formally ended.**
- **Sprint**: 31 — *v2.9.0 Feature Truth & Score Integrity* —
  implementation complete 2026-06-11 (7 items, 33/33 SP, commits
  33c2c98..09c6cd7 on `feature/v2.9.0-score-integrity`): status truth
  (#91: exit-code map fixed — dead -24 duplicate, NTSTATUS crashes →
  segfault, exit 2 = collection kill per design CoT; complete buckets +
  loud catch-all + sum-invariant test; kill-class score formula in all
  three channels; generic results rendering; worker captures log tail
  for every anomalous exit); type checking hardened (#92: basename
  detection — mypy.exe/uv-run forms used to ABORT runs; timeout/
  returncode/encoding — mypy exit 2 was a silent no-op filter; pyright
  severity filter; Context7 + empirically verified) and end-to-end
  (#93: to_mutants_relative canonical matching — the filter NEVER hit
  before; task intersection; DB persistence into its own bucket;
  100%-caught guard; E2E with real mypy); Ctrl-C honesty (#94:
  was_interrupted + unchecked, score over checked, exit 130, gate
  skip); **coverage gating REACTIVATED** (#95: spike + 8-step CoT —
  subprocess bridge, line reference system consistent by construction,
  normcase keying = CM-013, loud failure modes, dead compat API
  removed, mypy baseline 26→20); DB orphan purge on full runs (#96:
  safe default polarity, CLI wires the full-run fact, executemany —
  semgrep clean); CI channel (#97: score as computed_field in JSON,
  communicated zero-mutant gate). Gates: 773 passed / 4 skipped (+54),
  ruff 0, mypy 0 new, semgrep 0, lint-imports KEPT. **Released as
  v2.9.0 on 2026-06-11 — sprint fully closed (33/33 SP, 0 open
  issues).**
- **Sprint 30** — *v2.8.0 IL Detection Honesty* — implementation complete
  2026-06-11 (6 items, 25/25 SP, commits dfb9041..787633f on
  `feature/v2.8.0-il-honesty`): forensics persisted (#85) and rendered —
  `show` panel + browser IL awareness from constants (#87); CICD export
  counts IL kills, one score across run gate / results / export (#86);
  classifier honesty (#88, 12-step CoT + Context7): caller-declared
  `status_signal_available` (win32 → False), confidence capped `medium`
  on two-signal verdicts, PYTHONUNBUFFERED output signal,
  MIN_SAMPLES_FOR_VERDICT=5, output `None`-semantics on stat failure,
  sampler catch-all + `sampler_errors`/`status_signal_used` forensics,
  `output_threshold gt=0`, daemon/snapshot-cutoff/window-hint hygiene;
  io_counters spike (#89): REFUTED as sleeping substitute (sleep-wait ≡
  busy-loop at io level), BUILT as progress veto
  (`IO_OPS_PROGRESS_THRESHOLD=100`, veto-only, None-neutral); test/doc
  honesty (#90): running_ratio isolated for the first time,
  platform-exact integration asserts (win32 medium / POSIX high), sober
  prose. Audit register got a fix-log section. Gates: 719 passed /
  4 skipped (+38), ruff 0, mypy 0 new, semgrep src 0 (tests skipped by
  semgrep default ignore), lint-imports KEPT. **Released as v2.8.0 on
  2026-06-11 — sprint fully closed (25/25 SP, 0 open issues).**
- **Sprint 29** — *v2.7.0 Runtime Reliability* — implementation complete
  2026-06-11 (6 items, 27/27 SP, commits 4257f3c..243206a on
  `feature/v2.7.0-runtime-reliability`): both remaining S1 hangs fixed
  (#79 queue shutdown, #80 worker liveness) → **all 15 S1 audit findings
  closed**; per-task timeouts end-to-end + dead WallClockTimeout removed
  (#81, −464 lines); per-task kill-on-close jobs for tree reaping (#82 —
  ppid scans cannot bridge dead intermediates, empirically proven);
  job-object polish via parallel worktree subagent (#83); import-linter
  contracts realigned per ADR, gate now runs INSIDE pytest (#84).
  Gates: 681 passed / 4 skipped, ruff 0, mypy 0 new, semgrep 0,
  lint-imports KEPT. Release v2.7.0 pending user approval.
- **Sprint 28** — *v2.6.0 Source Protection & Codegen Correctness* —
  closed 2026-06-11 (all 6 items, 31/31 SP): BUG-2 clean_run_timeout
  config (#74), validate-then-write safety net + crash guards (#78),
  source protection incl. class-aware apply (#75), safe-unwrap for the
  parenless-yield class = BUG-1 (#73), mutants dict at module level
  (#77), wrapper codegen fixes (#76). Gates: 672 passed / 4 skipped,
  ruff 0, mypy 0 new, semgrep 0; lint-imports pre-existing broken
  (6 violations, verified pre-sprint — Sprint-29 item); dogfooding
  deferred until audit-C8 fixes. Note: environment SSL breaks pypi.org
  (pip-audit impossible; `uv lock`/`uv run` need `--system-certs` after
  version bumps).
- **Sprint 27** — *Full Source Audit (analysis-only)* — closed 2026-06-11.
  Deliverable: `_docs/audit/sprint_27_audit_findings.md` — **201 raw /
  ~180 unique findings, 15 × S1**, across all 29 src-modules, organized in
  fix clusters C1–C9. No source changes (analysis-only mandate). Trigger
  was the W4.11 downstream report (BUG-1 sole-genexp, BUG-2 300s-timeout —
  both verified, both NOT yet fixed).
- **GitHub Issues**: **0 open** — backlog fully cleared (verified 2026-06-11).
- **Tests**: 610 passed / 4 skipped (verified 2026-06-11); semgrep 0
  findings; pip-audit baseline NOT obtained (SSL error towards pypi.org).
- **In flight**: fixing sprints (28+) pending user prioritization.
  Recommended order: C1 source-protection (destructive: absolute
  paths_to_mutate overwrite sources; apply patches wrong function) →
  C2 codegen correctness (clean-run breakers, parenless-yield class incl.
  BUG-1) → C3 pool robustness / C4 timeout architecture (incl. BUG-2).

## Open Decisions / Open Items
**NONE — register closed by Sprint 34 / #117 (2026-06-11):**
- `--treat-timeout-as-kill` → deprecated now (warning on use, marked in
  help/README), functional through 2.x, removal in a future major.
- Hypothesis "shrink-storm" → monitor-only confirmed; never observed
  since Sprint 26, threshold tuning only on a real occurrence.
- `_bug_reporting/BUG_REPORT_9.md` → moot; the file no longer exists
  (verified 2026-06-11), its bugs were fixed in v2.2.0–v2.4.0.
- Release cadence → documented in the README ("Release policy"):
  demand-driven, gates → merge → bump → annotated tag → GitHub release,
  triggered only by an explicit user "Release"; no PyPI step.

## Architecture Cheatsheet
- `cli.py` / `browser.py` — UI layer (click + textual).
- `orchestrator.py` / `runner.py` / `mutant_diff.py` — coordination + execution.
- `config.py` / `models.py` / `constants.py` / `mutation.py` /
  `node_mutation.py` / `regex_mutation.py` / `trampoline.py` — domain layer.
- `process/` — Windows-specific subprocess + Job Object integration;
  `process/loop_monitor.py` (since v2.5.0) — `ProcessMonitor` sampling thread,
  pure `classify_samples()` triple-check classifier (CPU ≥ 70% AND output
  growth < 1 KB AND running_ratio ≥ 0.8 → `killed_by_infinite_loop`,
  exit code 38), `IlForensics`/`LoopClassification` Pydantic models.
- `db.py` — SQLite persistence (mutations, last_output, forensics JSON).
- `_state.py` — in-process globals populated by injected pytest plugin
  (`tests_by_mangled_function_name`, `current_test_name`,
  `record_trampoline_hit`).
- `import-linter` layers (in `pyproject.toml`):
  `cli|browser → orchestrator|runner|mutant_diff → config|models|constants|mutation|node_mutation|trampoline → process`.

## Recent History (one-liners)
- **Sprint 26 / v2.5.0 + v2.5.1** — true infinite-loop detection (#71:
  psutil ProcessMonitor + triple-check classifier + IlForensics persisted to
  DB, 5 new `[tool.mutmut]` keys, 2 new CLI flags), `--version` single source
  of truth via importlib.metadata (#72); hotfix v2.5.1 caches psutil.Process
  instances (fresh instances always returned cpu_percent 0.0).
- **Sprint 25 / v2.4.0** — final cleanup: `--extra-paths-to-copy` +
  `extra_paths` config for sibling packages (#69, downstream Bug #2),
  also_copy skips top-level venv/cache entries (#67, H-05), pytest-benchmark
  suite for mutation generation (#23).
- **Sprint 24 / v2.3.0** — Must-carryover cleanup: worker crash recovery
  (#12), full E2E pipeline validation on simple_lib + my_lib (#38, #49),
  deterministic Job Object kill-on-close test (#54), dogfooding expanded to
  full `src/mutmut_win/` (#65).
- **Sprint 23 / v2.2.0** — reliability wave for three downstream bugs: skip
  `or`-mutations on multi-line BooleanOperations (#68, Bug #1), skip
  default-parameter mutations (#70, Bug #3), `--treat-timeout-as-kill` flag
  (#71, Bug #5 stopgap).
- **Sprint 22 / v2.1.0** — Bug #4 typing.cast() skip (PR #66), housekeeping
  (42 stale issues closed, MEMORY.md+state.md+backlogs synced), v2.1.0 tag
  and consolidated GitHub release covering everything since v1.0.7.
- **v2.0.x** — Timeout diagnostics: subprocess timeouts, DEVNULL fix,
  temp-file capture, DB-persisted `last_output`.
- **v2.0.0** — Test-to-mutant mapping via injected pytest plugin
  (`fe194c2`).
- **v1.0.x** — Cache-invalidation fixes, WinError 32/206 fixes, `.pth`
  shadow, package copy.
- **Sprint 21 / Hardening v1.0.0** — Job Objects (#52–#54), 10 CLI flags
  (#63), hook fixes H-01–H-07 (#64), worker import fix H-06 (#62).
- **Sprints 14–20** — seven advanced operators merged (Regex, Math,
  Return, Conditional, Statement Removal, Collection, or-Default).

## Conventions Reminders
- Tooling: `uv` only (not `pip`). `uv run <tool>` for everything.
- Lint: Ruff (no black/flake8/isort/pylint in parallel).
- Type-check: mypy strict.
- Test: pytest + hypothesis + pytest-benchmark + pytest-cov.
- Mutation testing: `uv run mutmut-win run --paths-to-mutate <dir>`.
- Security: Semgrep before every sprint close, pip-audit on dependency
  changes.
- Filesystem ops: FS MCP server and Serena are **NOT available** for this
  project (FS MCP allowed-roots point elsewhere; Serena has no mutmut-win
  project registered — its memories belong to nextgen-cot-mcp-server).
  Use built-in tools (Read/Write/Edit/Glob/Grep); Bash file commands remain
  blocked by `.claude/settings.json`.
