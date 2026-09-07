# Code Style & Conventions (v2.21.1 / Sprint 39 contract)

## Language & versions
- Exactly CPython 3.14.7 on Windows (Ruff target `py314`; mypy checks Python 3.14 semantics).
- Code, docstrings and README in English; process docs (CLAUDE.md, sprint docs) in German.

## Naming
- snake_case for functions/variables/modules, PascalCase for classes,
  UPPER_CASE for constants.

## Types
- mypy strict mode; type hints on ALL public APIs; no `Any` where a concrete type is
  possible.
- No `# type: ignore` without a specific error code AND a justification comment
  (e.g. `# type: ignore[override]`).
- Release gate: `uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/`
  must complete without errors and without a checkout-local cache;
  historical baseline counts are not active acceptance criteria.

## Docstrings & comments
- Google-style docstrings for all public classes/functions.
- Comments only for constraints the code cannot express itself.

## Data structures
- Pydantic v2 models across boundaries — no raw dicts.

## Testing
- Release tests require both `UV_PROJECT_ENVIRONMENT` and
  `HYPOTHESIS_STORAGE_DIRECTORY` to point outside the checkout; Hypothesis
  6.151.10 writes cache bytes but no `.gitignore` of its own.
- The release suite uses `uv run --no-sync pytest -q --cov=mutmut_win
  --cov-report=term-missing -p no:cacheprovider` so neither pytest nor Coverage
  adds checkout-local cache control files.
- pytest-native: NO unittest.TestCase; fixtures instead of setUp/tearDown.
- hypothesis for property-based tests (roundtrips, parsing/validation invariants).
- pytest-benchmark for performance-critical paths; markers: `slow`, `integration`.
- TDD (red → green → refactor); no `@pytest.mark.skip` without documented reason.
- Mutation gate: new/changed code needs mutation score >= 80 %
  (`uv run mutmut-win run --paths-to-mutate <modules>`); document surviving mutants
  if below.

## Lint / format
- Ruff is the ONLY linter+formatter (replaces black/flake8/isort/pylint — never run
  those in parallel). Line length 100. Extensive rule set incl. S (bandit), B (bugbear),
  PTH (pathlib), PERF, RUF — see pyproject.
- per-file-ignores: S101 (assert) allowed in tests/ and benchmarks/.
- `tests/e2e_projects/` is fully excluded from ruff (upstream reference fixtures).
- Release gates use `uv run --no-sync ruff check --no-cache .` and
  `uv run --no-sync ruff format --no-cache --check .`.
- No `# noqa` without a justification comment directly above.

## Architecture
- import-linter layer contracts are binding (pyproject `[tool.importlinter]` +
  `tests/test_architecture.py`). Architecture rules MUST exist as executable contracts,
  never only as documentation. Never resolve a violation by removing/weakening a contract.
- The standalone architecture gate is `uv run --no-sync lint-imports --no-cache`.

## Windows specifics
- Use explicit encodings for file I/O. Public source processing honors the
  declared PEP-263 encoding; internally generated staging may upgrade to UTF-8
  when generated code is not representable in the source encoding.
- spawn semantics only (no fork); child processes belong to Job Objects;
  POSIX code paths carry no runtime-support or release-gate commitment.
- WER (Windows Error Reporting) dialogs are suppressed in workers (issue #123, WIN-001).

## Git
- Conventional Commits (`type(scope): description`); GitHub Flow;
  branches `feature/[ISSUE-NR]-kurzbeschreibung`; annotated SemVer tags after milestones.
