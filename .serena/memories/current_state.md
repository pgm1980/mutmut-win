# Current State — Sprint 39, Windows/CPython-3.14.7 follow-up

<!-- PUBLICATION_STATE_START -->
<!-- PUBLICATION_STATE: external-live-check-required -->
Publication status for v2.21.1 is external mutable state. These immutable bytes assert neither presence nor absence; verify the exact annotated tag and matching GitHub release before use.
<!-- PUBLICATION_STATE_END -->

LIVE state memory; project_overview/codebase_structure carry deeper detail,
sprint_36_progress is archived.

<!-- LIVE_STATE_START -->

<!-- RELEASE_PHASE: in_progress -->
<!-- RELEASE_PHASE_STATUS: implementation-and-final-gates-open -->
<!-- RELEASE_TARGET: v2.21.1 -->
<!-- RELEASE_BRANCH: `fix/v2.21.1-windows314` -->
<!-- RELEASE_ROADMAP: bug_reporting/BUGFIXUNG_ROADMAP.md -->
<!-- RELEASE_PUBLICATION_AUTHORITY: canonical-external-block -->

<!-- LIVE_STATE_END -->

<!-- ARCHIVE_START -->

## Archived v2.20.0 state

- **Previous release: v2.20.0** (external-QA hardening on Phase 4). History:
  v2.16 (profiles), v2.17 (Phase 2), v2.18 (Phase 3 regex), v2.19.0 (Phase 4
  all-tier + backports), v2.19.1 (robustness patch), v2.20.0 (WRK-002 +
  qualified do_not_mutate).
- The project returned to the documented development pause after v2.20.0.
- **v2.20.0 fixes (the last two open items from the external v2.19.0 re-test)**:
  WRK-002 — the staging phase used multiprocessing.Pool.imap_unordered (no
  broken-worker detection), so a worker dying at interpreter bootstrap (a crashing
  sitecustomize/.pth/site-packages that os._exit's before the mp child connects)
  hung the whole run forever (>80s; the WRK-001 SpawnPoolExecutor startup watchdog
  is never reached because staging blocks first). Fix: _generate_mutants uses
  concurrent.futures.ProcessPoolExecutor (spawn ctx) -> management thread raises
  BrokenProcessPool (~0.3s) -> clean OrchestratorError (exit 1); pool.map also
  restores deterministic ordering (we list() everything anyway). do_not_mutate_
  patterns now matches the QUALIFIED Class.method name too: MutationVisitor keeps a
  class-name stack (on_visit push ClassDef / on_leave pop), matched as qualified OR
  simple (additive, backward compatible). @staticmethod strict gating (solely-
  @staticmethod via _is_static_only) documented as BY-DESIGN in the install guide
  (Wichtige Hinweise) — no code change; @classmethod stays deferred.
- **v2.20.0 changed-line mutation**: WRK-002 safety-net mutants (raise->pass,
  msg=None, msg-string segments, OrchestratorError(None), list()-drop) **11/11
  killed** — but ONLY via a wrk002-ONLY gate. The tests/unit-wide stats run does
  NOT map a test that calls _generate_mutants directly with a mock (engine-self-
  mutation coverage gap, same as W5 wrapper-self-gate). Equivalents: max_workers=
  None / mp_context=None / get_context(None) == spawn-default on Windows; worker
  count does not change generated mutants; `> 1` is the pre-existing legacy line.
  Test hardened: lazy _BrokenPool.map (raises on iteration like real PPE.map ->
  pins the load-bearing list() inside the try) + exact-message assertion (str(exc)
  == _EXPECTED_MSG, kills every msg/raise mutation). qualified-name new visitor
  lines (qualified-OR, on_visit push, on_leave pop) 100% killed; the 23 residual
  _skip_node_and_children survivors are the same W4 legacy class (never-mutate gate
  + annotation/param-default/@staticmethod-relaxation/decorator skips).
- **v2.19.1 fixes** (recap): CACHE-001 (corrupt .mutmut-cache DB -> CorruptCacheError
  clean message via db.create_db + cli._load_results_or_exit; run --force recovers);
  setup.cfg parity for mutation_profile + do_not_mutate_patterns; dedup regression
  guard. create_db migration-coverage gap RESOLVED (merge e30b766, 66.1%->94.9%).
- Last gates: full suite **1419 passed / 5 skipped**, ruff 0, mypy 14 baseline,
  import-linter KEPT, Semgrep 0 (changed files). No new deps (concurrent.futures is
  stdlib) -> pip-audit unchanged. v2.19.0 acceptance_harness 204/200/98% unchanged
  (no operator/profile behaviour changed in v2.20.0).

### Operator profiles
- Registry node_mutation.mutation_operators = (node_type, operator, Profile).
- Counts: **basic 15, advanced 34, all 41**. `all` strictly exceeds `advanced`.

### Phase 4 shipped (v2.19.0) — node_mutation.py operators + mutation.py backports
- AOD (#2 operator_aod), exception-swap (#44 operator_exception_swap).
- statement-removal (#27 operator_statement_removal, allow-list Await/Yield/
  Subscript/NamedExpr), member-assignment-removal (#29).
- UOI (#12): operator_uoi_negate_while / _minus_operand / _negate_boolean_operand
  (comparison operands EXCLUDED by ToT).
- Backports: pragma block/start-end (pragma_no_mutate_lines + helpers);
  do_not_mutate_patterns (config regex -> _skip_node_and_children, threaded via
  the active_profile pool-tuple chain; v2.20.0 added qualified Class.method match);
  @staticmethod mutation (_is_static_only + create_trampoline_wrapper static
  dispatch). @classmethod DEFERRED (class-bound __name__ read-only).

### Phases 1-3 (recap)
v2.16 profile system; v2.17 #3 ROR / #15 CRCR / #22 negate / #23 force / #38
collection-empty / #41 match-guard; v2.18 14-sub-mutator regex suite
(regex_mutation.py, string-based class-span tokenizer).

### Reusable lessons (verified across Phase 4 + v2.20.0)
- Per-operator gate: mutmut-win run --paths-to-mutate <file> --tests-dir <unit>
  --profile all --force "*operator_X*" (fnmatch via match_mutant_names).
- **Engine-self-mutation coverage gap (now seen twice)**: a test that drives an
  orchestrator method (_generate_mutants) or the wrapper codegen DIRECTLY with a
  mock is NOT mapped as a covering test in the tests/unit-wide stats run, so its
  kills are under-credited. HONEST proof = re-gate the specific mutants with that
  test as the ONLY --tests-dir (forces the mapping). W5 did this for the wrapper.
- Mocking a lazy stdlib API (ProcessPoolExecutor.map) EAGERLY hides list()/
  iteration-timing mutants; make the mock lazy (generator raising on iteration) so
  the production list(...) shows as load-bearing.
- @staticmethod mutation is a SURFACE change (not profile-tagged) -> expands
  basic/advanced/all alike; advanced e2e pins NOT frozen from v2.19 on. my_lib
  Point.from_coords gives advanced 129->140 / all 163->174; _assert_profile_layered
  has a w5_static_prefixes allowance.
- e2e advanced/all pins: my_lib 140/174, config 30/40, type_checking 17/20,
  py3_14 10/14, covered 113/127.
- libcst renders verbatim -> inserted unary in operand position needs explicit
  parens; opmatrix tests assert the EXACT rendered string.
- SimpleStatementLine-removal scaffold: 2 inherent equivalents/op.
- Decorator-skipped methods (@field_validator/@classmethod/@property) produce 0
  mutants -> cover by direct tests.
- mypy 14 baseline. Commit -m: NO backticks (shell command-substitution).
  git merge does NOT support -F - (stdin) like git commit; use -m flags or -F file.
- acceptance_harness local run: pin [tool.uv.sources] mutmut-win = { path =
  "../../.." , editable = true }, then `uv sync --directory <h> --native-tls` +
  `uv run --directory <h> mutmut-win run --profile all --force --no-progress`;
  re-pin to git rev, revert <h>/uv.lock. `uv sync` on the MAIN repo drops dev
  extras -> always `uv sync --all-extras --all-groups`. `uv lock` (not sync)
  updates uv.lock for a version bump without the TLS-sensitive editable rebuild.

### Archived open / next at v2.20.0
Development pause (0 issues / backlog). Future: @classmethod mutation (trampoline-
lookup __func__.__name__), optional standalone-harness targets for the two
already-regression-tested skip backports (pragma / do_not_mutate), and
wrapper-codegen legacy coverage debt (multi-param self-index).

<!-- ARCHIVE_END -->
