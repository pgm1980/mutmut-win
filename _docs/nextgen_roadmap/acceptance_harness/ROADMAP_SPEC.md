# `roadmap` — executable acceptance spec for mutmut-win's planned operators

This project is a **TDD / acceptance harness** for the operators in
[`../MUTMUT_WIN_OPERATOR_ROADMAP.md`](../MUTMUT_WIN_OPERATOR_ROADMAP.md). Each
planned operator has a **target construct** (`src/roadmap/…`) and a **strong
kill-test** (`tests/test_roadmap.py`)
that will kill the operator's expected mutant **once it is implemented** — and
passed trivially in the original v2.14.0 baseline, because the mutant was not yet generated.

## How the maintainer uses this

1. Use this project in the mutmut-win checkout whose operator behavior is under
   verification (or copy its `src/` + `tests/` there).
2. Run `mutmut-win run --force --profile advanced`; use `--profile all` for the
   aggressive operator tier.
3. **Acceptance per target:** the mutant count rises from *Current* to *Expected*
   **and** the score stays **100 %** (every new mutant killed by the provided
   test). A survivor ⇒ either an operator bug or a genuine equivalent mutant to
   document. A missing count ⇒ operator not (fully) generating.

**Original baseline (v2.14.0, all operators on, no profiles yet): 71 mutants, 71 killed, 100 %, pytest 14 green.** Per-construct baseline counts are the *Current* column below.

**Phase 1 verification (v2.16.0 — profile scaffold, no new operators yet):**
`--profile advanced` (the default) reproduces the baseline exactly — **71 / 71 /
100 %** (behaviour-neutral). `--profile basic` filters down to mutmut's 15 base
operators — **55 / 55 / 100 %** (16 advanced-only mutants correctly dropped). The
*Expected* columns below stay untouched until Phase 2 lands the first real operators.

**Phase 2 verification (v2.17.0 — the first six advanced operators):** `--profile
advanced` now lands #3 (ROR matrix), #15 (number CRCR), #22 (negate), #23 (force),
#38 (collection-empty) and #41 (match-guard). The harness runs **152 / 152 / 100 %**
(pytest 18 green, 0 survivors). The *Expected* column below is a **per-operator**
estimate; with every operator on, the live count is legitimately higher because
operators overlap on a construct and there is no visitor-level dedup:

| Target | Expected (isolated) | Live (all operators) | Why higher |
|---|--:|--:|---|
| `ror` | 6 | **6** | exact — ROR matrix is decoupled from `swap_op` |
| `crcr` | 5 | **5** | exact |
| `negate_cond` | 5 | **7** | + force on the same `if flag` |
| `force_cond` | 8 | **14** | + ROR/CRCR on `x > 0` and the `0` |
| `coll_list` / `coll_set` / `coll_tuple` | 5 | **15** | + CRCR on the inner `1, 2, 3` |
| `coll_dict` | 8 | **14** | + CRCR on the inner values |
| `match_guard` | 10 | **16** | + ROR/CRCR/force on the `x > 0` guard |

Acceptance is **Score 100 %** (every mutant killed), not the isolated counts.
#42 (regex full 14-sub-mutator suite) stays Phase 3.

**Phase 3 verification (v2.18.0 — the full regex suite #42):** the 14 sub-mutators
ship string-based on the class-span tokenizer (`_class_spans`/`_in_class`), NOT the
roadmap's re._parser route (`re` has no `unparse`, so a round-trip emitter would be
the killer risk). The harness's regex targets were moved INTO their functions — a
module-level `_X = re.compile(...)` is never mutated (mutmut-win mutates function
bodies), so before this the regex operator never fired on them. With the patterns
inline, harness `--profile advanced` = **184 / 188 / 97.9 %** (152 in v2.17.0; the
+36 are the regex-pattern mutants). The 4 survivors are genuine equivalents,
documented: `\d+?` / `[a-c]+?` / `(ab)+?` (a lazy `+?` is identical to greedy `+`
under `fullmatch`) and `(ab)*` (returns the same `None` as `(ab)+` for `repeat_ab`).
Per-operator regex mutation is 96-99 % with documented `<` vs `!=` boundary
equivalents (`i+1` is never `> n`). `MAX_MUTATIONS_PER_PATTERN` was raised 5 -> 12 so
the suite can surface on one construct. The `all`-tier aggressive operators (#2 AOD,
#12 UOI, #27/#29 removal, #44 exception-swap) and the 3.6.0 surface backports remain
for a later phase.

**Phase 4 verification (v2.19.0 — the `all`-tier operators + 3.6.0 backports):** the
aggressive `all`-tier operators land — #2 AOD, #44 exception-swap, #27 general-statement
removal (effectful Expr statements: `await`/`yield`/subscript/walrus), #29 member-
assignment removal, #12 UOI (while-negate, arithmetic unary-minus on `Name` operands,
boolean-operand negation; comparison operands EXCLUDED for precedence/equivalent-rate
reasons) — plus the mutmut-3.6.0 surface backports: pragma `block`/`start`-`end`, regex
`do_not_mutate_patterns`, and `@staticmethod` mutation. At `--profile all` the harness
runs **204 / 200 / 98.0 %** (188 in v2.18.0; the +16 are the all-tier + `@staticmethod`
mutants). The 4 survivors are the SAME documented regex `fullmatch` equivalents as
Phase 3 (`\d+?`/`[a-c]+?`/`(ab)+?` lazy ≡ greedy, `(ab)*` ≡ `(ab)+`) — there are NO new
Phase-4 survivors. `@classmethod` is DEFERRED (the class-bound original's `__name__` is
read-only, which the trampoline-lookup codegen cannot set), so `Calc.triple` stays at
0 mutants; `Calc.double` (`@staticmethod`) mutates and is killed by
`test_calc_static_class`. `all` now strictly exceeds `advanced` (basic 15 / advanced 34
/ all 41 operators).

## Acceptance table — `advanced` profile

| # | Operator | Target (`src/roadmap/`) | Current | Expected (Δ) | Killed by |
|---|---|---|--:|--:|---|
| 3 | ROR full matrix (`<`→`>,>=,==,!=`) | `targets.ror` | 2 | **6** (+4) | `test_ror` |
| 15 | Number-literal CRCR (`7`→`0,1,-1,-7`) | `targets.crcr` | 1 | **5** (+4) | `test_crcr` |
| 22 | Negate whole condition (`if flag`→`if not flag`) | `targets.negate_cond` | 4 | **5** (+1) | `test_negate_cond` |
| 23 | Force conditional (`if x>0`→`if True/False`) | `targets.force_cond` | 6 | **8** (+2) | `test_force_cond` |
| 38 | Empty list literal | `targets.coll_list` | 4 | **5** (+1) | `test_collections` |
| 38 | Empty dict literal | `targets.coll_dict` | 7 | **8** (+1) | `test_collections` |
| 38 | Empty set literal | `targets.coll_set` | 4 | **5** (+1) | `test_collections` |
| 38 | Empty tuple literal | `targets.coll_tuple` | 4 | **5** (+1) | `test_collections` |
| 41 | Match-guard (`case x if g`→guard `True/False`) | `targets.match_guard` | 8 | **10** (+2) | `test_match_guard` |
| 42 | Regex suite (14 sub-mutators) | `regex_targets.*` | 19 total | **> 19** (see below) | `test_regex_*` |

## Acceptance table — `all` profile

| # | Operator | Target | Current | Expected (Δ) | Killed by |
|---|---|---|--:|--:|---|
| 2 | AOD (`a+b`→`a`/`b`) | `targets.aod_uoi` | 2 | **4** (+2) | `test_aod_uoi` |
| 12 | UOI (insert unary: `-a`, `not a`, …) | `targets.aod_uoi` | (shared) | +N (volume-gated) | `test_aod_uoi` |
| 29 | Member/attr-assignment removal | `targets.Counter.__init__` | 2 | **3** (+1) | `test_counter` |
| 44 | Exception swap (`raise ValueError`→`raise TypeError`) | `targets.guard_raise` | 7 | **8** (+1) | `test_guard_raise` |

## Acceptance — surface backport (mutmut 3.6.0)

| Backport | Target | Current | Expected | Killed by |
|---|---|--:|--:|---|
| `@staticmethod` mutation (`@classmethod` deferred) | `targets.Calc` | **0** (decorated → skipped) | `Calc.double` (`@staticmethod`) mutates; `Calc.triple` (`@classmethod`) stays **0** (deferred); `@property` stays 0 | `test_calc_static_class` |

The other two surface backports are skip behaviors that shipped in v2.19.0 and
remain covered by dedicated main-repository regressions rather than additional
targets in this standalone harness:

- **Pragma `block` / `start`-`end`:** `# pragma: no mutate block` and inclusive
  `start`/`end` regions are implemented; the dedicated mutation regressions verify
  that excluded regions generate no mutants.
- **`do_not_mutate_patterns` (regex):** the configuration key is implemented and
  excludes matching simple names. v2.20.0 additionally verifies qualified
  `Class.method` matches; dedicated configuration and mutation regressions cover
  both forms.

## Regex sub-mutator coverage (#42) — which target exercises what

Current mutmut-win already has a *lean* regex engine; the goal is the full
14-sub-mutator set (stdlib `re` has no `\p{}`, so Stryker's UnicodeClassNegation
is dropped; `Group→non-capturing` is added). Targets and the sub-mutators they
should each surface:

| Target (`regex_targets.`) | Pattern | Sub-mutators it should exercise |
|---|---|---|
| `all_digits` | `\d+` | shorthand `\d`→`\D` / →`[\d\D]` / →literal `d`; quantifier `+`→removal / `*` / `{n,}` |
| `only_abc` | `[a-c]+` | char-class range ±1, negation `[^a-c]`, →`[\w\W]` (to-any); (list form `[abc]` for child-removal) |
| `has_foo_prefix` | `^foo` | anchor removal `^` |
| `repeat_ab` | `(ab)+` | **group→non-capturing** (killed via `.group(1)`), quantifier change |
| `foo_before_bar` | `foo(?=bar)` | **look-around flip** `(?=)`→`(?!)` |

Acceptance: after the full suite lands, each applicable sub-mutator appears for
the relevant target and is killed by `test_regex_*`. (Some sub-mutators are
equivalent on a given pattern — e.g. `+`→`*` on `(ab)+` under `fullmatch` — and
may legitimately survive; document those rather than forcing a kill.)

## Notes

- Targets deliberately mirror the `opmatrix` methodology (one construct + one
  strong test per operator) so the maintainer's CI can assert **100 % kill** on
  this project as the operators land.
- Boundary asserts (`force_cond(1)`, `match_guard(1)`, `guard_raise(0)`) exist
  to kill the *current* number/relational mutants so today's baseline is a clean
  100 % — the same gap-closing discipline used in `opmatrix`.
</content>
