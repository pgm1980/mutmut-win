# Code Style & Conventions (as of v2.13.0)

## Language & versions
- Python >= 3.12 (ruff target py312, mypy python_version 3.12; dev venv 3.14.3).
- Code, docstrings and README in English; process docs (CLAUDE.md, sprint docs) in German.

## Naming
- snake_case for functions/variables/modules, PascalCase for classes,
  UPPER_CASE for constants.

## Types
- mypy strict mode; type hints on ALL public APIs; no `Any` where a concrete type is
  possible.
- No `# type: ignore` without a specific error code AND a justification comment
  (e.g. `# type: ignore[override]`).
- Known baseline: 14 mypy errors @ v2.13.0 — changes must not add new ones.

## Docstrings & comments
- Google-style docstrings for all public classes/functions.
- Comments only for constraints the code cannot express itself.

## Data structures
- Pydantic v2 models across boundaries — no raw dicts.

## Testing
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
- No `# noqa` without a justification comment directly above.

## Architecture
- import-linter layer contracts are binding (pyproject `[tool.importlinter]` +
  `tests/test_architecture.py`). Architecture rules MUST exist as executable contracts,
  never only as documentation. Never resolve a violation by removing/weakening a contract.

## Windows specifics
- ALWAYS pass `encoding='utf-8'` for file I/O (Windows default is cp1252).
- spawn semantics only (no fork); child processes belong to Job Objects;
  POSIX code paths stay functional for WSL/Linux CI.
- WER (Windows Error Reporting) dialogs are suppressed in workers (issue #123, WIN-001).

## Git
- Conventional Commits (`type(scope): description`); GitHub Flow;
  branches `feature/[ISSUE-NR]-kurzbeschreibung`; annotated SemVer tags after milestones.
