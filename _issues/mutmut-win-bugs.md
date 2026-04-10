# mutmut-win v1.0.6 — Bug Report

**Erstellt:** 2026-04-10
**Betrifft:** mutmut-win v1.0.6 (Windows-Port von mutmut 3.5.0)
**Repository:** https://github.com/pgm1980/mutmut-win
**Projekt-Setup:** Python 3.14.3, Windows 11 Pro, uv 0.11.6, hatchling Build-Backend, pytest 9.0.3, pytest-asyncio 1.3.0, hypothesis 6.151.12
**Installation:** `uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.6" --dev`

---

## Zusammenfassung

mutmut-win v1.0.6 ist auf dem NextGen CoT MCP Server Projekt (392 Tests, 13 Source-Module) **nicht lauffähig**. Vier Bugs verhindern den Einsatz:

| # | Bug | Schwere | Phase | Workaround |
|---|-----|---------|-------|------------|
| 1 | Hang bei In-Process-Statistik-Sammlung (~79%) | **Blocker** | Stats Collection | Keiner |
| 2 | `ListAllTestsResult` fehlender `stats` Parameter | Critical | Inkrementeller Lauf | Cache vor jedem Lauf löschen |
| 3 | `.pth`-Datei überschattet Trampoline-Mechanik | Critical | Forced-Fail Check | `.pth` temporär umbenennen |
| 4 | Nur mutierte Datei in `mutants/src/`, nicht gesamtes Package | Critical | Clean Test Suite | Keiner |

**Bug 1 (Hang) ist der primäre Blocker** — mutmut-win kommt nie über die Statistik-Sammlung hinaus und erzeugt keine Mutanten.

---

## Bug 1: Hang bei In-Process-Statistik-Sammlung

**Schwere:** Blocker — mutmut-win hängt endlos, keine Mutanten werden je erzeugt
**Phase:** Statistik-Sammlung (nach "Collecting test timing statistics…")

### Symptom

```
Running clean test suite…
Collecting test timing statistics…
[391 Tests laufen bis ~79% durch]
tests/unit/test_session_state.py::test_session_state_is_mutable PASSED   [ 79%]
[HANG — keine weitere Ausgabe, Prozess läuft endlos weiter]
```

Der Prozess hängt **reproduzierbar** bei ~79% der Statistik-Sammlung. Kein Timeout, kein Crash, kein Error — einfach Stillstand. Der Prozess muss manuell beendet werden.

### Kontext

- 391 Tests collected (11 property, 319 unit, 51 repository, 1 benchmark — Benchmark wird exkludiert)
- Tests bis `test_session_state.py` laufen durch (79%)
- Die nächsten Tests wären `test_stages.py` und `test_value_objects.py`
- Der Hang tritt in der **In-Process** pytest-Plugin-Phase auf (`StatsCollector` Plugin), NICHT in der subprocess-basierten Phase
- `--debug` Flag hat keinen Effekt auf den Hang

### Vermutete Ursache

Die In-Process-Statistik-Sammlung (`runner.py` → `collect_statistics()` → in-process pytest mit `StatsCollector` Plugin) blockiert möglicherweise bei:
- pytest-asyncio Event-Loop-Cleanup zwischen Test-Modulen
- hypothesis Database-Shrinking oder Example-Storage
- pytest-benchmark Fixture-Teardown
- Windows-spezifische File-Locking-Probleme im `mutants/` Verzeichnis

### Reproduktion

```bash
# Frische Installation, kein Cache:
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.6" --dev
# Cache löschen:
rm -rf .mutmut-cache mutants
# Lauf starten (hängt nach ~30-60 Sekunden bei 79%):
uv run mutmut-win run --debug
```

### Workaround

Keiner bekannt. Der Hang tritt vor jeder Mutation auf — ohne funktionierende Statistik-Sammlung kann mutmut-win keine Mutanten erzeugen.

---

## Bug 2: `ListAllTestsResult.__init__()` fehlender `stats` Parameter

**Schwere:** Critical — Crash bei inkrementellem Lauf
**Phase:** Inkrementelle Stats-Aktualisierung

### Symptom

```
Found 381 new tests, re-running stats collection for them
Error: ListAllTestsResult.__init__() missing 1 required keyword-only argument: 'stats'
```

Ohne `--debug` hängt mutmut-win stattdessen endlos (der Fehler wird verschluckt).

### Root Cause

`mutmut_win/stats.py`, Zeile 151:

```python
# BUGGY (Zeile 148-153):
if new_tests:
    print(f"Found {len(new_tests)} new tests, re-running stats collection for them")
    result = ListAllTestsResult(ids=current_tests)          # BUG: stats=cached fehlt
    result.clear_out_obsolete_test_names(cached)             # BUG: cached ist kein Path
    save_stats(cached, mutants_dir)
```

Constructor-Signatur: `__init__(self, *, ids: set[str], stats: MutmutStats)` — erwartet **zwei** keyword-only Argumente.

### Fix (2 Zeilen)

```python
    result = ListAllTestsResult(ids=current_tests, stats=cached)
    result.clear_out_obsolete_test_names(mutants_dir)
```

### Workaround

`.mutmut-cache/` und `mutants/` vor jedem Lauf löschen (verhindert den inkrementellen Pfad).

---

## Bug 3: `.pth`-Datei überschattet Trampoline-Mechanik

**Schwere:** Critical — Forced-Fail-Check scheitert, Mutationen werden nicht erkannt
**Phase:** Forced-Fail Verification

### Symptom

```
Running forced-fail verification…
Error: Forced-fail check passed with exit code 0 — the trampoline mechanism does not appear to work correctly.
```

### Root Cause

`uv` erstellt bei editierbaren Installationen eine `.pth`-Datei in `site-packages/`:

```
# .venv/Lib/site-packages/_nextgen_cot_mcp_server.pth
C:\path\to\project\src
```

Diese `.pth`-Datei wird beim Python-Startup verarbeitet und fügt den **echten** `src/`-Pfad in `sys.path` ein — **vor** den `PYTHONPATH`-Einträgen, die mutmut-win in `_mutants_env()` setzt (`runner.py:235-258`).

**Import-Auflösung:**
1. `.pth`-Datei → `sys.path` enthält echtes `src/` **← GEWINNT**
2. `PYTHONPATH` → `mutants/src/` ← wird überschattet
3. Tests importieren echtes Package → Trampoline-Code wird nie ausgeführt

### Betroffene Datei

`mutmut_win/runner.py`, Methode `_mutants_env()` — setzt `PYTHONPATH`, berücksichtigt aber keine `.pth`-Dateien.

### Vorgeschlagener Fix

`_mutants_env()` sollte `.pth`-Dateien des Pakets unter Test temporär deaktivieren.

### Workaround

Externes Script das die `.pth`-Datei vor dem mutmut-win-Aufruf umbenennt und danach wiederherstellt:

```python
pth = Path(".venv/Lib/site-packages/_mypackage.pth")
bak = pth.with_suffix(".pth.mutmut_bak")
pth.rename(bak)
try:
    subprocess.run([sys.executable, "-m", "mutmut_win", *sys.argv[1:]])
finally:
    bak.rename(pth)
```

**Hinweis:** Dieser Workaround allein reicht nicht — er macht Bug 4 sichtbar.

---

## Bug 4: Nur mutierte Datei in `mutants/src/`, nicht gesamtes Package

**Schwere:** Critical — Clean Test Suite scheitert für alle Module mit Cross-Package-Imports
**Phase:** Clean Test Suite

### Symptom

```
Running clean test suite…
Error: Clean test run failed with exit code 4. Fix tests before mutating.
```

### Root Cause

mutmut-win kopiert nur die **mutierte Datei** nach `mutants/src/`, nicht den Rest des Packages:

```
mutants/src/nextgen_cot_mcp_server/domain/errors.py    ← NUR diese Datei
# FEHLT: infrastructure/__init__.py, infrastructure/identifiers.py, ...
```

Die `conftest.py` (kopiert nach `mutants/tests/`) importiert Cross-Package-Module:

```python
# tests/conftest.py
from nextgen_cot_mcp_server.infrastructure import identifiers  # FEHLT in mutants/src/
```

→ `ModuleNotFoundError` → pytest Exit Code 4

### Beweis

```bash
# Manuell aus mutants/ Verzeichnis:
PYTHONPATH=mutants/src python -m pytest tests/unit/test_domain_errors.py
# → ImportError: No module named 'nextgen_cot_mcp_server.infrastructure'

# Inhalt von mutants/src/:
# nextgen_cot_mcp_server/domain/errors.py  ← NUR DIESE DATEI
```

### Zusammenhang mit Bug 3

Bug 3 und Bug 4 sind verknüpft:
- **Mit `.pth` aktiv** → Python importiert über `.pth` statt `mutants/src/` → Trampoline greift nicht (Bug 3), aber Tests laufen durch
- **Ohne `.pth`** → Trampoline könnte greifen, aber Module fehlen in `mutants/src/` (Bug 4)
- **Netto-Effekt:** Nur Module deren Tests **keine Cross-Package-Imports** in conftest.py haben funktionieren

In unserem Projekt ist das nur `identifiers.py` (dessen conftest-Fixture genau dieses Modul importiert).

### Vorgeschlagener Fix

mutmut-win sollte das **gesamte Package** nach `mutants/src/` kopieren, nicht nur die mutierte(n) Datei(en). Die Trampoline-Injektion erfolgt nur in den mutierten Dateien.

### Workaround

Keiner der ohne Eingriff in mutmut-win funktioniert.

---

## Einziger funktionierender Einzelfall

Mit dem `.pth`-Workaround (Bug 3) konnte **ein einzelnes Modul** erfolgreich getestet werden:

```
Module:     src/nextgen_cot_mcp_server/infrastructure/identifiers.py
Ergebnis:   42 Mutants, 30 killed, 12 survived → Score: 71.4%
Dauer:      ~20 Sekunden
Bedingung:  .pth manuell umbenannt + Cache gelöscht + --tests-dir tests/unit/test_identifiers.py
```

Dieses Modul funktioniert weil `test_identifiers.py` + `conftest.py` nur Imports aus dem gleichen Package benötigen, die in `mutants/src/` vorhanden sind.

Alle anderen 12 Module scheitern an Bug 4 (fehlende Cross-Package-Abhängigkeiten).

---

## Gesamtbewertung

mutmut-win v1.0.6 ist für Projekte mit folgendem Setup **nicht einsatzfähig**:
- uv + hatchling editable install (`.pth`-Datei)
- Cross-Package-Imports in `conftest.py`
- pytest-asyncio + hypothesis (möglicherweise Ursache des Hangs)
- 300+ Tests (Statistik-Sammlung hängt bei ~79%)

**Empfehlung:** Bugs 1-4 upstream im mutmut-win Repository melden. Alternative Mutation-Testing-Tools evaluieren (z.B. Cosmic Ray, mutmut 3.x original auf WSL/Linux).
