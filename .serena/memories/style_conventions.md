# Code Style & Conventions

## Naming
- snake_case for functions, variables, modules
- PascalCase for classes
- UPPER_CASE for constants

## Type Hints
- ALL public APIs must have type hints (mypy strict mode)
- No `Any` where a concrete type is possible
- No `# type: ignore` without specific error code and justification

## Docstrings
- Google-Style docstrings for all public classes/functions

## Data Models
- Pydantic v2 for all data structures (no raw dicts)

## Testing
- pytest-native (no unittest.TestCase)
- Fixture-based setup
- hypothesis for property-based testing
- TDD: Red → Green → Refactor

## Linting
- Ruff (replaces flake8, isort, black, pylint)
- No `# noqa` without documented justification
- Line length: 100

## File I/O
- Always use `encoding='utf-8'` (Windows default is CP1252)

## Imports
- import-linter enforces layer architecture
