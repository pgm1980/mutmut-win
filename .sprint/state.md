---
current_sprint: "Phase 4"
sprint_goal: "Phase 4: die aggressiven all-tier-Operatoren (#2 AOD, #12 UOI, #27/#29 removal, #44 exception-swap) + mutmut-3.6.0-Backports (@static/classmethod, pragma-block, do_not_mutate_patterns). Akzeptanz: per-operator Mutation ≥80%, all⊋advanced, e2e wellen-stabil, acceptance_harness all-Tabelle grün."
branch: "feature/v2.19.0-all-tier"
started_at: "2026-06-14"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: false
---

# Sprint State (Phase 4 — all-tier aggressive Operatoren + 3.6.0-Backports)

## Current Focus
Phase 4 — **die aggressiven `all`-tier-Operatoren + mutmut-3.6.0-Backports**.
Macht `all` ⊋ advanced ZUM ERSTEN MAL. Branch `feature/v2.19.0-all-tier`,
Ziel-Release v2.19.0. Backlog = `_docs/nextgen_roadmap/MUTMUT_WIN_OPERATOR_ROADMAP.md`
§4 (Operatoren) / §5 (Backports) + acceptance_harness `all`-Tabelle.

## Wellen-Plan (6)
1. **W1 AOD (#2) + exception-swap (#44)** — ✅ **ABGESCHLOSSEN**. Profile.ALL,
   `all` ⊋ advanced. Per-Operator-Mutation 18/18 = 100%, e2e all-Layer-Invarianten
   (advanced⊆all + exakte all-Counts: my_lib 147, config 38, type_checking 19,
   py3_14 14, covered 123).
2. **W2 member-assign (#29) + statement-removal (#27)** — ✅ **ABGESCHLOSSEN**.
   Zwei neue Profile.ALL-Operatoren auf cst.SimpleStatementLine (void_call_removal-
   Scaffold): operator_member_assignment_removal (single Attribute-Target
   `self.x = v` → pass) + operator_statement_removal (effektbehaftete Expr-Statements
   await/yield/subscript/walrus → pass; Calls=advanced, Docstrings/Ellipsis/
   Pure-Value per ToT-Entscheidung ausgeschlossen). Per-Operator-Mutation
   46/50 = 92% (4 dokumentierte Scaffold-Äquivalente: 2× `[0]≡[-1]` bei len==1,
   2× `body=[]` rendert via libcst zu `pass`). all-Counts: my_lib 153, type_checking 20.
3. **W3 UOI (#12) — HIGH RISK [ToT]** — unary insertion (`not`/`-`); eigene
   ToT für die Scope-Strategie (Explosion erwartet).
4. **W4 Backports do_not_mutate_patterns + pragma-block** — config-Regex +
   `_skip_node_and_children`; pragma-block extend `pragma_no_mutate_lines()`.
5. **W5 @staticmethod/@classmethod-Backport — HIGH RISK [ToT]** — Trampoline,
   decorator-skip relaxen; eigene ToT.
6. **W6 Harness-all-Akzeptanz + Doku + Release v2.19.0**.

## Architektur-Leitplanken
- all-tier-Operatoren sind `Profile.ALL`-getaggt → advanced-Counts bleiben
  UNVERÄNDERT (Schicht-Invariante basic⊆snap⊆adv⊆all + Per-Projekt-Count-Pins).
- Per-Operator-Gate: `mutmut-win run --paths-to-mutate <file> --tests-dir
  <unit-test> --profile all --force "*operator_X*"` (fnmatch-Glob via
  match_mutant_names). Neu geschriebene Funktionen zählen voll (Gate-Methodik #6).

## W1/W2 Ergebnis (Gates)
W2: 1342 passed / 5 skipped, ruff 0 (bare `.`), mypy 14 = Baseline, import-linter
KEPT, Semgrep 0 (node_mutation.py, Pro-Rules). Per-Operator-Mutation 46/50 = 92%
(4 inhärente Scaffold-Äquivalente, killbare stmt_5/member_6 via Tests gekillt).
e2e: advanced-Counts UNVERÄNDERT (129/30/17/10/113 = Regressionsbeweis); all wuchs
nur bei my_lib (147→153, async await/yield) und type_checking (19→20).
W1: 18/18 = 100% (`raise <Call>(...)` Robustheits-Test).

## Out of scope (Phase 5+)
Weitere Surface-Backports jenseits §5; PyPI-Publishing.
