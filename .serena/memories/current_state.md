# Current State — v2.19.0 (Phase 4 complete: all-tier operators + 3.6.0 backports)

LIVE state memory; project_overview/codebase_structure carry deeper detail,
sprint_36_progress is archived.

## Release status
- **Current release: v2.19.0** (Phase 4). History: v2.16 (profiles), v2.17
  (Phase 2: 6 advanced ops), v2.18 (Phase 3: regex suite), v2.19 (Phase 4).
- Back in the documented development pause after v2.19.0.
- Last gates: full suite 1397 passed / 5 skipped, ruff 0, mypy 14 baseline,
  import-linter KEPT, Semgrep 0, acceptance_harness 204/200/98% (4 documented
  regex equivalents, NO new Phase-4 survivors).

## Operator profiles
- Registry node_mutation.mutation_operators = (node_type, operator, Profile).
- Counts: **basic 15, advanced 34, all 41**. `all` strictly exceeds `advanced`.

## Phase 4 shipped (v2.19.0) — node_mutation.py operators + mutation.py backports
- AOD (#2 operator_aod), exception-swap (#44 operator_exception_swap).
- statement-removal (#27 operator_statement_removal, allow-list Await/Yield/
  Subscript/NamedExpr), member-assignment-removal (#29).
- UOI (#12): operator_uoi_negate_while / _minus_operand / _negate_boolean_operand
  (comparison operands EXCLUDED by ToT).
- Backports: pragma block/start-end (pragma_no_mutate_lines + helpers);
  do_not_mutate_patterns (config regex -> _skip_node_and_children, threaded via
  the active_profile pool-tuple chain); @staticmethod mutation (_is_static_only +
  create_trampoline_wrapper static dispatch). @classmethod DEFERRED (class-bound
  __name__ read-only).

## Phases 1-3 (recap)
v2.16 profile system; v2.17 #3 ROR / #15 CRCR / #22 negate / #23 force / #38
collection-empty / #41 match-guard; v2.18 14-sub-mutator regex suite
(regex_mutation.py, string-based class-span tokenizer).

## Reusable lessons (verified across Phase 4)
- Per-operator gate: mutmut-win run --paths-to-mutate <file> --tests-dir <unit>
  --profile all --force "*operator_X*" (fnmatch via match_mutant_names).
- @staticmethod mutation is a SURFACE change (not profile-tagged) -> expands
  basic/advanced/all alike; advanced e2e pins NOT frozen from v2.19 on. my_lib
  Point.from_coords gives advanced 129->140 / all 163->174; the 3.5.0 snapshot
  skipped it -> _assert_profile_layered has a w5_static_prefixes allowance.
- e2e advanced/all pins: my_lib 140/174, config 30/40, type_checking 17/20,
  py3_14 10/14, covered 113/127.
- libcst renders verbatim -> inserted unary in operand position needs explicit
  parens; opmatrix tests assert the EXACT rendered string.
- SimpleStatementLine-removal scaffold: 2 inherent equivalents/op.
- Engine-self-mutation coverage gap: mutation-testing create_trampoline_wrapper
  via mutate_file_contents under-credits kills -> verify wrapper changes by EXEC.
- Decorator-skipped methods (@field_validator/@classmethod/@property) produce 0
  mutants -> cover by direct tests.
- mypy 14 baseline. Commit -m: NO backticks (shell command-substitution).
- acceptance_harness local run: pin [tool.uv.sources] mutmut-win = { path =
  "../../.." , editable = true }, then `uv sync --directory <h> --native-tls`
  (Corporate TLS) + `uv run --directory <h> mutmut-win run --profile all --force
  --no-progress`; re-pin to git rev v2.19.0, revert <h>/uv.lock. `uv sync` on the
  MAIN repo drops dev extras -> always `uv sync --all-extras --all-groups`.

## Open / next
Development pause (0 issues / backlog). Future: @classmethod mutation (trampoline-
lookup __func__.__name__), the two unwired backport harness targets (pragma /
do_not_mutate), wrapper-codegen legacy coverage debt (multi-param self-index).
