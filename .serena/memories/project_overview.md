# mutmut-win — Project Overview

## Purpose
Windows-native mutation testing for Python, based on mutmut 3.5.0 (upstream explicitly
blocks Windows, mutmut#397). Replaces the Unix-only process layer (os.fork, RLIMIT_CPU,
SIGXCPU) with a spawn-based worker pool, Windows Job Objects (orphan protection: if the
parent dies, the kernel reaps every worker and pytest child) and a wall-clock timeout
model. Windows 10/11 is the primary target; POSIX code paths are kept functional for
WSL/Linux CI. Mutation engine, config format and workflow stay mutmut-compatible.

Repo: https://github.com/pgm1980/mutmut-win.git
Distribution: install from a pinned git tag only
(`uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@vX.Y.Z" --dev`).
PyPI publishing is deliberately NOT part of the release sequence.
Leading install doc: `_docs/mutmut-win-install.md` (referenced from CLAUDE.md).

## Status — see memory `current_state` for the LIVE state (v2.17.0, 2026-06-14)

> Current release is **v2.17.0**: Phase 1 (v2.16.0) added the basic/advanced/all
> operator-profile system, Phase 2 (v2.17.0) the six advanced operators. The v2.14.0
> baseline + Sprint-36 detail below is kept for history.

## Status (v2.14.0 baseline, 2026-06-13)
- Current release: **v2.14.0** (released 2026-06-13). Sprint 36 "Maintenance 4:
  Fable-5 360°" closed — all 28 findings of the 360° analysis (9 bugs A1–A9,
  13 anomalies B1–B13, 6 optimizations C1–C6; issues #124–#132). Merge `5ef27c1`,
  bump `43a7762`, annotated tag v2.14.0, GitHub release. Dogfooding 69.2 %
  (> S34 ref 68.3 %). C3 = documented Won't-Do; B11/B12 documented limitations.
- Prior release: v2.13.0 (2026-06-12, Sprint 35 "Maintenance 3: External QA",
  issues #118–#123).
- **Development pause**: 0 open issues / backlog / decisions. Resumption anchors:
  dogfooding pause baseline (7231 mutants / 69.2 %), the 360° report
  (`_docs/audit/fable5_360_analysis_v2.13.0.md`, memory `fable5_360_findings`),
  and the legacy tech-debt inventory in the Sprint 36 backlog (function-wide
  legacy survivor rates for a future tech-debt sprint).
- **Fable-5 360° code analysis (2026-06-12)**: 9 confirmed bugs (3 High),
  13 anomalies, 6 optimizations — report `_docs/audit/fable5_360_analysis_v2.13.0.md`,
  inventory in memory `fable5_360_findings`. All addressed by Sprint 36
  (C3 documented Won't-Do; B11/B12 documented limitations).
- Semgrep gate note: ALL historical semgrep_passed gates (incl. v2.13.0 release) ran on
  Community Edition (logged-out CLI). Since 2026-06-12 the host CLI is Pro
  (SEMGREP_APP_TOKEN as User env var, CLI 1.166.0): SAST active, **1228 rules — still
  0 findings** on this codebase. Gate criterion now: "Rules run" ≥ ~1200, no
  "semgrep login" hint. Sessions inherit the token only after a full Claude Desktop
  restart (workaround: registry bridge via winreg in a Python subprocess).
- Last verified gates @ Sprint 36 (2026-06-13): 1118 passed / 5 skipped, bare
  `ruff check .` 0 findings (B13: `.claude/` excluded), mypy 14 (known baseline),
  import-linter KEPT, Semgrep Pro 1228 rules / 0 findings, pip-audit clean
  (urllib3/idna/pip/pytest lifted past advisories). Runtime floor: pytest>=8.2
  (A2, @argfile).

## Key capabilities (vs upstream mutmut)
- Operator profiles (v2.16.0+): `basic` = mutmut 3.5.0's 15 base operators; `advanced`
  (default, 34 registry entries / 29 unique funcs) adds the extras (regex, math method
  swaps, return-value replacement, conditional expressions, statement removal, collection
  methods, or-defaults) + the six v2.17.0 Phase-2 operators (ROR matrix, number CRCR,
  condition negate/force, collection-empty, match-guard); `all` reserved. See `current_state`.
- Per-mutant test selection: a stats run records the test↔function mapping; each mutant
  runs only its covering tests. Mutants with zero covering tests → `no tests`, no runtime.
- Self-calibrating wall-clock timeouts: measured per-process startup floor + scaled
  runtime of assigned tests; the model is printed at run start.
- psutil-based infinite-loop classifier (CPU / output growth / process-status evidence,
  confidence bands, persisted forensics). On Windows the process-status signal does not
  exist → verdicts capped at `medium` confidence.
- Type checker as kill filter (`type_check_command`): mutants the checker rejects count
  as caught without running tests.
- Result reuse (since v2.13.0): verdicts of unchanged mutants (source + config +
  covering-tests fingerprints) are reused instead of re-run; `--rerun-all` opts out.
- Honest scoring: disjoint buckets (killed, survived, timeout, suspicious, skipped,
  no tests, segfault, type-check-caught, killed_by_infinite_loop); one score formula
  shared by run gate, `results` and CI export; interrupted runs exit 130 with no fake score.
  score = (killed + type-check + IL-killed + segfault) / (total − skipped − no tests − unchecked) × 100
- CI: `--min-score`, `--output json` (pure JSON on stdout, prose on stderr),
  `--since-commit REF`, `export-cicd-stats`.
- SQLite result cache (.mutmut-cache/), fingerprinted per-file mutant staging (mutants/).

## Tech stack
- Python >= 3.12 (classifiers 3.12/3.13/3.14; dev venv runs 3.14.3); package manager uv;
  build backend hatchling.
- Runtime deps: click (CLI), libcst (mutation engine), pydantic v2 (config/models),
  psutil (loop monitor), textual (TUI browser), coverage, setproctitle, pytest.
- Dev/QA: pytest, pytest-cov, pytest-asyncio, pytest-mock, pytest-benchmark, hypothesis,
  import-linter, mypy (strict), ruff, pip-audit; semgrep via CLI (Pro since 2026-06-12).
- Entry points: script `mutmut-win` = mutmut_win.cli:cli; `python -m mutmut_win` also
  works (__main__.py wraps cli and carries BWC re-exports for pre-v2.11.0 staging trees).
- 8 subcommands: run, results, show, apply, browse, tests-for-mutant, time-estimates,
  export-cicd-stats.
- Dogfooding: `[tool.mutmut]` in pyproject points at src/mutmut_win/ with tests_dir
  tests/unit/ — the tool mutation-tests itself as part of release gates.

## How a run works (pipeline)
1. Generate: libcst emits all mutants of a function behind a trampoline dispatcher into
   the mutants/ staging copy (staging mirrors the WHOLE project root minus a skip list;
   unchanged files are fingerprint-skipped).
2. Validate: clean suite must pass inside mutants/; a forced-fail check proves the
   trampoline switches mutants.
3. Map & budget: stats run → per-test durations + test↔function map → covering tests +
   wall-clock budget per mutant.
4. Execute: spawn worker pool activates one mutant at a time via the MUTANT_UNDER_TEST
   env var; job objects guarantee no process tree survives; results stream to SQLite.
Original sources are never modified.

## Release policy
Demand-driven, no calendar cadence. Only on an explicit maintainer "Release" decision
after all gates pass: merge to main → version bump (pyproject.toml + uv.lock) →
annotated tag vX.Y.Z → GitHub release with notes. Breaking changes wait for a major;
deprecations warn ≥ 1 minor first (current example: `--treat-timeout-as-kill`).
