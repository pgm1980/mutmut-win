# `roadmap` — executable acceptance spec for mutmut-win's planned operators

This project is a **TDD / acceptance harness** for the operators in
`reporting/MUTMUT_WIN_OPERATOR_ROADMAP.md`. Each planned operator has a **target
construct** (`src/roadmap/…`) and a **strong kill-test** (`tests/test_roadmap.py`)
that will kill the operator's expected mutant **once it is implemented** — and
passes trivially today (v2.14.0), because the mutant is not yet generated.

## How the maintainer uses this

1. Drop this project (or its `src/` + `tests/`) into a mutmut-win checkout that
   has the new operators implemented.
2. `mutmut-win run --force` (with `--profile advanced` / `--profile all` once
   the profile system exists).
3. **Acceptance per target:** the mutant count rises from *Current* to *Expected*
   **and** the score stays **100 %** (every new mutant killed by the provided
   test). A survivor ⇒ either an operator bug or a genuine equivalent mutant to
   document. A missing count ⇒ operator not (fully) generating.

**Baseline today (v2.14.0, all operators on, no profiles yet): 71 mutants, 71 killed, 100 %, pytest 14 green.** Per-construct current counts are the *Current* column below.

**Phase 1 verification (v2.16.0 — profile scaffold, no new operators yet):**
`--profile advanced` (the default) reproduces the baseline exactly — **71 / 71 /
100 %** (behaviour-neutral). `--profile basic` filters down to mutmut's 15 base
operators — **55 / 55 / 100 %** (16 advanced-only mutants correctly dropped). The
*Expected* columns below stay untouched until Phase 2 lands the first real operators.

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
| `@staticmethod` / `@classmethod` mutation | `targets.Calc` | **0** (decorated → skipped) | **≈6** (double+triple mutated; `@property` stays 0) | `test_calc_static_class` |

The other two surface backports are skip-behaviors best tested with dedicated
constructs (ready to add, not wired live to keep this baseline clean):

- **Pragma `block` / `start`-`end`:** add a function with `# pragma: no mutate block` (or a `start`/`end` region). Acceptance: that region's mutant count drops to **0** after the backport (today the block-pragma is unrecognized, so the region is still mutated).
- **`do_not_mutate_patterns` (regex):** add `do_not_mutate_patterns = ["targets\\.crcr"]` (say) to `[tool.mutmut]` + a matching target. Acceptance: matching constructs yield **0** mutants after the backport. (Not added now: the unknown key would warn on v2.14.0.)

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
