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
3. **W3 UOI (#12) — HIGH RISK [ToT]** — ✅ **ABGESCHLOSSEN**. ToT-Scope (Option B,
   0.89): drei Profile.ALL-Operatoren — operator_uoi_negate_while (While.test `not`,
   Gap zu negate_condition), operator_uoi_minus_operand (`(-name)` auf arithm.
   Name-Operanden, Literale=CRCR), operator_uoi_negate_boolean_operand (`not` auf
   and/or-Operanden). **T4 (comparison-Operanden) ausgeschlossen** (präzedenz-fragil,
   niedrigstes Signal, Explosion). Ausschlüsse: If.test=negate_condition,
   Literal-`-`=CRCR. Präzedenz: inserted unary in Operand-Position bekommt explizite
   Parens (`(-x) ** y`); `not`>and/or → kein outer-paren, nur _safe_unwrap.
   Per-Operator-Mutation 42/42 = 100%.
4. **W4 Backports do_not_mutate_patterns + pragma-block** — ✅ **ABGESCHLOSSEN**.
   (A) pragma-block/start-end: `pragma_no_mutate_lines()` erweitert (Text-Indentation
   per ToT, self-contained) + Helfer _pragma_no_mutate_suffix/_pragma_block_range/
   _indent_width. (B) do_not_mutate_patterns: config-Feld + fail-loud-Validator +
   Skip in `_skip_node_and_children` (FunctionDef/ClassDef-Name re.search), gethreadet
   wie active_profile (create_mutations→mutate_file_contents→write_all_mutants_to_file→
   create_mutants_for_file→orchestrator Pool-Tupel 7. Element + dry_run). Profil-
   unabhängig (kein e2e-Count-Effekt). Mutation: Pragma-Scanner 193/197 = 98%
   (4 dok. Äquivalente: `<`/`!=`-Boundary, redundanter Check, rpartition-Doppelmarker);
   neue Skip-Zeilen 100% gekillt (Validator decorator-geskippt, via Tests abgedeckt).
5. **W5 @staticmethod/@classmethod-Backport — HIGH RISK [ToT]** — Trampoline,
   decorator-skip relaxen; eigene ToT.
6. **W6 Harness-all-Akzeptanz + Doku + Release v2.19.0**.

## Architektur-Leitplanken
- all-tier-Operatoren sind `Profile.ALL`-getaggt → advanced-Counts bleiben
  UNVERÄNDERT (Schicht-Invariante basic⊆snap⊆adv⊆all + Per-Projekt-Count-Pins).
- Per-Operator-Gate: `mutmut-win run --paths-to-mutate <file> --tests-dir
  <unit-test> --profile all --force "*operator_X*"` (fnmatch-Glob via
  match_mutant_names). Neu geschriebene Funktionen zählen voll (Gate-Methodik #6).

## W1–W4 Ergebnis (Gates)
W4: 1385 passed / 5 skipped, ruff 0 (bare `.`), mypy 14 = Baseline, import-linter
KEPT, Semgrep 0 (Pro-Rules, 4 Dateien). Pragma-Scanner-Mutation 193/197 = 98%; neue
Skip-Zeilen 100% gekillt. e2e advanced+all-Pins UNVERÄNDERT (Backports profil-unabhängig).
W3: 42/42 = 100%, all = basic15/adv34/all41, all-Counts my_lib 163/config 40/
type_checking 20/py3_14 14/covered 127. W2: 46/50 = 92%. W1: 18/18 = 100%.

## Out of scope (Phase 5+)
Weitere Surface-Backports jenseits §5; PyPI-Publishing.
