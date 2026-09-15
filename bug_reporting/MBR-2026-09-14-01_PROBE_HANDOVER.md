# PROBE-HANDOVER — MBR-2026-09-14-01 (Run-Startup-Hänger, mutmut-win 2.21.2)

**An:** GLM-5.3 (OpenCode Agent), Projekt `lean4-lsp-mcp-server` (PO: pgm1980)
**Von:** mutmut-win-Entwicklung (Analyse vom 2026-09-14)
**Bezug:** `bug_reporting/MUTMUT_BUG_REPORT.md` (MBR-2026-09-14-01)
**Zweck:** Beweisführung der Hänge-Ursache auf der Reporter-Maschine per Faulthandler-Stackdump + gezielte Umgebungsfragen

---

## 1. Analysestand (Zusammenfassung für den Reporter)

Eure Bisektionshypothesen H1–H4 wurden auf unserer Seite geprüft — **alle vier sind widerlegt**:

| Hypothese | Ergebnis | Kurzbegründung |
|---|---|---|
| H1 `mutate_only_covered_lines` | ❌ | Coverage-Collection läuft NACH dem Profil-Hint (orchestrator.py:1286); euer Hänger liegt nachweislich davor (der Hint wurde nie gedruckt). |
| H2 `tests_dir`-Liste mit Datei-Eintrag | ❌ | Wir haben ein Projekt mit exakt eurer Config-Form (tests_dir-Liste mit `tests/test_repl.py`, pytest-Args mit Leerzeichen-Wert, `mutate_only_covered_lines=true`, `--profile all --force`) gebaut: **kompletter Durchlauf in 58 s** (29 Mutanten, Score 79,3 %). |
| H3 pytest-Args-Quoting | ❌ | Args greifen erst in Test-Phasen; lokal läuft dieselbe Pipeline durch. |
| H4 `SpawnPoolExecutor`-Konstruktion | ❌ | Konstruktor = Job-Object + Queues; kein Spawn, kein Loop (process/executor.py:88–127). |

Zusätzlich untersucht und **ausgeschlossen**: Run-Lock-Mechanik (strikt non-blocking; orphaned `.run.lock`-Dateien erzeugen höchstens einen sauberen Fehler, nie einen Spin), Atomic-Write-Retries (keine Loops), Observability-Schicht (opt-in, ohne Session pass-through).

**Die stille Zone zwischen „Removed .mutmut-cache/" und „profile=… operators active" enthält genau eine schwere Operation:** den zweifachen Ausführungsbasis-Fingerprint (orchestrator.py:330 → stats.py `_build_stats_context_evidence`), der den gesamten Projektbaum, alle konfigurierten Bäume, **jede Datei jeder installierten Distribution (komplettes Venv)** sowie effektive Import-Pfade hasht.

**Referenzmessung auf gesunder Maschine** (Windows 11, NVMe, Defender aktiv, CPython 3.14.7, mutmut-win 2.21.2):

| Szenario | Dauer der stillen Zone |
|---|---|
| Mini-Projekt (Venv: 2.174 Dateien / 40 MB) | 13,4 s |
| dito + 2 GB Pseudo-`.lake` im Projektbaum | 24,3 s (≈ 11 s pro 2 GB) |

Hochgerechnet entsprächen eure 15–60 min Stille **~300 GB–1,3 TB** Hash-Äquivalent — auf einer gesunden Maschine undiskutabel. Auch euer `.lake`-Entfernungs-Test (Hänger unverändert) passt dazu: Der Baum ist nicht das Problem. **Der Hänger ist eine umgebungsspezifische Pathologie** (z. B. Riesen-Venv, AV-/Filter-Treiber-Interaktion mit dem dateiintensiven Basis-Walk, Cloud-Placeholder-Sync) — und ist ohne Stack-Sicht auf eurer Maschine nicht final identifizierbar. Genau dafür ist die folgende Sonde.

---

## 2. Diagnose-Sonde (Copy-Paste-fertig)

Datei `_hang_probe.py` **im Projekt-Root** (`lean4-lsp-mcp-server`) anlegen — exakt dieser Inhalt:

```python
"""Diagnostic probe for MBR-2026-09-14-01 (mutmut-win 2.21.2 run-startup hang).

Runs the mutmut-win CLI in-process and dumps the exact Python stack to stderr
if the run does not finish within HANG_PROBE_TIMEOUT seconds (default 120).
The ``__main__`` guard keeps multiprocessing spawn children from re-running
the CLI when they import this module as ``__mp_main__``.
"""

from __future__ import annotations

import faulthandler
import os
import sys
import time

if __name__ == "__main__":
    timeout_seconds = float(os.environ.get("HANG_PROBE_TIMEOUT", "120"))
    faulthandler.dump_traceback_later(timeout_seconds, exit=True)

    from mutmut_win.cli import cli

    argv = sys.argv[1:] or [
        "run",
        "--profile",
        "all",
        "--max-children",
        "6",
        "--no-progress",
        "--force",
    ]

    started = time.perf_counter()
    print(f"[probe t=0.000s] invoking: mutmut-win {' '.join(argv)}", flush=True)
    try:
        cli(argv, standalone_mode=False)
    except SystemExit as exit_request:
        print(
            f"[probe t={time.perf_counter() - started:.3f}s] CLI exited "
            f"with code {exit_request.code}",
            flush=True,
        )
        raise
    print(f"[probe t={time.perf_counter() - started:.3f}s] CLI returned", flush=True)
```

### Ausführung (normales PowerShell-Terminal im Projekt-Root — NICHT über Agent-Tooling, damit stdout zeilengepuffert bleibt):

```powershell
$env:HANG_PROBE_TIMEOUT = "120"
uv run python _hang_probe.py run --profile all --max-children 6 --no-progress --force 2>&1 |
    Tee-Object -FilePath hang-stack-run1.txt
```

Nach 120 s bricht die Sonde automatisch ab und schreibt den **exakten Python-Stack der Hänge-Stelle** nach stderr (im Log: Block ab „Timeout … Thread …"). 

### Zweiter Lauf (wichtig zur Unterscheidung „festgefahren" vs. „endlos langsam"):

```powershell
$env:HANG_PROBE_TIMEOUT = "300"
uv run python _hang_probe.py run --profile all --max-children 6 --no-progress --force 2>&1 |
    Tee-Object -FilePath hang-stack-run2.txt
```

- Zeigen beide Dumps **denselben Frame** → echter Deadlock/Spin an einer Stelle.
- Zeigen sie **unterschiedliche Dateien/Pfade** (z. B. verschiedene `_hash_context_file`-Aufrufe) → langsam fortschreitender Walk (dann sind die Fragen 1–3 unten entscheidend).

### Alternative ohne Datei (One-Liner, 60 s):

```powershell
uv run python -c "import faulthandler,sys;faulthandler.dump_traceback_later(60,exit=True);from mutmut_win.cli import cli;cli(sys.argv[1:],standalone_mode=False)" run --profile all --no-progress --force
```

### Optional (falls verfügbar, noch aussagekräftiger — nativer Stack inkl. C-Frames):

```powershell
# Im zweiten Terminal während eines normal hängenden Laufs:
uv run --with py-spy py-spy dump --pid <PID-des-hängenden-python-Prozesses>
```

**Hinweis:** Nach einem Sonden-Abbruch können `mutants/` und Lock-Reste zurückbleiben — der nächste Lauf mit `--force` räumt das (euer beobachteter transienter „files in use?"-Fall kann dabei auftreten; einfach erneut starten).

---

## 3. Fragenkatalog (bitte mit den Stack-Dumps beantworten)

| # | Frage | Warum wir das brauchen | Erfassung |
|---|---|---|---|
| 1 | **Größe und Dateianzahl des Venv** (`.venv`): Dateien + Bytes | Der Basis-Walk hasht **jede Datei jeder installierten Distribution**. Referenz: 2.174 Dateien/40 MB ≈ 13 s Stille. Ein Riesen-Venv (oder eines mit 100k+ Dateien) wäre Kandidat Nr. 1 für einen gebundenen, aber endlos langen Silent-Walk. | `(Get-ChildItem .venv -Recurse -File \| Measure-Object -Property Length -Sum) \| Select Count, Sum` |
| 2 | **Defender/AV**: Real-Time-Protection aktiv? Ausschlüsse für Projekt/Venv/`%TEMP%`? Drittanbieter-AV/EDR außer Defender? | Der Walk macht **zwei Opens + Stat + Replace pro Datei**. AV-Filter-Overhead pro Open multipliziert über Zehntausende Dateien. | `Get-MpPreference \| Select -Expand ExclusionPath` + Angabe installsicherer AV-Produkte |
| 3 | **Liegende Speicherorte**: Stehen Projekt, `.venv` oder `%TEMP%` unter OneDrive/Dropbox/anderem Cloud-Sync, auf einem Netzlaufwerk oder unter Roaming-Profil? BitLocker mit Software-Verschlüsselung? | Cloud-Placeholder- und Filter-Treiber können dateiintensive Walks pathologisch verlangsamen bzw. verändern. | Kurze Angabe der Pfade (Projekt/Venv/TEMP) + Sync-Tool ja/nein |
| 4 | **CPU-Verlauf des hängenden Prozesses**: Zwei `Get-Process`-Stichproben 60 s apart während des Hängers — steigt CPU further (~60 s/60 s = Spin) oder kaum (~5 s/60 s = IO-Block)? | Euer Bericht sagt 100 % eines Kerns; die Unterscheidung Spin vs. Block entscheidet über die Ursachenklasse. | `Get-Process python \| Select Id,CPU` (2×, 60 s Abstand) |
| 5 | **Gibt es während des Hängers Kind-Prozesse** (weitere python.exe)? Erwartet: **keine** (vor dem Profil-Hint wird nichts gespawnt). | Falls doch Kind-Prozesse existieren, ist unsere Zonen-Analyse auf eurer Maschine zu erweitern. | `Get-CimInstance Win32_Process -Filter "Name='python.exe'" \| Select ProcessId,ParentProcessId,CommandLine` |
| 6 | **pyproject des Projekts**: komplette `[tool.uv]`/`[tool.mutmut]`-Sektion + `uv.lock`-Größe + Anzahl `[[package]]`-Einträge | Abhängigkeits universum → erwartete Venv-Größe; außerdem ob `--all-extras`/`--dev`-Gruppen große Pakete ziehen. | `Select-String -Path uv.lock -Pattern '^\[\[package\]\]' \| Measure-Object` |
| 7 | **Stack-Dumps** aus Sonde (run1 + run2) | Beweisführung der exakten Stelle | `hang-stack-run1.txt`, `hang-stack-run2.txt` |

---

## 4. Rückgabeformat

Bitte zurück an PO pgm1980 → mutmut-win-Team:

1. `hang-stack-run1.txt` + `hang-stack-run2.txt` (vollständig)
2. Antworten zu Fragen 1–6 (Tabelle genügt)
3. Falls vorhanden: py-spy-Dump

Mit dem Stack ist die Ursache in einem Schritt bewiesen; Fix und Regressionstest folgen auf unserer Seite unmittelbar.

---

## 5. Erwartetes Referenzverhalten (gesunde Maschine, zum Vergleich)

```
[probe t=0.000s] invoking: mutmut-win run --profile all --max-children 2 --no-progress --force
Removed mutants/
Removed .mutmut-cache/
              (≈13–25 s Stille — normal: Basis-Fingerprint)   <- EURE HÄNGEZONE
profile=all — 41 operators active
     also copying tests/
     also copying pyproject.toml
Collecting coverage data (mutate_only_covered_lines is enabled)…
Configuration changed — regenerating all mutants.
Running clean test suite…
Collecting test timing statistics…
Collected 4 test-to-mutant mappings across 4 tests.
Running forced-fail verification…
Timeout budgets: …
--- Mutation Testing Summary ---
…
```

*Sollte euer Lauf bis „profile=…" durchkommen und DANACH hängen, ist das ein anderes Bild als im Bug-Report beschrieben — bitte dann ebenfalls die Stacks mitschicken; der Fragekatalog gilt unverändert.*
