# mutmut-win

Windows-native mutation testing for Python, based on [mutmut 3.5.0](https://github.com/boxed/mutmut).

## What is this?

mutmut-win is a standalone Windows port of mutmut, the popular Python mutation testing tool. It replaces all Unix-only APIs (`os.fork()`, `os.wait()`, `resource.RLIMIT_CPU`, `signal.SIGXCPU`) with Windows-compatible alternatives while maintaining identical mutation testing behavior.

**mutmut** is for Unix/Linux. **mutmut-win** is for Windows.

## Why a separate package?

mutmut explicitly blocks Windows execution ([issue #397](https://github.com/boxed/mutmut/issues/397)). Rather than patching mutmut for cross-platform support, mutmut-win is a clean-room rewrite of the process management layer, purpose-built for Windows.

| Feature | mutmut (Unix) | mutmut-win (Windows) |
|---------|---------------|---------------------|
| Process creation | `os.fork()` | `multiprocessing.spawn` + Worker Pool |
| Timeout mechanism | `RLIMIT_CPU` + `SIGXCPU` | Wall-clock timeout via monitor thread |
| Orphan protection | None (children adopted by init) | Windows Job Objects (kernel-level) |
| IPC | `os.wait()` + exit codes | Two-Queue architecture (task + event) |
| Mutation engine | libcst (CST-based) | libcst (CST-based) - identical |
| Config format | `[tool.mutmut]` in pyproject.toml | `[tool.mutmut]` in pyproject.toml - compatible |

## Installation

```bash
pip install mutmut-win
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add mutmut-win --dev
```

**Requirements:** Python >= 3.12, Windows 10/11

## Quick Start

1. Add `[tool.mutmut]` to your `pyproject.toml`:

```toml
[tool.mutmut]
paths_to_mutate = ["src/"]
tests_dir = ["tests/"]
```

2. Run mutation testing:

```bash
mutmut-win run
```

3. View results:

```bash
mutmut-win results
```

## CLI Commands

```
mutmut-win run [--max-children N] [MUTANT_NAMES...]   Run mutation testing
mutmut-win results [--all]                             Show result summary
mutmut-win show <MUTANT_NAME>                          Show diff for a mutant
mutmut-win apply <MUTANT_NAME>                         Apply a mutant to source
mutmut-win browse [--show-killed]                      TUI result browser
mutmut-win tests-for-mutant <MUTANT_NAME>              Show tests for a mutant
mutmut-win time-estimates [MUTANT_NAMES...]             Show time estimates
mutmut-win export-cicd-stats                           Export CI/CD stats JSON
```

## Configuration

All configuration goes in `pyproject.toml` under `[tool.mutmut]` (compatible with mutmut):

```toml
[tool.mutmut]
paths_to_mutate = ["src/"]
tests_dir = ["tests/"]
timeout_multiplier = 30          # Wall-clock timeout factor (default: 30)
max_children = 8                 # Worker processes (default: CPU count)
do_not_mutate = ["**/migrations/*"]
also_copy = ["fixtures/"]
mutate_only_covered_lines = false
type_check_command = ["mypy", "src/"]
```

## Architecture

mutmut-win uses a 4-layer architecture:

```
CLI Layer          cli.py, browser.py
Application Layer  orchestrator.py, runner.py, stats.py
Domain Layer       config, models, constants, mutation engine
Infrastructure     process/ (executor, timeout, worker, job_object)
```

### Key Design Decisions

- **Spawn + Worker Pool:** N long-lived workers (via `multiprocessing.spawn`) initialize pytest once and consume tasks from a queue. This amortizes the spawn overhead across all mutants.
- **Wall-Clock Timeout:** A monitor thread in the main process tracks deadlines and kills workers that exceed them. Generous default multiplier (30x) accounts for wall-clock vs CPU-time differences.
- **Windows Job Objects:** When the parent process dies unexpectedly, the OS kernel automatically terminates all workers and their pytest subprocesses. Prevents CPU overheating from orphaned processes.
- **Two-Queue IPC:** `task_queue` (main to workers) + `event_queue` (workers to main). All data is pickle-safe (plain dicts over queues).

## Development

```bash
# Clone and setup
git clone https://github.com/pgm1980/mutmut-win.git
cd mutmut-win
uv sync --extra dev

# Run tests (477 unit + 4 architecture)
uv run pytest

# Lint + format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src/

# Architecture contracts
uv run lint-imports
```

## Test Projects

Two E2E test projects are included:

| Project | Mutants | Purpose |
|---------|---------|---------|
| `tests/e2e_projects/simple_lib` | ~5 | Quick smoke test (4 functions, 9 tests) |
| `tests/e2e_projects/stress_test` | ~1127 | Stress test (8 modules, 443 tests) |

## Mutation Operators

mutmut-win supports all 15 mutation operators from mutmut 3.5.0:

- Arithmetic operators (`+` to `-`, `*` to `/`, etc.)
- Comparison operators (`<` to `<=`, `==` to `!=`, etc.)
- Boolean operators (`and` to `or`, `True` to `False`)
- String mutations (case change, prefix/suffix)
- Number mutations (+1)
- Assignment mutations (`a = b` to `a = None`)
- Augmented assignment (`+=` to `=`)
- Keyword mutations (`break` to `return`, `is` to `is not`)
- Lambda mutations
- Unary operator removal (`not x` to `x`)
- Dict argument mutations
- Argument removal
- String method swaps (`lower()` to `upper()`)
- Match/case statement mutations

## License

ISC License (same as mutmut)

## Credits

Based on [mutmut](https://github.com/boxed/mutmut) by Anders Hovmoller. The CST-based mutation engine is ported directly from mutmut 3.5.0.
