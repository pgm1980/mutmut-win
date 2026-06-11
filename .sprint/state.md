---
current_sprint: "31"
sprint_goal: "v2.9.0 Feature Truth & Score Integrity — tote Features (Type-Check-Filter, Coverage) ehrlich reaktivieren oder abschalten; Score-Pipeline lückenlos (Buckets, Exit-Code-Map, Ctrl-C-Abbruch, Orphans, JSON-Kanal)."
branch: "feature/v2.9.0-score-integrity"
started_at: "2026-06-11"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Sprint 31 opened 2026-06-11)

## Current Focus
Sprint 31 — **v2.9.0 Feature Truth & Score Integrity** — **implementation
complete** (alle 7 Items, 33/33 SP). Commits auf
`feature/v2.9.0-score-integrity`:

| Issue | Commit | Inhalt |
|-------|--------|--------|
| #91 | `33c2c98` | Status-Wahrheit: Exit-Code-Map (−24-Dublette, NTSTATUS-Crashes, Exit 2 → killed per CoT), segfault-Bucket + Catch-All + Summen-Invariante, Kill-Klassen-Score in allen 3 Kanälen, generisches results-Rendering, Worker-Log-Tail für anomale Exits |
| #92 | `108ed87` | type_checking gehärtet: Basename-Erkennung (mypy.exe/uv run mypy brachen den Lauf ab), timeout/returncode/encoding (mypy-Exit-2 = stiller 0-Filter), pyright-Severity. Context7 + empirisch verifiziert |
| #93 | `18011c9` | Type-Check end-to-end: `to_mutants_relative`-Normalisierung (Matching traf NIE), Task-Schnittmenge, DB-Persistenz + eigenes Bucket, 100 %-caught-Guard, E2E mit echtem mypy |
| #94 | `80f38ab` | Ctrl-C: was_interrupted + unchecked (Score über Geprüfte), Exit 130, Gate-Skip |
| #95 | `75983f2` | Coverage REAKTIVIERT (Spike + 8-Schritt-CoT): Subprozess-Brücke, normcase-Keying (CM-013), laute Fehlerpfade; tote Kompat-API entfernt; mypy-Baseline 26→20 |
| #96 | `09fbad5`+`09c6cd7` | DB-Orphan-Purge bei Voll-Lauf (Default-Polarität False, CLI verdrahtet Voll-Lauf-Info); executemany statt dynamischem SQL (semgrep-clean) |
| #97 | `a70be0d` | CI-Kanal: score als computed_field im JSON; 0-Mutanten-Gate kommuniziert fail-closed |

Gates: **773 passed / 4 skipped** (+54), ruff 0, mypy **20 pre-existing /
0 neue** (Baseline gesunken), semgrep 0, lint-imports KEPT.

## Release — DONE 2026-06-11
v2.9.0 released: Merge `87a0271` (closes #91–#97, verifiziert 0 offene
Issues), Bump `e02bb34`, annotated Tag `v2.9.0`, GitHub Release
https://github.com/pgm1980/mutmut-win/releases/tag/v2.9.0 mit
prominenter ⚠-„Score corrections"-Sektion. Suite auf gemergtem main
erneut 773 passed / 4 skipped. Sprint 31 vollständig abgeschlossen,
alle Housekeeping-Items erledigt.

## Out of scope (Roadmap unverändert)
Sprint 32 / v2.10.0 = C8+C9 inkl. 3 vorgemerkter Pipeline-Hygiene-Punkte,
OS-012-Reste (mtime-Invalidierung, verwaiste .meta), Mutation-Gate
(C8-Stats-Fix), pip-audit (Umgebungs-SSL).
