# mutmut-win v1.0.11 — Upgrade-Anleitung fuer Projekte mit uv + editable Install

**Datum:** 2026-04-10
**Betrifft:** Projekte die mutmut-win via `[tool.uv.sources]` als git-Dependency installieren
**Anlass:** BUG_REPORT_5 (nextgen-cot-mcp-server)

---

## Was v1.0.11 behebt

### uv erstellt leeres `.venv` in `mutants/` (Blocker in v1.0.10)

**Problem:** mutmut-win kopiert `pyproject.toml` nach `mutants/` (noetig fuer pytest-Konfiguration). `uv` erkennt diese `pyproject.toml` und erstellt dort automatisch ein leeres `.venv`. Dieses leere `.venv` ueberschattet das Parent-Venv — pytest, das Projekt-Package und alle Dependencies fehlen.

**Fix in v1.0.11:** `_mutants_env()` setzt jetzt `UV_PROJECT_ENVIRONMENT` auf das Parent-Venv. Damit weiss `uv`, dass es kein neues `.venv` in `mutants/` anlegen soll.

---

## Upgrade-Schritte

### 1. mutmut-win aktualisieren

```bash
uv remove mutmut-win
uv cache clean mutmut-win
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.11" --dev
```

### 2. Version verifizieren

```bash
uv run mutmut-win --version
# Erwartete Ausgabe: mutmut-win, version 1.0.11
```

### 3. Alte Artefakte loeschen

```bash
rm -rf mutants/ .mutmut-cache/
```

### 4. Wrapper-Scripts entfernen

Wenn Wrapper-Scripts erstellt wurden die `UV_PROJECT_ENVIRONMENT` manuell setzen (z.B. `scripts/run_mutmut.py`), sind diese **nicht mehr noetig**. mutmut-win v1.0.11 setzt die Variable intern.

Wrapper die folgendes tun koennen komplett entfernt werden:
- `UV_PROJECT_ENVIRONMENT` setzen
- `uv.lock` nach `mutants/` kopieren
- `[tool.uv.sources]` in `mutants/pyproject.toml` injizieren

### 5. Testen

```bash
# Einzelnes kleines Modul zum Verifizieren:
uv run mutmut-win run --paths-to-mutate src/<package>/domain/errors.py
```

---

## Was auf Projektseite zu tun bleibt

### Tests die `uv run` aufrufen muessen markiert werden

mutmut-win fuehrt Tests innerhalb von `mutants/` aus. In diesem Verzeichnis liegt eine **sanitisierte** `pyproject.toml` (ohne `[tool.uv.sources]`). Tests die `uv run <tool>` aufrufen scheitern dort, weil `uv` die git-basierten Dependencies nicht aufloesen kann.

**Betroffene Tests:** Alle Tests die `uv run`, `uv sync`, oder andere uv-Befehle als Subprozess ausfuehren. Typisches Beispiel:

```python
# test_architecture.py
def test_engine_independence_contract():
    result = subprocess.run(["uv", "run", "lint-imports"], ...)
    assert result.returncode == 0
```

**Loesung:** Diese Tests mit einem Marker versehen und in der mutmut-Konfiguration ausschliessen:

```python
# conftest.py oder tests/conftest.py
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "no_mutmut: skip during mutation testing")
```

```python
# test_architecture.py
@pytest.mark.no_mutmut
def test_engine_independence_contract():
    result = subprocess.run(["uv", "run", "lint-imports"], ...)
    assert result.returncode == 0
```

```toml
# pyproject.toml
[tool.mutmut]
paths_to_mutate = ["src/<package>/"]
tests_dir = ["tests/"]
pytest_add_cli_args = ["-m", "not no_mutmut"]
```

**Warum das kein mutmut-win-Bug ist:** Mutation Testing testet ob **Code-Mutationen** von Tests erkannt werden. Tests die externe Toolchains aufrufen (`uv run`, `npm test`, Docker-Commands, etc.) testen Infrastruktur, nicht Code-Logik. Sie sind per Definition nicht mutations-relevant und sollten uebersprungen werden.

---

## Bekannte Limitierung: Keine test-to-mutant Mappings

Die Warnung `"no test-to-mutant mappings found"` ist **erwartetes Verhalten** in der aktuellen Version. Der Subprocess-basierte Test-Runner kann keine In-Process-Trampoline-Hits an den Hauptprozess zurueckmelden.

**Konsequenz:** Jeder Mutant wird gegen die gesamte Test-Suite getestet statt nur gegen relevante Tests.

**Workaround fuer grosse Projekte:** `--paths-to-mutate` auf einzelne Module beschraenken, um die Laufzeit zu begrenzen:

```bash
# Statt das gesamte Package:
uv run mutmut-win run --paths-to-mutate src/<package>/

# Besser einzelne Module:
uv run mutmut-win run --paths-to-mutate src/<package>/domain/errors.py
uv run mutmut-win run --paths-to-mutate src/<package>/infrastructure/identifiers.py
```

---

## Zusammenfassung der Aenderungen v1.0.8 bis v1.0.11

| Version | Fix |
|---------|-----|
| v1.0.8 | Retry-Logik fuer `write_text()` in `_sanitise_mutants_pyproject()` |
| v1.0.9 | Trampoline `KeyError` behoben (`os.environ.get()` statt `os.environ[]`), Retry auf alle `shutil`-Aufrufe |
| v1.0.10 | Root Cause WinError 32: absolute Pfade in `also_copy` verursachten Self-Copy |
| **v1.0.11** | **`UV_PROJECT_ENVIRONMENT` in `_mutants_env()` — verhindert leeres `.venv` in `mutants/`** |
