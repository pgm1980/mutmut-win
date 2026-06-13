# Roadmap Acceptance Harness — provenance

Executable **TDD / acceptance harness** for the planned operators in
[`../MUTMUT_WIN_OPERATOR_ROADMAP.md`](../MUTMUT_WIN_OPERATOR_ROADMAP.md) (Task 2). Rescued
from `_external_tests/testing/roadmap/` before that temporary tree was deleted. The
harness's own documentation is [`ROADMAP_SPEC.md`](ROADMAP_SPEC.md) — it carries the
**Current → Expected** mutant-count table per planned operator.

## How it is meant to be used

Baseline **today** (v2.14.0, all current operators on, no profile system yet):
**71 mutants / 100 % killed / 14 pytest green**. Each strong kill-test passes *trivially*
now because the future operator's mutant is not generated yet. As each planned operator
lands:

1. `mutmut-win run --force` (with `--profile advanced` / `--profile all` once profiles exist).
2. **Acceptance per target:** the mutant count rises from *Current* to *Expected* **and**
   the score stays **100 %** (the provided test kills the new mutant). A survivor ⇒ an
   operator bug or a genuine equivalent mutant to document; a missing count ⇒ the operator
   is not (fully) generating.

Mirrors the `opmatrix` methodology (one construct + one strong test per operator) so CI can
assert 100 % kill on this project as operators are implemented.

`[tool.uv.sources]` pins `@v2.14.0`; re-point it at this working tree to exercise operators
as they are built.
