# mutmut-win Testspezifikation — v2

**Status: FREIGEGEBEN durch PO am 2026-10-06 (mit vier Auflagen, §13.1).** Ersetzt die
v1 vom 2026-10-04. Umsetzung: GLM-5.3.

Stand: 2026-10-06. Auftraggeber: PO.
Ausgangsstand: `b0c8a10` (main, v3.0.0 released); Sprint-Basis `fix/v3.1.0-testsanierung`.
Grundlagen: Test-Pyramiden-Analyse 2026-10-04 · Modul-Gate-Kampagne 2026-10-05
(AR27-GATE-MATRIX.md §7, glm-followup-Korpus) · MOSAIC-Testspezifikation 2026-10-04
(strukturelle Vorlage, überarbeitete Fassung mit Wellenlebenszyklus).

## 1. Ziel und Geltungsbereich

Diese Spezifikation regelt die Sanierung der Testpyramide von mutmut-win. Sie gilt für
alle ausführbaren Engine-, Staging-, Prozess- und CLI-Pfade. Sie ergänzt die bestehende
Suite; bestehende Tests werden nicht gelöscht (§4.13) und keine bestehende Assertion
abgeschwächt.

Tests müssen Fehler über Modulgrenzen erkennen, Windows-Dateisystem- und
Prozessspezifika gegen echte Betriebssysteminteraktionen prüfen und fachliche Verträge
gegen unabhängig abgeleitete Erwartungen sichern. Eine hohe Testanzahl, Zeilenabdeckung
oder erfolgreiche Mock-Serialisierung allein genügt nicht.

Führende Produktnormen:

- [README](../../README.md): Operating Profile, Mutation-surface limits, Release policy.
- [Architecture](../architecture/adr_layer_contracts_v2.md): Fünf-Band-Schichtenarchitektur.
- R0-R4-Master-Ledger (146 Defektgruppen; Anhang 2026-10-05, dokumentierte
  Freigabe-Abweichung) — glm-followup-Korpus.
- AR27-GATE-MATRIX §7 (Modul-Gate-Endstand, Engine-Erkenntnisse E-A bis E-F) —
  glm-followup-Korpus.
- BLOCKED-GATES-MODELS-BROWSER (Trampolin-Grenze klassenlastiger Module; Hypothesen
  H1–H4) — glm-followup-Korpus, externes Review.
- [Test-Sanierungsroadmap](test_sanierungsroadmap.md): Wellen W0–W5.

## 2. Ausgangslage und Zählweise

### 2.1 Bestand

Die Release-Vollsuite 2026-10-05 (Receipt `evidence/vollsuite-r3-final.log`,
glm-followup) enthält **3.713 Collection-Fälle** (3.668 passed / 44 skipped / 1 failed
→ M-112-fix). Typbezogene Klassifikation der Pyramiden-Analyse 2026-10-04 (Anteile
seitdem unverändert; Nachzählung nach jeder Welle):

| Testtyp | Fälle | Anteil |
|---|---:|---:|
| Unit (gemockt) — MagicMock, @patch | 1.627 | 52,9 % |
| Unit (pur) — keine Mocks | 586 | 19,0 % |
| Subprocess-Tests — echte Prozesse in unit/ | 491 | 16,0 % |
| Property (parametrisiert) — @parametrize | 179 | 5,8 % |
| Integration (echtes FS) — NTFS, Junctions | 165 | 5,4 % |
| Property (Hypothesis) — @given | 79 | 2,6 % |
| Architektur — Supply Chain, Import-Linter | 35 | 1,1 % |
| **E2E** | **0** | **0 %** |

### 2.2 Zweite Messbasis: Kill-Raten der Modul-Gate-Kampagne

Ein überlebender Mutant ist eine Verhaltensänderung, die die Suite nicht erkennt. Die
Kampagne 2026-10-05 quantifiziert die Testblindheit:

| Modul-Gate | Kill-Rate | Bewertung |
|---|---:|---|
| output_capture (178 Mutanten) | 57,3 % | unter P-04-Standard (≥ 80 %) |
| suspended_spawn (279) | 34,8 % | schwach — Pilotmodul |
| trampoline (141) | 66,7 % raw / ~93,6 % adjudiziert | ok nach Adjudizierung |
| db (2.622; Teildaten 288) | 24,3 % | schwach — Pilotmodul |
| run_lock (1.333; abgebrochen bei 981) | 57 % (Teildaten) | unter Standard |
| models / browser | BLOCKED | Trampolin-Grenze; H1–H4 offen |

### 2.3 Zählregeln (verbindlich für alle Berichte)

1. Parametrisierungen zählen als Fälle; intern erzeugte Hypothesis-Beispiele erhöhen
   die Fallzahl nicht.
2. Architekturprüfungen werden separat gezählt, auch wenn ihr pytest-Marker
   `integration` ist.
3. Ablagequoten sind nicht Anteile tatsächlich isolierter Tests (in `tests/unit/`
   leben 437 Subprocess-Tests, die faktisch Integrationstests sind).
4. Ebenen und Methoden werden getrennt ausgewiesen; Property Testing ist eine Methode
   auf mehreren Ebenen.

## 3. Testarchitektur

| Ebene | Prüfumfang | Einsatz |
|---|---|---|
| Unit (pur) | Lokaler Vertrag, Algebra, Validierung, Grenzen | Schnelle breite Basis |
| Unit (gemockt) | Modulgrenzen mit kontrollierten Abhängigkeiten | Nur für echte externe Schnittstellen |
| Property | Invarianten über Eingabespektren (Hypothesis, Parametrize) | Systematische Grenzfall- und Fehlerinjektion |
| Integration | Mehrere echte Produktionsmodule, echtes NTFS, echte Prozesse, echter Staging-Lifecycle | **Schwerpunkt der Erweiterung** |
| Architektur | Schichtenverträge, Supply Chain, Import-Linter, CLI-Exit-Codes, JSON-Schemas | Eigenständige Vertragsschicht |
| Produkt-E2E | Öffentlicher CLI-Einstieg bis gespeichertem, wieder eingelesenem Ergebnis; Prozessgrenzen, wo relevant | Alle kritischen Produktabläufe und Fehlerwege |
| **Selbst-Mutation** | Engine wendet sich selbst an: Modul-Gates mit Contract-Tests als `--tests-dir` | Qualifikationsdach; Kill-Rate als Maß |

### Grenzen-Ehrlichkeit (Benennungsregel)

Ein Test einer kleineren Grenze wird exakt so benannt: `Run-E2E` (ein Lauf gegen ein
Fixture-Projekt), `Campaign-E2E` (Laufserie mit Unterbrechung/Resume),
`Wheel-Install-E2E` (installiertes Wheel außerhalb des Checkout). Kein kleiner
Grenzdurchstich wird als vollständiger Produkt-E2E ausgewiesen.

### Marker

Neue Tests kennzeichnen ihre Ebene mit `integration`, `e2e` oder `architecture`.
`slow`, `windows-only` beschreiben Ressourcen, nicht Ebenen. IDs in Testdocstrings
verbinden Tests mit dem Szenariokatalog (§5).

## 4. Regeln für belastbare Tests

1. Staging, atomic_file, run_lock, executor, worker, runner, orchestrator und db sind
   innerhalb der jeweils geprüften Grenze echte Produktionsimplementierungen.
2. Kleine synthetische Projekte, kurze Testlisten und kontrollierte Fixtures sind
   erlaubt. Ein Mock, Schattenmodell oder Stub darf den zu prüfenden Mechanismus nicht
   ersetzen.
3. Windows-FS-Fehler (Sharing Violation, Junction, Readonly) und kontrollierte I/O-
   Fehler dürfen injiziert werden. Ein solcher Test belegt Fehlerbehandlung, keine
   Hardwarequalifikation.
4. Erwartungen stammen aus unabhängiger Arithmetik, Spezifikation, kontrollierten
   Referenzdaten oder einer separat ausgeführten Referenz. **Keine Berechnung des
   Sollwerts mit derselben Produktionsfunktion, deren Korrektheit behauptet wird.**
5. Mindestens eine fachliche Gegenprobe pro kritischem Vertrag: fehlender
   Forced-Fail-Nachweis, verwaiste Jobhandles, ReadOnly-Templeichen,
   Stale-Staging-Evidence.
6. Prozesslebenszyklus-Tests beobachten Handle-/Pipe-/Verzeichnis-Ressourcen über den
   gesamten Prozessbaum (Job Object), nicht nur den direkten Kindprozess.
7. Tests beobachten Ergebnisse und Zustände, nicht bloß Aufrufzahlen. Private
   Inspektion kann ergänzen, ersetzt aber keinen Durchstich über den öffentlichen
   Einstieg (CLI oder Python-API).
8. Seeds, Toleranzen, Timeout-Budgets und maximale Laufzeit sind explizit. Ein
   Fehlschlag darf nicht durch schwächere Assertions oder unkontrolliertes Wiederholen
   verschwinden.
9. PASS, FAIL, BLOCKED und NOT_EXECUTED werden getrennt dokumentiert. Ein Skip ist kein
   PASS. Eine bestandene Negativkontrolle belegt korrekte Abweisung, nicht den
   erfolgreichen Produktablauf.
10. **Bekannte Lücken** bekommen einen konkreten, abgelegten Repro, eine
    Normzuordnung, eine eng begrenzte Fehlerursache und `xfail(strict=True)`. Sie
    zählen weder als PASS noch als geschlossene Anforderung. XPASS scheitert, bis
    Markierung und Lückenstatus korrigiert sind. Unverwandte Fehler dürfen nicht
    mitgefangen werden.
11. **Bug-Hunting-Kanal:** Findet eine Testwelle einen gültigen Produktfehler, werden
    Repro, Erwartung und Ursache gesichert, der Defekt erhält eine neue M-ID, wird
    rot/grün verifiziert und ins Master-Ledger eingetragen. Das Ergebnis darf nicht
    durch Mocking des fehlerhaften Kerns oder ein unbegründetes Skip verdeckt werden.
12. Mutation-Gates sind ein eigenständiger Nachweis, kein Ersatz für
    Integrationstests; Integrationstests sind kein Ersatz für Mutation-Gates. Die
    Kill-Rate je Modul ist das Abnahmeinstrument dieser Sanierung (§6).
13. **Bestandsschutz (PO-Auflage):** Bestehende Tests werden nicht gelöscht, um
    Prozentverhältnisse der Testpyramide künstlich zu verändern. »Mock-Reduktion«
    (TM-T7) bedeutet ausschließlich das Ergänzen echter Tests und das Freilegen von
    Grenzen. Ein bestehender Test darf nur nach dokumentierter PO-Entscheidung
    entfernt werden, wenn sein Vertrag durch einen stärkeren, echten Test vollständig
    abgedeckt ist.
14. **Enabler-TDD-Prinzip allgemein (PO-Auflage):** Jede/r neue Test muss Nachweiskraft
    besitzen — unabhängiges Orakel und die konkrete Möglichkeit, rot zu werden
    (keine Tautologien, keine Mock-Selbstbestätigung). Die Nachweiskraft wird für
    Pilotkorridore über Mutanten-Empfindlichkeit belegt (Kill-Rate) und je Welle in
    den Receipts dokumentiert. Bereits als gefixt geltende Gruppen (R0–R4) werden
    durch die neuen Integrations- und E2E-Tests verhaltensseitig nachgeschärft — ihr
    Fix wird nicht als gegeben vorausgesetzt, sondern bleibt angreifbar.

## 5. Verbindlicher Szenariokatalog

Zwölf Familien bleiben vollständig im Umfang. Ihre Teilfälle sind einzeln mit Tests
oder einer konkret benannten fehlenden Voraussetzung zu belegen.

| ID | Reale Kette | Positiv-/Negativfälle / unabhängiges Orakel | Norm |
|---|---|---|---|
| TM-01 | `mutmut-win run` → Staging → Clean-Run → Stats → Forced-Fail → Mutant-Dispatch → Verdikt | Node-IDs unabhängig von Verbosity; Forced-Fail-Nachweis nur bei echter Trampolin-Exception; Timeout ≠ Kill; leere Testliste kein Score-0 | Q-05, Q-70, Q-71 |
| TM-02 | Staging-Kopie → Gitignore-Boundary → Link-Abwehr → Deletion-Sync → Frische-Check | NTFS-Normcase-Identität; Junction-Kinder nicht gespiegelt; ignorierter Baum hinterlässt keine Hüllen; Meta-Fixture überlebt Companion-Refresh | Q-32, Q-43, Q-44 |
| TM-03 | Executor → Worker-Spawn → Task-Dispatch → Event-Loop → Shutdown → Ressourcen-Freigabe | Jobhandle bei Init-Fehler freigegeben; Runtime-Root nach Shutdown entfernt; Ctrl-C → Exit 130; Pool-Kollaps → aborted | Q-26, Q-48, M-146 |
| TM-04 | Run-Lock → Guard-Priming → Owner-Publikation → Stale-Recovery → Release | PermissionError → RunLockUnavailableError; Selbstblockade nach Post-Publikations-Fehler wird zurückgerollt; Byte-Range-Lock → RunLockHeldError | Q-47, Q-48, M-093 |
| TM-05 | `collect_tests` → Stats-Plugin → Cache → inkrementeller Vergleich → Timeout-Modell | Verbosity-unabhängige Node-ID-Liste; PYTEST_ADDOPTS wirkt genau einmal; übersprungene Tests liefern Dauer 0.0; Cache wird bei Suite-Änderung neugehoben | Q-70 |
| TM-06 | CLI-Run → Orchestrator → Pipeline → Finalisierung → finish_run → Export | Ctrl-C im Finalisierungsfenster → interrupted; Drift nennt korrekte Phase; Score-Nenner enthält unchecked; JSON-Export schema-valide | Issue #130, M-105, M-131 |
| TM-07 | Browser → Datei-Highlight → Mutant-Highlight → Diff-Laden → Anzeige | Veralteter Diff überschreibt nie den aktuellen; RuntimeError nach App-Ende kein Crash; leere Tabelle neutralisiert Detail; ein Worker, latest-wins | Q-65, M-117–M-120 |
| TM-08 | `mutmut-win run` gegen echtes Mini-Projekt → vollständiger Lauf → gespeicherte DB → `results`/`browse`/`apply` | Exit-Code korrekt; Score unabhängig rechnen; DB-Status terminal; CI/CD-Export nur bei qualifizierter Basis | Release-Vertrag |
| **TM-09** | Run → harte Unterbrechung (Kill/Shutdown-Fenster) → **Neustart → Verdikt-Wiederverwendung → Abschluss** | Identische Verdikte ohne Re-Run (Cache-Hit belegbar); Fortschritt bleibt über Neustart erhalten; abweichender tests-dir/HEAD hebt Cache korrekt auf; Abschluss-Score identisch zum ununterbrochenen Lauf | **#195**, E-C |
| **TM-10** | Clean-Run → Stats → Forced-Fail: **jede Phase terminiert konfigurierbar** | Hänger werden als Timeout diagnostiziert und abgebrochen, nicht als Kill gewertet; Timeout-Konfiguration greift phasenscharf; Forced-Fail-Timeout meldet Ursache, nicht nur Wirkung | **#194**, E-B |
| **TM-11** | Trampolinierung klassenlastiger Projekte: pydantic-`BaseModel`/`@computed_field`, Textual-App, py3.14-Features, Typ-Checking-Projekte → Clean-Run bleibt grün | Spiegelvergleich: untrampolinierte Suite grün ↔ trampolinierte Suite grün (aktuell: 136↔136 rot, 68-fach verlangsamt); xfail(strict=True) mit Repro bis H1–H4 geklärt sind | E-A, H1–H4 |
| **TM-12** | Gebautes Wheel → Installation außerhalb des Checkout → Fixture-Lauf → Provenance | Herkunft und Bytes aller importierten mutmut_win-Module stammen aus dem Wheel; Run, Results, Browse durchlaufen die Installation; beschädigte Inputs werden abgewiesen | Release-Vertrag; MOSAIC TM-D5 adaptiert |

Ein vollständiger Test einer kleineren Grenze wird genau benannt (§3) und nicht als
vollständiger Produkt-E2E ausgewiesen.

## 6. Soll-Zustand und Abnahme

### 6.1 Richtungswerte (Kommunikation, kein Freigabekriterium)

| Ebene | Ist 2026-10-04 | Richtung | Pakete |
|---|---:|---:|---|
| E2E | 0 | ≈ 25–40 (parametrisiert über Fixture-Projekte) | T1, T2, T8, T9 |
| Integration (echtes FS/Prozess) | 165 | ≈ 350 und mehr — **Schwerpunkt der Sanierung** | T3, T4 |
| Property (Hypothesis) | 79 | ≈ 200 | T5 |
| Architektur | 35 | ≈ 100 | T6 |
| Unit (mocked) | 1.627 | unverändert erhalten; Ergänzung echter Tests (§4.13) | T7 (schrittweise) |
| Unit (pur) | 586 | beibehalten + ausbauen | organisch |

Richtungswerte steuern Kommunikation und Ressourcenplanung. Sie sind **kein**
Freigabekriterium; es werden keine Varianten allein zur Erhöhung einer Quote erzeugt
und keine Bestandstests gelöscht (§4.13).

### 6.2 Abnahmekriterien der Sanierung (verbindlich)

1. **Szenario-Vollständigkeit:** Jede Familie TM-01 bis TM-12 ist vollständig
   abgedeckt — jeder Teilfall durch einen Test oder eine konkret benannte fehlende
   Voraussetzung (Nachweis je Welle im Fallinventar).
2. **Kill-Rate:** Je in der Sanierung betroffenem Modul Mutation-Score ≥ 80 % (P-04)
   oder ein dokumentierter Adjudizierungs-Korridor wie beim trampoline-Gate.
   Pilotmodule: **suspended_spawn** (Ist 34,8 %) und **db** (Ist 24,3 %).
3. **Nachweiskraft:** Jede Welle dokumentiert die Rot-Empfindlichkeit ihrer Tests
   (Regel 4.14); Pilotkorridore belegen sie über Mutanten-Empfindlichkeit.
4. **Wellen-Receipts:** Jede Welle liefert Fallinventar (nach Zählregeln §2.3),
   echte Laufbelege, offene Grenzen und — bei gefundenen Produktfehlern — neue
   M-IDs mit rot/grün-Receipts (Regel 4.11).
5. **Bestandsschutz:** Vollsuite grün; keine gelöschten Tests ohne PO-Entscheidung
   (§4.13); keine abgeschwächte Assertion; import-linter-Verträge unverändert.

## 7. Umsetzungspakete (Dateiebenen)

| Paket | Dateien | Abnahmekriterium | Welle |
|---|---|---|---|
| T0 | Engine-Enabler (`src/mutmut_win/…`) | #194/#195/M-097 rot/grün; TM-09/TM-10 grün | W0 |
| T1 | `tests/e2e/test_full_run.py` | Echter `mutmut-win run` gegen Fixture-Projekt; Exit-Code, DB-Status, Score-Plausibilität, CI/CD-Export | W1 |
| T2 | `tests/e2e/test_error_paths.py` | Negativ-Pfade: fehlende Tests, korrupte DB, unterbrochener Lauf, ungeeignetes Timeout | W1 |
| T3 | `tests/integration/test_windows_fs_contracts.py` | Junction-Anlage/-Abwehr, Hardlink-Identität, Readonly-Removal, Sharing-Violation-Retry, NTFS-Normcase | W2 |
| T4 | `tests/integration/test_process_lifecycle.py` | Jobhandle-/Pipe-/Runtime-Root-Freigabe über echten Prozessbaum; Ctrl-C in jeder Phase; Pool-Kollaps-Recovery | W2 |
| T5 | `tests/unit/properties/` | Wiederverwendbare Strategies + ≥ 60 neue @given-Tests (Serialisierung, Fingerprint-Stabilität, Pfade, Stat-Ergebnisse) | W3 |
| T6 | `tests/architecture/` | CLI-Exit-Code-Vertrag, JSON-Export-Schema, Konfigurations-Schema, Modul-Schreibpfad-Vertrag | W4 |
| T7 | Bestehende unit/-Tests | Für jede interne Modulgrenze, die nur über Mocks getestet wird, echte Integrationstests ergänzen (keine Löschung, §4.13) | fortlaufend |
| T8 | `tests/e2e/test_class_heavy_projects.py` | TM-11 mit xfail(strict=True)-Dokumentation der Trampolin-Grenze (Repro gesichert) | W1 |
| T9 | `tests/e2e/test_wheel_install.py` | TM-12: Wheel-Installation außerhalb Checkout, Fixture-Lauf, Modul-Provenance | W5 |

## 8. Wiederverwendbare Hypothesis-Strategies

`tests/unit/properties/strategies.py` stellt gemeinsame Strategies bereit:

```python
relative_paths = st.text(alphabet=st.characters(
    whitelist_categories=("Ll", "Lu", "Nd", "Pc"),
    min_codepoint=0x20, max_codepoint=0x7E
), min_size=1, max_size=60).filter(lambda s: "/" not in s and "\\" not in s)

exit_codes = st.integers(min_value=0, max_value=255)
mutant_names = st.text(alphabet="abcdefghij_", min_size=3, max_size=50)
stat_results = st.fixed_dictionaries({
    "status": st.sampled_from(["killed", "survived", "timeout", "suspicious"]),
    "exit_code": exit_codes,
    "duration": st.floats(min_value=0, max_value=3600, allow_nan=False),
})
```

Jede Strategy wird durch mindestens einen Round-Trip-Test gesichert
(generate → serialize → deserialize → compare).

## 9. Architektur-Verträge (Erweiterung)

| Vertrag | Werkzeug | Prüfumfang |
|---|---|---|
| Import-Linter (bestehend) | lint-imports | 5-Band-Schichten |
| Supply Chain (bestehend) | pytest test_release_supply_chain.py | Release-Lifecycle, Tags, Provenance |
| **CLI-Exit-Codes** (neu) | pytest parametrize | Jede CLI-Fehlerklasse → dokumentierter Exit-Code |
| **JSON-Export-Schema** (neu) | pytest + jsonschema | CI/CD-Export gegen Schema validieren |
| **Konfigurations-Schema** (neu) | pytest + pydantic | Ungültige Config-Kombinationen fail-closed |
| **Schreibpfad-Vertrag** (neu) | pytest | Nur atomic_file schreibt in mutants/; kein raw `open()` in Engine-Modulen — mit dokumentierter Ausnahmeliste (M-130-Forced-Fail-Beweis schreibt bewusst untrampoliert) |

## 10. Ausführung, Qualitätsgates und Betriebsregeln

```powershell
# Ebenen-spezifisch
uv run --no-sync pytest -m architecture -p no:cacheprovider -q
uv run --no-sync pytest -m integration -p no:cacheprovider -q
uv run --no-sync pytest -m e2e -p no:cacheprovider -q
uv run --no-sync pytest tests/unit/properties/ -p no:cacheprovider -q

# Vollständig
uv run --no-sync pytest -p no:cacheprovider -q --cov=src/mutmut_win --cov-report=term-missing

# Statische Gates
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy src/
uv run --no-sync lint-imports --no-cache
```

**Serena ist für alle Code-Analyse und Implementierung verpflichtend** (PO-Auflage;
Navigation über Symbole, Refactorings über Serena-Werkzeuge).

Betriebsregeln für Mutation-Gates (Lehren E-A bis E-F aus der Kampagne 2026-10-05):

1. Gezielte Single-File-Läufe mit Contract-Tests als einzigem `--tests-dir`;
   `--max-children ≤ 16` (Arbeitstakt des Auftraggebers); separater Worktree.
2. **Keine Worktree-Änderungen während Gate-Läufen** (Fingerprint-/Staging-Wächter).
3. **Lange Läufe grundsätzlich als detached Prozess** starten (E-D: OpenCode-
   Hintergrund-Shells sterben mit dem Shell-Host nach > 4 h).
4. **Monitoring liest die Cache-DB des tatsächlich laufenden Worktrees** (E-E).
5. Kampagnen langer Module setzen die W0-Fixes voraus (#194/#195); sonst drohen
   Forced-Fail-Hänger und Fortschrittsverlust bei jedem Abbruch.

## 11. Ausführungsbericht und Abschluss

Der Ausführungsbericht dokumentiert je TM-Familie, Testpaket und Welle:

- konkrete Testfunktionen, Fallzahl (nach Zählregeln §2.3) und Marker;
- echte Module, ersetzte Randbedingungen und unabhängiges Orakel;
- Befehl, Code-Stand, Laufzeit, PASS/FAIL/SKIP und Quellbindung;
- aufgedeckte Fehler (M-IDs) sowie nicht abgedeckte Produktvoraussetzungen;
- neuen Gesamtbestand mit getrennten Ebenen und Methoden;
- Aussagegrenze: Regression, Produktdurchstich, Release-Qualifikation oder
  Selbst-Mutations-Kampagne.

Abgeschlossen ist ein Paket erst nach tatsächlicher Ausführung und überprüften Belegen.
Ausgeführte FAILs sowie BLOCKED/NOT_EXECUTED bleiben offen und sichtbar.

## 12. Fachliche Quellen zur Teststrategie

- [Google Testing Blog: Fixing a Test Hourglass](https://testing.googleblog.com/2020/11/fixing-test-hourglass.html)
- [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Import Linter](https://import-linter.readthedocs.io/)
- MOSAIC-Testspezifikation (2026-10-04, überarbeitete Fassung) als strukturelle Vorlage.

Diese Quellen begründen die Strategie. Konkrete mutmut-win-Sollwerte werden aus den
Produktnormen abgeleitet, nicht aus allgemeinen Prozentempfehlungen.

## 13. PO-Entscheidungen und Auflagen der Freigabe

### 13.1 Entscheidungen (alle bestätigt am 2026-10-06)

| ID | Entscheidung | Ergebnis |
|---|---|---|
| E-1 | Abnahme über Szenario-Vollständigkeit + Kill-Rate statt Prozentquoten (§6) | **beschlossen** |
| E-2 | W0 inklusive Defektfixes #194/#195/M-097 per TDD | **beschlossen** |
| E-3 | Kill-Rate-Ziel ≥ 80 % je betroffenem Modul; Pilot suspended_spawn + db | **beschlossen** |
| E-4 | Rahmen: Sprint 47, Branch `fix/v3.1.0-testsanierung`, Versionsziel 3.1.0 | **beschlossen** |

### 13.2 Auflagen der Freigabe (2026-10-06, verbindlich)

1. **Serena-Pflicht:** Serena (serena-mutmut-win) ist für alle Code-Analyse und
   Implementierung verpflichtend — erhöht Qualität von Analyse und Implementierung.
2. **Enabler-TDD überall:** Das Rot-/Grün-Prinzip gilt nicht nur für #194/#195/M-097,
   sondern in der gesamten Sanierung — auch gegenüber bereits als gefixt geltenden
   Gruppen und grundsätzlich für jeden neuen Test (Regel 4.14).
3. **Keine Test-Löschung:** Bestehende Unit-Tests werden nicht gelöscht, um die
   Testpyramide prozentual zu rücken (Regel 4.13).
4. **Fokus Integration/E2E:** Viele sinnvolle neue echte Integrationstests und viele
   sinnvolle neue echte E2E-Tests einziehen (§6.1 Schwerpunkt).
