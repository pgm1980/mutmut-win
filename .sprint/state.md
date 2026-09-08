---
current_sprint: "39"
sprint_goal: "v2.21.1: candidate validated"
branch: "fix/v2.21.1-windows314"
started_at: "2026-09-02"
phase: "candidate_validated"
candidate_commit: ""
candidate_tree: ""
integrated_commit: ""
integrated_tree: ""
release_tag: ""
housekeeping_done: false
memory_updated: true
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State — Windows/CPython-3.14.7-Follow-up

<!-- PUBLICATION_STATE_START -->
<!-- PUBLICATION_STATE: external-live-check-required -->
Publication status for v2.21.1 is external mutable state. These immutable bytes assert neither presence nor absence; verify the exact annotated tag and matching GitHub release before use.
<!-- PUBLICATION_STATE_END -->

<!-- LIVE_STATE_START -->

<!-- RELEASE_PHASE: candidate_validated -->
<!-- RELEASE_PHASE_STATUS: local-candidate-gates-validated-publication-external -->
<!-- RELEASE_TARGET: v2.21.1 -->
<!-- RELEASE_BRANCH: `fix/v2.21.1-windows314` -->
<!-- RELEASE_ROADMAP: bug_reporting/BUGFIXUNG_ROADMAP.md -->
<!-- RELEASE_PUBLICATION_AUTHORITY: canonical-external-block -->

<!-- LIVE_STATE_END -->

<!-- ARCHIVE_START -->

## Archiv: v2.20.0 — external-QA hardening

### v2.20.0 — die letzten zwei offenen Punkte aus dem externen v2.19.0-Bericht
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

### Gates (alle gruen)
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

### Test-Haertung (wrk002)
- `_BrokenPool.map` ist LAZY (Generator, raise bei Iteration) wie echtes
  `ProcessPoolExecutor.map` -> pinnt das `list(...)` im try als load-bearing
  (Mutant 85: list()-drop laesst die Exception sonst aus dem try entkommen).
- exakte Diagnose-Message-Assertion (`str(exc) == _EXPECTED_MSG`) statt blossem
  `match=`-Substring -> killt jede msg-Segment-Mutation + msg=None + raise->pass.

### Reusable lesson (neu)
Engine-Self-Mutation-Coverage-Luecke gilt auch fuer den Orchestrator: ein Test,
der `_generate_mutants` direkt mit Mock aufruft, wird im tests/unit-weiten Stats-
Lauf NICHT als covering test zugeordnet -> ehrlicher Beweis = Gate mit genau
diesem Test als einzigem `--tests-dir`.

### Status
**v2.20.0 RELEASED** (Merge db71e53, Tag v2.20.0,
[GitHub-Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.20.0)).
PROJEKT ZURUECK IN DER ENTWICKLUNGSPAUSE (0 Issues / Backlog).

<!-- ARCHIVE_END -->
