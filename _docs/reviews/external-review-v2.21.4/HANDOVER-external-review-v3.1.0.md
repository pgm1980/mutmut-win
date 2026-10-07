# Übergabe externes Review — mutmut-win v3.1.0 (Testsanierung)

**Stand:** 2026-10-07 · **Release:** v3.1.0 · **Branch:** `fix/v3.1.0-testsanierung` → `main`
**Auftraggeber:** PO · **Review-Ziel:** Adversariale Prüfung der Engine-Grenzen, die intern NICHT vorab gefixt wurden

---

## 1. Review-Scope (bewusst OFFEN gelassen)

Die folgenden Punkte sind **bewusst nicht vorab behoben** worden. Sie sind der
Gegenstand dieses Reviews. Erwartet wird eine Differenzialdiagnose mit
Entscheidung: Engine-Grenze dokumentieren ODER Produkt-Bug fixen.

### H1: Trampolin-Generator vs. klassenlastige Module (pydantic/Textual)

**Symptom:** Trampolinierte Version von `mutmut_win/models.py` bricht
`tests/unit/test_file_setup.py` vollständig (136/140 FAILED), trampoliniertes
`mutmut_win/browser.py` bricht `tests/unit/test_browser_diff.py` (20/20 FAILED).
Ohne Trampolin laufen exakt dieselben Tests spiegelbildlich grün (H5-Refutation
2026-10-05, Gate-Worktree `9592ab7`). Verlangsamung ~68× im Failure-Fall.

**Offene Frage:** Kann der Trampolin-Generator pydantic `BaseModel`-Subklassen,
`@computed_field` und Textual-App-Klassen grundsätzlich verarbeiten (H1), oder
liegt ein Wechselswirkungsdefekt mit konkreten R3/R2-Änderungen vor (H2/H3)?

**Prüfvorschlag:**
1. `mutmut_win run` mit `paths_to_mutate=["src/mutmut_win/models.py"]` isoliert
   gegen eine dedizierte, kleine Testdatei (nicht die gesamte Staging-Pipeline).
2. Generierten Trampolin-Code inspizieren (`mutants/`-Staging): syntaktisch
   korrekt? Klassen-Body erhalten? Dispatch-Hülle um Methoden?
3. Pre-R3-Stand von models.py trampolinieren (git revert auf M-121/M-123) und
   vergleichen → H2 widerlegen/bestätigen.

### H2: models.py unter Trampolin — M-121/M-123-Wechselswirkung

M-121 (normalisierte Digests, dict-comprehension-Return) und M-123
(`_is_finite_real`) sind fokussiert rot-grün verifiziert, aber das Modul-Gate
ist BLOCKED. Ein Vorher-Nachher-Vergleich unter Trampolinierung fehlt.

### H3: browser.py unter Trampolin — M-117–M-120-Wechselswirkung

M-119 fügte `threading.Condition`, `_DiffRequest`, `on_unmount` hinzu.
Textual-Apps wurden vor R3 nie trampoliniert — keine Baseline.

### H4: Tests-dir-Wahl für Modul-Gates

`test_file_setup.py` testet die gesamte Staging-Pipeline, nicht nur
models-Funktionen. Bei funktionsbasierten Modulen funktioniert die Methode;
bei klassenlastigen ist die Testdatei-Wahl möglicherweise ungeeignet.
Vorschlag: dedizierte `test_models_*.py`/`test_browser_unit_*.py` als Gate-Tests.

### H5: Produkt-Bug in R3-Änderungen — BEREITS WIDERLEGT (2026-10-05)

Ohne Trampolin: 136 passed / 20 passed (spiegelbildlich zu den Failures).
R3-Produktcode ist entlastet. Kein Handlungsbedarf.

---

## 2. Kill-Rate-Korridore (dokumentierte Äquivalenz-Mutanten)

| Modul | Mutanten | Kill-Rate | Korridor | Receipt |
|---|---:|---:|---|---|
| trampoline | 141 | 66,7 % roh / 93,6 % adjudiziert | gesund | `killrate-trampoline.log` |
| suspended_spawn | 279 | 34,8 % | Äquivalenz (Windows-API-Nähe) | `killrate-suspended_spawn.log` |
| db | 2.989 | 16,4 % | Äquivalenz (SQL-Schema-Boilerplate) | `killrate-db-v3.log` |

**Behauptung (zu prüfen):** Die niedrigen Raten von suspended_spawn/db beruhen
auf Äquivalenz-Mutanten, nicht auf Blindheit der Test-Suite. Stichproben-Adjudikation
des Reviews willkommen: zufällige Survivors ziehen, manual prüfen, ob ein
Verhaltensexistenz-Test überhaupt möglich ist.

**Reproduktion (M-149b shared pycache, ~35 min für db):**
```powershell
cd <gate-worktree>
$env:UV_PROJECT_ENVIRONMENT = "$env:TEMP\opencode\testsanierung-venv"
uv run --no-sync mutmut_win run --paths-to-mutate src/mutmut_win/db.py --no-progress
```
(Ohne M-149b: ~31 h geschätzt für db.)

---

## 3. Was v3.1.0 liefert (Kontext für das Review)

- **119 M-Fixes** (M-005–M-149b), 23+ Commits auf `fix/v3.1.0-testsanierung`
- **Test-Pyramide sanierung:** 0→25 E2E, neue Integration-Tier (~30 Fälle),
  60 @given-Property-Tests, 87 Architektur-Verträge
- **Gap-Closure GAP-1–7** (32 neue Fälle): Config-Fail-Closed, Atomic-Crash-Recovery,
  Mutation-Operator-Korrektheit, Staging-Drift, Browser-Diff, Lock-Konkurrenz,
  Interrupt-Finalisierung
- **M-149/M-149b:** Shared pycache (Phasen + Worker), ~50× Dispatch-Beschleunigung,
  Isolation bewiesen (simple_lib: 14/14 killed mit shared pycache)
- **M-147 (#195):** Cross-Run-Verdikt-Cache mit kuratierter Env-Basis
- **M-148 (#194):** Forced-Fail-Liveness mit Faulthandler-Frame-Diagnose
- **Vollsuite:** 3.826+ passed / 0 failed / 45 skipped (dokumentiert), Finalstand-Receipt
  in `_docs/testmanagement/` bzw. Evidence-Dir

## 4. Evidence-Map

| Was | Wo |
|---|---|
| Vollsuite-/Gate-Receipts | `C:\Users\pmitt\Documents\Codex\reviews\mutmut-win-r2-2026-10-01\glm-followup\evidence\` |
| Master-Ledger (146 M-Gruppen) | `...\glm-followup\R0-R4-MASTER-LEDGER.md` |
| Gate-Matrix | `...\glm-followup\AR27-GATE-MATRIX.md` |
| H1–H5-Differenzialdiagnose | `...\glm-followup\BLOCKED-GATES-MODELS-BROWSER.md` |
| Review-Berichte (Claude/Astra) | `_docs/reviews/` (15 Dateien) |
| Testspezifikation v2 | `_docs/testmanagement/test_specification.md` |
| Sanierungsroadmap | `_docs/testmanagement/test_sanierungsroadmap.md` |
| GAP-Receipts (GAP-1–7) | `...\evidence\gap{1..7}*.log` |

## 5. Offene Issues (nicht Release-blockierend)

- **#193:** Generation-Fingerprint ohne Engine-Version (Q-60) — Konzept offen
- **#198:** Wird mit v3.1.0-Release geschlossen

## 6. Erwartete Review-Ergebnisse

1. **H1–H4-Entscheid** je Hypothese: Grenze dokumentieren ODER Bug-Ticket mit Reproducer
2. **Adjudizierung** der Kill-Rate-Korridore (Stichprobe ≥20 Survivors je Modul)
3. **Blind-Spot-Scan** der GAP-1–7-Tests: Welche M-Fixes sind immer noch nur dünn abgedeckt?
4. **Urteil:** Ist die Test-Pyramide belastbar genug für die 3.1.0-Abnahme?

---

*Erstellt im Rahmen der v3.1.0-Testsanierung (Sprint 47, Issue #198).*
