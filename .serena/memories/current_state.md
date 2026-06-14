# Current State — v2.18.0 (regex suite shipped)

LIVE state memory; `project_overview` / `codebase_structure` carry the deeper
detail (their headers point here), `sprint_36_progress` is archived history.

## Release status
- **Current release: v2.18.0** (GitHub release live). Project back in the
  documented development pause (0 open issues / backlog).
- History since v2.14.0: v2.16.0 (Phase 1: operator-profile system), v2.17.0
  (Phase 2: six advanced operators), v2.18.0 (Phase 3: full regex suite).
- Last gates: full suite 1313 passed / 5 skipped, ruff 0 (bare `.`), mypy 14
  baseline, Semgrep clean.

## Operator profiles (since v2.16.0)
- `Profile(IntEnum)` BASIC=0 / ADVANCED=1 / ALL=2 in constants.py. Registry
  `node_mutation.mutation_operators` = `(node_type, operator, Profile)` 3-tuples;
  `operators_for_profile(active)` filters `prof <= active`. **advanced is DEFAULT**
  (34 entries / 29 unique funcs); basic 15; all == advanced (all-tier not built).
- advanced is NOT behaviour-neutral vs v2.14 (Phase 2 + Phase 3 added operators).

## Phase 2 advanced operators (v2.17.0, node_mutation.py)
#3 operator_relational_matrix (ComparisonTarget), #15 operator_number_crcr
(Integer/Float), #22 operator_negate_condition + #23 operator_force_condition
(If), #38 operator_collection_empty (List/Tuple/Set/Dict), #41 operator_match_guard
(MatchCase). All decoupled (no visitor dedup).

## Phase 3 regex suite (v2.18.0, regex_mutation.py) — DONE
String-based on a class-span tokenizer (`_class_spans`/`_in_class`), NOT re._parser
(no unparse -> emitter round-trip risk). The 14 sub-mutators:
- #1 anchors (_mutate_anchors): ^ $ \A \Z \b \B removal.
- #2-6 quantifiers (_mutate_quantifiers + _brace_variants): removal, +<->* swap,
  short->range (?->{1}, +->{2,}), reluctant greedy->lazy, {n,m} ±1.
- #11-13 shorthands (_mutate_char_classes + _shorthand_positions): negation
  (swapcase), nullify (\d->d), to-any (\d->[\d\D], outside classes only).
- #7-10 char-classes (_mutate_classes + _class_members + _RANGE_RE): negation
  toggle, child-removal, range ±1, to-any.
- #14/+15 groups (_mutate_groups): look-around flip, capturing->non-capturing.
mutate_regex_pattern orchestrates; re.compile + seen-set gate; MAX_MUTATIONS=12.
operator_regex (node_mutation, ADVANCED) calls it on cst.Call re.* patterns.
Harness 184/188 (4 documented fullmatch equivalents). Commits: 6806434, 5e3f098,
367c90d, bbfabc2, aaf4b13, 85be62d; merge aa3bf75.

## Open (later phases)
`all`-tier aggressive operators (#2 AOD, #12 UOI, #27/#29 removal, #44 exception
swap) + mutmut-3.6.0 surface backports (@staticmethod/@classmethod, pragma block,
do_not_mutate_patterns). Roadmap §4/§5/§6, ROADMAP_SPEC `all`-profile table.

## Recurring lessons
- Regex/tokenizer survivor pattern: scan-start/boundary index mutants are
  documented equivalents (`<` vs `!=` where i+1 is never > n); trailing-backslash
  tests kill the IndexError variants; test index-heavy helpers DIRECTLY (exact
  units), not only via the public function.
- Harness gotcha: a target's regex pattern must live INSIDE its function — a
  module-level `_X = re.compile(...)` is never mutated (function-body mutation only).
- e2e test strategy for new operators: auto-memory `phase2-operator-e2e-profilschichtung`
  (layered invariants + --profile basic for the pipeline snapshot). Count pins
  unchanged through Phase 3 (no fixture uses regex on mutated lines): my_lib 129,
  config 30, type_checking 17, py3_14 10, covered 113.
- Host: `uv run --frozen` + `UV_SYSTEM_CERTS=1`; Semgrep host CLI; targeted gate
  via fully-qualified names from `.mutmut-cache/mutmut-cache.db`. acceptance_harness
  local run: pin `[tool.uv.sources] mutmut-win = { path = "../../.." }`, `uv sync
  --directory ...`, `mutmut-win run --profile advanced --force`; re-pin to @vX.Y.Z,
  revert uv.lock afterwards.
