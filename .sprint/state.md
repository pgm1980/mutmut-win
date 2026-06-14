---
current_sprint: "Phase 4"
sprint_goal: "Phase 4: die aggressiven all-tier-Operatoren (#2 AOD, #12 UOI, #27/#29 removal, #44 exception-swap) + mutmut-3.6.0-Backports (@static/classmethod, pragma-block, do_not_mutate_patterns). Akzeptanz: per-operator Mutation ≥80%, all⊋advanced, e2e wellen-stabil, acceptance_harness all-Tabelle grün."
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

# Sprint State (Phase 4 — all-tier aggressive Operatoren + 3.6.0-Backports)

## Current Focus
Phase 4 — **die aggressiven `all`-tier-Operatoren + mutmut-3.6.0-Backports** —
**ABGESCHLOSSEN (W1–W6), v2.19.0 RELEASED** (Merge `027cb41`, Tag v2.19.0,
[GitHub-Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.19.0)).
`all` ⊋ advanced (basic 15 / advanced 34 /
all 41). acceptance_harness `--profile all`: **204 / 200 / 98%** (4 dokumentierte
Regex-`fullmatch`-Äquivalente, KEINE neuen Phase-4-Survivors). Volle Suite 1397
passed / 5 skipped. **PROJEKT ZURÜCK IN DER ENTWICKLUNGSPAUSE** (0 Issues / Backlog).
W6: Doku (Roadmap §1/§6, Matrix mutmut-win-Spalte, ROADMAP_SPEC Phase-4-Verifikation,
README/install/CLAUDE.md @v2.19.0), Version-Bump 2.19.0, Harness re-pinnt @v2.19.0.

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
5. **W5 @staticmethod/@classmethod-Backport — HIGH RISK [ToT]** — ✅ **ABGESCHLOSSEN**.
   Empirische Probe widerlegte die Roadmap ("name-dispatched → sollte gehen"): BEIDE
   Formen waren kaputt (static droppt erstes Arg + AttributeError; class doppeltes cls
   + bound-`__name__` read-only). ToT-Scope (Option B, 0.84): **@staticmethod-only**,
   @classmethod dokumentiert deferred (Blast-Radius: nur create_trampoline_wrapper).
   `_is_static_only` (solely-@staticmethod) relaxt den decorator-skip; Wrapper dispatcht
   static wie free function (forward-all, self_arg=None, orig via `{Class}.{mangled}_orig`).
   Exec-verifiziert (orig + Mutant-Dispatch). `_is_static_only` 100%. e2e my_lib +11
   (Point.from_coords, intendierte Flächen-Expansion vs 3.5.0-Snapshot → w5_static_prefixes-
   Allowance + Pins 140/174). Wrapper-Self-Gate undercreditet (Engine-Self-Mutation
   Coverage-Lücke; _19/_23 manuell als killbar bewiesen, _4 echtes Äquivalent).
6. **W6 Harness-all-Akzeptanz + Doku + Release v2.19.0**.

## Architektur-Leitplanken
- all-tier-Operatoren sind `Profile.ALL`-getaggt → advanced-Counts bleiben
  UNVERÄNDERT (Schicht-Invariante basic⊆snap⊆adv⊆all + Per-Projekt-Count-Pins).
- Per-Operator-Gate: `mutmut-win run --paths-to-mutate <file> --tests-dir
  <unit-test> --profile all --force "*operator_X*"` (fnmatch-Glob via
  match_mutant_names). Neu geschriebene Funktionen zählen voll (Gate-Methodik #6).

## W1–W5 Ergebnis (Gates)
W5: 1397 passed / 5 skipped, ruff 0 (bare `.`), mypy 14 = Baseline, import-linter
KEPT, Semgrep 0. _is_static_only 100%; static-Dispatch exec-verifiziert. e2e my_lib-Pins
auf 140/174 angehoben (W5 @staticmethod-Flächen-Expansion, +11 Point.from_coords),
übrige 4 Projekte unverändert (kein @staticmethod). advanced ist ab W5 NICHT mehr
eingefroren (Surface-Backport, nicht profil-getaggt).
W4: 1385 passed, Pragma-Mutation 193/197 = 98%, neue Skip-Zeilen 100%. W3: 42/42 = 100%,
all = basic15/adv34/all41. W2: 46/50 = 92%. W1: 18/18 = 100%.

## Out of scope (Phase 5+)
Weitere Surface-Backports jenseits §5; PyPI-Publishing.
