# mutmut-win — Project Overview

<!-- PUBLICATION_STATE_START -->
<!-- PUBLICATION_STATE: external-live-check-required -->
Publication status for v2.21.1 is external mutable state. These immutable bytes assert neither presence nor absence; verify the exact annotated tag and matching GitHub release before use.
<!-- PUBLICATION_STATE_END -->

## Purpose
Windows-native mutation testing for Python, based on mutmut 3.5.0 (upstream explicitly
blocks Windows, mutmut#397). Replaces the Unix-only process layer (os.fork, RLIMIT_CPU,
SIGXCPU) with a spawn-based worker pool, Windows Job Objects (orphan protection: if the
parent dies, the kernel reaps every worker and pytest child) and a wall-clock timeout
model. The supported runtime is Windows with exactly CPython 3.14.7. Internal POSIX
paths carry no WSL/Linux runtime or CI-support commitment. Mutation engine, config
format and workflow stay mutmut-compatible.

Repo: https://github.com/pgm1980/mutmut-win.git
Distribution: install from a pinned git tag only
(`uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@vX.Y.Z" --dev`).
PyPI publishing is deliberately NOT part of the release sequence.
Leading install doc: `_config/mutmut-win-install.md` (referenced from CLAUDE.md);
the maintained documentation copy is `_docs/installation/mutmut-win-install.md`.

<!-- LIVE_STATE_START -->

<!-- RELEASE_PHASE: released -->
<!-- RELEASE_PHASE_STATUS: tagged-release-housekeeping-complete -->
<!-- RELEASE_TARGET: v2.21.1 -->
<!-- RELEASE_BRANCH: `main` -->
<!-- RELEASE_ROADMAP: bug_reporting/BUGFIXUNG_ROADMAP.md -->
<!-- RELEASE_PUBLICATION_AUTHORITY: canonical-external-block -->

<!-- LIVE_STATE_END -->

<!-- ARCHIVE_START -->

## Historical status (v2.14.0 baseline, 2026-06-13)
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

<!-- ARCHIVE_END -->

## Key capabilities (vs upstream mutmut)
- Operator profiles (v2.16.0+): `basic` = mutmut 3.5.0's 15 base operators; `advanced`
  (default, 34 registry entries / 29 unique funcs) adds the extras (regex, math method
  swaps, return-value replacement, conditional expressions, statement removal, collection
  methods, or-defaults) + the six v2.17.0 Phase-2 operators (ROR matrix, number CRCR,
  condition negate/force, collection-empty, match-guard); `all` adds the deliberately
  aggressive Phase-4 operators. See `current_state`.
- A stats run records a diagnostic test↔function mapping, but the collector cannot prove
  completeness across subprocesses, threads and native launchers. Every mutant therefore
  runs the full selected suite; cached mapping flags cannot create selective or `no tests`
  verdicts.
- Self-calibrating wall-clock timeouts: measured per-process startup floor + scaled
  full-suite runtime; the model is printed at run start.
- psutil-based infinite-loop classifier (CPU / output growth / process-status evidence,
  confidence bands, persisted forensics). On Windows the process-status signal does not
  exist → verdicts capped at `medium` confidence.
- Type checker as kill filter (`type_check_command`): mutants the checker rejects count
  as caught without running tests.
- Result reuse is permitted only when source, full selected tests, helpers, external
  configured fixtures, staged project, runtime and readable installed-distribution bytes
  share a complete content-bound execution basis; incomplete evidence disables reuse.
  `--rerun-all` opts out explicitly.
- Honest scoring: disjoint buckets (killed, survived, timeout, suspicious, skipped,
  no tests, segfault, type-check-caught, killed_by_infinite_loop); one score formula
  shared by run gate, `results` and CI export; interrupted runs exit 130 with no fake score.
  score = (killed + type-check + IL-killed + segfault) / (total − skipped − no tests − unchecked) × 100
- CI: `--min-score`, `--output json` (pure JSON on stdout, prose on stderr),
  `--since-commit REF`, `export-cicd-stats`.
- SQLite result cache (.mutmut-cache/), fingerprinted per-file mutant staging (mutants/).

## Tech stack
- Exactly CPython 3.14.7 on Windows; earlier Python versions and POSIX runtimes
  are unsupported. Package manager: uv; build backend: hatchling.
- Runtime deps: click (CLI), libcst (mutation engine), pydantic v2 (config/models),
  psutil (loop monitor), textual (TUI browser), coverage, setproctitle, pytest.
- Dev/QA: pytest, pytest-cov, pytest-asyncio, pytest-mock, pytest-benchmark, hypothesis,
  import-linter, mypy (strict), ruff, pip-audit; pinned Semgrep Community rules run
  through the tracked fail-closed offline release wrapper.
- Entry points: script `mutmut-win` = mutmut_win.cli:cli; `python -m mutmut_win` also
  works (__main__.py wraps cli and carries BWC re-exports for pre-v2.11.0 staging trees).
- 8 subcommands: run, results, show, apply, browse, tests-for-mutant, time-estimates,
  export-cicd-stats.
- Dogfooding: `[tool.mutmut]` in pyproject points at src/mutmut_win/ with tests_dir
  tests/unit/ — the tool mutation-tests itself as part of release gates.

## How a run works (pipeline)
1. Attempt & generate: a durable attempt precedes staging. libcst emits mutants behind a
   trampoline dispatcher into `mutants/`; exact source, mutation-universe, output and
   metadata digests govern transactional staging reuse.
2. Validate: clean suite must pass inside mutants/; a forced-fail check proves the
   trampoline switches mutants.
3. Map & budget: stats records per-test durations and a diagnostic map. Because mapping
   completeness is not provable, every mutant receives the full selected suite and a
   budget based on measured startup plus full-suite time.
4. Plan & execute: the exact universe is committed before spawn workers activate one
   mutant at a time via `MUTANT_UNDER_TEST`; mandatory Windows Job containment prevents
   escaped trees, and only planned results enter SQLite. Retained POSIX implementation
   paths are outside the supported runtime and carry no release-gate commitment.
Normal runs never modify original sources. The explicit `apply` command is the documented
exception: it backs up and atomically replaces the selected source file.

## Release policy
Demand-driven, no calendar cadence. Only on an explicit maintainer "Release" decision
after all gates pass: version bump on the release branch → final gates → merge to main →
integrated final gates → reproducible artifacts → annotated tag vX.Y.Z → GitHub
release with notes. Breaking changes wait for a major; deprecations warn ≥ 1 minor
first (current example: `--treat-timeout-as-kill`).
<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->
