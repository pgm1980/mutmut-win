# P-08-Entscheidungen des finalen Reviewers: M-008, M-003, M-144 Stufe 2

| | |
|---|---|
| Stand | 24.09.2026 |
| Verfasser | Claude, finaler Reviewer (Verfasser von `Review-Abschlussbericht.md`) |
| Anlass | Anfrage von GLM-5.3 zu drei ausstehenden Vertragsentscheidungen (Prinzip P-08) |
| Umsetzung | Issues #143 (M-008), #145 (M-003), #149 (M-144) |
| Referenzstand | mutmut-win v2.21.4, Commit `4d7f950` (Review-Arbeitsbereich `C:/claude_codex/mutmut-win-astra`) |
| Verbindlichkeit | Die Entscheidungen A/A/A sind verbindlich. Abschnitt „Korrekturen an Issues und Handover“ ist vor Umsetzungsbeginn in die Issue-Kommentare zu übernehmen. |

## Ergebnis auf einen Blick

| Gruppe | Kernbehauptung | Entscheidung | Wichtigste Auflagen |
|---|---|---|---|
| M-008 (high, AP-01) | bestätigt | **Variante A** – Publikationsfehler wird „suspicious“ | M-145 im selben Änderungssatz; gekapselte Re-Emission in `pytest_unconfigure`; keine Backslash-Escapes im Plugin-Literal; Runner-Meldung trägt den Tail; Satz „never a mutant verdict“ bleibt wörtlich; **kein** Kind-Fatalkanal, auch nicht später in AP-09 |
| M-003 (high, AP-03) | bestätigt | **Variante A** – gate-wirksam (Exit 1 nur mit `--min-score`) | gemeinsamer Kern vollständig inkl. `surface_complete`; schmale Revocation nach dem ersten UPDATE von `deauthorize_active_run_evidence`; Flächenprüfung als erste Prüfung unter `--min-score`; Degradation nur über die typisierte Warnung |
| M-144 (low, AP-07) | bestätigt | Stufe 1 bestätigt; **Stufe 2 Variante A** – fail-closed verweigern | Klassen-Vorprüfung vor dem Start; bei echter Instanz Beendigung per `_kill_proc_tree(proc)` vor jeder Job-Erzeugung; gleiche Wrapper-Schranke im Kompatibilitätszweig von `type_checking` (Q-08) |

Die drei Entscheidungen wirken widerspruchsfrei zusammen: keine neue Exit-Code-Nummer, `status_by_exit_code` unverändert, eine klare Dreiklassen-Taxonomie (fatal / suspicious / Autoritätsentzug) und kein Weg, auf dem ein unvollständiges oder verfälschtes Ergebnis `--min-score` oder den CI/CD-Export besteht (Abschnitt „Kohärenz“).

## Grundlage und Prüftiefe

- **Eigene Prüfung am Code:** Alle drei Kernbehauptungen habe ich selbst am Review-Stand `4d7f950` nachgeprüft (Belege unten, Zeilen 1-basiert). Die pytest-Semantik habe ich per `inspect.getsource` an pytest 9.0.3 unter CPython 3.14.7 geprüft.
- **Absicherung:** Ein Workflow mit zehn Agenten hat je Gruppe die Code-Fakten erhoben (Verifikationsagent) und die Varianten mit zwei Richtern mit Gegenlinsen bewertet („Score-Wahrheit und Vertrag“ bzw. „Betrieb und Minimalität“). Alle sechs Richter haben unabhängig Variante A gewählt, jeweils mit hoher Konfidenz. Ein Kohärenzagent hat das Zusammenspiel geprüft. Die Umsetzungsvorgaben unten sind die bereinigte Synthese; wo Richter voneinander abwichen, ist die Auflösung begründet.
- **Chain-of-Thought (CLAUDE.md):** Die parallelen Richter teilten sich den CoT-Server, ihre Ketten kollidierten (zwei Richter kamen nur auf einen think-Aufruf). Ich habe die Pflichtanalyse deshalb selbst mit 33 Schritten nachgeholt (10 für M-008, 10 für M-003, 3 für M-144, dazu Kohärenz), gespeichert als CoT-Sitzung `p08-finaler-reviewer-m008-m003-m144`. Die Richterkette ist als `p08-richter-workflow-wf_3da4e1c8-sicherung` gesichert.
- **Nur statisch:** Keine Tests, keine Reproduktion, kein mutmut-win-Lauf. pytest 8.2 bis 8.x ist nicht geprüft.
- **Zeilenangaben:** Alle Zeilen beziehen sich auf `4d7f950`. Im Arbeitsbranch `fix/v2.21.5-remediation-r1` sind sie teils verschoben (z. B. beginnt `create_mutants_for_file` dort 132 Zeilen später). Immer per Symbol verorten.
- **Werkzeughinweis Serena:** Der Serena-Server ist gemeinsam genutzt und aktuell auf das Arbeitsrepository von GLM-5.3 aktiviert. Die Agenten haben das erkannt und ihre tragenden Aussagen direkt gegen den Review-Arbeitsbereich geprüft; ich habe Serena nicht umgeschaltet, um die laufende Arbeit von GLM-5.3 nicht zu stören.

---

## Frage 1 – M-008: Proof-Publikation im generierten Phase-Guard-Hook

### 1. Verifikationsergebnis: bestätigt

- `src/mutmut_win/process/worker.py:477-479` (Konstante `_PYTEST_PHASE_GUARD_SOURCE`, generierter Hook `pytest_runtest_logreport`): `atomic_write_bytes(Path(marker_path), proof.encode("utf-8"))` ohne `try/except`; `_proof_published = True` nur nach Erfolg.
- `atomic_write_bytes` absorbiert nur eng begrenzte Rennen; `UnsafeAtomicWriteError`, `AtomicPublicationRaceError`, rohe `OSError` und erschöpfte Retry-Leitern entkommen (atomic_file.py ca. 369-404, 458-467).
- pytest 9.0.3: `_pytest.runner.call_and_report` ruft `ihook.pytest_runtest_logreport(report=report)` ohne `try`; `_pytest.main.wrap_session` setzt bei `BaseException` `ExitCode.INTERNAL_ERROR` (3).
- `worker.py:1232-1238` (`_process_task`, finally): Neutralisierung nur bei `exit_code == 0 and not phase_executed`.
- `constants.py:233`: `3: "killed"`; der Orchestrator zählt das (orchestrator.py:2150) und verwirft nur `fatal` (2142). `"killed"` steht in `REUSABLE_STATUSES` (orchestrator.py:1877-1879) – ein falscher Kill wird also in Folgeläufen wiederverwendet.
- Widerlegungskriterien geprüft, keines greift: Der Hook ist nicht gekapselt (kein Hookwrapper), pytest fängt die Ausnahme nicht, der Worker behandelt Exit 3 nicht gesondert.
- **Zusätzlicher, deterministischer Auslöser (neu belegt):** `pytest_runtest_logreport` für den Call-Report läuft innerhalb von `call_and_report(item, "call")` und damit **vor** dem Teardown des Tests. Function-scope-Monkeypatches des Nutzertests (z. B. `os.open`, `os.fsync`, `os.replace`, `Path.resolve`, das Sentinel-Env) sind dann noch aktiv; `atomic_file` ruft `os.*` zur Laufzeit über das Modul auf. Der Fehler ist also nicht nur ein seltener AV-Effekt, sondern auch testinduziert.

### 2. Entscheidung: Variante A

Ein Fehler bei der Proof-Publikation im pytest-Kind wird abgefangen, gemeldet und führt zu „kein Proof“: Exit 0 wird wie bisher zu 35 „suspicious“ neutralisiert, Exit 1 bleibt ein legitimer Kill. Kein INTERNALERROR, kein neuer Exit-Code, kein Fatalkanal über das Kind.

### 3. Begründung am Regelwerk

- **Regel 1 (Score-Wahrheit):** Beide Varianten beseitigen das falsche „killed“. A erzeugt kein neues falsches Ergebnis: „suspicious“ steht im Score-Nenner (`MutationRunResult.compute_score`) und senkt den Score, und es wird nie wiederverwendet (selbstheilend im Folgelauf).
- **Regel 2 (Fail-closed):** Beide sind konservativ. A liefert die Diagnose sichtbar (mit M-145 und Re-Emission), nicht still.
- **Regel 3 (Vertragskonsistenz) – entscheidet gegen B:**
  - Der Satz „A different or unverifiable competing leaf is a fatal pytest execution-boundary failure, never a mutant verdict“ (`worker.py:832-834`, Docstring `prepare_pytest_phase_guard`) betrifft die **parent-seitige Plugin-Publikation** (`_publish_pytest_guard`, Konversion in `PytestBoundaryError`, `worker.py:779-787`), nicht den Proof im Kind. Er bleibt unter A wahr; B gewinnt dort nichts.
  - Die bestehende Taxonomie zieht die Grenze an der Prozessgrenze: Grenzverletzungen, die dasselbe Plugin im Kind erkennt, enden schon heute als `pytest.UsageError` → Exit 4 → „suspicious“; fatal sind nur parent-seitige Fehler (`worker.py:988`). B würde einen Kind-Fehler, den Test- oder Mutantencode auslösen kann, als fatale Grenzverletzung klassifizieren.
  - Der reservierte Code in B ist durch Testcode erzeugbar (`os._exit(R)`, `pytest.exit(returncode=R)` im Testkörper, conftest setzt `session.exitstatus`). Das ergibt keinen falschen Score, aber einen Abbruchkanal ohne Herkunftsprüfung.
- **Regel 4 (Minimalität):** A ändert nur den Plugin-String, den Neutralisierungstext und die Runner-Meldung. B braucht einen reservierten Code, einen Worker-Zweig und `pytest.exit`-Mechanik, deren Semantik je pytest-Version zu prüfen wäre.
- **Regel 5:** Keine Upstream-Divergenz (Guard und Proof sind mutmut-win-eigen). Verhaltensänderung für Nutzer: frühere falsche Exit-3-Kills werden „suspicious“, Scores können sinken → Releasehistorie.

**Bewertung der zusätzlichen Risiken:**

| Risiko | Bewertung |
|---|---|
| Dauerstörung nach der Clean-Phase erzeugt viele „suspicious“ ohne Laufabbruch; ohne `--min-score` Exit 0 | Tragfähig als Restrisiko, für die Score-Wahrheit überzeichnet: kein falsches Verdikt, Score sinkt, sichtbar. Eine verzeichnisweite Störung trifft zuerst die Clean-Phase und bricht dort mit Diagnose ab (`runner.py:413-424`); nach AP-09 bricht die Parent-Vorbereitung fatal ab. Übrig bleibt eine nur das Sentinel-Blatt betreffende, erst nach der Clean-Phase einsetzende Störung – dokumentieren, als Produktentscheidung bestätigen lassen. |
| AV-/Filtertreiber (transiente Sharing-Violations jenseits der Leitern) | Tragfähig und spricht für A: eine „suspicious“-Zeile, die im Folgelauf neu läuft, statt eines Laufabbruchs mit Wahrscheinlichkeit proportional zur Mutantenzahl. |
| Fälschbarkeit von Exit-Codes in B | Tragfähig, in der Anfrage aber falsch gewichtet: kein Score-Problem, sondern ein von Test-/Mutantencode steuerbarer Laufabbruch und eine Taxonomieverletzung. |
| Diagnoseverlust (Zeile fällt aus dem 50-Zeilen-Tail; Runner-Meldung ohne Tail) | Unterschätzt; deshalb verbindlich: M-145, Re-Emission in `pytest_unconfigure`, Tail in der Runner-Ausnahme. |
| Testinduzierte Auslöser (Suite patcht `os.*`) | Tragfähig und unter A akzeptabel: Im ersten Test endet heute schon die Clean-Phase deterministisch (Exit 3); A macht daraus einen Clean-Abbruch mit korrekter Diagnose. Reihenfolgeabhängig entstehen „suspicious“-Zeilen statt falscher Kills. |
| Hook-Logik im String-Literal wird nicht mutiert (Q-07) | Tragfähig; Abdeckung über runpy- und Realphasen-Tests, Lücke dokumentieren. |

### 4. Umsetzungsvorgaben (Issue #143)

**U1 – Änderungssatz (Q-06):** ein Änderungssatz in der Reihenfolge M-142 → M-145 → M-008 → M-143. M-145 (Meldung plus Tail nach `capture.close()`) ist harte Voraussetzung und liegt im selben Änderungssatz.

**U2 – Generiertes Plugin** (`worker.py`, `_PYTEST_PHASE_GUARD_SOURCE`, bisheriger Block `_proof_published = False` bis `_proof_published = True`). Zielgestalt (Einrückung wie im Plugin; **keine Backslash-Escapes**, siehe U3):

```python
_PUBLICATION_FAILURE_PREFIX = "mutmut-win: execution proof publication failed"
_proof_published = False
_proof_publication_failed = False
_proof_publication_diagnostic = None


def _emit_publication_diagnostic():
    """Best-effort: repeat a recorded proof publication failure on file descriptor 2."""
    try:
        if _proof_publication_diagnostic:
            os.write(2, (_proof_publication_diagnostic + os.linesep).encode("utf-8", "backslashreplace"))
    except Exception:
        pass


def pytest_runtest_logreport(report):
    """<Docstring siehe U8a>"""
    if report.when != "call" or report.skipped:   # nur M-143 ändert diese Zeile
        return
    global _proof_published, _proof_publication_failed, _proof_publication_diagnostic
    if _proof_published or _proof_publication_failed:
        return
    marker_path = os.environ.get(_PATH_ENV)
    proof = os.environ.get(_PROOF_ENV)
    if not (marker_path and proof):
        return                                     # wie heute: stiller No-op, kein Fehler-Flag
    try:
        atomic_write_bytes(Path(marker_path), proof.encode("utf-8"))
    except Exception as exc:
        _proof_publication_failed = True
        try:
            _proof_publication_diagnostic = f"{_PUBLICATION_FAILURE_PREFIX}: {type(exc).__name__}: {exc}"
        except Exception:
            _proof_publication_diagnostic = f"{_PUBLICATION_FAILURE_PREFIX}: {type(exc).__name__}"
        _emit_publication_diagnostic()
        return
    _proof_published = True


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    """Repeat a recorded publication failure so it stays inside the captured output tail."""
    _emit_publication_diagnostic()
```

Semantik, die verbindlich ist:
- `except Exception`, **nicht** `BaseException`: `KeyboardInterrupt` und `SystemExit` propagieren unverändert.
- `Path(...)`, `proof.encode(...)` und `atomic_write_bytes(...)` stehen im `try`.
- Das Fehler-Flag wird vor jeder Diagnosearbeit gesetzt. One-shot gilt für Erfolg **und** Misserfolg: kein Retry je Report (Filtertreiber-Sturm aus MBR-2026-09-14-01 bleibt ausgeschlossen).
- Diagnose über `os.write(2, ...)`, nicht über `sys.stderr` (ein im Test ersetztes `sys.stderr` ist beim Call-Report noch aktiv). Beim Call-Report ist die globale pytest-Capture suspendiert, die Zeile erreicht die Worker-/Runner-Pipe.
- `pytest_unconfigure` darf **niemals** werfen: `Config._ensure_unconfigure` fängt Hook-Ausnahmen nicht, eine entkommende Ausnahme ergäbe einen Traceback mit Exit 1 = „killed“ (neuer False-Kill-Kanal). Deshalb vollständig gekapselt.
- Keine neuen Importe nötig (`os`, `Path`, `pytest`, `atomic_write_bytes` sind im Plugin vorhanden – mit Serena bestätigen).

**U3 – Escape-Falle:** `_PYTEST_PHASE_GUARD_SOURCE` ist ein **nicht-roher** `'''`-String (`worker.py:160`). Ein im Quelltext von `worker.py` geschriebenes `\n` würde im generierten Plugin zu einem echten Zeilenumbruch mitten in einem String und damit zu einem `SyntaxError` – dann lädt keine pytest-Phase mehr. Im Plugin-Code daher keine Backslash-Escapes; Zeilenende nur über `os.linesep`.

**U4 – Präfixkonstante in `worker.py`:** `_PROOF_PUBLICATION_FAILURE_PREFIX: str = "mutmut-win: execution proof publication failed"` mit Kommentar, dass sie dem Literal im Plugin gleichen muss (per Test gepinnt, T9).

**U5 – Neutralisierungstext (Worker)** als einmal definierte Modulkonstante, gemeinsam für M-008/M-143/M-145:
`"pytest exited 0 without executing a test call; the worker phase was neutralized by pytest arguments/configuration, every selected test was skipped, or the execution proof could not be published"`.
Der gepinnte Teilstring `without executing a test call` bleibt. Exit bleibt 35. Die Kombination aus Meldung und Tail erfolgt gemäß M-145 nach `capture.close()`.

**U6 – Runner** (`runner.py`, `PytestRunner._run_phase_process`, ca. 413-424): Meldung
`f"{phase_name} exited 0 without executing a pytest test call; the phase was neutralized by pytest arguments/configuration, every selected test was skipped, or the execution proof could not be published"`;
die Pins `without executing a pytest test call` bleiben. **Neu:** Die `OrchestratorError` trägt den Tail – `raise OrchestratorError(self._last_diagnostic_output)` (Meldung plus Tail, bereits so zusammengesetzt) statt nur der Meldung. Ohne diese Änderung wäre die Diagnose in clean/stats/coverage schlechter als heute (heute sichtbar als „Clean test run failed with exit code 3“ samt Tail). forced-fail (Exit 1, keine Proof-Prüfung) bleibt unberührt.

**U7 – Nicht ändern:** `status_by_exit_code` (3 → killed bleibt Vertrag), `_QUIET_EXIT_CODES`, `atomic_file` (Retry- und Tripwire-Taxonomie), `_publish_pytest_guard` samt Konversion in `PytestBoundaryError`, das fatal-Tupel in `worker_main`, orchestrator/executor/cli, das `TaskCompleted`-Schema, Token- und Pfaderzeugung. Keine neue Ausnahmeklasse, kein reservierter Exit-Code, kein `pytest.exit` im Hook.

**U8 – Docstrings:**
- a) Hook: Proof einmal nach dem ersten qualifizierenden Call-Report; jeder spätere Report ist nach Erfolg **und** nach Misserfolg ein No-op; ein Publikationsfehler wird einmal mit festem Präfix gemeldet (und am Sessionende wiederholt), entkommt nie in pytest, weil eine entkommende Hook-Ausnahme ein INTERNALERROR (Exit 3 = killed) wäre; der fehlende Proof macht einen sonst sauberen Exit 0 zu „suspicious“.
- b) `prepare_pytest_phase_guard`: Sätze 832-834 **wörtlich stehen lassen**, ergänzen: „This fatal classification covers the parent-side publication of the guard plugin only. The generated plugin publishes the execution proof later inside the pytest child; a failure there is reported on stderr with the prefix `mutmut-win: execution proof publication failed:` and leaves no proof, so an exit 0 is neutralized to suspicious (35) while a non-zero exit keeps its ordinary mapping. It never becomes a pytest internal error.“
- c) Kommentar im finally von `_process_task`, Docstring von `PytestRunner._run_phase_process` (Meldung trägt den Tail).

**U9 – Ausdrücklich nicht Teil von #143:** ein zweiter Publikationsversuch in `pytest_sessionfinish` oder `pytest_runtest_logfinish` (verdoppelt die Capture-Leiter auf bis zu ca. 31,7 s, ändert den Proof-Zeitpunkt, eine ungekapselte Ausnahme dort ergäbe Exit 1 = killed; für Regel 1–3 nicht nötig – Folgeoption nach Messdaten); ein Retry je Report; ein Fatalkanal über einen Kind-Exitcode (auch nicht später in AP-09).

**U10 – Gates:** Ruff check/format 0 Befunde auf allen geänderten Dateien, mypy strict 0, volle pytest-Suite, lint-imports, kanonisches Semgrep-Releasegate (src-Änderung). Gezieltes Mutation-Gate für `worker.py` mit genau `tests/unit/test_runner_sidecar_safety.py`, `tests/unit/test_process_worker.py` und `tests/unit/test_surface_hardening_220.py` als einzigem `--tests-dir` (Engine-Self-Mutation, P-05); für `runner.py` mit seinen Contract-Tests. ≥ 80 % auf geändertem Code; dass die Stringlogik nicht mutiert wird, als Q-07-Lücke dokumentieren.

### 5. Tests

| Nr. | Art | Inhalt |
|---|---|---|
| T1 | neu, rot vor Fix | `tests/unit/test_runner_sidecar_safety.py::test_generated_phase_proof_publication_failure_does_not_raise`: Muster wie `test_generated_phase_proof_publishes_once_per_phase`; vor `runpy.run_path` `atomic_file_module.atomic_write_bytes` durch eine zählende Funktion ersetzen, die `AtomicPublicationRaceError("race")` wirft. Hook gibt `None` zurück, kein Marker, zwei weitere Aufrufe erhöhen den Zähler nicht; `capfd.readouterr().err` enthält genau einmal `mutmut-win: execution proof publication failed: AtomicPublicationRaceError: race`. |
| T2 | neu, Hypothesis | `@given(st.sampled_from([UnsafeAtomicWriteError, AtomicReplaceError, AtomicPublicationRaceError, PermissionError, FileNotFoundError, FileExistsError, OSError, RuntimeError, ValueError]))`: Hook wirft nie, publiziert nicht, versucht genau einmal, genau eine Diagnosezeile mit dem Klassennamen. Je Beispiel frischer runpy-Namespace und `tempfile`-Verzeichnis, Patches über `pytest.MonkeyPatch.context()` im Testkörper (keine function-scope-Fixture). |
| T3 | neu | Writer wirft `KeyboardInterrupt` → propagiert; beide Flags unverändert. |
| T4 | neu | Diagnose-Robustheit: Ausnahme mit werfendem `__str__` → Zeile mit Typnamen; `os.write` auf werfende Funktion gepatcht → weder Hook noch `pytest_unconfigure` werfen; `pytest_unconfigure` nach Erfolg bzw. ohne Report schreibt nichts; nach einem Fehler schreibt es die Zeile erneut (genau zwei Vorkommen). |
| T5 | anpassen | `test_generated_phase_proof_detects_parent_swap_before_outside_write`: `pytest.raises(UnsafeAtomicWriteError)` entfällt; stattdessen: Hook gibt `None` zurück, `outside` bleibt leer, Marker nicht publiziert, stderr nennt `UnsafeAtomicWriteError` und `parent must be a real directory` (Tripwire-Nachweis), zweiter Aufruf ohne neue Zeile. Empfohlen: `_PARENT_CAPTURE_RETRY_DELAYS` per monkeypatch auf `()` (spart 15,85 s). |
| T6 | grün halten | u. a. `test_generated_phase_proof_publishes_once_per_phase`, `test_phase_guard_refuses_redirected_parent_before_outside_write`, `test_parallel_phase_guard_publishers_accept_only_the_identical_winner` (Parent-Publikation – eigentlicher Gegenstand von „never a mutant verdict“), `test_process_worker.py::TestWorkerMain::test_guard_publication_failure_is_fatal_and_stops_worker`, `::test_containment_failure_emits_fatal_completion_and_stops_worker`, `test_surface_hardening_220.py`-Realphasen-Tests. |
| T7 | anpassen | `test_surface_hardening_220.py::test_worker_exit_zero_without_execution_proof_is_suspicious`: Pin `without executing a test call` bleibt, zusätzlich `execution proof could not be published` in `last_output`. |
| T8 | neu (setzt M-145 voraus) | Worker-Ebene mit Fake-Popen, der die Präfixzeile in den Capture-Writer schreibt, `wait()` → 0, kein Proof; `_create_task_job` und `_maybe_start_loop_monitor` gepatcht (M-144-Konvention). Erwartet: 35, `fatal` False, `last_output` enthält Neutralisierungstext **und** Präfixzeile. |
| T9 | neu, Pin | `_PROOF_PUBLICATION_FAILURE_PREFIX` kommt in `_PYTEST_PHASE_GUARD_SOURCE` vor; `compile(_PYTEST_PHASE_GUARD_SOURCE, "_mutmut_phase_guard.py", "exec")` gelingt (Escape-Falle); `pytest_unconfigure` im runpy-Namespace vorhanden. |
| T10 | neu, realer Kindprozess, rot vor Fix | Clean-Phase, deren Testdatei per `monkeypatch.setattr(os, "replace", raiser)` einen `OSError(errno.EIO, "injected")` wirft (kein `EACCES`: das wird `PermissionError` und damit über die Leiter behandelt). Erwartet: `OrchestratorError` mit `without executing a pytest test call`, Nachricht enthält die Präfixzeile und `OSError`, nicht `INTERNALERROR`. Vor dem Fix gibt die Clean-Phase 3 zurück. |
| T11 | neu, realer Kindprozess | wie T10 plus ein zweiter Test `assert False` → Rückgabe 1 (legitimer Kill bleibt), kein `INTERNALERROR`. |
| T12 | neu, realer Worker-Lauf | Muster der Realphasen-Tests: einziger Test patcht `os.replace` (EIO) und besteht → Exit 35 mit Präfixzeile; vor dem Fix Exit 3. |
| T13 | neu | Tail-Test: nach dem Publikationsfehler folgen genügend weitere Ausgabezeilen (> 50), die Präfixzeile steht dennoch im Tail (Re-Emission). |
| T14 | optional, `@pytest.mark.slow` | Auslöser über `monkeypatch.setenv` des Sentinel-Pfads in ein nicht existierendes Verzeichnis (≥ 15,85 s wegen Capture-Leiter). |

Alle neuen Worker-Tests, die `subprocess.Popen` patchen, patchen auch `_create_task_job` (M-144-Konvention).

### 6. Dokumentation und Folgen für abhängige Gruppen

**Dokumentation:**
- `README.md` Statustabelle (ca. Z. 351), Zeile `suspicious`: „Unexpected pytest exit code, or pytest exited 0 without a verified test-call execution proof (neutralized phase, only skipped tests, or a proof publication failure – never counted as a kill); the diagnostic tail is captured“. Mit dem M-143-Wortlaut abstimmen.
- `README.md` ca. Z. 553-556 (Proof einmal je Phase): Halbsatz ergänzen, dass ein Publikationsfehler mit dem Präfix gemeldet wird und „suspicious“ ergibt (in clean/stats/coverage: Abbruch mit Diagnose), nie „killed“; Suiten, die `os.*` per monkeypatch patchen, können das auslösen.
- README-Änderungen gehören in den Fix-Änderungssatz, nicht in den Housekeeping-Commit (`tests/unit/test_release_supply_chain.py`, ca. 1256-1274).
- Release-Notizen (keine CHANGELOG-Datei; README „History and project status“ + GitHub Release): „Behavior change (score correction): a failure to publish the per-phase execution proof inside the pytest child no longer surfaces as a pytest INTERNALERROR (exit 3), which was counted as killed. It is reported on stderr with the prefix `mutmut-win: execution proof publication failed` and the mutant is classified suspicious (exit 35), which is never reused. Scores of affected runs may drop.“
- Sprintbericht/MEMORY.md: P-08-Entscheidung M-008 = A und die Taxonomie (Abschnitt „Kohärenz“). Q-07-Lücke dokumentieren.

**Folgen:**
- **M-142:** bleibt Grundlage (inneres `try/finally`, begrenzter Bytevergleich in `consume_pytest_phase_guard`). Fällt der Fehler erst nach dem Replace, liegt der korrekte Token vor, `consume` liefert True, das Ergebnis ist wahrheitsgemäß „survived“.
- **M-145:** harte Voraussetzung im selben Änderungssatz; Neutralisierungstext ist die gemeinsame Konstante.
- **M-143:** derselbe Hook; M-143 ersetzt nur die Filterzeile. One-shot umfasst jetzt auch den Fehlerfall – runpy-/Hypothesis-Tests von M-143 brauchen je Beispiel einen frischen Namespace.
- **Q-06/Q-07:** wie oben.
- **M-065/Q-09:** A braucht keine `WorkerEnvironmentError`. **Q-09 ist anzupassen:** Der „optionale Fatal-Kanal für Proof-Publikationsfehler aus M-008“ über Kind-Exitcode oder Kind-Ausgabe entfällt (Handover Z. 2116 und 2120). M-065 bleibt auf worker-seitige `OSError` und die Run-Root-Validierung (M-146) beschränkt. Eine Laufebenen-Eskalation bei Dauerstörung ist nur als eigene AP-09-Entscheidung mit **parent-seitiger** Evidenz zulässig (Vorschlag: Nach „Exit 0 ohne Proof“ publiziert der Worker selbst probeweise ins eigene `runtime_dir`; scheitert das, `WorkerEnvironmentError`).
- **Restgrenze für AP-09:** `consume_pytest_phase_guard` behandelt worker-seitige Lesefehler (z. B. AV-`PermissionError`) als „kein Proof“ → „suspicious“. Das ist konservativ, muss in AP-09 aber ausdrücklich eingeordnet werden (Vorschlag: `FileNotFoundError` = kein Proof, andere `OSError` optional fatal).

### 7. Offene Punkte für den Auftraggeber

1. Produktentscheidung bestätigen: Eine erst nach der Clean-Phase einsetzende, nur das Sentinel-Blatt treffende Dauerstörung erzeugt „suspicious“-Zeilen ohne Laufabbruch (Lauf „completed“, Gate greift nur mit `--min-score`).
2. Streichung des Kind-Fatalkanals in Q-09 bestätigen.
3. Altbestand: Früher persistierte falsche Exit-3-„killed“ sind wiederverwendbar. Dass der Versionssprung (engine_version bzw. Distributionsversionen im Kontext-Fingerprint) die Wiederverwendung sicher bricht, ist nur indiziell belegt. Entweder per Test belegen (Versionsänderung → anderer `tests_fingerprint` → kein Reuse) oder in den Release-Notizen einen einmaligen Lauf ohne Cache-Wiederverwendung empfehlen.
4. pytest 8.2 bis 8.x ist nicht geprüft; falls der Laufzeitvertrag 8.x zulässt, T10 einmal gegen die niedrigste zulässige Version bestätigen.

---

## Frage 2 – M-003: Degradierte Mutationsfläche

### 1. Verifikationsergebnis: bestätigt

- `src/mutmut_win/file_setup.py`, `create_mutants_for_file` (Review-Stand ab 2077): `except (cst.ParserSyntaxError, cst.CSTValidationError)` um den gesamten `write_all_mutants_to_file`-Aufruf (2213-2226) und `ast.parse`-Fallback (2232-2249) setzen beide `generated = source` und `mutant_names = []` und erzeugen nur eine `SyntaxWarning`; die `.meta` hat ein leeres `exit_code_by_key`.
- `orchestrator.py:1242-1248`: Warnungen werden gedruckt, Dateien ohne Namen per `continue` übersprungen. Nur echte Ausnahmen füllen `generation_errors` und führen fail-closed zu „mutant generation was incomplete; refusing to publish a new universe fingerprint“ (1266-1272).
- `MutationRunResult` hat kein Degradationsfeld; `execution_basis_complete` entsteht nur aus Terminalstatus, Basisevidenz und Deautorisierung (orchestrator.py:521-525); `is_full_run` ist rein filterbasiert (cli.py:714).
- CLI-Gate `cli.py:799-824`: Das Muster „Execution basis incomplete — score gate failed closed“ mit Exit 1 existiert bereits.
- Widerlegungskriterien geprüft, keines greift (kein Degradationsfeld, kein Gate, keine Deautorisierung bei Degradation).
- libcst: `CSTValidationError` kann sowohl beim Parsen (`__post_init__`-Validierung) als auch beim Knotenbau der Engine entstehen; Context7 dokumentiert keinen Ausschluss → neutraler Grund `cst_validation_error`.

### 2. Entscheidung: Variante A

Gate-wirksam: Mit `--min-score` endet ein Lauf mit degradierter Fläche mit spezifischer Meldung und Exit 1; ohne `--min-score` bleibt er ein diagnostischer Lauf mit Exit 0; der CI/CD-Export wird verweigert; die Verdikt-Wiederverwendung bleibt erhalten. Der gemeinsame Kern der Anfrage ist vollständig verbindlich (einschließlich `execution_basis_complete=False` über `surface_complete`).

### 3. Begründung am Regelwerk

- **Regel 1:** Ohne Gate-Wirkung besteht ein Lauf auf einer Teilfläche `--min-score` und wird exportiert – genau „unvollständiges Ergebnis, das als korrekt gilt“ (Risiko 1 des Abschlussberichts). Variante B scheidet damit aus.
- **Innerer Widerspruch von B:** Mit dem verbindlichen gemeinsamen Kern ist `execution_basis_complete` False; das bestehende Gate (cli.py:800-806) endet dann ohnehin mit Exit 1, aber mit der falschen Diagnose „not all execution inputs could be fingerprinted“ und ohne Ausweg. „Exit-Code unverändert“ wäre unwahr (Regel 3).
- **Regel 2:** A ist konservativ, ohne Laufabbruch, mit Diagnose und Ausweg. Die Degradation ist deterministisch (I/O-Störungen enden als Ausnahme in `generation_errors`, nicht als Degradation) – das Gate flattert nicht.
- **Regel 3:** A nutzt nur bestehende Kanäle (CLI-Exit 1 der Gate-Klasse, `evidence_invalidated` für den Export), keine neue Exit-Nummer. Das Produkt verhält sich damit endlich konsistent zu seiner eigenen Regel „refusing to publish“ für unvollständige Generierung.
- **Regel 4:** Gegenüber dem ohnehin verbindlichen Kern fügt A nur eine private CLI-Funktion und Texte hinzu.
- **Regel 5:** Verhaltensänderung gegenüber dem beobachteten, nicht gegenüber dem dokumentierten Verhalten (CI-Gate verspricht ein vollständiges Universum). Einordnung als fail-closed-Bugfix mit Präzedenz (#127 in v2.14.0, leerer Lauf MW220-034). Upstream mutmut 3.5.0 bricht bei ungültigem generiertem Code ab; mutmut-win degradiert seit #78 und entzieht jetzt zusätzlich die Autorität – A liegt näher an Upstream als B.

**Bewertung der zusätzlichen Risiken:**

| Risiko | Bewertung |
|---|---|
| Dauerhaft nicht mutierbare Datei macht jeden `--min-score`-Lauf rot, bis `do_not_mutate` | Tragfähig und gewollt; die Meldung nennt den Ausweg. Realistischer Dauerfall ist ein Engine-Fehler (Pfad b, z. B. CRCR-Klammerverlust M-046 im Default-Profil); Pfad a ist für gültiges Python 3.14 selten (libcst 1.8.6 parst t-Strings, PEP 758, PEP 695). Die Gate-Wirkung macht eine bisher stille Lücke sichtbar. |
| Folgelauf: Fast Path greift bei leerem `exit_code_by_key` nicht, Degradation wird erneut gemeldet | Tragfähig und gewollt (file_setup.py:2181-2187); Kosten nur die Neugenerierung dieser Datei. |
| Laufzeitregress durch breite Deautorisierung | Durch die schmale Revocation vermieden: `tests_fingerprint` bleiben, der Reuse hängt nicht von Basis oder `evidence_invalidated` ab (orchestrator.py:2004-2009). |
| Folgemeldungen raten nur zum Neulauf | Tragfähig; Texte generisch erweitern (U8), keine Schemaänderung. |
| Sechsstelliges Worker-Tupel bricht Entpackstellen | Begrenzt: produktiv nur orchestrator.py:1241; Tests siehe T5. `run_generation_supervised` prüft die Tupelform nicht. |
| Pickling der Warning-Unterklasse | Pickle-sicher bauen (U1), obwohl nur `GenerationDegradation` die Prozessgrenze passiert. |

### 4. Umsetzungsvorgaben (Issue #145)

**U1 – `exceptions.py`:** `class MutationSurfaceDegradedWarning(SyntaxWarning)` mit `__init__(self, reason: str, message: str) -> None`, `super().__init__(reason, message)`, Attributen `self.reason` und `self.detail = message`, `__str__` gibt `message` zurück (pickle-sicher unter CPython 3.14.7). Docstring: Producer `file_setup.create_mutants_for_file`, die drei Gründe, Abgrenzung zu funktionsgranularen Skips (U+01C1-Mangling, Trampolin-Kollision), die einfache `SyntaxWarning` bleiben.

**U2 – `models.py`:** `DegradationReason = Literal["unsupported_source_syntax", "cst_validation_error", "generated_code_invalid"]`; `class GenerationDegradation(BaseModel)` mit `model_config = ConfigDict(frozen=True, extra="forbid")`, Feldern `path: str` (min_length=1), `reason: DegradationReason`, `detail: str`. `MutationRunResult.degraded_files: list[GenerationDegradation] = Field(default_factory=list)` (additiver JSON-Vertrag; alte JSON ohne das Feld validieren zu `[]`). Score und Nenner bleiben unverändert. Pydantic-v2-APIs vorher per Context7 bestätigen (P-19).

**U3 – `file_setup.create_mutants_for_file`:**
- `except`-Zweig: `reason = "unsupported_source_syntax"` bei `isinstance(exc, cst.ParserSyntaxError)` mit unverändertem Text `f"Unsupported syntax in {filename} ({exc!s}), skipping"`; sonst `reason = "cst_validation_error"` mit neutralem Text `f"LibCST rejected the syntax tree for {filename} ({exc!s}), skipping"`.
- `ast.parse`-Fallback: `reason = "generated_code_invalid"`, Text („… do not compile … copying the file unmutated. Please report this as a mutmut-win bug.“) wortgleich.
- In beiden Fällen `message=MutationSurfaceDegradedWarning(reason, text)` und `category=MutationSurfaceDegradedWarning`. Safety-Net-Verhalten (#78: Datei unmutiert gestagt) bleibt. Funktionsgranulare Skips werden **nicht** umgestellt.

**U4 – `orchestrator._create_mutants_worker`:** Rückgabe als 6-Tupel `(rel_path, names, error, warn_msgs, took_fast_path, degradations)`. Die `GenerationDegradation`-Objekte werden per `isinstance(w.message, MutationSurfaceDegradedWarning)` **innerhalb des bestehenden `try`** gebildet, damit ein unbekannter Grund (ValidationError) fail-closed als Fehler in `generation_errors` endet. Fehlerweg: `(rel_path, [], exc, [], False, [])`.

**U5 – `orchestrator`:** `self._generation_degradations` in `__init__` anlegen und zu Beginn von `_generate_mutants` zurücksetzen; nur bei `error is None` sammeln; nach der Schleife nach `(path, reason)` sortieren (deterministische Logs/JSON). Die „Warning:“-Ausgabe bleibt.

**U6 – `orchestrator._run_with_identity`:**
- `result.degraded_files` **zentral** direkt nach `_run_pipeline` setzen, vor der Terminalstatus-Verzweigung (unabhängig von Frühreturns der Pipeline); `surface_complete = not result.degraded_files`.
- `completed`-Zweig: nach dem bestehenden Block zu `basis_changed`/unvollständiger Basis: `if not surface_complete and not execution_basis_deauthorized:` → `revoke_active_run_export_authority(self._db_path, self._active_run_id)` vor `finish_run`. Bei Fehler: `OrchestratorError(f"the mutation surface was incomplete ({n} file(s) could not be mutated) and its evidence authority could not be revoked; the run remains running for revoke-first recovery")`.
- Hinweiszeile bei nicht vollständiger Fläche (auch nach breiter Deautorisierung), **ohne** Reuse-Behauptung: `f"{n} file(s) could not be mutated (mutation surface incomplete); --min-score and CI/CD export are disabled for this run. Exclude them via do_not_mutate to accept the reduced surface."`
- Abschluss: `result.execution_basis_complete = terminal_status == "completed" and basis_evidence.complete and not execution_basis_deauthorized and surface_complete`.
- `deauthorize_active_run_evidence` wird wegen Degradation **nicht** aufgerufen. Bei `interrupted`/`aborted` (auch Totalverlust mit `total_mutants == 0`) keine Revocation; `degraded_files` bleibt zur Sichtbarkeit gesetzt.

**U7 – `db.py`:** neue Funktion `revoke_active_run_export_authority(path: Path, run_id: str) -> None`. Vorbild ist das **erste UPDATE von `deauthorize_active_run_evidence`** (db.py ca. 1728-1737), nicht `invalidate_latest_run_evidence` (dieses arbeitet latest-by-sequence, ohne Active-Run-Schutz, und setzt die Basis nicht auf NULL): `create_db(path)`; `with _write_transaction(path) as conn:` `_require_active_run(conn, run_id)`; `UPDATE mutation_run SET basis_fingerprint = NULL, basis_config_json = NULL, evidence_invalidated = 1 WHERE run_id = ? AND status = ?` mit `RUN_STATUS_RUNNING`; bei `rowcount != 1` `RunStateError`. `mutation_run_mutant.tests_fingerprint` und `mutant.tests_fingerprint` werden **nicht** angefasst. Docstring mit Abgrenzung zu beiden bestehenden Funktionen; Querverweis im Docstring von `deauthorize_active_run_evidence`.

**U8 – `cli.py` (Q-35):**
- private Modulfunktion `_mutation_surface_report(degraded: Sequence[GenerationDegradation]) -> str | None`: leer → `None`; sonst Kopfzeile `f"Mutation surface incomplete — {len(degraded)} file(s) could not be mutated:"`, je Eintrag `f"  - {d.path} ({d.reason})"`, Schlusszeile `"Exclude them via do_not_mutate to accept the reduced surface; if a file is valid Python source, please report it as a mutmut-win bug."`
- Score-Gate: als **erste** Prüfung unter `if min_score is not None` (vor `if not result.execution_basis_complete`): Bericht auf stderr, dann `"Score gate failed closed."`, `sys.exit(1)`. Bewusst unabhängig vom Flag (Tiefenverteidigung).
- Empty-Run-Zweig: den Bericht vor der bestehenden Meldung ausgeben; Exit-Codes 2 bzw. 1 und Texte bleiben.
- Vorrangkette (als Test pinnen): JSON → 130 → aborted 1 → Empty-Run 2/1 → Fläche 1 → Basis 1 → testable 1 → Schwelle 1.
- `_export_cicd_stats_locked` (ca. 1284-1292): Text erweitern auf „Latest mutation run evidence was invalidated because its recorded execution basis is no longer authoritative or its mutation surface was incomplete; re-run 'mutmut-win run' (excluding unmutatable files via do_not_mutate if a run reported them) before CI/CD export.“ Der Teilstring `evidence was invalidated` **muss** bleiben (Pins in `test_run_surface_integration_220.py`).
- `results` (ca. 865-871): Satz ergänzen zu „The recorded execution basis is no longer authoritative or the mutation surface was incomplete; re-run 'mutmut-win run'.“ Präfix `Evidence invalidated: yes; release-ready: no` bleibt (Pin). `browser.py` bleibt unverändert.
- JSON-Ausgabe bleibt rein (Prosa auf stderr).

**U9 – Nicht ändern:** Safety-Net-Charakter (#78), Score-Formel und Nenner, `is_full_run`-Semantik, `generation_errors`-Pfad für echte Ausnahmen, Texte „do not compile“ und „Unsupported syntax“ (für `ParserSyntaxError`), `deauthorize_active_run_evidence`, `invalidate_latest_run_evidence`, `status_by_exit_code`, `dry_run`, funktionsgranulare Skips.

**U10 – Architektur und Gates:** exceptions/models Band 5, db/file_setup Band 3, orchestrator Band 2, cli Band 1 – nur Abwärtsimporte, lint-imports grün. Mutation: `file_setup.py`, `orchestrator.py` und `db.py` nur per gezieltem Gate (Engine-Self-Mutation; `db.py` mit `test_db_state_boundary_220.py` und `test_run_identity_220.py`), `cli.py` gezielt mit der neuen Testdatei (U-T8), `models.py`/`exceptions.py` regulär; ≥ 80 %.

### 5. Tests

| Nr. | Inhalt |
|---|---|
| T1 | `test_mutant_safety_net.py::TestValidateThenWrite::test_invalid_generated_output_falls_back_to_original` erweitern: genau eine Warnung mit `isinstance(w.message, MutationSurfaceDegradedWarning)`, `reason == "generated_code_invalid"`, `issubclass(w.category, SyntaxWarning)`, weiterhin `do not compile` im Text. Rot vor dem Fix. |
| T2 | Neu: Pfad a mit echter Quelldatei `def (:` → `unsupported_source_syntax`, Text `Unsupported syntax in`, Staging unverändert, `mutant_names == []`; Pfad a mit `CSTValidationError` per monkeypatch von `write_all_mutants_to_file` → `cst_validation_error`, Text ohne `Unsupported syntax` und ohne `please report`. |
| T3 | `test_u01c1_identifier_does_not_crash_run` um Negativ-Assert ergänzen: keine `MutationSurfaceDegradedWarning`. `test_mutation_surface_121.py` bleibt grün. |
| T4 | Pickle-Roundtrip für `MutationSurfaceDegradedWarning` (reason, detail, str) und `GenerationDegradation`. |
| T5 | Worker-Tupel: 6. Element im Fallback-Fall gefüllt, sonst `[]`, im Fehlerfall `[]` mit gesetztem `error`. Anpassen: `test_profile.py` (ca. 326, 353), `test_orchestrator.py` (ca. 503-512), `test_review_cache_integrity.py` (ca. 161-165, muss weiter `OrchestratorError` „incomplete“ liefern). |
| T6 | `_generate_mutants` mit Fake-Supervisor: Degradationen zweier Dateien in umgekehrter Reihenfolge → sortiert; Reset bei erneutem Aufruf. |
| T7 | `_run_with_identity` mit Fake-Pipeline: (a) Degradation bei stabiler Basis → `revoke_active_run_export_authority` genau einmal, `deauthorize_active_run_evidence` nicht, `execution_basis_complete` False, Hinweiszeile; (b) Revoke-Fehler → `OrchestratorError` mit „remains running for revoke-first recovery“, Lauf bleibt `running`; (c) Ambient-Drift plus Degradation → nur deauthorize, Flächenzeile ohne Reuse-Behauptung; (d) Totalverlust → aborted, keine Revocation, `degraded_files` gesetzt; (e) ohne Degradation unverändert. |
| T8 | Neue Datei `tests/unit/test_generation_surface_authority.py` (einziges `--tests-dir` für das cli-Gate, Q-35), CliRunner mit gepatchtem `MutationOrchestrator.run`: (1) `killed=4, total=4, execution_basis_complete=True, degraded_files=[…]` mit `--min-score 50` → Exit 1, stderr mit Kopfzeile, Eintragszeile, `do_not_mutate`, `Score gate failed closed.`, **ohne** „not all execution inputs could be fingerprinted“; (2) dasselbe mit `execution_basis_complete=False` → dieselbe spezifische Meldung; (3) ohne `--min-score` → Exit 0, `--output json` reines JSON mit `degraded_files`; (4) Vorrangkette gepinnt. |
| T9 | Exakte String-Asserts für `_mutation_surface_report`; Hypothesis: Zeilenzahl `len + 2`, Reihenfolge erhalten, `None` genau bei leerer Liste; `MutationRunResult`-Roundtrip mit `degraded_files`, Score unabhängig davon, Alt-JSON ohne Feld → `[]`. |
| T10 | DB-Tests der neuen Funktion (`test_run_identity_220.py` bzw. `test_db_state_boundary_220.py`): Basis NULL, `evidence_invalidated=1`, `tests_fingerprint` in beiden Tabellen erhalten, andere Läufe unberührt, `RunStateError` bei fehlendem oder fremdem aktivem Lauf. Integriert: degradierter Lauf → `export-cicd-stats` Exit 1 mit `evidence was invalidated`; stabiler Folgelauf verwendet die Verdikte der nicht degradierten Mutanten wieder (kein Laufzeitregress). |
| T11 | Integrationstest (Windows, echter Spawn) über `run_generation_supervised`: Quelldatei `def (:` erzeugt über die Prozessgrenze eine `GenerationDegradation` mit `unsupported_source_syntax`. |
| T12 | Folgelauf: degradierte Datei nimmt keinen Fast Path und wird erneut gemeldet. |
| T13 | Grün halten: `test_run_surface_integration_220.py::test_mid_run_ambient_drift_preserves_results_without_authority`, `::test_ambient_deauthorization_failure_leaves_run_recoverable`, `test_run_identity_220.py` (ca. 252-266), `test_db_state_boundary_220.py` (ca. 688-693), `test_browser_evidence_invalidation_220.py`, `test_contract_120.py`, `test_interrupt_honesty.py`, `test_pool_collapse_127.py`. |

### 6. Dokumentation und Folgen für abhängige Gruppen

**Dokumentation:**
- README Optionstabelle (ca. Z. 180): `--min-score N` → „exit 1 below N percent, incomplete basis, or incomplete mutation surface“.
- README CI-Gate-Abschnitt (ca. 402-410) und Garantienliste (ca. 316-326): Datei, deren Quelle LibCST nicht parsen kann oder deren generierte Mutanten nicht kompilieren, wird unmutiert gestagt (#78) und in `degraded_files` geführt; `--min-score` und `export-cicd-stats` schlagen fail-closed fehl, bis die Datei per `do_not_mutate` ausgeschlossen ist; ohne `--min-score` diagnostischer Lauf mit Exit 0.
- README Exit-Code-Absatz (ca. 190-194): Exit 1 nennt zusätzlich die unvollständige Mutationsfläche.
- JSON-Vertrag: additives Feld `degraded_files` mit `{path, reason, detail}` und den drei Gründen.
- Releasehistorie: ausdrückliche Verhaltensänderung, eingeordnet als fail-closed-Bugfix mit Verweis auf den dokumentierten CI-Gate-Vertrag und die Präzedenzfälle; Upstream-Divergenz-Notiz.
- Docstrings: `MutationSurfaceDegradedWarning`, `GenerationDegradation`, `MutationRunResult.degraded_files`, `create_mutants_for_file`, `_create_mutants_worker`, `revoke_active_run_export_authority`, Querverweis in `deauthorize_active_run_evidence`.

**Folgen:**
- **AP-21 (db.py, M-037/M-095):** folgt AP-03; die neue Funktion erbt die Umgebungsklassifikation (`CacheEnvironmentError` statt Korruptionsdiagnose). Merge-Reihenfolge AP-03 vor AP-21.
- **Q-35:** Gate-Logik in der privaten Funktion, eigene Testdatei als einziges `--tests-dir`; AP-16 und AP-17 setzen das Muster fort.
- **AP-02/M-034:** Voraussetzung; Zeilen verschieben sich im Arbeitsbranch.
- **M-046 (AP-25):** häufigster Auslöser von Pfad b. Bis zu seinem Fix werden betroffene Projekte mit `--min-score` rot (gewollt); ein Vorziehen von AP-25 ist zu erwägen.
- **Taxonomie:** M-003 gehört zur Klasse „Autoritätsentzug ohne Abbruch“ (wie Ambient-Drift und `type_check_command`); M-065 soll diese Klasse neben „fatal“ und „suspicious“ führen.

### 7. Offene Punkte für den Auftraggeber

1. **Versionseinordnung:** Die README sagt „Breaking changes wait for a major version“; die Präzedenzfälle führen fail-closed-Korrekturen als Bugfix in Minor-Releases. Empfehlung: nicht als Patch 2.21.5, sondern mindestens Minor (2.22.0) mit ausdrücklichem Verhaltenshinweis. Das betrifft auch M-008 und M-144.
2. Die Handover-Karte M-003 (Z. 1342/1349, Einsatz von `deauthorize_active_run_evidence`) und die AP-03-Abnahme (Z. 1302) sind durch die schmale Revocation überholt.
3. Scope-Frage außerhalb von M-003: Sollen funktionsgranulare Skips, die eine Datei ebenfalls auf 0 Mutanten bringen können, gate-relevant werden? Eigenes Issue nach P-14.
4. Optional später: persistente Grundspalte für `evidence_invalidated`, damit `results`, Export und `browse` den Grund exakt nennen. Nicht Teil von M-003.

---

## Frage 3 – M-144: Popen-Doubles und echte Instanzen nach Popen-Ersetzung

### 1. Verifikationsergebnis: bestätigt

- `worker.py:1555-1563` (`_popen_contained`, Kompatibilitätszweig): Auswahl allein per `if subprocess.Popen is not _REAL_POPEN_TYPE:`; `1556` ruft `subprocess.Popen(cmd, **kwargs)` mit unveränderten kwargs (einschließlich `CREATE_SUSPENDED`, das der atomare Pfad in 1571 entfernt); `1557` `job_handle = _create_task_job(proc.pid)` **ohne** `isinstance`-Schranke → `OpenProcess`/`AssignProcessToJobObject` auf der nackten PID (job_object.py ca. 197, 217).
- Schranken existieren nur in `_resume_after_containment` (`worker.py:125`, erst nach der Zuweisung) und im Kill-Pfad (`worker.py:1657`).
- Der CLI-Produktlauf erreicht den Zweig nie: `src/` ersetzt `subprocess.Popen` nirgends; alle Aufrufer (`worker.py:1167`, `runner.py:137`, `runner.py:364`) übergeben das echte Popen; Worker starten per Spawn frisch.
- Öffentliche API: `src/mutmut_win/__init__.py` exportiert nur `__version__`; einziger Entry-Point `mutmut-win = mutmut_win.cli:cli`.
- `type_checking._run_type_check_process` hat einen eigenen Kompatibilitätszweig mit demselben Muster (eigener Import-Capture `type_checking.py:22`, Pfadwahl per Identität `262`, Zuweisung `305-306`, Resume `310`).
- **Stufe 1 bestätigt, mit Präzisierung:** Die Minimalform lässt die fünf Lifecycle-Pins grün; es ändern sich aber **zwei** Assertions (`test_hardening_132.py:78` und `:161`, jeweils `assert_called_once_with(4242)` → `(None)`), und der Aufruf muss positional mit genau einem Argument bleiben, weil vier Fixtures `_create_task_job` durch `lambda _pid: None` ersetzen.

### 2. Entscheidung: Stufe 1 wie beschrieben; Stufe 2 Variante A

Eine echte Popen-Instanz aus einem nach dem Import ersetzten `subprocess.Popen` wird fail-closed verweigert; eine ersetzende Popen-Unterklasse schon vor dem Start. Das gilt im Worker und – gemäß Q-08 – im Kompatibilitätszweig von `type_checking`.

### 3. Begründung am Regelwerk

- **Regel 1** trennt die Varianten nicht: `ProcessContainmentError` ist fatal und wird nie als Verdikt persistiert (orchestrator.py:2142-2147); im Hauptprozess Exit 1.
- **Regel 2 entscheidet:** B sanktioniert einen Pfad, dessen tragende Vorbedingung (der Wrapper reicht `CREATE_SUSPENDED` durch) der Code nicht prüfen kann – `_resume_suspended_process` prüft nur die Thread-Anzahl und `ResumeThread == 0xFFFFFFFF`, nicht den Suspend-Zähler. Verletzt ein Wrapper sie, ist das Ergebnis „meist fatal, manchmal still“ (stille Containment-Degradation, Venv-Launcher-Rennen laut Docstring `worker.py:117-123`). A bricht deterministisch mit Diagnose ab.
- **Regel 3:** A erzwingt die dokumentierte Invariante („no real production child uses that compatibility branch“, Docstring `_popen_contained`; README-Zusage, dass gewöhnliche Subprozesse atomar im Job entstehen) über den bestehenden Fatal-Kanal. B müsste sie abschwächen. Das Argument „keine Bibliotheks-API“ ist symmetrisch (auch B müsste nichts unterstützen) und entlastet nur nach Regel 5.
- **Regel 4:** A bleibt klein (zwei Helfer, zwei Konstanten, wenige Aufrufzeilen, ein Testumbau); der Minimalitätsvorteil von B zählt nicht, weil B an Regel 2 scheitert.
- **Regel 5:** Verhaltensänderung nur für eine nicht unterstützte In-Process-Einbettung; keine Upstream-Divergenz (Job-Containment ist mutmut-win-eigen). Releasehistorie.

**Bewertung der zusätzlichen Risiken:**

| Risiko | Bewertung |
|---|---|
| A bricht Einbettungen mit transparentem Popen-Wrapper | Tragfähig, aber enger als formuliert: Der CLI-Lauf ist nie betroffen; eine Ersetzung **vor** dem Import nimmt den atomaren Pfad (A greift dort nicht); Instrumentierung, die Methoden in place patcht, erhält die Identität. Getroffen wird nur die Ersetzung des Modulattributs nach dem Import. |
| „Keine Bibliotheks-API“ als Begründung | Trägt als Entlastung, ist aber nirgends ausdrücklich dokumentiert → README-Satz nötig (offener Punkt). |
| „Nie Nutzercode“ nur bei durchgereichtem `CREATE_SUSPENDED` | Tragfähig und zu dokumentieren; gilt für A und B gleich. Unter A führt eine Verletzung nie zu Ergebnissen; deshalb Beendigung per `_kill_proc_tree(proc)` statt `proc.kill()`, damit auch Nachfahren erreicht werden. |
| Resume-Echtzweig wird produktiv unerreichbar | Tragfähig und akzeptiert: Code bleibt als Tiefenverteidigung, der Fehlervertrag wird per direktem Unit-Test gepinnt; Entfernen wäre eine Nebenagenda. |
| Restfenster suspendierter Waise bei hartem Elterntod (PROC-02) | Low, inert, kein Ergebnis; unter A für Klassen-Wrapper geschlossen (Vorprüfung), für Funktions-Wrapper gleich lang. |

### 4. Umsetzungsvorgaben (Issue #149)

**Commit 1 – Stufe 1 (entscheidungsfrei, zuerst):** `worker.py`, Kompatibilitätszweig: `job_handle = _create_task_job(proc.pid if isinstance(proc, _REAL_POPEN_TYPE) else None)` – positional, genau ein Argument. Im selben Commit `test_hardening_132.py:78` und `:161` auf `job.assert_called_once_with(None)`; neuer Spy-Regressionstest (T1).

**Commit 2 – Stufe 2 / Variante A:**
- Modulkonstanten in `worker.py`:
  - `_REPLACED_POPEN_REFUSAL = "subprocess.Popen was replaced after import; refusing the non-atomic containment path for a real process"` (wortgleich zur Anfrage),
  - `_REPLACED_POPEN_SUBCLASS_REFUSAL = "subprocess.Popen was replaced after import by a Popen subclass; refusing the non-atomic containment path before starting a real process"`.
  Beide teilen das Testanker-Präfix `subprocess.Popen was replaced after import`.
- Helfer (privat, Google-Docstring, voll typisiert; Referenztyp als Parameter, damit `type_checking` seinen eigenen erfassten Typ übergibt):

```python
def _refuse_replaced_popen_subclass(real_popen_type: type[subprocess.Popen[bytes]]) -> None:
    current: object = subprocess.Popen
    if sys.platform != "win32" or current is real_popen_type:
        return
    if isinstance(current, type) and issubclass(current, real_popen_type):
        raise ProcessContainmentError(_REPLACED_POPEN_SUBCLASS_REFUSAL)


def _refuse_real_process_from_replaced_popen(
    proc: subprocess.Popen[bytes], real_popen_type: type[subprocess.Popen[bytes]]
) -> None:
    if sys.platform != "win32" or not isinstance(proc, real_popen_type):
        return  # Test-Doubles tragen keine Prozessidentität
    with contextlib.suppress(Exception):
        _kill_proc_tree(proc)
    raise ProcessContainmentError(_REPLACED_POPEN_REFUSAL)
```

  Die Typschranke `isinstance(current, type)` ist Pflicht: `issubclass(MagicMock(), X)` und Funktionen würfen sonst `TypeError`. `_kill_proc_tree(proc)` ohne Job-Argument aufrufen; die Signatur nach der M-009-Änderung mit Serena prüfen.
- Kompatibilitätszweig von `_popen_contained`, Reihenfolge verbindlich:
  1. `_refuse_replaced_popen_subclass(_REAL_POPEN_TYPE)` **vor** `subprocess.Popen(...)`,
  2. `proc = subprocess.Popen(cmd, **kwargs)` mit unveränderten kwargs (`CREATE_SUSPENDED` bleibt; Pin `test_robustness_123.py:309-314`; bestehendes `noqa S603` beibehalten),
  3. `_refuse_real_process_from_replaced_popen(proc, _REAL_POPEN_TYPE)` unmittelbar danach und **vor** jeder Job-Erzeugung (kein Handle-Leck bei Ablehnung),
  4. unverändert der Stufe-1-Ausdruck `_create_task_job(proc.pid if isinstance(proc, _REAL_POPEN_TYPE) else None)` als Tiefenverteidigung (der unter A unerreichbare True-Zweig ist als äquivalenter Überlebender zu dokumentieren),
  5. der `try/_resume_after_containment`-Block bleibt unverändert.
- `type_checking._run_type_check_process`, nicht-atomarer Zweig: beide Helfer im bestehenden funktionslokalen Importblock aus `mutmut_win.process.worker` importieren (schichtkonform, Band 3 → Band 4); **innerhalb** des bestehenden `try`: `_refuse_replaced_popen_subclass(_REAL_POPEN_TYPE)` vor `subprocess.Popen(type_check_command, **popen_kwargs)`, danach `_refuse_real_process_from_replaced_popen(process, _REAL_POPEN_TYPE)` – jeweils mit dem **eigenen** `_REAL_POPEN_TYPE` von `type_checking` (Z. 22), konsistent zur Pfadwahl in Z. 262. Der bestehende `except`-Zweig schließt Writer und Job und reicht die `ProcessContainmentError` weiter. Das Stufe-1-Analogon für Doubles in `type_checking` ist **nicht** Teil von M-144 (bräche `test_type_checking.py:470`).
- **Nicht ändern:** atomare Pfade (`worker.py:1565-1586`, `AtomicJobPopen`-Zweig in `type_checking`), Import-Captures, die Schranken 125/1657, den `pid`-Parameter von `_create_task_job` (Integrationstest `test_kill_proc_tree`), `_resume_after_containment`/`_resume_suspended_process`.
- **Exit-Codes und Meldungen (keine neuen Codes):** Worker → `WORKER RECOVERY` auf stderr, `TaskCompleted(exit_code=35, fatal=True)`, nicht persistiert, `run_aborted`, CLI Exit 1; Hauptprozess (Collection, Clean-, Stats-, Coverage-Phase, Typprüfer) → `Error: subprocess.Popen was replaced after import; …`, Exit 1, bei `--output json` JSON-Fehler mit Code 1.
- **Gates:** Ruff, mypy strict, lint-imports, vollständiges pytest, kanonisches Semgrep-Gate (src-Änderung, Prozess-Kill). Mutation: `worker.py` gezielt mit genau `tests/unit/test_process_worker.py` als einzigem `--tests-dir` (Engine-Self-Mutation; deshalb gehören alle neuen Worker-Helfertests in diese Datei), `type_checking.py` mit `tests/unit/test_type_checking.py`; ≥ 80 %; Integrationstests mit echten Prozessen nicht in den Mutationslauf.

### 5. Tests

| Nr. | Inhalt |
|---|---|
| T1 | Neu (Stufe 1, win32): `test_popen_contained_never_assigns_a_test_double_pid_to_a_job` – Autouse-Fixture im Test überschreiben (originales `_create_task_job` wiederherstellen), `job_object.create_kill_on_close_job` → 99, `assign_process_to_job` als Spy, `subprocess.Popen` liefert Double mit `pid=12345`; `assign.assert_not_called()`. Vor dem Fix deterministisch rot. |
| T2 | Anpassen: `test_hardening_132.py:78` und `:161` → `(None)`. Grün bleiben die fünf Lifecycle-Pins (`test_hardening_132.py` ca. 82-183, `test_runner.py` ca. 126-141). |
| T3 | Umbau (A): `test_process_worker.py::TestWorkerMain::test_real_task_resume_failure_is_fatal_and_stops_worker` (242-271) bricht unter A. Aufteilen in (a) `test_real_instance_from_replaced_popen_is_fatal_and_stops_worker` (`_REAL_POPEN_TYPE → object`, Popen liefert `fake_proc`, `_kill_proc_tree` und `_create_task_job` gepatcht; erwartet: 35, `fatal` True, `ProcessContainmentError` und `replaced after import` in `last_output`, `_kill_proc_tree.assert_called_once_with(fake_proc)`, `_create_task_job.assert_not_called()`, Sentinel nicht konsumiert) und (b) `test_resume_after_containment_failure_closes_job_and_raises` direkt auf den Helfer (Resume-Fehler → `ProcessContainmentError` mit `resume`, `close_job(77)`; zusätzlich Fall `job_handle is None` → `proc.kill` und `Job Object`). |
| T4 | Neu (win32): `test_popen_contained_refuses_popen_subclass_before_start` – Unterklasse von `subprocess.Popen`, deren `__init__` `pytest.fail` ruft, als `subprocess.Popen` gesetzt → `ProcessContainmentError` mit `Popen subclass`, kein Start, kein Job. |
| T5 | Neu, Hypothesis: `_refuse_replaced_popen_subclass` mit `st.one_of(st.integers(), st.text(), st.builds(MagicMock), st.just(lambda *a, **k: None))` als Popen-Ersatz wirft weder `TypeError` noch `ProcessContainmentError` (Monkeypatch per Kontextmanager im Beispiel). Gegenprobe: `Popen = MagicMock(return_value=MagicMock(pid=12345))` → Double-Pfad ohne `TypeError`. |
| T6 | Neu (win32, `test_type_checking.py`): echte Instanz aus ersetztem Popen → `ProcessContainmentError` mit `replaced after import`, `_assign_type_checker_to_job` nie aufgerufen, `_close_type_checker_job` genau einmal mit dem Sentinel; Popen-Unterklasse → Ablehnung vor dem Start. Die bestehenden `TestBoundedProcessRunner`-Tests bleiben grün. |
| T7 | Neu, Integration (win32, nicht im Mutationslauf): Funktions-Wrapper um den echten Popen, der die `creationflags` aufzeichnet und die echte Instanz festhält; das Kind-Skript würde als erste Anweisung eine Markerdatei schreiben. `_popen_contained(...)` wirft `ProcessContainmentError`; aufgezeichnete Flags enthalten `CREATE_SUSPENDED`; `instanz.poll() is not None`; Markerdatei existiert **nicht** (belegt „kein Nutzercode“ unter der dokumentierten Vorbedingung). |
| T8 | Grün halten: `test_robustness_123.py:309-314`, `test_process_worker.py:195-215`, `tests/integration/test_kill_proc_tree.py::TestKillProcTreeOrphans::test_job_reaps_grandchildren_across_dead_intermediates`, `test_type_checking.py:454-471`, `tests/integration/test_success_process_tree_cleanup.py`, die fünf 12345-Auslöser (`test_extra_paths.py:111`, `test_windows_path_alias_221.py:113`, `test_hardening_132.py:266/370/375`). |

### 6. Dokumentation und Folgen für abhängige Gruppen

**Dokumentation:**
- Docstring `_popen_contained`: Der Kompatibilitätszweig dient nur Popen-Test-Doubles, deren synthetische PID nie einen Job erreicht; eine echte Instanz aus einem nach dem Import ersetzten Popen wird mit `ProcessContainmentError` abgelehnt, eine ersetzende Unterklasse schon vor dem Start; „kein Nutzercode“ gilt nur, wenn der Ersatz `CREATE_SUSPENDED` durchreicht, sonst beendet `_kill_proc_tree` den Baum nach bestem Vermögen.
- Docstring `_create_task_job`: `pid` nur für echte, noch suspendierte Prozesse (Integrationstest); Doubles übergeben `None`.
- Docstring `_resume_after_containment`: kein Produktionspfad erreicht mehr den Echtprozess-Zweig; bleibt Tiefenverteidigung.
- Kommentar zu `_REAL_POPEN_TYPE` (worker.py ca. 57-59), Docstring `job_object.assign_process_to_job` (beschreibt den PID-Pfad noch als Produktionspfad), Kommentar und Raises-Abschnitt in `type_checking`, veralteter Testkommentar „exactly as _process_task does“ in `tests/integration/test_kill_proc_tree.py:79`.
- README-Releasehistorie: Unter Windows wird ein nach dem Import ersetztes `subprocess.Popen`, das echte Prozesse liefert, fail-closed abgelehnt (Exit 1); bisher lief es still über einen nicht-atomaren Assign-then-Resume-Handshake; Test-Double-PIDs erreichen keine Kernel-Job-Operation mehr.
- README-Satz nach Bestätigung durch den Auftraggeber: mutmut-win ist ausschließlich als CLI unterstützt; es gibt keine Bibliotheks-API; In-Process-Einbettung mit ersetztem `subprocess.Popen` wird abgelehnt. README ca. 448-450 („ordinary subprocesses are born atomically inside the Job“) bleibt unverändert und wird durch A erzwungen.

**Folgen:**
- **M-009:** verträglich. Die Erfassung der Root-`create_time` nach `_popen_contained` darf nur für `isinstance(proc, _REAL_POPEN_TYPE)` laufen (produktiv nur `AtomicJobPopen`). Beide Gruppen ändern `worker.py` und `type_checking.py`: gemeinsam im AP-07-Branch, M-144 zuerst.
- **Q-08:** in der stärksten Form umgesetzt (Kompatibilitätszweige lassen keine echten Prozesse mehr durch; gleiche Wrapper-Schranke in worker **und** type_checking).
- **Stufe-1-Pins:** fünf Pins grün, zwei Assertions geändert; `lambda _pid: None`-Fixtures erzwingen den positionalen Aufruf.
- **M-065/Q-09:** „Nach dem Import ersetztes `subprocess.Popen`“ als fatale Hostbedingung (Kanal `ProcessContainmentError`) in die Taxonomie aufnehmen. `ProcessContainmentError` ist keine `OSError` und wird auch nach M-065 nicht in `WorkerEnvironmentError` umverpackt – dazu nach M-065 einen Test führen.

### 7. Offene Punkte für den Auftraggeber

1. Produktaussage bestätigen: „mutmut-win ist ausschließlich als CLI unterstützt; In-Process-Einbettung mit nach dem Import ersetztem `subprocess.Popen` wird fail-closed abgelehnt“ (README-Satz und Releasehistorie).
2. Genügt im Worker-Pfad die generische CLI-Meldung „Run aborted: worker pool collapsed“? Der Detailtext steht in `executor.abort_reason`; eine Änderung wäre ein eigenes Issue.
3. Späteres Aufräum-Issue: Unter A werden der Echtprozess-Teil von `_resume_after_containment`, `_resume_suspended_process` und `_assign_type_checker_to_job` für echte Prozesse produktiv unerreichbar; sie bleiben in AP-07 bestehen.

---

## Kohärenz der drei Entscheidungen

**Exit-Code-Landschaft:** Keine neue Nummer; `status_by_exit_code` und die internen Codes bleiben unverändert (Pins in `test_constants.py` bleiben grün).
- M-008 A erzeugt nur Verdikt-35 („suspicious“) über die bestehende Neutralisierung 0 → 35.
- M-144 A erzeugt nur Fatal-35 (`TaskCompleted(exit_code=35, fatal=True)`): nie persistiert, Laufabbruch, CLI Exit 1; im Hauptprozess Exit 1.
- Die vorbestehende Doppelrolle von 35 löst das `fatal`-Flag, das beide Konsumenten zuerst prüfen (orchestrator.py:2142, executor.py ca. 335; gepinnt in `test_orchestrator.py` ca. 920-945). Es entsteht keine neue Doppelbedeutung.
- M-003 A nutzt den CLI-Exit 1 der bestehenden Gate-Klasse. Der CLI-Raum bleibt 0/1/2/130.

**Taxonomie (als Vertragsregel festschreiben, M-065/AP-09 übernimmt sie):** Trennkriterium ist die Zuordenbarkeit entlang der Prozessgrenze.

| Klasse | Bedeutung | Mitglieder |
|---|---|---|
| **F – fatal mit Laufabbruch** | parent-/worker-seitige, vom Mutanten unabhängige Grenz-, Containment- und Umgebungsfehler | `ProcessContainmentError` (bestehend und M-144 A), `PytestBoundaryError` aus `_publish_pytest_guard`, später `WorkerEnvironmentError` (M-065), Runner-Phasenfehler als `OrchestratorError` (inkl. M-008 in clean/stats/coverage) |
| **S – suspicious je Mutant** | kind-seitige Evidenzlücken, die Test- oder Mutantencode auslösen kann | Exit 0 ohne Proof (M-008-Publikationsfehler, Neutralisierung, Skips aus M-143), Guard-`UsageError` im Kind (Exit 4) |
| **A – Autoritätsentzug ohne Abbruch** | Lauf „completed“, Verdikte bleiben, Gate und Export werden entzogen | M-003 (schmal, Reuse bleibt), Ambient-Drift, diagnostic-only-Basis, `type_check_command` (breit) |

Grundsatz: **Kein Signal aus dem pytest-Kind (Exitcode, Ausgabe) darf einen Fatalpfad öffnen**, weil es vom Mutanten beeinflussbar bzw. fälschbar ist.

**Score-Gates und Export:** Nach den drei Entscheidungen kann im Rahmen der drei Behauptungen kein unvollständiges oder verfälschtes Ergebnis `--min-score` oder den CI/CD-Export bestehen:
- M-008: Der falsche, wiederverwendbare Exit-3-Kill entfällt; „suspicious“ senkt den Score und wird neu ausgeführt.
- M-003: Der Flächencheck steht als erste Prüfung unter `--min-score`; `execution_basis_complete` wird über `surface_complete` False; die schmale Revocation verweigert den Export, erhält aber den Reuse.
- M-144: Der Abbruch erfolgt vor jedem Gate.

**Bedingungen dafür:** (1) `pytest_unconfigure` ist vollständig gekapselt (sonst Exit 1 = killed); (2) das Plugin-Literal enthält keine Backslash-Escapes; (3) `degraded_files` wird zentral gesetzt, Degradation nur per `isinstance` auf die typisierte Warnung erkannt; (4) der Kind-Fatalkanal in Q-09 ist gestrichen.

## Korrekturen an den Issues und am Handover (vor Umsetzungsbeginn übernehmen)

Weil die Issues 1:1 umgesetzt werden, würden die folgenden Abweichungen der bisherigen Vorlagen die Entscheidungen verwässern:

- **#143 (M-008):**
  - Nicht „Docstring ‚never a mutant verdict‘ wird angepasst“, sondern: Sätze 832-834 bleiben wörtlich, eine Abgrenzung wird ergänzt (U8b).
  - Neu verbindlich: gekapselte Re-Emission in `pytest_unconfigure`, keine Backslash-Escapes im Plugin-Literal, Tail in der Runner-`OrchestratorError`.
  - Der optionale Zweitversuch in `pytest_sessionfinish` ist nicht Teil von #143.
- **#145 (M-003):**
  - Die Vorlage nennt die schmale Revocation, lässt aber `execution_basis_complete=False` über `surface_complete` weg; beides ist verbindlich.
  - Vorbild der Revocation ist das erste UPDATE von `deauthorize_active_run_evidence`, nicht `invalidate_latest_run_evidence`.
  - Namen einheitlich: `revoke_active_run_export_authority`, `_mutation_surface_report`, `GenerationDegradation` frozen/`extra="forbid"`, Gründe `unsupported_source_syntax` / `cst_validation_error` / `generated_code_invalid`.
- **#149 (M-144):**
  - Beendigung per `_kill_proc_tree(proc)` in `contextlib.suppress`, nicht `proc.kill(); proc.wait(timeout=2)`.
  - Die Klassen-Vorprüfung braucht `isinstance(subprocess.Popen, type)` vor `issubclass`.
  - Die Wrapper-Schranke gilt auch im `type_checking`-Kompatibilitätszweig (Q-08).
  - Zwei `(4242)`-Assertions ändern sich, nicht eine.
- **Handover:**
  - Q-09 und die AP-09-Karte (Z. 2116, 2120): Der „optionale Fatal-Kanal für Proof-Publikationsfehler (M-008)“ entfällt.
  - AP-03-Karte/Abnahme (Z. 1302, 1342, 1349): Der Einsatz von `deauthorize_active_run_evidence` ist durch die schmale Revocation überholt.
  - P-08-Liste: M-003, M-008 und M-144 Stufe 2 sind entschieden.

## Gesammelte offene Punkte für den Auftraggeber

1. **Versionseinordnung:** mindestens Minor (2.22.0) statt Patch 2.21.5 empfohlen, weil M-008, M-003 und M-144 beobachtbares Verhalten ändern (fail-closed-Korrekturen mit Präzedenz; README verlangt Breaking Changes erst in Major-Versionen).
2. **M-008:** Restrisiko der Dauerstörung nach der Clean-Phase bestätigen; Streichung des Kind-Fatalkanals in Q-09 bestätigen; Altbestand falscher Kills per Test belegen oder in den Release-Notizen einen Lauf ohne Wiederverwendung empfehlen.
3. **M-144:** Produktaussage „nur CLI unterstützt“ bestätigen.
4. **Neue Kandidaten nach P-14** (nicht in #143/#145/#149, jeweils als „unverifiziert“ anlegen):
   - Kind-Exitcodes 33–38 aus Testcode werden ungeprüft übernommen (z. B. `os._exit(34)` → „skipped“, fällt aus dem Nenner).
   - Funktionsgranulare Skips bleiben ohne Gate-Wirkung.
   - `_maybe_purge_stale` löscht historische Zeilen einer nun degradierten Datei.
   - `dry_run` zählt Mutanten ohne `ast.parse`-Prüfung.
   - Eine Popen-ähnliche Fremdklasse (keine Unterklasse) lässt das suspendierte Kind bis zum Timeout hängen.
   - `type_checking`-Tests mit PID 124/126 erreichen psutil-Kill/-Traversal ohne Schranke (Q-08/M-009).
   - Die CLI-Abbruchzeile nennt `executor.abort_reason` nicht.
5. **Werkzeug:** Der gemeinsame Serena-Server ist auf das Arbeitsrepository aktiviert; für künftige Review-Agenten auf dem Review-Stand ist die Bindung vorab zu klären.
