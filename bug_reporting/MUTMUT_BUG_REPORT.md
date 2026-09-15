# BUG REPORT — mutmut-win 2.21.2: Reproduzierbarer Hänger im Run-Startup (Windows / Python 3.14)

**Report-ID:** MBR-2026-09-14-01
**Datum:** 2026-09-14
**Reporter:** GLM-5.3 (OpenCode Agent), Projekt `lean4-lsp-mcp-server` (PO: pgm1980)
**Ziel:** Entwicklerteam mutmut-win — Bugfixing
**Schweregrad:** **Blocker** (Mutation-Gate des Projekts nicht ausführbar; `--min-score`-CI-Gate unmöglich)
**Status beim Reporter:** Task 3.4 (Mutation ≥ 97 % auf `repl`/`loogle`/`file_utils`) blockiert; Projekt fährt ohne mutmut-win weiter (CI-Mutation-Job zurückgestellt)

---

## 1. Zusammenfassung (Executive Summary)

`mutmut-win run --profile all` hängt auf unserem Windows-Setup **reproduzierbar** unmittelbar nach dem Force-Cleanup (bzw. sofort ohne `--force`) in der Phase **vor** „Running clean test suite…" (`orchestrator.py:663`). Der Parent-Python-Prozess brennt dabei **~100 % eines einzelnen Kerns** (89,6 CPU-Sekunden in 90 s Wall-Time gemessen), ohne jegliche Ausgabe — **auch nicht mit `--debug`**. Das Staging-Verzeichnis `mutants/` bleibt leer bzw. wird nie angelegt. Kein einziger Mutant wird ausgeführt (`results`: `0 completed`).

Bemerkenswert: Der **allererste** Lauf (Legacy-Konfiguration, s. Abschnitt 4.1) kam bis zur Clean-Suite-Ausführung (nach 35,6 min) — alle Folgeläufe mit verfeinerter Konfiguration hängen vorher. `--dry-run` (laut `cli.py:690-696` wird dabei der Executor nicht konstruiert) funktioniert **einwandfrei und schnell**. Das grenzt den Fehler auf die Kette **Executor-Konstruktion / Staging / Coverage-Basis / Clean-Run-Vorbereitung** ein — die Mutations-Engine selbst (Generierung) arbeitet korrekt.

Drei Begleitfunde (Abschnitt 7) betreffen Staging-Kosten bei Lean-Repos, eine Defender-Race im Force-Cleanup und einen Observability-Gap.

---

## 2. Umgebung

| Komponente | Wert |
|---|---|
| OS | Windows 11 (Windows NT 10.0.26200.0), 64 bit |
| CPU | AMD Ryzen AI 9 HX 370, 24 logische Kerne |
| RAM | 63 GB |
| Python | 3.14.7 (MSC v.1944, `tags/v3.14.7:823f032`) — **exakter Pin** (`requires-python ==3.14.7`) |
| mutmut-win | **2.21.2**, installiert per Git-Source `[tool.uv.sources]` → `git+https://github.com/pgm1980/mutmut-win.git@v2.21.2` |
| Package-Manager | uv (aktuell); Aufruf immer `uv run mutmut-win …` |
| Projekt | `lean4-lsp-mcp-server` (MCP-Server, pytest 9.1.1, pytest-asyncio, asyncio_mode=auto) |
| Besonderheit Projekt | Lean-Repo: `tests/test_project/.lake` = **6,7 GB** Build-Baum (gitignored); `tests/` enthält Root-Integrationstests, die echte Lean-Prozesse brauchen |
| Antivirus | Windows Defender real-time protection aktiv (Default) |

Versionen der relevanten mutmut-win-CLI-Befehle (alle funktional): `--version` ✓, `run --help` ✓, `results` ✓, `run --dry-run` ✓.

---

## 3. Reproduktion

### 3.1 Aktuelle Projektkonfiguration (`pyproject.toml`, beim Hänger)

```toml
[tool.mutmut]
paths_to_mutate = [
    "src/lean4_lsp_mcp/file_utils.py",
]
tests_dir = ["tests/unit", "tests/test_repl.py"]
pytest_add_cli_args = ["-m", "not slow and not network", "-p", "no:cacheprovider"]
pytest_add_cli_args_test_selection = [
    "-m",
    "not slow and not network",
    "-p",
    "no:cacheprovider",
]
mutate_only_covered_lines = true
```

### 3.2 Repro-Schritte

```powershell
# Im Projekt-Root (lean4-lsp-mcp-server)
uv run mutmut-win run --profile all --max-children 6 --no-progress --force
```

### 3.3 Erwartetes Verhalten

Nach „Removed mutants/" / „Removed .mutmut-cache/" folgen Mutanten-Generierung, Staging, und der Phase-Print **„Running clean test suite…"** (`orchestrator.py:663`); anschließend Mutant-Ausführung; am Ende `results` mit Score.

### 3.4 Tatsächliches Verhalten

```
Removed mutants/
Removed .mutmut-cache/
          <<<< HIER: dauerhaft Stille — 15 bis 59+ Minuten, dann Tool-Timeout >>>>
```

- Keine weitere Ausgabe, **auch nicht mit `--debug`** und **ohne** `--no-progress` (Progress-Rendering bleibt aus).
- Prozessbild: ein Python-Prozess (Parent) mit **~100 % eines Kerns** (kontinuierlich), z. B. PID 34676: `CPU=89,62 s` bei ~90 s Wall-Time seit Start.
- `mutants/` existiert nicht oder ist **leer (0 Dateien)**.
- „Running clean test suite…" wird nie gedruckt.
- `uv run mutmut-win results` danach: `Run status: failed (0 completed, 0 pending, 0 reused)` / `No results found`.
- stdout/stderr-Umleitung in Dateien bleibt **leer** (getestet mit `Start-Process -RedirectStandardOutput/-RedirectStandardError`).

### 3.5 Getestete Variationen (alle mit identischem Hänger)

| Variation | Ergebnis |
|---|---|
| `--max-children 6` | Hänger |
| `--max-children 1` | Hänger (ohne Force; mit Force s. Abschnitt 6 — Defender-Race) |
| `--force` / ohne `--force` | Hänger jeweils |
| `--no-progress` / mit Progress | Hänger jeweils |
| `--debug` | Hänger, keine zusätzliche Ausgabe |
| `tests/test_project/.lake` (6,7 GB) **aus dem Baum entfernt** (Same-Volume-Move) | Hänger unverändert → **Staging-Kosten als Ursache ausgeschlossen** |
| `--dry-run` (gleiche Config, `--paths-to-mutate`-Override) | ✅ **funktioniert**: „Dry run: 205 mutants would be generated." in Sekunden |

---

## 4. Chronologie der Versuche (mit Config-Evolution)

> Reihenfolge der Konfigurationsänderungen ist vermutlich diagnostisch relevant — der einzige Lauf, der über den Hängepunkt hinauskam, nutzte die Legacy-Konfiguration.

### 4.1 Versuch 1 — Legacy-Config: **kommt durch** (35,6 min, scheitert dann an roter Clean-Basis)

Config zu diesem Zeitpunkt:

```toml
[tool.mutmut]
paths_to_mutate = [
    "src/lean4_lsp_mcp/file_utils.py",
    "src/lean4_lsp_mcp/loogle.py",
    "src/lean4_lsp_mcp/repl.py",
]
tests_dir = "tests/"            # ← STRING, nicht Liste
# (keine pytest_add_cli_args, keine pytest_add_cli_args_test_selection,
#  kein mutate_only_covered_lines)
```

Aufruf: `uv run mutmut-win run --profile all --max-children 4 --no-progress` (ohne `--force`)

Verhalten: Lauf **erreicht** die Clean-Suite-Ausführung. Terminal-Output endet mit einer pytest-Zusammenfassung der **gesamten** `tests/`-Bauernts (inkl. Root-Integrationstests): `34 failed, 327 passed, 19 skipped in 147.11s` — die 34 Fehler sind umgebungsabhängige Integrationstests (echtes Lean), d. h. die Clean-Basis war rot → Lauf brach ab: `results: failed (0 completed, 1903 pending)`.

**Erkenntnis:** Staging, Executor (4 Worker) und Clean-Run-fähige Pipeline funktionierten unter dieser Config grundsätzlich — nur die Testbasis war falsch (deshalb die Folgeänderungen).

### 4.2 Versuch 2 — Config-Anpassung: Hänger beginnt

Änderungen gegenüber 4.1: `tests_dir = ["tests/unit", "tests/test_repl.py"]` (Liste, enthält eine **Datei**), `pytest_add_cli_args` ergänzt, `--force` im Aufruf. → 59-min-Timeout, keine Ausgabe nach „Removed …".

### 4.3 Versuch 3 — Verengung auf ein Modul + `mutate_only_covered_lines = true`

`paths_to_mutate = ["src/lean4_lsp_mcp/file_utils.py"]`, `--min-score 97` (→ korrekt abgelehnt: „--min-score requires a full unfiltered run"), dann ohne min-score mit `--force --max-children 6` → 40-min-Timeout, keine Ausgabe.

### 4.4 Versuch 4 — Observability

Foreground 4 min mit Progress: nur „Removed …"-Zeilen. Hintergrundlauf (`Start-Process`, Hidden/NoNewWindow, stdout/stderr in Dateien) + Poll nach 90/100 s: Logs leer, `mutants/` fehlt, Python-Prozess mit 100 %-Kern-Auslastung (s. 3.4).

### 4.5 Versuch 5 — `pytest_add_cli_args_test_selection` ergänzt

Annahme: Die Selection-/Stats-Phase könnte separate Args brauchen. Ergänzt (s. 3.1). → Hänger unverändert; zusätzlich einmalig die in Abschnitt 6 beschriebene Force-Cleanup-Verweigerung.

### 4.6 Versuch 6 — `--max-children 1` (mit und ohne `--force`)

Ohne Force: 15-min-Timeout, keine Ausgabe. Mit Force: 0,8–1,8 min, dann „Could not fully remove mutants/ (files in use?); refusing to run with stale state." (transient — s. Abschnitt 6; `mutants/` war im Nachhinein nachweislich ungelockt und leer). Nach manuellem Cleanup + Retry: wieder 15-min-Hänger ohne Force.

---

## 5. Code-Analyse (installierter Stand 2.21.2)

Quoten Code-Referenzen aus `.venv/Lib/site-packages/mutmut_win/`:

| Stelle | Beobachtung |
|---|---|
| `cli.py:656-680` | Force-Cleanup: `shutil.rmtree(ignore_errors=True)` + Existenz-Check + Verweigerungsmeldung („files in use?") — Quelle der transienten Defender-Race (Abschnitt 6) |
| `cli.py:687-698` | Nach dem Cleanup: `PytestRunner(config)` und **`SpawnPoolExecutor(max_workers=config.max_children, config=config)`** — Kommentar: „A dry-run is a source-only preview: constructing the Windows executor here **would create a Job Object** even though no worker can be used." → Dry-run überspringt genau diese Konstruktion — und dry-run funktioniert (3.5). **Hauptverdächtiger der Kette.** |
| `cli.py:711` | `orchestrator.run()` |
| `orchestrator.py:614-627` | Task-Selektion + `_start_current_run` vor Phase 1b |
| `orchestrator.py:630-655` | Step 1b: Type-Check-Filter nur falls `type_check_command` konfiguriert (bei uns: nicht konfiguriert → übersprungen) |
| `orchestrator.py:657-666` | Step 2: Print „Running clean test suite…" + `run_clean_test()` — **wird nie erreicht** |
| `runner.py:660-662` | Test-Basis-Kommando: `[sys.executable, "-m", "pytest"]` — **kein** `uv`-Re-Entry, kein Venv-Lock-Deadlock möglich |
| `config.py:418-439` | `default_also_copy`: `["tests/", "test/", "setup.cfg", "pyproject.toml", …]` + Root-`test*.py` — kopiert `tests/` **komplett** (Nebenbefund 7.1) |
| `file_setup.py:55-60`, `constants.py` (`WORKSPACE_EXCLUDED_DIR_NAMES`) | Staging-Skip-Liste enthält `.venv`, `__pycache__`, `.git`, Caches — **nicht** `.lake` (Nebenbefund 7.1) |

### Eingrenzung

Funktional geprüft und **ausgeschlossen** als Ursache:

1. **uv-Re-Entrancy/Venv-Deadlock** — Runner nutzt `sys.executable -m pytest` direkt.
2. **Staging-Kosten durch 6,7-GB-`.lake`** — Ausstashen (Same-Volume-Move, sofort wirksam) änderte nichts.
3. **Gelockte Dateien/verwaiste Prozesse** — Prozess-Scan (CommandLine-Prüfung) zeigte ausschließlich die MCP-Infrastruktur des Agenten (maxential), keine mutmut-Waisen; `mutants/` war im Ruhezustand leer und frei umbenennbar.
4. **Hängende/pytest-seitige Probleme** — die Unit-Basis läuft standalone in 1,3–2,5 s (284 passed / 0 failed); Clean-Run-Phase wird gar nicht erst erreicht.
5. **Mutations-Engine/Generierung** — `--dry-run` generiert korrekt und schnell (205 Mutanten für `file_utils.py`, Profil `all`).
6. **CPU-Auslastung Muster** — genau **ein** Kern voll (nicht n), über Minuten: passt zu einem Busy-Spin/engen Loop in einem einzelnen Prozess, nicht zu Worker-Pool-Aktivität.

---

## 6. Nebenbefund A — Force-Cleanup-Race mit Windows Defender (transient)

**Symptom:** „Could not fully remove mutants/ (files in use?); refusing to run with stale state." (cli.py:671-678) bei **zwei** Läufen; Direkt danach war `mutants/` manuell **ohne Lock** entfernbar (Rename-Test erfolgreich, 0 Dateien im Verzeichnis).

**Interpretation:** `shutil.rmtree(ignore_errors=True)` raced mit Defender-Realtime-Scan (oder Search-Indexer) über frisch angelegte Python-Dateien; die Existenz-Prüfung direkt danach schlägt fehl, obwohl der Lock nur Millisekunden besteht. Der anschließende **Refusal** ist ehrlich (Issue #101-Kommentar im Code), führt aber zu nicht-deterministischem CI-Verhalten.

**Vorschlag:** Retry-with-backoff (z. B. 3× 1–2 s) vor dem Refusal; oder Lock-Prüfung verzögert wiederholen.

---

## 7. Nebenbefund B — Staging-Kosten bei Lean-Repositories (6,7 GB)

`default_also_copy` enthält `"tests/"` pauschal. Lean-Projekte halten ihre Build-Bäume unter `tests/*/.lake` (hier: `tests/test_project/.lake` = **6,7 GB**, korrekt in `.gitignore`). Der Staging-Walk (`file_setup.py`, Skip-Liste `WORKSPACE_EXCLUDED_DIR_NAMES` enthält `.venv`/`.git`/Caches, **nicht** `.lake`) kopiert/verarbeitet diese Bäume — im einzigen durchgelaufenen Versuch (4.1) erklärt das einen Großteil der 35,6 min.

**Hinweis:** Das Ausstashen von `.lake` behob den Primär-Hänger **nicht** (s. 3.5) — es bleibt ein eigenständiges Kosten-/Skalierungsproblem.

**Vorschläge (beliebig/kombinierbar):**
1. `.gitignore`-Beachtung im Staging-Walk (pfadgenau, nicht nur Verzeichnisnamen),
2. neue Config `do_not_copy` (Globs, analog `do_not_mutate`),
3. optional `.lake` in die `WORKSPACE_*_EXCLUDED_DIR_NAMES` (Lean-Profil; ggf. opt-in, um generische Namen nicht zu hart zu codieren).

---

## 8. Nebenbefund C — Observability-Gap in der Hängezone

Zwischen „Removed .mutmut-cache/" und „Running clean test suite…" existiert **kein einzigen** Fortschritts-/Debug-Ausgaben — auch mit `--debug` und ohne `--no-progress` nicht. Bei einem Single-Core-Busy-Spin von 15–60 min bleibt dem Anwender jede Angriffsfläche für Diagnose genommen (stdout-Redirection leer).

**Vorschlag:** Phase-Entry-Prints (Generation/Staging/Coverage-Basis/Executor-Warmup) plus `--debug`-Trace in genau dieser Kette; idealerweise ein Watchdog, der 60 s ohne Fortschritt mit Stackdump abbricht.

---

## 9. Bisektions-Hypothesen (priorisiert, mit Gegenargumenten)

Für das Team als Startpunkte; nummeriert nach unserer Wahrscheinlichkeitseinschätzung:

| # | Hypothese | Dafür | Dagegen |
|---|---|---|---|
| H1 | **`mutate_only_covered_lines = true`** löst eine Coverage-Basis-Erfassung aus, die in einem engen Loop/CPU-Spin hängt (z. B. Coverage-Engine auf Python 3.14 / `sys.monitoring`-Interaktion) | Single-Core-100 %-Spin passt; Option war in **jedem** hängenden Lauf gesetzt und in keinem funktionierenden | Nicht direkt verifiziert |
| H2 | **`tests_dir` als Liste mit Datei-Eintrag** (`"tests/test_repl.py"`) bricht Staging/Globbing → stiller Retry/Spin | Änderung List+Datei kam genau mit dem ersten Hänger (4.1 → 4.2); Legacy-String lief durch | — |
| H3 | **`pytest_add_cli_args` mit Leerzeichen-Wert** (`"not slow and not network"`) wird zu einem Command-String gejoined und falsch gequotet (config.py-Docstring erwähnt „raw argument string … ValueError on unbalanced quotes") → interaktiver/blockierter Aufruf | Timing passt ebenfalls (4.2) | Clean-Run-Phase wird gar nicht erreicht — der Fehler müsste schon bei Vorbereitung/Parsing greifen |
| H4 | **`SpawnPoolExecutor`-Konstruktion (Windows Job Object)** deadlocked | cli.py-Kommentar markiert genau diesen Schritt als Windows-spezifisch; dry-run (ohne Executor) funktioniert | `--max-children 1` hing ebenfalls → weniger wahrscheinlich, aber nicht ausgeschlossen (Konstruktion ist unabhängig von `max_workers`) |
| H5 | Interaktion `--force` × Neu-Sync × uv-Build | In hängenden Läufen sah man „Built lean4-lsp-mcp-server …" | Auch ohne `--force` gehängt |

**Empfohlene Bisektionsreihe** (jeweils `--profile all --max-children 4`, Projektrepro aus 3.2):

1. `mutate_only_covered_lines = false` (alles andere unverändert) → läuft?
2. Falls Hänger: `tests_dir = "tests/unit"` (String, ohne Datei-Eintrag) → läuft?
3. Falls Hänger: `pytest_add_cli_args`/`…_test_selection` entfernen → läuft?
4. Falls immer noch Hänger: Kombination Legacy-Config aus 4.1 + einzeln H1/H2/H3-Optionen zugeben → welche Option kippt den Lauf in den Hänger?

---

## 10. Workarounds beim Reporter (Status)

| Workaround | Ergebnis |
|---|---|
| `.lake` aus Staging nehmen (Move) | kein Effekt auf den Hänger (nur Kosten) |
| `--max-children 1` | kein Effekt |
| Force/No-Force, Debug, Progress-Varianten | kein Effekt |
| `--dry-run` als Teil-Ersatz | ✅ nutzbar für Mutantenzahl/Planung, **kein Score** |
| **Entscheidung:** Sprint-Arbeit ohne mutmut-win fortsetzen; `[tool.mutmut]`-Config bleibt in `pyproject.toml` hinterlegt; Task 3.4 blockiert; CI-Mutation-Job zurückgestellt bis Fix vorliegt | aktiv |

---

## 11. Anforderung an das Team (Zusammenfassung)

1. **Primär:** Hänger reproduzieren (Abschnitt 3) und fixen — Priorität H1→H4 aus Abschnitt 9; ein Fortschritts-Output in der Hängezone (Abschnitt 8) wäre allein schon ein großer Diagnosegewinn.
2. **Nebenbefund A:** Retry/Backoff im Force-Cleanup statt sofortigem Refusal.
3. **Nebenbefund B:** `.gitignore`-Beachtung oder `do_not_copy`-Config fürs Staging (Lean-Repos: GB-schwere `tests/*/.lake`).
4. **Nebenbefund C:** `--debug`-Tracing + Watchdog in Generation/Staging/Executor-Warmup.

**Rückmeldungs-Kanal:** PO pgm1980 / Projekt `lean4-lsp-mcp-server`; Detail-Log der Versuche in `MEMORY.md` (Abschnitt „Offene Punkte") und `.sprint/sprint_backlog_sprint1.md` (Task 3.4).

---

## Anhang — Konsolidierte Befehle für Ersttests

```powershell
# Repro (Hänger erwartet)
uv run mutmut-win run --profile all --max-children 6 --no-progress --force

# Funktionierender Referenzpunkt
uv run mutmut-win run --paths-to-mutate src/lean4_lsp_mcp/file_utils.py --profile all --dry-run

# Prozessbild während des Hängers mitbeobachten
Get-Process python | Sort-Object CPU -Descending | Select-Object -First 5 Id, CPU, StartTime
```

## Nachtrag (2026-09-14, vor Übergabe) — Querdatenpunkt anderes Projekt

**Beobachtung des PO:** Eine andere GLM-5.3-Instanz arbeitet zeitgleich auf einem **anderen Projekt** mit mutmut-win 2.21.2 — **ohne einen einzigen Hänger**.

**Bewertung für die Bisektion (Abschnitt 9):**

- Zusammen mit dem einzigen hier durchgelaufenen Versuch (4.1, Legacy-Config: `tests_dir = "tests/"` als String, keine pytest-Args, kein `mutate_only_covered_lines`) stützt das die **konfigurationsspezifischen** Hypothesen **H1/H2/H3** deutlich und rückt **H4** (universeller Windows-Job-Object/Executor-Defekt) nach hinten — ein solcher müsste auf der anderen Maschine ebenfalls zuschlagen.
- **Wichtigste Frage an das Team daher:** Welche `[tool.mutmut]`-Konfiguration nutzt das andere Projekt? Falls es (nahezu) Defaults sind, ist der effektive Diff gegen dieses Projekt vermutlich: `tests_dir` als Liste mit **Datei-Eintrag** (`"tests/test_repl.py"`), `pytest_add_cli_args`/`pytest_add_cli_args_test_selection` mit **Leerzeichen-Wert** (`"not slow and not network"`), `mutate_only_covered_lines = true`. Die Bisektionsreihe aus Abschnitt 9 (Schritt 1→3) prüft genau diese drei einzeln.
- Projektbesonderheiten, die weiterhin als Kofaktoren im Blick bleiben sollten, aber als **Hänger-Ursache bereits ausgeschlossen** sind: 6,7-GB-`.lake`-Staging (Ausstashing änderte nichts — Abschnitt 3.5) und uv-Re-Entrancy (Runner nutzt `sys.executable -m pytest`, Abschnitt 5).

*Erstellt von GLM-5.3 (OpenCode) im Auftrag des PO; alle Beobachtungen aus Erste-Hand-Diagnose vom 2026-09-14.*
