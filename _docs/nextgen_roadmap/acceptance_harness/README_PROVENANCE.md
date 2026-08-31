# Roadmap Acceptance Harness — provenance

Executable **TDD / acceptance harness** for the planned operators in
[`../MUTMUT_WIN_OPERATOR_ROADMAP.md`](../MUTMUT_WIN_OPERATOR_ROADMAP.md) (Task 2). Rescued
from `_external_tests/testing/roadmap/` before that temporary tree was deleted. The
harness's own documentation is [`ROADMAP_SPEC.md`](ROADMAP_SPEC.md) — it carries the
**Current → Expected** mutant-count table per planned operator.

## How it is meant to be used

Original rescued baseline (v2.14.0, all then-current operators on, no profile system):
**71 mutants / 100 % killed / 14 pytest green**. In that baseline, a strong kill-test
passed *trivially* when its future operator's mutant was not generated. The phased results
after those operators and profiles shipped are recorded in `ROADMAP_SPEC.md`. To verify a
supported profile:

1. Run `mutmut-win run --force --profile advanced`; use `--profile all` for the
   aggressive operator tier.
2. **Acceptance per target:** the mutant count rises from *Current* to *Expected* **and**
   the score stays **100 %** (the provided test kills the new mutant). A survivor ⇒ an
   operator bug or a genuine equivalent mutant to document; a missing count ⇒ the operator
   is not (fully) generating.

Mirrors the `opmatrix` methodology (one construct + one strong test per operator) so CI can
assert 100 % kill on this project as operators are implemented.

The checked-in standalone environment pins `@v2.20.0`, the last released behavior
baseline before the v2.21.0 hardening cycle, and its `uv.lock` must resolve that same
tag. Re-point it at this working tree to exercise unreleased changes.
