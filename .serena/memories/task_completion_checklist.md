# Task Completion Checklist

Before declaring any task "done":

1. `uv run ruff check .` — 0 findings
2. `uv run ruff format .` — formatted
3. `uv run mypy src/` — 0 errors
4. `uv run pytest` — all green
5. `uv run pytest --cov=src` — coverage measured
6. `semgrep scan --config auto .` — 0 findings (security-relevant code)
7. `uv run lint-imports` — 0 violations
8. Conventional Commit messages used
9. MEMORY.md updated if needed
