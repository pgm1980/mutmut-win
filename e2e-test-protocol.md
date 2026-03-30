# E2E-Test-Protokoll: mutmut-win auf echtem Projekt

**Datum:** 2026-03-30
**Testprojekt:** simple_lib (4 Funktionen: add, subtract, multiply, is_positive; 9 Tests)
**mutmut-win Version:** v0.3.2 + cwd/PYTHONPATH-Fixes

---

## Testdurchführung

### Setup
```
1. simple_lib nach C:\tmp\e2e_test_simple_lib kopiert
2. uv sync (Dependencies installiert)
3. uv add pytest (Testframework)
4. uv pip install -e C:\claude_code\mutmut-win (mutmut-win editable installiert)
5. uv run pytest -v → 9 passed (Baseline-Validierung)
```

### Erster Versuch: FEHLGESCHLAGEN

**Befehl:** `uv run mutmut-win run`

**Ergebnis:** Exit Code 1

**Fehler:** `Forced-fail check passed with exit code 0 — the trampoline mechanism does not appear to work correctly.`

**Diagnose:**
- Die Trampoline-Dateien wurden korrekt in `mutants/` generiert (✅)
- Stats-Collection via in-process pytest.main() lief korrekt (✅)
- Forced-Fail-Test lief als subprocess OHNE `cwd="mutants/"` (❌)
- pytest importierte den Original-Code statt den trampolierten Code aus mutants/
- Zusätzlich: `PYTHONPATH` war nicht gesetzt — subprocess konnte `mutants/src/` nicht als Import-Pfad finden

**Root Cause:** Drei Methoden in `runner.py` + der Worker in `process/worker.py` führten pytest NICHT im `mutants/` Verzeichnis aus:
1. `PytestRunner.run_clean_test()` — kein `cwd="mutants"`, kein `PYTHONPATH`
2. `PytestRunner.run_forced_fail()` — kein `cwd="mutants"`, kein `PYTHONPATH`
3. `PytestRunner.run_tests()` — delegiert an run_clean_test(), gleicher Bug
4. `process/worker.py` → `worker_main()` — kein `PYTHONPATH` für mutants/src

**Erklärung warum das in keinem früheren Review aufgefallen ist:**
- mutmut (Original) nutzt `pytest.main()` in-process mit vorher manipuliertem `sys.path`
- mutmut-win nutzt `subprocess.run()` — subprocess erbt `sys.path` NICHT
- Alle Unit-Tests mocken subprocess.run — der echte Aufruf wurde nie getestet
- Die E2E-Referenztests prüfen nur Mutanten-GENERIERUNG, nicht den vollen Pipeline-Lauf

### Fix

| Datei | Änderung |
|-------|----------|
| `runner.py` → `run_clean_test()` | `cwd="mutants"` + `env[MUTANT_ENV_VAR]=""` + `_mutants_env()` |
| `runner.py` → `run_forced_fail()` | `cwd="mutants"` + `_mutants_env()` |
| `runner.py` → `_mutants_env()` (NEU) | Setzt `PYTHONPATH` auf `mutants/src`, `mutants/source`, `mutants/.` |
| `process/worker.py` → `worker_main()` | `cwd="mutants"` + `PYTHONPATH` analog zu `_mutants_env()` |

### Zweiter Versuch: ERFOLGREICH ✅

**Befehl:** `uv run mutmut-win run`

**Ausgabe:**
```
     also copying tests/
     also copying pyproject.toml
Running clean test suite…
Collecting test timing statistics…
9 passed in 0.01s
Running forced-fail verification…
1/5  🎉 0  🫥 0  ⏰ 0  🤔 0  🙁 0  🔇 0  🧙 0
...
10/5  🎉 5  🫥 0  ⏰ 0  🤔 0  🙁 0  🔇 0  🧙 0

--- Mutation Testing Summary ---
Total mutants : 5
Killed        : 5
Survived      : 0
Timeout       : 0
Suspicious    : 0
Skipped       : 0
No tests      : 0
Score         : 100.0%
Duration      : 2.7s
```

**Ergebnis:** 5/5 Mutanten killed, Score 100%, Laufzeit 2.7s

---

## Was gut lief

1. **Mutanten-Generierung:** CST-basierte Mutation funktioniert korrekt auf Windows (✅)
2. **Trampoline-Mechanismus:** `_mutmut_trampoline()` schaltet korrekt zwischen Original und Mutant (✅)
3. **also_copy Defaults:** tests/, pyproject.toml etc. werden automatisch nach mutants/ kopiert (✅)
4. **Stats-Collection:** In-process pytest.main() mit StatsCollector-Plugin funktioniert (✅)
5. **Forced-Fail-Test:** Trampoline-Validierung erkennt korrekt, dass Tests fehlschlagen (✅)
6. **Worker-Pool:** spawn-basierter Multiprocessing-Pool führt Mutanten parallel aus (✅)
7. **Live-Fortschritt:** Emoji-basierte Statusanzeige während des Laufs (✅)
8. **Ergebnis-Persistenz:** SQLite + JSON-Meta-Dateien (✅)
9. **CLI:** `mutmut-win run` funktioniert als Entry-Point (✅)

## Was nicht gut lief (und gefixt wurde)

1. **KRITISCH: subprocess ohne cwd="mutants/"**
   - 4 Stellen fehlte `cwd="mutants"` bei subprocess.run()
   - pytest importierte Original-Code statt trampolierten Code
   - **Fix:** `cwd="mutants"` + `_mutants_env()` mit PYTHONPATH

2. **KRITISCH: Kein PYTHONPATH für subprocess**
   - subprocess erbt sys.path nicht (anders als in-process pytest.main)
   - Ohne PYTHONPATH findet pytest die Module in mutants/src/ nicht
   - **Fix:** Neue `_mutants_env()` Methode setzt PYTHONPATH auf mutants/src etc.

## Bekannte kleine Probleme

1. **Fortschrittszähler überzählt:** Zeigt "10/5" weil er Events zählt (TaskStarted + TaskCompleted = 2 pro Mutant) statt nur abgeschlossene Mutanten
2. **Reihenfolge der Ausgabe:** "Collecting test timing statistics" erscheint vor "Running forced-fail verification" in der Konsolenausgabe (kosmetisch)

## Fazit

mutmut-win funktioniert End-to-End auf Windows. Der kritische Bug (fehlende cwd/PYTHONPATH) war ein reiner Integrationsdefekt der in Unit-Tests nicht auffiel, weil alle subprocess-Aufrufe gemockt waren. Ein einziger echter E2E-Test hätte das sofort aufgedeckt.

**Empfehlung:** Vor jedem Release einen nicht-gemockten E2E-Test auf einem echten Projekt ausführen.
