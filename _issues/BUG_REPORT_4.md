# Bug Report: mutmut-win — Absoluter Pfad in `also_copy` verursacht Self-Copy

| Feld                | Wert                                                                        |
|---------------------|-----------------------------------------------------------------------------|
| **Projekt**         | [mutmut-win](https://github.com/pgm1980/mutmut-win)                        |
| **Betroffene Versionen** | Alle (v1.0.4 bis v1.0.9, vermutlich auch aelter)                      |
| **Datei**           | `mutmut_win/config.py`                                                      |
| **Fehlerzeile**     | **182** — `[str(p) for p in project_dir.glob("test*.py")]`                  |
| **Symptom**         | `PermissionError: [WinError 32]` auf Python >= 3.14                         |
| **Eigentlicher Fehler** | `SameFileError` — Datei wird auf sich selbst kopiert                    |
| **Schweregrad**     | Kritisch — blockiert jeden Mutations-Lauf                                   |
| **Plattform**       | Windows 10/11, Python >= 3.14                                               |
| **Datum**           | 2026-04-10                                                                  |

---

## 1. Zusammenfassung

mutmut-win kopiert eine Datei auf sich selbst. Die Ursache ist ein absoluter Pfad in der `also_copy`-Liste, der entsteht weil `project_dir.glob("test*.py")` absolute `Path`-Objekte zurueckgibt. Wenn dieser absolute Pfad spaeter mit `Path("mutants") / absolute_path` verknuepft wird, verwirft Python den `"mutants/"`-Prefix — Quelle und Ziel sind identisch.

Auf **Python 3.14** nutzt `shutil.copy2()` die neue native Windows-API `_winapi.CopyFile2`, die diesen Self-Copy als `WinError 32` (ERROR_SHARING_VIOLATION) meldet. Auf **Python 3.13 und aelter** waere stattdessen ein `SameFileError` aufgetreten. Der `WinError 32` hat die Diagnose ueber fuenf Versionen hinweg in die falsche Richtung gelenkt.

---

## 2. Fehlerkette im Detail

### Schritt 1: Config-Laden (`config.py:256`)

```python
project_dir = Path.cwd()    # → Path("C:/bugfixing")  (ABSOLUT)
```

### Schritt 2: Default-`also_copy` erzeugen (`config.py:175-182`)

```python
default_also_copy: list[str] = [
    "tests/",           # relativ ✅
    "test/",            # relativ ✅
    "setup.cfg",        # relativ ✅
    "pyproject.toml",   # relativ ✅
    "pytest.ini",       # relativ ✅
    ".gitignore",       # relativ ✅
] + [str(p) for p in project_dir.glob("test*.py")]
#                       ↑
#   project_dir ist absolut → glob liefert absolute Pfade
#   → "C:\bugfixing\test_calculator.py"                    ← BUG
```

### Schritt 3: Dateien kopieren (`file_setup.py:193-200`)

```python
for path_str in config.also_copy:
    path = Path(path_str)                              # Path("C:\bugfixing\test_calculator.py")
    destination = Path("mutants") / path               # ← HIER geht es schief
    ...
    shutil.copy2(path, destination)
```

### Schritt 4: `Path.__truediv__` verwirft den linken Operanden

```python
>>> Path("mutants") / Path("C:/bugfixing/test_calculator.py")
WindowsPath('C:/bugfixing/test_calculator.py')
```

Wenn der rechte Operand ein absoluter Pfad ist, **ignoriert Python den linken Operanden**. Das ist dokumentiertes Verhalten von `pathlib.PurePath.__truediv__`. Die Destination wird identisch mit der Quelle.

### Schritt 5: Self-Copy schlaegt fehl

| Python-Version | `shutil.copy2()` Implementierung | Fehlermeldung |
|----------------|----------------------------------|---------------|
| **<= 3.13**    | `copyfile()` (pure Python)       | `SameFileError: ... are the same file` |
| **>= 3.14**    | `_winapi.CopyFile2()` (native)   | `PermissionError: [WinError 32]` |

Python 3.14 hat `shutil.copy2` geaendert: Es nutzt jetzt bevorzugt die native Windows-API `_winapi.CopyFile2()` (siehe `Lib/shutil.py:507-527`). Diese API prueft **nicht** auf Same-File und meldet den Self-Copy als Sharing Violation.

---

## 3. Beweis

### Test 1: Monkey-Patch — CopyFile2 deaktivieren

```python
import _winapi
delattr(_winapi, 'CopyFile2')   # Force pure-Python Fallback

from mutmut_win.file_setup import copy_also_copy_files
copy_also_copy_files(config)
```

Ergebnis — der **wahre** Fehler wird sichtbar:

```
shutil.SameFileError: WindowsPath('C:/bugfixing/test_calculator.py')
    and WindowsPath('C:/bugfixing/test_calculator.py') are the same file
```

### Test 2: Path-Verknuepfung mit absolutem Pfad

```python
>>> from pathlib import Path
>>> Path("mutants") / Path("C:/bugfixing/test_calculator.py")
WindowsPath('C:/bugfixing/test_calculator.py')           # "mutants/" ist weg!
```

### Test 3: Config-Inspektion

```python
>>> config.also_copy
['tests/', 'test/', 'setup.cfg', 'pyproject.toml', 'pytest.ini',
 '.gitignore', 'C:\\bugfixing\\test_calculator.py']
#                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#                  Absoluter Pfad — alle anderen sind relativ
```

---

## 4. Betroffener Code

### Primaere Ursache: `config.py` Zeile 182

```python
def _apply_default_also_copy(config: MutmutConfig, project_dir: Path) -> MutmutConfig:
    default_also_copy: list[str] = [
        "tests/",
        "test/",
        "setup.cfg",
        "pyproject.toml",
        "pytest.ini",
        ".gitignore",
    ] + [str(p) for p in project_dir.glob("test*.py")]   # ← Zeile 182: BUG
    #          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    #   project_dir ist absolut (Path.cwd())
    #   → glob gibt absolute Path-Objekte zurueck
    #   → str() erzeugt absolute Pfadstrings
    return config.model_copy(update={"also_copy": config.also_copy + default_also_copy})
```

### Sekundaere Absturzstelle: `file_setup.py` Zeile 196-200

```python
for path_str in config.also_copy:
    path = Path(path_str)
    destination = Path("mutants") / path    # ← Zeile 196: absoluter Pfad ueberschreibt "mutants/"
    ...
    shutil.copy2(path, destination)         # ← Zeile 200: Self-Copy → WinError 32 / SameFileError
```

---

## 5. Warum es frueher funktioniert hat

Auf **Python <= 3.13** haette `shutil.copy2()` den Self-Copy mit `SameFileError` abgewiesen. Es gibt zwei moegliche Gruende, warum das kein Problem war:

1. **`SameFileError` wurde irgendwo abgefangen** — unwahrscheinlich, da mutmut-win keinen solchen Handler hat.
2. **Das Projekt-Layout war anders** — wenn `tests_dir` auf ein Unterverzeichnis wie `tests/` zeigte und keine `test*.py`-Dateien im Root lagen, wurde die `glob`-Zeile nie zum Problem, weil sie nichts fand.

Auf diesem Projekt liegen die Tests direkt im Root (`test_calculator.py`), wodurch `project_dir.glob("test*.py")` einen Treffer liefert — mit absolutem Pfad.

---

## 6. Fix-Vorschlag

### Die glob-Ergebnisse muessen relativ zu `project_dir` gemacht werden.

**`config.py` Zeile 182 — vorher:**

```python
] + [str(p) for p in project_dir.glob("test*.py")]
```

**nachher:**

```python
] + [str(p.relative_to(project_dir)) for p in project_dir.glob("test*.py")]
```

Dadurch wird aus `C:\bugfixing\test_calculator.py` ein relatives `test_calculator.py`, und `Path("mutants") / Path("test_calculator.py")` ergibt korrekt `mutants/test_calculator.py`.

### Zusaetzliche Absicherung in `file_setup.py` (Defense in Depth)

In `copy_also_copy_files()` sollte ein Guard gegen absolute Pfade eingefuegt werden:

```python
for path_str in config.also_copy:
    path = Path(path_str)
    if path.is_absolute():
        # Absolute Pfade relativ zum CWD machen, damit
        # Path("mutants") / path korrekt funktioniert
        try:
            path = path.relative_to(Path.cwd())
        except ValueError:
            continue   # Pfad ausserhalb des Projekts — ueberspringen
    destination = Path("mutants") / path
    ...
```

---

## 7. Reproduktion

### Voraussetzung

- Windows 10/11
- Python >= 3.14
- `test*.py`-Dateien direkt im Projekt-Root (nicht in einem `tests/`-Unterverzeichnis)

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
[tool.mutmut]
paths_to_mutate = ["calculator.py"]
tests_dir = ["./"]
EOF

echo "def add(a, b): return a + b" > calculator.py
echo "from calculator import add
def test_add(): assert add(1, 2) == 3" > test_calculator.py

uv sync
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.9" --dev
git add -A && git commit -m "init"
uv run mutmut-win run
```

### Erwartetes Ergebnis

Mutations-Lauf startet und testet Mutanten.

### Tatsaechliches Ergebnis

```
     also copying C:\repro\test_calculator.py
Error: [WinError 32] Der Prozess kann nicht auf die Datei zugreifen,
       da sie von einem anderen Prozess verwendet wird
```

### Diagnose-Bestaetigung

```python
python -c "
from pathlib import Path
p = Path('mutants') / Path('C:/repro/test_calculator.py')
print(p)           # C:\repro\test_calculator.py  ← mutants/ ist weg
print(p.is_absolute())  # True
"
```

---

## 8. Chronologie der Fehldiagnosen

| Version | Annahme | Massnahme | Ergebnis |
|---------|---------|-----------|----------|
| v1.0.7  | WinError 32 = Windows-Dateisperre | — | Crash |
| v1.0.8  | `write_text()` in Sanitisation nicht abgesichert | Retry in `_sanitise_mutants_pyproject()` | Crash (falscher Ort) |
| v1.0.9  | `shutil.copy2()` in Kopierschleife nicht abgesichert | Retry via `_copy_with_retry()` | Crash (Retry hilft nicht bei Self-Copy) |
| **Tatsaechlich** | **Absoluter Pfad in `also_copy` → Self-Copy** | **glob-Ergebnisse relativieren** | — |

Der `WinError 32` auf Python 3.14 hat die Diagnose ueber drei Fix-Versuche hinweg in die Irre gefuehrt. Die Retry-Logik in v1.0.9 kann nicht helfen, weil kein Retry der Welt einen Self-Copy zum Erfolg bringt — die Datei ist **immer** gesperrt, weil sie gleichzeitig Quelle und Ziel ist.

---

## 9. Zusammenhang mit Python 3.14

Dies ist **kein Bug in Python 3.14**, aber ein Verhaltensunterschied, der den wahren Fehler maskiert:

```
shutil.copy2("file.py", "file.py")

Python <= 3.13:  → shutil.SameFileError("... are the same file")
                    Klarer Fehler, sofortige Diagnose

Python >= 3.14:  → _winapi.CopyFile2() → PermissionError: [WinError 32]
                    Irrefuehrender Fehler, fuehrt zu falschen Annahmen
                    ueber Dateisperren und Antivirus
```

`shutil.py:507-527` in Python 3.14 faengt nur `ERROR_PRIVILEGE_NOT_HELD` und `ERROR_ACCESS_DENIED` ab — `ERROR_SHARING_VIOLATION` (WinError 32) wird durchgereicht, ohne auf den pure-Python Fallback zurueckzufallen, der die `SameFileError`-Pruefung enthaelt.
