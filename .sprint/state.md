---
current_sprint: "30"
sprint_goal: "v2.8.0 IL Detection Honesty — Forensik persistieren + rendern, CICD-IL-Bucket, Windows-Classifier ehrlich machen (echtes Output-Signal, neutraler Status, Confidence-Cap)."
branch: "feature/v2.8.0-il-honesty"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: true
github_issues_closed: false
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

## Nächster Schritt
**Warten auf User-„Release"**: Merge auf main, Version-Bump 2.8.0
(`uv lock --system-certs`!), annotated Tag, GitHub Release, Issues #85–#90
schließen sich via Merge, danach `github_issues_closed: true` +
`housekeeping_done: true`.

## Out of scope (Roadmap unverändert)
C6+C7 (Sprint 31 / v2.9.0), C8+C9-Top (Sprint 32 / v2.10.0), OS-014
(json score — C7), pip-audit-Baseline (Umgebungs-SSL).
