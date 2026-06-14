---
current_sprint: "Phase 2"
sprint_goal: "Phase 2 (Aufgabe 2): die sechs cheap-high-yield advanced-Operatoren (#3 ROR-Matrix, #15 Number-CRCR, #22 negate, #23 force, #38 collection-empty, #41 match-guard) auf dem advanced-Default. Akzeptanz: acceptance_harness 152/152/100%, per-operator Mutation 100%, e2e wellen-stabil."
branch: "main"
started_at: "2026-06-13"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Phase 2 — Aufgabe 2, opened 2026-06-13)

## Current Focus
Phase 2 — **die sechs advanced Phase-2-Operatoren** —
**ABGESCHLOSSEN, v2.17.0 RELEASED 2026-06-14** (Merge `ef89333`, Doku/Bump
`beabc32`, annotated Tag v2.17.0,
[GitHub-Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.17.0)).
Gates vor dem Merge frisch verifiziert: 1217 passed / 5 skipped, ruff 0
(bare `.`), ruff format clean, mypy 14 = Baseline, Semgrep clean.
acceptance_harness 152/152/100% (alle sechs Operatoren), per-operator
Mutation 100%.

**PROJEKT ZURÜCK IN DER ENTWICKLUNGSPAUSE:**
0 offene Issues · 0 Backlog-Einträge. Wiederaufnahme-Startpunkte: Phase 3
(#42 volle Regex-Sub-Mutator-Suite) und die `all`-tier aggressive Operatoren
(#2 AOD, #12 UOI, #27/#29 statement/member-removal, #44 exception-swap) —
siehe `_docs/nextgen_roadmap/MUTMUT_WIN_OPERATOR_ROADMAP.md` §3.7/§4 +
`acceptance_harness`. e2e-Test-Strategie für künftige Operatoren: Memory
`phase2-operator-e2e-profilschichtung`.

## Phase 2 Ergebnis (Wellen)
1. **W1 #3 ROR full matrix** — decoupled von swap_op (die 4 Nicht-swap-
   Alternativen, kein Visitor-Dedup). Commit `3016eac`. Mutation 6/6.
2. **W2 #15 Number-CRCR** — unified int/float candidate-loop mit seen-dedup;
   sequence-Tests killen die Dedup-Logik. Commit `9a699ed`. Mutation 57/57.
   e2e_reference auf Schicht-Invarianten umgestellt.
3. **W3 #22 negate + #23 force** — auf cst.If (deckt elif); negate skippt
   Comparison/Not. Commit `e9598fb`. Mutation 33/33. Pipeline-Snapshot-Test
   auf `--profile basic` gepinnt (advanced renummeriert __mutmut_N).
4. **W4 #38 collection-empty** — List/Dict/Set(→`set()`)/Tuple(→`()`),
   skip-empty. Commit `9b7113b`. Mutation 18/18.
5. **W5 #41 match-guard** — cst.MatchCase guard True/False. Commit `c19fde2`.
   Mutation 19/19.
6. **W6 Doku/Harness/Release** — ROADMAP_SPEC Phase-2-Sektion, Roadmap §2/§6,
   Matrix, README, Install-Docs; harness 152/152; Release v2.17.0. Doku
   `beabc32`, Merge `ef89333`.

## Out of scope (bewusst, Phase 3+)
#42 volle Regex-Suite (14 Sub-Mutatoren), `all`-tier aggressive Operatoren,
mutmut-3.6.0-Surface-Backports (@staticmethod/@classmethod-Mutation,
Pragma-block, do_not_mutate_patterns).
