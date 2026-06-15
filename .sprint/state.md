---
current_sprint: "v2.20.0 (external-QA hardening)"
sprint_goal: "v2.20.0: WRK-002 (Staging-Worker-Pool gegen bootstrap-sterbende Worker absichern — ProcessPoolExecutor erkennt tote Worker → sauberer OrchestratorError statt Endlos-Hang) + do_not_mutate_patterns matcht jetzt auch den qualifizierten Class.method-Namen. Striktes @staticmethod-Gating als by-design dokumentiert. Akzeptanz: geaenderte Zeilen >=80% Mutation, volle Suite gruen."
branch: "feature/v2.20.0-wrk002-qualified"
started_at: "2026-06-15"
housekeeping_done: false
memory_updated: false
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State (v2.20.0 — external-QA hardening)

## v2.20.0 — die letzten zwei offenen Punkte aus dem externen v2.19.0-Bericht
User-Scope-Wahl: "WRK-002 + qualified-name" fixen, @staticmethod-strict-gating
als by-design dokumentieren.

1. **WRK-002 (Pre-Bootstrap-Worker-Hang)** — die STAGING-Phase nutzte
   `multiprocessing.Pool.imap_unordered`, das keine Broken-Worker-Erkennung hat:
   stirbt ein Worker beim Interpreter-Bootstrap (crashendes sitecustomize/.pth/
   site-packages, `os._exit` bevor das mp-Child connectet), blockiert der ganze
   Lauf FUER IMMER (empirisch >80s, kein Abbruch; der SpawnPoolExecutor-Watchdog
   WRK-001 wird nie erreicht, weil Staging davor haengt). Fix: `_generate_mutants`
   nutzt jetzt `concurrent.futures.ProcessPoolExecutor` (spawn-Kontext) — dessen
   Management-Thread wirft `BrokenProcessPool` (~0.3s in der Repro), das zu einem
   sauberen `OrchestratorError` (Exit 1) wird statt eines unbegrenzten Hangs.
   `pool.map` stellt zudem deterministische Ergebnis-Reihenfolge her (vorher
   `imap_unordered`; wir `list()`en ohnehin alles).
2. **do_not_mutate_patterns qualified-name** — der Matcher griff nur auf den
   blanken Funktions-/Methodennamen. Jetzt baut ein Klassennamen-Stack
   (`on_visit` push / `on_leave` pop ClassDef) den qualifizierten `Class.method`-
   Namen, der ZUSAETZLICH zum simplen Namen gematcht wird (additiv, rueckwaerts-
   kompatibel: `Drop\.shared` trifft nur Drop.shared, `shared` weiter jede Klasse).
3. **@staticmethod-strict-Gating = by-design** (kein Code-Change) — nur Methoden,
   die AUSSCHLIESSLICH `@staticmethod` tragen, werden mutiert; Kombination mit
   weiterem Dekorator bleibt geskippt (`_is_static_only`). Dokumentiert in
   `_config/mutmut-win-install.md` (Wichtige Hinweise) als bewusste, korrektheits-
   wahrende Entscheidung. @classmethod bleibt deferred (bound `__name__` read-only).

## Gates (alle gruen)
- volle Suite **1419 passed / 5 skipped**, ruff 0, mypy 14 = Baseline,
  import-linter KEPT, Semgrep 0 (geaenderte Dateien). Keine neuen Dependencies
  (ProcessPoolExecutor/concurrent.futures sind stdlib) -> pip-audit unveraendert
  ggue. v2.19.1.
- **Mutation geaenderte Zeilen:**
  - WRK-002 (`_generate_mutants` neue Zeilen): die Safety-Net-Mutanten
    (`raise`->`pass`, msg=None, msg-String, OrchestratorError(None), list()-drop)
    **11/11 = 100%** gekillt — bewiesen via wrk002-only-Gate (forciert die
    Test-Zuordnung; der tests/unit-weite Gate ordnet wrk002 wegen der
    Engine-Self-Mutation-Coverage-Luecke NICHT zu). Aequivalente: max_workers=None/
    weggelassen, mp_context=None/get_context(None) — auf Windows == spawn-Default,
    worker-Anzahl aendert die generierten Mutanten nicht. Die `> 1`-Bedingung ist
    vorbestehend (Legacy, nicht geaendert).
  - qualified-name (`_skip_node_and_children` + `on_leave`): die neuen Zeilen
    (qualified-OR, on_visit-push, on_leave-pop) **100%** gekillt; verbleibende
    23 Survivors sind dieselbe Legacy-Klasse wie W4 (never-mutate-Gate, annotation/
    param-default/@staticmethod-relaxation/decorator).

## Test-Haertung (wrk002)
- `_BrokenPool.map` ist LAZY (Generator, raise bei Iteration) wie echtes
  `ProcessPoolExecutor.map` -> pinnt das `list(...)` im try als load-bearing
  (Mutant 85: list()-drop laesst die Exception sonst aus dem try entkommen).
- exakte Diagnose-Message-Assertion (`str(exc) == _EXPECTED_MSG`) statt blossem
  `match=`-Substring -> killt jede msg-Segment-Mutation + msg=None + raise->pass.

## Reusable lesson (neu)
Engine-Self-Mutation-Coverage-Luecke gilt auch fuer den Orchestrator: ein Test,
der `_generate_mutants` direkt mit Mock aufruft, wird im tests/unit-weiten Stats-
Lauf NICHT als covering test zugeordnet -> ehrlicher Beweis = Gate mit genau
diesem Test als einzigem `--tests-dir`.

## Status
v2.20.0 RELEASE in Arbeit (Branch feature/v2.20.0-wrk002-qualified). Nach Merge/
Tag/Push/Release: Close-Commit setzt housekeeping_done + memory_updated, zurueck
in die Entwicklungspause (0 Issues / Backlog).
