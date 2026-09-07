# mutmut-win Operator Roadmap (Phase 4 deliverable)

*Companion to `MUTATION_OPERATOR_MATRIX.md`. Turns the matrix gaps into a concrete, profile-gated implementation plan with per-operator CST sketches. Scope decisions are the project owner's (2026-06-13): `→None` return is enough (no shape-return), full 15-mutator regex suite, UOI in, 3-profile model, and the mutmut-3.6.0 surface backports are in.*

**Binding runtime contract:** Windows with exactly CPython 3.14.7; other Python
versions, implementations, and operating systems are unsupported.

All file:line references are to `_codebase_v2140/mutmut_win/`.

---

## 1. The 3-profile model

Mirrors PIT's mutator groups and Stryker.NET-X's `MutationProfile` (Defaults/Stronger/All). A single config key + CLI flag selects the active set:

```toml
[tool.mutmut]
mutation_profile = "advanced"   # basic | advanced | all
```
```bash
mutmut-win run --profile all
```

| Profile (name) | = | Intent |
|---|---|---|
| **`basic`** (a.k.a. "default/standard": 1:1 mutmut) | the 15 mutmut base operators only | drop-in mutmut parity; smallest, lowest-noise surface |
| **`advanced`** | `basic` + the 7 current mutmut-win extras + the safe Tier-A additions | the recommended everyday set |
| **`all`** | `advanced` + the aggressive operators (high mutant volume / higher equivalent-mutant risk) | maximum thoroughness for audits |

> **Default-profile decision (REVISED 2026-06-14, supersedes the original 2026-06-13 lock): the out-of-box profile is `advanced`.** That is mutmut-win's historical operator set (mutmut base + the 9 extras), so making it the default is **behaviour-neutral** — existing users see the same mutants as before. `basic` is the opt-in for strict 1:1 mutmut parity (the 15 base operators only); `all` is for audits.
> ✅ **No breaking change.** Because `advanced` == today's behaviour, no "pass `--profile advanced` to keep current behaviour" migration is needed. The original §1 mitigations (BREAKING note, `basic`-default startup warning, major bump) are therefore void. What ships instead: (1) a normal release note announcing the new `--profile` / `[tool.mutmut].mutation_profile` option; (2) an informational once-per-run line (`profile=<name> — N operators active`; no warning tone); (3) a **minor** version bump (additive feature). Delivered in Phase 1, v2.16.0.

### Mechanism (small, localized change)

`node_mutation.py:641` currently exposes one flat `mutation_operators` list. Add a profile tag and let the visitor filter:

```python
# node_mutation.py — tag each operator with the LOWEST profile that includes it
class Profile(IntEnum):
    BASIC = 0; ADVANCED = 1; ALL = 2

mutation_operators: list[tuple[type[cst.CSTNode], Operator, Profile]] = [
    (cst.BaseNumber, operator_number,            Profile.BASIC),
    ...
    (cst.Call,       operator_regex,             Profile.ADVANCED),
    (cst.ComparisonTarget, operator_relational_matrix, Profile.ADVANCED),
    (cst.BaseExpression,   operator_unary_insertion,   Profile.ALL),
    ...
]
```
`MutationVisitor.__init__` (mutation.py:130) takes the active `Profile` and keeps only entries with `tag <= active`. One filter line; everything else is unchanged.

---

## 2. Profile → operator assignment (master table)

| Operator | Class (matrix #) | Profile | Status |
|---|---|---|---|
| number (+1), string, name, assignment, aug-assign→plain, swap_op (arith/rel-boundary/eq/logic/bitwise/shift), keywords (is/in/break/continue), unary-removal, dict-args, arg-removal, string-method swaps, lambda, match-arm-delete | 1,4,5,6,7,8,9,10,11,16,17,24*,25,28,30,31,34,40 | **basic** | exists (mutmut base) |
| regex (**full 14-suite ✅ v2.18.0**), return_value (→None), conditional-expr neutralize, void-call removal, raise removal, collection-neutralize, comprehension-filter, math-methods, or-default | 19,24,26,35,36,37,39,42,43,18 | **advanced** | all exist; regex full 14-suite ✅ v2.18.0 |
| **ROR full matrix** | 3 | **advanced** | ✅ v2.17.0 |
| **number-literal CRCR (0/1/-1/-n)** | 15 | **advanced** | ✅ v2.17.0 |
| **negate whole condition** | 22 | **advanced** | ✅ v2.17.0 |
| **force conditional True/False** | 23 | **advanced** | ✅ v2.17.0 |
| **collection-literal emptying** | 38 | **advanced** | ✅ v2.17.0 |
| **match-guard True/False** | 41 | **advanced** | ✅ v2.17.0 |
| **UOI (unary operator insertion)** | 12 | **all** | ✅ v2.19.0 (while/arith-minus/boolean-operand; comparison operands excluded) |
| **AOD (arith operand deletion)** | 2 | **all** | ✅ v2.19.0 |
| **general statement removal** | 27 | **all** | ✅ v2.19.0 |
| **member/attr assignment removal** | 29 | **all** | ✅ v2.19.0 |
| **exception swap** | 44 | **all** | ✅ v2.19.0 |
| ~~constructor→None / naked-receiver / arg-propagation~~ | 53,32,33 | — | **EXCLUDED** (owner decision: too dynamic-typing-hard, high equivalent-mutant rate) |

*match-arm-delete is `operator_match`, already present.

---

## 3. CST implementation sketches — `advanced` additions

### 3.1 ROR full matrix (#3)
Today `_operator_mapping` maps each comparison to **one** target. Add a multi-target table and a dedicated operator; dedup (#132 seen-set) absorbs the overlap with the base boundary/equality swaps.
```python
_ror_matrix = {
    cst.LessThan:         (cst.LessThanEqual, cst.GreaterThan, cst.GreaterThanEqual, cst.Equal, cst.NotEqual),
    cst.LessThanEqual:    (cst.LessThan, cst.GreaterThan, cst.GreaterThanEqual, cst.Equal, cst.NotEqual),
    cst.GreaterThan:      (cst.GreaterThanEqual, cst.LessThan, cst.LessThanEqual, cst.Equal, cst.NotEqual),
    cst.GreaterThanEqual: (cst.GreaterThan, cst.LessThan, cst.LessThanEqual, cst.Equal, cst.NotEqual),
}
def operator_relational_matrix(node: cst.ComparisonTarget):
    for new_op in _ror_matrix.get(type(node.operator), ()):
        yield node.with_changes(operator=new_op())
```
Register `(cst.ComparisonTarget, operator_relational_matrix, ADVANCED)`. (`==`/`!=` already fully covered by base swap.)

### 3.2 Number-literal CRCR (#15)
Augment `operator_number` (node_mutation.py:22) under `advanced`. **libcst caveat:** a negative literal is a `UnaryOperation(Minus, Integer)`, *not* an `Integer("-5")` — emit it as such.
```python
def operator_number_crcr(node):
    if isinstance(node, cst.Integer):
        orig = node.evaluated_value
        cands = {0, 1, -1, -orig}
        for v in cands:
            if v == orig: continue
            yield (cst.Integer(str(v)) if v >= 0
                   else cst.UnaryOperation(cst.Minus(), cst.Integer(str(-v))))
    # cst.Float analogous with {0.0, 1.0, -orig}, math.isfinite guard (reuse node_mutation.py:31)
```

### 3.3 Negate whole condition (#22)
```python
def operator_negate_condition(node):           # node: cst.If | cst.While
    t = node.test
    if isinstance(t, cst.UnaryOperation) and isinstance(t.operator, cst.Not):
        return                                  # `if not x` -> unary-removal already covers it
    yield node.with_changes(
        test=cst.UnaryOperation(cst.Not(), _parenthesize(t)))  # reuse _safe_unwrap's paren logic
```
Register for `cst.If`, `cst.While`. Overlap with `==`↔`!=` is fine (dedup).

### 3.4 Force conditional True/False (#23) — PIT REMOVE_CONDITIONALS
```python
def operator_force_condition(node):            # cst.If | cst.While
    yield node.with_changes(test=cst.Name("True"))
    yield node.with_changes(test=cst.Name("False"))
```
`while True:` is a legitimate mutant — mutmut-win's IL detector will classify it as `killed_by_infinite_loop` (desired). Optionally skip forcing `while`→`True` if you want to avoid guaranteed-IL noise.

### 3.5 Collection-literal emptying (#38)
```python
def operator_empty_collection(node):           # cst.List | cst.Set | cst.Dict | cst.Tuple
    if not node.elements:
        return
    yield node.with_changes(elements=[])
```
Register all four. Note `(a,)`→`()` and `[x]`→`[]` are exactly the high-value cases; bare parenthesized exprs aren't `Tuple` nodes, so no false hits.

### 3.6 Match-guard True/False (#41) — Python 3.10+
```python
def operator_match_guard(node):                # cst.MatchCase
    if node.guard is None:
        return
    yield node.with_changes(guard=cst.Name("True"))
    yield node.with_changes(guard=cst.Name("False"))
```

### 3.7 Full regex suite (#42) — historische Planungsgrundlage

Die ursprüngliche Roadmap empfahl, `regex_mutation.mutate_regex_pattern()` über
die private CPython-API `re._parser.parse()` auf die **Stryker-15-Mutator**-
Oberfläche zu erweitern. Diese Idee wurde nicht implementiert und ist durch die
in v2.18.0 ausgelieferte stringbasierte Class-Span-Tokenizer-Lösung überholt:
`re._parser` besitzt keinen stabilen Roundtrip-Emitter. Die folgende Tabelle
bleibt als historischer Scope-Katalog erhalten, nicht als aktuelle Parser-
Entscheidung. Jede tatsächlich erzeugte Kandidatenform durchläuft weiterhin das
bestehende `re.compile()`-Validierungsgate.

| # | Sub-mutator | Example | Python-`re` note |
|---|---|---|---|
| 1 | Anchor removal | `^abc$`→`abc$` | `^ $ \A \Z \b \B` |
| 2 | Quantifier removal | `a+`→`a` | `* + ? {n,m}` |
| 3 | Quantifier quantity ±1 | `a{2,4}`→`{1,4}`,`{3,4}`,`{2,3}`,`{2,5}` | validity-filtered |
| 4 | Quantifier unlimited ±1 | `a{2,}`→`{1,}`,`{3,}` | |
| 5 | Quantifier short→range | `a?`→`a{0,1}`… | normalize then ±1 |
| 6 | Reluctant addition | `a+`→`a+?` | greedy→lazy |
| 7 | Char-class negation | `[abc]`↔`[^abc]` | |
| 8 | Char-class child removal | `[abc]`→`[bc]`/`[ac]`/`[ab]` | |
| 9 | Char-class range ±1 | `[a-z]`→`[b-z]`/`[a-y]` | |
| 10 | Char-class → any | `[abc]`→`[\w\W]` | |
| 11 | Shorthand negation | `\d`↔`\D`, `\w`↔`\W`, `\s`↔`\S` | |
| 12 | Shorthand nullification | `\d`→`d` | |
| 13 | Shorthand → any | `\d`→`[\d\D]` | |
| 14 | Look-around flip | `(?=)`↔`(?!)`, `(?<=)`↔`(?<!)` | |
| ~~15~~ | ~~Unicode `\p{}` negation~~ | — | **DROP: stdlib `re` has no `\p{}`** (only the 3rd-party `regex` module) |
| +15 | Group→non-capturing | `(abc)`→`(?:abc)` | Python supports `(?:…)` |

→ **14 of Stryker's 15 apply** to stdlib `re` (drop `\p{}`-unicode; keep group→non-capturing). Validate every candidate with `re.compile`; silently drop non-compiling ones (mutmut-win already does this).

---

## 4. CST sketches — `all` additions (aggressive)

- **UOI (#12)** — insert a unary op. Dynamic typing means no static guard, so **scope conservatively to limit explosion**: insert `not` only on the *test* of `if`/`while` and on operands of `and`/`or`/comparisons; insert unary `-` only on numeric `Integer`/`Float`/`Name` operands inside arithmetic `BinaryOperation`s. Each insertion = `cst.UnaryOperation(cst.Not()/cst.Minus(), _parenthesize(expr))`. Gate **all** (Stryker-X gates it All-only for the same reason). Expect high mutant counts + some equivalents.
- **AOD (#2)** — `operator_aod(node: cst.BinaryOperation)`: `yield _safe_unwrap(node.left); yield _safe_unwrap(node.right)` (reuse node_mutation.py:213). Noisy; `all`.
- **General statement removal (#27)** — generalize `operator_void_call_removal` (node_mutation.py:551) to any `SimpleStatementLine` whose body is a single `Expr` (not just `Call`) → `pass`. Keep the existing exclusion list. `all`.
- **Member/attr-assignment removal (#29)** — `self.x = v` / `obj.attr = v` → drop the statement (distinct from base `a = None`). Match `Assign` whose single target is an `Attribute`. `all`.
- **Exception swap (#44)** — `raise ValueError(...)`→`raise TypeError(...)` via a small Python exception-pair table (`ValueError↔TypeError`, `KeyError↔IndexError`, `OSError↔RuntimeError`, …). Only inside `Raise(Call(Name=<known exc>))`. `all`.

**Explicitly EXCLUDED from `all` (owner decision 2026-06-13):** constructor→None (#53), naked-receiver (#32), argument-propagation (#33) — all require static type/shape matching that Python's dynamic typing can't provide reliably, yielding high false-positive/equivalent-mutant rates. (Remove-`await` (#54) is also not in scope for now; trivially addable later if async coverage becomes a priority.)

---

## 5. mutmut-3.6.0 surface backports (NOT operators — but in scope)

| Feature | 3.6.0 behavior | mutmut-win integration point | Sketch |
|---|---|---|---|
| **Pragma `block` / `start`-`end`** | region-level skip beyond single line | `pragma_no_mutate_lines()` (mutation.py:560) already returns `ignored_lines`; visitor consumes it (mutation.py:197) | Extend the scanner: `# pragma: no mutate block` → add the *next* block's line range; `# pragma: no mutate start` … `end` → add the inclusive range. Return the union set — **no visitor change needed**. |
| **`do_not_mutate_patterns` (regex)** | regex (not just glob) exclusions | new config field + `_skip_node_and_children` (mutation.py:207) | `config.py`: add `do_not_mutate_patterns: list[str]`, pre-compile. In `_skip_node_and_children`, also skip when the node's qualified name / rendered source matches any pattern. |
| **`@staticmethod`/`@classmethod` mutation** | mutate methods decorated *solely* with these | decorator-skip at **mutation.py:245** | Relax `len(node.decorators)` skip: do **not** skip when every decorator name ∈ {`staticmethod`,`classmethod`}; keep skipping `@property` & others (the comment at :238-243 explains why — trampoline signature). Mirror 3.6.0's narrowing: still skip these under `type_check_command` mode. Verify the `xǁClassǁmethod` trampoline handles a no-`self` staticmethod (it is name-dispatched, so it should). |

These three are **independent of the profile system** (they govern *what* is mutated, not *which operators*), so they apply across all profiles.

---

## 6. Suggested implementation phasing

1. ✅ **Profile scaffold first** (the `Profile` tag + visitor filter + CLI/config). Everything else hangs off it; ship `advanced` as the selected default. **(shipped v2.16.0)**
2. ✅ **Cheap, high-yield `advanced` operators**: ROR-matrix, number CRCR, negate-condition, force-conditional, collection-literal-empty, match-guard. (~each is a <30-line operator + one registry line.) **(shipped v2.17.0 — acceptance harness 152/152/100 %)**
3. ✅ **Regex suite** (the big one): the 14 applicable sub-mutators, **string-based on a class-span tokenizer** (NOT `re._parser` — `re` has no `unparse`, so a round-trip emitter would be the killer risk; decision confirmed in P3). **(shipped v2.18.0 — acceptance harness 184/188, +36 regex-pattern mutants; 4 documented `fullmatch` equivalents)**
4. ✅ **3.6.0 surface backports** (pragma block/start-end, do_not_mutate regex, `@staticmethod`) **(shipped v2.19.0; `@classmethod` deferred — class-bound `__name__` is read-only for the trampoline lookup)**
5. ✅ **`all`-tier aggressive operators**: UOI, AOD, general-statement-removal, member-assign-removal, exception-swap. **(shipped v2.19.0 — acceptance harness 204/200/98 %, 4 documented regex equivalents; comparison-operand UOI excluded by ToT)**

Each new operator should get an `opmatrix`-style probe (target fn + strong kill-test asserting the exact mutant) so the kill-matrix stays at 100% and equivalent mutants are flagged early — exactly the harness already built in `testing/opmatrix`.

---

## 7. Decisions (LOCKED 2026-06-13)

1. **Default-selected profile = `advanced`** (REVISED 2026-06-14, supersedes the 2026-06-13 `basic` lock). `advanced` == mutmut-win's historical operator set, so the default is **behaviour-neutral — NOT a breaking change**. `basic` is the opt-in mutmut-parity profile; `all` is for audits. See the ✅ box in §1; shipped in v2.16.0 (minor bump).
2. **`all`-tier scope = UOI + AOD + general-statement-removal + member/attr-assignment-removal + exception-swap.** The dynamic-typing-hard operators (constructor→None, naked-receiver, argument-propagation) and remove-`await` are **excluded**.
3. **Regex-Implementierung = stringbasierter Class-Span-Tokenizer.** Die
   ursprünglich erwogene private `re._parser`-API wurde mangels stabilem
   Roundtrip-Emitter verworfen; `re.compile()` bleibt das Validierungsgate.

Diese Entscheidungen wurden gemäß §6 in v2.16.0 bis v2.19.0 umgesetzt; die
ausgelieferten Implementierungen und Regressionstests sind gegenüber den
historischen Skizzen autoritativ.
