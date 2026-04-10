# Bug Report: mutmut-win — WinError 32 bleibt in v1.0.8 bestehen (unvollstaendiger Bugfix)

| Feld                | Wert                                                                   |
|---------------------|------------------------------------------------------------------------|
| **Projekt**         | [mutmut-win](https://github.com/pgm1980/mutmut-win)                   |
| **Betroffene Versionen** | v1.0.7 (Ursprungsbug), v1.0.8 (Fix unvollstaendig)               |
| **Datei**           | `mutmut_win/file_setup.py`                                            |
| **Absturzstelle**   | Zeile 161 — `shutil.copy2(path, destination)` in `copy_also_copy_files()` |
| **v1.0.8-Fix-Stelle** | Zeile 210-219 — `_sanitise_mutants_pyproject()` (wird nie erreicht) |
| **Fehler**          | `PermissionError: [WinError 32]`                                      |
| **Schweregrad**     | Kritisch — blockiert jeden Mutations-Lauf komplett                     |
| **Plattform**       | Windows 10/11                                                          |
| **Python**          | 3.14.3                                                                 |
| **Datum**           | 2026-04-10                                                             |

---

## 1. Zusammenfassung

`mutmut-win run` bricht auf Windows mit `[WinError 32]` ab, bevor ein einziger Mutant getestet wird. Der Absturz passiert beim Kopieren von Dateien in das `mutants/`-Staging-Verzeichnis.

**v1.0.8 sollte diesen Bug fixen, behebt ihn aber nicht.** Der Bugfix fuegt Retry-Logik in `_sanitise_mutants_pyproject()` (Zeile 210-219) ein — einer Funktion, die erst **nach** der Kopierschleife aufgerufen wird. Der tatsaechliche Absturz passiert bereits in Zeile 161 (`shutil.copy2()`) innerhalb der Kopierschleife, die der Fix nicht beruehrt.

---

## 2. Fehlerbild

### Befehl (identisch in v1.0.7 und v1.0.8)

```bash
uv run mutmut-win run
```

### Konsolenausgabe

```
     also copying tests/
     also copying test/
     also copying setup.cfg
     also copying pyproject.toml
     also copying pytest.ini
     also copying .gitignore
     also copying C:\bugfixing\test_calculator.py
Error: [WinError 32] Der Prozess kann nicht auf die Datei zugreifen,
       da sie von einem anderen Prozess verwendet wird
```

Die letzte "also copying"-Zeile zeigt die Datei, bei deren Kopiervorgang der Fehler auftritt. Der Prozess endet sofort mit Exit-Code 1.

### Getestete Varianten — alle fehlgeschlagen

| Befehl                              | Ergebnis       |
|--------------------------------------|----------------|
| `mutmut-win run`                     | WinError 32    |
| `mutmut-win run --max-children 1`    | WinError 32    |
| `mutmut-win run --max-children 4`    | WinError 32    |
| `mutmut-win run --force`             | WinError 32    |
| `mutmut-win run --debug`             | WinError 32    |
| `mutmut-win run --dry-run`           | **Funktioniert** (kein Dateikopieren) |

---

## 3. Vollstaendiger Traceback

Die CLI faengt die Exception pauschal ab (`cli.py:163-164`) und gibt nur `Error: {exc}` aus. Der vollstaendige Traceback wurde durch direkten Aufruf der internen Funktionen ermittelt:

```python
from mutmut_win.config import load_config
from mutmut_win.file_setup import copy_src_dir, copy_also_copy_files

config = load_config()
copy_src_dir(config)
copy_also_copy_files(config)   # ← crasht
```

```
Traceback (most recent call last):
  File "<string>", line 6, in <module>
    copy_also_copy_files(config)
    ~~~~~~~~~~~~~~~~~~~~^^^^^^^^
  File "mutmut_win/file_setup.py", line 161, in copy_also_copy_files
    shutil.copy2(path, destination)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
  File "Python314/Lib/shutil.py", line 514, in copy2
    _winapi.CopyFile2(src_, dst_, flags)
    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^
PermissionError: [WinError 32] Der Prozess kann nicht auf die Datei zugreifen,
                 da sie von einem anderen Prozess verwendet wird
```

---

## 4. Aufrufkette

```
cli.py:162           orchestrator.run()
  orchestrator.py:282    copy_src_dir(config)             ← laeuft durch
  orchestrator.py:283    copy_also_copy_files(config)     ← crasht hier
    file_setup.py:154      for path_str in config.also_copy:
    file_setup.py:161        shutil.copy2(path, dest)     ← ABSTURZ (Zeile 161)
    file_setup.py:168      _sanitise_mutants_pyproject()  ← WIRD NIE ERREICHT
      file_setup.py:210-219  write_text() mit Retry       ← v1.0.8-Fix (unerreichbar)
  cli.py:163-164     except Exception: click.echo("Error: ...")
```

---

## 5. Analyse: Warum v1.0.8 den Bug nicht behebt

### Was v1.0.8 geaendert hat

In `_sanitise_mutants_pyproject()` wurde der nackte `write_text()`-Aufruf durch eine Retry-Schleife ersetzt:

```python
# VORHER (v1.0.7) — Zeile 210:
if cleaned != content:
    pyproject_path.write_text(cleaned, encoding="utf-8")        # ← kein Schutz

# NACHHER (v1.0.8) — Zeile 210-219:
if cleaned != content:
    import time
    for attempt in range(5):
        try:
            pyproject_path.write_text(cleaned, encoding="utf-8")
            break
        except OSError:
            if attempt < 4:
                time.sleep(0.1 * (2 ** attempt))                # 0.1s … 0.8s Backoff
```

### Warum das nicht hilft

`_sanitise_mutants_pyproject()` wird in Zeile 168 aufgerufen — **nach** der Kopierschleife (Zeile 154-163). Der Absturz passiert aber **innerhalb** der Kopierschleife in Zeile 161:

```python
# Zeile 154-163: Kopierschleife — HIER crasht es
for path_str in config.also_copy:
    print("     also copying", path_str)
    path = Path(path_str)
    destination = Path("mutants") / path
    if not path.exists():
        continue
    if path.is_file():
        shutil.copy2(path, destination)      # ← Zeile 161: ABSTURZ
    else:
        shutil.copytree(path, destination, dirs_exist_ok=True, ignore=_ignore_venvs)

# Zeile 168: Wird nur erreicht wenn die Schleife oben NICHT crasht
_sanitise_mutants_pyproject()                # ← v1.0.8-Fix sitzt hier drin
```

Der Fix schuetzt eine Stelle, die der Programmfluss nie erreicht.

### Visualisierung

```
copy_also_copy_files()
│
├─ for path_str in config.also_copy:       Zeile 154
│   ├─ shutil.copy2(path, destination)     Zeile 161  ──── CRASH ────╮
│   └─ shutil.copytree(...)                Zeile 163                 │
│                                                                     │
├─ _sanitise_mutants_pyproject()           Zeile 168  ← nie erreicht │
│   └─ write_text() mit Retry              Zeile 210-219  (v1.0.8)   │
│                                                                     │
╰─ Exception propagiert nach oben  ←──────────────────────────────────╯
     → orchestrator.py:283
       → cli.py:163 except Exception
         → "Error: [WinError 32] ..."
```

---

## 6. Ursache: Windows-Dateisperren

Auf Windows koennen Dateien nach einem Schreibvorgang fuer kurze Zeit gesperrt bleiben:

| Ursache                     | Mechanismus                                                     |
|-----------------------------|-----------------------------------------------------------------|
| **Windows Defender**        | Scannt neue/geaenderte Dateien automatisch im Hintergrund       |
| **Windows Search Indexer**  | Indiziert Dateien in ueberwachten Ordnern                       |
| **NTFS-Journaling**         | Metadaten-Updates nach Dateioperationen                         |
| **Editor/IDE File Watcher** | VS Code, JetBrains etc. ueberwachen Dateisystem-Events          |
| **shutil-Interna**          | Datei-Handles werden auf Windows nicht immer sofort freigegeben  |

Die `also_copy`-Schleife kopiert mehrere Dateien in schneller Folge. Zwischen dem Kopieren einer Datei und dem naechsten `shutil.copy2()`-Aufruf vergehen nur Mikrosekunden. Wenn die Zieldatei im `mutants/`-Verzeichnis noch von einem der obigen Prozesse gesperrt ist, schlaegt der Kopiervorgang mit `WinError 32` fehl.

---

## 7. Alle ungeschuetzten shutil-Aufrufe

Neben Zeile 161 gibt es weitere ungeschuetzte `shutil`-Aufrufe in derselben Datei:

| Zeile | Funktion                  | Aufruf                                     | Risiko   |
|-------|---------------------------|---------------------------------------------|----------|
| **116** | `copy_src_dir()`        | `shutil.copy2(source_path, target_path)`    | Hoch     |
| **125** | `copy_src_dir()`        | `shutil.copy2(source_path, target_path)`    | Hoch     |
| **161** | `copy_also_copy_files()`| `shutil.copy2(path, destination)`           | **Absturzstelle** |
| **163** | `copy_also_copy_files()`| `shutil.copytree(path, destination, ...)`   | Hoch     |

Alle vier Stellen sind anfaellig fuer denselben WinError 32 und sollten abgesichert werden.

---

## 8. Fix-Vorschlag

### Zentrale Retry-Hilfsfunktion

```python
import time
import shutil
from pathlib import Path


def _copy_with_retry(
    src: Path,
    dst: Path,
    *,
    is_tree: bool = False,
    max_attempts: int = 5,
    **kwargs,
) -> None:
    """Copy a file or directory tree with retry logic for Windows file locks.

    On Windows, recently written files can be temporarily locked by Defender,
    the Search Indexer, or NTFS journaling.  This wrapper retries with
    exponential backoff (0.1 s, 0.2 s, 0.4 s, 0.8 s) before giving up.
    """
    for attempt in range(max_attempts):
        try:
            if is_tree:
                shutil.copytree(src, dst, **kwargs)
            else:
                shutil.copy2(src, dst)
            return
        except OSError:
            if attempt < max_attempts - 1:
                time.sleep(0.1 * (2 ** attempt))
    # Letzter Versuch — Exception durchlassen wenn er auch fehlschlaegt
    if is_tree:
        shutil.copytree(src, dst, **kwargs)
    else:
        shutil.copy2(src, dst)
```

### Anwendung in `copy_src_dir()` (Zeile 116 und 125)

```python
# Zeile 116 — vorher:
shutil.copy2(source_path, target_path)
# nachher:
_copy_with_retry(source_path, target_path)

# Zeile 125 — vorher:
shutil.copy2(source_path, target_path)
# nachher:
_copy_with_retry(source_path, target_path)
```

### Anwendung in `copy_also_copy_files()` (Zeile 161 und 163)

```python
# Zeile 161 — vorher:
shutil.copy2(path, destination)
# nachher:
_copy_with_retry(path, destination)

# Zeile 163 — vorher:
shutil.copytree(path, destination, dirs_exist_ok=True, ignore=_ignore_venvs)
# nachher:
_copy_with_retry(path, destination, is_tree=True,
                 dirs_exist_ok=True, ignore=_ignore_venvs)
```

### v1.0.8-Fix beibehalten

Die bereits vorhandene Retry-Logik in `_sanitise_mutants_pyproject()` (Zeile 210-219) ist korrekt und sollte beibehalten werden — sie schuetzt den `write_text()`-Aufruf fuer den Fall, dass die Kopierschleife durchlaeuft aber die Datei danach noch gesperrt ist.

---

## 9. Reproduktion

### Minimales Setup

```bash
mkdir repro && cd repro
git init

cat > pyproject.toml << 'EOF'
[project]
name = "repro"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = ["pytest>=9.0"]
EOF

cat > calculator.py << 'EOF'
def add(a, b):
    return a + b
EOF

cat > test_calculator.py << 'EOF'
from calculator import add
def test_add():
    assert add(1, 2) == 3
EOF

uv sync
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.8" --dev
git add -A && git commit -m "init"
uv run mutmut-win run
```

### Erwartetes Ergebnis

Mutations-Lauf startet, Mutanten werden getestet.

### Tatsaechliches Ergebnis

```
     also copying ...
     also copying C:\repro\test_calculator.py
Error: [WinError 32] Der Prozess kann nicht auf die Datei zugreifen,
       da sie von einem anderen Prozess verwendet wird
```

### Voraussetzungen

- Windows 10/11
- Aktiver Dateiscanner (Windows Defender, Antivirus, Search Indexer)
- Dateien in der `also_copy`-Liste (automatisch vom Config-Loader erkannt)

---

## 10. Workaround

Es gibt **keinen zuverlaessigen Workaround**, da der Fehler beim Kopieren beliebiger Projektdateien auftritt.

Massnahmen, die die Wahrscheinlichkeit reduzieren aber nicht eliminieren:

1. **Windows Defender Exclusion** fuer das Projektverzeichnis und `mutants/`-Unterordner
2. **Windows Search Indexer** fuer das Projektverzeichnis deaktivieren
3. **Alle Editoren/IDEs schliessen**, die das Projekt mit File-Watchern ueberwachen
4. **Antivirus Realtime-Scanning** temporaer pausieren

---

## 11. Zeitleiste

| Version | Aenderung | Ergebnis |
|---------|-----------|----------|
| v1.0.7  | Erstveroeffentlichung | WinError 32 — Absturz in Zeile 161 |
| v1.0.8  | Retry-Logik in `_sanitise_mutants_pyproject()` (Zeile 210-219) | WinError 32 **besteht weiterhin** — Fix schuetzt die falsche Stelle |
| v1.0.9? | **Notwendig:** Retry-Logik auf alle `shutil.copy2()`/`copytree()`-Aufrufe | — |
