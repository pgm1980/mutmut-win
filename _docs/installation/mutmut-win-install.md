# mutmut-win Installation für Claude Code Python-Projekte

<!-- PUBLICATION_STATE_START -->
<!-- PUBLICATION_STATE: external-live-check-required -->
Publication status for v2.21.1 is external mutable state. These immutable bytes assert neither presence nor absence; verify the exact annotated tag and matching GitHub release before use.
<!-- PUBLICATION_STATE_END -->

**Zweck:** Diese Anleitung installiert und konfiguriert mutmut-win in einem bestehenden Python-Projekt.
**Version:** v2.21.1 (verbindlicher Versionsstand dieser Anleitung)
**Ausführung:** Sage Claude Code: *"Führe die Installation aus entsprechend mutmut-win-install.md"*

> **Releasehinweis:** Vor der Installation gilt der kanonische externe
> Publikationsvertrag am Anfang dieser Anleitung. Das v2.21.0-Tag bleibt
> unverändert.

---

## Voraussetzungen

- Windows mit exakt CPython 3.14.7
- Windows 10/11
- uv als Package Manager
- pyproject.toml vorhanden
- Git initialisiert
- Tests laufen mit pytest (>= 8.2 und < 10 — selektive autoritative Ziele nutzt der Worker per pytest-`@argfile`) und sind grün

---

## Schritt 1: mutmut-win installieren

```bash
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.21.1" --dev
```

Verifikation:
```bash
uv run mutmut-win --version
```
Erwartete Ausgabe: `mutmut-win, version 2.21.1`

Scheitert die Live-Prüfung des Tags oder stimmt sein Ziel nicht mit dem
freigegebenen Commit überein, darf diese Installationszeile nicht ausgeführt
werden. Ein Quelltext-Versionsstring allein ist kein Publikationsbeweis.

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
(Forced-Fail-Check) und führt dann alle Mutanten parallel aus. Nichtautoritäre
Mappingdauern planen nur die Reihenfolge unabhängiger Mutanten-Tasks; jeder
Task behält die native pytest-Reihenfolge und das Vollsuite-Budget. Das
Timeout-Modell kalibriert sich selbst (gemessener Startup-Sockel + skalierte
Testzeit) und wird zu Beginn des Laufs ausgegeben.

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
- **Wiederholte Läufe sind billig:** Quell-, Test-, Konfigurations-, Import- und Dependency-Fingerprints überspringen unveränderte Generierung und dürfen frühere Vollsuite-Verdicts nur bei identischer Execution-Basis wiederverwenden. Änderungen an `paths_to_mutate` oder `--paths-to-mutate` invalidieren den betroffenen Plan automatisch; `--force` ist nur für einen bewusst vollständig neuen Staging-/Cacheaufbau nötig.
- **Test-Mapping bleibt korrektheitssicher:** Der aktuelle Collector kann Treffer aus Subprozessen, Threads oder xdist nicht vollständig beweisen. Beobachtete Dauern dürfen deshalb nur unabhängige Mutanten-Tasks planen; pytest behält innerhalb jedes Tasks seine native Reihenfolge und bricht beim ersten Fehler ab. Ein Survivor durchläuft die vollständige konfigurierte Suite, und ein fehlender Mappingeintrag erzeugt weder einen stillen Skip noch `no tests`.
- **`no tests` ist reserviert:** Dieser Status wird erst von einem künftig end-to-end autoritativen Mapper erzeugt. Der aktuelle nichtautoritative Collector lässt ungemappte Mutanten stets gegen die Vollsuite laufen; historische `no tests`-Zeilen bleiben im Anzeige- und Scorevertrag lesbar.
- **Score-Semantik:** Kill-Klasse = killed + type-check-caught + infinite-loop-killed + segfault; Nenner = total − skipped − no tests − unchecked. `survived` ist die zu schließende Testlücke.
- **Exit-Codes von `run`:** 0 Erfolg, 1 Laufzeitfehler oder `--min-score` verfehlt, 2 ungültige Konfiguration/Option, 130 unterbrochen (Ctrl-C; Teilergebnisse persistiert, Score-Gate übersprungen).
- **Editable Installs (.pth):** Projektinterne Editable-Pfade werden im Staging automatisch neutralisiert, damit sie die Trampolinmodule nicht überschatten; externe Editable-Quellen und `.pth`-Importwirkungen werden in die Execution-Basis gebunden. Eine manuelle Umbenennung in `site-packages` ist nicht erforderlich.
- **Langsame Suiten:** `clean_run_timeout` (Default 300 s) erhöhen, wenn die trampolinierte Suite im Staging länger braucht.
- **`@staticmethod`-Mutation ist strikt gegated (by-design):** Nur Methoden, die AUSSCHLIESSLICH mit `@staticmethod` dekoriert sind, werden mutiert. Trägt eine Methode `@staticmethod` zusammen mit einem weiteren Dekorator, bleibt sie ungetestet — der zweite Dekorator könnte zur Definitionszeit laufen oder den Trampolin-Freifunktions-Dispatch brechen. `@classmethod` wird aus demselben Grund nicht mutiert (der klassengebundene `__name__` ist read-only). Das ist eine bewusste, korrektheitswahrende Entscheidung (externe QA v2.19.0), kein Bug — ein „fehlender" Mutant auf einer mehrfach dekorierten Statisch-Methode ist erwartet.

## Nützliche CLI-Flags

| Flag | Beschreibung |
|------|-------------|
| `--paths-to-mutate PATH` | Nur bestimmte Dateien/Verzeichnisse mutieren (repeatable, ein Pfad pro Flag) |
| `--since-commit HEAD~1` | Nur seit dem Commit geänderte Dateien |
| `--min-score 80` | Vollständiges Projektgate: Exit 1 unter 80 %; mit Namens-, Pfad- oder `--since-commit`-Subset unzulässig (Exit 2) |
| `--output json` | Reines JSON auf stdout (Prosa geht nach stderr) |
| `--tests-dir DIR` | Test-Verzeichnis überschreiben |
| `--no-progress` | Keine Live-Fortschrittszeilen (End-Summary erscheint immer) |
| `--dry-run` | Mutanten zählen ohne Tests |
| `--profile {basic,advanced,all}` | Operator-Profil: `advanced` (Default) = mutmut-Basis + mutmut-win-Extras + Phase-2-Operatoren; `basic` = strikte mutmut-Parität (15 Basis-Operatoren); `all` = + aggressive Operatoren |
| `--max-children N` | Anzahl Worker-Prozesse |
| `--force` | Staging + Cache löschen und komplett neu starten |
| `--debug` | Volle Tracebacks bei Fehlern |

## Die Killer-Kombination für CI/CD und DoD

```bash
uv run mutmut-win run --min-score 80 --output json --no-progress
```

Eine Zeile: vollständiges Mutation Testing mit automatischem Pass/Fail-Gate
und maschinenlesbarem Output — `json.loads(stdout)` funktioniert, alle
Meldungen laufen über stderr. Inkrementelle `--since-commit`-, gezielte
`--paths-to-mutate`- und Namensläufe sind Diagnose-Subsets und dürfen nicht mit
`--min-score` als projektweiter Score ausgegeben werden.
