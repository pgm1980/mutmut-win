---
current_sprint: "30"
sprint_goal: "v2.8.0 IL Detection Honesty — Forensik persistieren + rendern, CICD-IL-Bucket, Windows-Classifier ehrlich machen (echtes Output-Signal, neutraler Status, Confidence-Cap)."
branch: "feature/v2.8.0-il-honesty"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 30 opened 2026-06-11)

## Current Focus
Sprint 30 — **v2.8.0 IL Detection Honesty** — planned, implementation not
started. Basis: audit cluster **C5**. The v2.5 flagship feature finally
delivers: forensics get persisted AND rendered, the CICD export counts IL
kills, and the Windows-degenerate triple check becomes honest. Issues
#85–#90 created. Branch `feature/v2.8.0-il-honesty`.

## Sprint 30 Backlog (25 SP — Must 17, Should 8)
1. **#85 (Must, 2 SP):** persist forensics — save_result gets
   event.forensics (JT-004, main-session verified); 38-literal → constant.
2. **#86 (Must, 2 SP):** CICD export learns the IL bucket (OS-002,
   verified 33.3% vs 66.7%); one score across run gate / results / export.
3. **#87 (Must, 5 SP):** rendering — `show` forensics panel (NULL-safe for
   pre-v2.8 rows) + browser IL awareness derived from constants.py
   (UI-004/008).
4. **#88 (Must, 8 SP):** classifier honesty — PYTHONUNBUFFERED output
   signal, running_ratio neutral on win32, confidence capped 'medium' on
   two-signal verdicts, all guards (min-sample floor, gt=0 threshold,
   run() catch-all + sampler_errors field, stat-unknown, window hint) and
   hygiene (daemon super().__init__, snapshot-before-tail-read) in ONE
   pass. Detail design via MANDATORY ≥10-step CoT before implementation;
   Context7 for psutil specifics.
5. **#89 (Should, 5 SP):** timeboxed spike — io_counters deltas as the
   Windows substitute for the sleeping signal; explicit decide gate,
   negative results documented in the audit doc.
6. **#90 (Should, 3 SP):** test/doc honesty LAST — Windows-realistic
   fixtures mirroring the FINAL semantics, sober prose.

Scope valve: #89/#90 slip to Sprint 31 on blowup.

## Planning insights (sequential-thinking session)
- Value chain ordering: persist → count → render → be-honest; classifier
  changes come AFTER the forensics pipeline works so behaviour is
  debuggable through visible data.
- The confidence cap is only non-breaking NOW: forensics were never
  persisted, so no consumer can depend on old confidence values.
- JT-013 is obsolete (timeout.py removed in Sprint 29).

## Out of scope (roadmap unchanged)
C6+C7 (Sprint 31 / v2.9.0), C8+C9-top (Sprint 32 / v2.10.0), OS-014
(json score — C7), pip-audit baseline (environment SSL).
