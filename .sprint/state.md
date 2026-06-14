---
current_sprint: "Phase 3"
sprint_goal: "Phase 3 (Aufgabe 2): die volle 14-Sub-Mutator-Regex-Suite (#42), string-basiert auf einem class-span-Tokenizer. Akzeptanz: acceptance_harness 184/188, per-operator Mutation 96-99%, e2e wellen-stabil."
branch: "main"
started_at: "2026-06-14"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (Phase 3 — Aufgabe 2, regex suite)

## Current Focus
Phase 3 — **die volle 14-Sub-Mutator-Regex-Suite (#42)** —
**ABGESCHLOSSEN, v2.18.0 RELEASED** (Merge `aa3bf75`, Tag v2.18.0,
[GitHub-Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.18.0)).
Gates: 1313 passed / 5 skipped, ruff 0 (bare `.`), mypy 14 = Baseline, Semgrep
clean. acceptance_harness 184/188 (4 dokumentierte fullmatch-Äquivalente).

**PROJEKT ZURÜCK IN DER ENTWICKLUNGSPAUSE:**
0 offene Issues · 0 Backlog. Wiederaufnahme: `all`-tier aggressive Operatoren
(#2 AOD, #12 UOI, #27/#29 removal, #44 exception-swap) + mutmut-3.6.0-Backports
(@staticmethod/@classmethod, pragma-block, do_not_mutate_patterns). Siehe
`_docs/nextgen_roadmap/MUTMUT_WIN_OPERATOR_ROADMAP.md` §4/§5/§6 +
acceptance_harness `all`-Tabelle. Serena-Memory `current_state` = Live-Stand.

## Phase 3 Ergebnis (Wellen)
1. **W1 Tokenizer + Anker (#1)** — _class_spans/_in_class-Fundament + Anker
   ^ $ \A \Z \b \B removal. Commit `6806434`. Mutation 95.6%.
2. **W2 Quantoren (#2-6)** — removal/swap/short→range/reluctant/brace±1; lazy-marker
   in _QUANTIFIER_RE. Commit `5e3f098`. Mutation 98.8%.
3. **W3 Shorthand (#11-13)** — negation(swapcase)/nullify/to-any; _shorthand_positions
   escape-bewusst. Commit `367c90d`. Mutation 98.8%.
4. **W4 Char-Klassen (#7-10)** — negation/child-removal/range±1/to-any; _class_members
   + _RANGE_RE; inner/body/mark entkoppelt. Commit `bbfabc2`. Mutation 98.5%.
5. **W5 Gruppen/Look-around (#14,+15) + Cap** — flip/non-capturing; MAX 5→12.
   Commit `aaf4b13`. Mutation 99.3%.
6. **W6 Harness/Doku/Release** — regex-Targets inline gefixt (module-level wurde nie
   mutiert), _QUANTIFIER_RE (?=-Fix (foo(=bar)), Doku (Matrix/Roadmap/README/Spec),
   Release v2.18.0. Commit `85be62d`, Merge `aa3bf75`.

## Architektur-Entscheidung (User-bestätigt)
String-basiert, NICHT re._parser — `re` hat keine `unparse`, ein Emitter-Round-trip
wäre das Hauptrisiko (ein Bug verfälscht alle Mutanten). Der Tokenizer löst die
Kontext-Sensitivität (^ in [^..], \d in [\d], ( in [(]).

## Out of scope (Phase 4+)
`all`-tier aggressive Operatoren, mutmut-3.6.0-Surface-Backports.
