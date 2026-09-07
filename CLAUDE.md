# mutmut-win

<!-- PUBLICATION_STATE_START -->
<!-- PUBLICATION_STATE: external-live-check-required -->
Publication status for v2.21.1 is external mutable state. These immutable bytes assert neither presence nor absence; verify the exact annotated tag and matching GitHub release before use.
<!-- PUBLICATION_STATE_END -->

## Projekt

- **Stack**: Windows + CPython 3.14.7 (exactly; no Linux/POSIX or older-Python support)
- **Repository**: https://github.com/pgm1980/mutmut-win.git
- **Ziel**: 

---

## Verbindliche Tool-Nutzung (OBERSTE DIREKTIVEN — NICHT VERHANDELBAR)

Die folgenden Tools MÜSSEN während der gesamten Entwicklung aktiv eingesetzt werden — sowohl in der Hauptsession als auch in Subagenten. Kein Fallback auf generische Alternativen ohne dokumentierte Begründung.

**Konfigurative Durchsetzung:** Zusätzlich zu diesen Direktiven sind Filesystem-Bash-Befehle und `pwsh` **hart gesperrt** via `.claude/settings.json`. Selbst bei Nichtbeachtung dieser Regeln werden `cat`, `ls`, `grep`, `find`, `cp`, `mv`, `rm`, `pwsh` etc. vom Harness mit `Permission denied` blockiert. Siehe Sektion [Konfigurative Durchsetzung via settings.json](#konfigurative-durchsetzung-via-settingsjson) für die vollständige Liste.

### Subagenten-Policy

Subagenten haben seit Claude Code v2.1.x vollen Zugriff auf alle **MCP-Server**, **Plugins** und **Skills** der Hauptsession. 
Die frühere Einschränkung (kein MCP-, Plugin und Skill-Zugriff für Subagenten) wurde durch Anthropic behoben.

#### Einsatz von Subagenten

Subagenten MÜSSEN für parallelisierbare Aufgaben eingesetzt werden. 
Sie erben automatisch alle MCP-Server, Plugins sowie Skills der Hauptsession und MÜSSEN die gleichen Quality-Standards einhalten wie die Hauptsession.

**ERLAUBT:**
- `subagent-driven-development` Skill für Task-basierte Implementierung mit Review-Zyklen
- `dispatching-parallel-agents` Skill für unabhängige, parallele Aufgaben
- `executing-plans` Skill für Plan-Ausführung in separater Session
- Code Reviews via Subagent (mit Serena + Semgrep Zugriff)

**PFLICHT für jeden Subagent-Prompt:**
Jeder Subagent-Prompt MUSS folgende Regeln enthalten, damit der Subagent die Projekt-Standards kennt:

```
PROJEKT-STANDARDS (NICHT VERHANDELBAR):
- FS MCP Server für ALLE Filesystem-Operationen (KEIN cat, cp, mv, rm, find, grep via Bash)
- Serena für Code-Navigation (KEIN Grep für Klassen/Funktionen/Variablen)
- Context7 VOR Nutzung neuer APIs konsultieren
- Kanonisches Semgrep-Releasegate auf dem vollständigen Git-owned Scope; keine Raw- oder Changed-file-Scans als PASS-Ersatz
- Bei Release-/Workflowarbeit den kanonischen nativen Release-Wrapper ausführen; er prüft die drei manifestgebundenen nativen Werkzeuge und Zizmor 1.30.0 offline in den Personas regular und pedantic
- Ruff Lint + Format auf JEDE geänderte Datei — 0 Findings
- mypy strict — 0 Errors
- pytest + hypothesis für alle Tests — kein unittest.TestCase
- Kein `# noqa` ohne Kommentar-Begründung direkt darüber
- Kein `# type: ignore` ohne spezifischen Error-Code und Begründung
- Type Hints für ALLE öffentlichen APIs — strict Mode
- Google-Style Docstrings für alle öffentlichen Klassen/Funktionen
- Pydantic-Models für alle Datenstrukturen — keine rohen Dicts
- Alle neuen Module: Package-Struktur muss der src/-Verzeichnisstruktur entsprechen
- `uv run` für ALLE Ausführungen (nicht `python` direkt)
- mutmut-win Mutation Testing auf JEDEN neuen/geänderten Code (`uv run mutmut-win run --paths-to-mutate <geänderte Module>`)
- Mutation Score ≥ 80% auf neuem Code — surviving Mutants dokumentieren wenn unter 80%
```

#### Verifikation nach Subagent-Rückkehr

Auch wenn Subagenten MCP-Zugriff haben, MUSS die Hauptsession nach jeder Subagent-Rückkehr stichprobenartig verifizieren:

- [ ] Ruff: 0 Lint-Findings? (`uv run ruff check --no-cache .` selbst ausführen)
- [ ] mypy: 0 Errors? (`uv run mypy --no-incremental --cache-dir=nul src/` selbst ausführen)
- [ ] Alle Tests grün? (`uv run --no-sync pytest -p no:cacheprovider` selbst ausführen)
- [ ] Serena `get_symbols_overview` auf neue Dateien — Strukturcheck
- [ ] Bei Security-relevantem Code: das kanonische Semgrep-Releasegate selbst bestätigen
- [ ] Bei Release-/Workflowarbeit: den kanonischen nativen Release-Wrapper selbst bestätigen
- [ ] Mutation Testing: `uv run mutmut-win run --paths-to-mutate <geänderte Module>` — Score ≥ 80%?

**Vertrauen, aber verifizieren.** Subagent-Aussagen "Build sauber, Tests grün" sind Hinweise, keine Beweise.

#### Subagent-Prompt-Standard

Jeder Subagent-Prompt MUSS die folgenden 5 Sektionen enthalten. Unvollständige Prompts führen zu schlechter Agent-Qualität.

```
## KONTEXT
[Wo stehen wir im Sprint? Was wurde bisher gemacht? Welche Dateien/Module sind betroffen?]

## ZIEL
[Exakt was der Agent tun soll — ein klar abgegrenztes Ergebnis, nicht vage]

## CONSTRAINTS
[Was der Agent NICHT tun darf — z.B. keine anderen Module ändern, keine Breaking Changes]

## MCP-ANWEISUNGEN
[Welche MCP-Server für diese Aufgabe relevant sind und wie sie eingesetzt werden sollen]
Beispiel:
- Serena: `find_symbol` vor jeder Code-Änderung, `get_symbols_overview` auf neue Dateien
- Semgrep: kanonisches Releasegate auf dem vollständigen Git-owned Scope vor Abschluss
- Context7: Bei Nutzung neuer APIs konsultieren
- FS MCP: Für alle Filesystem-Operationen (kein cat/cp/rm)

## OUTPUT
[Was der Agent zurückmelden soll — geänderte Dateien, Zusammenfassung, Build/Test-Status, offene Probleme]
```

**Beispiel eines vollständigen Subagent-Prompts:**
```
## KONTEXT
Sprint 3, Task 2: Wir implementieren den CacheService. Task 1 (Models) ist abgeschlossen.
Betroffene Dateien: src/<package>/infrastructure/cache.py (neu),
src/<package>/domain/cache_models.py (neu)

## ZIEL
Implementiere CacheService mit folgenden Methoden:
- get(key: str) → CacheEntry | None
- set(key: str, value: Any, ttl: int) → None
- invalidate(key: str) → bool
Inklusive Unit Tests mit pytest + hypothesis für Roundtrip-Properties.

## CONSTRAINTS
- Keine Änderungen an bestehenden Service-Klassen
- Keine neuen PyPI-Pakete ohne Context7-Prüfung
- asyncio-basiert, kein Threading

## MCP-ANWEISUNGEN
- Serena: get_symbols_overview auf base_service.py um bestehende Patterns zu verstehen
- Context7: asyncio.Lock API prüfen (Reentrancy, Timeout)
- Semgrep: kanonisches Releasegate nach Implementierung
- FS MCP: Für alle Dateioperationen

## OUTPUT
- Liste geänderter/neuer Dateien
- Ruff/mypy-Status (0 Findings, 0 Errors)
- Test-Status (alle grün)
- Offene Fragen oder Probleme
```

#### Worktree-Isolation (PFLICHT bei parallelen Edit-Agents)

Wenn mehrere Subagenten **parallel Code editieren**, MÜSSEN sie mit `isolation: "worktree"` gestartet werden. 
Ohne Worktree-Isolation überschreiben sich parallele Agents gegenseitig.

| Agent-Typ                                                | `isolation: "worktree"` | Begründung             |
|----------------------------------------------------------|-------------------------|------------------------|
| Parallele Implementierung (2+ Agents editieren Code)     | **PFLICHT**             | Verhindert Konflikte   |
| Sequentielle Implementierung (1 Agent nach dem anderen)  | Nicht nötig             | Kein Konfliktrisiko    |
| Code Review (read-only)                                  | Nicht nötig             | Keine Änderungen       |
| Exploration/Recherche (read-only)                        | Nicht nötig             | Keine Änderungen       |

**Nach Worktree-Agent-Rückkehr:**
1. Änderungen aus dem Worktree in den Hauptbranch mergen
2. Bei Konflikten: Hauptsession löst Konflikte manuell
3. Build + Test nach dem Merge ausführen

#### MaxTurns-Empfehlungen (PFLICHT)

Jeder Subagent-Aufruf MUSS einen `max_turns`-Parameter enthalten, um Endlosschleifen bei autonomem Betrieb zu verhindern.

| Agent-Aufgabe                         | `max_turns` | Begründung                                |
|---------------------------------------|-------------|-------------------------------------------|
| Feature-Implementierung (komplex)     | 40–50       | Braucht Platz für TDD-Zyklen, Refactoring |
| Feature-Implementierung (einfach)     | 20–30       | Weniger Zyklen nötig                      |
| Code Review                           | 15–20       | Lesen + Analysieren + Report              |
| Exploration/Recherche                 | 10–15       | Gezielte Suche, nicht open-ended          |
| Quick Fix / Bug Fix                   | 10–15       | Fokussierte Änderung                      |
| Security Audit (Semgrep)              | 10–15       | Scan + Analyse + Report                   |

**Bei Überschreitung:** Wenn ein Agent sein `max_turns`-Limit erreicht, MUSS die Hauptsession bewerten:
- War die Aufgabe zu groß? → In kleinere Tasks aufteilen
- Steckt der Agent in einer Schleife? → Anderen Ansatz wählen
- Braucht er mehr Kontext? → Neuen Agent mit besserem Prompt dispatchen

#### Error Recovery Pattern (PFLICHT)

Wenn ein Subagent fehlschlägt oder ein unvollständiges Ergebnis liefert:

```
     ┌─────────────────────┐
     │ Agent meldet Failure│
     └──────────┬──────────┘
                │
                ▼
┌─────────────────────────────────┐
│ Hauptsession analysiert Fehler  │
│ (Transcript lesen, Build prüfen)│
└───────────────┬─────────────────┘
                │
          ┌─────┴─────┐
          │           │
          ▼           ▼
┌──────────────┐  ┌──────────────┐
│ Trivial      │  │ Komplex/     │
│ (Typo,Import)│  │ Architektur  │
│              │  │              │
└──────┬───────┘  └──────┬───────┘
       │                 │
       ▼                 ▼
 ┌──────────┐  ┌────────────────────┐
 │ Fix-Agent│  │ Hauptsession löst  │
 │ mit Error│  │ selbst (kein Agent)│
 │ + Context│  │                    │
 └────┬─────┘  └────────────────────┘
      │
      ▼
┌──────────────────────┐
│ Max 2 Retry-Zyklen   │
│ Dann → Hauptsession  │
└──────────────────────┘
```

**Regeln:**
1. **Nie manuell fixen nach Agent-Failure** ohne den Fehler zu verstehen — Kontext-Pollution vermeiden
2. **Fix-Agent** bekommt: Original-Prompt + Fehlermeldung + relevante Teile des Agent-Transcripts
3. **Max 2 Retries** — nach 2 gescheiterten Fix-Agents eskaliert die Hauptsession und löst selbst
4. **Bei Lint/Type-Fehlern**: Erst `uv run ruff check --no-cache .` und `uv run mypy --no-incremental --cache-dir=nul src/` Output analysieren, dann gezielten Fix-Agent mit exakter Fehlermeldung dispatchen
5. **Bei Test-Fehlern**: Erst `uv run --no-sync pytest -p no:cacheprovider` Output analysieren, dann Fix-Agent mit Failed-Test-Namen + Stack Trace dispatchen

### Serena — Symbolbasierte Code-Analyse

Serena ist als MCP-Server verfügbar und bietet präzise, symbolbasierte Code-Navigation via Jedi/Pyright.
**Serena MUSS bevorzugt vor Grep/Glob/Read verwendet werden**, wenn es um Code-Analyse geht — während der gesamten Implementierung und bei Code-Navigation.

**Wann Serena verwenden (IMMER zuerst):**
- **Import-Fehler / NameError**: `find_symbol` um das fehlende Symbol zu lokalisieren, `find_referencing_symbols` um alle Aufrufer zu finden
- **Test-Failures**: `find_symbol` für die fehlschlagende Funktion, `get_symbols_overview` für das Testmodul, `find_referencing_symbols` um die Aufrufkette zu verstehen
- **Refactoring**: `rename_symbol` statt manuelles Suchen/Ersetzen, `find_referencing_symbols` um Impact zu prüfen
- **Code verstehen**: `get_symbols_overview` für Datei-Überblick, `find_symbol` mit `include_body=true` für Implementierungsdetails
- **Neue Dateien erkunden**: `get_symbols_overview` IMMER zuerst, bevor eine Datei gelesen wird

**Serena-Tools in Reihenfolge der Präferenz:**
1. `get_symbols_overview` — Erster Überblick über eine Datei (Klassen, Funktionen, Variablen)
2. `find_symbol` — Symbol nach Name finden (mit `include_body=true` für Quelltext)
3. `find_referencing_symbols` — Wer ruft dieses Symbol auf? Wo wird es verwendet?
4. `rename_symbol` — Sicheres Umbenennen über die gesamte Codebase
5. `replace_symbol_body` — Gezielter Ersatz einer Funktion/Klasse
6. `insert_after_symbol` / `insert_before_symbol` — Code an symbolischer Position einfügen
7. `search_for_pattern` — Regex-Suche (nur wenn symbolische Suche nicht passt)

**Wann Grep/Glob als Fallback erlaubt:**
- Suche in Nicht-Code-Dateien (TOML, JSON, YAML, Markdown, Notebooks)
- Suche nach Textmustern die keine Code-Symbole sind (z.B. Fehlermeldungen, Konfigurationswerte)
- Suche nach Dateinamen (`Glob`)

**VERBOTEN bei Code-Analyse:**
- **NICHT** `Grep` verwenden um Klassen, Funktionen oder Variablen zu finden — Serena nutzen
- **NICHT** `Read` auf eine ganze Datei anwenden um ein Symbol zu finden — `find_symbol` nutzen
- **NICHT** manuell Suchen/Ersetzen für Umbenennungen — `rename_symbol` nutzen

### Semgrep — Security-Scanning

Semgrep MUSS ausschließlich über den getrackten, fail-closed Release-Wrapper ausgeführt werden. Der Wrapper bindet Semgrep 1.175.0 aus `uv.lock`, spiegelt den vollständigen Git-owned Release-Scope in ein externes Root, verwendet das content-gepinnte Offline-Regelbundle und validiert Findings, Parserfehler, übersprungene Regeln, Fixpoint-Timeouts sowie Manifest-/Target-/Policy-/TOCTOU-Drift.

Vor jedem Sync oder Gate mit Releaseevidenz MUSS `UV_PROJECT_ENVIRONMENT` auf
ein frisches absolutes Verzeichnis außerhalb des Checkouts zeigen.
`HYPOTHESIS_STORAGE_DIRECTORY` MUSS ebenfalls auf ein absolutes Verzeichnis
außerhalb des Checkouts zeigen; Hypothesis 6.151.9 schreibt dort Cachebytes,
ohne selbst eine `.gitignore` anzulegen. Im Release-Checkout sind `.venv` und
Werkzeug-Caches mit eigener `.gitignore` oder `.hypothesis`-Cachebytes
unzulässig.

```bash
uv sync --locked --only-group security --no-install-project
uv run --no-sync python -I scripts/semgrep_release_gate.py
```

**Wann das kanonische Gate verwenden (PFLICHT):**
- **Vor jedem Sprint- und Release-Abschluss**: vollständiger Git-owned Release-Scope
- **Bei Code Reviews und nach sicherheitsrelevantem Code**: Auth, Crypto, Input-Validierung, Deserialisierung, Pickle-Loading
- **AI-spezifisch**: Model-Loading, User-Input-to-Prompt-Pipelines, API-Key-Handling
- **Supply-Chain-Analyse**: zusätzlich bei neuen PyPI-Abhängigkeiten den gelockten Dependency-Audit ausführen

**VERBOTEN:**
- **NICHT** direkte, registryabhängige oder auf geänderte Dateien begrenzte Semgrep-Aufrufe als Gate-Evidenz oder `semgrep_passed` werten
- **NICHT** einen Sprint oder Release ohne bestandenen kanonischen Wrapperlauf abschließen
- **NICHT** Security-Findings ignorieren oder als False Positive markieren ohne dokumentierte Begründung und exakte Allowlist-Signatur
- **NICHT** `pickle.load()` auf nicht-vertrauenswürdige Daten ohne Semgrep-Review

### Native Release- und Workflow-Prüfung

Der kanonische lokale Wrapper ist:

```bash
uv sync --locked --only-group release --no-install-project
uv run --no-sync python -I scripts/release_native_gate.py
```

Er lädt und prüft ausschließlich die drei nativen ZIP-Werkzeuge aus
`scripts/release_native_tools.json` (actionlint 1.7.12, ShellCheck 0.11.0 und
Gitleaks 8.30.1). Zusätzlich führt derselbe Wrapper das aus `uv.lock` gebundene
Zizmor 1.30.0 offline mit `--strict-collection --no-config --no-ignores` in den
Personas `regular` und `pedantic` aus. Git for Windows stammt ausschließlich
aus dem systemweiten HKLM-Installationsvertrag, nicht aus Caller-PATH. Zizmor
ist kein viertes Manifest-ZIP und besitzt keine native GitHub-Asset-Provenienz
in diesem Vertrag. Der Wrapper ist vor jedem Release-Abschluss und nach
Workflowänderungen verpflichtend. Lokal darf nur eine unmittelbar zuvor
gelockt synchronisierte Releaseumgebung als Bootstrap-Trust-Root dienen.

### Context7 — Aktuelle Dokumentation

Context7 MUSS vor der Nutzung von APIs und Libraries konsultiert werden.

**Wann Context7 verwenden (PFLICHT):**
- **Vor Nutzung neuer APIs**: Python stdlib, PyTorch, Transformers, FastAPI, Pydantic, etc.
- **Bei Unsicherheit über API-Verhalten**: Parameter, Rückgabewerte, Exceptions
- **Bei Versionswechseln**: Breaking Changes gegen die verbindliche CPython-3.14.7-Runtime prüfen
- **Best Practices verifizieren**: Aktuelle Empfehlungen für Patterns und Anti-Patterns
- **AI-Libraries**: Aktuelle API-Docs für PyTorch, HuggingFace, LangChain etc. — diese ändern sich häufig

**VERBOTEN:**
- **NICHT** APIs aus dem Gedächtnis verwenden ohne aktuelle Dokumentation zu prüfen
- **NICHT** veraltete Patterns anwenden wenn Context7 aktuellere Empfehlungen liefert
- **NICHT** AI-Library-APIs raten — Transformers/PyTorch-APIs ändern sich zwischen Minor Versions

### Sequential Thinking — Komplexe Entscheidungen

Sequential Thinking ist ein **MCP Server** (`mcp__sequential-thinking__sequentialthinking`). 
Er hat keine serverseitige Konfiguration — die Denktiefe wird über die Aufrufparameter gesteuert.

**Wann Sequential Thinking verwenden (PFLICHT):**
- Bei Architekturentscheidungen mit mehreren validen Alternativen
- Bei mehrstufigen Problemen die schrittweise Analyse erfordern
- Bei Abwägungen zwischen Performance, Wartbarkeit und Komplexität
- Bei Debugging-Szenarien mit mehreren möglichen Ursachen
- Bei Design-Reviews vor Implementierungsbeginn

**Nutzungsregeln (PFLICHT):**
- **Mindestens 10 Denkschritte** (`totalThoughts >= 10`) bei Architektur- und Softwaredesign-Entscheidungen
- **Mindestens 8 Denkschritte** (`totalThoughts >= 8`)beim Entwurf von komplexeren Algorithmen
- **Mindestens 3 Denkschritte** (`totalThoughts >= 3`)bei einfacheren Abwägungen
- `needsMoreThoughts: true` setzen wenn die Analyse nach dem letzten Schritt noch oberflächlich ist
- `isRevision: true` verwenden wenn ein früherer Denkschritt sich als falsch herausstellt — nicht einfach linear weitermachen
- `branchFromThought` nutzen wenn es zwei gleichwertige Lösungsansätze gibt — beide zu Ende denken, dann vergleichen
- Ergebnis des Sequential Thinking im Chat zusammenfassen und dem User zur Entscheidung vorlegen

**VERBOTEN:**
- **NICHT** Sequential Thinking mit nur 1-2 Schritten abkürzen
- **NICHT** `nextThoughtNeeded: false` setzen bevor eine fundierte Schlussfolgerung erreicht ist

### Ruff — Linting + Formatting

Ruff MUSS als All-in-One Linter und Formatter eingesetzt werden. Ersetzt flake8, isort, black, pylint, pyflakes, pycodestyle.

**pyproject.toml — Ruff-Konfiguration:**
```toml
[tool.ruff]
target-version = "py314"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "S",    # flake8-bandit (security)
    "B",    # flake8-bugbear
    "A",    # flake8-builtins
    "C4",   # flake8-comprehensions
    "DTZ",  # flake8-datetimez
    "T10",  # flake8-debugger
    "ISC",  # flake8-implicit-str-concat
    "ICN",  # flake8-import-conventions
    "PIE",  # flake8-pie
    "PT",   # flake8-pytest-style
    "RET",  # flake8-return
    "SIM",  # flake8-simplify
    "TCH",  # flake8-type-checking
    "ARG",  # flake8-unused-arguments
    "PTH",  # flake8-use-pathlib
    "ERA",  # eradicate (commented-out code)
    "PD",   # pandas-vet
    "NPY",  # NumPy-specific rules
    "PERF", # perflint
    "RUF",  # Ruff-specific rules
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # assert in tests erlaubt
"notebooks/**" = ["E402", "T201"]  # Imports und print in Notebooks erlaubt
```

**Ruff-Verantwortung:**
- **E/W/F**: Basis-Code-Qualität (pycodestyle, pyflakes)
- **S (bandit)**: Security-Lints (SQL Injection, Hardcoded Passwords, etc.)
- **NPY/PD**: NumPy- und Pandas-spezifische Best Practices
- **UP**: Automatisches Upgrade auf moderne Python-Syntax

**VERBOTEN:**
- **NICHT** `# noqa` ohne dokumentierte Begründung im Code-Kommentar
- **NICHT** Ruff-Regeln global deaktivieren ohne Begründung in `pyproject.toml`
- **NICHT** andere Linter/Formatter (black, flake8, isort) parallel zu Ruff verwenden

### mypy — Statische Typ-Prüfung

mypy MUSS im strikten Modus für Type Safety eingesetzt werden.

**pyproject.toml — mypy-Konfiguration:**
```toml
[tool.mypy]
python_version = "3.14"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[[tool.mypy.overrides]]
module = ["torch.*", "transformers.*", "sklearn.*"]
ignore_missing_imports = true
```

**VERBOTEN:**
- **NICHT** `# type: ignore` ohne dokumentierte Begründung
- **NICHT** `Any` als Typ verwenden wo ein konkreter Typ möglich ist
- **NICHT** mypy-Fehler durch Entfernen von Type Hints "lösen"

### Test-Stack — pytest-Ökosystem

Die folgenden Packages MÜSSEN als Dev-Dependencies konfiguriert sein:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-cov>=6.1",
    "pytest-asyncio>=0.25",
    "pytest-mock>=3.14",
    "pytest-benchmark>=5.1",
    "hypothesis>=6.119",
    "import-linter>=2.1",
    "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.21.1",
]

[tool.pytest.ini_options]
markers = [
    "slow: langlaufende Tests (Model-Training, große Datasets)",
    "gpu: Tests die GPU/CUDA benötigen",
    "integration: Integration Tests",
]
testpaths = ["tests"]
asyncio_mode = "auto"
```

Der Arbeitsbaum und die aktive Abhängigkeitszeile definieren dieselbe Version.
Vor ihrer Verwendung gilt ausschließlich der kanonische externe
Publikationsvertrag am Anfang dieser Datei. Das v2.21.0-Tag bleibt unverändert.

**pytest-Konventionen:**
- `tests/unit/` für Unit Tests
- `tests/integration/` für Integration Tests
- `tests/conftest.py` für shared Fixtures
- `tests/test_architecture.py` für Architektur-Tests (import-linter)
- Fixture-basiertes Setup statt setUp/tearDown
- `@pytest.mark.slow` für langlaufende Tests (Model-Training, große Datasets)

**VERBOTEN:**
- **NICHT** Tests ohne Coverage-Messung (pytest-cov) ausführen
- **NICHT** `unittest.TestCase` verwenden — pytest-native Fixtures nutzen
- **NICHT** `@pytest.mark.skip` ohne dokumentierte Begründung

### mutmut-win — Mutation Testing (Windows)

mutmut-win MUSS als Mutation-Testing-Tool eingesetzt werden, um die Qualität der Tests zu verifizieren. mutmut-win ist der Windows-native Port von mutmut 3.5.0.

**Installation** (PyPI-Publishing ist nicht Teil der Release-Sequenz — Installation erfolgt über die Git-URL; führendes Dokument: `_config\mutmut-win-install.md`):
```bash
uv add "mutmut-win @ git+https://github.com/pgm1980/mutmut-win.git@v2.21.1" --dev
```

Vor der Installation ist die am Dateianfang vorgeschriebene externe
Tag-/Releaseprüfung auszuführen; die Quelldokumentation zertifiziert keinen
veränderlichen GitHub-Zustand. Das v2.21.0-Tag wird weder verschoben noch gelöscht.

**Wann mutmut-win verwenden (PFLICHT):**
- **Nach Abschluss der Unit Tests eines Features**: Mutation Score als Qualitätsmetrik erheben
- **Bei Code Reviews**: Mutation Score des geänderten Codes prüfen
- **Bei Verdacht auf schwache Tests**: Tests die immer grün sind, aber nichts wirklich prüfen

**Ausführung:**
```bash
mutmut-win run --paths-to-mutate src/<package>/
mutmut-win results
```

**VERBOTEN:**
- **NICHT** einen Sprint abschließen ohne Mutation Testing auf neuen/geänderten Code
- **NICHT** surviving Mutants ignorieren ohne dokumentierte Begründung


### import-linter — Architektur-Durchsetzung

import-linter MUSS eingesetzt werden, um Schichtenarchitektur und Dependency-Regeln als ausführbare Contracts zu definieren.

**pyproject.toml oder `.importlinter` Konfiguration:**
```ini
[importlinter]
root_packages =
    <package>

[importlinter:contract:layers]
name = Layer architecture
type = layers
layers =
    <package>.api
    <package>.service
    <package>.domain
    <package>.infrastructure
```

**Wann import-linter verwenden (PFLICHT):**
- **Bei Projektanlage**: Grundlegende Schichtenregeln definieren
- **Bei neuen Modulen/Packages**: Sofort Architektur-Contracts ergänzen
- **Bei Refactoring**: Architektur-Contracts als Sicherheitsnetz

**VERBOTEN:**
- **NICHT** Architekturregeln nur dokumentieren — sie MÜSSEN als import-linter Contracts existieren
- **NICHT** Schichtverletzungen durch Entfernen von Contracts "lösen"

### hypothesis — Property-Based Testing

hypothesis MUSS ergänzend zu klassischen Unit Tests eingesetzt werden, um Edge Cases durch randomisierte Eingaben zu finden.

**Wann hypothesis verwenden (PFLICHT):**
- **Serialisierung/Deserialisierung**: Roundtrip-Properties (Serialize→Deserialize = Original)
- **Parsing/Validation**: Für JEDEN gültigen Input muss die Invariante gelten
- **Daten-Pipelines**: Transformationen müssen für beliebige Inputs korrekt sein
- **Pydantic-Models**: Validierung gegen generierte Daten
- **AI-spezifisch**: Tensor-Shape-Invarianten, Normalisierungs-Roundtrips

**Beispiel:**
```python
from hypothesis import given, strategies as st

@given(st.lists(st.floats(allow_nan=False, allow_infinity=False), min_size=1))
def test_normalization_roundtrip(values: list[float]) -> None:
    normalized = normalize(values)
    assert len(normalized) == len(values)
    assert all(-1.0 <= v <= 1.0 for v in normalized)
```

**VERBOTEN:**
- **NICHT** nur Happy-Path-Tests schreiben wenn Property-Based Testing Edge Cases aufdecken kann
- **NICHT** hypothesis-Failures ignorieren — sie zeigen echte Grenzfälle auf

### pytest-benchmark — Performance Benchmarks

pytest-benchmark MUSS für Performance-kritische Komponenten eingesetzt werden.

**Wann pytest-benchmark verwenden (PFLICHT):**
- **Hot Paths**: Inference-Pipelines, Preprocessing, häufig aufgerufene Funktionen
- **Vor/Nach Optimierungen**: Messbare Vergleiche statt Bauchgefühl
- **Bei Architekturentscheidungen**: Performance-Vergleich zwischen Alternativen
- **AI-spezifisch**: Tokenisierung, Embedding-Lookup, Batch-Processing

**Beispiel:**
```python
def test_inference_performance(benchmark):
    result = benchmark(model.predict, sample_input)
    assert result is not None
```

**VERBOTEN:**
- **NICHT** Performance-Behauptungen ohne Benchmark-Daten aufstellen

### pip-audit — Dependency-Audit

pip-audit MUSS eingesetzt werden, um Abhängigkeiten auf bekannte Sicherheitslücken zu prüfen.

**Installation:**
```bash
uv pip install pip-audit
```

**Wann pip-audit verwenden (PFLICHT):**
- **Bei neuen Dependencies**: Vor dem Hinzufügen neuer Packages
- **Vor jedem Sprint-Abschluss**: Vollständiger Audit der Dependency-Chain
- **Regelmäßig in CI**: Automatisierter Check auf neue Advisories
- **AI-spezifisch**: Besonders bei ML-Libraries mit nativen Extensions (PyTorch, TensorFlow, ONNX)

**VERBOTEN:**
- **NICHT** einen Sprint abschließen mit bekannten Vulnerabilities in Dependencies
- **NICHT** Advisory-Warnungen ignorieren ohne dokumentierte Begründung und Mitigationsplan

### FS MCP Server — Filesystem-Operationen

Der FS MCP Server (`service_catalog` + `execute_workflow`) ist der **primäre Handler für ALLE Filesystem-Operationen**. 
Er MUSS bevorzugt vor Built-In Tools (Read, Write, Edit, Glob, Grep) verwendet werden, wenn Filesystem-Operationen durchgeführt werden.

**Vollständige Richtlinie:** Siehe [_config/fs_mcp_server.md](_config/fs_mcp_server.md) — enthält Tier 1-4, Entscheidungsbaum und Pipeline-Beispiele.

**Kurzfassung der Tiers:**

| Tier                                              | Regel                                                                                                          | Beispiel                                                            |
|---------------------------------------------------|----------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| **Tier 1: ERSETZT Bash**                          | Bash für Filesystem-Ops ist **VERBOTEN UND GESPERRT** via settings.json — Versuch führt zu `Permission denied` | `execute_workflow` mit `read_file`, `copy_file`, `search_code` etc. |
| **Tier 2: BEVORZUGT vor Built-In**                | Multi-File, große Dateien, komplexe Suche, Batch-Edits, Produktionsdateien                                     | Pipeline mit mehreren Steps statt einzelne Read/Edit/Grep           |
| **Tier 3: Built-In BLEIBT (mit Einschränkungen)** | Siehe Tier-3-Klarstellung unten                                                                                | Read, Edit, Glob, Grep nur unter den definierten Bedingungen        |
| **Tier 4: EINZIGARTIG**                           | Pipelines, Auto-Versioning, Tagging, Snapshots, Templates, Use Cases, Security Scan                            | `execute_workflow` mit Steps, `sensitive_scan`, `project_overview`  |

**Bash bleibt ERLAUBT für:** `uv run --no-sync pytest ... -p no:cacheprovider`, `uv run --no-sync ruff ... --no-cache`, `uv run --no-sync mypy --no-incremental --cache-dir=nul ...`, `uv run --no-sync mutmut-win`, `uv run --no-sync lint-imports --no-cache`, `uv run --no-sync python -I scripts/semgrep_release_gate.py`, `uv run --no-sync pip-audit` — Build/Test/Lint-Befehle mit den verpflichtenden cachelosen Formen. Für Releaseevidenz bleiben zusätzlich externe `UV_PROJECT_ENVIRONMENT` und `HYPOTHESIS_STORAGE_DIRECTORY` vorgeschrieben.

**VERBOTEN UND HART GESPERRT (settings.json `deny`):**
- `cat`, `head`, `tail`, `cp`, `mv`, `rm`, `find`, `grep`, `rg`, `diff`, `tar`, `du`, `stat`, `ls`, `tree`, `sort`, `uniq`, `sed`, `awk`, `wc`, `base64`, `sha256sum`, `mkdir`, `touch` — **werden vom Harness blockiert**
- `pwsh` — **wird vom Harness blockiert**

**Tier-3-Klarstellung — Wann Built-In Tools (Read, Write, Edit, Glob, Grep) erlaubt sind:**

Built-In Tools können NICHT via settings.json gesperrt werden. Ihre Nutzung wird durch diese Regeln gesteuert:

| Built-In Tool | ERLAUBT wenn                                                | FS MCP BEVORZUGT wenn                                           |
|---------------|-------------------------------------------------------------|-----------------------------------------------------------------|
| **Read**      | Einzeldatei <1 MB, schneller Überblick                      | Mehrere Dateien → `read_multiple_files`/Pipeline                |
| **Edit**      | Gezielte Ersetzung in Einzeldatei (visueller Diff-Output)   | Batch-Edits in mehreren Dateien → Pipeline                      |  
| **Write**     | Neue Datei erstellen (kein Überschreiben)                   | Produktionsdateien → `write_file`/`safe_write` (mit Versioning) |
| **Glob**      | Einfache Dateinamen-Suche                                   | — (Glob hat kein FS MCP Äquivalent für reine Namensuche)        |
| **Grep**      | Nicht-Code-Dateien (TOML, JSON, YAML, Markdown, Notebooks)  | Projektweite Code-Suche → `search_code`. Code-Symbole → Serena  |

**Kernregel:** FS MCP (`read_file`, `write_file`, `search_code`) ist **immer die erste Wahl**. Built-In Tools sind der **Fallback** für Einzeldatei-Operationen wo der FS MCP keinen Mehrwert bietet (z.B. Edit mit visuellem Diff).

**VERBOTEN (CLAUDE.md-Direktive):**
- **NICHT** `Read` auf mehrere Dateien nacheinander — `read_multiple_files` oder Pipeline nutzen
- **NICHT** `Write` zum Überschreiben von Produktionsdateien — `write_file` oder `safe_write` nutzen
- **NICHT** `Grep` für projektweite Code-Suche — `search_code` mit Kontext-Zeilen nutzen
- **NICHT** `Grep` für Klassen/Methoden/Properties — Serena `find_symbol` nutzen

---

## Commands

Für Kandidaten- und integrierte Finalgates ist vor jedem der folgenden Befehle
eine frische absolute `UV_PROJECT_ENVIRONMENT` außerhalb des Checkouts Pflicht;
auch `HYPOTHESIS_STORAGE_DIRECTORY` zeigt auf ein absolutes externes
Verzeichnis. Der Checkout darf weder `.venv`, Werkzeug-Caches mit eigener
`.gitignore` noch `.hypothesis`-Cachebytes enthalten.

| Command                                              | Beschreibung                              |
|------------------------------------------------------|-------------------------------------------|
| `uv sync`                                            | Nur mit gesetzter externer Projektumgebung synchronisieren |
| `uv run --no-sync pytest -p no:cacheprovider`        | Alle Tests ohne Checkout-Cache ausführen  |
| `uv run --no-sync pytest -p no:cacheprovider tests/unit/` | Nur Unit Tests                       |
| `uv run --no-sync pytest -p no:cacheprovider tests/integration/` | Nur Integration Tests          |
| `uv run --no-sync pytest -p no:cacheprovider -m "not slow"` | Schnelle Tests                     |
| `uv run --no-sync pytest --cov=mutmut_win --cov-report=term-missing -p no:cacheprovider` | Release-Coverage ohne HTML-/pytest-Cache |
| `uv run --no-sync ruff check --no-cache .`           | Linting (alle Regeln, ohne Checkout-Cache) |
| `uv run --no-sync ruff format --no-cache .`          | Code ohne Checkout-Cache formatieren      |
| `uv run --no-sync ruff check --no-cache --fix .`     | Auto-fixbare Lint-Fehler beheben          |
| `uv run --no-sync mypy --no-incremental --cache-dir=nul src/` | Statische Typ-Prüfung ohne Modulcache |
| `uv run --no-sync lint-imports --no-cache`           | Architektur-Contracts ohne Checkout-Cache prüfen |
| `uv run --no-sync mutmut-win run --paths-to-mutate src/<package>/` | Mutation Testing              |
| `uv run --no-sync mutmut-win results`                | Mutation Testing Ergebnisse               |
| `uv sync --locked --only-group security --no-install-project` | Gelockte Security-only-Umgebung herstellen |
| `uv run --no-sync python -I scripts/semgrep_release_gate.py` | Kanonisches fail-closed Semgrep-Releasegate |
| `uv sync --locked --only-group release --no-install-project` | Gelockte Release-Gate-Umgebung herstellen |
| `uv run --no-sync python -I scripts/release_native_gate.py` | Drei native Manifesttools plus Zizmor 1.30.0 offline regular/pedantic ohne Config/Ignored-Findings; HKLM-Git |
| `uv run pip-audit`                                   | Dependency-Audit auf Vulnerabilities      |

---

## Architecture

> Wird bei Projektanlage befüllt. Erwartete Struktur:

```
<Projektname>/
  src/
    <package>/
      __init__.py          # Package Root
      py.typed             # PEP 561 Marker für Type Stubs
      api/                 # API-Schicht (FastAPI Router, CLI)
      service/             # Business Logic
      domain/              # Domänenmodelle (Pydantic)
      infrastructure/      # Externe Systeme (DB, APIs, ML-Models)
      ml/                  # AI/ML-spezifisch
        models/            # Model-Definitionen
        training/          # Training-Loops, Trainer
        evaluation/        # Metriken, Evaluierung
        data/              # Datasets, Preprocessing, Augmentation
  tests/
    unit/                  # Unit Tests
    integration/           # Integration Tests
    conftest.py            # Shared Fixtures
    test_architecture.py   # import-linter Architektur-Tests
  notebooks/               # Jupyter Notebooks (Exploration, Prototyping)
  benchmarks/              # pytest-benchmark Tests
  pyproject.toml           # Manifest, Dependencies, Tool-Config
  ruff.toml                # Ruff-Konfiguration (optional, kann in pyproject.toml)
  uv.lock                  # Lockfile (uv)
```

---

## Key Files

> Wird bei Projektanlage befüllt. Erwartete Einträge:

- `pyproject.toml` — Manifest, Dependencies, Tool-Konfiguration (Ruff, mypy, pytest)
- `src/<package>/__init__.py` — Package Root, öffentliche API
- `src/<package>/py.typed` — PEP 561 Type Stub Marker
- `uv.lock` — Dependency Lockfile
- `.importlinter` — Architektur-Contracts (alternativ in pyproject.toml)

---

## Environment / Prerequisites

| Voraussetzung               | Version           | Zweck                                         |
|-----------------------------|-------------------|-----------------------------------------------|
| Python                      | ==3.14.7          | Exakt unterstützte CPython-Runtime (Windows) |
| uv                          | aktuell           | Package Manager + Virtual Environments        |
| Ruff                        | aktuell           | Linting + Formatting                          |
| mypy                        | aktuell           | Statische Typ-Prüfung                         |
| mutmut-win                  | Paketstand aus `pyproject.toml`; Publikation extern prüfen | Mutation Testing (Windows) |
| pip-audit                   | aktuell           | Dependency-Audit                              |
| Semgrep CLI                 | 1.175.0 (uv.lock) | Security-Scanning über den Release-Wrapper    |
| Zizmor                      | 1.30.0 (uv.lock)  | Offline-Workflowaudit via nativem Release-Wrapper |
| Serena MCP-Server           | aktuell           | Symbolbasierte Code-Analyse                   |
| Context7 MCP-Server         | aktuell           | Aktuelle API-Dokumentation                    |
| Git                         | aktuell           | Versionskontrolle                             |
| CUDA Toolkit                | projektspezifisch | GPU-Beschleunigung (falls PyTorch/TF mit GPU) |

---

## Git-Konventionen

Beim Repository-Setup den `git-workflow-guide` Skill verwenden.

- **Branching**: GitHub Flow
- **Commits**: Conventional Commits (`type(scope): description`)
- **Tags**: SemVer (`vMAJOR.MINOR.PATCH`), annotated Tags nach Erreichen eines Milestones
- **Branch-Naming**: `feature/[ISSUE-NR]-kurzbeschreibung`, `fix/[ISSUE-NR]-kurzbeschreibung`

---

## Sprint State Management (`.sprint/state.md`)

Die Datei `.sprint/state.md` ist das zentrale Steuerungsdokument für alle Hooks in `.claude/hooks/`. Sie MUSS ein **YAML-Frontmatter** mit exakt den unten definierten Feldern enthalten. Fehlt die Datei oder das Frontmatter, feuern die Hooks ohne Wirkung.

### Schema (PFLICHT — alle Felder erforderlich)

```yaml
---
current_sprint: "1"                    # Sprint-Nummer (String)
sprint_goal: "Kurzbeschreibung"        # 1-Satz Sprint-Ziel
branch: "feature/1-kurzbeschreibung"   # Erwarteter Git-Branch für diesen Sprint
started_at: "2026-03-30"               # ISO-Datum des Sprint-Starts
housekeeping_done: false               # true = alle HK-Items erledigt, false = Sprint-Gate aktiv
memory_updated: false                  # true = MEMORY.md in diesem Sprint aktualisiert
github_issues_closed: false            # true = alle Sprint-Issues geschlossen
sprint_backlog_written: false          # true = Sprint-Backlog-Dokument existiert
semgrep_passed: false                  # true = kanonisches Gate ohne unerwartete Findings/Errors/Skips/Timeouts
tests_passed: false                    # true = alle Tests grün (pytest + mypy + ruff)
documentation_updated: false           # true = Docs/Docstrings aktualisiert
---
```

### Feld-Referenz

| Feld | Typ | Default | Gelesen von Hook(s) |
|------|-----|---------|---------------------|
| `current_sprint` | String | — | sprint-health, sprint-gate, statusline, post-compact-reminder, sprint-housekeeping-reminder |
| `sprint_goal` | String | — | sprint-health, post-compact-reminder |
| `branch` | String | — | sprint-health, post-compact-reminder |
| `started_at` | ISO-Datum | — | sprint-health, sprint-gate |
| `housekeeping_done` | Boolean | `false` | sprint-health, sprint-gate, statusline, post-compact-reminder, sprint-housekeeping-reminder |
| `memory_updated` | Boolean | `false` | sprint-health, sprint-housekeeping-reminder |
| `github_issues_closed` | Boolean | `false` | sprint-health, sprint-housekeeping-reminder |
| `sprint_backlog_written` | Boolean | `false` | sprint-health, sprint-housekeeping-reminder |
| `semgrep_passed` | Boolean | `false` | sprint-health |
| `tests_passed` | Boolean | `false` | sprint-health |
| `documentation_updated` | Boolean | `false` | sprint-health |

### Lifecycle

1. **Sprint-Start**: Claude erstellt/aktualisiert `.sprint/state.md` mit neuem Sprint, `housekeeping_done: false` und allen Items auf `false`
2. **Während Sprint**: Items werden auf `true` gesetzt sobald sie erledigt sind
3. **Sprint-Ende**: Alle Items `true`, dann `housekeeping_done: true` setzen → Sprint-Gate deaktiviert
4. **Nächster Sprint**: Frontmatter mit neuer Sprint-Nummer überschreiben, alle Items zurück auf `false`

### Hook-Zuordnung

| Hook | Trigger | Liest | Wirkung |
|------|---------|-------|---------|
| `sprint-health.sh` | SessionStart | Alle Felder | Zeigt Sprint-Status + offene HK-Items + Warnungen |
| `sprint-gate.sh` | PostToolUse (git commit) | `housekeeping_done`, `current_sprint`, `started_at` | Warnt wenn HK nicht erledigt |
| `statusline.sh` | Permanent | `current_sprint`, `housekeeping_done` | `S1 [HK!]` oder `S1` |
| `post-compact-reminder.sh` | PostCompact | `current_sprint`, `sprint_goal`, `branch`, `housekeeping_done` | CLAUDE.md-Reminders + Sprint-State |
| `sprint-housekeeping-reminder.sh` | Stop | `current_sprint`, `housekeeping_done`, `memory_updated`, `github_issues_closed`, `sprint_backlog_written` | Session-End-Warnung |
| `sprint-state-save.sh` | PreCompact | Gesamte Datei | Hängt Git-Context an state.md an |
| `verify-after-agent.sh` | SubagentStop | — (prüft Code direkt) | Ruff + mypy + pytest + kanonisches Semgrep-Gate |

### Validierung

Der `sprint-health.sh` Hook validiert beim SessionStart, ob alle Pflichtfelder vorhanden sind. Fehlende Felder werden als Warnung ausgegeben.

**VERBOTEN:**
- **NICHT** `.sprint/state.md` ohne YAML-Frontmatter schreiben — die Hooks ignorieren die Datei dann komplett
- **NICHT** Felder weglassen — fehlende Felder führen zu stillen Hook-Fehlfunktionen
- **NICHT** `housekeeping_done: true` setzen bevor alle Items tatsächlich erledigt sind

---

## Entwicklungsprozess — Scrum-basiert

Vollständiger Prozess: Siehe [_config/development_process.md](_config/development_process.md)

**Kurzübersicht:**

| Phase           | Inhalt                                                                               | Ergebnis                                                            |
|-----------------|--------------------------------------------------------------------------------------|---------------------------------------------------------------------|
| Sprint 0        | Brainstorming → Architektur (ADRs) → Softwaredesign (FRs, NFRs)                      | `architecture_specification.md`, `software_design_specification.md` |
| Product Backlog | DoD, Epics, Features, User Stories, Acceptance Criteria → GitHub Issues + Milestones | `product_backlog.md`, Vollständiges Backlog in GitHub               |
| Sprint 1–N      | Sprint Planning → Implementation (TDD) → Tests → Increment                           | `sprint_backlog.md`, Lauffähiges und getestetes Feature             |
| Review          | Code Review → Feedback → Branch Integration                                          |  Merged Feature, GitHub Issues schließen, ggf. GitHub Tag           |

---

## Overlap-Resolution

Wenn zwei Skills in Frage kommen, gilt diese Entscheidungstabelle:

| Situation                                    | Verwende                                                         | Nicht                        |
|----------------------------------------------|------------------------------------------------------------------|------------------------------|
| Neues Konzept, kein Code vorhanden           | `brainstorming`                                                  | `feature-development`        |
| Feature in bestehender Codebase              | `feature-development`                                            | `brainstorming`              |
| Vage Idee → strukturiertes Spec-Dokument     | `write-spec`                                                     | `brainstorming`              |
| Einzelne Tech-Entscheidung (ADR)             | `architecture`                                                   | `architecture-designer`      |
| Vollständiges System-Design (neues Projekt)  | `architecture-designer`                                          | `architecture`               |
| Architektur steht, nur Task-Breakdown        | `writing-plans`                                                  | `feature-development`        |
| Architektur offen, Exploration nötig         | `feature-development`                                            | `writing-plans`              |
| Tasks sind sequentiell/abhängig              | `executing-plans`                                                | `subagent-driven-development`|
| Tasks sind unabhängig/parallelisierbar       | `subagent-driven-development` oder `dispatching-parallel-agents` | Sequentielle Einzelarbeit    |
| Schneller Check nach einem Task              | `requesting-code-review`                                         | `pr-review`                  |
| Umfassendes Review vor Merge/PR              | `pr-review`                                                      | `requesting-code-review`     |
| Quality Review innerhalb feature-development | `feature-development` (Phase 6)                                  | `pr-review`                  |
| Standalone Review außerhalb Feature-Workflow | `pr-review`                                                      | `feature-development`        |
| Bug mit klarem Stack Trace / Error           | `debug`                                                          | `systematic-debugging`       |
| Bug unklar, mehrere mögliche Ursachen        | `systematic-debugging`                                           | `debug`                      |
| Code-Qualität bewerten, Refactoring-Backlog  | `tech-debt`                                                      | `requesting-code-review`     |
| Iterative Prozessverbesserung (PDCA)         | `plan-do-check-act`                                              | `tech-debt`                  |
| MCP Server bauen/erweitern                   | `mcp-builder`                                                    | `feature-development`        |
| Feature-Branch braucht Isolation             | `using-git-worktrees`                                            | Manuelles `git worktree`     |
| Einfaches Reasoning (step-by-step)           | `thought-based-reasoning`                                        | `tree-of-thoughts`           |
| Komplexes Reasoning (Exploration + Pruning)  | `tree-of-thoughts`                                               | `thought-based-reasoning`    |
| Multi-Agent-Architektur entwerfen            | `multi-agent-patterns`                                           | `dispatching-parallel-agents`|
| Tiefgehende Multi-Perspektiven-Analyse       | `critique`                                                       | `pr-review`                  |
| Schnelles Code-Review vor Merge              | `pr-review`                                                      | `critique`                   |

---

## Cross-Cutting Skills

Diese Skills sind an keine Phase gebunden — sie werden **situativ** aktiviert:

| Skill                            | Trigger                                                                   |
|----------------------------------|---------------------------------------------------------------------------|
| `systematic-debugging`           | Bug, Testfehler, unerwartetes Verhalten — Ursache unklar, mehrere Hypothesen |
| `debug`                          | Bug mit klarem Stack Trace oder Error Message — schnelle, fokussierte Session |
| `verification-before-completion` | Vor jeder Behauptung "fertig", "funktioniert", "Tests grün"               |
| `finishing-a-development-branch` | Wenn alle Tests grün und Sprint abgeschlossen                             |
| `dispatching-parallel-agents`    | Wenn 2+ unabhängige Aufgaben gleichzeitig bearbeitet werden können        |
| `receiving-code-review`          | Wenn Review-Feedback vorliegt, vor Umsetzung der Vorschläge               |
| `subagent-driven-development`    | Wenn Plan mit unabhängigen Tasks in der aktuellen Session ausgeführt wird |
| `write-spec`                     | Vage Feature-Idee → strukturiertes Spec/PRD mit Goals, Non-Goals, Akzeptanzkriterien |
| `architecture`                   | Einzelne Architekturentscheidung (ADR) treffen, Technologie-Wahl bewerten |
| `architecture-designer`          | Vollständiges System-Design: Requirements, Patterns, Diagramme, NFRs, DB-Auswahl |
| `tech-debt`                      | Nach Release: Code-Qualität bewerten, Refactoring priorisieren, Wartungsbacklog |
| `plan-do-check-act`             | Iterative Verbesserung: Hypothese → Experiment → Messung → Standardisierung |
| `mcp-builder`                    | MCP Server bauen oder erweitern (Python FastMCP oder TypeScript SDK)      |
| `using-git-worktrees`           | Feature-Branch-Isolation vor Implementierung oder paralleler Arbeit       |
| `thought-based-reasoning`        | Komplexes Reasoning: CoT, Self-Consistency, Least-to-Most, ReAct, PAL — Technik-Auswahl |
| `tree-of-thoughts`              | Hardest Problems: Systematische Exploration mit Pruning, Multi-Agent-Judges, Synthesis |
| `multi-agent-patterns`           | Multi-Agent-Architektur entwerfen: Supervisor, Peer-to-Peer, Hierarchisch |
| `critique`                       | Tiefgehende Multi-Perspektiven-Analyse: 3 Judges + Debate + Consensus (report-only) |
| `skill-creator`                  | Nur beim Erstellen, Bearbeiten oder Testen von Skills selbst              |


---

## Gotchas

- **Ruff ersetzt alles**: Nicht black, flake8, isort, pylint parallel verwenden — Ruff deckt alles ab. Konflikte sind garantiert.
- **Serena-Onboarding nicht vergessen**: Nach jedem Projektstart `get_symbols_overview` auf die Hauptdateien ausführen, damit Serena den Projekt-Index aufbaut.
- **pytest-cov braucht explizite Flags**: `pytest` allein erzeugt keinen Coverage-Report. Immer `--cov=src --cov-report=html` verwenden.
- **mutmut-win Laufzeit**: Kann bei großen Projekten extrem lang sein. `--paths-to-mutate` für gezieltes Testen verwenden. `--max-children 4` bei RAM-knappen Systemen.
- **mypy + AI-Libraries**: PyTorch, Transformers, sklearn haben unvollständige Type Stubs. `ignore_missing_imports` pro Modul konfigurieren, nicht global.
- **`pickle.load()` ist ein Security-Risiko**: Nie auf nicht-vertrauenswürdige Daten anwenden. `safetensors` oder `torch.load(weights_only=True)` bevorzugen.
- **Runtime-Kompatibilität halten**: Produktionscode MUSS unter Windows mit CPython 3.14.7 funktionieren; andere Python-Versionen und Betriebssysteme sind nicht Teil des Produktvertrags.
- **`# noqa` ist verboten** ohne dokumentierte Begründung im Code-Kommentar direkt darüber.
- **`# type: ignore` ist verboten** ohne dokumentierte Begründung und spezifischen Error-Code (`# type: ignore[override]`).
- **Notebooks sind kein Produktionscode**: Jupyter Notebooks nur für Exploration/Prototyping. Produktionscode MUSS in `src/` als getestete Module leben.
- **GPU-Tests markieren**: Tests die GPU benötigen mit `@pytest.mark.gpu` markieren und in CI separat ausführen.
- **Reproducibility**: Seeds für Random, NumPy, PyTorch IMMER setzen und dokumentieren. `torch.use_deterministic_algorithms(True)` wo möglich.
- **Semgrep bei Python**: Nur der gelockte, zweiphasige Release-Wrapper besitzt Gate-Autorität: isolierte Regelmaterialisierung, anschließend contentgeprüfter Offline-Bundlescan; Teil- oder Direktläufe sind höchstens diagnostisch.
- **uv statt pip**: Immer `uv` verwenden — schneller, reproduzierbar, Lockfile-Support.

---

## AI/ML-spezifische Regeln

- **Datenvalidierung**: Pydantic für alle Eingabe-/Ausgabe-Schemas. Keine rohen Dicts an ML-Pipelines übergeben.
- **Model-Loading**: `safetensors`-Format bevorzugen. `pickle`/`torch.load()` nur mit `weights_only=True`.
- **Experiment-Tracking**: Hyperparameter, Metriken und Artefakte MÜSSEN reproduzierbar dokumentiert sein (MLflow, W&B, oder strukturierte Logs).
- **Tensor-Shapes dokumentieren**: Bei allen Tensor-Operationen die erwarteten Shapes als Kommentar angeben:
  ```python
  # input: (batch_size, seq_len, hidden_dim) -> output: (batch_size, seq_len, num_classes)
  logits = self.classifier(hidden_states)
  ```
- **Seed-Management**: Zentraler `set_seed(seed)` Helper der Python, NumPy und PyTorch Seeds setzt.
- **Data/Code-Trennung**: Datasets und Modellgewichte NICHT im Git-Repository. `.gitignore` muss enthalten:
  ```gitignore
  # AI/ML Artefakte
  data/
  models/
  *.pt
  *.pth
  *.safetensors
  *.onnx
  *.bin
  *.h5
  wandb/
  mlruns/
  ```
- **Evaluation vor Deployment**: Kein Modell wird deployed ohne dokumentierte Evaluation-Metriken auf einem Held-Out-Testset.

---

## Projektspezifische Regeln

- **Sprache**: CPython 3.14.7 (`==3.14.7`, ausschließlich Windows)
- **Package Manager**: uv
- **Projektformat**: `pyproject.toml` (PEP 621)
- **Async Framework**: asyncio + FastAPI (empfohlen für API-Serving, nicht Pflicht)
- **AI/ML-Framework**: PyTorch (empfohlen), Hugging Face Transformers
- **Datenvalidierung**: Pydantic v2
- **Serialisierung**: `safetensors` (Modelle), `serde`-Äquivalente via Pydantic (Daten)
- **Testframework**: pytest + hypothesis + pytest-benchmark + pytest-cov
- **Coverage**: pytest-cov
- **Mutation Testing**: mutmut-win (Windows-nativer Port von mutmut 3.5.0)
- **Linting**: Ruff (All-in-One) + mypy (Type Checking)
- **Dependency-Audit**: pip-audit
- **Architecture-Enforcement**: import-linter
- **Code-Dokumentation**: Google-Style Docstrings, Type Hints für alle öffentlichen APIs
- **Plattformen**: ausschließlich Windows 10/11 oder Windows Server 2016+

---

## Referenzen

| Pfad                             | Inhalt                                                           |
|----------------------------------|------------------------------------------------------------------|
| `_config/development_process.md` | Vollständiger Scrum-basierter Entwicklungsprozess                |
| `_config/fs_mcp_server.md`       | File System MCP Server                                           |
| `MEMORY.md`                      | Projektgedächtnis mit aktuellem Stand und offenen Entscheidungen |
