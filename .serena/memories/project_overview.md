# mutmut-win — Project Overview

## Purpose
Windows-only fork of mutmut 3.5.0 mutation testing tool. Replaces Unix-only APIs (os.fork, os.wait, resource.RLIMIT_CPU, signal.SIGXCPU) with Windows-compatible alternatives (multiprocessing spawn + worker pool, wall-clock timeout).

## Tech Stack
- Python 3.14.3
- Package Manager: uv
- Mutation Engine: libcst (CST-based, ported from mutmut)
- CLI: click
- TUI: textual
- Config: pydantic v2
- Testing: pytest + hypothesis + pytest-benchmark + pytest-cov
- Linting: ruff (all-in-one) + mypy (strict)
- Security: semgrep
- Mutation Testing: mutmut
- Architecture: import-linter

## Key Architecture
- spawn-based worker pool (no fork)
- Two-queue architecture (task_queue + event_queue)
- Wall-clock timeout via monitor thread
- Clean-room rewrite of __main__.py into focused modules

## Package Structure
src/mutmut_win/ with subpackage process/
