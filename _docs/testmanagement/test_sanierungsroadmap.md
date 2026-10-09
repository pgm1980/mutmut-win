# Test-Sanierungsroadmap — Wellen W0 bis W5

**Status: FREIGEGEBEN durch PO am 2026-10-06 (Auflagen: Testspezifikation §13.2).**
Basis: [Testspezifikation v2](test_specification.md).
Rahmen (E-4): Sprint 47, Branch `fix/v3.1.0-testsanierung`, Versionsziel **3.1.0**,
gewohnte Disziplin (Issue mit Wellen-Checklisten, `.sprint/state.md`, Baseline-Gates,
Vollsuite-Receipt, Conventional Commits, keine Gate-Abschwächung).

## Zielbild

Aus 97 % Unit-Schwergewicht (52,9 % gemockt, 0 % E2E) wird eine getragene Pyramide mit
vier Dächern: Unit → Integration → Produkt-E2E → **Selbst-Mutation**. Abnahme über
Szenario-Vollständigkeit (TM-01 bis TM-12) und Kill-Rate (≥ 80 %, Pilotmodule
suspended_spawn 34,8 % und db 24,3 %) — nicht über Prozentquoten (E-1).

## Wellenübersicht

| Welle | Inhalt | Pakete | TM-Familien | Umfang (Richtung) | Vorbedingung |
|---|---|---|---|---:|---|
| **W0** | Enabler-TDD: #194, #195, M-097 | T0 | TM-09, TM-10 | 25–35 Fälle | keine |
| **W1** | E2E-Rückgrat | T1, T2, T8 | TM-01, TM-06, TM-08, TM-11 | 30–50 Fälle | W0 (für Resume-Szenarien) |
| **W2** | Windows-FS- & Prozesskorridore | T3, T4 | TM-02, TM-03, TM-04 | 50–80 Fälle | keine (parallel zu W1 möglich) |
| **W3** | Property-Ausbau | T5 | TM-05 (+ Querschnitt) | 60–80 Fälle | keine |
| **W4** | Architekturverträge | T6 | Querschnitt | 30–50 Fälle | keine |
| **W5** | Wheel-Grenze + Kill-Rate-Kampagnen | T9 + Abnahme | TM-12 + §6.2 | 10–15 Fälle + 2 Kampagnen | **W0 zwingend**, W1–W4 bevorzugt |

Integration und E2E sind der Schwerpunkt der Sanierung (PO-Auflage §13.2.4): viele
sinnvolle echte Integrationstests, viele sinnvolle echte E2E-Tests.

## W0 — Enabler-TDD: Engine-Defekte als Rot-Beweise

**Prinzip:** Die neuen Szenario-Tests *sind* die Rot-Beweise der offenen Engine-Defekte.
Defektsanierung und Testaufbau in einem Aufwasch.

1. **TM-09 (Issue #195 — kein Cross-Run-Verdikt-Cache):**
   - Test rot: Run gegen Fixture → harter Abbruch im Dispatch → Neustart mit
     identischem tests-dir/HEAD → heute werden alle Verdikte neu gerechnet.
   - Fix: stabiler `tests_fingerprint` (tests-dir-Inhalt + HEAD), Verdikt-Wiederverwendung
     über Run-Grenzen mit Cache-Hit-Beleg.
   - **Pflicht-Gegenprobe:** abweichender tests-dir oder HEAD hebt den Cache korrekt auf
     (falsche Wiederverwendung wäre schlimmer als keine).
2. **TM-10 (Issue #194 — Forced-Fail-Hang):**
   - Test rot: Forced-Fail mit hängender Import-Phase/Retry-Loop unter Fail-Sentinel
     (Repro-Muster: test_duplicate_definitions_220.py) terminiert nicht konfigurierbar.
   - Fix: phasenscharfe Timeouts; Hänger werden als Timeout diagnostiziert und
     abgebrochen, nicht als Kill gewertet; Fehlermeldung nennt die Ursache.
3. **M-097 (deferred aus R3):** Refactor der `load_current_run`/`load_results`-Signaturen,
   rot/grün nachgewiesen; Ledger-Zeile OFFEN → IMPLEMENTIERT+VERIFIZIERT.

**Abnahme:** TM-09/TM-10 grün; Issues #194/#195 mit Fix-Receipts schließbar; M-097 im
Ledger erledigt; Vollsuite grün; Gates gemäß Testspezifikation §10.
**Risiko:** #195-Fix muss Cache-Identität exakt definieren → Negativfälle sind
Abnahmekriterium, nicht optional.

## W1 — E2E-Rückgrat (T1, T2, T8)

1. **`tests/e2e/test_full_run.py` (T1):** kompletter `mutmut-win run` gegen die
   bestehenden Fixture-Projekte (simple_lib, my_lib, py3_14_features, source_layout,
   config, mutate_only_covered_lines) — parametrisiert, wo der Vertrag identisch ist.
   Geprüft: Exit-Code, DB-Status terminal, Score unabhängig nachgerechnet,
   CI/CD-Export nur bei qualifizierter Basis. Benennung: `Run-E2E`.
2. **`tests/e2e/test_error_paths.py` (T2):** fehlende Tests, korrupte Cache-DB,
   unterbrochener Lauf (nutzt W0: Resume nach Abbruch = `Campaign-E2E`), ungeeignetes
   Timeout. Negativkontrollen belegen Abweisung, nicht Produktablauf.
3. **`tests/e2e/test_class_heavy_projects.py` (T8, TM-11):** neue Fixture mit
   pydantic-`BaseModel`/`@computed_field` und Textual-App. Spiegelvergleich
   (untrampoliniert grün ↔ trampoliniert aktuell rot, 68-fache Verlangsamung) als
   **`xfail(strict=True)`** mit gesichertem Repro (BLOCKED-GATES-MODELS-BROWSER.md,
   glm-followup-Korpus). **Kein Vorab-Fix** — H1–H4 sind dem externen adversarialen
   Review vorbehalten; xfail macht die Grenze sichtbar und scheitert automatisch,
   sobald sich etwas ändert.

**Abnahme:** TM-01/06/08-Teilfälle grün; TM-11-xfail dokumentiert; Fallinventar nach
Zählregeln.
**Bug-Hunting-Erwartung:** hoch (Resume-, Finalisierungs-, Export-Pfad).

## W2 — Windows-FS- & Prozesskorridore (T3, T4)

1. **`tests/integration/test_windows_fs_contracts.py` (T3):** Junction-Anlage und
   -Abwehr, Hardlink-Identität, Readonly-Entfernung, Sharing-Violation-Retry,
   NTFS-Normcase-Identität, Deletion-Sync, Gitignore-Boundary. Echtes NTFS, echte
   Temphierarchien (M-146-Lebenszyklus).
2. **`tests/integration/test_process_lifecycle.py` (T4):** Jobhandle-/Pipe-/
   Runtime-Root-Freigabe über den echten Prozessbaum (Job Object), Ctrl-C in jeder
   Phase (Exit 130), Pool-Kollaps-Recovery, Shutdown-Fenster.

**Abnahme:** TM-02/03/04-Teilfälle grün; Ressourcenbeobachtung über den gesamten
Baum (Regel 4.6), nicht nur Kindprozesse.
**Hinweis:** Korridore, die die Pilotmodule abdecken, fließen zusätzlich als
Contract-Tests in deren `--tests-dir` ein (Vorbereitung der W5-Kampagnen).

## W3 — Property-Ausbau (T5)

- `tests/unit/properties/strategies.py` (Pfade, Exit-Codes, Mutant-Namen,
  Stat-Ergebnisse, Cache-Snapshots) mit Round-Trip-Sicherung je Strategy.
- ≥ 60 neue `@given`-Tests: Serialisierung (Cache/JSON/TOML), **Fingerprint-Stabilität**
  (Anknüpfung an #195: identische Eingaben → identischer Fingerprint, über Spektren),
  Normcase/Pfade, Timeout-Modell, Score-Arithmetik gegen unabhängige Referenz.
- Hypothesis-Profile: `ci` (schnell) und `nightly` (ausführlich); Beispiele zählen nicht
  als Fälle (Zählregel §2.3).

**Abnahme:** TM-05 vollständig; Properties laufen in beiden Profilen grün.

## W4 — Architekturverträge (T6)

- **CLI-Exit-Code-Vertrag:** parametrisierte Tabelle jeder CLI-Fehlerklasse auf den
  dokumentierten Exit-Code (Issue-#130-Klassen, RunLock-Fehlertaxonomie M-093).
- **JSON-Export-Schema:** CI/CD-Export gegen jsonschema validiert.
- **Konfigurations-Schema:** ungültige Werte bekannter Optionen und ungültige
  Kombinationen werden vor dem Staging mit Exit 2 abgewiesen. Unbekannte
  Schlüssel werden mit Warnung auf stderr ignoriert; sie sind kein
  Ablehnungsfall. Die Warnung und die erfolgreiche Fortsetzung benötigen
  getrennte Assertions. Siehe [GAP-1-Vertragskorrektur S3-038](config_contract_s3.md).
- **Schreibpfad-Vertrag:** kein raw `open()` in Engine-Modulen — mit dokumentierter
  **Ausnahmeliste** (der erzwungene Forced-Fail-Beweis nach M-130-fix schreibt bewusst
  untrampoliert; die Ausnahme ist Teil des Vertrags, keine Schwächung).

**Abnahme:** Verträge als eigene Suite (`-m architecture`) grün; jede historische
Befundklasse (fail-closed, Fehlerkanal, Exit-Code, atomarer Schreibpfad) hat
mindestens einen Guard-Test.

## W5 — Wheel-Grenze + Kill-Rate-Kampagnen (T9 + Gesamtabnahme)

1. **`tests/e2e/test_wheel_install.py` (T9, TM-12):** gebautes Wheel in isoliertem Venv
   außerhalb des Checkout installieren; Run-E2E gegen Fixture; Herkunft und Bytes aller
   importierten mutmut_win-Module gegen das Wheel prüfen; beschädigte Inputs abgewiesen.
2. **Kill-Rate-Kampagne suspended_spawn (Pflicht):** Modul-Gate mit erweitertem
   Contract-Tests-dir (W2-Korridore); Ziel ≥ 80 % oder dokumentierter
   Adjudizierungs-Korridor. Umfang 279 Mutanten ≈ 2–4 h.
3. **Kill-Rate-Kampagne db (nachrangig, PO-Abstimmung):** 2.622 Mutanten ≈ 20–24 h
   Wandzeit bei ~2 Verdikten/min — dank W0/#195 mit Abbruch-Überlebensfähigkeit.
   Durchführung als detached Overnight-Kampagne (Betriebsregeln §10).

**Abnahme:** TM-12 grün; Pilot-Kill-Raten gemäß §6.2; Kampagnen-Receipts archiviert.

## Gesamtabnahme des Programms (3.1.0)

1. Szenario-Matrix TM-01 bis TM-12 vollständig (Test oder benannte fehlende Voraussetzung).
2. Kill-Rate-Pilotmodule ≥ 80 % bzw. adjudiziert; Kampagnen-Receipts archiviert.
3. Vollsuite grün auf Finalstand; Release nach gewohntem Muster (PR, annotierter Tag,
   GitHub-Release, Housekeeping, Vollsuite-Receipt).
4. Issues #194/#195 geschlossen; M-097 erledigt; neue M-IDs aus Testwellen im Ledger;
   AR27/Evidenz-Korpus aktualisiert.
5. **Übergabe an externen adversarialen Multi-Agenten-Review** (GPT-6 Astra / Fable 5.1)
   mit Prüfaufträgen H1–H4 und E-A bis E-F — die Testsanierung liefert diesem Review die
   Reproduktions- und Messbasis (TM-11-xfail, Kill-Raten, Fallinventare).

## Querschnittsregeln (jede Welle)

- **Vorab:** Baseline-Gates (ruff/format/mypy/lint-imports/pytest) grün; Conventional
  Commits mit `[Wx]`- und `[M-xxx]`-Tags.
- **Serena-Pflicht (PO-Auflage):** Alle Code-Analyse und Implementierung erfolgt
  über Serena (serena-mutmut-win) — Navigation über Symbole, Edits und Refactorings
  über Serena-Werkzeuge. Kein Grep für Symbole, kein blindes Zeilen-Editieren.
- **Enabler-TDP-Verallgemeinert (PO-Auflage):** Jede/r neue Test muss Nachweiskraft
  besitzen (unabhängiges Orakel, potentiell rot — Regel 4.14). Kein Fix ohne roten
  Test; bereits gefixte Gruppen werden durch die neuen Tests verhaltensseitig
  nachgeschärft, nicht als gegeben vorausgesetzt.
- **Keine Test-Löschung (PO-Auflage):** Bestehende Tests bleiben (Regel 4.13);
  Nachweis-Pflicht statt Quotengerade.
- **Während:** Produktfehler → neue M-ID (Regel 4.11); keine Assertion-Abschwächung;
  Tests räumen auf (P-13).
- **Nachher:** Fallinventar (Zählregeln §2.3), echte Laufbelege, offene Grenzen,
  Vollsuite grün, Rückmeldung nach R3-Muster (Verifikationsergebnisse, Commits, Gates).

## Aufwands-Richtungswert

W0: 1–2 Tage · W1: 2–3 Tage · W2: 2–4 Tage · W3: 1–2 Tage · W4: 1–2 Tage ·
W5: 2–4 Tage (inkl. Kampagnen; db-Kampagne ggf. als Overnight-Detached-Lauf) —
gesamt ≈ 9–17 Arbeitstage. Schätzwerte ohne Quotencharakter; maßgeblich sind die
Abnahmekriterien der Testspezifikation §6.
