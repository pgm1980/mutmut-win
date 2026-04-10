# Bug Report: mutmut-win v1.0.7 — WinError 32 in `_sanitise_mutants_pyproject()`

| Feld             | Wert                                                                 |
|------------------|----------------------------------------------------------------------|
| **Projekt**      | [mutmut-win](https://github.com/pgm1980/mutmut-win)                 |
| **Version**      | 1.0.7                                                                |
| **Datei**        | `mutmut_win/file_setup.py`                                          |
| **Funktion**     | `_sanitise_mutants_pyproject()` (Zeile 171-210)                     |
| **Fehlerzeile**  | **210** — `pyproject_path.write_text(cleaned, encoding="utf-8")`    |
| **Schweregrad**  | **Kritisch** — blockiert jeden Mutations-Lauf auf betroffenen Systemen |
| **Plattform**    | Windows 10/11                                                        |
| **Python**       | 3.14.3                                                               |
| **Datum**        | 2026-04-10                                                           |

---

## 1. Zusammenfassung

`mutmut-win run` bricht auf Windows mit `[WinError 32]` ab, bevor ein einziger Mutant getestet wird. Die Ursache ist ein fehlender `try/except`-Block um die `write_text()`-Operation in `_sanitise_mutants_pyproject()`. Die direkt darüber liegende `read_text()`-Operation ist korrekt abgesichert — der Schreibzugriff jedoch nicht.

---

## 2. Fehlerbild

### Befehl

```bash
uv run mutmut-win run
```

### Ausgabe

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

### Verhalten

- Der Fehler tritt **deterministisch** auf — jeder Lauf schlägt fehl.
- `--max-children 1`, `--max-children 4`, `--force` und `--debug` ändern nichts.
- `--dry-run` funktioniert (kein Dateikopieren nötig).

---

## 3. Ursachenanalyse

### Ablauf in `copy_also_copy_files()` (Zeile 136-168)

```
Schritt 1:  Dateien in mutants/ kopieren (Zeile 154-163)
            -> shutil.copy2() / shutil.copytree()
            -> "also copying ..." wird gedruckt

Schritt 2:  _sanitise_mutants_pyproject() aufrufen (Zeile 168)
            -> mutants/pyproject.toml lesen  (Zeile 187-190)  ✅ try/except OSError
            -> Regex-Bereinigung durchführen (Zeile 196-207)
            -> mutants/pyproject.toml schreiben (Zeile 210)   ❌ KEIN try/except
```

### Das Problem

Auf Windows können frisch kopierte Dateien für kurze Zeit gesperrt sein durch:

- **Windows Defender / Antivirus** — scannt neue Dateien automatisch
- **Windows Search Indexer** — indiziert neue Dateien in überwachten Ordnern
- **NTFS-Journaling** — Dateisystem-Metadaten werden noch geschrieben
- **shutil-Interna** — Datei-Handles werden auf Windows nicht sofort freigegeben

Die Zeitspanne zwischen `shutil.copy2()` (Zeile 161) und `write_text()` (Zeile 210) beträgt nur wenige Millisekunden — zu kurz, damit Windows die Datei verlässlich freigibt.

### Asymmetrie im Error-Handling

```python
# Zeile 187-190: Lesen — korrekt abgesichert ✅
try:
    content = pyproject_path.read_text(encoding="utf-8")
except OSError:
    return

# Zeile 210: Schreiben — NICHT abgesichert ❌
pyproject_path.write_text(cleaned, encoding="utf-8")
```

Der `read_text()`-Aufruf hat einen `try/except OSError`-Block mit sauberem Fallback (`return`). Der `write_text()`-Aufruf direkt darunter hat **keinen** — ein `OSError` (einschliesslich `WinError 32`) propagiert ungefangen nach oben und beendet den gesamten Prozess.

---

## 4. Betroffener Code

**Datei:** `mutmut_win/file_setup.py`, Funktion `_sanitise_mutants_pyproject()`

```python
def _sanitise_mutants_pyproject() -> None:                          # Zeile 171
    pyproject_path = Path("mutants") / "pyproject.toml"             # Zeile 183
    if not pyproject_path.exists():                                 # Zeile 184
        return                                                      # Zeile 185

    try:                                                            # Zeile 187
        content = pyproject_path.read_text(encoding="utf-8")        # Zeile 188
    except OSError:                                                 # Zeile 189
        return                                                      # Zeile 190

    import re                                                       # Zeile 193

    cleaned = re.sub(                                               # Zeile 196
        r'\[tool\.uv\.sources\]\s*\n(?:(?!\[)[^\n]*\n)*',
        '',
        content,
    )

    cleaned = re.sub(                                               # Zeile 203
        r'\[tool\.uv\]\s*\n(?=\[|\Z)',
        '',
        cleaned,
    )

    if cleaned != content:                                          # Zeile 209
        pyproject_path.write_text(cleaned, encoding="utf-8")        # Zeile 210  ← BUG
```

---

## 5. Reproduktion

### Minimales Setup

```bash
mkdir repro && cd repro
git init
echo '[project]
name = "repro"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = []

[dependency-groups]
dev = ["pytest>=9.0"]' > pyproject.toml

echo 'def add(a, b):
    return a + b' > calculator.py

echo 'from calculator import add
def test_add():
    assert add(1, 2) == 3' > test_calculator.py

uv sync
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v1.0.7" --dev
git add -A && git commit -m "init"
uv run mutmut-win run
```

### Erwartetes Ergebnis

Mutations-Lauf startet und testet Mutanten.

### Tatsaechliches Ergebnis

```
Error: [WinError 32] Der Prozess kann nicht auf die Datei zugreifen,
       da sie von einem anderen Prozess verwendet wird
```

### Voraussetzungen

- Windows 10/11
- `pyproject.toml` enthält `[tool.uv.sources]`-Sektion (wird von `uv add ... --dev` mit Git-Source automatisch erzeugt)
- Aktiver Dateiscanner (Windows Defender, Antivirus, Search Indexer)

---

## 6. Fix-Vorschlag

### Variante A: try/except analog zum read-Block (minimal)

```python
if cleaned != content:
    try:
        pyproject_path.write_text(cleaned, encoding="utf-8")
    except OSError:
        pass  # Sanitisation ist optional — Lauf kann ohne fortfahren
```

### Variante B: Retry mit Backoff (robust)

```python
import time

if cleaned != content:
    for attempt in range(5):
        try:
            pyproject_path.write_text(cleaned, encoding="utf-8")
            break
        except OSError:
            if attempt < 4:
                time.sleep(0.1 * (2 ** attempt))  # 0.1s, 0.2s, 0.4s, 0.8s
            # Letzter Versuch fehlgeschlagen — still weitermachen
```

### Empfehlung

**Variante B** ist vorzuziehen, da die Sanitisation einen echten Zweck erfüllt (verhindert "Distribution not found"-Fehler bei relativen Pfaden). Ein stiller Fallback (Variante A) könnte zu schwer debugbaren Folgefehlern führen.

---

## 7. Workaround

Bis der Bug gefixt ist, kann die `[tool.uv.sources]`-Sektion manuell aus `pyproject.toml` entfernt werden, **bevor** `mutmut-win run` aufgerufen wird. Dann hat `_sanitise_mutants_pyproject()` nichts zu bereinigen und überspringt den `write_text()`-Aufruf (Zeile 209: `cleaned == content`).

```bash
# Vor dem Lauf:
# [tool.uv.sources]-Sektion aus pyproject.toml entfernen oder auskommentieren
uv run mutmut-win run
```

**Achtung:** Danach `uv sync` erneut ausführen, damit uv die Source-Referenz wiederherstellt.
