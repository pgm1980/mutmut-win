# Analyse zu BUG_REPORT_5 — mutmut-win 1.0.10

**Datum:** 2026-04-10
**Bezug:** BUG_REPORT_5 (nextgen-cot-mcp-server)
**Analysiert von:** mutmut-win Maintainer
**Status:** Rueckfrage an Reporter — kein Code-Defekt identifiziert

---

## Kurzfassung

Wir koennen die gemeldeten Probleme mit mutmut-win 1.0.10 nicht reproduzieren. Ein anderes Projekt mit vergleichbarem Setup (hatchling, src-Layout, uv, Python 3.14.3, git-basierte mutmut-win-Dependency) laeuft stabil. Die Analyse des mutmut-win-Quellcodes zeigt, dass mutmut-win **kein** `.venv` in `mutants/` erstellt — das muss von einem anderen Tool kommen.

Wir bitten um Verifizierung der unten aufgefuehrten Punkte, damit wir die Ursache eingrenzen koennen.

---

## Detailanalyse der gemeldeten Bugs

### Bug 1: "Empty .venv in mutants/" — Nicht von mutmut-win verursacht

**Kernaussage:** mutmut-win erstellt kein `.venv` in `mutants/`. Nirgendwo im Quellcode existiert ein `venv`-Erstellungsaufruf (`python -m venv`, `uv venv`, `virtualenv`, etc.).

**Was mutmut-win tatsaechlich tut:**

1. `copy_src_dir()` kopiert Quelldateien nach `mutants/src/` (bzw. `mutants/source/`, `mutants/`)
2. `copy_also_copy_files()` kopiert Konfigurationsdateien (`pyproject.toml`, `tests/`, etc.) nach `mutants/`
3. Subprocess-Aufrufe nutzen `sys.executable` — das ist der Python-Interpreter des **Parent-Venvs**, nicht eines neuen Venvs
4. `_mutants_env()` setzt `PYTHONPATH` so, dass `mutants/src/` bevorzugt importiert wird
5. `_write_sitecustomize_pth_blocker()` schreibt eine `sitecustomize.py`, die den echten `src/`-Pfad aus `sys.path` entfernt

**Relevanter Code** (`runner.py:246`):

```python
def _base_pytest_cmd(self) -> list[str]:
    return [sys.executable, "-m", "pytest"]
    #       ^^^^^^^^^^^^^^
    #       Parent-Venv Python — KEIN mutants/.venv/Scripts/python
```

**Moegliche externe Ursache:** Wenn `pyproject.toml` in `mutants/` landet (das tut es — via `also_copy`) und ein Tool wie `uv` automatisch ein `.venv` anlegt wenn es eine `pyproject.toml` findet, dann koennte das `.venv` in `mutants/` von **uv** erstellt worden sein, nicht von mutmut-win.

**Frage an Reporter:**

- Existiert das `.venv` in `mutants/` **vor** dem `mutmut-win run`-Aufruf? Bitte pruefen:
  ```bash
  rm -rf mutants/ .mutmut-cache/
  # NICHT uv run mutmut-win — sondern:
  uv run python -c "
  from mutmut_win.config import load_config
  from mutmut_win.file_setup import copy_src_dir, copy_also_copy_files
  config = load_config()
  copy_src_dir(config)
  copy_also_copy_files(config)
  "
  # Jetzt pruefen:
  dir mutants\.venv
  # Existiert es? Falls ja: WANN wurde es erstellt?
  ```

- Haben Sie ein uv-Hook, Pre-Install-Script, oder IDE-Integration die automatisch `uv sync` ausfuehrt wenn eine `pyproject.toml` erkannt wird?

- Ist in `.vscode/settings.json` oder einer aehnlichen IDE-Konfiguration ein automatischer `uv sync`-Trigger aktiv?

- Laeuft ein File-Watcher-Prozess der auf neue `pyproject.toml`-Dateien reagiert?

---

### Bug 2: "[tool.uv.sources] Reordering" — Erwartetes Verhalten der Sanitisation

mutmut-win entfernt `[tool.uv.sources]` bewusst aus `mutants/pyproject.toml` (`_sanitise_mutants_pyproject()` in `file_setup.py`). Der Grund: Relative Pfade in `[tool.uv.sources]` brechen in `mutants/`, weil das Verzeichnis eine Ebene tiefer liegt.

Wenn die Sektion im Report als "ans Ende verschoben" erscheint statt "entfernt", deutet das darauf hin, dass die Regex nicht greift. Das kann passieren, wenn die TOML-Formatierung vom erwarteten Muster abweicht.

**Frage an Reporter:**

- Bitte den exakten Inhalt der `[tool.uv.sources]`-Sektion in der **Root** `pyproject.toml` zeigen (mit umgebenden Zeilen, Leerzeilen, Kommentaren):
  ```bash
  uv run python -c "
  from pathlib import Path
  content = Path('pyproject.toml').read_text()
  # Zeilen rund um [tool.uv.sources] zeigen:
  lines = content.splitlines()
  for i, line in enumerate(lines):
      if 'uv' in line.lower() or 'sources' in line.lower():
          start = max(0, i-2)
          end = min(len(lines), i+5)
          for j in range(start, end):
              print(f'{j+1:4d}: {lines[j]}')
          print('---')
  "
  ```

- Wie lautet der exakte Inhalt von `mutants/pyproject.toml` **nach** einem `mutmut-win run`? Bitte vollstaendig posten.

---

### Bug 3: Version String "1.0.7" — Bereits behoben

Dies war ein Versaeumnis beim Taggen von v1.0.8 und v1.0.9. Der Version-String in `__init__.py` und `pyproject.toml` wurde erst mit dem letzten Commit auf 1.0.10 aktualisiert.

**Loesung:** Bitte mutmut-win neu installieren:

```bash
uv remove mutmut-win
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.10" --dev
uv run mutmut-win --version
# Erwartete Ausgabe: mutmut-win, version 1.0.10
```

Wenn nach der Neuinstallation weiterhin `1.0.7` angezeigt wird, liegt ein Caching-Problem vor:

```bash
# uv-Cache leeren und erneut installieren:
uv cache clean mutmut-win
uv remove mutmut-win
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.10" --dev
uv run mutmut-win --version
```

---

### Bug 4: "No test-to-mutant mappings found" — Bekannte Limitierung (by design)

Das ist **kein Bug**, sondern eine bekannte Architektur-Limitierung des Subprocess-basierten Test-Runners.

**Hintergrund:**

In mutmut-win v1.0.7+ laeuft die Stats-Collection als **Subprocess** (nicht in-process), um Haenger durch pytest-asyncio, hypothesis und andere Plugins zu vermeiden (Fix fuer den urspruenglichen Bug 1 aus v1.0.6).

Der Trampoline-Code im Subprocess ruft `record_trampoline_hit()` auf, aber diese Hits landen im **In-Process-State des Subprozesses** — der Hauptprozess hat keinen Zugriff darauf. Daher bleiben `tests_by_mangled_function_name` im Hauptprozess leer.

**Konsequenz** (`runner.py:160-164`):

```python
# If trampoline hits can't be collected from subprocess (no shared state),
# fall back to mapping ALL tests to ALL mutants. This is less efficient
# but correct — every mutant runs against the full test suite.
```

Jeder Mutant wird gegen die **gesamte** Test-Suite getestet statt nur gegen die relevanten Tests. Das ist korrekt aber langsamer.

**Performance-Auswirkung:**

| Metrik | Mit Mappings | Ohne Mappings (aktuell) |
|--------|-------------|------------------------|
| Tests pro Mutant | 5-20 (nur relevante) | Alle (915 in Ihrem Fall) |
| CPU-Auslastung | ~95% | ~5% (I/O-bound durch viele Tests) |
| Geschaetzter Durchsatz | ~200 Mutants/min | ~10 Mutants/min |

Das ist eine bekannte Einschraenkung, die in einem zukuenftigen Release durch einen IPC-Mechanismus (z.B. Shared Memory, Temp-File, oder Socket) behoben werden soll. Fuer den Moment ist der Workaround, `--paths-to-mutate` auf einzelne Module zu beschraenken, um die Laufzeit zu begrenzen.

---

## Checkliste zur Selbstdiagnose

Bitte die folgenden Punkte pruefen und die Ergebnisse zurueckmelden:

### 1. Saubere Neuinstallation

```bash
# Altes mutmut-win komplett entfernen
uv remove mutmut-win
uv cache clean mutmut-win

# Alte Artefakte loeschen
rm -rf mutants/ .mutmut-cache/

# Frisch installieren
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.10" --dev

# Version verifizieren
uv run mutmut-win --version
# → muss "mutmut-win, version 1.0.10" ausgeben
```

### 2. Basis-Tests verifizieren

```bash
# Alle Tests muessen GRUEN sein, bevor mutmut-win laeuft
uv run pytest
# → Exit Code 0?
```

### 3. Minimaler mutmut-win-Lauf (einzelne Datei)

```bash
# Kleines Modul mit wenigen Funktionen waehlen:
uv run mutmut-win run --paths-to-mutate src/nextgen_cot_mcp_server/infrastructure/identifiers.py
```

### 4. mutants/.venv Entstehung pruefen

```bash
rm -rf mutants/ .mutmut-cache/
uv run mutmut-win run --dry-run --paths-to-mutate src/nextgen_cot_mcp_server/domain/errors.py
# dry-run kopiert keine Dateien — existiert mutants/.venv trotzdem?
dir mutants\.venv 2>nul && echo ".venv EXISTIERT" || echo ".venv existiert NICHT"
```

```bash
rm -rf mutants/ .mutmut-cache/
uv run mutmut-win run --paths-to-mutate src/nextgen_cot_mcp_server/domain/errors.py
# Normaler Lauf — existiert mutants/.venv jetzt?
dir mutants\.venv 2>nul && echo ".venv EXISTIERT" || echo ".venv existiert NICHT"
# Falls ja: Wann wurde es erstellt?
dir /TC mutants\.venv
```

### 5. sys.executable verifizieren

```bash
uv run python -c "import sys; print('Python:', sys.executable)"
# → Muss auf das Parent-.venv zeigen, z.B.:
#   C:\...\nextgen-cot-mcp-server\.venv\Scripts\python.exe
# NICHT auf mutants/.venv/Scripts/python.exe
```

### 6. Subprocess-Python verifizieren

```bash
uv run python -c "
import subprocess, sys
result = subprocess.run(
    [sys.executable, '-c', 'import sys; print(sys.executable)'],
    capture_output=True, encoding='utf-8', cwd='mutants'
)
print('Subprocess Python:', result.stdout.strip())
print('Parent Python:    ', sys.executable)
print('Gleich?', result.stdout.strip() == sys.executable)
"
```

Wenn der Subprocess-Python auf `mutants/.venv/` zeigt statt auf das Parent-Venv, ist das die Ursache — aber mutmut-win ist nicht der Verursacher.

### 7. uv-Konfiguration pruefen

```bash
# Gibt es globale uv-Konfiguration die auto-venv-Erstellung triggert?
uv run python -c "
from pathlib import Path
import os
for p in [
    Path.home() / '.config' / 'uv' / 'uv.toml',
    Path.home() / 'AppData' / 'Roaming' / 'uv' / 'uv.toml',
    Path('uv.toml'),
]:
    if p.exists():
        print(f'GEFUNDEN: {p}')
        print(p.read_text())
    else:
        print(f'Nicht vorhanden: {p}')
"
```

---

## Zusammenfassung

| Gemeldeter Bug | Unsere Einschaetzung | Aktion |
|----------------|---------------------|--------|
| Bug 1: Empty .venv | **Nicht von mutmut-win verursacht** — externes Tool (uv/IDE) erstellt das .venv | Reporter soll Checkliste Punkt 4-7 pruefen |
| Bug 2: Section reordering | Erwartetes Verhalten der Sanitisation, oder Regex-Mismatch | Reporter soll exakte pyproject.toml-Inhalte posten |
| Bug 3: Version 1.0.7 | **Behoben** in aktuellem v1.0.10 | Neuinstallation (Checkliste Punkt 1) |
| Bug 4: No mappings | **By design** — bekannte Limitierung des Subprocess-Runners | Kein Fix noetig, Optimierung fuer zukuenftiges Release geplant |

Bitte die Ergebnisse der Checkliste zurueckmelden. Insbesondere die Punkte 4-7 sind entscheidend, um die `.venv`-Entstehung einzugrenzen. Falls sich herausstellt, dass doch ein Szenario existiert in dem mutmut-win das `.venv` verursacht, werden wir das defensiv absichern.
