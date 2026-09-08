# BUGFIXUNG ROADMAP – mutmut-win 2.20.0 → 2.21.0 → 2.21.1

**Stand:** 2026-09-08
**Quellen:** [ANALYSE_MUTMUTWIN220.md](ANALYSE_MUTMUTWIN220.md) und
[ANALYSE_MUTMUTWIN221.md](ANALYSE_MUTMUTWIN221.md)

**Ziel:** Die für Windows und exakt CPython 3.14.7 bestätigten MW221-Defekte
schließen und als v2.21.1 veröffentlichen.

**Arbeitsbaum:** v2.21.0 ist als Tag und GitHub-Release auf
`40b6af31da66f3544ab9d1a38d34511e7e02c79a` / Tree
`9fe800a9849fe35cf87f57b2f098ee02a08cd76a` veröffentlicht. Die aktuelle
Reparatur erfolgt auf `fix/v2.21.1-windows314`.

**Aktueller Stand:** Die vollständigen lokalen Implementierungsgates einschließlich strikter Coverage-Suite,
Quality, Dependencies, kanonischem Semgrep-/Native-Gate, Hygiene und Dogfood sind
auf Commit `6e12964f9a0460e7faf1b77d9e70a8f8c9f53a3b` / Tree `bfc7b834421630f5e0d51eef590b8a6db449943c` abgeschlossen.
27 MW221-Zielsystemfixes und alle 70 CX221-Befunde (2 P0, 63 P1, 5 P2) sind
`VERIFIED_FIXED`; MW221-003 bleibt `OPEN_PROCESS`. Die lokale Candidate-Attestierung
ist für Review und die folgende commit-genaue Validierung vorbereitet. Die durch
diese Dokumentbytes neu entstehende Candidate-Identität wird erst nach dem Commit
extern bestimmt. Sämtliche vertraglichen Candidate-Gates, einschließlich der
vollständigen Suite und Dogfood, sind auf diesem neuen Commit vor Push zu wiederholen.
Integration, integrierte Gates, reproduzierbare Artefakte, Installed-Smokes,
annotiertes Tag und GitHub-Release bleiben bis zu ihren tatsächlichen Nachweisen offen.
Die historische MW220-ID-Menge bleibt unverändert bei 115. Die MW221-Summe bleibt
46: 27 VERIFIED_FIXED, 7 ACCEPTED_LIMITATION, 3 REJECTED_AS_BUG,
4 OUT_OF_TARGET, 4 MIXED und 1 OPEN_PROCESS.

## 0. Verbindlicher v2.21.1-Vertrag

1. Unterstütztes Laufzeitsystem ist ausschließlich Windows mit exakt CPython
   3.14.7. Frühere Interpreter sowie Linux/POSIX/macOS sind kein Releasegate.
2. Ein fokussierter Test beweist nur die konkrete Implementierung. Release-
   autorität entsteht erst aus dem vollständigen quieszenten Zielsystemgate,
   Securitygate, reproduzierbaren Artefakten und Installed-Artifact-Smokes.
3. Eine wegen Billing nicht gestartete neue GitHub-CI ist eine akzeptierte
   Evidenzlücke und weder PASS noch FAIL. Tatsächlich ausgeführte Jobs werden
   weiterhin vollständig adjudiziert.
4. LIVE-State darf keine Erfolgsflags, Branches, Commits oder Prosa als
   unveränderliche Wahrheit festpinnen. Unit-Tests prüfen Struktur und logische
   Zustandsübergänge; Remotezustand wird direkt vor Remote-Writes live gelesen.
5. Das veröffentlichte annotierte Tag `v2.21.0` bleibt unverändert an seiner
   bestehenden Releaseprovenienz. Es wird weder verschoben noch gelöscht;
   v2.21.1 erhält nach seinen eigenen Gates ein separates annotiertes Tag.
6. Die reale v2.21.0-GitHub-CI war rot (Quality `99647140872`, Ubuntu-Boundary
   `99647141304`, Windows-Security `99647141196`) und ist kein PASS. Läuft eine
   neue v2.21.1-CI wegen Billing nicht an, lautet ihr Status `NOT_EXECUTED`:
   akzeptierte Evidenzlücke, weder PASS noch FAIL.

Der lokale Legacy-ZIP-Arbeitsbaum wurde byte- und inventarbasiert vollständig in den Clone migriert und enthält keine exklusiven relevanten Dateien. Autoritativ und allein bearbeitet wird `<repository root>`; der Legacy-Baum ist keine zweite Source of Truth.

> **Scopehinweis zu den folgenden historischen Abschnitten:** Die Kapitel 1 bis
> 12 dokumentieren die breitere MW220-Arbeit einschließlich Linux- und
> Mehrversions-Evidenz. Sie begründen keinen aktuellen Runtime-Support. Für
> v2.21.1 gilt ausschließlich der Vertrag aus Abschnitt 0: Windows und exakt
> CPython 3.14.7. Abschnitt 13 ist der verbindliche Follow-up-Plan.

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

**Status: implementiert; frühere Artefaktsnapshots durch MW220-112 bis -114 ungültig, reparierter Doppelbuild ausstehend.** Hatch verwendet eine Sdist-Allowlist. `LICENSE` enthält ISC, den übernommenen BSD-3-Clause-Text und für die CPython-abgeleiteten Spawnadapter den vollständigen PSF-2.0-Text samt Copyright-Hinweis und Änderungszusammenfassung; die Paketmetadaten verwenden `ISC AND BSD-3-Clause AND PSF-2.0` (MW220-035/-072). Wheel/Sdist werden erst vom reparierten, integrierten Follow-up-Commit gebaut, inventarisiert und bytegenau gegen die Lizenzdatei geprüft.

- Hatch-Sdist allowlisten oder interne Verzeichnisse vollständig ausschließen.
- Wheel-/Sdist-Inhaltstest ergänzen.
- .claude, .serena, .sprint, interne Reviews/Memory und lokale Settings nie ausliefern.
- den vollständigen Composite-Lizenzvertrag samt PSF-Notice/Änderungszusammenfassung als Wheel-/Sdist-Datei verifizieren.

### C2. Tooling und Abhängigkeiten

**Status: implementiert; lokale Gesamtgates grün.** Ruff verwendet `extend-exclude`; click/msgpack/pip und der Lock wurden auf die korrigierten Mindeststände aktualisiert. Ruff, Format, Cross-Platform-mypy, Lockprüfung und Audit des reparierten Gesamtbaums sind in Abschnitt 12 belegt.

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

**Status: umgesetzt und am realen Consumer verifiziert.** Solange selektive Hit-Zuordnung nicht end-to-end beweisbar ist, bleibt Mapping nichtautoritativ und nutzt die Vollsuite. Das vorhandene #130/360-B3-Budget setzt dafür `max(60, clean_wall × timeout_multiplier)` an. Der isolierte GitHub-Issue-#133-Repro auf Consumer-Snapshot `8296cd9a…` beendete genau einen bekannten `x_verify`-Mutanten als killed: `completed 1/1`, `pending 0`, `reused 0`, 0 Timeout/Suspicious/Skipped/No-tests, Orchestrator-Exit 0 und 1,8833385 s DB-Taskdauer bei nominal rund 111 s Vollsuite-Budget. Der damalige uncommittete 227-Mutanten-Arbeitsbaum ist nicht bytegenau rekonstruierbar; der Canary bindet den letzten Commit vor Issue-Erstellung, die dokumentierte Ad-hoc-Konfiguration und den problematischen `\boxed{42}`-Node-ID. Es ist kein weiterer MW220-Produktionsbefund außerhalb des geschlossenen 115er-Registers erforderlich. Vollsuite-Verdicts dürfen bei unverändertem Source-/Universe-Fast-Path und identischem vollständigem Kontextdigest sicher wiederverwendet werden (MW220-047).

**Exit:** Die gezielten Regressionstests sind vorhanden; Welle E gilt erst nach der vollständigen Matrix in Abschnitt 12 als releaseverifiziert.

## 7. Welle F – dritte Welle und finale Multi-Agenten-Diff-, Claim- und Boundary-Reaudits

### F1. Physische DB-Locks, Run-Basis und semantischer Cachezustand

**Status MW220-050 bis -053 sowie -058 bis -060: implementiert, fokussiert verifiziert und im lokalen Gesamtfinalgate grün.**

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

**Status MW220-054 bis -057, durch MW220-074 vervollständigt: implementiert, fokussiert verifiziert und im lokalen Gesamtfinalgate grün.**

- zentralen Atomic-Writer mit privater exklusiver Geschwisterdatei, Parent-/Identitätsprüfung, Replace und Fehlercleanup verwenden.
- Meta-, Apply-/Backup-, Runner- und zentrale Statewriter auf diese Grenze migrieren.
- die im finalen Writer-Inventar gefundenen Restpublisher für Stats-/CI-JSON, generierte pytest-Plugins, Phase-Guard/Proof, pytest-Argfiles und Run-Lock-Owner ebenfalls ausschließlich über den zentralen Atomic-Writer publizieren.
- generierte Python-Bytes per `generated_hash` an Meta binden; Legacy-Meta ohne Hash genau einmal regenerieren.
- `_copy_with_retry()` ohne Close→Reopen-Austauschfenster veröffentlichen und Freshness-Metadaten plattformverträglich erhalten.

**Regressionen:** `test_atomic_write_safety_220.py`, `test_runner_sidecar_safety.py`, `test_staging_authority_p1_220.py` und die Parent-Swap-/Redirect-Regressionen mit Hardlink-/Symlink-, Parent-, Temp-Substitutions-, Generated-Tamper-, Partial-Publish- und Copy-Swap-Repros. Das Produktwriter-Inventar darf außer `atomic_file.py` keinen eigenen Rename-Publisher und keinen direkten `write_text`-/`write_bytes`-/`mkstemp`-Writer enthalten; anonyme `TemporaryFile`-Bootstraps publizieren keinen Pfad und fallen nicht unter diesen Vertrag.

### F3. Windows-Containment vor erstem User Mode

**Status MW220-061 bis -063: implementiert, fokussiert verifiziert und im lokalen Gesamtfinalgate grün.**

- Job-Mitgliedschaft atomar über `PROC_THREAD_ATTRIBUTE_JOB_LIST` bereits in `CreateProcess` festlegen; kein suspendierter Create→Assign-Zwischenzustand.
- Multiprocessing-Bootstrap vollständig vor Resume in seekbarem Speicher serialisieren, damit frühes `.pth`/`sitecustomize` die Parent-Startgrenze nicht blockiert.
- private Spawnbackends auf auditiertes CPython 3.12–3.14 begrenzen; Resume-/Assignmentfehler fatal und poolweit behandeln.

**Regressionen:** `test_atomic_spawn.py`, `test_suspended_spawn.py`, `test_process_worker.py` sowie die Windows-Fälle `test_pool_has_no_post_create_assignment_hard_exit_window` und `test_wedged_sitecustomize_large_payload_is_contained_and_nonblocking` in `test_pool_shutdown.py`.

### F4. POSIX-Pre-Interpreter-Session, PGID-Evidenz, Hard-Parent-Liveness und Cleanup

**Status MW220-064 bis -068, durch MW220-075 ergänzt: implementiert, laut Prozess-/Diff-Reaudit fokussiert verifiziert und im lokalen Gesamtfinalgate grün.**

- Multiprocessing-Generation bereits in `fork_exec` in eine eigene Session bringen, Bootstrap vor Kindstart seekbar serialisieren und Parent-Liveness über eine separate Pipe erhalten.
- pytest hinter einem EOF-sicheren Pre-exec-Pipe-Gate starten, Worker-ID/PGID synchron an den Executor publizieren und erst danach Interpreter-/Nutzcode freigeben.
- publizierte PGIDs executorweit halten und bei Worker-`SIGKILL` per `killpg` reapen.
- auf Linux am privaten Child-Entry zuerst `PR_SET_PDEATHSIG` setzen und die erwartete Parent-PID unmittelbar erneut prüfen; danach EOF-Watcher und `killpg` als Liveness-/Baumfallback verwenden.
- Executor- und Typechecker-Cleanup-Stufen unabhängig und begrenzt ausführen; Cleanupfehler dürfen spätere Ressourcen und Originalfehler nicht verdrängen.
- erfolgreichem Generation-`DONE` einen eigenen begrenzten 15-Sekunden-Join geben.

**Regressionen:** POSIX-Teile von `test_generation_supervisor.py`, realer WSL-Test `test_worker_sigkill_reaps_registered_pytest_session`, reale Hard-Parent-Exit-Tests für Sessionkind und Prozessbaum unter Last, `test_cleanup_failures_do_not_skip_later_resources_or_escape`, `test_job_close_failure_does_not_skip_fallback_kill_or_mask_timeout` und `test_done_teardown_uses_its_own_generous_bounded_timeout`.

**Restgrenze:** Linux ist ab dem privaten Child-Entry durch `PR_SET_PDEATHSIG`, Parent-PID-Racecheck und EOF-/`killpg`-Fallback abgesichert. Auf generischem POSIX ohne cgroup-/`PDEATHSIG`-Äquivalent bleibt das kleine Pre-Entry-Fenster vor Installation des EOF-Watchdogs nicht kernelgarantiert schließbar; diese Restgrenze ist keine plattformweite Hard-Parent-Garantie.

### F5. Python-Metadaten, Composite-Lizenz, GitHub-CI und Artefakt-Supply-Chain

**Status MW220-069 bis -072: lokal implementiert und fokussiert verifiziert; Vorfix-Artefakte durch MW220-112 bis -114 ungültig, reparierter Rebuild ausstehend.** Die Remote-CI wurde tatsächlich ausgeführt und deckte drei weitere Blocker auf; der Workflow besitzt keinen Gesamt-PASS.

- Runtimevertrag auf CPython 3.12–3.14 begrenzen und Klassifikatoren/README angleichen.
- vollständigen PSF-2.0-Text, Copyright-Hinweis und Änderungszusammenfassung für die CPython-abgeleiteten Backends liefern und den Composite-Vertrag `ISC AND BSD-3-Clause AND PSF-2.0` in Metadaten und Artefakten pinnen.
- GitHub-CI mit minimalen Berechtigungen und Windows-/Ubuntu-Matrix über 3.12, 3.13 und 3.14 bereitstellen.
- Lock, Quality, Tests, matrixweites Audit, Build und installierte Artefakt-Smokes trennen; keine globale Frozen-Konfiguration darf `uv lock --check` neutralisieren.
- ausschließlich allowgelistete Actions an vollständige Commit-SHAs pinnen; Wheel und Sdist zweimal offline aus dem gelockten Build-Environment bauen, vergleichen, übertragen, isoliert installieren und smoke-testen.

**Exit:** Statische Verträge, vollständige lokale Cross-Platform-Matrix, Lizenzbytes und Inventar im reproduzierbaren finalen Wheel/Sdist sind auf demselben reparierten Follow-up-Commit grün. Eine Billing-bedingt ausbleibende Remote-CI bleibt eine akzeptierte Evidenzlücke und kein PASS.

### F6. Vollständige Execution-Basis und finaler Reaudit

**Status MW220-073 bis -075:** implementiert und fokussiert verifiziert; MW220-073 hat zusätzlich den unabhängigen fokussierten Abschluss-Reaudit bestanden. Das lokale repositoryweite Finalgate ist grün.

- Dependency-Evidenz an lesbare Bytes installierter Distributionen und Editables binden; gleiche Versionsnamen ohne identische Bytes dürfen Reuse nicht autorisieren.
- den geordneten effektiven `sys.path`, `.pth`-/unregistrierte Module, Runtime/ABI/Executable und ausnahmslos die vollständige geerbte Umgebung erfassen; vor dem Child-Start vorhandene Werte intern verwendeter Handshake-Namen bleiben Teil der Parentbasis.
- interne `sys.path`-Änderungen vor der Pre-Completion-Revalidierung exakt zurücksetzen und Verdict-Fingerprints versioniert mit voller SHA-256-Breite speichern.
- Vollständigkeit als typisierte Evidenz behandeln: Bei nicht les- oder inventarisierbarer Basis darf der technische Plan `completed` sein, aber Stats-/Verdict-Reuse bleibt gesperrt, persistierte Basis-/Konfigurationsautorität bleibt leer und CI-Export lehnt fail-closed ab.
- das restlose Atomic-Publisher-Inventar aus F2 und die Linux-Hard-Parent-Liveness samt generischer POSIX-Restgrenze aus F4 als eigenständige Reaudit-Ergebnisse festhalten.

**Exit:** Kein Cache, Verdict oder CI-Export kann aus einer unvollständigen Execution-Basis Autorität ableiten; kein eigener Produktpublisher umgeht `atomic_file.py`; Linux-Hard-Parent-Exit ist ab privatem Child-Entry geschlossen, ohne die generische POSIX-Pre-Entry-Restgrenze zu verschweigen. Releaseverifikation folgt erst aus Abschnitt 12.

### F7. Generische Typechecker und immutable pytest-Grenze

**Status MW220-076 bis -078:** implementiert und durch fokussierte Regressionen sowie zwei unabhängige Boundary-Reaudits verifiziert; die reale Remote-Matrix deckte mit MW220-113 zusätzlich einen nicht portablen Same-byte-Identity-Test auf. Dessen Linux-/Windows-Fokussierung ist grün, das Gesamtfinalgate bleibt offen.

- jedes nicht leere generische `type_check_command` als nicht vollständig inventarisierbare Execution-Basis markieren; technische Klassifikation zulassen, aber Stats-/Verdict-Reuse, `--min-score` und CI-Export fail-closed sperren.
- moderne und historische Runs über eine zentrale typisierte Incompleteness-Klassifikation auswerten; `results` und `browse` müssen unvollständige Basis sichtbar als `release-ready: no` kennzeichnen.
- eine einzige immutable pytest-Boundary vor jedem Run einfrieren: Staging-Root, Config und explizite Testziele an kanonische Pfade, Typen, Dateisystemidentitäten und Datei-Digests binden.
- pytest-Optionen und Argfile-Injektion in `tests_dir` ablehnen, interne Targets nach `--` transportieren und Boundary-Revalidierung in Runner, Executor, Worker sowie bei leerer Taskliste erzwingen; Boundary-Drift ist fatal.
- frühen Child-Guard vor pytest-Conftest-Preloading installieren: Exact-File-Autorität umfasst keine benachbarten/übergeordneten Conftests, Directory-Autorität nur den eigenen Baum und keine Routing-Vorfahren; externe `testpaths` ohne eingefrorene Identität scheitern.
- pytest-Unterstützung fail-closed auf ≥ 8.2 und < 10 begrenzen, unbekannte/unparsebare Versionen vor Locks/DB/Stagingwrites ablehnen und die privaten Multi-Root-Conftest-Hooks mit echten pytest-8.2.2-/9.x-Prozessen sowie eigener Windows-/Ubuntu-CI-Stufe überwachen.

**Exit:** Kein generischer Checker kann Releaseautorität vortäuschen; kein pytest-Target, Config-, Root- oder Conftest-Pfad kann die eingefrorene Execution-Basis statisch oder zwischen Parent- und Childprüfung umgehen; lokale pytest-8.2.2-/9.x-Regressionsläufe sind unter den Windows-/Linux-Grenzen grün. Tatsächlich verfügbare Remote-Läufe werden adjudiziert; eine Billing-bedingt ausbleibende Follow-up-CI bleibt Evidenzlücke und kein PASS.

### F8. Adversariale Finalgate-, Dogfood- und Releaseevidenz-Closure

**Status MW220-079 bis -111:** auf dem ersten Kandidaten lokal implementiert und fokussiert verifiziert. Dessen vollständige Suite, stabiler `.venv`-Digest, Dogfood, Semgrep, Doppelbuild und Inventar bleiben historische Evidenz, besitzen nach MW220-112 bis -114 aber keine Finalgate-Autorität mehr.

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
- Semgrep-Childumgebung von allen geerbten `GIT_*`-, `PYTHON*`-, `SEMGREP_*`-, `UV_*`-, Credential-, Home-, Settings- und Temp-Autoritäten isolieren; Wrapper und Scanner exakt an die deklarierte aktive externe `UV_PROJECT_ENVIRONMENT` binden.
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

### F9. Remote-CI-Releaseblocker und Report-Vertrag MW220-112 bis -115

**Status:** Alle vier Befunde sind auf `fix/v2.21.0-release-blockers` implementiert und lokal vollständig verifiziert: MW220-112 unter den Windows-/Linux-Typansichten, MW220-113 als reiner Testportabilitätsfehler unter Linux und Windows, MW220-114 durch den seriellen Vollscanvertrag samt wiederholten realen Windows-Läufen und MW220-115 durch exakte Follow-up-IDs plus eigenen Report-Vertrag. Der Post-MW220-115-Strict-Lauf bestand mit 2.002 Tests und 44 Skips.

- `mypy` explizit unter den Plattformansichten `linux` und `win32` ohne Incremental-Cache ausführen; plattformspezifische Prozessmodule müssen unter beiden Typeshed-Sichten fehlerfrei sein.
- Same-byte-Identity-Negativtests müssen die alte Datei über einen Hardlink-Anker am Leben halten, damit OverlayFS die gerade freigegebene Geräte-/Inodeidentität nicht wiederverwenden kann; dies ist Testhärte und kein Produktions-TOCTOU-Fix.
- Den finalen Semgrep-Bundlescan seriell mit `--jobs 1` ausführen, während die reine Regelmaterialisierung vier Shards behalten darf; `time.fixpoint_timeouts` bleibt vollständig fail-closed und muss die betroffene Diagnose sichtbar machen.
- LIVE-State darf kein Finding über einen losen Zahlenteilstring vortäuschen; alle Follow-up-IDs, Gesamtzahlen, Prioritäten, Adjudikationen und Finalgate-/Remote-Ausnahmen werden explizit in Analyse und Roadmap gebunden.
- Nach jedem Fix die fokussierten Linux-/Windows-Regressionen, die vollständige lokale Matrix, den kanonischen Semgrep-Wrapper, Dogfood, Inventar und Doppelbuild erneut ausführen; danach Follow-up-PR publizieren und jeden tatsächlich verfügbaren Remote-CI-Befund adjudizieren. Eine Billing-bedingt nicht verfügbare Remote-CI blockiert nach ausdrücklicher Nutzerfreigabe nicht, bleibt aber eine dokumentierte Evidenzlücke und niemals ein PASS.

**Exit:** Linux- und Windows-mypy fehlerfrei; beide Same-byte-Identity-Cluster plattformübergreifend grün; wiederholter serieller Windows-Semgrep-Finalscan ohne Fixpoint-Timeout bei zuvor grünem Ubuntu-Vertrag; exakter Report-/Live-State-Vertrag; neue byteidentische Artefakte aus dem reparierten integrierten Commit. Eine nicht verfügbare Follow-up-CI wird dokumentiert und nie als PASS gewertet.

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

Seit der zweiten Welle wird ausschließlich im Git-Clone unter `<repository root>` gearbeitet. PR #134 ist als `55d25dfff2225ffb3e4a2b56ead4a3c190d054cf` mit Tree `761e264a91a52bda4c284f3f36fe53954d7fff2b` integriert; die CI-Blocker werden auf `fix/v2.21.0-release-blockers` repariert. Follow-up-PR, endgültiger Tag und GitHub-Release sind noch nicht erfolgt. Der vorzeitige Tag wurde entfernt. Der Legacy-ZIP-Baum ist nicht autoritativ.

## 10. Verifikationsmatrix

Nach jeder Welle:

    uv run --no-sync pytest -q -p no:cacheprovider <fokussierte Tests>
    uv run --no-sync ruff check --no-cache <geänderte Dateien>
    uv run --no-sync ruff format --no-cache --check <geänderte Dateien>
    uv run --no-sync mypy --no-incremental --cache-dir=nul <geänderte Produktionsmodule>
    uv run --no-sync lint-imports --no-cache

Vor Abschluss:

Eine frisch angelegte absolute `UV_PROJECT_ENVIRONMENT` außerhalb des
Release-Checkouts ist dabei Vorbedingung; ebenso zeigt
`HYPOTHESIS_STORAGE_DIRECTORY` auf ein separates absolutes externes
Verzeichnis. Hypothesis 6.151.10 schreibt Cachebytes, aber keine eigene
`.gitignore`. Der Checkout darf weder `.venv`, Werkzeug-Caches mit eigener
`.gitignore` noch `.hypothesis`-Cachebytes enthalten. Wheel- und Sdist-Smoke-
Venvs werden ausschließlich getrennt unterhalb von `RUNNER_TEMP` angelegt.

    uv run --no-sync pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning
    uv run --no-sync pytest -q --cov=mutmut_win --cov-report=term-missing -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning
    uv run --no-sync ruff check --no-cache .
    uv run --no-sync ruff format --no-cache --check .
    uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/
    uv run --no-sync lint-imports --no-cache
    uv lock --check
    uv sync --locked --only-group security --no-install-project
    uv run --no-sync python -I scripts/semgrep_release_gate.py

Zusätzlich: actionlint samt ShellCheck/Pyflakes, Zizmor regular/pedantic, Gitleaks über vollständige Historie und Git-owned Worktree, Unicode-/Bidi-/NUL-/Control-/Merge-Marker-Inventar sowie `git diff --check`; vollständigen Lock exportieren und mit `pip-audit` prüfen; Wheel/Sdist zweimal aus identischen gelockten Inputs extern bauen, Byte-/SHA-/Inventargleichheit und Lizenzbytes vergleichen, mit gepinnten Twine-/Wheel-Content-Tools prüfen und isoliert installieren/smoke-testen; die externe uv-Projektumgebung vor/nach dem Testlauf stabil inventarisieren und beide Artefakt-Smoke-Venvs ausschließlich getrennt unterhalb von `RUNNER_TEMP` anlegen; alle P0-Minimalrepros und die echte pytest-8.2.2-Grenze erneut ausführen; CI-Export auf identischer Basis akzeptieren und bei Environment-Drift fail-closed ablehnen; einen dokumentierten Vier-Worker-Dogfooding-Piloten auf genau dem danach eingefrorenen finalen Baum ausführen. Danach Follow-up-PR publizieren. Eine Billing-bedingt ausbleibende weitere GitHub-CI wird als Evidenzlücke dokumentiert und nie als PASS gewertet.

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
| 2026-08-31 | PR-Integration | PR #134 als Mergecommit `55d25dfff2225ffb3e4a2b56ead4a3c190d054cf` mit unverändertem Tree `761e264a91a52bda4c284f3f36fe53954d7fff2b` in `main` integriert |
| 2026-08-31 | Remote-CI-Reaudit | reale CI deckte MW220-112 bis -114 auf; kein PASS. Vorfix-Artefakte invalidiert, vorzeitiger `v2.21.0`-Tag vor Release entfernt |
| 2026-08-31 | MW220-113-Adjudikation | kein Produktions-TOCTOU; OverlayFS-Inode-Reuse machte zwei Tests nicht portabel. Hardlink-Anker; Linux 42/5 und Windows 45/2 fokussiert grün |
| 2026-09-01 | MW220-112/-114-Closure | Windows-/Linux-mypy jeweils 38 Dateien/0 Fehler; serieller Semgrep-Vollscan mit unverändertem Vier-Shard-Bootstrap, 70 Wrappertests und wiederholte reale Windows-Läufe ohne Fixpoint-Timeout; letzter exakter Kandidatenlauf mit 218 Manifestdateien, Manifest-SHA-256 `2915abda1e40304ac05145115cdf2feede0d8e956a665f049b0d5d7aa8a6dde1`, 49 Policy-Skips und Target-SHA-256 `d54286198b9fca7419b0db6728cd5a48e67269d5f8cf9c8f2fdda1e163a92f8e` |
| 2026-09-01 | Reparierte lokale Matrix | vollständige Suite 2.001/44; Coverage 2.001/44 bei 85 % und 8.524/1.275; `.venv` 4.675 Dateien / 120.311.470 Bytes / SHA-256 `2ecc7ac4bebcbda560bcc06b230b5da92da9ccfd1d5be26cc62ba9d0851bddf8`; Ruff, Format, Import-Linter, Lock, Audit, Gitleaks und `git diff --check` grün |
| 2026-09-01 | Reparierter Dogfood-Recheck | 90 total, 86 killed, vier äquivalente Survivors, 0 timeout/suspicious/skipped/no-tests/type-check-caught/segfault/unchecked, 95,6 %, 81,0 s |
| 2026-09-01 | MW220-115 Report-Vertrag | loser `114`-Teilstring und fehlende Analyse-/Roadmap-Bindung gefunden; exakte Follow-up-IDs, 115er Gesamtzählung und stale-Claim-Verbote implementiert; 12 fokussierte Tests und vollständiger Strict-Lauf 2.002/44 grün |
| 2026-09-01 | GitHub Issue #133 Closure-Repro | detached Consumer-Snapshot `8296cd9a…`, Kandidat 2.21.0, genau `math_matcher.x_verify__mutmut_1`: completed 1/1, killed, 0 pending/reused/timeout/suspicious/skipped/no-tests, Orchestrator-Exit 0; MW220-047 plus #130/360-B3 bestätigt, kein weiterer formaler MW220-Befund außerhalb des 115er-Registers |

## 12. Finale Abschlussnachweise

| Gate | Bisherige Evidenz / finaler Recheck |
|---|---|
| `uv run --no-sync pytest -q -W error::pytest.PytestUnhandledThreadExceptionWarning` | reparierter Post-MW220-115-Baum 2.002/44 grün |
| Coverage mit identischem striktem Warnungsgate | reparierter Baum 2.001/44, 85 %, 8.524 Statements / 1.275 Missing |
| `uv run --no-sync ruff check src tests benchmarks scripts` | reparierter Baum ohne Befund |
| `uv run --no-sync ruff format --check src tests benchmarks scripts` | 168 Python-Dateien bereits formatiert |
| Cross-Platform-mypy | native Windows- und `--platform linux --no-incremental`-Läufe jeweils 38 Dateien/0 Fehler; Prozessmatrix 80 bestanden/10 übersprungen |
| `uv run --no-sync lint-imports` | 37 Dateien / 123 Abhängigkeiten / 1 Vertrag grün |
| `uv lock --check` | `2.21.0`, 115 Pakete, grün |
| `uv build` plus Wheel-/Sdist-Inventar | Vorfix-Artefakte ungültig; reparierter integrierter Doppelbuild, Inventar und Smokes ausstehend |
| vollständiger `uv export --frozen --all-extras --all-groups --no-hashes --no-emit-project` plus Pip-Audit | Pip-Audit 2.10.0 über vollständigen reparierten Export ohne bekannte Advisories |
| kanonischer Semgrep-Wrapper | serieller Finalscan (`--jobs 1`, Bootstrap vier Shards); 70 Wrappertests und wiederholte reale Windows-Läufe grün, Timeoutliste bleibt fatal; letzter exakter Kandidatenlauf: 218 Manifestdateien / 49 Policy-Skips / 168 Targets / 342 Regeln / 20 allowgelistete Findings / 0 Fehler oder Fixpoint-Timeouts |
| actionlint/ShellCheck/Pyflakes; Zizmor regular/pedantic | unveränderter Workflow historisch jeweils ohne Befund; letzter Recheck lokal mangels Binärdateien/Images nicht ausführbar, statische Supply-Chain-Verträge und vollständige Suite grün |
| Gitleaks Historie/Worktree und Unicode-/Bidi-/NUL-/Control-/Merge-Marker | reparierter Stand: 280 Commits und exakter 409-Dateien-Git-owned Worktree ohne Leak; frühere vollständige Zeichen-/Pfad-/Artefaktinventare bleiben für unveränderte Bereiche gültig |
| `git diff --check` und P0-Minimalrepros | aktueller Diff ohne Whitespacefehler; P0-Regressionen durch fokussierte Cluster und vollständige reparierte Suite grün |
| CI-Export identische Basis / Environment-Drift | Post-MW220-111-Kandidat: identische Basis 288 Bytes, SHA-256 `3a01ee2d05da06ac61c6fb3a0e4dc4bb9c5cf89c2b2daa46e5ab55080c40cc7f`; Drift: Exit 1 und stale Artefakt gelöscht; Restore erneut byteidentisch |
| Projektumgebung vor/nach E2E | reparierter Post-MW220-115-Lauf vor/nach exakt identisch: 5.119 Dateien / 126.091.419 Bytes / SHA-256 `8e5a29550f9f8a61811a63687c90c31aa962ddc8e8ab0f34af34334da9553268` |
| isolierte pytest-8.2.2-Boundary-/Conftest-Matrix | MW220-113 fokussiert korrigiert: Linux 42 bestanden/5 übersprungen, Windows 45 bestanden/2 übersprungen; vollständige reparierte Suite grün |
| dokumentierter Dogfooding-Pilot auf dem reparierten Kandidaten | 90 total, 86 killed, 4 äquivalente Survivors, 0 timeout/suspicious/skipped/no-tests/type-check-caught/segfault/unchecked, 95,6 %, 81,0 s |
| realer GitHub-Issue-#133-Consumer-Repro | historischer Snapshot `8296cd9a…`, 1/1 completed und killed nach 1,8833385 s, 0 pending/reused/timeout/suspicious/skipped/no-tests, Orchestrator-Exit 0; Vollsuite-Budget nominal rund 111 s |
| Branch-/PR-Publikation | PR #134 integriert; Reparaturbranch und Follow-up-PR ausstehend |
| GitHub-CI | tatsächlich ausgeführt und an MW220-112 bis -114 blockiert; kein PASS |

**Technisches Urteil dieses damaligen Vorveröffentlichungsstands: Release-NO-GO nur noch bis zur Veröffentlichungskette.** 115 Befunde waren bestätigt; MW220-112 bis -115 waren implementiert, und die vollständige lokale Cross-Platform-Matrix war grün. PR #134 war integriert, seine Artefakte waren jedoch nicht mehr releaseautoritativ. Der vorzeitige Tag war entfernt; `v2.21.0`-Tag und GitHub-Release waren damals absent. Erst Follow-up-Integration und integrierter Doppelbuild samt Smokes erlaubten die Veröffentlichung. Eine Billing-bedingt ausbleibende Follow-up-CI blieb akzeptierte Evidenzlücke und kein PASS.

> **Historischer Hinweis:** Das vorstehende Urteil beschreibt den Zustand vor
> der tatsächlichen Veröffentlichung von v2.21.0. Der aktuelle, verbindliche
> v2.21.1-Plan folgt; die Detailadjudikation steht in
> `ANALYSE_MUTMUTWIN221.md`.

## 13. MW221-Fixplan für v2.21.1

### 13.1 P0/P1-Zielsystemkorrekturen

| IDs | Maßnahme | Stand | Exitkriterium |
|---|---|---|---|
| MW221-004 | Pfadalias und Redirect über Komponenten-/Objektidentität unterscheiden, in Atomic Writer, DB, Staging, pytest-Boundary und Run-Lock konsistent | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | deterministische Alias-Seam-Tests plus reale 8.3-Probe, sofern das Volume einen Alias bereitstellt |
| MW221-005 | Apply/Show aus öffentlicher Originaldefinition erzeugen; Signatur, Defaults, Annotationen, Dekoratoren und Quellkontext erhalten | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | Roundtrip-Test führt die angewandte Mutation mit identischer Aufrufsignatur aus; erzeugter Patch ist anwendbar |
| MW221-006/-007 | Tokenizerfehler kontrolliert behandeln; abgeleitetes `mutants/` nicht rekursiv in seinen eigenen Stats-Digest aufnehmen | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | Tab-/Indent-Repros und vollständiger Run ohne Post-Stats-Selbstdrift |
| MW221-008 | Nichtautoritäre Mappingdaten nur zur Reihenfolge unabhängiger Mutanten-Tasks verwenden; innerhalb jedes Tasks native pytest-Reihenfolge, vollständige Suite und Vollsuite-Fingerprint bewahren, beim ersten echten Fehler abbrechen | sichere Teilkorrektur implementiert; selektive Autorität bleibt bewusst offen; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | reihenfolgeabhängige Gegenprobe beweist unveränderte pytest-Reihenfolge; Survivor durchläuft alle Tests; Reuse bleibt an die Vollsuite gebunden |
| MW221-010/-011 | Full-/Subset-Autorität persistieren; Subset-Export sperren; Subset-Population in CLI `results` und Browser sichtbar als nicht release-ready kennzeichnen; Git-Dateinamen NUL-separiert lesen | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | Legacy-/Browser-/CLI-Subset exportiert nicht; Total/Score ist sichtbar auf den Subset-Scope begrenzt; non-ASCII-`--since-commit`-Repro vollständig |
| MW221-013 | Core-Drift terminal halten, reine Ambient-Drift diagnostisch abschließen und Basis-/Reuse-Autorität atomar entziehen | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | Source-/Test-/Config-/Projektimport-Drift bleibt `failed`; Ambient-Drift bleibt sichtbar, aber Score, Export und Reuse sind fail-closed; Widerrufsfehler bleibt recoveryfähig `running` |
| MW221-014/-017/-018 | stille Linkauslassung diagnostizieren; Fake-PID-Kills verhindern; E2E muss echten Survivor beweisen | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | fokussierte Safety-Tests und vollständige E2E-Referenz grün |
| MW221-019 / MW220-108/-115 | LIVE-State reparieren und Governance von Prosa-/Bool-Pins auf Zustandsinvarianten umstellen | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt | Governance-Test bleibt sowohl bei ehrlichem In-Progress- als auch Abschlusszustand gültig und erkennt inkonsistente Übergänge |

MW221-001/-002/-015/-016 werden nicht als Produktfix in v2.21.1 verfolgt, weil
sie ausschließlich nicht unterstützte Interpreter oder POSIX betreffen. Der
ehemals breitere Metadaten-/CI-/Dokumentationsvertrag wird stattdessen ehrlich
auf Windows/CPython 3.14.7 verengt.

### 13.2 P2-Korrekturen

| IDs | Maßnahme | Stand |
|---|---|---|
| MW221-020/-023/-024 | PEP-263-Roundtrip, vollständige Methodenargumente, parameterlose/`*args`-Methoden | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| MW221-021/-026/-027/-028 | `typing_extensions.cast`, Regex-Klassen/Cache, strukturelle Docstrings und exakte Pragmas | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| MW221-030/-031/-032 | Lock-Contention diagnostizieren, O(n)-Plan-Dublettenerkennung, Apply-Auflösung vor Invalidierung | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| MW221-035/-036/-041/-042 | Dotenv-Basisbindung, Root-only-Workspace-Ausschlüsse, `#`-sichere Config und Node-ID-Normalisierung | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| MW221-025/-037/-043 | kollisionssicherer Trampolin-Namensraum, vollständiger SQLite-Sidecar-Ausschluss und Exit-0-No-op für leere gültige `--since-commit`-Diffs | implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| MW221-022 | Async-Generatoren und PEP-695-Generika nur mit einem eigenen semantikerhaltenden Operatorvertrag erweitern | akzeptierte konservative Grenze: explizite Regressionen pinnen den Skip; kein ungeprüftes Scope-Wachstum und keine protokollwidrigen Mutanten im Releasefix |
| MW221-029/-033/-039 | Dev-Schema-, Legacy-Retention- und Watchdog-Adjudikation | kein offener Releasebug: v2.20.0 besaß keine `mutation_run`-Tabelle; Legacy-Verdicts werden vor Apply absichtlich fail-closed invalidiert; der nur bei queued/no-in-flight greifende 60-s-Watchdog ist eine nicht reproduzierte theoretische Availability-Grenze |
| MW221-040/-044 | Filesystem-/Co-Installationsgrenzen | MW221-040 im README als fail-closed Identitätsgrenze dokumentiert; kein universeller Kompatibilitätsclaim |
| MW221-045 | pytest-/Security-/Git-Supply-Chain-Bündel | hashgepinntes pytest-Overlay, vollständiger Semgrep-Targetscope, isoliertes Git-Inventar einschließlich `.git/info/exclude` und PR-only Cancellation implementiert; Registry/`--metrics off` bleibt bis zu einem vendorten Regelbundle dokumentierte Grenze |
| MW221-046 | gemischte Testharness-Schulden | Python-3.14-Orakel, Survivor-Blindheit und Fake-PID-Cleanup geschlossen; übrige Testschulden einzeln führen |

MW221-008 erhält bewusst keine Auslassungsautorität: Mapping-Hints optimieren
nur die Mutanten-Task-Reihenfolge, niemals die pytest-Reihenfolge oder
Testpopulation. MW221-009, MW221-034 und MW221-038
werden nicht durch eine weniger strenge Implementierung „behoben“; ihre
konservativen Grenzen verhindern stale oder unbelegte Releaseevidenz. Bei
MW221-013 bleibt dieselbe Strenge für fachliche Core-Drift erhalten, während
reine Ambient-Drift diagnostische Ergebnisse ohne Releaseautorität bewahren darf.

### 13.3 Codex-Follow-up-Findings

Diese eigene ID-Serie ergänzt Claudes unveränderte MW221-001-bis--046-Matrix
und fließt nicht in deren Statussumme ein.

Sie umfasst exakt CX221-001 bis CX221-070; ihre Prioritätsverteilung lautet
2 P0, 63 P1 und 5 P2.

| ID | Maßnahme | Stand |
|---|---|---|
| CX221-001 | Explizite `sys.path`-Unterbäume wie `project/build` separat hashen, wenn der Projektroot sie bei seinem Root-Inventar übersprungen hat | VERIFIED_FIXED; implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-002 | Versteckte Toolverzeichnisse in jeder Tiefe rekursiv ausschließen, generische fachliche Verzeichnisnamen aber nur am Workspace-Root | VERIFIED_FIXED; implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-003 | `tests_dir` und Git-Diffpfade unter Windows komponentenweise case-normalisieren | VERIFIED_FIXED; implementiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-004 | `show`/Browser wie `apply` an den persistierten `source_hash` binden und bei stale Staging fail-closed diagnostizieren | VERIFIED_FIXED; implementiert; Render- und CLI-Regression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-005 | Lokale Identifier, die den reservierten Mutantentrenner erst an der ID-Grenze bilden, disjunkt und reversibel kodieren; Apply/Show auf die exakte Ursprungsdefinition binden | VERIFIED_FIXED; implementiert; E2E-Regression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-006 | Reservierten Trennertext in Modul-/Paketkomponenten bewahren und nur den letzten lokalen numerischen Mutantensuffix parsen | VERIFIED_FIXED; implementiert; Mapping-/Parserregressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-007 | Explizit konfigurierte externe Test-, Fixture- und Importbäume vollständig nach den tatsächlich gestagten Bytes hashen | VERIFIED_FIXED; implementiert; externe Generic-Child-Regression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-008 | PEP-758-Mehrfach-Exceptions in allen Scan-Targets innerhalb des Parservertrags von Semgrep 1.175.0 halten, ohne Gate oder Allowlist abzuschwächen | VERIFIED_FIXED; implementiert; explizite Klammern plus AST-Guard; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-009 | Vollständige Staging-Ownership führen und gelöschte Source-/Fixture-/Rootdateien, Ghosts, Sidecars und read-only-Artefakte prunen; Read-only-Replacement und Modus-Restore an contained Non-Reparse-Identität und `st_nlink == 1` binden, externe Hardlinks fail-closed lassen | VERIFIED_FIXED; implementiert; Lösch-, Read-only-, Identity- und Hardlink-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-010 | Persistierten `generated_hash` als gemeinsame Provenienzgrenze für Show, Apply und Run erzwingen | VERIFIED_FIXED; implementiert; Missing-/Mismatch-/Edit-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-011 | Stabilen Digest über alle ausführbaren Staging- und Fixturebytes einfrieren und auf jedem autoritativen Erfolgspfad erneut validieren | VERIFIED_FIXED; implementiert; Phasen-/Driftregressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-012 | Self-Dogfood-Governance nur in eindeutig erkennbarem generiertem Mutation-Staging überspringen; Git-lose normale Checkouts weiter prüfen | VERIFIED_FIXED; implementiert; Governance-Erkennung eng begrenzt; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-013 | Root-Ausschlüsse, explizite Importroots und bereits vorhandenes Staging so adjudizieren, dass keine unsichtbaren False-Green-Bytes verbleiben | VERIFIED_FIXED; implementiert; Root-/Namespace-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-014 | `.meta`-Eigentum nur über valides Schema und das gebundene Source-/Generated-Paar autorisieren; normale `.meta`-Fixtures erhalten | VERIFIED_FIXED; implementiert; Ownership-/Fixture-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-015 | Stateful pytest-/Tool-Caches isolieren und cachegesteuerte Testauswahl ohne gebundene Autorität ablehnen | VERIFIED_FIXED; implementiert; Cache-/pytest-Optionsregressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-016 | `.py`-Endungen an CLI-Ingress, Source-Walk und Mutation-Ignore unter Windows case-insensitiv erkennen | VERIFIED_FIXED; implementiert; positiver Dry-run sowie realer 16-Mutanten-/Show-Gegenlauf; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-017 | Staging-Evidenz zusätzlich an leere Verzeichnistopologie, Dateiart, Modus und relevante Metadaten binden | VERIFIED_FIXED; implementiert; Datei-/Verzeichnismetadaten-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-018 | Sichtbare Root-/Fixturebytes vollständig binden und ausschließlich klaren Runtime-/PYC-Zustand vor dem Snapshot rekursiv entfernen | VERIFIED_FIXED; implementiert; Runtime-/PYC-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-019 | Vollständigen Staging-Snapshot vor der Coverage-Phase aufnehmen und direkt danach auf unveränderte Basis prüfen | VERIFIED_FIXED; implementiert; Pre-Coverage-Driftregression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-020 | Reuse-Zuordnungen nach Fehler, Hard-Kill, Abbruch, Interrupt oder später Abschlussdrift revoke-first widerrufen; bei Widerrufsfehler den Run recoveryfähig `running` lassen | VERIFIED_FIXED; implementiert; SQLite-Trigger-/Recovery-Regression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-021 | Pytest-Report-, Temp-, Coverage- und Benchmark-Ausgaben vor Pluginstart in einen frischen externen Runtime-Root umleiten | VERIFIED_FIXED; implementiert; echte JUnit-/Coverage-/Benchmark-Gegenproben grün; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-022 | `--min-score` für Namens-, Pfad- und `--since-commit`-Subsetläufe vor Ausführung ablehnen | VERIFIED_FIXED; implementiert; drei CLI-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-023 | Ausgeschlossenen Toolstate nicht indirekt über NTFS-Verzeichnisgröße/-Linkzahl in Cross-run-Digests wiedereinführen | VERIFIED_FIXED; implementiert; 0-zu-4096-NTFS- und Topologie-Regression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-024 | Tool-eigene Atomic-Publish-Zeiten aus Cross-run-Reuse trennen, ohne die strikte In-run-Metadaten-/ABA-Evidenz zu lockern | VERIFIED_FIXED; implementiert; realer Meta-Lifecycle und Cache-Reuse gegengeprüft; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-025 | Kanonische DB-/Cache-Ausschlüsse durch sämtliche sekundären `sys.path`-, Editable- und Distribution-Walks propagieren | VERIFIED_FIXED; implementiert; ausgeschlossene DB-Bytes und benachbarte Runtimebytes dynamisch getrennt; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-026 | Gesamtbasis in fachlichen Core und Ambient-Anteil klassifizieren; nur Ambient-Drift diagnostisch bewahren und Autorität atomar entziehen | VERIFIED_FIXED; implementiert; Core-/Ambient-/Recovery-/Export-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-027 | Unsichere Intra-Suite-Umsortierung nichtautoritativer Hints verhindern; native pytest-Reihenfolge bewahren und nur Mutanten-Tasks planen | VERIFIED_FIXED; implementiert; reihenfolgeabhängige Real-Pytest-, Timeout- und Reuse-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-028 | Phasenausführungsbeweis nicht durch ausschließlich im Call-Body übersprungene Tests autorisieren | VERIFIED_FIXED; implementiert; reale All-skipped-Pytest-Regression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-029 | DB-/Sidecar-Ausschlüsse auch in expliziten `also_copy`-/`extra_paths`-Mirrors durchsetzen und alte Stagingkopien prunen | VERIFIED_FIXED; implementiert; explizite Datei- und verschachtelte Verzeichnismirror-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-030 | Initial diagnostische Ambient-Basis bis in Stats- und Verdict-Reuse propagieren; beide Caches für diesen Lauf frisch beziehungsweise deaktiviert halten und bei Abschluss auch für eine unverändert unvollständige Basis alle aktuellen/historischen Fingerprints atomar deautorisieren | VERIFIED_FIXED; implementiert; frische Stats-, End-to-End-No-Reuse- und Future-Reuse-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-031 | Aktiven Release-Ref ohne Prosaselbstzertifikat auf Paketversion oder unmittelbaren Patchvorgänger begrenzen und README-/CLAUDE-Befehle an den kanonischen Guide binden | VERIFIED_FIXED; implementiert; exakte Guide-/README-/CLAUDE-Parser sowie Alt-/Zukunfts-/Serien-Gegenproben vorhanden; Remoteexistenz bleibt Live-Gate; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-032 | Nichtautoritative Vollsuite-Targets wie autoritative Auswahl über eine private geordnete Runtime-Argfile transportieren, damit Windows' Prozesskommandozeilenlimit die vollständige Suite nicht neutralisiert | VERIFIED_FIXED; implementiert; synthetische Zielmenge über 32.767 Zeichen beweist vollständigen Inhalt, native Reihenfolge und kurze `argv`; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-033 | Sicherheitstest-Setups an verschärfte reale Vorbedingungen binden: Phase-Guard-Double mit `skipped=False`, `--force`-Teillöschtest mit minimal gültigem Mutationsroot | VERIFIED_FIXED; implementiert; beide Orakel erreichen wieder ihre behauptete Atomic-/Löschgrenze; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-034 | uv-Hardlink-Linkzahlen aus langlebigen Project-/Dependency-/`sys.path`-Digests und deren Reopen-Identitätsvergleich entfernen, ohne die strikte In-run-Staging-Hardlink-Evidenz zu lockern | VERIFIED_FIXED; implementiert; Alias-add/remove-, Write-through-, Export-Doppelsnapshot- und Strict-Staging-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-035 | Flakiges NTFS-ABA-Testorakel auf beobachtbare leere Topologie, explizite Parent-Metadatenänderung und Dateimodus trennen | VERIFIED_FIXED; implementiert; 4/10-Flakeursache entfernt, Produktdigest unverändert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-036 | Semgrep-Allowlist-Filehash nur für CRLF/bare-CR normalisieren und Unicode-Zeilentrenner bytewirksam binden | VERIFIED_FIXED; implementiert; U+2028-Bypassregression vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-037 | Windows-Layoutroot und finalen `__init__`-Stem bei der qualifizierten Mutantenidentität case-insensitiv mit der Runtime abgleichen | VERIFIED_FIXED; implementiert; realer `SRC/pkg/__INIT__.PY`-Subprozess beweist Tokenaktivierung; weitergehende Package-/Modul-Casefold-Challenge dynamisch verworfen; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-038 | Sämtliche geplanten automatischen und konfigurierten Staginginputs gegen tool-eigene Sidecar-, Guard-, Fingerprint- und Exportziele prüfen; Modul-/Package-/Resource-Namespace-/`.pyd`-Shadowing unter `src`/`source` vor jeder Mutation fail-closed abweisen | VERIFIED_FIXED; implementiert; auch data-only Namespaces werden abgewiesen, lose Bytecodeinputs vor Ausführung gepurgt; CLI-Text/JSON, `--force`-Nichtlöschung, Direct API, Dry-run, Copy-, Case-, Package-, Native- und Präzisionsregressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-039 | Docstring-Erkennung auf konstanten `str`-Wert und erste Statementposition begrenzen, führende Bytes-/f-String-Verkettungen wieder mutieren, Semikolon-Docstrings erhalten und Wrapper-Doppelausführung verhindern | VERIFIED_FIXED; implementiert; Mutationsregressionen plus generierte Laufzeitproben mit korrektem `__doc__` und exakt einem Seiteneffekt grün; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-040 | LIVE-State auf geschlossene Phasen-/Publikationsblöcke, exakte Ref-/Commit-/Parent-/Tree-Identität des Quellbranches oder seines byteidentischen Main-Merges und Reviewstatus auf den tatsächlichen Final-/Housekeeping-Lifecycle binden; Post-Release an Kandidat, Integrationsmerge, annotiertes Tag und direkten docs-only Housekeeping-Child koppeln | VERIFIED_FIXED; implementiert; lokale/GitHub-Detached-, Branch-, Main-Merge-, Version-, Tagtyp/-ziel-, Candidate-/Integration-Tree-, Housekeeping-Diff- und Prozessabschluss-Gegenproben vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-041 | Generierte Quellen im Typechecker-Filter nach ihrem PEP-263-Encoding statt pauschal als UTF-8 lesen | VERIFIED_FIXED; implementiert; reale CP1252-Quelle mit Checkerfehler wird korrekt klassifiziert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-042 | `extra_paths` über eine zentrale kanonische Planner-/Copy-/Cleanup-/Runner-/Worker-Abbildung ausschließlich auf Stagingroots begrenzen; externe, rootrelative, drive-relative, geerbte und aliasbedingt abweichende Livepfade nie in `PYTHONPATH` übernehmen | VERIFIED_FIXED; implementiert; Parent-/Worker-, echter Kindimport- und reale Windows-8.3-Kreuzregressionen grün; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-043 | Post-Merge-Sequenz durch einen maschinenlesbaren Marker binden, beide reproduzierbaren Builds mit vollständigen sortierten Artefakt-/SHA-256-Inventaren vergleichen und die installierte Wheel-/Sdist-Version im Windows-Smoke exakt beweisen | VERIFIED_FIXED; implementiert; Sequenzmarker erweitert, `SHA256SUMS` und sortierte Wheel-/Sdist-Inventare beider Builds werden verglichen und publiziert, Windows prüft Hashes vor Installation sowie zweimal exakt Version 2.21.1; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-044 | Alle zusätzlichen lokalen Security-, Supply-Chain-, Reproduzierbarkeits- und Installed-Artifact-Gates mit reproduzierbaren Werkzeugpins, assetgepinntem stdlib-Runner, minimalem Semgrep-Bootstrap-Environment und kanonischen Befehlen versehen | VERIFIED_FIXED; implementiert; Python-/Native-Manifestpins, Safe-Extract, exakte Versionsausgaben, isolierte Git-/Toolzustände und vollständiger Gitleaks-Worktree/-History-Vertrag vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-045 | Automatische und konfigurierte Peer-Mirrors einschließlich fehlender Cleanup-Owner nur dann denselben Stagingtarget besitzen lassen, wenn sie dieselbe Live-Identität beziehungsweise eine konsistente Abbildung derselben Quelle darstellen | VERIFIED_FIXED; implementiert; File-/Tree-/Missing-/Ancestor-/Sentinel-Gegenproben vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-046 | Dry-run bei PEP-263-Dekodierung und physischer Source-Identity-Deduplizierung an die reale Generation angleichen | VERIFIED_FIXED; implementiert; CP1252-, Overlap- und Windows-Alias-Regressionen ohne Workspacewrite vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-047 | `show` als byte-exakten Git-Patch serialisieren: physische LF-Zeilen, CRLF/BOM/PEP-263/EOF-Erhalt, korrekte No-Newline-Marker, binäres stdout und Forensik nur auf stderr | VERIFIED_FIXED; implementiert; reale CP1252-/BOM-/CRLF-/EOF-/Unicode-Separator- und Git-Apply-Gegenproben vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-048 | Leere automatische/konfigurierte Live-Namespaces materialisieren und entfallene leere Staging-Shells bottom-up entfernen, ohne explizite Mirrorroots zu löschen | VERIFIED_FIXED; implementiert; Zwei-Run- und reale `find_spec`-/PEP-420-Regressionen vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-049 | PEP-263-Cookie beim UTF-8-Fallback nur über physische LF-Zeilen bestimmen, damit Unicode-Zeilentrenner die echte zweite Cookiezeile nicht verdecken | VERIFIED_FIXED; implementiert; Latin-1/NEL-Regressionsbytes kompilieren mit aktualisiertem UTF-8-Cookie; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-050 | Aktive Architektur-, Design-, Lizenz- und Testsuppressionsverträge auf Windows plus exakt CPython 3.14.7, PEP-263-Quelltext und UTF-8-Metadaten sowie GitHub Release als Publikationskanal vereinheitlichen | VERIFIED_FIXED; implementiert; aktive Vertragsquellen und Kommentare korrigiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-051 | Native Releaseasset-Provenienz auf die drei Manifesttools begrenzen und Zizmor getrennt als PyPI-/`uv.lock`-Abhängigkeit mit Sdist- und Plattform-Wheel-Hashes ausweisen | VERIFIED_FIXED; implementiert; Phantom-ZIP/-API-Claim entfernt; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-052 | Exakten Sprint-39-Backlog anlegen und aktive Product-/Serena-/Sprint-Metadaten samt Governanceprüfung auf Scope, Branch, Reviewquellen, `NOT_EXECUTED` und Releasefolge synchronisieren | VERIFIED_FIXED; implementiert; Existenz und Pflichtinhalt maschinenlesbar gebunden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-053 | Lokalen Releasewrapper um gelocktes Zizmor 1.30.0 mit Offline-`regular`-/`pedantic`-Personas erweitern, damit billing-blockierte CI keine Security-Lücke erzeugt | VERIFIED_FIXED; implementiert; Pfad/Version/Personas/minimale Umgebung und Orchestrierung regressionsgebunden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-054 | Report-Provenienz als exakt markierte Artefakt-zu-Digest-Abbildung statt freie Hashteilstrings binden | VERIFIED_FIXED; implementiert; sechs eindeutige Zeilen werden direkt gegen Native-Manifest und `uv.lock` geprüft; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-055 | Aktive Scope-/Release-/Sprint-/Strukturdokumente semantisch statt tokenbasiert prüfen und verbliebene Linux-, Build-, Velocity-, Regexparser- und Markupdrift entfernen | VERIFIED_FIXED; implementiert; strukturierte Positiv-/Negativverträge vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-056 | Gesamten CPython-Derivatabschnitt einschließlich Herkunft, Anpassungsbeschreibung, Copyright und Anwendbarkeit zusätzlich zum PSF-Text exakt hashen | VERIFIED_FIXED; implementiert; positionsgebundener Abschnittshash vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-057 | Gemessenes Coverage-Laufzeitrisiko des 60-Minuten-Testjobs durch ein gepinntes 120-Minuten-Limit mit belastbarer Setup-/Runnerreserve schließen | VERIFIED_FIXED; implementiert; Messung 2.274/43, 85 %, 51:37 und Workflowregression dokumentiert; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-058 | Sprintbacklog phasenabhängig an offene Candidate- beziehungsweise abgeschlossene Released-Gates binden und genau den aktiven Backlog im direkten docs-only Housekeeping verpflichten | VERIFIED_FIXED; implementiert; ASCII-Sprintpfad sowie Candidate-/Released-/Historien-Negativverträge vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-059 | Staging aus dem Eltern- und Spawn-Worker-Importpfad entfernen; ausführbares Staging ausschließlich den explizit isolierten pytest-Kindern geben | VERIFIED_FIXED; implementiert; Eltern-`sys.path`-/Spawn-Preparation-Regression und realer Vier-Worker-Arbeitsbaum-Recheck grün: 91/91, 90/1, einziger Survivor Windows-äquivalent, 0 Problem-Buckets, 98,9 %, kein Staging-`__pycache__`; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-060 | Zizmor-Konfiguration und Inline-Ignores in beiden Offline-Personas mechanisch deaktivieren | VERIFIED_FIXED; implementiert; Native Wrapper und direkte Build-Prüfungen verwenden `--no-config --no-ignores`, globaler Workflow-/Dokumentvertrag regressionsgebunden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-061 | Git for Windows aus dem systemweiten HKLM-Installationsvertrag statt Caller-PATH beziehen und seine Ausgabe strikt als einzeilige Windows-Version prüfen | VERIFIED_FIXED; implementiert; Registry-/Pfad-/Version-/Fake-PATH-Gegenproben vorhanden; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-062 | Jeden urllib-Redirect-Hop vor dem Folgen gegen HTTPS-, Host- und Credential-Allowlist prüfen | VERIFIED_FIXED; implementiert; erlaubte Zweihop- sowie Host-/HTTP-/Userinfo-Negativtests grün; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-063 | Sämtliche Release-Gate-Caches aus dem Checkout fernhalten: externe uv-Projektumgebung, externes `HYPOTHESIS_STORAGE_DIRECTORY`, Artefakt-Smoke-Venvs unter `RUNNER_TEMP`, In-Suite-Import-Linter ohne Cache, Ruff/Import-Linter/pytest cachelos, mypy nichtinkrementell mit Windows-Cacheziel `nul` sowie Workflow-, Quell- und Hidden-Ignore-Vertrag | VERIFIED_FIXED; implementiert; Hypothesis 6.151.10 schreibt bestätigt `.hypothesis`-Cachebytes, aber keine eigene `.gitignore`; exakte Befehle und `lint_imports(no_cache=True)` sind strukturell gebunden, Hidden-Ignore-Inventarisierung ist `lstat`-/Reparse-sicher und behandelt Windows-`.gitignore`-Pfade case-insensitiv; der zuvor bei 64 Prozent reproduzierte `.import_linter_cache/.gitignore`-Fehler und benachbarte Kontaminationen werden gezielt und in der vollständigen Suite erneut geprüft; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-064 | Semgrep aus der exakt deklarierten aktiven absoluten `UV_PROJECT_ENVIRONMENT` außerhalb des Release-Checkouts beziehen statt `<Repository>/.venv` vorauszusetzen | VERIFIED_FIXED; implementiert; Wrapper validiert externe Prefix-/pyvenv-/Scripts-/Executable-Identität, akzeptiert aufgelöste Windows-Pfadalias-Identität und lehnt fehlende, relative, abweichende sowie den Checkout enthaltende oder darin enthaltene Umgebungen ab; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-065 | Die nach CX221-063 verschobene, unverändert legitime Architekturtest-Importstelle erneut vollständig an Span, Zeilen- und normalisierten Dateihash binden | VERIFIED_FIXED; implementiert; kanonisches Gate brach mit exaktem Missing-/Extra-Paar fail-closed ab, unabhängige Adjudikation bestätigte die nur verschobene literale Eigenmodulliste, source-grounded Contracttest ergänzt; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-066 | Reale CLI-Unit-Surfaces aus dem Repository-CWD isolieren, ohne die sicherheitsbedingt persistente Produkt-Guard-Inode zu löschen | VERIFIED_FIXED; implementiert; gemeinsame opt-in-`tmp_path`-Workspace-Fixture für neun Module, vorhandene testlokale CWDs bleiben maßgeblich, echte CLI-Gegenprobe erwartet den Guard nur extern, statischer Modulvertrag und fokussierter Cluster 235/235 bei unverändert null Root-Lock-Artefakten; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-067 | Jede verbliebene `.py.meta`-Userfixture anhand ihrer eigenen Expected-/Mirror-Ownership erhalten, auch nach alleiniger Löschung der Python-Begleitdatei | VERIFIED_FIXED; implementiert; vier negative Übergangsregressionen einschließlich Windows-Großschreibung sowie `also_copy`/`extra_paths`; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-068 | Leere reservierte Helper-Namespaces vor Materialisierung ablehnen, reguläre extensionlose Datendateien weiter erlauben | VERIFIED_FIXED; implementiert; 15 Namespace-Gegenproben und neun positive Datendatei-Kontrollen; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-069 | Physische Python-Zeilenenden durch Generation, Show und Apply erhalten; nicht treues Altstaging vor Writes ablehnen und Generationspolicy erneuern | VERIFIED_FIXED; implementiert; 20 neue Generation-/Patch-/Apply-/Backup-/Legacy-/Pragmafälle, fokussierter Verbund 319/3; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |
| CX221-070 | Geordnete interne Argfiles auch für sämtliche Elternphasen verwenden und deren Lifetime an externe Runtime-Kontexte binden; alle argparse-Zeilentrenner gemeinsam ablehnen | VERIFIED_FIXED; implementiert; 36 neue Transporttests mit 601 realen Targets sowie 34 weitere Parser-/Eltern-/Workerfälle mit echtem Unicode-Parserroundtrip; Implementierungsgates verifiziert; Candidate-/Integrationswiederholung folgt |

CX221-044 bindet in `[dependency-groups].release`
`check-wheel-contents==0.6.3`, `pyflakes==3.4.0`, `twine==7.0.0` und
`zizmor==1.30.0`; der erneuerte `uv.lock` umfasst 133 Pakete einschließlich
`packaging==26.3`. Der Supply-Chain-Vertrag prüft Root-Metadaten, Registry und
die exakten Sdist-/Windows-Wheel-Namen samt SHA-256. Der Build synchronisiert
die Gruppe und führt Zizmor regular und pedantic, Twine `--strict` sowie
`check-wheel-contents` aus. Frühere fokussierte Arbeitsbaumläufe bestanden den
Versionsassert, actionlint 1.7.12 mit ShellCheck 0.11.0 und Pyflakes 3.4.0,
beide Zizmor-Personas sowie Gitleaks 8.30.1 ohne Leak. Der kanonische Native-
Lauf ist im aktuellen Implementierungsnachweis enthalten; die Wiederholungen
auf dem neuen Candidate- und Integrationscommit bleiben getrennte Gates.

<!-- RELEASE_TOOL_PROVENANCE_START -->
| Autorität | Tool/Artefakt | SHA-256 |
|---|---|---|
| Native GitHub asset | actionlint 1.7.12 ZIP | `6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9` |
| Native GitHub asset | ShellCheck 0.11.0 ZIP | `8a4e35ab0b331c85d73567b12f2a444df187f483e5079ceffa6bda1faa2e740e` |
| Native GitHub asset | Gitleaks 8.30.1 Windows x64 ZIP | `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e` |
| PyPI / `uv.lock` | zizmor 1.30.0 sdist | `9a17ac3bb043afbbd9d3c8b6f309fa5b319c6a32e3259fbaf050f6fcd3d0a9cd` |
| PyPI / `uv.lock` | zizmor 1.30.0 Windows amd64 wheel | `ca321b5b1cb85d08ac0c3c86275bfd5a6b5564c176437e3b41e10bd1e4463296` |
| PyPI / `uv.lock` | zizmor 1.30.0 manylinux build-host wheel | `9c08a7c34b33ed6f9a3a3d28fcf8c64e3e078c53c51bc9ce05c32ec3ba7feae9` |
<!-- RELEASE_TOOL_PROVENANCE_END -->

Das Native-Manifest umfasst bewusst nur die ersten drei GitHub-Assets. Zizmor
kommt aus `uv.lock`; das manylinux-Wheel belegt nur den Buildhost und keine
unterstützte Linux-Runtime.
Der damalige Windows-/CPython-3.14.7-Arbeitsbaum bestand vor dem
Implementierungscommit die vollständige strikte Suite mit 2.303 passed,
43 skipped und 0 failed in 40:34 Minuten sowie auf dem sauberen Commit
`4daed987742d24b420285fec46fc91bc2e1189a4` die Coverage-Suite mit denselben
Testzahlen, 9.727 Statements, 1.450 Missing und 85 Prozent in 43:51 Minuten.
Ruff Check, Format (172 Dateien), mypy (39 Dateien), Import-Linter, Lockprüfung
und der vollständige Dependency-Export/Pip-Audit waren auf diesem damaligen
Commit grün; Pip-Audit meldete 0 bekannte Schwachstellen. Das kanonische
Semgrep-Gate bestand mit 225
Manifestdateien, 224 Targets, 346 Regeln, exakt 22 allowgelisteten Treffern und
jeweils 0 unerwarteten Findings, Errors, übersprungenen Regeln und Fixpoint-
Timeouts. Derselbe saubere Implementierungscommit bestand in einer frisch
gelockten CPython-3.14.7-Releaseumgebung zusätzlich das Native-Gate aus
actionlint, ShellCheck, Pyflakes, Zizmor regular/pedantic und Gitleaks
Worktree/History. Der erste commit-genaue Kandidatenlauf deckte danach bei 64
Prozent CX221-063 auf und war deshalb ausdrücklich kein PASS. Die korrigierte
Suite auf Commit `277821da25fbf791cea2ac3c30495984808c74e6` bestand mit
2.313/43, 85 Prozent und sauberer Nachlaufprovenienz; das anschließend zweimal
vor dem Scan abgebrochene Semgrep-Gate deckte CX221-064 auf; der erste danach
erreichte Scan deckte mit einem exakten Missing-/Extra-Paar die stale
Allowlist-Signatur CX221-065 auf. Die danach inhaltlich grüne vollständige
Suite deckte im Nachlauf den ignorierten Checkout-Guard CX221-066 auf. Nach
dessen Korrektur waren sämtliche Candidate-Gates und anschließend die
integrierten Gates erneut erforderlich; diese Aussage beschreibt den damaligen Stand.

Der unabhängige Reaudit vom 2026-09-07/08 bestätigte danach CX221-067 bis
CX221-070. Der noch laufende Vollsuiteversuch auf `04089557` wurde deshalb
kontrolliert beendet und ist ABORTED, kein PASS. Die vier Korrekturen
besitzen getrennte Rot-/Grünbelege: 19/9 vor den Stagingfixes, 15/5 vor
dem Sourcefidelity-Fix und 24/12 vor dem Argfile-Fix; danach bestanden
sämtliche 84 ursprünglichen neuen Fälle in den jeweiligen fokussierten Verbünden.
Der Crossreview ergänzte 34 Parser-/Eltern-/Workerfälle zur Ablehnung aller
argparse-Zeilentrenner und zum bytegetreuen Unicode-Roundtrip. Der abschließende
Root-Verbund bestand mit 494 passed/3 skipped in 35,59 s; Ruff check/format
aller 13 geänderten Pythondateien blieb ohne Befund. Der damals neue Gesamtbaum
benötigte sämtliche commit-genauen Kandidatengates; aktuelle Belege folgen in Abschnitt 13.4.

Die vollständige Implementierungssuite auf `19f8d3a` endete anschließend mit
4 failed/2.430 passed/43 skipped in 2.109,49 s (9.752 Statements, 1.453 Missing,
85 %). Die vier Parameterfälle eines bestehenden Oberflächentests erwarteten
noch direkte Targets in argv; ihre Anpassung prüft die mit CX221-070 eingeführte
Argfile an der Prozessgrenze samt Inhalt und Cleanup. Dieser FAIL bleibt
erhalten; er autorisiert keine Candidate-Attestierung. Der kanonische separate
Dogfood auf demselben Commit bestand vollständig mit 91/91 autorisierten
Ergebnissen, 90 Kills, einem Windows-äquivalenten Survivor und keinen
Problem-Buckets. Eine falsche Standardannahme im externen Nachprüfer wurde
quellenbelegt korrigiert und derselbe abgeschlossene Lauf erneut ausgewertet.
Die angepasste Oberflächenregression behält sämtliche bisherigen Selektions-,
Config- und Rootprüfungen bei. Ihr Verbund bestand mit 158 Tests in 30,26 s;
der unabhängige Root-Verbund einschließlich Supply Chain mit 61 Tests in 3,39 s.
Ruff und Format blieben ohne Befund. Produktbytes wurden dabei nicht geändert;
der nachfolgende Commit benötigte seine vollständige Revalidierung; deren abgeschlossener Nachweis steht in Abschnitt 13.4.

### 13.4 Aktueller Abschlussstand und exakte Sequenz

Die vollständigen lokalen Implementierungsgates einschließlich strikter Coverage-Suite,
Quality, Dependencies, kanonischem Semgrep-/Native-Gate, Hygiene und Dogfood sind
auf Commit `6e12964f9a0460e7faf1b77d9e70a8f8c9f53a3b` / Tree `bfc7b834421630f5e0d51eef590b8a6db449943c` abgeschlossen.
27 MW221-Zielsystemfixes und alle 70 CX221-Befunde (2 P0, 63 P1, 5 P2) sind
`VERIFIED_FIXED`; MW221-003 bleibt `OPEN_PROCESS`. Die lokale Candidate-Attestierung
ist für Review und die folgende commit-genaue Validierung vorbereitet. Die durch
diese Dokumentbytes neu entstehende Candidate-Identität wird erst nach dem Commit
extern bestimmt. Sämtliche vertraglichen Candidate-Gates, einschließlich der
vollständigen Suite und Dogfood, sind auf diesem neuen Commit vor Push zu wiederholen.
Integration, integrierte Gates, reproduzierbare Artefakte, Installed-Smokes,
annotiertes Tag und GitHub-Release bleiben bis zu ihren tatsächlichen Nachweisen offen.

1. Diese Attestierung ändert ausschließlich State, Root-Memory, zwei LIVE-Serena-Memories,
   Analyse und Roadmap; die neun Sprint-39-Checkboxen bleiben unverändert offen.
2. Attestierung committen; Candidate C und Tree(C) extern festhalten; alle
   vertraglichen Candidate-Gates einschließlich Vollsuite und Dogfood auf C wiederholen.
3. Remotezustand live lesen, C normal pushen und nach unabhängigem Review ausschließlich
   mit `--merge --match-head-commit C` integrieren. Merge M hat exakt zwei Parents;
   Parent 1 ist das vorherige main, Parent 2 ist C, Tree(M) = Tree(C).
4. Den Fixref bis zum Abschluss der integrierten Gates unverändert auf C halten.
   Alle integrierten Gates auf M wiederholen, danach Doppelbuild, Artefaktprüfung
   und getrennte frische Wheel-/Sdist-Smokes durchführen.
5. Erst danach das annotierte Tag auf M und den GitHub-Release mit allen fünf Assets
   veröffentlichen; live zurücklesen, Assets vergleichen und Download-/Installsmoke ausführen.
6. Erst nach Publikationsbestätigung Housekeeping als direkten docs-only Child von M
   vorbereiten: C/M-Provenienz binden, MW221-003 schließen und neun Sprintboxen abhaken.
   Nach dessen Commit Governance-/Supply-Chain-Tests auf sauberem Checkout durchführen.

| Beleg | Commit / Tree | Tatsächliches Ergebnis |
|---|---|---|
| implementation | `6e12964f9a0460e7faf1b77d9e70a8f8c9f53a3b` / `bfc7b834421630f5e0d51eef590b8a6db449943c` | Windows CPython 3.14.7, uv 0.11.6; strikte Vollsuite 2434 passed/43 skipped/1988.55 s; Coverage 9752 Statements/1449 Missing/85 Prozent. Ruff check und Format 175 Dateien, mypy 39 Sourcefiles, Importvertrag 1/1, Lock 133 Pakete, headerloser vollstaendiger Export und pip-audit ohne bekannte Schwachstellen. pytest 8.2.2: 116 passed/2 skipped. Semgrep 1.175.0: 228 Manifestdateien/227 Targets/346 Regeln/22 erlaubte Findings, 0 unerwartete Findings/Scannerfehler/Skips/Timeouts. Canonical Native: actionlint, ShellCheck, Pyflakes, Zizmor regular/pedantic, Gitleaks Worktree/History bestanden. Dogfood 91/91, 90 killed/1 Windows-aequivalenter Survivor, 0 Problem-Buckets, volle Basis, evidence_invalidated=0, 91/91 Run-/History-Fingerprints autorisiert. Checkout sauber und zugehoerige Prozesse beendet. Unabhaengiger Diff-/Claim-Reaudit samt Root-Gegenpruefung abgeschlossen; GitHub-CI NOT_EXECUTED. Die 43 Skips: 28 fehlende Symlinkprivilegien (WinError 1314), 13 Nichtzielplattformen, 1 installierte psutil-Abhaengigkeit, 1 pytest-Major-Fall; pytest 8.2.2 ist separat geprueft. |

Externe Rohbelege (SHA-256; die Zusammenfassungen stammen aus diesen abgeschlossenen Läufen):

- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2211-release-20260907\implementation-complete-6e12964.json` — `4097da0acfbc6c71bc7d5a4e1a535e9e5d1cd8f05836a6427c9256219c2a1a9f`

GitHub-CI: `NOT_EXECUTED` wegen des bekannten, vom Product Owner akzeptierten
Billing-Problems; weder PASS noch FAIL.
