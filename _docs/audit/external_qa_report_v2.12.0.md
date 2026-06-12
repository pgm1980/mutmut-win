# mutmut-win v2.12.0 — 360° Test: Bug Report

**Tool under test:** mutmut-win v2.12.0 (Windows-native port of mutmut 3.5.0)
**Source:** `git+https://github.com/pgm1980/mutmut-win.git@v2.12.0`
**Test environment:** Windows 11 Pro (10.0.26200), Python 3.14.3, uv 0.11.6, PowerShell 7
**Test period:** 2026-06-12
**Methodology:** Black-box testing of the documented CLI contract (README.md and install guide as specification) plus white-box testing of attack surfaces identified through source analysis of `src/mutmut_win/`. All reproduction steps were executed in dedicated test projects under an isolated test directory.

**ID prefixes:** `DOC` documentation · `CLI` CLI contract · `CFG` configuration · `MUT` mutation engine · `SCO` scoring/classification · `RUN` run pipeline · `WIN` Windows specifics

## Executive summary

mutmut-win v2.12.0 is solid at its core: the mutation engine, parallel execution, scoring math, result persistence, and Windows-specific hardening all held up under deliberate stress. The score is identical across all four reporting channels (`run`, `results`, `export-cicd-stats`, `--output json`), the 22-operator set generates correctly, the trampoline dispatch is correct, and paths with spaces/Unicode, cp1252 consoles, oversized command lines, and corrupted cache files are all handled without crashing. No correctness defect in the score itself was found.

The 15 findings are concentrated in **documentation accuracy**, **input validation / exit codes**, and **a few silent-exclusion gaps in the mutation surface**. None corrupts results; the most user-visible are:

- **MUT-001 (Medium)** — functions whose only mutable content is an f-string are silently dropped from the mutation surface (no mutants, invisible in every report).
- **RUN-002 (Medium)** — `--paths-to-mutate` subset runs silently purge results for all other paths, undermining the README's recommended "targeted run" workflow.
- **CLI-002 / CFG-001 (Medium)** — a mistyped path exits 0 (reports success while testing nothing), and invalid `[tool.mutmut]` values exit 1 with a raw traceback instead of the documented exit 2.
- **RUN-001 (Medium)** — the README's "unchanged mutants are not re-run" caching claim is not implemented; every run re-executes every mutant.

The remaining items are Low (documentation drift, message wording, an unreachable status, presentation inconsistencies). **WIN-001** is the only unconfirmed item — raised from code evidence because live reproduction risked hanging the host. Counts: **6 Medium, 9 Low — no Critical, no High.** One Low item (WIN-001) is unconfirmed (code-evidenced only). Full breakdown below; **What works** (positive confirmations) is documented near the end.

## Severity scale

| Severity | Meaning |
|----------|---------|
| Critical | Data loss, corrupted results, or a wrong score presented as correct |
| High     | Feature broken/unusable, or results that mislead the user |
| Medium   | Incorrect behavior with a workaround; docs that block or mislead first use |
| Low      | Cosmetic issues, minor doc drift, UX friction |

## Findings summary

| ID | Severity | Component | Title | Status |
|----|----------|-----------|-------|--------|
| DOC-001 | Medium | README / packaging | README advertises PyPI installation, but the package is not published on PyPI | Confirmed |
| RUN-001 | Medium | run pipeline / caching | README claims "unchanged mutants are not re-run", but every run re-executes all mutants | Confirmed |
| SCO-001 | Low | export-cicd-stats output | Console line "Score: 71.4% (40 killed / 78 total)" implies the wrong denominator | Confirmed |
| DOC-002 | Low | staging / docs | The entire project root is mirrored into `mutants/`, but docs only describe the `also_copy` defaults | Confirmed |
| RUN-002 | Medium | run pipeline / result cache | `--paths-to-mutate` subset runs purge all results outside the given paths (name-pattern subset runs preserve them) | Confirmed |
| CLI-001 | Low | `run --min-score` validation | `--min-score` accepts out-of-range values (150, −5): full run executes, then the gate trivially fails/passes | Confirmed |
| CLI-002 | Medium | `run --paths-to-mutate` validation | Non-existent path yields "No mutants generated." with exit 0 instead of a configuration error (exit 2) | Confirmed |
| CLI-003 | Low | `apply` error handling | Staleness rejection surfaces as a raw 25-line traceback instead of a clean CLI error (without `--debug`) | Confirmed |
| CFG-001 | Medium | config loading / exit codes | Invalid `[tool.mutmut]` values exit 1 with a 47-line traceback — documented contract is exit 2, and CLI flags with the same rules correctly exit 2 | Confirmed |
| CFG-002 | Low | `do_not_mutate` validation | Exclusion patterns that match nothing are silently ignored (a typo silently re-enables mutation of "excluded" files) | Confirmed |
| MUT-001 | Medium | mutation engine | Functions whose only mutable content is an f-string are silently excluded from mutation entirely (no trampoline, no mutants, invisible in all reports) | Confirmed |
| SCO-002 | Low | status model / docs | The documented `skipped` status is unreachable — no code path emits exit 34; `@pytest.mark.skip` targets become `no tests` | Confirmed |
| SCO-003 | Low | `results` output | `results` folds `caught by type check` into the "Killed" count (no separate line), disagreeing with the `run` summary and CI JSON for the same DB | Confirmed |
| MUT-002 | Low | mutation engine / messaging | A single valid-but-unmanglable identifier (U+01C1) makes the whole file silently skipped, reported as "Unsupported syntax" though the code is valid Python | Confirmed |
| WIN-001 | Low | worker subprocess / Windows | Worker spawns pytest without WER suppression — a hard-crashing mutant may stall on the Windows Error Reporting dialog and be misclassified `timeout` instead of `segfault` | Unconfirmed (code-evidenced) |

---

## DOC-001 — README advertises PyPI installation, but the package is not published on PyPI

- **Severity:** Medium
- **Component:** README.md, "Installation" section
- **Affected version:** v2.12.0 (README shipped with the release)
- **Status:** Confirmed 2026-06-12

### Description

The README "Installation" section instructs:

```bash
pip install mutmut-win
# or
uv add mutmut-win --dev
```

Both commands fail because `mutmut-win` is not published on PyPI. The README even contradicts itself: the "Release policy" section in the same document states *"PyPI publishing is not part of that sequence."*

### Reproduction

```powershell
Invoke-RestMethod -Uri "https://pypi.org/pypi/mutmut-win/json"
```

### Expected

The installation commands in the README work as documented, or the README documents the actual (Git-based) installation channel.

### Actual

```
PyPI: 404 (Not Found) — package does not exist on PyPI
```

`pip install mutmut-win` / `uv add mutmut-win --dev` therefore fail with "no matching distribution". A new user's very first contact with the tool fails.

### Suggested fix

Replace the Installation section with the Git-based channel that the release policy actually supports, pinned to a release tag:

```bash
pip install "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.12.0"
# or
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.12.0" --dev
```

Alternatively, publish to PyPI and add that step to the release sequence — either resolution removes the internal contradiction between "Installation" and "Release policy".

---

## RUN-001 — README claims "unchanged mutants are not re-run", but every run re-executes all mutants

- **Severity:** Medium
- **Component:** `run` pipeline (orchestrator), result cache usage
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12 (dynamic + static evidence)

### Description

The README ("What it does" → *Caches aggressively*) states:

> "Results live in SQLite, per-file mutant staging is fingerprinted (source + configuration) — unchanged files are not regenerated, **unchanged mutants are not re-run**."

The first half is true (staging regeneration is skipped via fingerprints). The second half is not: the result cache is **write-only** for `run`. Existing results are never consulted before dispatch, so every run re-executes every dispatchable mutant — even back-to-back runs with zero changes.

### Reproduction

In a project with a green suite and `[tool.mutmut]` configured (74 mutants, 56 dispatchable):

```powershell
uv run mutmut-win run   # run A: completes, 56 mutants executed, results in SQLite
uv run mutmut-win run   # run B: immediately afterwards, NO changes of any kind
```

### Expected

Run B detects that all mutants are unchanged and already have results, skips execution (or re-runs nothing), and reports the cached outcome quickly.

### Actual

Run B re-executes all 56 mutants (progress counts 1/56 … 56/56) and takes essentially the same wall-clock time as run A (5.9s vs 5.8s; on real projects this scales to the full mutation cost on every invocation).

### Evidence (static)

`db.load_results()` is referenced only by `cli.py` (`results`, `show`, `time-estimates`, `export-cicd-stats`) and `browser.py`. `orchestrator.py` only ever *writes* results (`save_result` for type-check kills, no-tests verdicts, and task completions). The only fingerprint check in the orchestrator is `config_fingerprint_matches` (orchestrator.py:481), and it gates **generation** only (`allow_fast_path` — whether to regenerate staging files); after generation every mutant name becomes a dispatched `MutationTask` regardless of any prior result. There is no code path that reads prior results to skip unchanged mutants before dispatch.

### Suggested fix

Either implement the documented behavior (before dispatch, drop tasks whose mutant fingerprint is unchanged and whose DB row holds a completed verdict — with an opt-out flag like `--rerun-all`), or correct the README/install-guide claim to "unchanged files are not re-**generated**" only.

---

## SCO-001 — `export-cicd-stats` console output implies the wrong score denominator

- **Severity:** Low
- **Component:** `export-cicd-stats` console output (`cli.py:670`)
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

The console summary printed by `export-cicd-stats` reads:

```
Score: 71.4%  (40 killed / 78 total)
```

40/78 = 51.3%, not 71.4%. The actual score formula (correctly implemented and correctly exported in the JSON) divides by `total − skipped − no tests − unchecked` = 56. Printing "40 killed / 78 total" directly next to the score invites the reader to verify the score with the wrong division and conclude the tool miscalculates.

### Reproduction

Project state: 78 total, 40 killed, 22 no tests, 16 survived (denominator 56).

```powershell
uv run mutmut-win run; uv run mutmut-win export-cicd-stats
```

### Expected

A breakdown consistent with the formula, e.g. `Score: 71.4% (40 of 56 scoreable mutants killed)` — or no parenthetical at all (like `run`'s summary and `results`).

### Actual

`Score: 71.4%  (40 killed / 78 total)` — the JSON file itself is correct and internally consistent.

### Suggested fix

In `cli.py:670`, print the scoreable denominator instead of raw total, e.g. `f"Score: {cicd.score:.1f}%  ({effective_killed} killed / {denominator} scoreable)"`.

---

## DOC-002 — Entire project root is mirrored into `mutants/`, but docs only describe `also_copy` defaults

- **Severity:** Low
- **Component:** staging (`file_setup.copy_src_dir`), README/install-guide
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

User-facing docs describe staging as: `paths_to_mutate` + `also_copy` (documented auto-defaults: `tests/`, `test/`, `setup.cfg`, `pyproject.toml`, `pytest.ini`, `.gitignore`, `test*.py`). In reality, `copy_src_dir()` deliberately mirrors **all files from the source roots `src/`, `source/`, and `.`** (the entire project root, minus a fixed skip list: `.venv`, `.git`, caches, `mutants/`, …) into `mutants/`. The docstring documents this; the user docs do not.

Observed consequences in the test project: `uv.lock` and two unrelated scratch files (`_stdout.txt`, `_stderr.txt`) appeared in `mutants/`, and subsequent runs printed `updated: _stdout.txt (source changed since last run)` for files that are not sources at all.

### Why it matters

- Surprise: secrets/config files in the project root (e.g. `.env`) are silently copied into `mutants/`.
- Cost: projects with large root-level assets (data dumps, media, docs builds) pay copy time and disk on every run.
- Confusing UX: "source changed since last run" messages for non-source files.

### Reproduction

```powershell
New-Item scratch.bin -ItemType File; uv run mutmut-win run --dry-run  # dry-run is clean, but:
uv run mutmut-win run                                                # scratch.bin appears in mutants\
Get-ChildItem mutants | Select-Object Name
```

### Expected

Docs state that the whole project tree (minus skip list) is mirrored — or staging copies only `paths_to_mutate` + `also_copy` as documented.

### Actual

Whole-root mirroring (by design per code docstring), undocumented for users.

### Suggested fix

Document the actual staging rule in README ("Staging copies your whole project tree except …") and consider an exclude option (e.g. honoring `.gitignore` or a `do_not_copy` config key) for large/sensitive root content.

---

## RUN-002 — `--paths-to-mutate` subset runs purge all results outside the given paths

- **Severity:** Medium
- **Component:** `run` pipeline — stale-result purging vs. subset semantics
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

Subset runs filtered by **mutant name pattern** correctly preserve unrelated DB results. Subset runs filtered by **`--paths-to-mutate`** do not: changing `paths_to_mutate` regenerates the staging for the new path set only, and the stale-result purge then deletes every DB row whose mutant no longer exists in staging — i.e. all results for the paths *not* listed.

This hits the officially recommended workflow ("run `--paths-to-mutate <changed module>` after each feature", README "Targeted" workflow): after a cheap module-scoped run, the expensive full-project results are gone, and `results`/`export-cicd-stats` silently report numbers for the subset only.

### Reproduction

```powershell
uv run mutmut-win run                                          # full run: results = 74 mutants
uv run mutmut-win run "refproj.textutils.x_truncate*"          # name-pattern subset
uv run mutmut-win results                                      # still Total: 74  ✓ (preserved)
uv run mutmut-win run --paths-to-mutate src/refproj/calc.py    # path subset (38 mutants)
uv run mutmut-win results                                      # Total: 38  ✗ (36 results purged)
```

### Expected

Path-scoped subset runs preserve results outside the scope, consistent with name-pattern subset runs — or at minimum a loud warning that N existing results are about to be discarded.

### Actual

`results` shows `Total: 38` after the path-scoped run; the 36 results for `textutils.py`/`untested.py` are deleted without any notice.

### Suggested fix

Treat a `--paths-to-mutate` override (narrower than the configured `paths_to_mutate`) as a subset run for purge purposes (`purge_stale_results=False`), mirroring the name-pattern logic. Purging is only safe when the staging covers the full configured mutation surface.

---

## CLI-001 — `--min-score` accepts out-of-range values

- **Severity:** Low
- **Component:** `run --min-score` option validation
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

`--min-score` is documented as a percentage gate. Values outside [0, 100] are accepted without complaint: the full (potentially hours-long) mutation run executes first, and only then does the gate evaluate — failing unconditionally for >100, passing unconditionally for <0. Other numeric options (`--timeout-multiplier 0`, `--max-children 0`) are correctly rejected upfront with exit 2, so the tool already has the validation pattern; `--min-score` just lacks the range constraint.

### Reproduction

```powershell
uv run mutmut-win run --min-score 150   # full run executes, then exit 1:
                                        # "Mutation score 71.4% is below threshold 150.0%"
uv run mutmut-win run --min-score -5    # full run executes, gate always passes, exit 0
```

### Expected

Exit 2 ("invalid configuration or option value") before any work, e.g. "min-score must be between 0 and 100".

### Actual

Full run executes; threshold 150 can never pass (likely a typo for 15.0), threshold −5 makes the gate a no-op.

---

## CLI-002 — Non-existent `--paths-to-mutate` path: silent success (exit 0) instead of configuration error

- **Severity:** Medium
- **Component:** `run --paths-to-mutate` / config validation
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

Pointing `--paths-to-mutate` at a path that does not exist produces `No mutants generated.` and **exit 0**. A non-existent path is a configuration error (typo) per the documented exit-code contract ("2 — invalid configuration or option value") and should fail loudly. Without a `--min-score` gate, a CI job with a typo in the path reports success while testing nothing.

Positive note: *with* `--min-score`, the gate correctly fails closed ("No testable mutants — score gate failed closed", exit 1) — the same fail-closed reasoning should apply to the path itself.

Side effect: the run still rewrites the configuration fingerprint ("Configuration changed — regenerating all mutants."), so the next regular run regenerates the full staging.

### Reproduction

```powershell
uv run mutmut-win run --paths-to-mutate does_not_exist/
echo $LASTEXITCODE   # 0
```

### Expected

Exit 2 with an error naming the missing path (matching the validation behavior of other options).

### Actual

`No mutants generated.` — exit 0.

---

## CLI-003 — `apply` staleness rejection surfaces as a raw traceback

- **Severity:** Low
- **Component:** `apply` / `mutant_diff.apply_mutant` error handling
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

The staleness check itself works as documented (README: "backup + atomic write + staleness check"): applying a mutant after the source file changed is correctly refused with exit 1. However, the refusal is presented as an **unhandled `RuntimeError` traceback** (~25 lines of Click/runpy internals) instead of the one-line error style used by every other error path (`show`/`run` errors print a clean red message). The documented contract is that full tracebacks appear only with `--debug`.

The actual message — buried at the bottom of the traceback — is good: `src\refproj\textutils.py changed after its mutants were generated — re-run 'mutmut-win run' before applying mutants.`

### Reproduction

```powershell
uv run mutmut-win run                  # generate staging
Add-Content src\refproj\textutils.py "`n# any change"
uv run mutmut-win apply refproj.textutils.x_truncate__mutmut_1
```

### Expected

```
src\refproj\textutils.py changed after its mutants were generated — re-run 'mutmut-win run' before applying mutants.
```
(one line, red, exit 1; traceback only with `--debug`)

### Actual

`RuntimeError` traceback through `cli.py:547` / `mutant_diff.py:402`, exit 1.

### Suggested fix

Raise a `MutmutWinError` subclass (handled by the CLI's error formatter) instead of `RuntimeError` in `apply_mutant`, or catch `RuntimeError` in the `apply` command.

---

## CFG-001 — Invalid `[tool.mutmut]` values exit 1 with a raw traceback instead of exit 2

- **Severity:** Medium
- **Component:** config loading (`config.load_config`) / CLI error handling / exit-code contract
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

The documented exit-code contract is: `2 — invalid configuration or option value`. This holds for CLI options (`--timeout-multiplier 0`, `--max-children 0` → clean Click error, exit 2). The **same validation rules** triggered through `pyproject.toml`, however, exit **1** and print a full unhandled traceback (47 lines through Click/pydantic internals, without `--debug`).

The pydantic messages themselves are excellent (e.g. for `max_stack_depth = 0`: *"would discard every stats hit (every mutant would run the full suite) — use -1 for unlimited or a positive depth"*; for absolute paths outside the project a clear explanation of the staging-overwrite risk). They are just wrapped in the wrong presentation and the wrong exit code.

Impact: CI systems that distinguish "score gate failed / runtime error" (1) from "broken configuration" (2) misclassify configuration mistakes.

### Reproduction

```powershell
# pyproject.toml: [tool.mutmut] max_children = "viele"   (or max_stack_depth = 0,
# or paths_to_mutate = ["C:/Windows/Temp/"])
uv run mutmut-win run --dry-run
echo $LASTEXITCODE   # 1, with full InvalidConfigValueError traceback
uv run mutmut-win run --max-children 0
echo $LASTEXITCODE   # 2, clean one-line error — inconsistent with the above
```

### Expected

Exit 2 and the same compact error presentation as CLI option errors; traceback only with `--debug`.

### Actual

Exit 1, 47-line traceback ending in `mutmut_win.exceptions.InvalidConfigValueError: Invalid [tool.mutmut] configuration: …`.

### Suggested fix

Catch `InvalidConfigValueError` (and config-stage `MutmutWinError`s generally) in the CLI layer, print `e` compactly, and exit 2.

---

## CFG-002 — `do_not_mutate` patterns that match nothing are silently ignored

- **Severity:** Low
- **Component:** `do_not_mutate` handling
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

Unknown config **keys** produce a did-you-mean warning (good). A `do_not_mutate` **pattern** that matches no file produces no output at all. A typo in an exclusion glob (e.g. `**/migration/*` vs `**/migrations/*`) therefore silently re-enables mutation of files the user intended to exclude — the opposite of the configured intent, discoverable only by noticing unexpected mutants.

### Reproduction

```powershell
# pyproject.toml: do_not_mutate = ["**/nothing_matches.py"]
uv run mutmut-win run --dry-run
# Output: "Dry run: 78 mutants would be generated." — no warning, exit 0
# Control: do_not_mutate = ["**/calc.py"] correctly reduces the count (40).
```

### Expected

A warning such as `do_not_mutate pattern '**/nothing_matches.py' matched no files` (mirroring the unknown-key warning).

### Actual

Silence; pattern is a no-op.

---

## MUT-001 — Functions whose only mutable content is an f-string are silently excluded from mutation

- **Severity:** Medium
- **Component:** mutation engine — `operator_string`, `operator_return_value` (one of the 7 mutmut-win-specific operators)
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12 (dynamic + static + upstream comparison)

### Description

A function like

```python
def fstring_with_spec(value):
    return f"{value:>10.2f}"
```

produces **zero mutants**. It is not trampolined, gets no `__mutmut_orig` copy, and appears in no statistic — not as `survived`, not as `no tests`. The user has no way to notice that this function is entirely outside the mutation scope. Formatting helpers (`return f"{price:.2f} EUR"`) are precisely the kind of code where mutation testing of format specs and literal parts would be valuable — and they are common in modern Python.

Two interacting causes:

1. `operator_string` (node_mutation.py:47) mutates only `cst.SimpleString` — `cst.FormattedString` literal parts are never mutated. *This limitation is inherited from upstream mutmut 3.5.0 (verified against the published 3.5.0 source, node_mutation.py:32 has the same `isinstance(node, cst.SimpleString)` guard).*
2. `operator_return_value` (node_mutation.py:486) skips every `cst.BaseString` return with the justification "literal values … are **already mutated by other operators**". For `FormattedString` (a `BaseString` subclass) that justification is false — no other operator touches it. *This operator is mutmut-win-specific, so this half is not inherited.*

When a function contains other mutable code, only the f-string stays unmutated (confirmed: a mixed function produced mutants for its arithmetic but none inside the f-string). When the f-string is the only mutable content, the function silently vanishes from the mutation surface.

### Reproduction

```python
# src/ops/probe.py
def fstring_only(name):
    return f"hi {name}!"
```

```powershell
uv run mutmut-win run
# fstring_only: no mutants, no trampoline in mutants\src\ops\probe.py,
# absent from results --all; bytes literals (b"raw") by contrast ARE mutated.
```

### Expected

At minimum, `return f"..."` should yield the standard return-value replacement (`return None`) so the function stays inside the mutation surface. Ideally, f-string literal parts (and/or conversion/format specs) are mutated like plain string literals.

### Actual

Zero mutants; the function is invisible to every report and never contributes to the score denominator.

### Suggested fix

Exclude `cst.FormattedString` from the `BaseString` skip in `operator_return_value` (one-line change, fixes the invisibility). Optionally add an f-string literal-part mutation (XX-wrap of `FormattedStringText` parts) as an engine extension.

---

## SCO-002 — Documented `skipped` status is unreachable in v2.12.0

- **Severity:** Low
- **Component:** status model (`constants.EXIT_CODE_SKIPPED`) / README "Result statuses" table
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12 (dynamic + static)

### Description

The README lists `skipped` ("Excluded from this run") as one of the nine result statuses, and every score consumer subtracts `skipped` from the denominator. But **no code path ever assigns a mutant the `skipped` status or exit code 34.** `EXIT_CODE_SKIPPED = 34` is defined in constants.py and consumed in the summary/score aggregation, yet the worker never produces it (it returns pytest's real exit code, and pytest never exits 34).

Consequently a mutant whose only covering test is `@pytest.mark.skip` is **not** reported as `skipped`. Empirically it becomes `no tests`: the skipped test records no trampoline hit during the stats run, so the mutant maps to zero tests.

### Reproduction

```python
# test file
@pytest.mark.skip(reason="...")
def test_skip_marked():
    assert probe.skip_marked() == 42
```

```powershell
uv run mutmut-win run --force
uv run mutmut-win results --all
# statuses.probe.x_skip_marked__mutmut_1: no tests   (never "skipped")
# Summary: "Skipped: 0" in every run.
```

Static confirmation: a tree-wide search for producers of exit 34 / status `"skipped"` finds only the constant definition and the consumers (summary counter, score denominator) — no emitter.

### Expected

Either the engine emits `skipped` where documented (e.g. for `@pytest.mark.skip`-only mutants, or `--ignore`d ones), or the README/status list drops `skipped` as a reachable status.

### Actual

`skipped` is always 0; the category is effectively dead. Harmless to the score (the bucket is always empty) but misleading in the documented status model.

---

## SCO-003 — `results` folds `caught by type check` into "Killed", disagreeing with the run summary

- **Severity:** Low
- **Component:** `results` console rendering (`cli.py`) vs. run summary (`orchestrator.py`)
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12

### Description

For one and the same cache DB, the "Killed" number differs between commands:

- The **`run` summary** prints `Killed` (plain kills incl. infinite-loop) and a **separate `Type-check` line**.
- **`results`** prints `Killed: <killed + type-check + infinite-loop>  (incl. N infinite-loop)` and **no `Type-check` line at all** — `caught by type check` is in the `aggregated` set excluded from the per-status loop (cli.py:420-423), so it is silently merged into "Killed", and the annotation mentions only the infinite-loop part.

The score is identical and correct across both (and the CI JSON), so this is presentation-only. But a user reconciling `run` and `results` sees the killed count change (e.g. 5 → 6) and the type-check category vanish.

### Reproduction

Project with 1 type-check-caught mutant, 1 infinite-loop kill, 4 plain kills (15 total):

```powershell
uv run mutmut-win run --force
# Summary:  Killed: 5   Type-check: 1   (Score 46.2%)
uv run mutmut-win results
# Total: 15 / Killed: 6  (incl. 1 infinite-loop) / (no Type-check line) (Score 46.2%)
uv run mutmut-win export-cicd-stats   # killed=5, caught_by_type_check=1 (separate, like run)
```

### Expected

Consistent category presentation across `run`, `results`, and the CI JSON — e.g. `results` shows a separate `Type-check:` line and keeps it out of the "Killed" number (matching the run summary and JSON), or all three adopt one scheme.

### Actual

`run` and the CI JSON keep `caught by type check` separate; `results` folds it into "Killed" without annotation and shows no type-check line.

---

## MUT-002 — One unmanglable identifier silently drops the whole file, mislabelled "Unsupported syntax"

- **Severity:** Low
- **Component:** mutation engine fallback (`file_setup.py:631-636`)
- **Affected version:** v2.12.0
- **Status:** Confirmed 2026-06-12 (partly by design, issue #78)

### Description

The mangling separator `ǁ` (U+01C1) is a **valid Python identifier character** (`"funcǁname".isidentifier()` is `True`), so a function may legitimately contain it. The mangler guard correctly refuses such a name, and `create_mutants_for_file` catches the `ValueError` and copies the file unchanged. Two rough edges:

1. **Whole-file granularity.** One offending function disables mutation for the **entire file**. A normal neighbour function in the same file gets zero mutants — silent coverage loss beyond the one-line warning (`run` still exits 0).
2. **Misleading wording.** The warning is a `SyntaxWarning` reading `Unsupported syntax in <file> (Function name must not contain 'ǁ': 'funcǁname'), skipping`. The code is valid Python; the limitation is mutmut-win's internal mangling, not a syntax error. A user may wrongly conclude their source is broken.

The run as a whole is robust — other files mutate normally and the run does not abort (verified). This is the same silent-exclusion family as MUT-001: the dropped code never enters the score denominator.

### Reproduction

```python
# src/pkg/separator.py
def funcǁname(x):      # U+01C1 — valid identifier
    return x + 1

def normal_neighbor(y):  # ordinary function
    return y * 2
```

```powershell
uv run mutmut-win run --force
# Warning: Unsupported syntax in src\pkg\separator.py (Function name must not contain 'ǁ': 'funcǁname'), skipping
# normal_neighbor: 0 mutants (whole file skipped), exit 0
```

### Expected

Skip only the offending function (mutate the rest of the file), and word the warning as an engine limitation, e.g. `cannot mutate <file>: identifier 'funcǁname' collides with the internal mangling separator (U+01C1); file left unmutated`.

### Actual

Whole file skipped; `SyntaxWarning: Unsupported syntax …` on valid Python.

---

## WIN-001 — Worker spawns pytest without Windows Error Reporting suppression (segfault may stall / misclassify)

- **Severity:** Low
- **Component:** `process/worker.py` subprocess spawn
- **Affected version:** v2.12.0
- **Status:** Unconfirmed — code-evidenced; live crash deliberately not provoked (see below)

### Description

The worker launches each mutant's pytest run with:

```python
proc = subprocess.Popen(cmd, env=env, stdout=log_fd, stderr=subprocess.STDOUT, cwd="mutants")
```

There is no `creationflags` (e.g. `CREATE_NO_WINDOW`) and no error-mode suppression (`SetErrorMode`/`SEM_NOGPFAULTERRORBOX`) anywhere in the worker or its child. On a Windows host where Windows Error Reporting UI is enabled (`HKLM\…\Windows Error Reporting\DontShowUI` not set to 1 — the default on interactive workstations, and the state on this test host), a mutant that triggers a genuine hard crash (access violation `0xC0000005`, stack overflow `0xC00000FD`, …) can cause **WerFault.exe** to hold the crashing process while it collects a dump or shows a dialog.

If WerFault holds the process past the task's wall-clock budget, the worker's `proc.wait(timeout)` fires first, the job object reaps the tree, and the mutant is recorded as **`timeout`** (or possibly `killed_by_infinite_loop`) instead of **`segfault`**. Both are still "detections" for the score, but the diagnostic category is wrong, and the run is slowed by the full budget per crashing mutant.

On headless CI (where WER UI is typically disabled), `proc.wait()` returns immediately with the NTSTATUS exit code and the `segfault` classification works correctly (verified by code inspection of `constants.status_by_exit_code`: `0xC0000005 / 0xC00000FD / 0xC0000409 → segfault`).

### Why "Unconfirmed"

A live hard crash was **intentionally not forced** on the test host: with WER UI not suppressed and `LocalDumps` configured, a real access violation / stack overflow risks hanging the worker on WerFault (observed: a standalone deep-recursion crash attempt stalled and had to be killed). Confirming the misclassification would require either suppressing WER machine-wide (an unwarranted system change) or accepting a hang. The classification mapping itself is correct; only the live Windows interaction is unverified.

### Suggested fix

In the worker, spawn the child with error-mode suppression so crashes return immediately as NTSTATUS codes on every host: pass `creationflags=subprocess.CREATE_NO_WINDOW` and have the child set `SetErrorMode(SEM_NOGPFAULTERRORBOX | SEM_FAILCRITICALERRORS)` (or set `SEM_NOGPFAULTERRORBOX` in the worker before spawning, which children inherit). This makes the documented `segfault` status reliable on interactive Windows hosts too.

### Note for the maintainer

This is the one item in this report I could not reproduce end-to-end. It is raised because mutmut-win is a Windows-first tool and the code path is unambiguous (no WER handling); please treat it as a lead to verify on a host with WER UI enabled, not as a confirmed defect.

---

## What works (positive confirmations)

These were actively tested and held up — recorded so the maintainer knows the report is not silent on them:

- **Score integrity.** The score is identical across all four channels — `run` summary, `results`, `export-cicd-stats` JSON, and `--output json` (verified at 71.4% and 46.2% on two projects). The kill-class formula and the `total − skipped − no_tests − unchecked` denominator match the README.
- **`--output json` stream hygiene.** stdout carries *pure* JSON (parses cleanly); all prose goes to stderr.
- **Exit-code contract.** `0` success, `1` score-gate/runtime, `2` invalid option *value* (`--timeout-multiplier 0`, `--max-children 0`, unknown option with did-you-mean), `130`-style fail-closed gate when nothing is testable. Empty-DB asymmetry holds: `results`/`time-estimates` exit 0, `export-cicd-stats` exits 1.
- **Mutation engine.** All operator classes generate (149 mutants on a one-function-per-operator probe): arithmetic, comparison, boolean, identity/membership, numbers, strings, f-string *text vs* skip, lambdas, keywords, arg-removal, match/case, augmented-assign, slicing, unary, plus the 7 extras (regex, math-method swap, return-value, conditional-expr, statement removal, collection methods, or-default). Trampoline dispatch via `MUTANT_UNDER_TEST` verified mutant-by-mutant.
- **Status classes.** 8 of 9 reachable statuses provoked and observed directly (`killed`, `survived`, `no tests`, `timeout`, `suspicious`, `caught by type check`, `killed_by_infinite_loop`, and `no tests` for skip-marked); `segfault` verified by code mapping (see WIN-001); `skipped` is unreachable (SCO-002).
- **`pragma: no mutate`** is respected (0 mutants on the pragma'd line). **`len()`/`isinstance()`** call semantics are protected from mutation.
- **Class methods & nested classes** mangle and dispatch correctly via the `xǁClassǁmethod` scheme.
- **`apply`** writes atomically with a `.mutmut-orig.bak` backup and a real staleness check (refuses to apply when the source changed after generation).
- **Name-pattern subset runs** (`run "pkg.mod.x_fn*"`) preserve DB results for all other mutants (contrast RUN-002 for path subsets).
- **`do_not_mutate` globs**, **absolute-path rejection** (outside project root), and **`max_stack_depth = 0` rejection** all work with clear messages.
- **Resilience.** Corrupted/truncated/empty `.meta` files trigger a "rebuilding from scratch" warning, never a crash (`results` reads SQLite and is immune). Unparseable/un-mutatable files are skipped without aborting the run.
- **Windows specifics.** cp1252 redirected console degrades emoji to `?` with no `UnicodeEncodeError` (issue #103); a project path containing a space *and* an umlaut runs end-to-end (100% score); ~1600 test node-IDs (~72 KB, well past the 32767-char `CreateProcess` limit) are carried via the `@argfile` mechanism with all mutants still killed.

## Test coverage

| Area | Coverage | Projects used |
|------|----------|---------------|
| CLI contract (8 commands, all `run` flags) | Full | refproj |
| Configuration matrix (keys, typos, invalid values, setup.cfg, precedence) | Full | refproj |
| 22 mutation operators | Full (generation verified per class) | operators |
| 9 status classes + 4-way score consistency | 8/9 live, 1 by code (segfault) | statuses |
| White-box surfaces (pragma, never-mutate, methods, nesting, Unicode, U+01C1, corrupt cache) | Full | edgecases |
| Windows specifics (cp1252, spaced/umlaut path, argfile) | Full | refproj, "pfad mit leerzeichen ä" |
| `browse` TUI | Smoke (renders, non-interactive headless check only) | refproj |
| Infinite-loop classifier confidence bands | Partial (verdict reached; confidence-band edges not exhaustively swept) | statuses |
| Job-object orphan reaping under parent kill | Not tested (would require killing a live run mid-flight) | — |
| Live hard-crash → segfault classification | Not tested (WerFault hang risk — see WIN-001) | — |

### Environment note

`uv` on the test host required `--system-certs` for every network operation (corporate TLS interception); this is environmental, not a mutmut-win issue. mutmut-win was installed from `git+https://github.com/pgm1980/mutmut-win.git@v2.12.0` (the package is not on PyPI — DOC-001).
