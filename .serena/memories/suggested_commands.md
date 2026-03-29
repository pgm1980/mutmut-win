# Suggested Commands

## Build & Run
- `uv sync` — Install/sync dependencies
- `uv run python -m mutmut_win` — Run the tool

## Testing
- `uv run pytest` — All tests
- `uv run pytest tests/unit/` — Unit tests only
- `uv run pytest tests/integration/` — Integration tests only
- `uv run pytest --cov=src --cov-report=html` — Tests with coverage
- `uv run pytest --benchmark-only` — Benchmarks only

## Linting & Type Checking
- `uv run ruff check .` — Lint
- `uv run ruff format .` — Format
- `uv run ruff check --fix .` — Auto-fix lint
- `uv run mypy src/` — Type checking (strict)

## Architecture & Security
- `uv run lint-imports` — Architecture contracts
- `semgrep scan --config auto .` — Security scan
- `uv run pip-audit` — Dependency audit

## Mutation Testing
- `uv run mutmut run --paths-to-mutate src/mutmut_win/` — Mutation testing
- `uv run mutmut html` — HTML report

## Version Control
- `git` commands for version control (GitHub Flow, Conventional Commits)

## System utilities
- Use FS MCP Server for ALL filesystem operations (cat, ls, cp, mv, rm, find, grep are BLOCKED)
- `git` via Bash is allowed
- `uv run ...` via Bash is allowed
