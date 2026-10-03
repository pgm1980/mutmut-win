# mutmut-win Testspezifikation

Stand: 2026-10-04. Auftraggeber: PO. Umsetzung: GLM-5.3.
Ausgangsstand: `9592ab7` (`fix/v3.0.0-remediation-r3`). Analysegrundlage: Test-Pyramiden-Analyse vom 2026-10-04.

## 1. Ziel und Geltungsbereich

Diese Spezifikation konkretisiert die PO-Diskussion über Testbalance, echte
Komponentenintegration, Property-Testing und Architekturverträge. Sie gilt für
mutmut-win und alle ausführbaren Engine-, Staging-, Prozess- und CLI-Pfade.

Die laufende R3-Sanierungsroadmap läuft parallel; diese Spezifikation und ihre
Umsetzung ergänzen die bestehende Suite, sie ersetzen keine bestehenden Tests.

Tests müssen Fehler über Modulgrenzen erkennen, Windows-Dateisystem- und
Prozessspezifika gegen echte Betriebssysteminteraktionen prüfen und fachliche
Verträge gegen unabhängig abgeleitete Erwartungen sichern. Eine hohe
Testanzahl, Zeilenabdeckung oder erfolgreiche Mock-Serialisierung allein
genügt nicht.

Führende Produktnormen:

- [README](../../README.md): Operating Profile, Mutation-surface limits, Temporary directories, Release policy.
- [Architecture](../../_docs/architecture/adr_layer_contracts_v2.md): Fünf-Band-Schichtenarchitektur.
- [Review-Abschlussbericht](../../reviews/): 146 Defektgruppen, Q-01–Q-76 Querschnittsmaßnahmen.
- [R0-R4 Master-Ledger](../../reviews/mutmut-win-r2-2026-10-01/glm-followup/R0-R4-MASTER-LEDGER.md): Gruppen-scharfe Abnahme.
- [Test-Pyramiden-Analyse](#): Messdaten und Soll/Ist-Vergleich (2026-10-04).

## 2. Ausgangslage und Zählweise

Die geprüfte Collection enthält 3.072 pytest-Fälle in 186 Dateien.

| Ablage bzw. expliziter Prüfzweck | Fälle | Anteil |
|---|---:|---:|
| `tests/unit/` | 2.979 | 96,97 % |
| `tests/integration/` | 93 | 3,03 % |
| `tests/e2e_projects/` (Fixtures, keine Tests) | 0 | 0,00 % |

Nach Testtyp (Methodenklassifikation, nicht Ablage):

| Testtyp | Fälle | Anteil |
|---|---:|---:|
| Unit (gemockt) — MagicMock, @patch | 1.627 | 52,9 % |
| Unit (pur) — keine Mocks | 586 | 19,0 % |
| Subprocess-Tests — echte Prozesse in unit/ | 491 | 16,0 % |
| Property (parametrisiert) — @parametrize | 179 | 5,8 % |
| Integration (echtes FS) — NTFS, Junctions | 165 | 5,4 % |
| Property (Hypothesis) — @given | 79 | 2,6 % |
| Architektur — Supply Chain, Import-Linter | 35 | 1,1 % |

Ordnerquoten sind nicht identisch mit Anteilen tatsächlich isolierter Tests.
Unter `tests/unit/` leben 437 Subprocess-Tests, die faktisch
Integrationstests sind. Echte E2E-Tests (CLI-Vollständigkeitsdurchstich)
existieren nicht.

## 3. Testarchitektur

| Ebene | Prüfumfang | Einsatz |
|---|---|---|
| Unit (pur) | Lokaler Vertrag, Algebra, Validierung, Grenzen | Schnelle breite Basis |
| Unit (gemockt) | Modulgrenzen mit kontrollierten Abhängigkeiten | Reduzieren; nur für externe Schnittstellen |
| Property | Invarianten über Eingabespektren (Hypothesis, Parametrize) | Systematische Grenzfall- und Fehlerinjektion |
| Integration | Mehrere echte Produktionsmodule, echtes NTFS, echte Prozesstry, echte Staging-Lifecycle | Schwerpunkt der Erweiterung |
| Architektur | Schichtenverträge, Supply Chain, Import-Linter, CLI-Exit-Codes, JSON-Schemas | Eigenständige Vertragsschicht |
| E2E | Öffentlicher CLI-Einstieg bis gespeichertem, wieder eingelesenem Ergebnis | Alle kritischen Produktabläufe und Fehlerwege |

Property Testing ist eine Methode auf mehreren Ebenen und wird getrennt von
der Ebene erfasst. Architekturtests sind ein eigener Prüfzweck.

Keine feste Prozentquote ist ein Freigabekriterium. Entscheidend sind die
abgedeckten Anforderungen, Systemgrenzen, Fehlerwege und zuverlässige
Fehlererkennung. Bestehende nützliche Unit-Tests bleiben erhalten.

Neue Tests kennzeichnen ihre Ebene mit `integration`, `e2e` oder `architecture`.
Marker `slow` und `windows-only` beschreiben Ressourcen, nicht Ebenen.

## 4. Regeln für belastbare Tests

1. Staging, atomic_file, run_lock, executor, worker, runner, orchestrator und
   db sind innerhalb der jeweils geprüften Grenze echte Produktionsimplementierungen.
2. Kleine synthetische Projekte, kurze Testlisten und kontrollierte Fixtures
   sind erlaubt. Ein Mock darf den zu prüfenden Mechanismus nicht ersetzen.
3. Windows-FS-Fehler (Sharing Violation, Junction, Readonly) dürfen injiziert
   werden. Ein solcher Test belegt Fehlerbehandlung, keine Hardwarequalifikation.
4. Erwartungen stammen aus unabhängiger Arithmetik, Spezifikation oder
   kontrollierten Referenzdaten. Keine Berechnung des Sollwerts mit derselben
   Produktionsfunktion, deren Korrektheit behauptet wird.
5. Mindestens eine fachliche Gegenprobe pro kritischem Vertrag: fehlender
   Forced-Fail-Nachweis, verwaiste Jobhandles, ReadOnly-Templeichen,
   Stale-Staging-Evidence.
6. Prozesslebenszyklus-Tests beobachten Handle-/Pipe-/Verzeichnis-Ressourcen
   über den gesamten Prozessbaum (Job Object), nicht nur den direkten Kindprozess.
7. Tests beobachten Ergebnisse und Zustände, nicht bloß Aufrufzahlen.
   Private Inspektion kann ergänzen, ersetzt aber keinen Durchstich über
   den öffentlichen Einstieg (CLI oder Python-API).
8. Seeds, Toleranzen, Timeout-Budgets und maximale Laufzeit sind explizit.
   Ein Fehlschlag darf nicht durch schwächere Assertions verschwinden.
9. PASS, FAIL, BLOCKED und NOT_EXECUTED werden getrennt dokumentiert.
   Ein Skip ist kein PASS. Bekannte Produktlücken werden nicht mit Attrappen geschlossen.
10. Mutation-Gates sind ein eigenständiger Nachweis, kein Ersatz für
    Integrationstests; Integrationstests sind kein Ersatz für Mutation-Gates.

## 5. Verbindlicher Szenariokatalog

Acht Familien bleiben vollständig im Umfang. Teilfälle sind einzeln mit Tests
oder einer konkreten fehlenden Voraussetzung zu belegen.

| ID | Reale Kette | Positiv-/Negativfälle / unabhängiges Orakel | Norm |
|---|---|---|---|
| TM-01 | `mutmut-win run` → Staging → Clean-Run → Stats → Forced-Fail → Mutant-Dispatch → Verdikt | Node-IDs unabhängig von Verbosity; Forced-Fail-Nachweis nur bei echter Trampolin-Exception; Timeout ≠ Kill; leere Testliste kein Score-0 | Q-05, Q-70, Q-71 |
| TM-02 | Staging-Kopie → Gitignore-Boundary → Link-Abwehr → Deletion-Sync → Frische-Check | NTFS-Normcase-Identität; Junction-Kinder nicht gespiegelt; ignoringierter Baum hinterlässt keine Hüllen; Meta-Fixture überlebt Companion-Refresh | Q-32, Q-43, Q-44 |
| TM-03 | Executor → Worker-Spawn → Task-Dispatch → Event-Loop → Shutdown → Ressourcen-Freigabe | Jobhandle bei Init-Fehler freigegeben; Runtime-Root nach Shutdown entfernt; Ctrl-C → Exit 130; Pool-Kollaps → aborted | Q-26, Q-48 |
| TM-04 | Run-Lock → Guard-Priming → Owner-Publikation → Stale-Recovery → Release | PermissionError → RunLockUnavailableError; Selbstblockade nach Post-Publikations-Fehler wird zurückgerollt; Byte-Range-Lock → RunLockHeldError | Q-47, Q-48 |
| TM-05 | `collect_tests` → Stats-Plugin → Cache → inkrementeller Vergleich → Timeout-Modell | Verbosity-unabhängige Node-ID-Liste; PYTEST_ADDOPTS wirkt genau einmal; übersprungene Tests liefern Dauer 0.0; Cache wird bei Suite-Änderung neugehoben | Q-70 |
| TM-06 | CLI-Run → Orchestrator → Pipeline → Finalisierung → finish_run → Export | Ctrl-C im Finalisierungsfenster → interrupted; Drift nennt korrekte Phase; Score-Nenner enthält unchecked; JSON-Export schema-valide | Issue #130, M-105, M-131 |
| TM-07 | Browser → Datei-Highlight → Mutant-Highlight → Diff-Laden → Anzeige | Veralteter Diff überschreibt nie den aktuellen; RuntimeError nach App-Ende kein Crash; leere Tabelle neutralisiert Detail; ein Worker, latest-wins | Q-65 |
| TM-08 | `mutmut-win run` gegen echtes Mini-Projekt → Vollständiger Lauf → gespeicherte DB → `results`/`browse`/`apply` | Exit-Code korrekt; Score unabhängig rechnen; DB-Status terminal; CI/CD-Export nur bei qualifizierter Basis | Release-Vertrag |

## 6. Soll-Zustand und Umsetzungspakete

### Soll-Testpyramide (Ziel nach Umsetzung)

| Ebene | Ist (2026-10-04) | Soll | Maßnahme |
|---|---:|---:|---|
| E2E | 0 (0 %) | ≥ 15 (≥ 3 %) | TM-T1, TM-T2 |
| Integration (echtes FS/Prozess) | 165 (5,4 %) | ≥ 350 (≥ 10 %) | TM-T3, TM-T4 |
| Property (Hypothesis) | 79 (2,6 %) | ≥ 200 (≥ 6 %) | TM-T5 |
| Architektur | 35 (1,1 %) | ≥ 100 (≥ 3 %) | TM-T6 |
| Unit (mocked) | 1.627 (52,9 %) | Reduzieren durch Freilegung | TM-T7 (schrittweise) |
| Unit (pur) | 586 (19,0 %) | Beibehalten + ausbauen | organisch |

### Umsetzungspakete

| Paket | Dateien | Abnahmekriterium | Priorität |
|---|---|---|---|
| T1 | `tests/e2e/test_full_run.py` | Echter `mutmut-win run` gegen Fixture-Projekt aus e2e_projects/; Exit-Code, DB-Status, Score-Plausibilität, CI/CD-Export | P0 |
| T2 | `tests/e2e/test_error_paths.py` | Negativ-Pfade: fehlende Tests, korrupte DB, unterbrochener Lauf, unfaires Timeout | P0 |
| T3 | `tests/integration/test_windows_fs_contracts.py` | Junction-Anlage/-Abwehr, Hardlink-Identität, Readonly-Removal, Sharing-Violation-Retry, NTFS-Normcase | P0 |
| T4 | `tests/integration/test_process_lifecycle.py` | Jobhandle-/Pipe-/Runtime-Root-Freigabe über echten Prozessbaum; Ctrl-C in jeder Phase; Pool-Kollaps-Recovery | P1 |
| T5 | `tests/unit/properties/` | Wiederverwendbare Hypothesis-Strategies (Pfade, Exit-Codes, Mutant-Namen, Stat-Ergebnisse) + mindestens 60 neue @given-Tests | P1 |
| T6 | `tests/architecture/` | CLI-Exit-Code-Vertrag, JSON-Export-Schema, Konfigurations-Schema, Modul-Schreibpfad-Vertrag | P1 |
| T7 | Bestehende unit/-Tests | Mock-Quote reduzieren: für jede interne Modulgrenze, die nur über Mocks getestet wird, einen echten Integrationstest ergänzen | P2 |

Die genaue Fallzahl ergibt sich aus unterschiedlichen Verträgen und relevanten
Parametrisierungen. Es werden keine Varianten allein zur Erhöhung einer Quote erzeugt.

## 7. Wiederverwendbare Hypothesis-Strategies

`tests/unit/properties/strategies.py` stellt gemeinsame Strategies bereit:

```python
# Beispiele für geplante Strategies
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

## 8. Architektur-Verträge (Erweiterung)

| Vertrag | Werkzeug | Prüfumfang |
|---|---|---|
| Import-Linter (bestehend) | lint-imports | 5-Band-Schichten |
| Supply Chain (bestehend) | pytest test_release_supply_chain.py | Release-Lifecycle, Tags, Provenance |
| **CLI-Exit-Codes** (neu) | pytest parametrize | Jede CLI-Fehlerklasse → dokumentierter Exit-Code |
| **JSON-Export-Schema** (neu) | pytest + jsonschema | CI/CD-Export gegen Schema validieren |
| **Konfigurations-Schema** (neu) | pytest + pydantic | Ungültige Config-Kombinationen fail-closed |
| **Schreibpfad-Vertrag** (neu) | pytest | Nur atomic_file schreibt in mutants/; keine raw open() in Engine-Modulen |

## 9. Ausführung und Qualitätsgates

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

Mutation-Gates bleiben unverändert: gezielte Single-File-Läufe mit
Contract-Tests als einzigem `--tests-dir`, `--max-children ≤ 6`,
Separater Worktree ohne parallele Worktree-Änderungen.

Neue Tests dürfen keine bestehende Assertion abschwächen. Bei einem gültigen
Produktfehler werden Repro, Erwartung und Ursache gesichert.

## 10. Ausführungsbericht und Abschluss

Der Ausführungsbericht dokumentiert je TM-Familie und Testpaket:

- konkrete Testfunktionen, Fallzahl und Marker;
- echte Module, ersetzte Randbedingungen und unabhängiges Orakel;
- Befehl, Code-Stand, Laufzeit, PASS/FAIL/SKIP und Quellbindung;
- aufgedeckte Fehler sowie nicht abgedeckte Produktvoraussetzungen;
- neuen Gesamtbestand mit getrennten Ebenen und Methoden;
- Aussagegrenze: Regression, Produktdurchstich oder Release-Qualifikation.

Abgeschlossen ist ein Testpaket erst nach tatsächlicher Ausführung und
überprüften Belegen.

## 11. Fachliche Quellen zur Teststrategie

- [Google Testing Blog: Fixing a Test Hourglass](https://testing.googleblog.com/2020/11/fixing-test-hourglass.html):
  Eine tragfähige Integrationsschicht zwischen lokalen und Gesamttests.
- [The Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html):
  Verschiedene Prüfumfänge und gezielte Tests kritischer Gesamtabläufe.
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/):
  Property-Based Testing für systematische Grenzfallabdeckung.
- [Import Linter](https://import-linter.readthedocs.io/):
  Architekturverträge als CI-erzwungene Schichtprüfung.

Diese Quellen begründen die Strategie. Konkrete mutmut-win-Sollwerte werden
aus den Produktnormen abgeleitet, nicht aus allgemeinen Prozentempfehlungen.
