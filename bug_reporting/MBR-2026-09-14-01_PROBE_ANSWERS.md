# PROBE-ANTWORTEN — MBR-2026-09-14-01 (Run-Startup-Hänger, mutmut-win 2.21.2)

**An:** mutmut-win-Entwicklung (via PO pgm1980)
**Von:** GLM-5.3 (OpenCode Agent), Projekt `lean4_lsp-mcp-server`
**Bezug:** `MBR-2026-09-14-01_PROBE_HANDOVER.md` (Sonde + Fragenkatalog)
**Datum:** 2026-09-14
**Ergebnis in einem Satz:** **Ursache gefunden und experimentell bewiesen — kein Deadlock, sondern ein endlos langsamer Walk über `tests/test_project/.lake` (120.065 Dateien / 6,53 GB), der vom Projektbaum-Hash und vom Staging-Namespace-Walk nicht ausgeschlossen wird (`.gitignore` wird nicht respektiert), massiv verstärkt durch eine zeitgleich laufende zweite mutmut-win-Instanz auf einem anderen Projekt (~50 Prozesse).**

---

## 1. Rückgabegegenstände

| Gegenstand | Status |
|---|---|
| `hang-stack-run1.txt` (Probe-Timeout 150 s) | ✅ liegt im Projekt-Root |
| `hang-stack-run2.txt` (Probe-Timeout 300 s) | ✅ liegt im Projekt-Root |
| `hang-stack-run3.txt` (**Bestätigungsexperiment**, `.lake` außerhalb des Projektbaums, 240 s) | ✅ liegt im Projekt-Root |
| py-spy-Dump | entbehrlich — Beweisführung über die drei Faulthandler-Dumps abgeschlossen |

## 2. Fragenkatalog (Abschnitt 3 des Handovers)

| # | Frage | Antwort |
|---|---|---|
| 1 | Venv-Größe | **7.766 Dateien / 179 MB** (Referenzskalierung eurer Messung: ≈ 45–50 s Stille — erklärt **nicht** 15–60 min) |
| 2 | Defender/AV | Real-Time-Protection **aktiv**; Exclusions nicht abrufbar (nicht-erhöhte Shell: „Must be an administrator to view exclusions"); Drittanbieter-AV: keine Anzeichen (nur Defender) |
| 3 | Speicherorte | Projekt `C:\claude_codex\mcp_server\lean4-lsp-mcp-server` (lokale NVMe), TEMP lokal unter `C:\Users\pmitt\AppData\Local\Temp`; **kein** OneDrive/Dropbox-Prozess aktiv; kein Netzlaufwerk |
| 4 | CPU-Verlauf des Hängers | Sondenprozess PID 24944: t=60 s → 47,5 CPU-s; t=120 s → 95,84 CPU-s (**Δ ≈ 48 CPU-s / 60 s ≈ 80 % eines Kerns**) → **busy, nicht IO-blockiert** (rein passives Warten hätte Δ≈0); deckelt mit der früheren Beobachtung (89,6 CPU-s / 90 s) |
| 5 | Kind-Prozesse während des Hängers | Vom Sondenprozess: **keine** (wie vorhergesagt — vor dem Profil-Hint wird nichts gespawnt). **ABER:** ~50 fremde python.exe einer **zeitgleich laufenden zweiten mutmut-win-Instanz** (`C:\claude_codex\mosaic`, `--max-children 6`, inkl. ~24 multiprocessing-spawn-Children + zahlreicher pytest-Worker) — das ist die vom PO erwähnte „andere GLM-5.3-Instanz ohne Hänger" |
| 6 | pyproject/uv.lock | `[tool.mutmut]`: siehe Bug-Report 3.1 (unverändert); `uv.lock` 239 KB / **94 Pakete** — moderates Universum, keine Riesen-Extras |

## 3. Framedifferenzierung (eure Entscheidungsmatrix)

| Lauf | Probe-Timeout | Innerster Frame | Phase |
|---|---|---|---|
| run1 | 150 s | `pathlib.is_dir` ← `file_setup.py:791 validate_staging_namespace` ← `cli.py:646` | Staging-Namespace-Walk |
| run2 | 300 s | `pathlib.open` ← `stats.py:422 _hash_context_file` ← `stats.py:609 _hash_context_tree` ← `stats.py:1250 _build_stats_context_evidence` ← `orchestrator.py:330` | **Basis-Fingerprint** (eure Verdachtszone — bestätigt, aber siehe Ursache) |

**Unterschiedliche Frames → „endlos langsamer, fortschreitender Walk"** — exakt eure zweite Kategorie. Kein Deadlock, keine Spin-Schleife fester Stelle.

## 4. Bestätigungsexperiment (run3) — Ursache bewiesen

`tests/test_project/.lake` (**120.065 Dateien / 6,53 GB**, gebautes Mathlib-Projekt, **korrekt in `.gitignore`**) wurde **komplette aus dem Projektbaum** verschoben (nach `C:\claude_codex\_lake_park`, also außerhalb von Projekt UND `tests/`), dann identischer Sondenlauf (240 s):

```
[probe t=0.000s] invoking: mutmut-win run --profile all --max-children 6 --no-progress --force
profile=all — 41 operators active          ← in SEKUNDEN erreicht (in allen bisherigen Läufen NIE zu sehen)
     also copying tests/
     also copying pyproject.toml
     also copying .gitignore
Collecting coverage data (mutate_only_covered_lines is enabled)…
Timeout (0:04:00)!                          ← spätere Phase (Coverage-Collect), KEIN Startup-Hänger mehr
```

**Schlussfolgerung:** Der Startup-„Hänger" ist die Kombination aus

1. **Primärursache:** `_build_stats_context_evidence`/`_hash_context_tree` (Projektbaum-Hash) **und** `validate_staging_namespace` (Staging-Input-Walk über das Default-`also_copy`-Root `tests/`) laufen über die 120k-Dateien/6,5-GB-`.lake`-Baum — `.gitignore` wird von beiden nicht respektiert. 6,5 GB File-open+hash in reinem Python, jedes Open durch Defender-Realtime-Filter = viele Minuten „stille Zone" (konsistent mit dem einzigen historischen Durchläufer: 35,6 min bis zur Clean-Suite, ohne mosaic-Konkurrenz).
2. **Verstärker:** die konkurrente mosaic-Instanz (50 Prozesse) hat die letzten Läufe zusätzlich verlangsamt.

## 5. Korrektur unseres Bug-Reports (Ehrlichkeitshalber)

Unser früherer „`.lake`-Ausstash-Test" (Bug-Report 3.5: „Staging-Kosten als Ursache ausgeschlossen") war **methodisch invalide**: Der Baum wurde nach `tests/_lake_stash` verschoben — **bleibt innerhalb des gewalkten `tests/`-Roots**. Die Aussage „Staging ausgeschlossen" wird hiermit **zurückgezogen**; run3 ist der gültige Gegenbeweis. Eure Widerlegung von H1–H4 bleibt unverändert richtig — es war nie die Config.

## 6. Empfehlungen

**Eure Seite** (verstärkt den bisherigen „Nebenbefund B" zum Hauptbefund):
1. Projektbaum-Hash (`_build_stats_context_evidence`) und Staging-Walk (`validate_staging_namespace`, `also_copy`-Default) sollten `.gitignore` respektieren oder einen Ausschluss-Mechanismus (`do_not_copy`/`do_not_hash`, Glob) bekommen.
2. Unabhängig davon: Ein Fortschritts-Output in dieser Zone („hashing project tree: n Dateien / X s") hätte die Diagnose von Wochen auf Minuten verkürzt — eure Abschnitt-8-Empfehlung gilt doppelt.

**Unsere Seite (Workaround bis zum Fix):** `.lake` vor Mutation-Läufen außerhalb des Projektbaums parken (bewiesenermaßen wirksam, run3). Wir werden das als dokumentierten Prozessschritt führen.

---

*Durchgeführt von GLM-5.3 (OpenCode) am 2026-09-14; alle Dumps Erste-Hand-Aufzeichnungen dieser Session.*
