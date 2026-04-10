# mutmut-win Installation für Claude Code Python-Projekte

**Zweck:** Diese Anleitung installiert und konfiguriert mutmut-win in einem bestehenden Python-Projekt.
**Version:** v2.0.1
**Ausführung:** Sage Claude Code: *"Führe die Installation aus entsprechend mutmut-win-install.md"*

---

## Voraussetzungen

- Python >= 3.14
- Windows 10/11
- uv als Package Manager
- pyproject.toml vorhanden
- Git initialisiert

---

## Schritt 1: mutmut-win installieren

```bash
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.0.1" --dev
```

Verifikation:
```bash
uv run mutmut-win --version
```
Erwartete Ausgabe: `mutmut-win, version 2.0.1`

## Schritt 2: pyproject.toml konfigurieren

Füge folgende Sektion in `pyproject.toml` ein (falls nicht vorhanden):

```toml
[tool.mutmut]
paths_to_mutate = ["src/"]
tests_dir = ["tests/"]
```

**Anpassungen:**
- `paths_to_mutate`: Pfad(e) zum Quellcode der mutiert werden soll. Anpassen wenn der Code nicht unter `src/` liegt.
- `tests_dir`: Pfad(e) zu den Tests. Anpassen wenn die Tests nicht unter `tests/` liegen.

## Schritt 3: Verifikation — Erster Lauf

Zuerst prüfen ob die Tests ohne Mutation grün sind:
```bash
uv run pytest
```

Dann mutmut-win mit Dry-Run testen (zählt Mutanten ohne Tests auszuführen):
```bash
uv run mutmut-win run --dry-run
```

Wenn das funktioniert, einen echten Lauf starten (optional mit wenigen Workern):
```bash
uv run mutmut-win run --max-children 4
```

## Schritt 4: CLAUDE.md aktualisieren

Folgende Einträge in der CLAUDE.md des Projekts ergänzen, sofern noch nicht vorhanden.

### Unter PROJEKT-STANDARDS (Subagent-Prompt-Standard):
```
- mutmut-win Mutation Testing auf JEDEN neuen/geänderten Code (`uv run mutmut-win run --paths-to-mutate <geänderte Module>`)
- Mutation Score ≥ 97% auf neuem Code — surviving Mutants dokumentieren wenn unter 80%
```

### Unter Verifikation nach Subagent-Rückkehr:
```
- [ ] Mutation Testing: `uv run mutmut-win run --paths-to-mutate <geänderte Module>` — Score ≥ 97%?
```

### Unter Commands-Tabelle:
```
| `uv run mutmut-win run --paths-to-mutate src/<package>/` | Mutation Testing                      |
| `uv run mutmut-win results`                              | Mutation Testing Ergebnisse           |
```

### Unter Definition of Done (pro Sprint):
```
- [ ] Mutation Testing auf neuem/geändertem Code (`uv run mutmut-win run --paths-to-mutate <Module>`) — Score ≥ 97%
```

## Schritt 5: Erster richtiger Mutations-Lauf

```bash
uv run mutmut-win run
```

Ergebnisse anzeigen:
```bash
uv run mutmut-win results
```

---

## Wichtige Hinweise

- **mutmut-win MUSS als dev-Dependency installiert bleiben.** Nicht entfernen. `uv run mutmut-win` nutzt `sys.executable` aus dem Projekt-venv.
- **Wiederholte Läufe:** v2.0.1 aktualisiert geänderte Dateien automatisch (mtime-Vergleich). Bei Problemen: `uv run mutmut-win run --force` für einen sauberen Neulauf.
- **Editable Installs (.pth):** Bei editierbaren Installationen (`uv pip install -e .`) kann die `.pth`-Datei in `site-packages/` die Trampoline-Mechanik überschatten. Workaround: `.pth`-Datei temporär umbenennen vor dem Lauf.

## Nützliche CLI-Flags

| Flag | Beschreibung |
|------|-------------|
| `--paths-to-mutate PATH...` | Nur bestimmte Dateien/Verzeichnisse mutieren |
| `--min-score 80` | Exit code 1 wenn Score < 80% (für CI/CD und DoD) |
| `--output json` | Maschinenlesbarer JSON-Output |
| `--since-commit HEAD~1` | Nur seit letztem Commit geänderte Dateien |
| `--tests-dir DIR` | Test-Verzeichnis überschreiben |
| `--no-progress` | Keine Fortschrittsanzeige (für CI) |
| `--dry-run` | Mutanten zählen ohne Tests |
| `--max-children N` | Anzahl Worker-Prozesse |
| `--force` | Cache löschen und komplett neu starten |
| `--debug` | Debug-Output |

## Die Killer-Kombination für CI/CD und DoD

```bash
uv run mutmut-win run --since-commit HEAD~1 --min-score 80 --output json --no-progress
```

Eine Zeile: gezieltes inkrementelles Mutation Testing mit automatischem Pass/Fail Gate und maschinenlesbarem Output.
