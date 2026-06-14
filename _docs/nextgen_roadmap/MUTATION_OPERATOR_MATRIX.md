# Mutation-Operator Comparison Matrix — mutmut-win vs. mutmut / Stryker.NET / Stryker.NET-X / cargo-mutants / PIT

*Compiled 2026-06-13 from first-hand source reading of all six tools (the five others under `_others/`, mutmut-win under `_codebase_v2140/`). Per-tool catalogs were extracted directly from each tool's mutator source, not from docs.*

## 1. Tools compared

| Tool | Version | Lang | Engine | Philosophy | Operator count (own granularity) |
|---|---|---|---|---|---|
| **mutmut-win** | 2.14.0 | Python | libcst | AST operators + 7 ported extras | 24 operator fns ≈ 30 normalized classes |
| mutmut | 3.6.0 | Python | libcst | AST operators (the base set) | 15 operators / 60 token-transforms (== 3.5.0) |
| Stryker.NET | 4.14.2 | C# | Roslyn | AST operators + regex sub-engine | 26 C# + 15 regex = 41 classes / 19 enum |
| **Stryker.NET-X** | 3.3.9 | C#14/.NET10 | Roslyn | Stryker + 26 ported/greenfield | 52 C# + 16 regex = 68; **26 ADDED** |
| cargo-mutants | 27.1.0 | Rust | syn | **Return-value/body replacement** (different paradigm) | 6 genres / 63 transforms |
| PIT | 1.25.4 | Java | bytecode (Gregor) | Bytecode operators, grouped | 26 selectable ids / 21 factory classes |

**Counts are NOT directly comparable** (granularity differs wildly — one PIT `MATH` id ≈ 11 mutmut token-swaps; cargo's one `FnValue` genre ≈ 29 type rules). The normalized matrix in §3 is the comparable view.

## 2. Legend

- ✅ = supported (first-class)
- ◐ = partial / a narrower variant only
- — = not supported (but conceptually applicable to the language)
- 🚫 = not applicable to that language (syntax/type system makes it meaningless)

## 3. The matrix (normalized mutation classes)

### Operators — arithmetic / relational / logical / bitwise

| # | Mutation class | mutmut-win | mutmut 3.6 | Stryker.NET | Stryker.NET-X | cargo-mutants | PIT |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 1 | Arithmetic operator replacement (`+`↔`-`, `*`↔`/`…) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 2 | **Arithmetic operand deletion (AOD)** `a+b`→`a`/`b` | — | — | — | ✅ | — | — |
| 3 | **Relational full matrix (ROR)** `<`→`<=,>,>=,==,!=` | ✅ | ◐ | ◐ | ✅ | ◐ | ◐ |
| 4 | Conditional boundary `<`↔`<=`, `>`↔`>=` | ✅ | ✅ | ◐ | ✅ | ✅ | ✅ |
| 5 | Equality negate `==`↔`!=` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 6 | Logical connector `and`↔`or` | ✅ | ✅ | ✅ | ✅ | ✅ | ◐ |
| 7 | Bitwise `&`↔`\|`, `^` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 8 | Shift `<<`↔`>>` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 9 | Augmented-assign swap `+=`↔`-=` | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| 10 | Augmented→plain `x+=1`→`x=1` | ✅ | ✅ | — | — | — | — |

### Unary / literals

| # | Mutation class | mutmut-win | mutmut 3.6 | Stryker.NET | Stryker.NET-X | cargo-mutants | PIT |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 11 | Unary operator deletion (remove `not`/`~`/unary `-`) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 12 | **Unary operator insertion (UOI)** `x`→`not x`/`-x` | — | — | — | ✅ | — | — |
| 13 | Increment/decrement `++`/`--` | 🚫 | 🚫 | ✅ | ✅ | 🚫 | ✅ |
| 14 | Number-literal mutation `5`→`6` | ◐ (+1 only) | ◐ (+1 only) | — | ✅ (0/1/-1/±1) | — | ✅ |
| 15 | **Number-literal CRCR** `5`→`0,1,-1,-5` | ✅ | — | — | ✅ | — | ◐ |
| 16 | String-literal mutation (empty/case/wrap) | ✅ | ✅ | ✅ | ✅ | — | — |
| 17 | Boolean-literal `True`↔`False` | ✅ | ✅ | ✅ | ✅ | ◐ | ✅ |
| 18 | Null/None-coalescing default (`x or d`→`x`/`d`) | ✅ | — | ✅ (`??`) | ✅ | — | — |

### Return values / function body

| # | Mutation class | mutmut-win | mutmut 3.6 | Stryker.NET | Stryker.NET-X | cargo-mutants | PIT |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 19 | Return value → None/null | ✅ | ◐ (lambda only) | ◐ | ✅ | ✅ | ✅ |
| 20 | **Return value → type/shape default** (`return []`/`""`/`0`) | — | — | — | ✅ | ✅ (core) | ✅ |
| 21 | **Whole function-body replacement** | — | — | — | ✅ | ✅ (core) | — |

### Conditionals / control flow

| # | Mutation class | mutmut-win | mutmut 3.6 | Stryker.NET | Stryker.NET-X | cargo-mutants | PIT |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 22 | **Negate whole condition** `if x`→`if not x` | ✅ | — | ✅ | ✅ | — | ✅ |
| 23 | **Force/remove conditional** `if c`→`if True`/`if False` | ✅ | — | ◐ | ◐ | ✅ (guard) | ✅ |
| 24 | Ternary neutralize `x if c else y`→`x`/`y` | ✅ | — | ✅ | ✅ | — | — |
| 25 | Control-flow keyword `break`→`return`, `continue`→`break` | ✅ | ✅ | ◐ | ◐ | — | — |

### Statements / assignments / calls

| # | Mutation class | mutmut-win | mutmut 3.6 | Stryker.NET | Stryker.NET-X | cargo-mutants | PIT |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 26 | Void-call removal (`f();`→`pass`) | ✅ | — | ✅ | ✅ | ◐ | ✅ |
| 27 | **General statement / block removal** | ◐ (void+raise) | — | ✅ | ✅ | — | ◐ |
| 28 | Assignment value → None (`a=b`→`a=None`) | ✅ | ✅ | — | — | — | — |
| 29 | **Member/field assignment removal** (`self.x=v`→drop) | — | — | — | ✅ | — | ✅ |
| 30 | Call argument removal / →None | ✅ | ✅ | — | — | — | — |
| 31 | dict keyword corruption (`dict(a=)`→`dict(aXX=)`) | ✅ | ✅ | — | — | — | — |
| 32 | **Naked receiver** `a.f(x)`→`a` | — | — | ◐ | ✅ | — | ✅ |
| 33 | **Argument propagation** `f(a)`→`a` | — | — | — | ✅ | — | ✅ |
| 34 | String-method swap (`lower`↔`upper`, `find`↔`rfind`…) | ✅ | ✅ | ✅ | ✅ | — | — |
| 35 | Math-method swap (`ceil`↔`floor`, `min`↔`max`) | ✅ | — | ✅ | ✅ | — | ◐ |
| 36 | Collection/LINQ-method swap | ◐ | — | ✅ | ✅ | — | — |

### Collections / match / regex / exceptions

| # | Mutation class | mutmut-win | mutmut 3.6 | Stryker.NET | Stryker.NET-X | cargo-mutants | PIT |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| 37 | Collection *neutralize* (`sorted(x)`→`x`) | ✅ | — | — | — | — | — |
| 38 | **Collection *literal* emptying** (`[1,2,3]`→`[]`) | ✅ | — | ✅ | ✅ | ◐ | ◐ |
| 39 | Comprehension filter removal (`[x for x in s if p]`→`…`) | ✅ | — | — | — | — | — |
| 40 | Match/switch arm deletion | ✅ | ✅ | — | ✅ | ✅ | ✅ |
| 41 | **Match guard** `case x if c`→`if True`/`if False` | ✅ | — | — | ✅ | ✅ | — |
| 42 | Regex pattern mutation | ◐ (lean) | — | ✅ (15 sub) | ✅ (16 sub) | — | — |
| 43 | `raise`/throw removal | ✅ | — | ✅ | ✅ | ◐ | — |
| 44 | **Exception swap** (`raise ValueError`→`raise TypeError`) | — | — | — | ✅ | — | — |

### Language-foreign for Python (🚫 — listed for completeness, NOT gaps)

| # | Mutation class | Native to | Python analog |
|---|---|---|---|
| 45 | `checked`/`unchecked` overflow context | C# | none |
| 46 | `??` / `??=` null-coalescing operator | C# | `or` (class 18, already ✅) |
| 47 | LINQ method-name swaps | C#/.NET | itertools/builtins (concept = class 36) |
| 48 | `System.Math.*` method swaps | C#/.NET | `math.*` (concept = class 35, ✅) |
| 49 | `string.Empty`/`IsNullOrEmpty`/interpolation | C# | `""`/`f""` (class 16, ✅) |
| 50 | C# is-patterns / collection-expr / `stackalloc` | C#7-12 | partial via `match` (class 40/41) |
| 51 | Span/Memory, ConfigureAwait, Task.WhenAll, record-`with`, generic constraints, DateTime API | .NET BCL | none / library-specific |
| 52 | Boxed-primitive return splits (TRUE/FALSE/PRIMITIVE/NULL_RETURNS) | Java | unified by Python's dynamic types (class 19/20) |
| 53 | Constructor→null (`new Foo()`→`null`) | C#/Java | `Foo()`→`None` (niche, see §5 Tier B) |
| 54 | Async sync-over-async (`await x`→`x.Result`) | .NET | remove `await` (niche, see §5 Tier B) |

## 4. mutmut-win's lineage (source-documented)

mutmut-win = **mutmut's 15-operator base + 7 added classes**, and `node_mutation.py` literally tags each addition's origin:

| mutmut-win addition | Source comment | Borrowed from |
|---|---|---|
| `operator_regex` | *"unique to mutmut-win — no other Python tool has this"* | concept from **Stryker.NET** RegexMutator |
| `operator_return_value` | *"inspired by cargo-mutants"* | **cargo-mutants** FnValue |
| `operator_conditional_expression` | *"inspired by Stryker.NET"* | **Stryker.NET** ConditionalExpression |
| `operator_void_call_removal`, `operator_raise_removal` | *"inspired by Stryker.NET"* | **Stryker.NET** Statement/Block |
| `operator_collection_neutralize`, `operator_comprehension_filter_removal` | *"inspired by Stryker.NET LINQ"* | **Stryker.NET** Linq/Initializer |
| `operator_math_methods` | *"inspired by Stryker.NET"* | **Stryker.NET** Math |
| `operator_or_default` | *"inspired by Stryker.NET null-coalescing"* | **Stryker.NET** NullCoalescing |

So mutmut-win already did exactly the cross-pollination you did for Stryker.NET-X — just earlier and smaller. The matrix's `—` cells in mutmut-win's column are the *next* round of that same exercise.

## 5. mutmut-win gaps — PRELIMINARY Python-relevance triage

*(This is my opening proposal for the collaborative Phase 4 — to be refined together. Each gap = a `—`/`◐` in mutmut-win's column that IS conceptually Python-applicable.)*

### Tier A — relevant & worthwhile (clear Python semantics, real test-gap value)

| Class | Why it matters for Python | Effort/risk |
|---|---|---|
| **#3 ROR full matrix** | `<`→`>`/`>=`/`==`/`!=` catches off-by-direction bugs mutmut-win misses (it only does `<`↔`<=` + `==`↔`!=`). PIT/Stryker-X treat this as core. | Low — extend `_operator_mapping` to multi-target |
| **#15 Number-literal CRCR** | `n`→`0,1,-1` (not just `n+1`) — classic, high-yield; mutmut-win's lone +1 misses zero/sign boundaries. | Low |
| **#22 Negate whole condition** | `if x:`→`if not x:` flips untested branch logic that operator-local negation can't reach (e.g. truthy non-comparisons). | Low-med |
| **#23 Force conditional True/False** | `if c:`→`if True:`/`if False:` (PIT REMOVE_CONDITIONALS) — proves both branches are exercised. | Med (CST: replace test) |
| **#38 Collection-literal emptying** | `[1,2,3]`→`[]`, `{…}`→`{}`, `(…)`→`()` — extremely common, mutmut-win only *neutralizes calls*, never empties literals. | Low-med |
| **#42 Richer regex sub-mutations** | Python `re` supports everything Stryker's 15 sub-mutators do (lookaround flip, group→non-capturing, char-class→any, range ±1, quantifier rewrites, unicode-class negation). mutmut-win's engine is comparatively lean. | Med (port Stryker's regex set) |
| **#20 Shape-appropriate return** | `return <list>`→`return []`, `return <str>`→`return ""` (value-shape based, since Python is dynamic) — richer than the single `→None`. | Med (infer from literal shape) |
| **#41 Match-guard mutation** | Python 3.10+ `case x if cond:` → guard `True`/`False` (cargo/Stryker-X have it). | Low-med |

### Tier B — niche / context-dependent (worth discussing, lower priority)

| Class | Note |
|---|---|
| **#2 AOD** `a+b`→`a`/`b` | Useful but noisy; overlaps operator swaps. |
| **#12 UOI** insert `not`/`-` | Powerful (PIT-grade) but high mutant volume; Stryker-X gates it to "All" only. |
| **#27 general statement removal** | mutmut-win has void/raise; generalizing to any expr-stmt/`pass`-block is reasonable but raises equivalent-mutant noise. |
| **#29 member-assignment removal** | `self.x = v` → drop; overlaps mutmut-win's `a=None` (neutralize vs remove). |
| **#44 Exception swap** | `raise ValueError`→`raise TypeError` — needs a sensible Python exception-pair table. |
| **#53 Constructor→None** | `Foo()`→`None`; in Python just a call, overlaps arg/return ideas. |
| **#54 Remove `await`** | `await x`→`x` (async test-gap probe) — Python has async; small, plausible. |
| **#32/#33 naked-receiver / arg-propagation** | Hard under dynamic typing (no static type match); high false-positive risk. |

### Tier C — language-foreign, do NOT port (rows 45–52)

`++`/`--`, `checked`, `??`/`??=` operator form, LINQ/`System.Math`/`string.Empty` method-name tables, interpolated-string specifics, C# is-patterns / collection-expressions / `stackalloc`, Span/Memory/ConfigureAwait/Task.WhenAll/record-`with`/generic-constraints/DateTime, and Java boxed-primitive return splits. Either no Python syntax exists or the Python analog is already covered (e.g. `??` ≈ `or` = class 18 ✅).

## 6. Caveats

- Cell values are normalized judgments; a `◐` means "a narrower variant exists" (see per-tool catalogs for exact transforms).
- cargo-mutants' paradigm (replace whole return value by type) makes many literal/operator rows `—` by design, not by omission — it is *intentionally* not an in-place operator tool.
- 3 scientific papers (2026) were referenced by the project owner but are **not** in `_others/`; their operators are to be folded in as additional columns/rows in a later pass.
- mutmut 3.6.0 adds no new operators vs 3.5.0 (mutmut-win's base) but adds *surface* features (pragma `block`/`start-end`, `do_not_mutate_patterns` regex, `@staticmethod`/`@classmethod` mutation) — backport candidates, tracked separately from operators.
</content>
