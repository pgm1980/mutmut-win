# BUGFIXUNG ROADMAP – mutmut-win 2.20.0 → 2.21.0

**Stand:** 2026-08-31
**Quelle:** [ANALYSE_MUTMUTWIN220.md](ANALYSE_MUTMUTWIN220.md)
**Ziel:** False Greens und Daten-/Sourceintegrität zuerst schließen, dann Prozessrobustheit und Releasehygiene.

**Arbeitsbaum:** frischer Clone unter `<repository root>`, Branch `fix/360-review-hardening`, abgezweigt von `main` bei `6cb727d`.
**Aktueller Stand:** Drei adversariale Review-Wellen plus finaler Multi-Agenten-Diff-/Claim-Reaudit, unabhängiger pytest-/Execution-Basis-Reaudit und adversarialer Finalgate-/Dogfood-/Security-Reaudit haben 111 fortlaufende Befunde ergeben: 30 P0, 53 P1 und 28 P2. MW220-001 bis -111 sind lokal implementiert und gezielt beziehungsweise deterministisch belegt. MW220-090 bis -104 härten das Semgrep-/Releasegate, MW220-105 schließt den Ready-PID-Testharness-Race, MW220-106 normalisiert checkoutabhängige Textbytes, MW220-107 macht Audit-Hashprovenienz und Gatesnapshots reproduzierbar, MW220-108 korrigiert den vollständigen maschinen-gelesenen Live-State, MW220-109 synchronisiert die Installationsautoritäten, MW220-110 repariert den Standalone-Harness-Lock und MW220-111 entfernt die ausführbare Raw-/Teilscan-Semgrep-False-Green-Autorität aus Hooks und aktiven Entwicklerverträgen. Der vollständige Post-MW220-111-Kandidatenbaum bestand zweimal mit jeweils 2.000 Tests und 44 Skips; der warme `.venv`-Vor-/Nachdigest ist byteidentisch. Finaler Dogfood-Recheck, kanonisches Semgrep-Gate, reproduzierbarer Doppelbuild und Git-owned Inventar sind ebenfalls grün. GitHub-CI wird auf ausdrückliche Nutzeranweisung wegen des Billing-Problems übersprungen und nicht als PASS gewertet. Commit, Push, PR-Integration, Tag `v2.21.0` und GitHub-Release sind autorisiert, aber noch nicht erfolgt.

Der lokale Legacy-ZIP-Arbeitsbaum wurde byte- und inventarbasiert vollständig in den Clone migriert und enthält keine exklusiven relevanten Dateien. Autoritativ und allein bearbeitet wird `<repository root>`; der Legacy-Baum ist keine zweite Source of Truth.

## 1. Verbindliche Regeln

1. Unsicheres Mapping bedeutet Vollsuite oder unchecked, niemals no tests.
2. Stats-/Verdict-Reuse und CI-/Release-Autorität sind nur bei vollständig nachgewiesener Source-, Test-, Konfigurations-, Dependency-, Environment-, Import-, Runtime- und Prozessbasis gültig; unvollständige Evidenz deaktiviert Reuse und CI-Export fail-closed.
3. Eine Phase committed Fingerprint und Runzustand erst nach vollständigem Erfolg.
4. Pfade außerhalb des Projektroots benötigen einen expliziten isolierten Mechanismus.
5. Timeout bedeutet beendeter Prozessbaum und geschlossene Ressourcen.
6. Kein Fix gilt ohne positiven Regressionstest und negativen Grenztest als erledigt.
7. Ein fokussiert grüner Testlauf ist Implementierungsevidenz, aber kein Ersatz für das Finalgate des quieszenten Gesamtbaums.

## 2. Welle A – P0 False-Green-Gates

### A1. Einheitliche pytest-Basis

**Status: umgesetzt.** Selektionsargumente werden zentral validiert und durch alle Eltern- und Workerphasen geführt; nicht beweisende Collection-/Terminalmodi scheitern geschlossen.

- pytest_add_cli_args_test_selection an Clean, Stats, Coverage, Forced-fail und Worker weiterreichen.
- pytest-Kommandobau zentralisieren.
- collect_tests mit Returncodeprüfung, Timeout und Tree-Reaping versehen.
- Exitcode 2/4/5 darf den Stats-Cache nicht als Testlöschung verändern.
- terminale beziehungsweise phasenneutralisierende Optionen wie --collect-only, --help und --version validieren/verbieten.
- E2E-Beweis mit tests/e2e_projects/config.

**Exit:** Alle Phasen nutzen dieselbe Selektion; Collect-Fehler sind diagnostizierter Abbruch oder konservativer Fallback.

### A2. Autoritatives Stats-/Verdict-Mapping

**Status: umgesetzt.** Mapping besitzt eine explizite Autorität; unsichere oder fehlgeschlagene Erhebung fällt auf die volle selektierte Suite zurück. Stats und Reuse teilen einen SHA-256-Kontextdigest.

- Kontextdigest aus Source, relevanten Test-/Helperdateien und mappingrelevanter Konfiguration bilden.
- direkte Testfingerprints von mtime:size auf SHA-256 umstellen.
- alte Daten ohne Schema-/Kontextdigest invalidieren.
- bei fehlgeschlagenem Refresh alte Datei nur forensisch behalten, aktuellen Lauf aber mit leerem nichtautoritativen Mapping/Vollsuite fortsetzen.
- Collection-/Import-Hits konservativ der Vollsuite zuordnen.
- Kindprozess-/xdist-Mapping per IPC/Artefakt-Merge lösen oder diese Modi explizit als nichtautoritative Vollsuite behandeln.
- Verdict-Reuse an denselben Kontextdigest binden.
- Stats atomar schreiben.

**Exit:** Source-, Helper-, Konfig- und same-size/same-mtime-Änderungen verhindern alte no-tests-/Reuse-Entscheidungen.

### A3. Transaktionale Mutantengeneration

**Status: umgesetzt.** Source- und Universe-Digests sind autoritativ; Fingerprint, generierte Datei und Meta werden erst nach vollständigem Erfolg veröffentlicht.

- source_hash und Universe-Fingerprint in .meta einführen; alte Meta ohne Hash invalidieren.
- Mirror und Source-Fast-Path inhaltsbasiert machen.
- do_not_mutate_patterns und kanonisierte Covered Lines fingerprinten.
- Config-Fingerprint nur read-only vergleichen und nach vollständigem Erfolg atomar committen.
- Output und Meta pro Datei gemeinsam über Tempdateien veröffentlichen.
- unerwartete Dateifehler als Phasenfehler behandeln.

**Exit:** Fault Injection kann keinen neuen Fingerprint mit altem/partiellem Universe hinterlassen.

### A4. Pfad- und Apply-Integrität

**Status: umgesetzt.** Aufgelöste Containmentgrenzen gelten für Mutation, Spiegelung, Symlinks/Junctions, Apply und `--force`; interne Toolbäume, Dotenv-Secrets und kanonische Run-Lock-Artefakte werden nicht automatisch gestaged (MW220-039).

- paths_to_mutate nach resolve gegen Projektroot prüfen.
- mutants, Cache- und Umgebungsverzeichnisse beim Walk prunen.
- jedes berechnete Ziel unabhängig gegen den mutants-Root prüfen.
- apply nur bei aktuellem Source-Hash erlauben.
- Punkt-, Parent-, Symlink- und same-size/same-mtime-Grenztests.

### A5. Trampolin-, Regex- und Pragma-Semantik

**Status: umgesetzt.** Definition-Time-Semantik, Generatorart, sichere Regex-/Pragma-Verarbeitung und Dedup sind regressionstestgedeckt. Wiederholte gleichnamige Definitionen verwenden eine reversible Ordinalidentität.

- interne Funktionen ohne erneut evaluierte Defaults, Annotationen und Decorators emittieren.
- öffentlichen Docstring, Signatur und Definition-Time-Evaluation einmal erhalten.
- feste Wrapper-Lokale vermeiden und Helperbinding kollisionsfest machen.
- Sync-/Async-Generatorart oder konservativen Nichtmutationspfad erhalten.
- Regex über evaluated_value mutieren, sicher literalisieren und Kandidaten einzeln syntaktisch prüfen.
- Pragmas nur aus COMMENT-Tokens lesen.
- gerenderten Funktionscode gegen Original und unter Kandidaten deduplizieren.
- Deklarationsnamen vom Name-Operator ausschließen; doppelte Definition-IDs stabilisieren.

**Exit:** Side-effect-, Docstring-, Parameter-, Generator-, Quote-/Backslash-, String-Pragma- und Dublettentests grün.

## 3. Welle B – Prozess- und Runzustand

### B1. Bounded Prozessbäume

**Status: umgesetzt und subsystembezogen verifiziert; Gesamtfinalgate siehe Abschnitt 12.** Generation läuft hinter einem eigenen Supervisor mit No-Progress-Deadline; Runner, Worker und Typechecker verwenden begrenzte Ausgabeerfassung und reapen den gesamten erreichbaren Prozessbaum bei Timeout, Fehler und Interrupt. Der MW220-040-Race ist geschlossen: Nach gesetztem Stop beginnt garantiert ein weiterer Drain-Pass, sodass bereits geschriebene Forced-Fail-Diagnostik erhalten bleibt.

- Executor-Watchdog pro Worker/Progresszustand statt dauerhaftem any_task_pulled.
- Mischfall ein Worker fertig/einer im Bootstrap hängend begrenzt abbrechen.
- Typechecker über Popen plus Job Object/psutil-Prozessbaum ausführen.
- Generation-Pool mit Deadline, Fortschrittswatchdog und kontrolliertem Abbruch.
- KeyboardInterrupt/BaseException in Runner/Coverage reap-en.
- Logcapture begrenzen oder rotieren.

### B2. Run-Identität und Parallelität

**Status: umgesetzt.** Ein Versuch wird vor der Generation persistiert, der exakte Plan danach genau einmal finalisiert. Aktuelle Abfragen werden ausschließlich aus dem aktuellen Run-Snapshot beantwortet; historische Verdicts sind nur Reuse-Daten. Ein kanonischer, aus dem aufgelösten DB-Pfad abgeleiteter Lock schützt Run, `--force`, Apply und Export.

- exklusiven Workspace-Run-Lock mit Besitzerdiagnostik einführen.
- geplante Mutanten vor Dispatch pending markieren.
- Run-ID, Generation und Completion-Status in SQLite migrieren.
- Result-Reuse als separaten Cache behandeln.
- results, Browser und CI-Export unterscheiden aktuell abgeschlossen, aktuell ungeprüft und historisch.
- unknown-Completions als unchecked zählen; Summary-Invariante testen.

**Exit:** Interrupt, Poolkollaps und paralleler Start können keine alten Verdicts als aktuellen vollständigen Lauf darstellen.

## 4. Welle C – Release- und Testhygiene

### C1. Paketinhalt

**Status: implementiert; MW220-105-Arbeitsbaumsnapshot artefaktbelegt, Post-MW220-111- und integrierter Rebuild ausstehend.** Hatch verwendet eine Sdist-Allowlist. `LICENSE` enthält ISC, den übernommenen BSD-3-Clause-Text und für die CPython-abgeleiteten Spawnadapter den vollständigen PSF-2.0-Text samt Copyright-Hinweis und Änderungszusammenfassung; die Paketmetadaten verwenden `ISC AND BSD-3-Clause AND PSF-2.0` (MW220-035/-072). Wheel/Sdist werden nach der LF-/Testnachschärfung und nochmals vom integrierten Releasecommit gebaut, inventarisiert und bytegenau gegen die Lizenzdatei geprüft.

- Hatch-Sdist allowlisten oder interne Verzeichnisse vollständig ausschließen.
- Wheel-/Sdist-Inhaltstest ergänzen.
- .claude, .serena, .sprint, interne Reviews/Memory und lokale Settings nie ausliefern.
- den vollständigen Composite-Lizenzvertrag samt PSF-Notice/Änderungszusammenfassung als Wheel-/Sdist-Datei verifizieren.

### C2. Tooling und Abhängigkeiten

**Status: implementiert; finale Gesamtgates ausstehend.** Ruff verwendet `extend-exclude`; click/msgpack/pip und der Lock wurden auf die korrigierten Mindeststände aktualisiert. Fokussierte Prüfungen sind grün, doch Ruff, Format, mypy, Lockprüfung und Audit des finalen Gesamtbaums bleiben Abschnitt 12 vorbehalten.

- Ruff exclude zu extend-exclude ändern.
- Formatabweichungen korrigieren.
- click, msgpack, pip und Lock aktualisieren; Audit wiederholen.
- 14 mypy-Fehler abbauen.

### C3. Testisolation und Ressourcen

**Status: umgesetzt.** E2E-Fixtures sind von der Projektumgebung isoliert, SQLite-Verbindungen werden explizit geschlossen und die aufgeführten Randfehler besitzen Regressionstests.

- E2E-Fixtures nicht in die Projekt-.venv installieren.
- SQLite-Testverbindungen explizit schließen.
- Regex-FutureWarnings beseitigen oder eng als erwartete Fälle testen.
- Tests für Wildcard-Mutantensuffix, lokales cast, deepcopy-Deklaration und zu kurzen Hit-Stack ergänzen.

### C4. CLI- und Persistenzverträge

**Status: umgesetzt.** Nichtendliche Werte, leere Auswahlen, JSON-Pfade, Scoreaggregation, Browserstatus, `setup.cfg` und Meta-Typen folgen jetzt einem geschlossenen Domänenvertrag.

- --min-score sowie alle Timeout-/Ratiofelder auf endliche Zahlen begrenzen.
- explizite Mutantenselektion ohne Treffer vor Persistierung fehlschlagen lassen; vollständige Leerläufe nur über bewussten allow-empty-Vertrag erlauben.
- setup.cfg ohne Interpolation lesen, Parserfehler als ConfigError kapseln und Argumentlisten korrekt tokenisieren.
- für jeden erfolgreichen JSON-Pfad gültiges JSON ausgeben.
- eine gemeinsame Scoreaggregation für Run, results und CI-Export verwenden.
- Browserfallback am persistierten Status ausrichten und Cachefehler sauber darstellen.
- vollständige .meta-Struktur strikt typvalidieren.

## 5. Welle D – Dokumentation und Releaseentscheidung

**Status der ersten Welle: abgeschlossen.** README, Analyse und diese Roadmap wurden an den damaligen Korrekturstand angepasst. Die früheren Gesamtgates bleiben historische Evidenz dieses Vorgängerstands und ersetzen nicht die frische Verifikation nach Welle E.

- README und Architekturtexte an Mapping-, Prozess-, Cache- und Vertrauensgrenzen anpassen.
- Operatorzahl, Versionen und Installation konsolidieren.
- Befundregister mit behoben, teilweise und offen plus Regressionstest fortschreiben.
- alle Artefakte und Gates frisch erzeugen; keine Freigabe aus alten Resultaten ableiten.

## 6. Welle E – zweites adversariales Review

### E1. CLI- und Run-Ehrlichkeit

**Status: umgesetzt.** Beschädigte historische Mutantennamen degradieren in `time-estimates` konservativ; `KeyboardInterrupt` wird in jeder Pipelinephase als `interrupted` persistiert; neuer Run und Apply invalidieren alte CI-/Latest-Run-Evidenz (MW220-041, -043, -048).

### E2. Physische Dateisystemgrenzen

**Status: umgesetzt.** Stagingziele werden komponentenweise gegen Symlink/Junction geprüft, Hardlinks vor Writes ersetzt und Skipnamen Windows-gerecht case-insensitiv behandelt. Default-Cache, DB und Sidecars verweigern umgeleitete oder hart verlinkte Statepfade vor Read, Migration oder Write (MW220-042, -044, -045).

### E3. Prozessbesitz ohne Erfolgs- oder Setup-Lücke

**Status: umgesetzt; durch MW220-061/-066 vervollständigt.** POSIX-Subprozesse laufen in eigenen Sessions; Windows-Worker sind ab `CreateProcess` atomar Job-Mitglied. `TaskStarted` folgt erst auf synchrone Prozess-/PGID-Evidenz hinter einem Pre-exec-Gate, während Deadline und Startup-Watchdog die Vorbereitungsphase begrenzen (MW220-046, -049, -061, -066).

### E4. Mapping und Reuse

**Status: umgesetzt.** Solange selektive Hit-Zuordnung nicht end-to-end beweisbar ist, bleibt Mapping nichtautoritativ und nutzt die Vollsuite. Vollsuite-Verdicts dürfen bei unverändertem Source-/Universe-Fast-Path und identischem vollständigem Kontextdigest sicher wiederverwendet werden (MW220-047).

**Exit:** Die gezielten Regressionstests sind vorhanden; Welle E gilt erst nach der vollständigen Matrix in Abschnitt 12 als releaseverifiziert.

## 7. Welle F – dritte Welle und finale Multi-Agenten-Diff-, Claim- und Boundary-Reaudits

### F1. Physische DB-Locks, Run-Basis und semantischer Cachezustand

**Status MW220-050 bis -053 sowie -058 bis -060: implementiert und fokussiert verifiziert; Finalgate ausstehend.**

- Workspace-Lock immer vor kanonischem DB-Pfadlock und, bei vorhandener Datei, DB-Identitätslock erwerben; Orchestrator, Apply und CI-Export teilen diese Reihenfolge.
- gleiche absolute DB über verschiedene Workspaces und Hardlink-Identitäten prozessübergreifend koordinieren; laufende Fremd-Runs niemals invalidieren.
- Legacy-Ergebnisse nur diagnostisch laden, niemals als CI-Autorität verwenden.
- vollständige Source-/Test-/Config-Basis aus einem stabilen Snapshot speichern, vor `completed` live revalidieren und beim Export erneut berechnen; MW220-073 erweitert diese Autoritätsbasis in F6 auf die effektive Execution-Umgebung.
- effektive `--tests-dir`-Konfiguration vor `--since-commit` anwenden.
- benutzerdefinierte DB-Pfade, Parent-Komponenten, Blatt und Sidecars gegen Symlink/Junction/Hardlink schützen; neue DB exklusiv voranlegen und Identität an Connect-/Schema-/Write-/Commit-, erfolgreicher Exit- und Current-Run-Return-Grenze prüfen.
- SQLite-/JSON-/Pydantic-Korruption, unbekannte Verdicts und unmögliche `completed`-/Plan-/Pending-Kombinationen als `CorruptCacheError` behandeln.
- den vollständigen geordneten Plan separat per `plan_digest` binden, lückenlose Ordinale beim Laden prüfen und migrierte moderne Runs ohne Digest nur diagnostisch, nie als CI-Autorität, zulassen.
- den neuesten Run-Header gegen den `sqlite_sequence`-High-Water-Mark und sämtliche Planzeilen gegen vorhandene Header prüfen; Header-Rollback und Orphans dürfen keine ältere Evidenz reaktivieren.
- Browser und `results` müssen invalidierte Evidenz ausdrücklich `stale`/`release-ready: no` nennen.

**Regressionen:** `test_run_lock.py`, `test_run_lock_processes.py`, `test_run_surface_integration_220.py`, `test_surface_hardening_220.py`, `test_browser_evidence_invalidation_220.py` und `test_db_state_boundary_220.py`, insbesondere `test_load_current_run_revalidates_exact_ordered_plan_digest`, `test_load_current_run_rejects_noncontiguous_plan_ordinal`, `test_load_current_run_rejects_orphan_plan_after_latest_header_rollback`, `test_cicd_export_rejects_header_high_water_rollback_and_removes_stale_artifact`, `test_cicd_export_rejects_missing_migrated_plan_digest` und `test_load_current_run_rejects_permanent_path_swap_after_final_query`.

**Exit:** Keine DB-Aliasparallelität, keine Legacy-/Drift-/Plan-Rollback-Autorität, keine externe Migration/Write über validierte Statepfade und keine semantisch korrupte false-green Evidenz. Permanente Pfadtausche werden abgefangen; die engere, vollständige Same-User-ABA-Restgrenze zwischen zwei Identitätsbeobachtungen von Python `sqlite3` bleibt ehrlich ausgewiesen.

### F2. Namespace-sichere Atomic-/Sidecar-/Staging-Autorität

**Status MW220-054 bis -057, durch MW220-074 vervollständigt: implementiert und fokussiert verifiziert; Finalgate ausstehend.**

- zentralen Atomic-Writer mit privater exklusiver Geschwisterdatei, Parent-/Identitätsprüfung, Replace und Fehlercleanup verwenden.
- Meta-, Apply-/Backup-, Runner- und zentrale Statewriter auf diese Grenze migrieren.
- die im finalen Writer-Inventar gefundenen Restpublisher für Stats-/CI-JSON, generierte pytest-Plugins, Phase-Guard/Proof, pytest-Argfiles und Run-Lock-Owner ebenfalls ausschließlich über den zentralen Atomic-Writer publizieren.
- generierte Python-Bytes per `generated_hash` an Meta binden; Legacy-Meta ohne Hash genau einmal regenerieren.
- `_copy_with_retry()` ohne Close→Reopen-Austauschfenster veröffentlichen und Freshness-Metadaten plattformverträglich erhalten.

**Regressionen:** `test_atomic_write_safety_220.py`, `test_runner_sidecar_safety.py`, `test_staging_authority_p1_220.py` und die Parent-Swap-/Redirect-Regressionen mit Hardlink-/Symlink-, Parent-, Temp-Substitutions-, Generated-Tamper-, Partial-Publish- und Copy-Swap-Repros. Das Produktwriter-Inventar darf außer `atomic_file.py` keinen eigenen Rename-Publisher und keinen direkten `write_text`-/`write_bytes`-/`mkstemp`-Writer enthalten; anonyme `TemporaryFile`-Bootstraps publizieren keinen Pfad und fallen nicht unter diesen Vertrag.

### F3. Windows-Containment vor erstem User Mode

**Status MW220-061 bis -063: implementiert und fokussiert verifiziert; Finalgate ausstehend.**

- Job-Mitgliedschaft atomar über `PROC_THREAD_ATTRIBUTE_JOB_LIST` bereits in `CreateProcess` festlegen; kein suspendierter Create→Assign-Zwischenzustand.
- Multiprocessing-Bootstrap vollständig vor Resume in seekbarem Speicher serialisieren, damit frühes `.pth`/`sitecustomize` die Parent-Startgrenze nicht blockiert.
- private Spawnbackends auf auditiertes CPython 3.12–3.14 begrenzen; Resume-/Assignmentfehler fatal und poolweit behandeln.

**Regressionen:** `test_atomic_spawn.py`, `test_suspended_spawn.py`, `test_process_worker.py` sowie die Windows-Fälle `test_pool_has_no_post_create_assignment_hard_exit_window` und `test_wedged_sitecustomize_large_payload_is_contained_and_nonblocking` in `test_pool_shutdown.py`.

### F4. POSIX-Pre-Interpreter-Session, PGID-Evidenz, Hard-Parent-Liveness und Cleanup

**Status MW220-064 bis -068, durch MW220-075 ergänzt: implementiert und laut Prozess-/Diff-Reaudit fokussiert verifiziert; Finalgate ausstehend.**

- Multiprocessing-Generation bereits in `fork_exec` in eine eigene Session bringen, Bootstrap vor Kindstart seekbar serialisieren und Parent-Liveness über eine separate Pipe erhalten.
- pytest hinter einem EOF-sicheren Pre-exec-Pipe-Gate starten, Worker-ID/PGID synchron an den Executor publizieren und erst danach Interpreter-/Nutzcode freigeben.
- publizierte PGIDs executorweit halten und bei Worker-`SIGKILL` per `killpg` reapen.
- auf Linux am privaten Child-Entry zuerst `PR_SET_PDEATHSIG` setzen und die erwartete Parent-PID unmittelbar erneut prüfen; danach EOF-Watcher und `killpg` als Liveness-/Baumfallback verwenden.
- Executor- und Typechecker-Cleanup-Stufen unabhängig und begrenzt ausführen; Cleanupfehler dürfen spätere Ressourcen und Originalfehler nicht verdrängen.
- erfolgreichem Generation-`DONE` einen eigenen begrenzten 15-Sekunden-Join geben.

**Regressionen:** POSIX-Teile von `test_generation_supervisor.py`, realer WSL-Test `test_worker_sigkill_reaps_registered_pytest_session`, reale Hard-Parent-Exit-Tests für Sessionkind und Prozessbaum unter Last, `test_cleanup_failures_do_not_skip_later_resources_or_escape`, `test_job_close_failure_does_not_skip_fallback_kill_or_mask_timeout` und `test_done_teardown_uses_its_own_generous_bounded_timeout`.

**Restgrenze:** Linux ist ab dem privaten Child-Entry durch `PR_SET_PDEATHSIG`, Parent-PID-Racecheck und EOF-/`killpg`-Fallback abgesichert. Auf generischem POSIX ohne cgroup-/`PDEATHSIG`-Äquivalent bleibt das kleine Pre-Entry-Fenster vor Installation des EOF-Watchdogs nicht kernelgarantiert schließbar; diese Restgrenze ist keine plattformweite Hard-Parent-Garantie.

### F5. Python-Metadaten, Composite-Lizenz, GitHub-CI und Artefakt-Supply-Chain

**Status MW220-069 bis -072: lokal implementiert und fokussiert verifiziert; MW220-105-Snapshot artefaktbelegt, Post-MW220-111- und integrierter Rebuild ausstehend.** Der lokale Packaging-/Workflow-Handoff ist abgeschlossen. Remote-CI wird wegen des vom Nutzer akzeptierten GitHub-Billing-Problems übersprungen und ausdrücklich nicht als PASS gewertet.

- Runtimevertrag auf CPython 3.12–3.14 begrenzen und Klassifikatoren/README angleichen.
- vollständigen PSF-2.0-Text, Copyright-Hinweis und Änderungszusammenfassung für die CPython-abgeleiteten Backends liefern und den Composite-Vertrag `ISC AND BSD-3-Clause AND PSF-2.0` in Metadaten und Artefakten pinnen.
- GitHub-CI mit minimalen Berechtigungen und Windows-/Ubuntu-Matrix über 3.12, 3.13 und 3.14 bereitstellen.
- Lock, Quality, Tests, matrixweites Audit, Build und installierte Artefakt-Smokes trennen; keine globale Frozen-Konfiguration darf `uv lock --check` neutralisieren.
- ausschließlich allowgelistete Actions an vollständige Commit-SHAs pinnen; Wheel und Sdist zweimal offline aus dem gelockten Build-Environment bauen, vergleichen, übertragen, isoliert installieren und smoke-testen.

**Exit:** Statische Verträge grün, Lizenzbytes und Inventar im reproduzierbaren finalen Wheel/Sdist nachgewiesen und Workflow-Handoff abgeschlossen. Für diesen Korrekturstand ersetzt die dokumentierte, vom Nutzer akzeptierte Billing-Ausnahme den Remote-Lauf nicht durch einen PASS; lokales GO und Remote-Evidenzlücke bleiben getrennt sichtbar.

### F6. Vollständige Execution-Basis und finaler Reaudit

**Status MW220-073 bis -075:** implementiert und fokussiert verifiziert; MW220-073 hat zusätzlich den unabhängigen fokussierten Abschluss-Reaudit bestanden. Das repositoryweite Finalgate ist ausstehend.

- Dependency-Evidenz an lesbare Bytes installierter Distributionen und Editables binden; gleiche Versionsnamen ohne identische Bytes dürfen Reuse nicht autorisieren.
- den geordneten effektiven `sys.path`, `.pth`-/unregistrierte Module, Runtime/ABI/Executable und ausnahmslos die vollständige geerbte Umgebung erfassen; vor dem Child-Start vorhandene Werte intern verwendeter Handshake-Namen bleiben Teil der Parentbasis.
- interne `sys.path`-Änderungen vor der Pre-Completion-Revalidierung exakt zurücksetzen und Verdict-Fingerprints versioniert mit voller SHA-256-Breite speichern.
- Vollständigkeit als typisierte Evidenz behandeln: Bei nicht les- oder inventarisierbarer Basis darf der technische Plan `completed` sein, aber Stats-/Verdict-Reuse bleibt gesperrt, persistierte Basis-/Konfigurationsautorität bleibt leer und CI-Export lehnt fail-closed ab.
- das restlose Atomic-Publisher-Inventar aus F2 und die Linux-Hard-Parent-Liveness samt generischer POSIX-Restgrenze aus F4 als eigenständige Reaudit-Ergebnisse festhalten.

**Exit:** Kein Cache, Verdict oder CI-Export kann aus einer unvollständigen Execution-Basis Autorität ableiten; kein eigener Produktpublisher umgeht `atomic_file.py`; Linux-Hard-Parent-Exit ist ab privatem Child-Entry geschlossen, ohne die generische POSIX-Pre-Entry-Restgrenze zu verschweigen. Releaseverifikation folgt erst aus Abschnitt 12.

### F7. Generische Typechecker und immutable pytest-Grenze

**Status MW220-076 bis -078:** implementiert und durch fokussierte Regressionen sowie zwei unabhängige Boundary-Reaudits verifiziert; vollständige repositoryweite Post-MW220-111-Kandidatenmatrix grün; Remote-Matrix wegen Billing übersprungen, kein PASS.

- jedes nicht leere generische `type_check_command` als nicht vollständig inventarisierbare Execution-Basis markieren; technische Klassifikation zulassen, aber Stats-/Verdict-Reuse, `--min-score` und CI-Export fail-closed sperren.
- moderne und historische Runs über eine zentrale typisierte Incompleteness-Klassifikation auswerten; `results` und `browse` müssen unvollständige Basis sichtbar als `release-ready: no` kennzeichnen.
- eine einzige immutable pytest-Boundary vor jedem Run einfrieren: Staging-Root, Config und explizite Testziele an kanonische Pfade, Typen, Dateisystemidentitäten und Datei-Digests binden.
- pytest-Optionen und Argfile-Injektion in `tests_dir` ablehnen, interne Targets nach `--` transportieren und Boundary-Revalidierung in Runner, Executor, Worker sowie bei leerer Taskliste erzwingen; Boundary-Drift ist fatal.
- frühen Child-Guard vor pytest-Conftest-Preloading installieren: Exact-File-Autorität umfasst keine benachbarten/übergeordneten Conftests, Directory-Autorität nur den eigenen Baum und keine Routing-Vorfahren; externe `testpaths` ohne eingefrorene Identität scheitern.
- pytest-Unterstützung fail-closed auf ≥ 8.2 und < 10 begrenzen, unbekannte/unparsebare Versionen vor Locks/DB/Stagingwrites ablehnen und die privaten Multi-Root-Conftest-Hooks mit echten pytest-8.2.2-/9.x-Prozessen sowie eigener Windows-/Ubuntu-CI-Stufe überwachen.

**Exit:** Kein generischer Checker kann Releaseautorität vortäuschen; kein pytest-Target, Config-, Root- oder Conftest-Pfad kann die eingefrorene Execution-Basis statisch oder zwischen Parent- und Childprüfung umgehen; reale lokale pytest-8.2.2- und 9.x-Regressionsläufe sind grün. Der Remote-Kompatibilitätsjob bleibt wegen Billing eine dokumentierte, akzeptierte Evidenzlücke und ist kein PASS.

### F8. Adversariale Finalgate-, Dogfood- und Releaseevidenz-Closure

**Status MW220-079 bis -111:** vollständig lokal implementiert und fokussiert verifiziert; MW220-079 bis -089 zusätzlich im realen Dogfood-Workload beziehungsweise in einer leeren externen Buildumgebung belegt, MW220-090 bis -104 durch 74 fokussierte Tests und den realen Security-only-Wrapperlauf geschlossen, MW220-105 durch beide realen Cross-Process-Fälle und 50 Stresswiederholungen, MW220-106 bis -110 durch Byteforensik, zehn Supply-Chain-/State-Regressionen und einen realen Offline-Nested-Lockcheck sowie MW220-111 durch drei fail-closed Executor-Hooks, synchronisierte aktive Governance, 11/11 fokussierte Regressionen und Shell-Syntaxchecks. Die vollständige Post-MW220-111-Gesamtsuite, der stabile `.venv`-Digest, der finale Dogfood-Recheck, das kanonische Semgrep-Gate, der reproduzierbare Doppelbuild und das Kandidateninventar sind grün; Remote-CI ist wegen Billing ausdrücklich abgewählt.

- Workflow-Shellvertrag mit actionlint/ShellCheck/Pyflakes und Zizmor prüfen; Command Substitution und `export` trennen, damit ein fehlgeschlagenes `git log` den reproduzierbaren Build stoppt.
- alle Git-owned Dateien byteweit auf unsichtbare Unicode-/Bidi-/Control-/NUL-/Merge-Marker prüfen und das einzige U+00AD entfernen.
- E2E-Subprozessbudget weiterhin hart begrenzen, aber mit 300 Sekunden ausreichend Headroom für Coverage-Instrumentierung und belastete Windows-Runner geben; fokussiert und im vollständigen Coverage-Lauf beweisen.
- byteidentische parallele Guard-Publisher content-verifiziert und idempotent behandeln, ohne Symlink-/Hardlink-/Reparse-/fremde-Bytes- oder sonstige Writerfehler zu akzeptieren.
- jeden unverifizierbaren Guard-/Boundary-Publisherfehler fatal transportieren; kein `suspicious`-Verdict und keine Resultzeile, Mutant bleibt pending, Run abortiert und besitzt keine vollständige Execution-Basis.
- alle nicht äquivalenten Survivors des Coverage-Bridge-Piloten durch semantische Path-, Freshness-, Exit-, Mapping- und Diagnoseassertions töten; Operatoren und Schwelle unverändert lassen.
- synthetische Surface-Tests vollständig von realen lokalen Current-Run-/DB-Snapshots isolieren.
- Buildbackend und editierbare PEP-660-Laufzeitabhängigkeiten vollständig pinnen und in jedem CI-Job vor dem gelockten `--no-build-isolation`-Projektsync aus der Buildgruppe bootstrappen; den exakten Workflowvertrag zusätzlich in Release-Supply-Chain-Tests festschreiben.
- CLI-Unit-Tests an den vollständigen Snapshot-/Command-Seams isolieren; Corrupt-Cache-Übersetzung durch den echten Helper laufen lassen und jeden Export in einem eigenen Temp-Workspace ausführen, damit eine reale Dogfood-DB weder Fixtures noch Locks oder Artefakte beeinflusst.
- alle lokalisierten Windows-`mklink`-Diagnosen durch `/u` auf einen expliziten UTF-16LE-Pipevertrag zwingen und Readerthread-Warnungen als Testfehler behandeln.
- fachliche Orchestrator-Unit-Tests mit stabiler Basisfixture vom live veränderlichen editable Repository entkoppeln, ohne die dedizierten echten Stable-/Mid-Run-Driftverträge zu mocken.
- Workspace-Verzeichnisse, die nie in den Workerbaum gestaged werden, über eine gemeinsame Konstante ebenso aus dem Projekt-/Editable-Basishash ausschließen; Tool-/IDE-Cachechurn darf keine fachliche Inputdrift vortäuschen.
- Semgrep nur noch über einen getrackten, versionierten, plattformneutralen Wrapper auf einem externen Git-owned Root-Mirror ausführen; Findings, Parserfehler, `skipped_rules`, Fixpoint-Timeouts, Rule-ID-/Target-/Skip-/Manifest- oder TOCTOU-Drift müssen trotz eines möglichen Semgrep-Exitcodes 0 fail-closed abbrechen.
- Inline-`nosemgrep` zwingend deaktivieren und ausschließlich exakt adjudizierte Testcode-False-Positives über Rule-/Path-/Span-/Lines-/Full-file-Digest-Signaturen zulassen; Suppressionen selbst dürfen keine Gate-Autorität besitzen und jede Kontextdrift erzwingt Re-Review.
- Semgrep-Childumgebung von allen geerbten `GIT_*`-, `PYTHON*`-, `SEMGREP_*`-, `UV_*`-, Credential-, Home-, Settings- und Temp-Autoritäten isolieren; Wrapper und Scanner exakt an die gelockte Repository-`.venv` binden.
- den unauthentifizierten Community-Regelbestand einmal vollständig materialisieren und content-hashen und den eigentlichen Scan anschließend offline ausschließlich gegen dieses geprüfte Bundle ausführen; Pro-/Registry-/Rule-Content-Drift ist fatal.
- Wrapper und `.semgrepignore` unter exakt kanonischen Sdistpfaden byteidentisch ausliefern; README, CI, Rootgruppe und Lock auf denselben minimalen Security-only-Vertrag binden.
- statische Workflowtests dürfen keine Shell-Zusätze, allgemeines `uvx`, Ersatzarchivpfade oder gelöste Semgrep-Root-/Lockbindungen übersehen.
- ausführbare Agent-/Pre-commit-Hooks und maschinen-gelesene Entwicklerverträge dürfen keine direkte, changed-/staged-only oder bei fehlenden Voraussetzungen übersprungene Semgrep-Autorität besitzen; nur der kanonische Vollscope-Wrapper darf einen Security-PASS begründen.
- Cross-Process-Ready-Signale dürfen keine nur angelegte, aber noch leere PID-Datei veröffentlichen; Kind schreibt in eine eindeutige Tempdatei und ersetzt atomar, Parent wartet auf einen gültigen positiven PID.
- repositoryweite Textbytes über `.gitattributes` auf LF festlegen und alle Kandidatendateien vor dem frischen Checkout frei von CR-/Mischzeilenenden halten.
- Dependency-Evidenz mit kanonischem stdout- und pfadunabhängigem Body-Digest beschreiben; keine absolute `--output-file`-Headerprovenienz als undokumentierten Universalhash ausgeben.
- `.sprint/state.md`, Projekt-`MEMORY.md` und ausdrücklich LIVE markierte Serena-Zustände auf denselben v2.21.0-Kandidaten ausrichten; ältere Langzustände klar als Archiv markieren und die aktive Version statisch pinnen.
- numerisches Sprintfrontmatter, realen Sprint-38-Backlog, vollständige LIVE-/ARCHIVE-Grenzen und identische Releasefolge in allen maschinen-gelesenen Zuständen erzwingen.
- beide bewusst gepflegten Installationsanleitungen byteidentisch an Projektversion, Git-Tag und CLI-Ausgabe binden.
- eigenständigen Acceptance-Harness auf eine ausdrücklich historische v2.20.0-Verhaltensbasis festlegen und Projekt, Lock, Paketversion, Gitquelle und Provenienz gemeinsam prüfen.

**Exit:** actionlint/Security-/Unicode-Gates grün; deterministischer Fünf-Publisher-Race und fataler Pending-Vertrag grün; realer Vier-Worker-Dogfood-Run ohne Recovery, ohne suspicious/unchecked und mit Score ≥80; CI-Export scheitert bei Environment-Drift und gelingt bei exakt identischer Basis; ein leerer externer Runner kann den gepinnten Buildbootstrap und den vollständigen editierbaren CI-Sync reproduzieren; der gesamte CLI-Isolationscluster bleibt auch mit vorhandener realer Current-Run-DB deterministisch grün.

## 8. Beabsichtigte Breaking Changes

- **Umgesetzt:** Relative Mutation-, Copy- und Extra-Pfade außerhalb des Projektroots werden abgelehnt; externe Symlink-/Junctionziele werden nicht verfolgt.
- **Umgesetzt:** Alte `.meta`-/Stats-Dateien ohne die neuen Digests werden einmalig invalidiert.
- **Umgesetzt:** Korrekte Testselektion kann Baseline und Mutantenmenge gegenüber dem ursprünglichen 2.20.0-Snapshot ändern.
- **Umgesetzt:** Nichtautoritative Mappings führen zur Vollsuite. Das kann langsamer sein, verhindert aber unbewiesenes `no tests`.
- **Umgesetzt:** Identische gerenderte Mutanten werden entfernt. Die erste gleichnamige Definition behält ihre historische ID; Definitionen ab Vorkommen 2 erhalten den reversiblen Suffix `ǁ<Ordinal>`. Betroffene alte Verdicts sind absichtlich nicht wiederverwendbar.
- **Umgesetzt:** Das SQLite-Schema wird lesemigriert und trennt historischen Cache vom aktuellen Run-Snapshot; ältere Programmversionen müssen das neue Schema nicht schreibkompatibel halten.
- **Umgesetzt:** Run/Apply/Export erwerben Workspace-, DB-Pfad- und vorhandene DB-Identitätslocks in stabiler Reihenfolge; gleiche absolute DBs über verschiedene Workspaces teilen eine Lockdomäne.
- **Umgesetzt:** `--force` verweigert nicht enthaltene oder umgeleitete Cache-/Stagingroots, bevor dort Guard- oder Lockartefakte erzeugt werden.
- **Umgesetzt:** Feste Default-Statepfade verweigern Symlink-, Junction- und Hardlink-Umleitungen bereits vor Reads und Schema-Migrationen; bewusst extern gespeicherter State benötigt künftig einen expliziten separaten Vertrag.
- **Umgesetzt:** Selektive Testzuordnung bleibt deaktiviert, bis ihre Autorität end-to-end beweisbar ist; Korrektheit bedeutet vorerst Vollsuite.
- **Umgesetzt:** Unter Windows wird ein Worker-Subprozess ohne verfügbare sichere Job-Zuweisung nicht gestartet; unter POSIX werden isolierte Sessions für vollständigen Prozessbesitz verwendet.
- **Umgesetzt:** Erfolgreiches `apply` und jeder neue Run invalidieren alte Current-Run-/CI-Export-Evidenz.
- **Umgesetzt:** Benutzerdefinierte DB-Hardlinks und umgeleitete Parent-/Sidecarpfade werden fail-closed abgelehnt; vorhandene bisher tolerierte Alias-Setups müssen auf eine echte Einzeldatei migrieren.
- **Umgesetzt:** CI-Export akzeptiert keine Legacy-Daten und keine modernen Runs ohne live identische vollständige Source-/Test-/Config-/Dependency-/Environment-/Import-/Runtimebasis.
- **Umgesetzt:** Eine nicht vollständig inventarisierbare Execution-Basis verhindert nicht den technischen Abschluss des Plans, deaktiviert aber Stats-/Verdict-Reuse, hinterlässt keine persistierte Basis-/Konfigurationsautorität und wird vom CI-Export fail-closed abgelehnt.
- **Umgesetzt:** Unbekannte persistierte Verdicts, widersprüchliche Completed-Zustände, manipulierte geordnete Pläne, Orphans und Header-Rollbacks gelten als Cachekorruption statt als darstellbare Fremdwerte; migrierte Runs ohne `plan_digest` sind keine CI-Autorität.
- **Umgesetzt:** Der deklarierte Runtimevertrag ist auf CPython 3.12–3.14 begrenzt.
- **Umgesetzt:** Der pytest-Runtimevertrag ist auf ≥ 8.2 und < 10 begrenzt; unbekannte oder nicht parsebare Versionen werden vor Workspacewrites abgelehnt.
- **Umgesetzt:** `tests_dir` akzeptiert ausschließlich Pfade/Node-IDs. Ein explizites externes Testfile autorisiert kein angrenzendes `conftest.py`; ein externes Verzeichnis nur seinen eigenen Conftest-Baum, nicht dessen Routing-Vorfahren.
- **Umgesetzt:** Ein nicht leeres generisches `type_check_command` lässt die technische Ausführung zu, macht den Run aber nicht release-autoritativ: Reuse, `--min-score` und CI-Export sind gesperrt und Diagnoseoberflächen warnen explizit.
- **Umgesetzt:** Unverifizierbare pytest-Guard-/Control-Plane-Fehler werden nicht mehr als fachliche `suspicious`-Verdicts gespeichert. Der betroffene Mutant bleibt pending und der gesamte Run abortiert fail-closed.

## 9. Dateipakete für parallele Umsetzung

| Paket | Primäre Dateien |
|---|---|
| Mapping/Runner | runner.py, stats.py, process/worker.py, Mappingtests |
| Generation/Staging | file_setup.py, models.py, config.py, orchestrator.py, mutant_diff.py |
| Mutationssemantik | mutation.py, node_mutation.py, regex_mutation.py, Mutationstests |
| Prozess/Runstate | process/executor.py, type_checking.py, db.py, Prozesstests |
| Releasehygiene | pyproject.toml, Lockfile, E2E-/Packagingtests, Dokumentation |

Seit der zweiten Welle wird ausschließlich im Git-Clone unter `<repository root>` auf `fix/360-review-hardening` von `main@6cb727d` gearbeitet. Commit, Push, PR-Integration, Tag und GitHub-Release sind nach Abschluss der lokalen Gates autorisiert; sie sind zum Stand dieses Dokuments noch nicht erfolgt. Der lokale Legacy-ZIP-Baum ist nicht autoritativ. `v2.21.0` ist live als frei geprüft, verbindlich gewählt und in Projektmetadaten sowie Lock eingetragen.

## 10. Verifikationsmatrix

Nach jeder Welle:

    uv run --no-sync pytest -q <fokussierte Tests>
    uv run --no-sync ruff check <geänderte Dateien>
    uv run --no-sync ruff format --check <geänderte Dateien>
    uv run --no-sync mypy <geänderte Produktionsmodule>
    uv run --no-sync lint-imports

Vor Abschluss:

    uv run --no-sync pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning
    uv run --no-sync pytest -q --cov=mutmut_win --cov-report=term-missing -W error::pytest.PytestUnhandledThreadExceptionWarning
    uv run --no-sync ruff check .
    uv run --no-sync ruff format --check .
    uv run --no-sync mypy src/ scripts/
    uv run --no-sync lint-imports
    uv lock --check
    uv sync --locked --only-group security --no-install-project
    uv run --no-sync python -I scripts/semgrep_release_gate.py

Zusätzlich: actionlint samt ShellCheck/Pyflakes, Zizmor regular/pedantic, Gitleaks über vollständige Historie und Git-owned Worktree, Unicode-/Bidi-/NUL-/Control-/Merge-Marker-Inventar sowie `git diff --check`; vollständigen Lock exportieren und mit `pip-audit` prüfen; Wheel/Sdist zweimal aus identischen gelockten Inputs extern bauen, Byte-/SHA-/Inventargleichheit und Lizenzbytes vergleichen, mit gepinnten Twine-/Wheel-Content-Tools prüfen und isoliert installieren/smoke-testen; Projekt-.venv vor/nach Testlauf stabil inventarisieren; alle P0-Minimalrepros und die echte pytest-8.2.2-Grenze erneut ausführen; CI-Export auf identischer Basis akzeptieren und bei Environment-Drift fail-closed ablehnen; einen dokumentierten Vier-Worker-Dogfooding-Piloten auf genau dem danach eingefrorenen finalen Baum ausführen. Danach Branch/PR publizieren. GitHub-CI wird wegen Billing dokumentiert übersprungen und nicht als PASS gewertet.

## 11. Fortschritt

| Datum | Welle | Ergebnis |
|---|---|---|
| 2026-08-30 | Review | Historische Baseline erhoben; adversariales Register auf 40 Befunde erweitert |
| 2026-08-30 | Welle A | False-Green-, Cache-, Staging-, Apply- und Mutationssemantikfixes implementiert und gezielt regressionstestgedeckt |
| 2026-08-30 | Welle B | Generation-Supervisor, bounded Output/Tree-Cleanup, Run-ID, exakter Plan, Current-Snapshot-Autorität und kanonischer Lock implementiert |
| 2026-08-30 | Welle C | Paket-/Lizenzkonfiguration, Abhängigkeiten, Ruff, E2E-Isolation, Ressourcen- und CLI-Verträge implementiert |
| 2026-08-30 | Welle D | Analyse, Roadmap und README an den implementierten Stand angepasst |
| 2026-08-30 | MW220-040 | Stop/Read/Write-Race in `BoundedOutputCapture` geschlossen; deterministischer Regressionstest, Markertest 100/100 und 147 angrenzende Tests grün |
| 2026-08-30 | Erste Abschlussgates | historisch grün für den Vorgängerstand; keine Freigabeevidenz für die zweite Welle |
| 2026-08-30 | Git-Neustart | frischer Clone unter `<repository root>`, `fix/360-review-hardening` von `main@6cb727d` |
| 2026-08-30 | Zweite Review-Welle | MW220-041 bis -049 gefunden und mit gezielten Regressionen geschlossen |
| 2026-08-30 | Dritte Review-Welle | MW220-050 bis -071 bestätigt und lokal implementiert; repositoryweite und Remote-Gates ausstehend |
| 2026-08-30 | DB-/Korruptionsnachschärfung | Custom-DB-/Connect-/Return-Grenze, Verdict-Whitelist, Completed-/Plan-Digest-/High-Water-/Orphan-Invarianten fokussiert grün; 122 Tests bestanden, 6 plattformspezifisch übersprungen, zusätzlicher Fedora-Post-Read-Swap bestanden; kein Gesamtgate daraus abgeleitet |
| 2026-08-30 | Prozess-Handoff | Windows-Atomic-Spawn und POSIX-Session/PGID/Cleanup/DONE fokussiert verifiziert; repositoryweites Finalgate bleibt offen |
| 2026-08-30 | Finaler Diff-/Claim-Reaudit | MW220-072 bis -075 ergänzt; Composite-Lizenz, vollständige Execution-Basis, Restpublisher und POSIX-Hard-Parent-Liveness lokal bearbeitet |
| 2026-08-30 | Execution-/pytest-Boundary-Reaudit | MW220-076 bis -078 ergänzt und implementiert; generische Typechecker-Autorität und Legacy-Anzeige geschlossen; pytest-Boundary Schema v2 samt frühem Conftest-Guard unter echten pytest 8.2.2/9.x-Prozessen unabhängig reauditiert; beide Reaudits GO, Final-/Remote-Gates ausstehend |
| 2026-08-30 | Adversarialer Finalgate-/Dogfood-Reaudit | MW220-079 bis -084 ergänzt; Workflow-/Unicode-/Coverage-Harness geschlossen; Guard-Publisher-Race darf keine fachlichen Verdicts mehr erzeugen; Coverage-Bridge-Testlücken und DB-Testisolation geschlossen; erneuter Realpilot 86/90 killed, 0 suspicious, 95,6 %, identischer-Basis-CI-Export grün |
| 2026-08-30 | Fresh-Runner-Build-Reaudit | MW220-085 ergänzt; verdeckte `hatchling`-/`editables`-Voraussetzungen reproduziert, vollständig gepinnt und als gelockter Buildgruppen-Bootstrap vor allen CI-`--no-build-isolation`-Syncs in einer leeren externen Umgebung verifiziert |
| 2026-08-30 | CLI-/Current-Snapshot-Isolationsreaudit | MW220-086 ergänzt; 22 veraltete Legacy-Reader-Mocks und drei reale Export-Workspaces geschlossen; 31/31 betroffene Tests im Repo-CWD mit vorhandener 90er-Dogfood-DB grün |
| 2026-08-30 | Windows-Pipe-/Unit-Hermetik-Reaudit | MW220-087/-088 ergänzt; sieben lokalisierte `mklink`-Pipes auf `/u`/UTF-16LE normiert und Orchestrator-Unit-Tests von Live-Basisdrift isoliert; 13 Junction- sowie 59 Orchestrator-/Drifttests grün |
| 2026-08-30 | Staging-/Execution-Basis-Skip-Reaudit | MW220-089 ergänzt; auseinanderlaufende Tool-/IDE-Verzeichnisgrenzen in `WORKSPACE_EXCLUDED_DIR_NAMES` vereinigt; 61 Basis-/Staging-Regressionsfälle grün |
| 2026-08-31 | Strikter Abschluss-Zwischenlauf | 1.925 Tests bestanden, 44 übersprungen, keine Thread-Warnung; Coverage 85 % bei 8.513 Statements/1.271 Missing; Lock, Ruff, Format, mypy, Import-Linter und alle übrigen Security-/Unicode-/Actions-Gates grün; Baum und stabile `.venv` unverändert |
| 2026-08-31 | Semgrep-Evidenz-Reaudit | MW220-090 ergänzt: rohe Befehle meldeten trotz 48/40 Fixpoint-Timeouts Exit 0; Root-Mirror mit Semgrep 1.175.0, vier Jobs und exakter Target-/Skipmenge technisch vollständig; getrackter fail-closed Wrapper in Umsetzung |
| 2026-08-31 | Semgrep-Wrapper-Red-Team | MW220-091/-092 ergänzt: reales JSON-Schema korrigiert, Inline-Suppressionen durch `--disable-nosem` entmachtet, 20 exakte Testcode-Matches adjudiziert; lokaler Loginbestand vom frischen Community-Runner getrennt, 1.074 Definitionen contentgepinnt und Offline-Bundlescan mit 342 Regeln reproduziert |
| 2026-08-31 | Semgrep-Tool-/Environment-Red-Team | MW220-093 bis -101 geschlossen: Git-/Python-/venv-Bindung, Cross-Version-Lock, Sdistpolicy, Full-file-Kontext, NETRC und TMPDIR fail-closed; realer Security-only-Lauf grün |
| 2026-08-31 | Frozen-Contract-Reaudit | MW220-102 bis -104 geschlossen: exakte Workflowkommandos, kanonische Sdistpfade und Root-/Lockbindung; 74 fokussierte Tests grün |
| 2026-08-31 | Releaseversion | `v2.21.0` live frei geprüft und verbindlich festgelegt; Projekt, Lock, CLI und Installationshinweise melden `2.21.0`; 76 Versions-/Release-/Securitytests grün |
| 2026-08-31 | Lokale Abschlussmatrix | nach MW220-090 bis -104 und Versionsbump 1.994 Tests / 44 Skips sowie 85 % Coverage; Ruff/Format/mypy/Import-Linter, Lock/Audit, Actions-/Security-/Unicode-Gates, reproduzierbarer Build und CPython-3.12–3.14-Smokes grün |
| 2026-08-31 | Dogfood-Pilot vor MW220-111 | 86/90 killed, vier äquivalente Survivors, 0 timeout/suspicious/skipped/no-tests, 95,6 %; CI-Export byteidentisch, Environment-Drift fail-closed |
| 2026-08-31 | MW220-105 | Empty-Read-Race im Ready-PID-Testharness geschlossen; 2/2 reale Prozessfälle und 50/50 Stresswiederholungen grün |
| 2026-08-31 | MW220-106 bis -108 | checkoutabhängige EOL-Bytes, pfadabhängige Exporthashprovenienz/stale Gateformulierungen und maschinen-gelesener v2.14–v2.20-Live-State geschlossen; zwei neue statische Regressionen grün |
| 2026-08-31 | MW220-109/-110 und MW220-108-Reaudit | Installationskopien byteidentisch auf v2.21.0; Standalone-Harness-Projekt/Lock/Provenienz konsistent auf v2.20.0; vollständiger State-/Hookvertrag und zehn Supply-Chain-/State-Regressionen grün |
| 2026-08-31 | MW220-111 Governance-Reaudit | Raw-/Changed-file-Semgrep aus drei ausführbaren Hooks und aktiven Arbeitsverträgen entfernt; fehlende Voraussetzungen fail-closed; 600-s-Hookbudget, exakte Vollscope-Wrapperbindung, 11/11 Regressionen und Shell-Syntaxchecks grün |
| 2026-08-31 | Quieszente Abschlusswiederholung | 20/20 IL-Wiederholungen sowie zwei vollständige Läufe mit jeweils 1.999 Tests / 44 Skips grün; erster Lauf erzeugte zwei deterministische Pytest-Hypothesis-Caches, warmer Vor-/Nachdigest danach exakt stabil bei 11.597 Dateien / 484.952.668 Bytes / SHA-256 `31fa8b0322fa085bd9b173f15e2244aed3794f5d9050cb29b225b331be8bf35b` |
| 2026-08-31 | Post-MW220-111-Kandidatenmatrix | zwei vollständige strikte Läufe mit jeweils 2.000 Tests / 44 Skips grün; erster Lauf erzeugte ausschließlich zwei weitere Hypothesis-Assertion-Rewrite-Caches, unmittelbarer Warmlauf hielt `.venv` exakt bei 11.597 Dateien / 484.925.395 Bytes / SHA-256 `95c1fed54da9cbdfdd8ab7d7addec3b63deb11b88e92d85968d2cb42e3488d82` |
| 2026-08-31 | Finaler Dogfood-Recheck | Post-MW220-111-Kandidat: 86/90 killed, vier äquivalente Survivors, 0 timeout/suspicious/skipped/no-tests/unchecked, 95,6 %, 105,4 s; CI-Export vor/nach Negativtest byteidentisch, Environment-Drift Exit 1 ohne stale Artefakt |
| 2026-08-31 | Finales Semgrep-Gate | eingefrorener Post-MW220-111-Scope: 218 Manifestdateien, 168 Targets, 49 Policy-Skips, 1.074 Definitionen, 342 Regeln, 20/20 allowgelistete Testtreffer und jeweils 0 unerwartete Findings/Errors/Skipped-Rules/Fixpoint-Timeouts |
| 2026-08-31 | Kandidatenbuild und Inventar | kanonischer 409-Dateien-Git-Index ohne Hygiene-/Secretbefund; zwei byteidentische Offline-Builds, Twine/Wheel-Content, CPython-3.12–3.14-Wheel-Smokes und 3.12-Sdist-Smoke grün |

## 12. Finale Abschlussnachweise

| Gate | Bisherige Evidenz / finaler Recheck |
|---|---|
| `uv run --no-sync pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning` | Post-MW220-111-Kandidatenbaum zweimal vollständig grün: jeweils 2.000 bestanden, 44 übersprungen; zusätzlich 20/20 frühere IL-Wiederholungen grün |
| Coverage mit identischem striktem Warnungsgate | 1.994 bestanden, 44 übersprungen, 85 %, 8.513 Statements / 1.271 Missing; MW220-105 bis -111 ändern keine Produktionsstatements |
| `uv run --no-sync ruff check .` | Post-MW220-111 repositoryweit ohne Befund grün |
| `uv run --no-sync ruff format --check .` | Post-MW220-111 repositoryweit grün; 168 Python-Dateien formatiert |
| `uv run --no-sync mypy src/ scripts/` | 38 Dateien grün |
| `uv run --no-sync lint-imports` | 37 Dateien / 123 Abhängigkeiten / 1 Vertrag grün |
| `uv lock --check` | `2.21.0`, 115 Pakete, grün |
| `uv build` plus Wheel-/Sdist-Inventar | gestagter Post-MW220-111-Git-Kandidat zweimal byteidentisch offline gebaut: Wheel 270.613 Bytes / SHA-256 `8a89f0f6243ff7775ddcd918965b86f3385adda25adf051b8e1f5254d1e26e89`, Sdist 683.043 Bytes / SHA-256 `07a5e86969eacd888aee30751643ee87e3a3f5740b58ae263df7a6c2ec0f38b4`; 44/224 Archivmember, Lizenz-/Wrapper-/Policybytes, Twine 7.0.0 und Check-Wheel-Contents 0.6.3 grün; Wheel-Smokes 3.12.13/3.13.13/3.14.7 und Sdist-Smoke 3.12.13 grün; integrierter Rebuild ausstehend |
| vollständiger `uv export --frozen --all-extras --all-groups --no-hashes --no-emit-project` plus `uv run --no-sync pip-audit --requirement ... --progress-spinner off` | finaler pfadunabhängiger Dependency-Body: 7.345 Bytes / SHA-256 `7deef5fd17ec5e7aa60cb18c6be87e3d1a8478af3d7e1262d0bb2155bbd1fdd6`; frischer leerer HTTP-Cache, keine bekannten Advisories |
| `uv sync --locked --only-group security --no-install-project` plus `uv run --no-sync python -I scripts/semgrep_release_gate.py` | finaler Post-MW220-111-Scope grün: 218 Manifestdateien / SHA-256 `45e0e74e02ef8d9fb9de4dd0a31455095890ce3d6c9ad7c11d3c5640e23a029c`, 168 Targets / SHA-256 `d54286198b9fca7419b0db6728cd5a48e67269d5f8cf9c8f2fdda1e163a92f8e`, 49 Policy-Skips, 1.074 Definitionen, 342 Rule-IDs, 20/20 allowgelistete Matches, 0 unerwartete Findings/Errors/Skipped-Rules/Fixpoint-Timeouts |
| actionlint/ShellCheck/Pyflakes; Zizmor regular/pedantic | 1 Workflow, jeweils 0 Befunde |
| Gitleaks Historie/Worktree und Unicode-/Bidi-/NUL-/Control-/Merge-Marker | 279 Commits und kanonischer 409-Dateien-Indexkandidat ohne Leak; Unicode-/Bidi-/NUL-/Control-/CR-/ungültige-UTF-8-/Symlink-/Reparse-/Pfad-/Case-/Artefakt-/Merge-Marker-Inventar ohne Befund |
| `git diff --check` und P0-Minimalrepros | gestagter 152-Dateien-Diff ohne Whitespacefehler; P0-Regressionen durch fokussierte Cluster und beide vollständigen Kandidatenläufe grün |
| CI-Export identische Basis / Environment-Drift | Post-MW220-111-Kandidat: identische Basis 288 Bytes, SHA-256 `3a01ee2d05da06ac61c6fb3a0e4dc4bb9c5cf89c2b2daa46e5ab55080c40cc7f`; Drift: Exit 1 und stale Artefakt gelöscht; Restore erneut byteidentisch |
| Projektumgebung vor/nach E2E | Post-MW220-111-Warmlauf vor/nach exakt identisch: 11.597 Dateien / 484.925.395 Bytes / SHA-256 `95c1fed54da9cbdfdd8ab7d7addec3b63deb11b88e92d85968d2cb42e3488d82` |
| isolierte pytest-8.2.2-Boundary-/Conftest-Matrix | lokal fokussiert grün; Remote Windows/Ubuntu wegen Billing übersprungen, kein PASS |
| dokumentierter Dogfooding-Pilot auf dem Post-MW220-111-Kandidaten | 90 total, 86 killed, 4 äquivalente Survivors, 0 timeout/suspicious/skipped/no-tests/unchecked, 95,6 %, 105,4 s |
| Branch-/PR-Publikation | ausstehend |
| GitHub-CI auf exakt dem publizierten finalen Commit | auf ausdrückliche Nutzeranweisung wegen Billing übersprungen; kein PASS |

**Technisches Urteil: lokales Commit-/Publikations-GO, noch kein Release-Gesamt-GO.** Alle 111 Befunde sind implementiert und gezielt beziehungsweise deterministisch belegt; vollständige Post-MW220-111-Suite, Dependency-Audit, finaler Dogfood-Recheck, kanonisches Semgrep-Gate, reproduzierbarer Kandidatenbuild und Git-owned Inventar sind grün. Es folgen Commit, Push und PR-Integration; erst der verifizierte integrierte `main`-Commit wird erneut gebaut und darf den annotierten Tag `v2.21.0` und das GitHub-Release tragen. GitHub-CI wird wegen des Billing-Problems auf ausdrückliche Nutzeranweisung übersprungen; das verbleibt eine akzeptierte Evidenzlücke und ist kein CI-PASS.
