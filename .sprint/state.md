---
current_sprint: "30"
sprint_goal: "v2.8.0 IL Detection Honesty — Forensik persistieren + rendern, CICD-IL-Bucket, Windows-Classifier ehrlich machen (echtes Output-Signal, neutraler Status, Confidence-Cap)."
branch: "feature/v2.8.0-il-honesty"
started_at: "2026-06-11"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 30 opened 2026-06-11)

## Current Focus
Sprint 30 — **v2.8.0 IL Detection Honesty** — **implementation complete**
(all 6 items, 25/25 SP). Commits on `feature/v2.8.0-il-honesty`:

| Issue | Commit | Inhalt |
|-------|--------|--------|
| #85 | `dfb9041` | Forensik-Persistenz (orchestrator → save_result) + Exit-Code-Konstanten |
| #86 | `5764d5d` | CICD-IL-Bucket + Drei-Kanal-Konsistenz (66,7 % statt 33,3 %) |
| #87 | `b038edc` | `show`-Forensik-Panel (NULL-safe) + Browser-IL (Map = constants-Alias, `_KILL_STATUSES`, `_describe_mutant`) |
| #88 | `519d014` | Classifier-Ehrlichkeit (12-Schritt-CoT): `status_signal_available`, Confidence-Cap medium, PYTHONUNBUFFERED, Sample-Floor 5, None-Output, Sampler-Catch-All, gt=0, Hygiene |
| #89 | `cf11a57` | io_counters: als Sleeping-Ersatz widerlegt, als Progress-Veto eingebaut (Spike-Daten im Audit-Doc) |
| #90 | `787633f` | Test-/Doku-Ehrlichkeit: ratio isoliert, plattform-exakte Asserts, Marketing-Prosa entfernt |

Gates: **719 passed / 4 skipped** (+38 neue), ruff 0, mypy 26 pre-existing /
0 neue, semgrep src 0 Findings (tests von Semgrep-Default-Ignore
übersprungen — vermerkt), lint-imports KEPT (in-suite).

## Release — DONE 2026-06-11
v2.8.0 released: Merge `ba4f545` (closes #85–#90, verifiziert 0 offene
Issues), Bump `78f01cc`, annotated Tag `v2.8.0`, GitHub Release
https://github.com/pgm1980/mutmut-win/releases/tag/v2.8.0. Suite auf
gemergtem main erneut 719 passed / 4 skipped. Sprint 30 vollständig
abgeschlossen, alle Housekeeping-Items erledigt.

## Vorgemerkt für Sprint 32 (C8, User-bestätigt)
Drei Pipeline-Hygiene-Neuzugänge im Audit-Register: repo-weites
ruff-format-Gate, pytest-Kanon (`--ignore=tests/e2e_projects`)
config-verankern, semgrep-Default-Ignore für `tests/` explizit entscheiden.

## Out of scope (Roadmap unverändert)
C6+C7 (Sprint 31 / v2.9.0), C8+C9-Top (Sprint 32 / v2.10.0), OS-014
(json score — C7), pip-audit-Baseline (Umgebungs-SSL).
