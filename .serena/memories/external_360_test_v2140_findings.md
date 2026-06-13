# External 360° Test of v2.14.0 — Bug Inventory + Roadmap Acceptance (2026-06-13)

Source: a separate **test-management Claude-Code project** that black/white-box tested
the *released* mutmut-win v2.14.0. A temporary copy lived in `_external_tests/`
(DELETED by the user AFTER rescue). RESCUED ARTIFACTS (this session): roadmap acceptance harness -> `_docs/nextgen_roadmap/acceptance_harness/` (was testing/roadmap/, + README_PROVENANCE.md); bug-repro projects -> `_bug_reports/repro_projects/{crash,cache,poolcollapse,encodings}/` (gitignored/local-only, + README mapping finding->project). The two durable deliverables survive outside that folder:
- Bug report: `_bug_reports/BUG_REPORT.md` (Task 1 source).
- Nextgen operator roadmap: `_docs/nextgen_roadmap/` (`MUTATION_OPERATOR_MATRIX.md`
  + `MUTMUT_WIN_OPERATOR_ROADMAP.md`) (Task 2 source).
White-box ref used by the testers: `_external_tests/_codebase_v2140/mutmut_win/` was
SHA-256 byte-identical to the installed v2.14.0 (29 .py) — its line refs are authoritative.

Big picture: **all 15 prior v2.12.0 external-QA findings verified genuinely FIXED**
(behavioral, not comment-trust). Positive confirmations: opmatrix 100% (every ~29
operators yields a killable mutant), syntax314 92% (modern 3.12–3.14 syntax robust),
cache reuse / config validation / JSON purity / --since-commit / type-check filter / regex
operator / staging hygiene all good. Pool-collapse→exit1 and Ctrl-C→130 validated LIVE.

## FIX STATUS — branch feature/v2.15.0-maintenance-5 (2026-06-13, this session)
Light maintenance (Wellen-Commits, no GitHub issues — the report IS the spec):
- IL-001 (Medium) — commit 353f1c1 — loop_monitor.effective_window_seconds +
  worker._scale_il_window + orchestrator HINT recast; mutation 100% (24/24).
- DOC-003 + DOC-004 — commit 5f2ba06 — README closure wording + status -> v2.14.0.
- conftest-not-fingerprinted — commit b2bc19e — file_setup._conftest_staleness_warning
  in copy_src_dir; mutation 100% (7/7, verbatim pin).
- WRK-001 (Low) — commit ac6a52b — executor startup watchdog (_startup_grace_expired
  + _declare_startup_collapse in get_events, 60s grace); mutation 91.3%, 0 survived.
- MUT-003 (Low) — commit 865140f — orchestrator.dry_run encoding warning before
  continue; wave mutation 100% (2/2, mutmut_24 separator + 25 continue->break); the
  9 remaining dry_run survivors are pre-existing legacy debt, documented in the commit.
Per-wave gates: ruff 0, mypy 14 baseline, full suite 1140/5 green, mutation >=80% on
changed functions (verbatim diagnostic pins kill string mutants). NOT done yet:
the project MEMORY.md refresh (stale since Sprint 35 — Sprint 36/v2.14.0 missing);
merge to main + release stay the user's decision. All 6 findings committed:
353f1c1, 5f2ba06, b2bc19e, ac6a52b, 865140f.

## TASK 1 — 6 new findings to fix (BUG_REPORT.md §3, §6, §7, §8)

### IL-001 — Medium, highest priority
Infinite-loop classifier only returns a verdict when its sampling window fits the band
**[~2.5 s (min samples = 5×0.5 s), per-task timeout]**. Both ways out → `timeout`
(NOT in score numerator) instead of `killed_by_infinite_loop` (IS in numerator):
- **Window too large = the shipped default** `infinite_loop_window_seconds=10.0` >
  self-calibrated per-task timeout (~5–8 s on fast suites) → window never completes
  before task times out → `timeout`. Tool warns (`IL-MONITOR HINT`) but ships the
  mismatched default.
- **Window < ~2.5 s** → too few samples → also `timeout`. The HINT wrongly advises a
  *smaller* window → pushes users into this failure mode.
Effect: genuine IL mutants the tool *did* detect are scored as not-killed → **score
under-counted** on common fast suites; blunts a headline feature.
Repro (crash project, identical non-terminating mutants): window 10.0/2.0 → `timeout`;
window **3.0 → killed_by_infinite_loop** (CPU ~98-100%, output growth 0 B, 6 samples).
Fix: auto-scale default window into the band relative to the computed per-task timeout
(clamp 10.0 down to ≤ timeout, floor ~2.5 s); correct the HINT's directional advice.
White-box (verify with Serena): `process/loop_monitor.py` (window/sampling + HINT text),
`orchestrator.py` (per-task timeout calc / where window is applied), `config.py`
(default `infinite_loop_window_seconds`). Disproven mid-investigation hypothesis (NOT a
finding): "memory-growth loops defeat the classifier" — refuted, pure vs memory both
IL-killed at window 3.0. Sole cause is the band.

### MUT-003 — Low (CORRECTED from first pass)
A full `run` correctly **warns** for non-UTF-8 source (`Warning: could not mutate … 'utf-8'
codec can't decode byte 0xe9 …`), but **`--dry-run` is silent** (even with `--debug`) —
just reports a reduced count. Dry-run/run inconsistency. Repro: encodings project — utf8
file → mutants; latin1/cp1252 → 0, silent under dry-run. Fix: route the encoding-skip
warning through the dry-run code path too. White-box: `file_setup.py` (encoding skip),
`orchestrator.py` dry-run path.

### DOC-003 — Low (README)
README §"Result statuses and the score" → "mutation-surface limits" wrongly says nested
*functions* contribute no mutants. **Closures ARE mutated** (folded into the enclosing
top-level function; repro `edgecases.surfaces.x_outer_with_closure__mutmut_1`:
`return base+delta`→`return None`). Only nested-*class* methods (`Account.Nested.inner`)
are truly mutant-free. Fix: reword — closures' code IS mutated within the enclosing
top-level function; only nested-class methods are exempt. White-box: `README.md`
(~"Mutation-surface limits" paragraph, around line 264).

### DOC-004 — Low (README) — PARTIALLY DONE
README §"History and project status" said "v2.12.0 is the current release … zero open
issues". **Already fixed in this session**: updated to v2.14.0 + resumption baseline
(7231 mutants / 69.2%); History paragraph now covers v2.13.0 + v2.14.0. STILL TO CHECK:
report mentions "the embedded `[tool.uv.sources]` examples" — confirm README has no
remaining stale @v2.12.0 install snippet (current install snippets already show @v2.14.0).
(The "CLAUDE.md @v2.12.0" note in the report referred to the TEST project, not ours.)

### conftest-not-fingerprinted — Low
Widening only a `conftest.py` fixture (test file untouched) changes real coverage, but a
plain re-run **reuses stale verdicts** (e.g. 60%) where `--force` gives truth (100%). Tool
PRINTS `updated: …conftest.py (source changed since last run)` — it *detects* the change —
yet reuses anyway with no staleness warning. Repro: cache project (`cases` fixture
`[3]`→`[3,0]`; `first_or(x)=x or 99`, or-default mutant only killable when x=0 tested).
Fix: emit a one-line staleness warning ("cached verdicts may be stale; use --force")
instead of silently reusing. White-box: `stats.py` / `orchestrator.py` (test-file
fingerprint vs reuse, the #130 in-place-edit path).

### WRK-001 — Low, robustness
A worker that dies **during interpreter startup (before the multiprocessing bootstrap
completes)** makes the run **HANG (≥50 s, continual fresh worker respawns)** instead of
aborting. A death slightly later (post-bootstrap, mid-task) aborts cleanly → `run_aborted`
→ exit 1 (validated live, poolcollapse). Realistic trigger: a user env whose
`sitecustomize`/`.pth`/site-packages crashes Python at startup wedges every worker. Fix:
spawn-failure backstop (abort if N consecutive workers die before pulling a task).
White-box: `process/executor.py` (spawn pool / respawn loop). Repro harness:
poolcollapse `sccfg/sitecustomize.py` — daemon thread `os._exit(1)` after 1.2 s delay,
gated on `POOL_COLLAPSE=1` + `--multiprocessing-fork` token (immediate os._exit = the
WRK-001 hang; the 1.2 s delay = the clean mid-task abort).

## TASK 2 — Nextgen operator roadmap + its acceptance harness

Roadmap (in `_docs/nextgen_roadmap/`): 3 profiles — `basic` (1:1 mutmut, planned new
out-of-box default = deliberate behavior change, needs release-note + startup hint),
`advanced` (+7 current extras +6 Tier-A: ROR matrix, number CRCR, negate/force condition,
empty collection literal, match-guard + full 14-sub-mutator regex), `all` (+UOI, AOD,
general statement-removal, member-assign-removal, exception-swap). Regex via `re._parser`,
14 sub-mutators (no `\p{}` in stdlib re → drop UnicodeClassNegation; add group→non-capturing).
Return only →None. 3.6.0 surface backports (profile-independent): pragma block/start-end,
`do_not_mutate_patterns` regex, `@staticmethod`/`@classmethod` mutation (loosen skip at
`mutation.py:245`; keep `@property` skipped). Owner-locked 2026-06-13. **Implementation
is THIS project's job** (the test project only produced the spec).

**Executable acceptance harness `testing/roadmap/` exists ONLY in `_external_tests`**
(LOST on delete unless copied out). It mirrors the opmatrix methodology: one target
construct + one strong kill-test per planned operator. Today (all ops on, no profiles):
**71 mutants / 100% / 14 pytest green**; each kill-test passes trivially now (mutant not
yet generated) and will kill the new mutant once the operator lands. Acceptance per target
= mutant count rises Current→Expected AND score stays 100%. Files: `ROADMAP_SPEC.md`
(Current→Expected tables), `src/roadmap/targets.py` (ror, crcr, negate_cond, force_cond,
coll_list/dict/set/tuple, match_guard, aod_uoi, Counter, guard_raise, Calc@static/class),
`src/roadmap/regex_targets.py` (5 patterns for the 14 sub-mutators),
`tests/test_roadmap.py` (14 strong tests). RESCUED to `_docs/nextgen_roadmap/acceptance_harness/` (see its README_PROVENANCE.md; re-point [tool.uv.sources] at the local tree to exercise operators as they land).

## Test projects (each own venv+config) — final v2.14.0 scores, for reference
Frozen baselines: refproj 80/72.4%, operators 174/6.6%, statuses 15/46.2%, edgecases
35/68.6%, "pfad mit leerzeichen ä"/proj 5/100%. Tier-1+2+3 expansion: opmatrix 126/100%
(operator kill-matrix), syntax314 53/92%, encodings utf8 5/100% (MUT-003), cache (conftest
demo), staging 4/100% (extra_paths+PYTHONPATH), crash (IL-001 + segfault, window 3.0),
poolcollapse (WRK-001/run_aborted), interrupt (Ctrl-C→130), roadmap 71/100% (Task-2 spec).
Note: segfault status NOT live-reproducible on Py3.14 (faulthandler intercepts `_sigsegv`
→ exit 3; deep recursion grows heap frame stack 3.11+ → IL not C-stack overflow) — only
code-confirmed. WER suppression (WIN-001) validated live.

Related: [[fable5_360_findings]] (the INTERNAL audit that produced v2.14.0; this is the
EXTERNAL re-test OF v2.14.0). [[mutation-zeilen-gate-methodik]] for the ≥80% change gate.
