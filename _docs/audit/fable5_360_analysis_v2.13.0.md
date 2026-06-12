# 360°-Code-Analyse mutmut-win v2.13.0

| | |
|---|---|
| **Analysestand** | v2.13.0, `main` @ `2e481fd` (Release 2026-06-12) |
| **Datum** | 2026-06-12 |
| **Analyst** | Claude Fable 5 (Claude Code) mit Serena (symbolbasierte Code-Analyse), FS MCP, Context7 |
| **Scope** | Alle 29 Quellmodule unter `src/mutmut_win/` (~9.700 LOC), vollständige Lektüre + Cross-File-Analyse |
| **Ergebnis** | 9 bestätigte Bugs (3 Hoch, 5 Mittel, 1 Niedrig) · 13 Anomalien · 6 Optimierungspotentiale · 1 entkräfteter Verdacht |

---

## 1 Executive Summary

Die Analyse hat **9 bestätigte, bisher unentdeckte Bugs** identifiziert, davon 6 empirisch
bzw. dokumentarisch verifiziert (reale Dogfooding-Artefakte, offizielle pytest-Doku,
README-Quelltext). Die drei schwerwiegendsten:

1. **A1** — Die `.meta`-Dateien erhalten auf src-Layouts **nie** Exit-Codes/Durations
   (Prefix-Mismatch in `_update_source_data`); `browse` zeigt deshalb jeden Mutanten als
   „Not checked". Empirisch belegt am Dogfooding-Staging dieses Repos.
2. **A2** — Der Worker übergibt Tests immer per `@argfile`; das pytest-Feature existiert
   erst **seit pytest 8.2**, der deklarierte Floor ist `pytest>=6.2.5`. Zielprojekte mit
   älterem pytest erleben eine Suspicious-Flut für jeden gedeckten Mutanten.
3. **A3** — `get_mutant_name` strippt nur `src.`, nicht `source.` — obwohl `source/` als
   Staging-Root überall sonst unterstützt wird. `source/`-Layouts liefern flächendeckend
   „no tests".

Dazu kommen Korrektheitslücken im CI-Kanal (`--output json` deterministisch verschmutzt
bei `--force`; Pool-Kollaps endet als Exit 0), eine fehlende Engine-Versions-Bindung der
Fingerprints (Upgrade lässt das alte Mutanten-Universum stillschweigend weiterleben)
sowie systematische Anomalien im Stats-/Mapping-Subsystem.

Maschinelle Gates zum Analysezeitpunkt: **Semgrep 0 Findings** (320 Regeln, 173 Dateien;
159 Dateien via `.semgrepignore` übersprungen), **mypy exakt auf der bekannten
14er-Baseline**, **ruff rot** mit 23 Findings — alle in `.claude/skills/mcp-builder/`
(Umgebungs-Anomalie B13, kein Projektcode).

> **Amendment (2026-06-12, nach Pro-Aktivierung):** Der ursprüngliche Semgrep-Lauf war —
> wie sich nachträglich herausstellte — ein Community-Edition-Scan (CLI ausgeloggt).
> Nach Aktivierung des Pro-Accounts (SEMGREP_APP_TOKEN, CLI 1.166.0) wurde der Scan mit
> **Semgrep Code (SAST)** wiederholt: **1228 Regeln, weiterhin 0 Findings** — Details und
> Kontext in Abschnitt 3.

---

## 2 Methodik

1. **Vollständige Lektüre** aller 29 Module bottom-up entlang der fünf Architektur-Bänder
   (Fundament → process → Engine → Orchestrierung → CLI/TUI) via Serena (`read_file`,
   `get_symbols_overview`, `find_symbol`).
2. **Cross-File-Invariantenprüfung**: Mutantenname ↔ `orig.__module__` ↔ Trampoline-Prefix;
   Fingerprint-Ketten (Staging-Fast-Path, Config-Fingerprint, Tests-Fingerprint, Reuse);
   Score-Buchhaltung (Run-Gate ↔ `results` ↔ CI-Export); Prozess-Lifecycle
   (Executor/Worker/Job-Objects/Phasen); stdout-Disziplin im `--output json`-Pfad.
3. **Verifikation** jedes Verdachtspunkts gegen die Realität: echte Dogfooding-Artefakte
   (`.mutmut-cache/mutmut-cache.db`, `mutants/**/*.meta`), exakte Quelltextstellen
   (Serena `search_for_pattern`), offizielle Doku (pytest via Context7 + docs.pytest.org),
   Scanner-Läufe (Semgrep, mypy, ruff).
4. **Kennzeichnung**: Befunde sind als *empirisch verifiziert* (Artefakt/Doku-Beleg) oder
   *statisch verifiziert* (Code-Beweis ohne Laufzeit-Repro) markiert. Upstream-Erbe
   (Verhalten identisch zu mutmut 3.5.0) ist ausgewiesen.

Nicht Teil dieser Analyse: Laufzeit-Reproduktion aller Befunde, Tests-/Benchmark-Code,
`tests/e2e_projects/`-Fixtures (Upstream-Kopien).

---

## 3 Maschinelle Gates (Stand der Analyse)

| Gate | Ergebnis | Bemerkung |
|---|---|---|
| `semgrep scan --config auto .` (CE, ausgeloggt) | **0 Findings** | 320 Regeln (Community), 173 Dateien; 159 Dateien via `.semgrepignore` übersprungen; Scan auf git-getrackte Dateien beschränkt |
| `semgrep scan --config auto .` (**Pro/SAST**, Amendment) | **0 Findings** | CLI 1.166.0, eingeloggt: Semgrep OSS ✔ + Semgrep Code (SAST) ✔, **1228 Regeln**, 174 Dateien; Supply Chain (SCA) im `scan`-Modus inaktiv — Dependency-Audit weiterhin via `pip-audit` |
| `uv run mypy src/` | **14 Errors** | Exakt die dokumentierte Baseline (node_mutation 5, mutation 7, browser 2) |
| `uv run ruff check .` | **23 Findings** | Alle in `.claude/skills/mcp-builder/scripts/` → Befund B13; `src/`, `tests/`, `benchmarks/` sauber |

**Amendment-Kontext (gleicher Tag):** Die Erstanalyse lief unwissentlich gegen die
Community Edition — die globale Host-CLI (damals 1.152.0) war ausgeloggt, und der
Semgrep-Pro-MCP-Server (Docker) ist aus Claude-Code-Sessions heraus doppelt defekt:
kein Bind-Mount des Projekte-Roots (pfadbasierte Scans scheitern mit ENOENT auf
`/C:/claude_code/…`) und kein Token mit `webapi`-Rolle für die Findings-API. Das betraf
sämtliche bisherigen `semgrep_passed`-Gates dieses Projekts einschließlich der
v2.13.0-Release-Gates — sie alle liefen auf CE-Regelbasis. Nach Pro-Aktivierung der
Host-CLI bestätigt der SAST-Re-Scan den Nullbefund bei knapp vervierfachter Regelbasis.
Die MCP-Container-Defekte (Mount, webapi-Token) bleiben offen und sind als
Infrastruktur-Punkte außerhalb dieses Repos zu beheben.

---

## 4 Bestätigte Bugs (A-Befunde)

### A1 · `.meta`-Dateien erhalten nie Exit-Codes (src-Layouts) — Prefix-Mismatch

**Schwere:** Hoch · **Status:** empirisch verifiziert · **Kategorie:** Result-Persistenz

**Fundort:** `src/mutmut_win/orchestrator.py:1301` (`_update_source_data`), Gegenstück
`src/mutmut_win/file_setup.py:495` (`get_mutant_name`).

**Mechanik:** `_update_source_data` ordnet ein Ergebnis seiner Quelldatei per
`mutant_name.startswith(norm_path)` zu. `norm_path` wird aus dem Datei-Pfad **inklusive**
`src.`-Präfix gebaut (`"src/mutmut_win/config.py"` → `"src.mutmut_win.config"`), die
Mutantennamen sind aber per `get_mutant_name` **`src.`-gestrippt**
(`"mutmut_win.config.x_f__mutmut_1"`). Der Vergleich ist auf src-Layouts nie wahr — die
Funktion kehrt ohne Schreibvorgang zurück.

**Evidenz (dieses Repo, Reuse-Demo-Lauf C):**
`mutants/src/mutmut_win/type_checking.py.meta` enthält 176 Einträge in
`exit_code_by_key` — **alle `null`** — und ein leeres `durations_by_key`, während die
Ergebnis-DB für exakt dieselben Mutanten 212 killed / 44 survived hält.

**Impact:**
- `browse` (meta-gestützte Ansicht) zeigt auf src-Layouts **jeden Mutanten als „Not
  checked"**; Beschreibungstexte, Durations, Estimates und `type_check_error_by_key`
  bleiben leer.
- Zweiter Defekt derselben Zeile: Der Vergleich ist **unverankert** — `pkg.util` matcht
  auch Mutanten von `pkg.utils` (`"pkg.utils.x_f…".startswith("pkg.util")` ist wahr).
  Auf flachen Layouts können Ergebnisse der **falschen** `.meta`-Datei zugeschrieben
  werden (abhängig von Dict-Iterationsreihenfolge).

**Fix-Empfehlung:** Zuordnung nicht per String-Prefix, sondern über dieselbe Funktion wie
die Namenserzeugung: beim Aufbau von `source_data_by_file` eine Map
`mutant_name → file_path` füllen (die qualifizierten Namen existieren dort bereits) und
in `_update_source_data` per exaktem Lookup zuordnen. Regressionstest: src-Layout-Fixture,
nach Lauf `exit_code_by_key`-Werte ≠ `null`.

---

### A2 · `@argfile` erfordert pytest ≥ 8.2 — deklarierter Floor ist 6.2.5

**Schwere:** Hoch · **Status:** dokumentarisch verifiziert · **Kategorie:** Ausführung/Kompatibilität

**Fundort:** `src/mutmut_win/process/worker.py:172` (`cmd.append(f"@{tests_argfile.name}")`),
`pyproject.toml` (`pytest>=6.2.5` als Runtime-Dependency).

**Mechanik:** Der Worker übergibt die zugewiesenen Tests **immer** per pytest-Argfile
(`@mutmut_tests_*.txt`) — bewusst gewählt gegen das Windows-32k-Kommandozeilenlimit.
Das `@`-Feature existiert laut offizieller pytest-Dokumentation (how-to/usage,
„Read arguments from file") erst **„Added in version 8.2"**. Der Worker startet
`sys.executable -m pytest` im **venv des Zielprojekts** — es zählt dessen pytest-Version,
nicht die des Entwicklungs-Repos.

**Impact:** Zielprojekte mit pytest 6.2.5–8.1 (vom eigenen Floor ausdrücklich erlaubt):
`@…` wird als literaler Pfad interpretiert → Usage-/Collection-Error → **jeder gedeckte
Mutant endet „suspicious"**, obwohl Clean-Run und Forced-Fail grün waren (beide Phasen
nutzen kein Argfile). Das Schadensbild sieht aus wie ein Trampoline-Defekt und ist
schwer zu diagnostizieren.

**Fix-Empfehlung (eine von beiden):**
1. Dependency-Floor ehrlich machen: `pytest>=8.2` (Breaking für Alt-Umgebungen, aber
   ehrlich), oder
2. Versionsweiche im Worker: pytest-Version im Staging-venv erkennen; < 8.2 → Inline-
   Node-IDs solange die Kommandozeile < 32.767 Zeichen bleibt, sonst harter, erklärender
   Abbruch.

---

### A3 · `source/`-Layouts brechen die Namens-/Modul-Invariante

**Schwere:** Hoch (für betroffene Layouts) · **Status:** statisch verifiziert · **Kategorie:** Engine/Naming

**Fundort:** `src/mutmut_win/file_setup.py:495` (`strip_prefix(module_name, prefix="src.")`).

**Mechanik:** Die zentrale Invariante des Trampoline-Dispatches ist
`MUTANT_UNDER_TEST == orig.__module__ + '.' + mangled_name + '__mutmut_N'`. `copy_src_dir`,
`setup_source_paths`, Worker-PYTHONPATH und `runner._mutants_env` behandeln `source/`
gleichberechtigt zu `src/` als Import-Root (`mutants/source` landet auf dem PYTHONPATH,
Tests importieren `pkg.mod`). `get_mutant_name` strippt aber **nur** `src.` — Mutanten
heißen `source.pkg.mod.x_f__mutmut_1`, während `orig.__module__ == "pkg.mod"` ist.

**Impact:**
- Stats-Mapping-Lookup (`mangled_name_from_mutant_name` → `tests_by_mangled_function_name`)
  findet nie einen Treffer → **alle Mutanten „no tests"**, 0 dispatcht, Score über leerer
  Menge. Laut, aber irreführend (sieht aus wie fehlende Testabdeckung).
- Selbst direkt dispatcht würde der Trampoline-Prefix-Check nie aktivieren (Mutant liefe
  als Original).
- Spiegelfall: ein echtes Root-Package namens `src` (Tests importieren `src.*`) wird
  fälschlich gestrippt — gleiche Invariante andersherum verletzt.

**Hinweis:** Kein `tests/e2e_projects/`-Fixture nutzt ein `source/`-Layout — die Lücke
ist strukturell untestbar gewesen.

**Fix-Empfehlung:** Die Wurzel nicht raten, sondern dieselbe Liste wie die
PYTHONPATH-Logik nutzen: `strip_prefix` für jede unterstützte Root (`src.`, `source.`)
— oder besser: den Modulnamen aus dem Pfad **relativ zur erkannten Import-Root**
ableiten (single source of truth mit `setup_source_paths`/Worker). e2e-Fixture mit
`source/`-Layout ergänzen; `src`-als-Package-Edge dokumentieren.

---

### A4 · `--since-commit`: Testdatei-Ausschluss bricht bei verschachteltem `tests_dir`; uncommittete Änderungen unsichtbar

**Schwere:** Mittel · **Status:** statisch verifiziert · **Kategorie:** CLI

**Fundort:** `src/mutmut_win/cli.py:273` und `cli.py:255` ff.

**Mechanik (a):** `_is_mutation_target` schließt Testdateien per
`all(parts[0] != td for td in tests_dirs)` aus — verglichen wird die **erste
Pfadkomponente** (`"tests"`) mit dem **vollen** konfigurierten String (`"tests/unit"`,
nach Strip). Bei verschachteltem `tests_dir` ist der Vergleich nie gleich → geänderte
Testdateien passieren den Filter und werden zu `paths_to_mutate`-Einträgen. **Dieses
Projekt selbst** konfiguriert `tests_dir = ["tests/unit/"]` — ein
`--since-commit`-Lauf nach einer Test-Änderung würde Testdateien mutieren (Trampolines
in Testcode, der zugleich via `also_copy` als Test läuft).

**Mechanik (b):** `git diff --name-only {ref}..HEAD` vergleicht Commits — **uncommittete
Working-Tree-Änderungen sind unsichtbar**. Der README-Workflow „Local, incremental —
check what you just changed" (`run --since-commit HEAD~1` direkt nach dem Editieren)
liefert dann „No .py files changed" mit Exit 0.

**Fix-Empfehlung:** (a) Pfad-präfixbasiert vergleichen:
`Path(name).parts[:len(td_parts)] == td_parts` je `tests_dir`. (b) `git diff
--name-only {ref}` (ohne `..HEAD`) einbeziehen oder beide Diffs vereinigen; Verhalten
im README präzisieren.

---

### A5 · README-Beispiel für `type_check_command` führt zum Laufabbruch

**Schwere:** Mittel · **Status:** empirisch verifiziert (README + Parser-Code) · **Kategorie:** Doku/UX

**Fundort:** `README.md:186` (`type_check_command = ["mypy", "src/"]`) vs.
`src/mutmut_win/type_checking.py:92`.

**Mechanik:** Der mypy-Zweig des Parsers verlangt zwingend JSON-Zeilen-Output
(`json.loads(line) for line in stdout.splitlines()`). Mit dem im README dokumentierten
Kommando (ohne `--output=json`) liefert mypy menschenlesbaren Text →
`TypeCheckCommandError` → Lauf bricht ab. Gleiches gilt für pyright ohne `--outputjson`.
Die interne Docstring (`['mypy', '--output=json', 'src/']`) ist korrekt — nur die
nutzerseitige Doku nicht. Es gibt weder Config-Validierung noch Warnung; der Nutzer
erfährt die Magie-Flags nur über den Fehlertext. Randnotiz: `--output=json` existiert
erst ab mypy 1.11 — nirgends dokumentiert.

**Fix-Empfehlung:** README-Beispiel korrigieren; beim Config-Load für erkannte Checker
(`_detect_checker`) das fehlende JSON-Flag entweder automatisch ergänzen oder mit
klarer Meldung ablehnen; mypy-Mindestversion dokumentieren.

---

### A6 · `--output json`: stdout-Reinheit mehrfach verletzt

**Schwere:** Mittel · **Status:** statisch verifiziert · **Kategorie:** CLI/CI

**Fundort:** `src/mutmut_win/cli.py:220` (`--force`-Echo), `cli.py:333`
(`redirect_stdout` beginnt erst hier), `src/mutmut_win/config.py:483` und :468
(Config-Warnungen via `print()`), `src/mutmut_win/process/worker.py:115` u. a.
(Kindprozess-Prints), `src/mutmut_win/process/executor.py:187`.

**Mechanik:** Drei Leck-Klassen:
1. **Deterministisch:** `--force` echo't `Removed mutants/` / `Removed .mutmut-cache/`
   auf stdout **vor** dem Redirect; ebenso landen Unknown-Key-/Twin-Warnungen aus
   `load_config()` (läuft vor dem Redirect) auf stdout.
2. **Kindprozesse:** `redirect_stdout` ersetzt nur das Python-Level-Objekt im
   Elternprozess. Worker-Prints (`WORKER RECOVERY`, `WORKER ERROR`,
   `WORKER MONITOR start failed`) und Warnungen aus den Generierungs-Pool-Workern
   (z. B. Meta-Korruptionswarnung in `models.load`) schreiben über den geerbten
   OS-Level-fd 1 direkt ins „reine" stdout.
3. Der Executor-Abbruchstext (alle Worker tot) läuft im Elternprozess und ist vom
   Redirect abgedeckt — gehört aber ohnehin nach stderr.

**Impact:** `mutmut-win run --output json --force` produziert heute **garantiert** kein
parsebares stdout; Worker-Hiccups verschmutzen JSON-Läufe nichtdeterministisch. Das
bricht exakt das Versprechen aus Issue #103/A4-UI-006.

**Fix-Empfehlung:** Output-Modus vor jeder Ausgabe bestimmen; `--force`-Echo und
Config-Warnungen auf stderr (`err=True` bzw. `print(..., file=sys.stderr)`);
Kindprozess-Diagnostik grundsätzlich auf stderr ausgeben (Worker erben fd 2 genauso).
Regressionstest: `run --output json --force` + Typo-Config-Key → `json.loads(stdout)`.

---

### A7 · Pool-Kollaps endet als Erfolg (Exit 0 / Gate über Rumpf-Rest)

**Schwere:** Mittel · **Status:** statisch verifiziert · **Kategorie:** Ausführung/CI

**Fundort:** `src/mutmut_win/process/executor.py:187` (Abbruchpfad), Orchestrator-Schritt 6/7,
`cli.py` (Exit-/Gate-Logik).

**Mechanik:** Sterben alle Worker (z. B. Crash-Kaskade), bricht `get_events()` die
Schleife ab. Der Orchestrator setzt nur `unchecked = total - completed`;
`was_interrupted` bleibt `False`. Die CLI behandelt ausschließlich `was_interrupted`
(Exit 130, Gate übersprungen). Beim Pool-Kollaps gilt dagegen: ohne `--min-score`
**Exit 0**; mit Gate wird der Score **über den geprüften Rest** gerechnet (`unchecked`
verlässt den Nenner) — ein Lauf mit 90 % ungeprüften Mutanten kann CI-grün enden. Die
einzige Spur ist eine Fehlerzeile, die im JSON-Modus auf stderr liegt.

**Fix-Empfehlung:** Pool-Kollaps als eigenen Abbruchzustand modellieren (z. B.
`run_aborted: true` im Summary + eigener Exit-Code ≠ 0; Gate fail-closed wie beim
„No testable mutants"-Fall). Mindestens: `--min-score` bei `unchecked > 0` ohne
Interrupt hart fehlschlagen lassen.

---

### A8 · Engine-Version fehlt in Staging-/Config-Fingerprints — Upgrades wirken nicht

**Schwere:** Mittel · **Status:** statisch verifiziert · **Kategorie:** Engine/Caching

**Fundort:** `src/mutmut_win/file_setup.py:345` (`config_fingerprint_matches`-Payload),
Meta-Fast-Path (`source_mtime`/`source_size`-Gleichheit).

**Mechanik:** Der Generierungs-Fast-Path reaktiviert gestagte Mutanten, wenn (a) Quelle
(mtime+size) und (b) Config-Universum (paths/do_not_mutate/coverage/also_copy/extra_paths)
unverändert sind. **Die Engine-Version ist in keinem der beiden Fingerprints enthalten.**
Nach einem mutmut-win-Upgrade mit Operator-Änderungen — v2.13.0 selbst hat per MUT-001
f-Strings in die Mutationsfläche aufgenommen! — bleiben unveränderte Dateien auf dem
alten Mutanten-Universum: neue Operatoren erscheinen **nie**, alte Nummerierungen und
Reuse-Verdicts leben konsistent-aber-veraltet weiter, bis die Quelldatei sich ändert
oder `--force` kommt. Nutzer, die v2.12→v2.13 upgegradet haben, sehen auf unveränderten
Dateien keine f-String-Mutanten.

**Fix-Empfehlung:** `mutmut_win.__version__` (oder ein Hash der Operatorliste) in den
`config_fingerprint_matches`-Payload aufnehmen — ein Feld, eine Zeile, invalidiert
genau bei Upgrades. Release-Note-Hinweis für Bestands-Stagings.

---

### A9 · `show <glob>` verliert das IL-Forensik-Panel

**Schwere:** Niedrig · **Status:** statisch verifiziert · **Kategorie:** CLI

**Fundort:** `src/mutmut_win/cli.py:562`.

**Mechanik:** `show` löst Patterns via `get_diff_for_mutant` → `resolve_mutant` korrekt
auf einen Mutanten auf — der anschließende DB-Lookup für das Forensik-Panel vergleicht
aber gegen das **Roh-Pattern** (`r.mutant_name == mutant_name`). Bei Glob-Aufruf
(`show 'src.mod.x_f__mutmut_?'`) fehlt das Panel kommentarlos.

**Fix-Empfehlung:** `resolve_mutant` einmal in `show` aufrufen (statt versteckt in
`get_diff_for_mutant`) und den aufgelösten Namen für Diff **und** DB-Lookup verwenden.

---

## 5 Anomalien & Robustheitslücken (B-Befunde, statisch verifiziert)

### B1 · In-place editierte Tests invalidieren das Mapping nicht (Mittel)
`stats.collect_or_load_stats` triggert Re-Collection nur bei **neuen/gelöschten
Node-IDs**. Ein editierter Test (gleiche ID) aktualisiert weder Duration noch — kritisch —
das Test↔Funktions-Mapping: Deckt ein bestehender Test neu eine Funktion ab, bleiben
deren Mutanten „no tests"; verstärkte Assertions erreichen ihre Mutanten über das
**alte** Test-Set (der Tests-Fingerprint erzwingt zwar Re-Run bei Datei-Änderung, aber
mit unveränderter Test-Zuordnung). Zudem ist die „re-running stats collection for them"-
Meldung (`stats.py:160`) irreführend: der `tests`-Parameter von `_run_stats_collection`
ist ungenutzt (`ARG001 — reserved`), es läuft **immer die volle Suite**.
**Empfehlung:** Test-Datei-Fingerprints im Stats-Cache persistieren; bei geänderten
Dateien Mapping-Einträge der betroffenen Node-IDs invalidieren und neu sammeln.

### B2 · `collect_tests` mit anderem Scope als die Stats-Phase (Mittel)
`runner.py:187`: Collection läuft im Projekt-Root **ohne** `cwd=mutants`, **ohne**
`tests_dir`-Argumente und **ohne** `pytest_add_cli_args` (nur `…_test_selection`).
Folgen: (a) Marker-Filter nur in `pytest_add_cli_args` (z. B. `-m "not slow"`) oder
fehlende `testpaths`-Konfiguration ⇒ Collection sieht dauerhaft „neue" Tests ⇒
**permanente Voll-Re-Collection bei jedem Lauf** (Inkrementalität wirkungslos);
(b) `encoding="utf-8"` ohne `errors=`-Fallback dekodiert die Pipe strikt — auf
cp1252-Konsolen mit Non-ASCII-Test-IDs (`parametrize`-IDs) droht `UnicodeDecodeError`.
**Empfehlung:** Collection mit identischem Scope (cwd, `tests_dir`, beide Arg-Listen)
wie die Stats-Phase fahren; `errors="replace"` bzw. `PYTHONUTF8=1` für das Kind.

### B3 · Timeout-Fallback: Voll-Suite mit Einzeltest-Budget (Mittel)
`orchestrator.py:788` (`_apply_timeouts`): Hat ein Task keine Tests, das Mapping ist
aber leer (Stats lief, ohne Trampoline-Hits — z. B. nie importiertes Package,
kaputtes Hit-Recording, kleines `max_stack_depth`), wird er mit dem **Mittelwert eines
einzelnen Tests** budgetiert, läuft aber die **volle Suite** (keine Node-IDs ⇒
`tests_dir`). Ergebnis: Timeout-Flut. Der `else`-Zweig (`clean_wall × multiplier`)
wäre der korrekte Fallback für genau diesen Fall.

### B4 · Type-Check-Filter ohne Baseline-Abzug (Mittel)
Ein **vorbestehender** Typfehler im Funktionskörper wird in jede Mutantenkopie der
Funktion repliziert — der Checker meldet ihn in jedem `x_f__mutmut_N`-Range, und
**alle** Mutanten der Funktion gelten als „caught by type check" (Score-Inflation),
obwohl die Mutation nichts damit zu tun hat. (Fehler in `__mutmut_orig`/Wrapper werden
korrekt verworfen — die Replikation in die Kopien nicht.) Upstream-Erbe.
**Empfehlung:** Baseline-Lauf des Checkers gegen das ungemutete Staging; nur **neue**
Fehler zählen. Mindestens: Verhalten dokumentieren („nur für baseline-saubere Projekte").

### B5 · Phasen-Timeouts reapen Enkelprozesse nicht (Mittel-Niedrig)
`runner._run_phase` nutzt `subprocess.run(timeout=…)` — bei Timeout wird nur das
direkte pytest-Kind gekillt. Anders als der Worker (per-Task-Job-Object +
psutil-Sweep) haben Clean-/Stats-/Forced-Fail-/Coverage-Phasen **keinen** Schutz gegen
überlebende Enkel (test-gespawnte Subprozesse). Asymmetrie zur sonst konsequenten
Orphan-Story.

### B6 · Staging-Stale-Lücken (Mittel-Niedrig)
(a) `file_setup.py:179`: Der Kopier-Sync nutzt `source_mtime > target_mtime` — ein
**rückdatierter Restore** (git checkout älterer Stand) einer **nicht-mutierten** Datei
bleibt unbemerkt stale (der `.meta`-Gleichheits-Fingerprint schützt nur mutierte
Dateien; die Docstring-Behauptung deckt den Fall nicht ab). Clean-Run validiert dann
gegen veralteten Code. (b) Unter dem `.`-Root **gelöschte Testdateien laufen für immer
weiter**: `_sync_deleted_sources` synct bewusst nur `src`/`source`, und der
`also_copy`-copytree löscht nie. Erst `--force` räumt auf — nirgends dokumentiert.

### B7 · `extra_paths` mit `..` zeigen am Staging vorbei (Niedrig)
Kopiert wird nach `mutants/<name>` (Bug-#69-Logik), aber Worker (`worker.py:192`) und
`runner._mutants_env` setzen `mutants/../x` auf den PYTHONPATH — das ist der **echte**
Sibling, nicht die Staging-Kopie. Heute inhaltsgleich (Siblings werden nicht mutiert),
aber die Kopie ist toter Ballast und die Isolation durchbrochen.

### B8 · IL-Konstanten doppelt definiert (Niedrig)
`EXIT_CODE_INFINITE_LOOP = 38` existiert in `constants.py:80` **und**
`loop_monitor.py:511` (dazu der Status-String). Das MUTANT_ENV_VAR-Vorbild
(#110: single source + Pin-Test) ist hier nicht angewandt — Drift-Risiko.

### B9 · setup.cfg-Pfad unvollständig und warnungslos (Niedrig)
`_load_setup_cfg` kennt weder `extra_paths` noch die `infinite_loop_*`-Keys und gibt —
anders als der pyproject-Pfad seit #102 — **keine** Unknown-Key-Warnung aus. Typos in
setup.cfg verschwinden lautlos.

### B10 · Meta-Load toleriert nur Decode-Korruption (Niedrig)
`SourceFileMutationData.load` fängt `JSONDecodeError`/`UnicodeDecodeError` (A3-CM-009),
aber valide JSON mit falschen Typen (`"duration": null` ⇒ `float(None)`) wirft einen
unbehandelten `TypeError` und blockiert Läufe bis zum manuellen Löschen — exakt die
Fehlerklasse, die #101 eigentlich schließen wollte.

### B11 · Methoden verschachtelter Klassen werden still nie mutiert (Niedrig, Upstream-Erbe)
`OuterFunctionProvider.visit_Module` (`mutation.py:83`) registriert nur Top-Level-
Funktionen und Methoden von Top-Level-Klassen. Nested-Class-Methoden erzeugen Mutationen
ohne Top-Level-Zuordnung, die beim Gruppieren kommentarlos verworfen werden — keine
Warnung, keine Doku.

### B12 · Nenner-Divergenz bei Legacy-Status (Niedrig, theoretisch)
`results`/`export-cicd-stats` rechnen `total − skipped − no_tests`; Zeilen mit
Legacy-Status (`check was interrupted by user`, `not checked` aus Alt-DBs) bleiben im
Nenner, während das Run-Gate `unchecked` ausschließt. README behauptet formale
Gleichheit der drei Kanäle. Praktisch nur bei migrierten Alt-Datenbanken relevant.

### B13 · Umgebung: ruff-Gate aktuell nicht reproduzierbar (Niedrig)
`uv run ruff check .` liefert 23 Findings — **alle** in
`.claude/skills/mcp-builder/scripts/` (nach Sprint-35-Abschluss hinzugekommene
Skill-Dateien). `tool.ruff.exclude` kennt nur `tests/e2e_projects`. Empfehlung:
`.claude/` in die Exclude-Liste aufnehmen, damit „ruff 0" wieder ein ehrliches Gate ist.

---

## 6 Optimierungspotentiale (C-Befunde)

| # | Potential | Ort | Erwarteter Effekt |
|---|---|---|---|
| C1 | `save_result` öffnet **pro Mutant** zwei SQLite-Connections inkl. `create_db`-Schema-Check; `_persist_skipped_mutants` lädt zusätzlich die ganze DB und schreibt pro Name einzeln. Eine Verbindung pro Lauf + `executemany`-Batches | `db.py`, Orchestrator-Persist-Pfade | Bei 7.800 Mutanten zehntausende Connects gespart; Persist-Overhead um Größenordnungen kleiner |
| C2 | `copy_also_copy_files` kopiert `tests/` u. a. **jeden Lauf vollständig** (`copytree dirs_exist_ok`, `file_setup.py:314`) — mtime-Sync wie `copy_src_dir` | file_setup | Spürbar bei großen Test-Trees; löst zugleich Teil von B6(b), wenn mit Deletion-Sync kombiniert |
| C3 | Inkrementelle Stats wirklich inkrementell: ungenutzten `tests`-Parameter implementieren (gezielter Re-Run + Merge statt Voll-Suite bei jedem neuen Test) | stats/runner | Stats-Phase skaliert mit Δ statt Suite-Größe |
| C4 | `copy_src_dir`: `.`-Walk kopiert `src`/`source` doppelt; `skip_dirs` um `node_modules`, `.import_linter_cache`, `.benchmarks`, `.serena`, `.claude` erweitern (oder `.gitignore` honorieren) | file_setup | Schnellere Erstläufe, schlankeres Staging |
| C5 | `regex_mutation`: identische Mutanten dedupen (Quantifier-/Klassen-Mutationen können kollidieren) | regex_mutation | Weniger äquivalente Duplikat-Mutanten |
| C6 | `status_by_exit_code` als `defaultdict` mutiert sich bei jedem Unknown-Lookup selbst — plain `dict` + `.get(code, "suspicious")` | constants | Hygiene; keine Seiteneffekte durch Lookups |

---

## 7 Entkräftete Verdachtspunkte & Positivbefunde

**Geprüft und entkräftet:**
- `SetInformationJobObject` erhält die **Int-Konstante** `_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION`
  (= 9), nicht die fast gleichnamige ctypes-Strukturklasse (`job_object.py:144`) — kein Bug.
- Verdacht „Source-Änderung ⇒ falscher Verdict-Reuse": strukturell ausgeschlossen — Reuse
  ist an den Staging-Fast-Path gekoppelt (Quell-Fingerprint-Gleichheit), zusätzlich
  Tests-Fingerprint **und** Status-Whitelist (`REUSABLE_STATUSES`). Saubere Konstruktion.

**Positivbefunde (Auswahl):**
- Semgrep-clean über 320 Regeln; konsequente `encoding='utf-8'`-Disziplin.
- Job-Object-Bindings korrekt und least-privilege (A2-JT-006/017 wirksam).
- IL-Klassifikator handwerklich stark: Instanz-Caching für `cpu_percent` (dokumentierte
  psutil-Falle), Veto-Logik für IO-Progress, Confidence-Kappung bei fehlendem
  Status-Signal, Forensik-Persistenz.
- Disjunkte Score-Buckets mit lautem Drift-Schutz (`_increment_summary`-Default-Zweig).
- Atomare Schreibpfade (`.meta`-tmp-Swap, `apply` mit Backup + `os.replace` + Staleness-Gate).

---

## 8 Priorisierungsvorschlag

| Welle | Befunde | Begründung |
|---|---|---|
| 1 | **A1, A2** | Beschädigen Kernversprechen auf realen Zielprojekten (Browse-/Meta-Wahrheit; Kompatibilität des zentralen Dispatch-Mechanismus) |
| 2 | **A6, A7** | CI-Vertrauen: deterministische JSON-Verschmutzung, false-green bei Pool-Kollaps |
| 3 | **A3, A8, A4** | Korrektheitsschulden mit klaren, kleinen Fixes (Root-Strip, Versions-Fingerprint, Pfadvergleich/Diff-Basis) |
| 4 | **A5, B13** + B1–B4 | Doku-/Gate-Ehrlichkeit, dann Stats-/Mapping-Subsystem |
| 5 | Rest B + C gebündelt | Maintenance-Paket nach bewährtem Muster (#118–#123) |

*Alle Zeilenangaben beziehen sich auf `main` @ `2e481fd` (v2.13.0).*
