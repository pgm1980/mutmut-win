---
current_sprint: "46"
sprint_goal: "v3.0.0: released"
branch: "main"
started_at: "2026-10-02"
phase: "released"
candidate_commit: "d291ee53e529692063dee2f55ad9ac9087003472"
candidate_tree: "5457315eb374776c230e13946a18df126bee97d2"
integrated_commit: "99db317609d120f2f269824ea56f67636580d0fb"
integrated_tree: "5457315eb374776c230e13946a18df126bee97d2"
release_tag: "v3.0.0"
housekeeping_done: true
memory_updated: true
github_issues_closed: true
sprint_backlog_written: true
semgrep_passed: true
tests_passed: true
documentation_updated: true
---

# Sprint State - Sanierung v3.0.0: R3-Welle und Release abgeschlossen (AP-33 bis AP-47)

<!-- LIVE_STATE_START -->

<!-- RELEASE_PHASE: released -->
<!-- RELEASE_PHASE_STATUS: tagged-release-housekeeping-complete -->
<!-- RELEASE_TARGET: v3.0.0 -->
<!-- RELEASE_BRANCH: `main` -->
<!-- RELEASE_PUBLICATION_AUTHORITY: canonical-external-block -->

<!-- LIVE_STATE_END -->

<!-- ARCHIVE_START -->

## Archiv: Sprint 46 - v3.0.0

Release-Sprint der R3-Welle (AP-33 bis AP-46) und des Release-Abschlusses
(AP-47): Kandidat `d291ee5` (Tree `5457315e`), integriert als `99db317`
(Merge PR #197, Baum byte-identisch), annotierter Tag `v3.0.0`,
GitHub-Release mit Gate-Evidenz. Release-Vollsuite 3.668 passed / 1 failed /
44 skipped; Root Cause des Fails: PEP-758-Multi-Except aus `95341e11`
(M-112) ausserhalb des Semgrep-1.175-Parser-Subsets — Fix `ea0069c`
[M-112-fix] plus gezielter Grün-Nachweis (88 passed: Semgrep-Gate-Suite und
suspended_spawn-Tests). Modul-Gate-Kampagne nach Auftraggeberentscheidung
abgebrochen und als dokumentierte Abweichung vom Ledger-Kriterium
freigegeben: 3 PASS (output_capture 57,3 %, suspended_spawn 34,8 %,
trampoline 66,7 % + Adjudizierung ~93,6 %), 2 BLOCKED (models/browser:
Trampolin-Grenze klassenlastiger Module; Produkt-Bug widerlegt),
db-Teilevidenz 288/2.622 (24,3 % Kill), Rest NOT_EXECUTED — Matrix
AR27-GATE-MATRIX.md Sektion 7. Offen: #193, #194, #195; M-097 deferred;
Übergabe an externen adversarialen Multi-Agenten-Review (GPT-6 Astra /
Fable 5.1) mit Prüfaufträgen H1-H4 und E-A bis E-F.

## Archiv: Sprint 45 - v2.21.5

Release-Sprint der Astra-Nachbesserung R1/R2: Kandidat `b47209c`
(Tree `ee302345`), integriert als `9e3bec8` mit identischem Tree,
annotierter Tag `v2.21.5`, GitHub-Release mit vollständiger
Gate-Evidenz. Vollsuite integriert 3599/0/43; ruff/format/mypy-strict/
import-linter grün auf Kandidat und Integration; kanonisches
Semgrep-Gate PASS (31 adjudizierte Findings); pip-audit sauber bis auf
dokumentierte pyjwt-Dev-Abweichung (mcp-Deckelung). Offene
Folgeaufträge: #194 (Forced-Fail-Hang), #195 (Cache-Reuse),
regex_mutation-Gate-Wiederholung, Cross-File-Adjudizierung
node_mutation — Receipts laufen über den GitHub-Release-Body nach.
R3 (AP-33..AP-46) und R4 (AP-47) folgen vor 3.0.0; Abnahmeinstrument
ist das R0-R4-Master-Ledger (146 Gruppen).

## Archiv: Sprint 42 - v2.21.4

Vorangegangener Release-Sprint: Kandidat `4319744` (Tree `aa9bdf11`), integriert
als `4d7f950` mit identischem Tree, annotierter Tag `v2.21.4`. Dokumentiert in
`_docs/sprint backlogs/sprint_42_backlog.md`.

## Archiv: Sprint 39 - v2.21.1

Der vorherige abgeschlossene Sprint ist
in `_docs/sprint backlogs/sprint_39_backlog.md`,
`bug_reporting/ANALYSE_MUTMUTWIN221.md` und
`bug_reporting/BUGFIXUNG_ROADMAP.md` dokumentiert. Sein Kandidat
`e48fda5e7cf0f633f4180b72e891db502605fa30` wurde als
`e91d338f945b9d6526463fb0f835fab2d0b82736e` mit identischem Tree
`b5fce8e29500b337677094aaa17b3674f1e86bd1` integriert. Das bestehende
annotierte Tag `v2.21.1` bleibt unver├ñndert. Die offenen Flags dieses neuen
Sprints sind keine R├╝cknahme dieser historischen Befunde oder Gates.

## Archiv: v2.20.0 ÔÇö external-QA hardening

### v2.20.0 ÔÇö die letzten zwei offenen Punkte aus dem externen v2.19.0-Bericht
User-Scope-Wahl: "WRK-002 + qualified-name" fixen, @staticmethod-strict-gating
als by-design dokumentieren.

1. **WRK-002 (Pre-Bootstrap-Worker-Hang)** ÔÇö die STAGING-Phase nutzte
   `multiprocessing.Pool.imap_unordered`, das keine Broken-Worker-Erkennung hat:
   stirbt ein Worker beim Interpreter-Bootstrap (crashendes sitecustomize/.pth/
   site-packages, `os._exit` bevor das mp-Child connectet), blockiert der ganze
   Lauf FUER IMMER (empirisch >80s, kein Abbruch; der SpawnPoolExecutor-Watchdog
   WRK-001 wird nie erreicht, weil Staging davor haengt). Fix: `_generate_mutants`
   nutzt jetzt `concurrent.futures.ProcessPoolExecutor` (spawn-Kontext) ÔÇö dessen
   Management-Thread wirft `BrokenProcessPool` (~0.3s in der Repro), das zu einem
   sauberen `OrchestratorError` (Exit 1) wird statt eines unbegrenzten Hangs.
   `pool.map` stellt zudem deterministische Ergebnis-Reihenfolge her (vorher
   `imap_unordered`; wir `list()`en ohnehin alles).
2. **do_not_mutate_patterns qualified-name** ÔÇö der Matcher griff nur auf den
   blanken Funktions-/Methodennamen. Jetzt baut ein Klassennamen-Stack
   (`on_visit` push / `on_leave` pop ClassDef) den qualifizierten `Class.method`-
   Namen, der ZUSAETZLICH zum simplen Namen gematcht wird (additiv, rueckwaerts-
   kompatibel: `Drop\.shared` trifft nur Drop.shared, `shared` weiter jede Klasse).
3. **@staticmethod-strict-Gating = by-design** (kein Code-Change) ÔÇö nur Methoden,
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
    **11/11 = 100%** gekillt ÔÇö bewiesen via wrk002-only-Gate (forciert die
    Test-Zuordnung; der tests/unit-weite Gate ordnet wrk002 wegen der
    Engine-Self-Mutation-Coverage-Luecke NICHT zu). Aequivalente: max_workers=None/
    weggelassen, mp_context=None/get_context(None) ÔÇö auf Windows == spawn-Default,
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
- exakte Diagnose-Message-Assertion (`str(exc) == _EXPECTED_MSG`) statt blosem
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
