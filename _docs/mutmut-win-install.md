# mutmut-win Installation für Claude Code Python-Projekte

**Zweck:** Diese Anleitung installiert und konfiguriert mutmut-win in einem bestehenden Python-Projekt.
**Version:** v2.14.0
**Ausführung:** Sage Claude Code: *"Führe die Installation aus entsprechend mutmut-win-install.md"*

---

## Voraussetzungen

- Python >= 3.12 (Projektstandard: 3.14)
- Windows 10/11
- uv als Package Manager
- pyproject.toml vorhanden
- Git initialisiert
- Tests laufen mit pytest (>= 8.2 — der Worker übergibt Tests per pytest-`@argfile`) und sind grün

---

## Schritt 1: mutmut-win installieren

```bash
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.14.0" --dev
```

Verifikation:
```bash
uv run mutmut-win --version
```
Erwartete Ausgabe: `mutmut-win, version 2.14.0`

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

**Empfohlene Ergänzungen** (optional, projektabhängig):

```toml
[tool.mutmut]
# ... wie oben, zusätzlich:
do_not_mutate = ["**/migrations/*"]   # generierter/ausgenommener Code
type_check_command = ["mypy", "src/"] # Type-Checker als kostenloser Kill-Filter:
                                      # Mutanten, die mypy ablehnt, gelten als
                                      # gefangen — ohne einen einzigen Testlauf
```

Bei knappem RAM: `max_children = 4` ergänzen.
Vollständige Konfigurationsreferenz: README.md des mutmut-win-Repos.

**`.gitignore` ergänzen** (falls nicht vorhanden):
```gitignore
mutants/
.mutmut-cache/
```

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

Der Lauf validiert zuerst die unmutierte Suite im Staging (`mutants/`),
sammelt Test-Timing-Statistiken, verifiziert die Mutations-Mechanik
(Forced-Fail-Check) und führt dann alle Mutanten parallel aus. Das
Timeout-Modell kalibriert sich selbst (gemessener Startup-Sockel +
skalierte Testzeit) und wird zu Beginn des Laufs ausgegeben.

## Schritt 4: CLAUDE.md aktualisieren

Folgende Einträge in der CLAUDE.md des Projekts ergänzen, sofern noch nicht vorhanden.

### Unter PROJEKT-STANDARDS (Subagent-Prompt-Standard):
```
- mutmut-win Mutation Testing auf JEDEN neuen/geänderten Code (`uv run mutmut-win run --paths-to-mutate <geänderte Module>`)
- Mutation Score ≥ 80% auf neuem Code — surviving Mutants dokumentieren wenn unter 80%
```

### Unter Verifikation nach Subagent-Rückkehr:
```
- [ ] Mutation Testing: `uv run mutmut-win run --paths-to-mutate <geänderte Module>` — Score ≥ 80%?
```

### Unter Commands-Tabelle:
```
| `uv run mutmut-win run --paths-to-mutate src/<package>/` | Mutation Testing                      |
| `uv run mutmut-win results`                              | Mutation Testing Ergebnisse           |
```

### Unter Definition of Done (pro Sprint):
```
- [ ] Mutation Testing auf neuem/geändertem Code (`uv run mutmut-win run --paths-to-mutate <Module>`) — Score ≥ 80%
```

## Schritt 5: Erster richtiger Mutations-Lauf

```bash
uv run mutmut-win run
```

Ergebnisse anzeigen:
```bash
uv run mutmut-win results
```

Surviving Mutants inspizieren:
```bash
uv run mutmut-win browse                  # TUI-Browser (Dateien → Mutanten → Diff)
uv run mutmut-win show <mutant-name>      # Diff eines einzelnen Mutanten
```

Namens-Matching ist überall einheitlich (seit v2.12.0): exakter Name
oder Glob-Pattern (`*`, `?`, `[...]`). `show`/`apply` verlangen einen
EINDEUTIGEN Treffer — bei mehrdeutigem Pattern wird die Kandidatenliste
ausgegeben. Die `show`-Diffs sind patch-fähig (a/- und b/-Labels, echte
Zeilennummern der Originaldatei).

---

## Wichtige Hinweise

- **mutmut-win MUSS als dev-Dependency installiert bleiben.** Nicht entfernen. `uv run mutmut-win` nutzt `sys.executable` aus dem Projekt-venv.
- **`--paths-to-mutate` ist repeatable — ein Pfad pro Flag.** Mehrere Pfade hinter EINEM Flag werden als Mutanten-Namensfilter geparst und enden mit „No mutants match the given names":
  ```bash
  # FALSCH:
  uv run mutmut-win run --paths-to-mutate src/a.py src/b.py
  # RICHTIG:
  uv run mutmut-win run --paths-to-mutate src/a.py --paths-to-mutate src/b.py
  ```
- **Wiederholte Läufe sind billig:** Quell- und Konfigurations-Fingerprints überspringen unveränderte Dateien bei der Generierung; Ergebnisse liegen in einer SQLite-DB. Bei Konfigurationsänderung wird automatisch alles regeneriert. Bei Problemen mit altem Staging: `uv run mutmut-win run --force` für einen sauberen Neulauf.
- **Nach Änderung von `paths_to_mutate` (oder `--paths-to-mutate`-Wechsel): `--force` verwenden.** Das Test-zu-Mutant-Mapping stammt aus einem Stats-Cache des vorherigen Laufs; deckt der alte Cache die neu mutierten Module nicht ab, werden deren Mutanten ehrlich als `no tests` verbucht statt getestet. `--force` erzwingt eine frische Stats-Sammlung über das neue Staging.
- **`no tests` ist ein Befund, kein Fehler:** Mutanten, die kein Test abdeckt, werden ohne Testlauf als `no tests` verbucht und verlassen den Score-Nenner. Viele `no tests`-Einträge = Module ohne Testabdeckung.
- **Score-Semantik:** Kill-Klasse = killed + type-check-caught + infinite-loop-killed + segfault; Nenner = total − skipped − no tests − unchecked. `survived` ist die zu schließende Testlücke.
- **Exit-Codes von `run`:** 0 Erfolg, 1 Laufzeitfehler oder `--min-score` verfehlt, 2 ungültige Konfiguration/Option, 130 unterbrochen (Ctrl-C; Teilergebnisse persistiert, Score-Gate übersprungen).
- **Editable Installs (.pth):** Bei editierbaren Installationen (`uv pip install -e .`) kann die `.pth`-Datei in `site-packages/` die Trampolin-Mechanik überschatten. Workaround: `.pth`-Datei temporär umbenennen vor dem Lauf.
- **Langsame Suiten:** `clean_run_timeout` (Default 300 s) erhöhen, wenn die trampolinierte Suite im Staging länger braucht.

## Nützliche CLI-Flags

| Flag | Beschreibung |
|------|-------------|
| `--paths-to-mutate PATH` | Nur bestimmte Dateien/Verzeichnisse mutieren (repeatable, ein Pfad pro Flag) |
| `--since-commit HEAD~1` | Nur seit dem Commit geänderte Dateien |
| `--min-score 80` | Exit-Code 1 wenn Score < 80 % (für CI/CD und DoD) |
| `--output json` | Reines JSON auf stdout (Prosa geht nach stderr) |
| `--tests-dir DIR` | Test-Verzeichnis überschreiben |
| `--no-progress` | Keine Live-Fortschrittszeilen (End-Summary erscheint immer) |
| `--dry-run` | Mutanten zählen ohne Tests |
| `--max-children N` | Anzahl Worker-Prozesse |
| `--force` | Staging + Cache löschen und komplett neu starten |
| `--debug` | Volle Tracebacks bei Fehlern |

## Die Killer-Kombination für CI/CD und DoD

```bash
uv run mutmut-win run --since-commit HEAD~1 --min-score 80 --output json --no-progress
```

Eine Zeile: gezieltes inkrementelles Mutation Testing mit automatischem
Pass/Fail-Gate und maschinenlesbarem Output — `json.loads(stdout)`
funktioniert, alle Meldungen laufen über stderr.
