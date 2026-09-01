# Adversariales 360-Grad-Review: mutmut-win 2.20.0 → 2.21.0

**Review-Stand:** 2026-09-01
**Arbeitsbaum:** `<repository root>`
**Git-Basis:** PR #134 wurde als `55d25dfff2225ffb3e4a2b56ead4a3c190d054cf` mit Tree `761e264a91a52bda4c284f3f36fe53954d7fff2b` in `main` integriert; aktuelle Reparatur auf `fix/v2.21.0-release-blockers`
**Status:** 115 Befunde (30 P0, 56 P1, 29 P2; MW220-001 bis -115) bestätigt. MW220-001 bis -111 waren auf dem integrierten Kandidatentree lokal belegt; die tatsächlich angelaufene GitHub-CI deckte anschließend MW220-112 bis -114 als neue Releaseblocker auf. Alle drei sind auf `fix/v2.21.0-release-blockers` implementiert und zusammen mit der vollständigen lokalen Cross-Platform-Matrix verifiziert. Der abschließende Report-Vertragsaudit fand und schloss zusätzlich MW220-115. Alle vor diesen Fixes erzeugten integrierten Artefakte und Finalclaims sind ungültig; Follow-up-Integration und integrierter Rebuild stehen noch aus. Ein vorzeitig erzeugter Tag `v2.21.0` wurde vor jeder Releasepublikation entfernt; Tag und GitHub-Release sind derzeit nicht vorhanden.
**Leitprinzip:** Ein Mutant darf nur bei autoritativem Mapping als `no tests` gelten. Ein technisch vollständig ausgeführter Plan kann auch bei nicht vollständig inventarisierbarer Umgebung `completed` sein; Wiederverwendung und CI-/Release-Autorität benötigen jedoch eine nachweislich vollständige Test-, Source-, Konfigurations-, Abhängigkeits-, Environment-, Import- und Prozessbasis.

## 1. Historisches Gesamturteil vor der Korrektur

Die Architektur war grundsätzlich tragfähig und die bestehende Suite groß. Der zu Beginn des Reviews untersuchte Stand war dennoch **nicht releasefähig**: Mehrere unabhängige Pfade konnten betroffene Mutanten fälschlich als no tests behandeln, alte Verdicts unter einer neuen Basis wiederverwenden oder eine unvollständige Mutantengeneration als gültig cachen. Hinzu kamen bestätigte Trampolin-Semantikfehler, offene Pfadgrenzen, nicht vollständig begrenzte Prozesspfade sowie ein Sdist mit internen Arbeitsartefakten.

Dieses Urteil beschreibt ausschließlich den ursprünglichen Ausgangssnapshot. Die zweite Review-Welle steht in Abschnitt 14, ihr Closure-Stand in Abschnitt 15, die dritte Review-Welle einschließlich des finalen Diff-/Claim- und pytest-/Execution-Basis-Reaudits sowie der Remote-CI-Reaudit in Abschnitt 16, deren Umsetzungsstand in Abschnitt 17 und die noch ausstehenden Veröffentlichungs- und Artefaktgates des reparierten Releasekandidaten in Abschnitt 18.

## 2. Umfang und Methode

Das Review umfasste Quell-, Test-, Build- und Dokumentationsbaum und war ausdrücklich nicht auf die vorherige Fassung dieses Dokuments beschränkt:

- drei unabhängige Review-Wellen der Mutations-/Trampolinlogik, Prozess-/Persistenzpfade und CLI-/Build-/Architekturoberfläche sowie ein finaler Multi-Agenten-Diff-/Claim-Reaudit, zwei unabhängige Red-Team-Reaudits der Execution-/pytest-Grenzen und ein adversarial ausgewerteter Finalgate-/Dogfooding-Lauf;
- Code- und Vertragstracing über CLI, Orchestrator, Staging, Stats, Worker, SQLite und Ergebnisdarstellung;
- temporäre Reproduktionen für Cacheinvalidierung, Pfadgrenzen, pytest-Selektion, Prozess-Hits, Trampolinsemantik und Fault Injection;
- historische vollständige Ausgangsgates und gezielte Regressionen der Fixwellen; die vollständigen Test-, Coverage-, Lint-, Typ-, Build-, Dependency-, Semgrep- und Dogfooding-Gates des finalen Baums bleiben Abschnitt 18 vorbehalten; die tatsächlich ausgeführte Remote-CI und ihre drei Releaseblocker werden dort ausdrücklich als fehlender PASS dokumentiert;
- Abgleich mit aktueller offizieller Ruff-, Hatch- und Upstream-mutmut-Dokumentation.

Die erste Review- und Fixwelle lief in einem lokalen ZIP-Snapshot ohne `.git`. Seit der zweiten Welle ist ausschließlich der frische Clone unter `<repository root>` autoritativ und bearbeitet. Der erste Korrekturkandidat auf `fix/360-review-hardening` wurde durch PR #134 als Mergecommit `55d25dfff2225ffb3e4a2b56ead4a3c190d054cf` mit unverändertem Tree `761e264a91a52bda4c284f3f36fe53954d7fff2b` in `main` integriert. Nach den CI-Funden wird ausschließlich auf `fix/v2.21.0-release-blockers` weitergearbeitet. Die Migration aus dem lokalen Legacy-ZIP-Baum wurde byte- und inventarbasiert bestätigt; dort verblieben keine exklusiven relevanten Dateien. Der Legacy-Baum ist keine zweite Source of Truth.

PR #134 ist integriert; ein reparierter Follow-up-PR, Tag und GitHub-Release stehen noch aus. Der Nutzer hat `v2.21.0` ausdrücklich festgelegt. Projektmetadaten, Lock, Installationshinweise und installierte CLI melden konsistent `2.21.0`. Ein vorzeitig erzeugter gleichnamiger Tag wurde nach den CI-Funden wieder entfernt, bevor ein GitHub-Release entstand. Der endgültige annotierte Tag und das Release dürfen erst auf dem reparierten, lokal mit vollständiger Cross-Platform-Evidenz verifizierten Follow-up-Commit erzeugt werden. Eine wegen Billing ausbleibende weitere Remote-CI bleibt eine akzeptierte Evidenzlücke und ist kein PASS.

## 3. Verifizierte Ausgangslage vor der Korrektur

| Gate | Ergebnis | Bewertung |
|---|---:|---|
| uv run pytest -q | 1418 bestanden, 6 übersprungen | grüne Baseline; deckt die reproduzierten False-Green-Pfade nicht ab |
| Coverage | 93 %, 4012 Statements / 275 Missing | hoch, aber relevante blinde Integrationspfade |
| Import Linter | 1 Vertrag gehalten, 0 gebrochen | Schichtenvertrag intakt |
| Ruff auf src/tests/benchmarks | bestanden | enger Gate grün |
| ruff check . | 69.041 Befunde, überwiegend .venv | exclude ersetzt Ruff-Defaults |
| Ruff Format | 2 Testdateien abweichend | Gate nicht grün |
| mypy src | 14 Fehler | kein grünes Typgate |
| uv build | Wheel und Sdist gebaut | Sdist-Inhalt fehlerhaft |
| pip-audit | 3 Advisories | click Runtime; msgpack und pip Dev-Transit |
| Semgrep auto | 1 Treffer in Testcode | begründeter exec-False-Positive; zwei Regel-Timeouts |

Der Testlauf erzeugte außerdem ResourceWarnings für nicht geschlossene SQLite-Verbindungen und Regex-FutureWarnings. Integrationstests installierten ein Fixture editable in die gemeinsame Projekt-.venv; danach zeigte simple-lib auf ein gelöschtes pytest-Tempverzeichnis.

## 4. Architektur und zentrale Invariante

Die fünf Import-Linter-Bänder sind:

1. CLI und Textual-Browser;
2. Orchestrierung, Runner, Stats und Apply/Diff;
3. Mutation, Staging, Persistenz, Coverage und Typfilter;
4. Prozessinfrastruktur;
5. Konfiguration, Modelle und gemeinsamer Kernel.

Der Laufpfad lautet:

    Konfiguration/Source
      -> mutants/-Staging
      -> optionale Coverage
      -> LibCST-Mutantengeneration
      -> optionaler Typechecker
      -> Clean-Test
      -> pytest-Stats/Test-Mapping
      -> Forced-fail-Gate
      -> Cache-/Verdict-Reuse
      -> Spawn-Worker + pytest-Prozess je Mutant
      -> .meta + Stats-JSON + SQLite
      -> results/show/apply/browse/CI-Export

Staging, Mapping, Reuse und Runabschluss sind correctness-kritisch: Sie entscheiden, ob ein Mutant überhaupt getestet wird und ob ein altes Ergebnis als aktuelle Wahrheit erscheint.

## 5. Befundregister

P0 bezeichnet belegte False-Green-, Source-Korruptions- oder grundlegende Semantikpfade. P1 ist hohe Robustheits-/Integritätsrelevanz. P2 betrifft Releasehygiene, Wartbarkeit oder engere Randfälle.

| ID | Prio | Befund | Evidenz |
|---|---|---|---|
| MW220-001 | P0 | Stats-Cache ignoriert Source, Callgraph, Helper, pytest-Konfiguration und max_stack_depth | Repro + stats.py:108-220 |
| MW220-002 | P0 | Fehlgeschlagener Stats-Refresh liefert im aktuellen Lauf wissentlich altes Mapping | Repro + stats.py:223-283 |
| MW220-003 | P0 | Hits aus Collection/Modulimport, Kindprozessen und xdist werden verloren/überschrieben | Repro + runner.py:504-559 |
| MW220-004 | P0 | collect_tests prüft den pytest-Returncode nicht | Repro + runner.py:203-247 |
| MW220-005 | P0 | pytest_add_cli_args_test_selection gilt nicht für reale Laufphasen | E2E-Repro + runner.py/worker.py |
| MW220-006 | P0 | Konfig-Fingerprint wird vor erfolgreicher Gesamtgeneration committed | Fault-Repro + file_setup.py:416-470 |
| MW220-007 | P0 | Dateifehler bei Generation werden nur gewarnt; Teiluniversum läuft weiter | orchestrator.py:651-681,754-799 |
| MW220-008 | P0 | Relative ..-Pfade verlassen Staging; Punkt-Pfad rekursiert in mutants | zwei Repros + config.py/file_setup.py |
| MW220-009 | P0 | Source-, Test-, Reuse- und Apply-Gültigkeit beruht auf mtime/Größe | Repros + drei Module |
| MW220-010 | P0 | Trampolinkopien evaluieren Defaults/Annotationen mehrfach und verlieren Docstring | Repro + mutation.py:478-621 |
| MW220-011 | P0 | Wrapper-Lokale kollidieren; Generatorart und Helperbindung können brechen | Repros + mutation.py:523-621 |
| MW220-012 | P0 | Regex-Codegen verwechselt Quelllexem und Stringwert; ein Kandidat verwirft ganze Datei | Repros + node_mutation.py:486-525 |
| MW220-013 | P0 | Pragma-Scanner deutet Marker in Stringliteralen als Kommentare | Repro + mutation.py:655-729 |
| MW220-014 | P1 | Coverage-Fast-Path kennt konkrete Covered Lines nicht | Repro + file_setup.py:710-747 |
| MW220-015 | P1 | do_not_mutate_patterns fehlt im Mutanten-Fingerprint | Repro + file_setup.py:440-456 |
| MW220-016 | P1 | Identische Mutanten und gleichnamige Definitionen kollidieren | Repros + mutation.py:223-253 |
| MW220-017 | P1 | Verdict-Reuse ignoriert Helper und indirekte Abhängigkeiten | Repro + orchestrator.py:1252-1350 |
| MW220-018 | P1 | Startup-Watchdog wird nach irgendeinem Task dauerhaft deaktiviert | Repro + executor.py:199-255 |
| MW220-019 | P1 | Typechecker-Timeout beendet keinen Prozessbaum | Repro + type_checking.py:47-88 |
| MW220-020 | P1 | Generation-Pool hat keinen Task-Timeout/Job-Tree und kann hängen | orchestrator.py:651-659 |
| MW220-021 | P1 | SQLite kennt keine Run-ID, Completion-Markierung oder Run-Lock | db.py:26-58 + Orchestrator |
| MW220-022 | P1 | Ctrl-C räumt Runner-Prozessbäume ohne Job Object nicht zuverlässig | runner.py:177-195,338-362 |
| MW220-023 | P1 | unknown-Recovery verletzt Summary-Invariante | Repro + orchestrator.py:427-457,1490-1499 |
| MW220-024 | P1 | Stats/Fingerprint nicht atomar; Logcapture unbegrenzt | Codepfade bestätigt |
| MW220-025 | P1 | Sdist liefert interne .claude/.serena/.sprint/Reviewdateien aus | Artefaktinventar |
| MW220-026 | P1 | Runtime-Abhängigkeit click besitzt Advisory | pip-audit |
| MW220-027 | P2 | Ruff scannt .venv durch ersetzte Default-Excludes | Repro + pyproject.toml |
| MW220-028 | P2 | E2E-Tests kontaminieren die gemeinsame virtuelle Umgebung | Repro + Integrationstests |
| MW220-029 | P2 | SQLite-Verbindungen/FutureWarnings sind unhygienisch | vollständiger Testlauf |
| MW220-030 | P2 | Wildcard-Mapping, lokales cast, deepcopy-Name und Hit-Stack haben Randfehler | Code + Minimalrepros |
| MW220-031 | P2 | Dokumentation, Versionen und Qualitätsgates sind gedriftet | Inventar |
| MW220-032 | P0 | --min-score nan umgeht das CI-Score-Gate | CLI-Repro + cli.py:112-118,425-444 |
| MW220-033 | P1 | terminale pytest-Argumente können reale Phasen mit Exit 0 neutralisieren | pytest-Repro + Runner |
| MW220-034 | P1 | leere/nicht passende Mutantenauswahl endet standardmäßig erfolgreich | Codepfad + Orchestrator/CLI |
| MW220-035 | P1 | Paket deklariert ISC, liefert aber keinen Lizenztext | Artefaktinventar |
| MW220-036 | P2 | setup.cfg-Parser verletzt Fehler-/Arg-Vertrag | drei Repros + config.py |
| MW220-037 | P2 | JSON-No-op, Scoreformel, Browserfallback und Meta-Validierung sind inkonsistent | Codepfade + Repros |
| MW220-038 | P2 | nicht-endliche Timeout-/Ratio-Werte werden akzeptiert | Config-Repro |
| MW220-039 | P1 | Automatisches Staging kann interne Tool-/Reviewbäume, Dotenv-Secrets, Run-Lock-Artefakte oder externe Symlink-/Junction-Inhalte spiegeln | Staging-Inventar + Pfad-/Junction-Repros |
| MW220-040 | P1 | BoundedOutputCapture kann in einem Stop/Read/Write-Race bereits geschriebene Diagnosedaten verlieren und die Forced-Fail-Attribution sporadisch verfälschen | deterministischer Race-Repro + 100/100 Markertest |
| MW220-041 | P2 | `time-estimates` bricht bei einem historisch beschädigten Mutantennamen mit `ValueError` ab | CLI-Repro + `test_cli.py` |
| MW220-042 | P0 | Bereits vorhandene Symlink-, Junction- oder Hardlink-Ziele im Staging können Mirror-/Generationswrites nach außen umleiten | Dateisystem-Repros + `test_file_setup.py` |
| MW220-043 | P1 | `KeyboardInterrupt` außerhalb der Worker-Eventschleife wird als fehlgeschlagen statt unterbrochen persistiert | Pipelinephasen-Repro + `test_run_surface_integration_220.py` |
| MW220-044 | P1 | Windows-Groß-/Kleinschreibung umgeht Staging-Skiplisten für Tool-, Cache- und Umgebungsverzeichnisse | Mixed-Case-Repro + `test_staging_hygiene.py` |
| MW220-045 | P0 | Umgeleitete oder hart verlinkte Default-Cache-, DB- und Sidecarpfade erlauben externe Reads/Writes oder Migrationen | Symlink-/Junction-/Hardlink-Repros + Run-Surface-Tests |
| MW220-046 | P1 | Erfolgreiche Subprozesse können Nachfahren hinterlassen; unter Windows besteht vor Job-Zuweisung ein Prozessstart-Race | reale Prozessbaumtests + Fault Injection |
| MW220-047 | P1 | Dokumentiertes selektives Mapping und Verdict-Reuse sind im sicheren Pfad unerreichbar; unvollständiges Mapping darf dennoch nie autoritativ werden | Mapping-/Reuse-Tracing + End-to-End-Reuse-Test |
| MW220-048 | P1 | `apply` oder ein neuer fehlgeschlagener Run können ein altes CI-Exportartefakt als scheinbar aktuelle Evidenz stehen lassen | Apply-/Run-Repros + Current-Snapshot-Tests |
| MW220-049 | P1 | `TaskStarted` wird vor erfolgreichem Prozesssetup emittiert und öffnet eine unbegrenzte Lücke im Startup-Watchdog | Worker-Popen-Fault + Watchdog-Repro |
| MW220-050 | P0 | Workspace-Locks allein koordinieren dieselbe physische SQLite-DB nicht über verschiedene Workspaces, absolute Pfade oder Hardlink-Aliase; ein Konkurrent kann einen fremden Live-Run invalidieren | Cross-Workspace-/Cross-Process-Lock-Repros |
| MW220-051 | P0 | Legacy-Zeilen oder ein moderner `completed`-Run ohne live gebundene Source-/Test-/Config-Basis können CI-Export autorisieren | CI-Export-Repros in `test_run_surface_integration_220.py` |
| MW220-052 | P0 | Der Run-Basisfingerprint kann ohne stabilen Eingangssnapshot beziehungsweise bei Mid-Run-Drift einen nicht mehr getesteten Workspace als `completed` markieren | Stable-Snapshot- und Mid-Run-Drift-Repros |
| MW220-053 | P1 | `--since-commit` filtert vor der effektiven `--tests-dir`-Konfiguration; ein benutzerdefinierter Testbaum kann dadurch Mutationstarget werden | CLI-Reihenfolgerepro |
| MW220-054 | P0 | Vorhersagbare Temp-/Backupnamen und nicht namespace-sichere Atomic-Writes können Symlink-/Hardlink-Referenten oder umgeleitete Eltern außerhalb des Workspaces verändern | Atomic-Writer-Fault-Injection |
| MW220-055 | P0 | Runner-generierte Sidecars und deren Stats-Publish können bereits vorhandenen Linkblättern beziehungsweise austauschbaren Tempblättern folgen | Sidecar-Link-/Substitutionsrepros |
| MW220-056 | P0 | Der Generations-Fast-Path bindet Metadaten nicht an die tatsächlich publizierten Python-Bytes; manipuliertes oder partiell publiziertes Staging kann wiederverwendet werden | Generated-Hash-/Legacy-Meta-Repros |
| MW220-057 | P1 | `_copy_with_retry()` schließt die private Kopie und öffnet sie für Metadaten erneut; ein Close→Reopen-Austausch kann die Atomic-Publish-Autorität unterlaufen | deterministischer Close/Substitute-Repro |
| MW220-058 | P1 | `browse` und nicht-TUI-Statusausgaben zeigen invalidierte `completed`-Evidenz nicht überall ausdrücklich als stale/nicht releasefähig | Browser-/`results`-Regressionen |
| MW220-059 | P0 | Benutzerdefinierte DB-Pfade und die Validate→`sqlite3.connect`-/Read-Return-Grenze sind gegen umgeleitete Eltern, Linkblätter, Identitäts-Swaps und Sidecars unzureichend geschützt; ein permanenter POSIX-Pfadtausch nach dem letzten Read konnte detached Evidenz zurückliefern | Hardlink-/Parent-/Connect-/Sidecar-/Post-Read-Swap-Repros |
| MW220-060 | P0 | Semantisch korrupte SQLite-/JSON-/Pydantic-Werte, unbekannte Verdicts, manipulierte Planzeilen und zurückgerollte neueste Run-Header können Tracebacks, ältere resurrected Evidenz oder false-green CI-Statistik erzeugen | Legacy-/Run-/Plan-Digest-/High-Water-/CLI-Korruptionsrepros |
| MW220-061 | P0 | `CREATE_SUSPENDED` plus nachträgliches Job-Assignment lässt unter Windows weiterhin ein Parent-Hard-Exit-Fenster zwischen CreateProcess und Assignment | Kernel-Beobachtungs- und Hard-Exit-Repro |
| MW220-062 | P1 | Windows-Workerbootstrap über eine begrenzte Pipe kann bei frühem `.pth`/`sitecustomize`-Stillstand bereits in `Process.start()` blockieren | Large-Payload-/wedged-sitecustomize-Repro |
| MW220-063 | P1 | Private Spawn-Interna laufen ohne auditierte Runtimegrenze; Resume-/Containmentfehler können als gewöhnlicher Mutantenfehler degradiert werden | Runtime-Range- und Resume-Fault-Injection |
| MW220-064 | P1 | POSIX-Generation ruft `setsid()` erst im Python-Target auf; Interpreterstart, `.pth` und `sitecustomize` laufen zuvor außerhalb der killbaren Session | WSL-Startup-/Supervisor-Repros |
| MW220-065 | P0 | Nach hartem POSIX-Worker-Tod besitzt der Executor keine dauerhafte pytest-PGID-Evidenz und kann die bereits laufende Testsitzung nicht gezielt reapen | realer WSL-SIGKILL-Repro |
| MW220-066 | P1 | Asynchrones `TaskStarted` ist keine belastbare Pre-Execution-Evidenz; pytest kann vor synchroner Parent-Publikation von Worker-ID und PGID laufen | EOF-sicheres Pre-exec-Gate und realer SIGKILL-Repro |
| MW220-067 | P1 | Ein Fehler in einer Executor- oder Typechecker-Cleanup-Stufe überspringt spätere Ressourcen oder maskiert den ursprünglichen Fehler | mehrfache Cleanup-Fault-Injection |
| MW220-068 | P1 | Erfolgreiches Generation-`DONE` verwendet den kurzen Abort-Join und kann einen korrekten großen Abschluss beim Teardown fälschlich als Fehler behandeln | deterministischer DONE-Teardown-Test |
| MW220-069 | P1 | Python-Metadaten behaupten einen unbeschränkten `>=3.12`-Runtimevertrag, obwohl private Containmentbackends nur für CPython 3.12–3.14 auditiert sind | statischer Metadatenvertrag; lokal implementiert; Remote-CI tatsächlich ausgeführt, Gesamtworkflow wegen MW220-112 bis -114 kein PASS |
| MW220-070 | P1 | Das GitHub-Repository besitzt keine belastbare Windows/Linux- und CPython-3.12–3.14-CI-Matrix mit getrennten Lock-, Quality-, Test- und Auditgates; globale Frozen-Konfiguration und ein einplattformiges Audit können dabei false-green werden | Workflow-/Lock-/Audit-Vertrag; Matrix ausgeführt und gerade dadurch MW220-112 bis -114 aufgedeckt; kein Gesamt-PASS |
| MW220-071 | P1 | GitHub-Release-Evidenz ist nicht durch SHA-gepinnte Actions sowie einen gelockten Build, Upload und installierte Wheel-/Sdist-Smokes abgesichert | Supply-Chain-/Artefaktvertrag; Remote-Build-/Smokepfade liefen, aber die Gesamtmatrix blockiert und alle Vorfix-Artefakte sind ungültig |
| MW220-072 | P1 | Die CPython-abgeleiteten Prozessbackends wurden ohne vollständigen PSF-2.0-Lizenztext, Copyright-Hinweis und erforderliche Änderungszusammenfassung ausgeliefert | Provenienz der privaten Spawnadapter plus Lizenz-/Metadateninventar; auf dem MW220-105-Snapshot artefaktbelegt, Rebuild des integrierten Releasecommits bleibt erforderlich |
| MW220-073 | P0 | Stats-, Verdict-, Run- und CI-Basis banden die effektive Ausführungsumgebung nicht vollständig; Paketbytes gleicher Version, Editables, `sys.path`/`.pth`, unregistrierte Module, Runtime oder geerbte Environment-Werte konnten bei scheinbar identischer Basis driften, während unvollständige Inventare ihren fehlenden Beweisstatus verloren | Dependency-/Environment-Repros sowie Reuse-/CI-Tracing; implementiert, unabhängig reauditiert und im lokalen Gesamtfinalgate grün |
| MW220-074 | P1 | Restliche eigene Publisher für Stats-/CI-JSON, generierte pytest-Plugins/Guards/Proofs/Argfiles und Run-Lock-Owner konnten einem ausgetauschten Parent folgen oder außerhalb der vorgesehenen Grenze schreiben | Parent-Swap-/Redirect-Repros und vollständiges Produktwriter-Inventar |
| MW220-075 | P1 | Ein POSIX-Sessionkind oder -prozessbaum konnte beim harten Tod des obersten Parents vor Installation des bisherigen EOF-Watchdogs weiterleben | reale Hard-Parent-Exit-Repros für Kind und Baum plus Busy-Parent-Stresstest |
| MW220-076 | P0 | Ein beliebiges `type_check_command` konnte trotz nicht inventarisierbarer Executable-, Script-, Plugin-, Responsefile- oder Konfigurationsbytes eine scheinbar vollständige Execution-Basis erzeugen und damit Stats-/Verdict-Reuse, `--min-score` und CI-Export autorisieren | generischer externer Checker und Legacy-Run-Repros; typisierte Unvollständigkeit, Release-Gates fail-closed |
| MW220-077 | P0 | Die pytest-Ausführungsgrenze war durch Options-/Target-Injektion, Root-/Config-/Target-Austausch, Worker-Fallbacks, externe `testpaths` und vorab geladene fremde `conftest.py`-Dateien umgehbar; zudem fehlten konsistente Version-, Identitäts- und Fatalitätsverträge | Schema-v2-, Reparse-/Identity-, Real-Subprocess- und pytest-8.2/9-Regressionsmatrix |
| MW220-078 | P1 | Historische technisch abgeschlossene Runs mit generischem Typechecker konnten in `results` und `browse` ohne Incompleteness-Warnung als release-ready erscheinen | Legacy-DB-Repros; zentrale Incompleteness-Klassifikation und explizite Anzeige |
| MW220-079 | P1 | Der reproduzierbare GitHub-Build exportierte `SOURCE_DATE_EPOCH` zusammen mit einer Command Substitution und konnte dadurch einen Fehler von `git log` maskieren | actionlint/ShellCheck SC2155; getrennte Zuweisung und Export, Workflow-Reaudit |
| MW220-080 | P2 | Ein unsichtbares Soft-Hyphen U+00AD blieb in einer Auditdatei verborgen und entzog sich gewöhnlicher Textsicht | byteweites Unicode-/Bidi-/Control-Inventar aller Git-owned Dateien |
| MW220-081 | P2 | Das feste 120-Sekunden-Budget des E2E-Subprozesshelpers war unter legitimer Coverage-Instrumentierung beziehungsweise starker Gate-Last zu knapp und erzeugte reproduzierbare False-Red-Timeouts | Gesamt- und Coverage-Läufe; weiterhin hart begrenztes 300-Sekunden-Budget |
| MW220-082 | P0 | Parallele Worker publizierten pro Mutant dieselbe pytest-Guarddatei; identische Atomic-Writer ersetzten gegenseitig ihre Inodes, Windows konnte zusätzlich `WinError 5` liefern, und diese Control-Plane-Fehler wurden als fachliche `suspicious`-Verdicts gespeichert, während der Run dennoch `completed` und basisautoritativ wurde | realer 90-Mutanten-Dogfood-Repro, deterministischer Fünf-Publisher-Race und Fatal-/Pending-Regressionen |
| MW220-083 | P1 | Der vorgeschriebene Dogfood-Pilot erreichte nur 71,1 %, weil 18 beobachtbare Coverage-Bridge-Mutanten echte Lücken in Pfad-, Freshness-, Exit-, Mapping- und Diagnoseverträgen überlebten | vollständige Diff-/DB-Forensik aller 21 Survivors; gezielte fachliche Assertions, vier Äquivalente verbleiben |
| MW220-084 | P2 | Eine Surface-Regression mockte nur den Legacy-Ergebnisleser und konnte deshalb eine reale lokale Dogfood-DB als Current-Run-Snapshot einbeziehen | Repro mit vorhandener `.mutmut-cache`; vollständige Snapshot-Grenze im Test isoliert |
| MW220-085 | P1 | Die CI-Jobs Quality, Tests und Audit führten den editierbaren Projektbuild mit `--no-build-isolation` auf einem frischen Runner aus, ohne dessen Backend- und PEP-660-Laufzeitabhängigkeiten vorher zu installieren; die vorhandene lokale `.venv` verdeckte zunächst fehlendes `hatchling` und danach fehlendes `editables` | echte externe Fresh-Runner-Umgebung; gelockter Buildgruppen-Bootstrap und nachfolgender vollständiger Sync erfolgreich |
| MW220-086 | P2 | 22 CLI-Tests mockten weiterhin nur den Legacy-Result-Reader; mit einer realen Current-Run-Dogfood-DB konnten sie ihre Fixtures umgehen, echte 90er-Resultate lesen, Export-Locks beziehungsweise Artefaktpfade berühren und je nach Assertion falsch rot oder zufällig grün werden | Full-Suite-Repro `Total 90` statt 3, unabhängiger Mock-Seam-Reaudit und 31-Test-Isolationscluster im Repo-CWD |
| MW220-087 | P2 | Sieben Windows-Junction-Tests dekodierten die lokalisierte `cmd.exe /c mklink`-Ausgabe implizit als CP1252 beziehungsweise UTF-8; deutsches OEM-Byte `0x81` aus „für“ ließ den internen Subprocess-Readerthread sterben, während der Test ohne strikte Warnungsbehandlung scheinbar bestand | Full-Suite-`PytestUnhandledThreadExceptionWarning`, deterministischer CP850-Repro und strikter 13-Test-Junction-Cluster |
| MW220-088 | P2 | Reine Orchestrator-Unit-Tests mockten Runner und Executor, führten aber pro `run()` mehrere vollständige Live-Fingerprints über Environment, Distributionen, Importpfade und das editable gemeinsame Repository aus; fachfremder gleichzeitiger Baumdrift konnte dadurch Count-/Timeout-/Persistenztests fail-closed abbrechen | Full-Suite-Repro nach 883 Pässen, isolierter Doppel-Fingerprint und hermetischer 59-Test-Orchestrator-/Driftcluster |
| MW220-089 | P1 | Staging- und Execution-Basis verwendeten auseinanderlaufende Verzeichnis-Skiplisten: `.import_linter_cache`, `.benchmarks`, `.idea` und `.vscode` gelangten nie in den Workerbaum, ihre Tool-/IDE-Schreibvorgänge konnten aber den Live-Basishash ändern und einen fachlich unveränderten Run abbrechen | Konstanten-Diff, externer Drift-Reaudit und parametrisierte Basis-/Staging-Regressionen über die vollständige gemeinsame Skipmenge |
| MW220-090 | P1 | Der dokumentierte Semgrep-Releasebefehl war ungepinnt und akzeptierte trotz Exit 0 intern als unvollständig klassifizierte Taint-Fixpoint-Timeouts; Split-Targets ließen unter Windows außerdem 31 von 49 ausgeschlossenen Fixturedateien unerwartet in den Scan gelangen | adversarial ausgewertetes Semgrep-JSON: 48 beziehungsweise 40 versteckte Fixpoint-Timeouts; externer Git-owned Root-Mirror mit `jobs=4`, exakter Targetmenge und 0 Timeouts |
| MW220-091 | P1 | Das Semgrep-Gate respektierte implizit Inline-`nosemgrep`-Kommentare; nackte oder nicht inventarisierte Suppressionen konnten neue Findings vollständig aus dem Gate entfernen | Vollscan mit `--disable-nosem`: exakt 20 zuvor unterdrückte Testcode-Findings; exakte Rule-/Path-/Span-/Lines-/Full-file-Digest-Adjudikation |
| MW220-092 | P1 | `--config auto` erbte lokalen Semgrep-Login und dynamische Registry-Regeln: der lokale OSS-Engine-Lauf lud 1.856 Pro- plus 1.074 Community-Regeln, während ein frischer unauthentifizierter GitHub-Runner nur Community-Regeln erhält; Rule-IDs banden die Regeldefinitionen selbst nicht | bereinigter Fresh-Runner-Doppeldump und Offline-Bundlescan: 1.074 Definitionen contentidentisch, 342 anwendbare Regeln; lokaler Loginbestand 1.340 Regeln und inkompatibler Digest |
| MW220-093 | P1 | Geerbte `GIT_INDEX_FILE`-/`GIT_CONFIG_*`-Werte konnten trotz korrektem Repositoryroot das dynamische Git-Inventar verkleinern und beliebige Solltargets aus dem Scan entfernen | hostile Environment-Repro; vollständiges case-insensitives `GIT_*`-Stripping für alle Git-/Semgrep-Kindprozesse |
| MW220-094 | P1 | Ein absolutes `.venv`-Semgrep konnte über geerbtes `PYTHONPATH`/`PYTHONHOME` fremde Pythonmodule importieren | Import-Redirect-Repro; `python -I`, vollständiges `PYTHON*`-Stripping, `PYTHONNOUSERSITE` und `PYTHONSAFEPATH` |
| MW220-095 | P1 | Die gelockte Security-Gruppe installierte Semgrep nur unter Python 3.13, obwohl der Projektvertrag CPython 3.12–3.14 umfasst | Cross-Version-Lock-Reaudit; unmarkiertes `semgrep==1.175.0`, universeller 115-Pakete-Lock |
| MW220-096 | P1 | Die erste Toolbindung akzeptierte ein beliebiges Semgrep unter `sys.prefix`, einschließlich eines globalen beziehungsweise nicht projektgelockten Interpreters | Environment-Boundary-Repro; aktive venv und exakt aufgelöstes `<repo>/.venv/Scripts|bin/semgrep` zwingend |
| MW220-097 | P2 | Der Sdist enthielt den Security-Wrapper, aber nicht dessen verpflichtende `.semgrepignore`-Policydatei | Artefaktinventar; beide Dateien werden unter kanonischem Sdistroot byteidentisch geprüft |
| MW220-098 | P2 | README und CI verwendeten unterschiedliche Semgrep-Umgebungsverträge: kombinierte Dev-Umgebung lokal, minimale Security-only-Umgebung remote | Dokument-/Workflow-Reaudit; identischer gelockter Security-only-Sync und isolierter Start statisch gebunden |
| MW220-099 | P2 | Allowlist-Signaturen banden nur die gematchten Zeilen; sicherheitsrelevanter Datenflusskontext derselben Datei konnte bei unverändertem Match driften | Kontextdrift-Repro; zusätzlicher LF-kanonischer Full-file-SHA jeder der zehn adjudizierten Testdateien |
| MW220-100 | P2 | Ein geerbtes `NETRC` konnte beim Community-Regeldump unabhängig von HOME unerwartet Registry-Credentials mitsenden | Requests-Netrc-Reaudit; case-insensitives Entfernen und Regressionstest |
| MW220-101 | P2 | POSIX `TMPDIR` blieb außerhalb der isolierten Control-Root-Grenze und konnte Semgrep-/Core-Temporärartefakte umleiten | Ubuntu-`tempfile`-Vertrag; `TMPDIR`, `TEMP` und `TMP` zeigen auf dasselbe geprüfte externe Tempverzeichnis |
| MW220-102 | P2 | Substring-basierte Workflowtests akzeptierten Shell-Zusätze oder andere `uvx`-Aufrufe trotz scheinbar korrektem Securitykommando | statischer Bypass-Repro; exakte geordnete `run:`-Liste und allgemeines Token-`uvx`-Verbot |
| MW220-103 | P2 | Sdist-Regressionen akzeptierten per `endswith` verschachtelte Ersatzpfade statt kanonischer Rootpfade | Archivpfad-Reaudit; genau ein Sdistroot und exakte Root-/`scripts`-Pfade |
| MW220-104 | P2 | Der statische Releasevertrag band die Security-Rootabhängigkeit und das Semgrep-Lockpaket nicht vollständig aneinander | Lock-Reaudit; unmarkierte Rootgruppe, Lock-Metadaten, Version, Registry und SHA-256-belegte Distributionsdateien geprüft |
| MW220-105 | P2 | Der Cross-Process-Run-Lock-Test veröffentlichte seine PID über eine bereits sichtbare, aber noch leere Ready-Datei und konnte das Releasegate sporadisch falsch rot machen | reproduzierter Empty-Read-Race; atomarer Tempfile-Replace-Handshake, 2/2 fokussierte Prozesse und 50/50 Stresswiederholungen grün |
| MW220-106 | P2 | Ohne `.gitattributes` machten `core.autocrlf` und gemischte Arbeitsbaumzeilenenden byteidentische Policy-/Sdist- und Cross-Platform-Buildbelege checkoutabhängig | vier real gemischte Kandidatendateien; LF-Policy, byteweise Normalisierung und statische Supply-Chain-Regression |
| MW220-107 | P2 | Der dokumentierte Dependency-Exporthash band einen absoluten `--output-file`-Pfad im uv-Header, obwohl der angegebene Befehl diesen hashrelevanten Parameter verschwieg; weitere Gatezeilen waren nach neueren Läufen stale | Rohbytevergleich von stdout/Dateiartefakt und identischem Dependency-Body; kanonische stdout-/Body-Digests und konsolidierte Snapshotbegriffe |
| MW220-108 | P1 | Maschinen-gelesene Sprint-/Hook- und ausdrücklich als LIVE markierte Projektzustände steuerten weiterhin auf v2.14–v2.20 und einen alten Featurebranch | `CLAUDE.md`-Hookvertrag, `.sprint/state.md`, `MEMORY.md`, Serena-Live-State; v2.21-Kandidatenheader und statische Versionsregression |
| MW220-109 | P2 | Zwei bewusst gepflegte, nicht als Archiv markierte Installationsanleitungen drifteten auseinander; die Dokumentationskopie installierte weiterhin v2.14.0, während die führende Konfiguration v2.21.0 verlangte | Git-Historie und Bytevergleich; beide Kopien LF-normalisiert byteidentisch, Versions-/Tag-/CLI-Regression |
| MW220-110 | P2 | Der eigenständige ausführbare Acceptance-Harness deklarierte v2.20.0, sein Lock und seine Provenienz banden aber weiterhin v2.14.0; sein eigener `uv lock --check` scheiterte | Standalone-Projekt-/Lock-Repro; v2.20.0-Verhaltensbaseline, Lockquelle/-version/-provenienz statisch gebunden und Offline-Lockcheck grün |
| MW220-111 | P1 | Ausführbare Claude-Hooks und aktive maschinen-gelesene Arbeitsanweisungen umgingen den fail-closed Release-Wrapper mit registryabhängigen Raw-/Changed-file-Scans und konnten danach trotzdem einen Security- beziehungsweise Gesamt-PASS melden | drei Executor-Hooks, Hooksettings, Sprint-/PostCompact-Governance, CLAUDE/Serena/DoD/Design; obligatorischer kanonischer Vollscope-Wrapper, fail-closed Voraussetzungen und statischer Frozen Contract |
| MW220-112 | P1 | Das lokal auf Windows ausgeführte mypy-Gate bewies die Linux-/POSIX-Plattformzweige nicht; `mypy --platform linux --no-incremental src/ scripts/` meldete 49 Fehler in sechs Prozessmodulen, obwohl der Kandidat als typgeprüft galt | GitHub-CI Quality-Job `99647140872`; Fix in sechs Prozessmodulen, native Windows- und Linux-Plattformanalyse jeweils 38 Dateien/0 Fehler, Prozesscluster 80/10 und vollständige Suite grün |
| MW220-113 | P1 | Zwei Same-byte-Identity-Regressionen setzten voraus, dass unmittelbares Unlink/Recreate auf jedem Dateisystem eine neue Geräte-/Inodeidentität erzeugt; Linux OverlayFS konnte die soeben freigegebene Identität samt Zeitwerten wiederverwenden, sodass der Test keinen beobachtbaren Austausch erzeugte und falsch rot wurde | Ubuntu-CI-Job `99647141304`: zwei DID-NOT-RAISE-Fälle; Hardlink-Anker hält die alte Identität bis nach dem Ersatz belegt, Linux 42/5 und Windows 45/2 fokussiert grün; kein Produktions-TOCTOU-Befund |
| MW220-114 | P1 | Der kanonische Semgrep-Wrapper war auf Windows nicht deterministisch releasefähig: derselbe Vertrag bestand lokal und auf Ubuntu, scheiterte im Windows-CI-Job jedoch fail-closed an nicht leeren `time.fixpoint_timeouts` | GitHub-CI Security-Job `99647141196`; Vollscan auf `--jobs 1` serialisiert, Vier-Shard-Bootstrap unverändert und Timeoutliste fatal; 70 Wrappertests sowie wiederholte reale Windows-Läufe grün |
| MW220-115 | P2 | Der Live-State-Vertrag prüfte nur den beliebigen Teilstring `114` und las Analyse/Roadmap nicht; dadurch konnten MW220-113 fehlen und widersprüchliche Fix-/Finalgate-Claims trotzdem grün bleiben | exakte Prüfung aller Follow-up-IDs und eigener Report-Vertrag für Anzahl, Prioritäten, Adjudikation, Semgrep-Evidenz und verbotene stale Claims |

## 6. P0-Befunde im Detail

### MW220-001 bis -004: Test-Mapping kann False Green erzeugen

MutmutStats invalidiert nur anhand gesammelter Node-IDs und mtime_ns:size der direkt benannten Testdateien (src/mutmut_win/stats.py:36-220). Source, neu verdrahtete Callgraphs, importierte Helper, mappingrelevante Konfiguration und max_stack_depth fehlen.

Reproduktionen:

- Nach einer Sourceänderung bei unveränderten Testdateien wurde run_stats kein einziges Mal aufgerufen; altes Mapping blieb autoritativ.
- Nach erkannter Teständerung und absichtlich fehlschlagendem Stats-Lauf wurde das alte Mapping für den aktuellen Lauf zurückgegeben. Es darf als Recovery-Datei erhalten bleiben, aber nicht verdict-bestimmend sein.
- Der generierte Plugin leert _state._stats am Anfang jedes pytest_runtest_protocol. Ein Modul mit VALUE = compute() bei Import hatte einen bestandenen Test und drei Mutanten, aber leeres Mapping.
- In einem Test gestartete Kindprozesse besitzen eigenen Hit-State. Im Repro mit Parent- und Child-Hit wurde nur parent.func persistiert.
- Bei pytest-xdist besitzen Controller und Worker eigene Dictionaries und schreiben denselben Pfad; partielle Daten können einander überschreiben.
- collect_tests verarbeitet stdout auch bei pytest-Exitcode 4. Im Repro wurde ein guter Cache wie eine autoritative Testlöschung bereinigt.

Sobald irgendein Mapping existiert, klassifiziert _split_no_test_tasks fehlende Funktionskeys als no tests (src/mutmut_win/orchestrator.py:1357-1387). Ein vollständig leeres Mapping fällt korrekt auf Vollsuite zurück; gefährlich ist das partielle oder alte, nichtleere Mapping.

### MW220-005: Testselektion ist nicht end-to-end

Nur collect_tests hängt pytest_add_cli_args_test_selection an. Clean, Stats, Coverage, Forced-fail und Worker verwenden nur pytest_add_cli_args (src/mutmut_win/runner.py:104-392; src/mutmut_win/process/worker.py:80-190).

Im kopierten Fixture tests/e2e_projects/config liefen beabsichtigt ausgeschlossene Fail-Tests trotzdem und brachen die Baseline ab. Damit beeinflussen ausgeschlossene Tests Testdauer, Coverage, Mapping, Gates und Verdicts.

### MW220-006/-007: Vorzeitiger Commit macht Teilgeneration gültig

config_fingerprint_matches schreibt den neuen Fingerprint sofort (src/mutmut_win/file_setup.py:416-470), bevor der Pool alle Dateien generiert hat. Dateifehler werden nur gewarnt (src/mutmut_win/orchestrator.py:651-681,754-799).

Repro: Profilwechsel basic zu all, danach simulierter Workerfehler. Der Folgelauf nahm den Fast Path und verwendete einen alten Basic-Mutanten statt sechs All-Mutanten. Erforderlich sind Two-Phase-Commit, atomare Datei-/Meta-Veröffentlichung und harter Phasenfehler.

### MW220-008/-009: Pfad- und Inhaltsgrenzen sind offen

Der Validator weist absolute, aber keine aufgelösten relativen Pfade außerhalb des Roots zurück (src/mutmut_win/config.py:305-330). Der Zielguard prüft nur exakte Source-/Zielgleichheit (src/mutmut_win/file_setup.py:663-708).

- paths_to_mutate=[\"../outside\"] wurde akzeptiert; das Ziel lag außerhalb mutants.
- paths_to_mutate=[\".\"] lieferte a.py und mutants/a.py als Eingaben.

Generation, Stats und Reuse vergleichen mtime/Größe (file_setup.py:716-747; stats.py:108-125; orchestrator.py:1252-1306). apply prüft nur Zeitrelationen (mutant_diff.py:371-432). Gleich große Inhalte mit zurückgesetztem Timestamp bleiben unsichtbar und apply kann eine ganze veraltete Funktion über echten Source schreiben. Content-Digests sind erforderlich; Altmetadaten ohne Digest sind ungültig.

### MW220-010/-011: Trampolin verändert Python-Semantik

function_trampoline_arrangement emittiert Wrapper, vollständige Originalfunktion und eine vollständige Definition je Mutant (src/mutmut_win/mutation.py:478-520). Defaults, Annotationen und Decorators werden beim Import wiederholt ausgewertet; der ersetzte Wrapperbody verliert den Docstring.

Ein Fixture mit vier Mutanten beobachtete 18 Definition-Time-Ereignisse statt drei; f.__doc__ war None. Nur die öffentliche Definition darf Defaults/Annotationen einmal auswerten. Interne Kopien müssen davon bereinigt werden.

Feste Wrapper-Lokale _mutmut_args/_mutmut_kwargs kollidieren mit legalen Parametern. Ein Keyword-only-Parameter wurde durch [] ersetzt; ein ungewöhnlich benannter Self-Parameter führte object.__getattribute__ gegen eine Liste aus. Ein späteres Modul-Rebinding von _mutmut_trampoline kann Dispatch ebenfalls brechen. Sync-/Async-Generatorwrapper verlieren inspect.isgeneratorfunction beziehungsweise inspect.isasyncgenfunction.

### MW220-012/-013: Regex und Pragmas sind lexikalisch unsicher

operator_regex schneidet SimpleString.value als Quelltext und setzt Mutationen ungeescaped zusammen (src/mutmut_win/node_mutation.py:486-525). Dadurch unterscheiden sich semantisch gleiche Raw-/Nonraw-Patterns; ein mutiertes Quote-Zeichen kann ungültigen Python-Code erzeugen. Der Safety-Net verwirft dann alle ansonsten gültigen Mutanten der Datei.

pragma_no_mutate_lines scannt Zeilentext (src/mutmut_win/mutation.py:655-729). Ein String mit \"# pragma: no mutate start\" unterdrückte alle Folgezeilen. Nur echte COMMENT-Tokens dürfen Direktiven bilden.

## 7. Weitere Integritäts- und Prozessbefunde

- do_not_mutate_patterns fehlt im Fingerprint; konkrete Covered Lines ebenfalls. Änderungen beider Basen nahmen im Repro den alten Fast Path.
- Ein einfaches Fixture erzeugte 12 Mutationen mit zwei identischen Paaren. Gleichnamige Top-Level-Definitionen erzeugen zudem dieselben Mutantennamen; Meta-Dicts kollabieren sie.
- _tests_fingerprint enthält direkte Node-IDs/Testdatei-Statdaten, aber keine Helper. Die Änderung von tests/helper.py ließ ihn unverändert.
- Der Executor benutzt ein globales any_task_pulled. Nach einem erfolgreichen Task kann ein anderer scheinbar lebender Bootstrap-Worker unbegrenzt hängen; im Repro war nach sieben Grace-Perioden aborted noch False.
- run_type_checker nutzt subprocess.run mit capture_output und timeout. Ein Grandchild hielt die Pipes offen; 0,2 s Timeout dauerte 2,17 s. Ein dauerhaftes Kind wäre unbounded.
- list(pool.map(...)) für Generation hat weder Taskdeadline noch Job-Object-Grenze. Ein lebender hängender Generationsworker blockiert unbegrenzt.
- Runner _run_phase räumt bei KeyboardInterrupt ohne erfolgreiches Job Object den Prozessbaum nicht mit dem psutil-Fallback ab.
- Die SQLite-Tabelle ist nur nach mutant_name keyed, ohne Run-ID, Generation oder Completion (src/mutmut_win/db.py:26-58). Vor Dispatch gibt es kein pending. Ein zweiter Lauf teilt Staging, Fingerprint, Stats, Meta, DB und kann Workerartefakte des ersten löschen.
- unknown-Recovery erhöht completed ohne Verdictbucket; im Ein-Task-Repro galt completed=1 und unchecked=0, obwohl kein Ergebnisbucket existierte.
- Stats-JSON/Fingerprint werden direkt überschrieben. .meta selbst wird bereits atomar ersetzt.
- stdout/stderr werden bis zum Timeout unbeschränkt in Dateien geschrieben; Tail-Limits begrenzen nur das Lesen. Print-Loops können Disk erschöpfen.
- Auf POSIX betrachtet der IL-Monitor für Status nur den Rootprozess, obwohl CPU/I/O baumweit summiert werden. Ein schlafender Parent mit spinnendem Kind kann dadurch unterbewertet werden; Windows ist hiervon nicht betroffen.

## 8. Release-, Build- und Testhygiene

Das Wheel war paketrein. Das Sdist enthielt .claude/settings.local.json, Hook-Skills, .serena/memories, .sprint samt Backups, CLAUDE.md, MEMORY.md, interne Dokumente und bug_reporting. Im Snapshot wurde darin kein Secret gefunden; die Auswahl bleibt ein Datenschutz-, Größen- und Reproduzierbarkeitsdefekt. Hatch benötigt ein explizites Allowlisting oder belastbare Excludes.

Ruff exclude ersetzt die Defaultausschlüsse und zieht .venv in ruff check . hinein. Additive Semantik erfordert extend-exclude.

pip-audit meldete:

- click 8.3.1, Fix 8.3.3, direkte Runtime-Abhängigkeit;
- msgpack 1.1.2, Fix 1.2.1, Dev-Transit;
- pip 26.1.2, Fix 26.2, Dev-Transit.

tests/integration/test_e2e.py:67-77,128-136 und test_e2e_pipeline_validation.py:49-63 installieren Fixtures in die laufende Projektumgebung. Mehrere Tests benutzen with sqlite3.connect, das committet, aber die Connection nicht schließt.

### MW220-039: Staging war keine belastbare Vertraulichkeitsgrenze

Der automatische Projektspiegel schloss nicht alle internen Arbeitsbäume und dynamischen Run-Lock-Namen aus. Dotenv-Dateien konnten unterhalb beliebiger Unterverzeichnisse gespiegelt werden; Datei-Symlinks und Windows-Junctions benötigten zusätzlich eine aufgelöste Containment-Prüfung. Damit konnten lokale Reviewdaten, Secrets oder Inhalte außerhalb des Projektroots in `mutants/` beziehungsweise durch eine destruktive `--force`-Operation berührt werden.

Der Fix zentralisiert die Ausschlüsse in `src/mutmut_win/file_setup.py`, behandelt Dotenv-Namen und kanonische `.mutmut-win-*.run.lock*`-Artefakte dynamisch, prüft Datei-Symlinks gegen den Projektroot und lässt explizites `also_copy` nur innerhalb der gültigen Grenze zu. `src/mutmut_win/cli.py` prüft die `--force`-Ziele vor Lock-Erzeugung; `src/mutmut_win/process/run_lock.py` kanonisiert Pfadaliase. Regressionen liegen in `tests/unit/test_file_setup.py`, `tests/unit/test_staging_hygiene.py` und `tests/unit/test_run_surface_integration_220.py`.

### MW220-040: Stop-Race konnte bereits geschriebene Diagnostik verlieren

`BoundedOutputCapture` konnte nach einem leeren nichtblockierenden Read den Stopzustand beobachten, obwohl das Kind unmittelbar dazwischen noch Daten geschrieben hatte. Der Reader beendete sich dann ohne weiteren Drain-Pass. Das begrenzte zwar weiterhin Speicher und Laufzeit, verlor aber den für die Forced-Fail-Attribution benötigten Marker und konnte dadurch sporadisch einen korrekten Mutationsnachweis als fremden Fehler behandeln. `src/mutmut_win/process/output_capture.py` garantiert nun einen Drain-Pass, der erst nach gesetztem Stop beginnt. `tests/unit/test_bounded_output_capture_220.py` pinnt die Interleaving-Reihenfolge deterministisch; der Markertest war 100/100 stabil, 147 angrenzende Tests blieben grün.

## 9. Weitere begrenzte Funktionsfehler

- test_mapping.py:109-139 matcht Mutantensuffix-Wildcards direkt gegen Funktionskeys ohne Suffix; pkg.x_f__mutmut_* liefert leer.
- node_mutation.py:334-343 mutiert auch einen Deklarationsnamen deepcopy; nach internem Umbenennen wird daraus ein No-op-Mutant.
- mutation.py:330-347 behandelt jede lokal definierte Funktion cast syntaktisch wie typing.cast und überspringt fälschlich Mutationen im ersten Argument.
- hit_recording.py:62-72 kann nach zu kurzem Stack ohne gefundenen pytest-/unittest-Frame dennoch einen Hit aufzeichnen.

## 10. CLI-, Gate- und Persistenzverträge

### MW220-032: NaN umgeht das CI-Gate

Click FloatRange akzeptiert NaN, weil Bereichsvergleiche mit NaN false sind (src/mutmut_win/cli.py:112-118). Das Gate scheitert nur bei gate_score < min_score (cli.py:425-444); dieser Vergleich ist für NaN ebenfalls false. Ein gemockter Run mit Score 0 und --min-score nan endete deshalb mit Exitcode 0. Alle Score-, Timeout- und Ratioeingaben benötigen eine explizite math.isfinite-Prüfung.

### MW220-033/-034: Steuerargumente und leere Auswahl

pytest_add_cli_args wird ungefiltert hinter interne Flags gehängt. --collect-only, --help oder --version können Clean-, Stats- oder Forced-fail-Phasen mit Exit 0 beenden, ohne Tests auszuführen. Im direkten Repro beendete --collect-only pytest erfolgreich nach reiner Collection. Ein zentraler phasenspezifischer Arg-Builder muss terminale/override-Optionen verbieten.

Keine generierten Tasks oder ein nicht passender Name/Glob ergeben ein Nullresultat; ohne --min-score endet die CLI mit Exit 0. Beim No-match-Pfad werden gefilterte Mutanten zuvor sogar als skipped persistiert (orchestrator.py:151-182). Explizite Selektion ohne Treffer muss vor Persistierung ein Usage-/Domainfehler sein; vollständige leere Projekte benötigen einen bewussten --allow-empty-Vertrag.

### MW220-035 bis -038: Paket-, Config- und Oberflächenkonsistenz

- pyproject und README deklarieren ISC, aber weder Repository, Wheel noch Sdist enthalten LICENSE/COPYING/NOTICE. Ein ISC-Lizenztext und ein Artefakttest sind erforderlich.
- setup.cfg wird mit Standardinterpolation gelesen. Ein legitimes Prozentzeichen erzeugt InterpolationSyntaxError, eine Datei ohne Section MissingSectionHeaderError mit fremdem Exit 1, und quoted pytest-Args werden nicht shellartig tokenisiert (config.py:427-440,518-539).
- --since-commit --output json gibt beim erfolgreichen No-op vor der JSON-Ausgabe leeres stdout zurück (cli.py:328-395).
- RunSummary schließt unchecked aus dem Score-Nenner aus; results und CI-Export tun dies nicht (models.py:297-302; cli.py:495-501; stats.py:408-471).
- Browserdetail kann beim DB-Fallback exit_code statt des persistierten status anzeigen und kapselt korrupte DBs nicht sauber (browser.py:255-270,357-362).
- .meta validiert exit_code_by_key-Werte nicht vollständig. Eine Liste wird übernommen und kann beim Statuslookup unhashbar werden (models.py:157-189; browser.py:177-185).
- positive Unendlichkeit passiert mehrere nur-gt=0-Validatoren und kann Timeout-/Loop-Grenzen neutralisieren (config.py:150-153,245-248).

## 11. Adjudikation der Vorgängeranalyse

Alle neun Hauptthesen wurden bestätigt. Ihre Schwere und Reichweite war teilweise unterschätzt:

| Frühere These | Dynamisches Urteil |
|---|---|
| Job Objects/Worker Best Effort | bestätigt; Mischfehler-Watchdog und mehrere Tree-Cleanup-Lücken ergänzt |
| Stats-Invalidierung unvollständig | bestätigt und wegen weiterer Import-/Subprozess-/Returncode-Pfade auf P0 erhöht |
| pytest-Selektion inkonsistent | durch vollständigen Fixture-Lauf bestätigt |
| Config-/Coverage-Fingerprint unvollständig | bestätigt; vorzeitiger Commit vergiftet zusätzlich Folgeläufe |
| Staging-Pfadgrenze offen | mit Punkt- und Parent-Repro bestätigt |
| DB ohne Run-Identität/Lock | bestätigt und auf alle gemeinsamen Stagingartefakte erweitert |
| Doppelte/kollidierende Mutanten | mit zwei Dublettenpaaren und Namenskollision bestätigt |
| mtime/Größe statt Content | bestätigt; zusätzlich Mirror, Reuse und apply betroffen |
| Dokumentationsdrift | bestätigt; Sdist- und Qualitätsgates ergänzt |

## 12. Bewusst verworfene oder eingegrenzte False Positives

- Der Semgrep-exec-Treffer führt in einem Unit-Test ausschließlich generierten Trampolincode aus; kein externer Injection-Pfad.
- Ein gewöhnlicher Worker-Tod nach TaskStarted hängt nicht automatisch: Der Executor synthetisiert suspicious; kompletter Pooltod setzt aborted. Der neue Hänger benötigt den gemischten wedged-worker-Fall.
- Ein vollständig leeres Stats-Mapping fällt auf Vollsuite zurück. False Greens entstehen bei altem oder partiellem, aber nichtleerem Mapping.
- Ungültiger Regex-Code wird nicht persistiert. Der Defekt ist der stille Verlust aller Dateimutanten.
- apply und .meta schreiben bereits atomar. Defekt sind Vorbedingung beziehungsweise fehlende Phasentransaktion.
- Exakte absolute Selbstmutation wird erkannt; offen bleiben Containment, Punkt und Parent.
- Mutierter Anwendungscode läuft bewusst mit Benutzerrechten. Ohne Sandboxversprechen ist dies eine Vertrauensgrenze, kein eigenständiger Bug.
- Upstream-mutmut nutzt teilweise dasselbe Vollfunktionskopie-Muster. Upstream-Parität widerlegt die reproduzierte Semantikänderung nicht.
- Keine Shell-/SQL-Injection und keine unsichere Objekt-Deserialisierung wurden gefunden; Subprozesse verwenden argv-Listen, SQL ist statisch/parametrisiert und externe Persistenz ist TOML/JSON.
- Wheel-Inhalte wie CSS und py.typed waren im damaligen Ausgangsinventar vorhanden; Import-Linter und Lockfile-Check waren für den jeweiligen Zwischenstand grün. Finale Artefakt- und Lockevidenz steht ausschließlich in Abschnitt 18.

## 13. Historisches Releaseurteil des Ausgangssnapshots

**NO-GO für den untersuchten Ausgangssnapshot.** P0-Befunde erlaubten falsche no-tests-Entscheidungen, falsche Wiederverwendung, unvollständig gecachte Generation, Sourceüberschreibung oder veränderte Python-Semantik. Ein grüner Testlauf allein hob das nicht auf.

Release-GO erfordert:

1. alle P0-Repros als Regressionstests;
2. bei unsicherem Mapping stets Vollsuite/unchecked statt no tests;
3. inhaltsbasierte, transaktional veröffentlichte Fingerprints;
4. invariant getestete Pfad- und Apply-Grenzen;
5. bounded Prozessbäume und sichtbare Abbrüche;
6. geprüfte Wheel-/Sdist-Allowlist und vollständige Drittanbieter-Lizenzpflichten;
7. frische Tests, Coverage, Ruff, Format, mypy, Import Linter, Build, Audit und Semgrep;
8. einen dokumentierten Dogfooding-Piloten auf dem finalen Baum;
9. standardmäßig einen adjudizierten GitHub-CI-Lauf auf dem publizierten finalen Commit.

Für diesen Korrekturstand hat der Nutzer den Remote-CI-Nachweis wegen eines bekannten GitHub-Billing-Problems ausdrücklich als Releasegate abgewählt und die daraus verbleibende Unsicherheit akzeptiert. PR #134 lief unerwartet dennoch weit genug, um MW220-112 bis -114 aufzudecken; diese Funde bleiben verbindliche Blocker. Eine spätere Billing-bedingt ausbleibende Remote-CI ist weiterhin eine dokumentierte Evidenzlücke und kein CI-PASS; die vollständige lokale Cross-Platform-Matrix bleibt verpflichtend.

Die Reihenfolge und Breaking-Entscheidungen stehen in [BUGFIXUNG_ROADMAP.md](BUGFIXUNG_ROADMAP.md).

## 14. Zweite adversariale Review-Welle

### MW220-041: Historische Namen dürfen Diagnosebefehle nicht abstürzen lassen

`time-estimates` leitete einen historisch beschädigten Cache-Namen ungefangen durch die strikte Mutantennamenzerlegung und endete mit `ValueError`. `src/mutmut_win/cli.py` degradiert einen solchen Datensatz nun konservativ auf eine Null-/`<no tests>`-Schätzung, ohne die übrigen Ergebnisse zu verlieren. `tests/unit/test_cli.py::TestTimeEstimatesCommand::test_malformed_cached_mutant_name_degrades_to_zero_estimate` pinnt den Vertrag.

### MW220-042/-044: Die Staging-Grenze muss Zielpfade und Windows-Semantik prüfen

Quellcontainment allein verhindert keine Umleitung, wenn ein bereits vorhandenes Ziel im Staging ein Datei-Symlink, Directory-Symlink, Junction oder Hardlink ist. Zusätzlich sind Skipnamen unter Windows case-insensitiv; `.VENV`, `.ClAuDe` oder `Node_Modules` dürfen nicht durch Groß-/Kleinschreibung wieder ins Staging gelangen. `src/mutmut_win/file_setup.py` validiert nun jeden lexikalischen Zielpfad komponentenweise, ersetzt Hardlinks vor dem Schreiben und verwendet durchgehend `casefold()` für Windows-relevante Skipentscheidungen. Die Grenztests stehen in `tests/unit/test_file_setup.py` und `tests/unit/test_staging_hygiene.py`.

### MW220-043/-048: Run- und CI-Zustand müssen bei jeder Pipelinegrenze ehrlich bleiben

Ein `KeyboardInterrupt` vor oder nach der Worker-Eventschleife wurde vom generischen Fehlerpfad als `failed` persistiert. Der Orchestrator markiert ihn nun in jeder Pipelinephase als `interrupted` und propagiert ihn weiter. Gleichzeitig wird `mutmut-cicd-stats.json` bereits beim Beginn jedes neuen Runs entfernt; erfolgreiches `apply` invalidiert den Latest-Run-Snapshot und entfernt ebenfalls das alte Exportartefakt. `tests/unit/test_run_surface_integration_220.py` deckt Interrupts vor/nach Planfinalisierung, fehlgeschlagene neue Runs und Apply-Invalidierung ab.

### MW220-045: Feste Workspace-Statepfade sind keine konfigurierbaren Vertrauensgrenzen

Default-Cache, SQLite-DB und Sidecars konnten über Symlinks, Junctions oder Hardlinks auf externe Ziele zeigen. Damit konnten schon Read-/Migrationspfade externe Dateien verändern. `src/mutmut_win/cli.py` und `src/mutmut_win/db.py` validieren feste Workspace-Statewurzeln vor Lock, Read, Schemaanlage oder Write und scheitern bei Umleitung geschlossen. `tests/unit/test_run_surface_integration_220.py` prüft Commands, Snapshotloader sowie DB- und Sidecar-Hardlinks.

### MW220-046/-049: Prozessbesitz beginnt vor Setup und endet auch nach Erfolg

Timeout-/Fehlerpfade räumten Bäume auf, erfolgreiche Clean-, Typechecker- oder Workerprozesse konnten aber Hintergrundkinder zurücklassen. Die erste Closure führte POSIX-Sessions, suspendierten Windows-Start und spätes `TaskStarted` ein; MW220-061 schloss danach das atomare Windows-Create→Assign-Fenster und MW220-066 die synchrone POSIX-Pre-exec-Publikationslücke. Der im finalen Reaudit bestätigte Hard-Parent-Exit-Pfad benötigte zusätzlich MW220-075. Taskdeadline und Pool-Watchdog begrenzen weiterhin die gesamte Vorbereitungsphase. Evidenz: `tests/integration/test_success_process_tree_cleanup.py`, `tests/unit/test_process_worker.py`, `tests/unit/test_pool_collapse_127.py`, `tests/unit/test_runner.py` und `tests/unit/test_type_checking.py`; die vervollständigenden Regressionen stehen in Abschnitt 17.

### MW220-047: Korrektheit vor Selektivität, Reuse nur mit beweisbar vollständigem Kontext

Die aktuelle Hit-Erhebung kann selektive Zuordnungen nicht end-to-end autoritativ beweisen. Die Closure erfindet daher keine Selektivität: Mapping bleibt explizit nichtautoritativ und führt stets zur Vollsuite. Sichere Wiederverwendung bleibt dennoch erreichbar, aber nur bei unverändertem Source-/Universe-Fast-Path und einem beweisbar vollständigen Kontextdigest. Der finale Reaudit MW220-073 erweiterte diesen Vertrag über Projekt- und Konfigurationsbytes hinaus auf installierte und editierbare Abhängigkeiten, geerbte Environment-Werte, den geordneten effektiven Importpfad einschließlich `.pth`/unregistrierter Module sowie Runtime/Executable. Kann irgendein Bestandteil nicht vollständig inventarisiert werden, werden weder Stats-Mapping noch Verdicts wiederverwendet. `src/mutmut_win/stats.py` und `src/mutmut_win/orchestrator.py` trennen damit Mappingautorität, Kontextvollständigkeit und Reuse-Gültigkeit; `tests/unit/test_result_reuse_119.py` und `tests/unit/test_dependency_basis_220.py` pinnen den Vertrag.

Der reale Closure-Repro für GitHub Issue #133 bestätigt diesen Pfad zusammen mit dem vorhandenen #130/360-B3-Vollsuite-Budget. In einem isolierten detached Consumer-Snapshot `8296cd9ac1a06cce50f0841ebd1c6ffaa4828823` lief der v2.21.0-Kandidat gegen exakt `llm_fusion_mcp.eval.verifiers.math_matcher.x_verify__mutmut_1`. Obwohl 73 Mappingkanten für 100 Tests beobachtet wurden, blieb das Mapping nichtautoritativ und die Task erhielt das Vollsuite-Budget `max(60, clean_wall × 30)`: bei geloggten 3,7 s Clean-Wall nominal rund 111 s. Run `c4705ab1-229a-42b5-b343-0fe692a6d257` endete mit Orchestrator-Exit 0, `completed 1/1`, `pending 0`, `reused 0`; der Mutant wurde nach 1,8833385 s mit Test-Exit 1 getötet, ohne Timeout-/Suspicious-/Skip-/No-tests-Diagnose. SQLite `quick_check` und die CLI-Zähler waren konsistent. Der damalige uncommittete 227-Mutanten-Arbeitsbaum ist nicht bytegenau rekonstruierbar; verwendet wurden der letzte Commit vor Issue-Erstellung, die dokumentierte Ad-hoc-Testeingrenzung und `clean_run_timeout=900`. Der fachlich diskriminierende `\boxed{42}`-Node-ID war im beobachteten Mapping enthalten. Damit reproduziert v2.21.0 den gemeldeten Timeout-Flood nicht; es ist kein zusätzlicher MW220-116-Produktionsfix erforderlich.

## 15. Closure der 49 Befunde

`implementiert` beziehungsweise `geschlossen` bezeichnet hier den konkreten Produktions- und Regressionstestfix bis MW220-049. Es ist keine Behauptung, dass der nach der dritten Welle weiter veränderte Baum bereits die repositoryweiten Abschlussgates bestanden hat; diese stehen ausschließlich in Abschnitt 18.

| ID | Closure | Produktions- und Testevidenz |
|---|---|---|
| MW220-001 | implementiert; Kontextvollständigkeit durch MW220-073 erweitert | `stats.py` bildet einen SHA-256-Kontext über Projekt-, Test-, Helper-, Fixture-, Lock- und pytest-Konfiguration; MW220-073 ergänzt die effektive Abhängigkeits-/Environment-/Import-/Runtimebasis; `test_review_cache_integrity.py`, `test_result_reuse_119.py`, `test_dependency_basis_220.py` |
| MW220-002 | implementiert | Nichtautoritative Refresh-Recovery in `stats.py` erzwingt Vollsuite statt altem Mapping; `test_stats_truth.py`, `test_surface_hardening_220.py` |
| MW220-003 | implementiert | `runner.py` erhält Collection-/Import-Hits; xdist/Kindprozessfälle verlieren Autorität und fallen konservativ zurück; `test_surface_hardening_220.py`, `test_stats.py` |
| MW220-004 | implementiert | Begrenzte Collection mit Returncode-, Timeout- und Tree-Cleanup in `runner.py`; `test_surface_hardening_220.py`, `test_runner.py` |
| MW220-005 | implementiert | Zentral validierte Selektionsargumente erreichen Runner und Spawn-Worker; `test_surface_hardening_220.py` |
| MW220-006 | implementiert | Read-only Fingerprintvergleich und Commit erst nach Gesamtgeneration in `file_setup.py`/`orchestrator.py`; `test_staging_hygiene.py`, `test_review_cache_integrity.py` |
| MW220-007 | implementiert | Unerwartete Generationsfehler brechen die Phase ab, Output/Meta werden transaktional veröffentlicht; `test_review_cache_integrity.py`, `test_generation_supervisor.py` |
| MW220-008 | implementiert | Aufgelöste Projekt-/Staging-Containmentprüfung und rekursionsfreies Pruning in `config.py`/`file_setup.py`; `test_staging_hygiene.py`, `test_file_setup.py` |
| MW220-009 | implementiert | Source-, Mirror-, Reuse- und Apply-Autorität beruhen auf Inhaltsdigests in `file_setup.py`, `models.py`, `orchestrator.py`, `mutant_diff.py`; `test_review_cache_integrity.py`, `test_source_protection.py` |
| MW220-010 | implementiert | Interne Trampolinfunktionen evaluieren Defaults/Annotationen/Decorators nicht erneut und erhalten den öffentlichen Docstring; `mutation.py`; `test_default_param_skip.py`, `test_mutation_adversarial_a5.py` |
| MW220-011 | implementiert | Kollisionsfeste Wrapperbindung sowie Sync-/Async-Generatorsemantik in `mutation.py`; `test_wrapper_codegen.py`, `test_mutation_adversarial_a5.py` |
| MW220-012 | implementiert | Regexmutation arbeitet auf `evaluated_value`, serialisiert sicher und verwirft nur ungültige Kandidaten; `node_mutation.py`; `test_regex_mutation.py`, `test_mutant_safety_net.py` |
| MW220-013 | implementiert | Pragmaauswertung verwendet echte COMMENT-Tokens in `mutation.py`; `test_mutation_adversarial_a5.py`, `test_mutation_hardening_round2.py` |
| MW220-014 | implementiert | Kanonisierte Covered Lines sind Bestandteil des Universe-Fingerprints; `file_setup.py`; `test_review_cache_integrity.py`, `test_code_coverage.py` |
| MW220-015 | implementiert | `do_not_mutate_patterns` ist Bestandteil des Universe-Fingerprints; `file_setup.py`; `test_review_cache_integrity.py`, `test_do_not_mutate_patterns.py` |
| MW220-016 | implementiert | Mutanten werden dedupliziert; gleichnamige Definitionen erhalten ab Vorkommen 2 eine reversible `ǁ<Ordinal>`-Identität, Vorkommen 1 bleibt kompatibel; `trampoline.py`, `mutation.py`, `test_mapping.py`, `mutant_diff.py`; `test_duplicate_definitions_220.py` |
| MW220-017 | implementiert; Kontextvollständigkeit durch MW220-073 erweitert | Verdict-Reuse ist an denselben beweisbar vollständigen Kontextdigest gebunden; unvollständige Dependency-/Environment-Evidenz deaktiviert Reuse; `stats.py`/`orchestrator.py`; `test_result_reuse_119.py`, `test_review_cache_integrity.py`, `test_dependency_basis_220.py` |
| MW220-018 | implementiert | Executor-Liveness wird pro Worker/Fortschritt bewertet; `process/executor.py`; `test_process_executor.py`, `test_worker_liveness.py` |
| MW220-019 | implementiert | Typechecker nutzt begrenzte Pipe-Capture und Tree-Reaping bei Timeout/Interrupt; `type_checking.py`; `test_type_checking.py`, `test_type_checker_process_tree.py` |
| MW220-020 | implementiert | Eigener Generation-Supervisor mit No-Progress-Deadline und hart begrenztem Tree-Abbruch; `process/generation_supervisor.py`, `orchestrator.py`; `test_generation_supervisor.py` |
| MW220-021 | implementiert | SQLite speichert Versuch, exakten Plan, Run-ID, Universe-Fingerprint, Pending und Completion; kanonischer Workspace-Lock schützt Run/Force/Apply/Export; `db.py`, `process/run_lock.py`; `test_run_identity_220.py`, `test_run_surface_integration_220.py` |
| MW220-022 | implementiert | Runner und Worker reapen Prozessbäume auch bei Interrupt/BaseException; `runner.py`, `process/worker.py`; `test_surface_hardening_220.py`, `test_interrupt_honesty.py` |
| MW220-023 | implementiert | Ungewisse oder unvollständige Abschlüsse bleiben `unchecked` und können keinen Complete-Status erzeugen; `orchestrator.py`/`db.py`; `test_run_surface_integration_220.py`, `test_status_truth.py` |
| MW220-024 | implementiert; Publishergrenze durch MW220-074 vervollständigt | Stats/CI-JSON werden über den gemeinsamen namespace-sicheren Atomic-Writer publiziert; subprocess-Ausgabe wird in einer begrenzten Pipe-Tail gehalten; `stats.py`, `atomic_file.py`, `process/output_capture.py`; `test_stats.py`, `test_bounded_output_capture_220.py`, `test_run_surface_integration_220.py` |
| MW220-025 | implementiert | Hatch-Sdist ist auf Source, Tests, README, Lizenz, Projektdatei und Lockfile allowgelistet; `pyproject.toml`, `test_surface_hardening_220.py`; Arbeitsbaumsnapshot durch Doppelbuild belegt, integrierter Commit wird erneut gebaut |
| MW220-026 | implementiert und auditbelegt | Sicherheitsminima für click/msgpack/pip und `uv.lock` wurden aktualisiert; kanonischer 354-Zeilen-Export ohne bekannte Advisories |
| MW220-027 | implementiert | Ruff verwendet `extend-exclude` statt ersetzender Excludes; `pyproject.toml`; repositoryweites lokales Gesamtfinalgate ist grün |
| MW220-028 | implementiert | E2E-Projekte werden isoliert ausgeführt und nicht editable in die Projektumgebung installiert; `test_e2e.py`, `test_e2e_pipeline_validation.py` |
| MW220-029 | implementiert | SQLite-Verbindungen werden explizit geschlossen und Regex-Warnings bereinigt; `db.py` und Integrationstests; `test_db_hardening.py` |
| MW220-030 | implementiert | Wildcard-Suffix, lokales `cast`, `deepcopy`-Deklaration und kurzer Hit-Stack sind korrigiert; `test_mapping.py`, `mutation.py`, `hit_recording.py`; `test_test_mapping.py`, `test_typing_cast_skip.py`, `test_mutation_adversarial_a5.py`, `test_hit_recording.py` |
| MW220-031 | implementiert und im lokalen Gesamtfinalgate grün | README und Reviewdokumente bilden die Vertrauensgrenzen ab; nur integrierter Artefaktbuild und Veröffentlichung bleiben offen |
| MW220-032 | implementiert | CLI-Score- und Config-Grenzen verwerfen NaN/Infinity explizit; `cli.py`, `config.py`; `test_contract_120.py`, `test_clean_run_timeout.py` |
| MW220-033 | implementiert | Phasenneutralisierende pytest-Argumente werden vor dem Start abgelehnt; `runner.py`; `test_surface_hardening_220.py` |
| MW220-034 | implementiert | Explizite No-Match- und vollständige Leerläufe scheitern ohne falsche `skipped`-Persistenz und halten JSON maschinenlesbar; `cli.py`/`orchestrator.py`; `test_surface_hardening_220.py` |
| MW220-035 | implementiert; spätere PSF-Pflicht separat als MW220-072 geschlossen | ISC- und BSD-3-Clause-Texte wurden zunächst ergänzt; der aktuelle Composite-Vertrag `ISC AND BSD-3-Clause AND PSF-2.0` einschließlich PSF-Text/Notice/Änderungszusammenfassung steht in `pyproject.toml` und `LICENSE`; MW220-105-Artefakte waren bytegenau grün, integrierter Commit wird erneut gebaut |
| MW220-036 | implementiert | `setup.cfg` liest ohne Interpolation, kapselt Parserfehler als `ConfigError` und tokenisiert Argumente shellartig; `config.py`; `test_config.py` |
| MW220-037 | implementiert | JSON-No-op, gemeinsame Scoreaggregation, Browserstatus und strikte Meta-Validierung sind vereinheitlicht; `cli.py`, `stats.py`, `browser.py`, `models.py`; `test_surface_hardening_220.py`, `test_run_surface_integration_220.py`, `test_models.py` |
| MW220-038 | implementiert | Sämtliche Timeout-/Ratio-/Dauerfelder validieren Endlichkeit; `config.py`, `models.py`, `process/generation_supervisor.py`; `test_contract_120.py`, `test_generation_supervisor.py` |
| MW220-039 | geschlossen | Tooling-, Dotenv-, Run-Lock- und externe Symlink-/Junction-Pfade werden nicht automatisch gespiegelt oder destruktiv verfolgt; `file_setup.py`, `cli.py`, `process/run_lock.py`; `test_file_setup.py`, `test_staging_hygiene.py`, `test_run_surface_integration_220.py` |
| MW220-040 | geschlossen | Der Reader garantiert einen nach Stopbeginn gestarteten Drain-Pass und erhält bereits geschriebene Diagnostik; `process/output_capture.py`; deterministischer Race-Test in `test_bounded_output_capture_220.py`, Markertest 100/100, 147 angrenzende Tests grün |
| MW220-041 | geschlossen | `time-estimates` behandelt beschädigte historische Mutantennamen konservativ statt mit `ValueError`; `cli.py`; `test_cli.py` |
| MW220-042 | geschlossen | Staging-Ziele werden komponentenweise gegen Symlink/Junction geprüft, Hardlinks vor Writes ersetzt; `file_setup.py`; `test_file_setup.py` |
| MW220-043 | geschlossen | `KeyboardInterrupt` wird in jeder Pipelinephase als `interrupted` persistiert und weitergereicht; `orchestrator.py`; `test_run_surface_integration_220.py` |
| MW220-044 | geschlossen | Staging-Skiplisten verwenden Windows-gerechtes `casefold()`; `file_setup.py`; `test_staging_hygiene.py` |
| MW220-045 | geschlossen | Default-Cache, DB und Sidecars verweigern umgeleitete oder hart verlinkte Workspace-Statepfade vor Read/Migration/Write; `cli.py`, `db.py`; `test_run_surface_integration_220.py` |
| MW220-046 | geschlossen; durch MW220-061 und MW220-075 ergänzt | Erfolgreiche Prozessbäume werden auf POSIX über Sessions/Prozessgruppen und unter Windows atomar ab `CreateProcess` im Job besessen und bereinigt; Linux-Hard-Parent-Liveness ab privatem Child-Entry folgt aus MW220-075, die generische POSIX-Pre-Entry-Restgrenze bleibt dokumentiert; Prozessmodule und Spawn-Regressionen |
| MW220-047 | geschlossen; Kontextvollständigkeit durch MW220-073 erweitert; realer Issue-#133-Consumer-Repro grün | Mapping bleibt korrektheitshalber nichtautoritativ/Vollsuite; #130/360-B3 budgetiert diese Tasks gegen den Clean-Wall-Lauf; isolierter historischer Consumer-Snapshot `8296cd9a…`: 1/1 completed, killed, 0 timeout/suspicious, Orchestrator-Exit 0; Vollsuite-Verdicts dürfen nur bei identischem beweisbar vollständigem Source-/Test-/Config-/Dependency-/Environment-/Import-/Runtimekontext wiederverwendet werden; `stats.py`, `orchestrator.py`; `test_result_reuse_119.py`, `test_dependency_basis_220.py` |
| MW220-048 | geschlossen | Neuer Run und erfolgreiches Apply invalidieren Latest-Run-/CI-Artefakte vor neuer Evidenz; `orchestrator.py`, `cli.py`, `db.py`; `test_run_surface_integration_220.py` |
| MW220-049 | geschlossen; durch MW220-066 und MW220-075 ergänzt | `TaskStarted` folgt erst auf belastbare synchrone Prozess-/PGID-Evidenz; Deadline beginnt vor Setup und Startup-Watchdog bleibt bis dahin aktiv; MW220-075 ergänzt den harten Tod des obersten POSIX-Parents; `process/worker.py`, `process/executor.py`, `process/posix_spawn.py`; Prozess- und Hard-Exit-Regressionen |

## 16. Dritte Welle und finale Multi-Agenten-Diff-, Claim- und Boundary-Reaudits

### MW220-050 bis -053: Gemeinsamer State braucht physische Lock- und Evidenzdomänen

Der Workspace-Lock allein serialisierte nur denselben Checkout. Zwei Workspaces mit demselben absoluten DB-Pfad oder Hardlink-Alias konnten gleichzeitig arbeiten; ein späterer Start durfte dabei den fremden Live-Run als vermeintlich verwaist behandeln. `src/mutmut_win/process/run_lock.py` stellt deshalb eine stabile, deadlockfreie Reihenfolge Workspace → kanonischer DB-Pfad → vorhandene Dateiidentität bereit. Orchestrator, Apply und CI-Export verwenden dieselbe Domäne; benutzerdefinierte DB-Hardlinks werden an der Pfadgrenze zusätzlich fail-closed abgelehnt. Regressionen: `test_database_lock_domains_cover_canonical_path_and_hardlink_identity`, `test_absolute_database_uses_same_lock_domain_from_different_workspaces`, `test_live_database_holder_excludes_hardlink_alias_across_processes` und `test_shared_hardlink_database_is_rejected_without_foreign_run_invalidation`.

CI-Export akzeptiert keine Legacy-Zeile mehr als Release-Autorität. Ein moderner Run speichert einen vollständigen Source-/Test-/Config-Basisfingerprint aus einem stabilen Doppelsnapshot; unmittelbar vor `finish_run(..., "completed")` wird derselbe Live-Workspace erneut berechnet. Drift führt zu `failed`, nicht zu `completed`. Export berechnet die Basis erneut und entfernt bei jeder Abweichung das Artefakt. Das decken `test_cicd_export_requires_live_source_test_and_config_basis`, `test_modern_completed_run_without_basis_cannot_authorize_cicd_export`, `test_initial_run_basis_must_be_a_stable_snapshot` und `test_mid_run_source_drift_is_recorded_failed_not_completed` ab. Diagnosebefehle behalten die Legacy-BWC, ohne sie dem CI-Gate zu verleihen.

Die effektive und validierte `--tests-dir`-Konfiguration wird jetzt vor `--since-commit` angewandt. `test_since_commit_uses_effective_custom_tests_dir_before_filtering` verhindert, dass ein benutzerdefinierter Testbaum als Mutationstarget durchrutscht.

### MW220-054 bis -060: Atomicität umfasst Namespace, publizierte Bytes und semantischen State

Ein Rename allein war noch keine sichere Atomic-Write-Grenze: vorhersagbare `.tmp`-/Backupnamen, Linkblätter, umgeleitete Eltern und ein Close→Reopen konnten auf externe Dateien zeigen. `src/mutmut_win/atomic_file.py` veröffentlicht über private, exklusiv angelegte Geschwisterdateien, prüft Eltern und Identität und ersetzt Linkblätter statt Referenten. Die erste Closure migrierte Meta-, Apply-, Runner- und zentrale Statewriter; der finale Writer-Reaudit MW220-074 fand und schloss die verbliebenen eigenen Publisher für Stats-/CI-JSON, generierte pytest-Plugins, Phase-Guard/Proof, pytest-Argfiles und Run-Lock-Owner. Das Produktinventar enthält danach außer `atomic_file.py` keinen eigenen Rename-Publisher und keinen direkten `write_text`-/`write_bytes`-/`mkstemp`-Writer mehr; die zwei verbleibenden anonymen `TemporaryFile`-Nutzungen sind seekbare Bootstraps und publizieren keinen Pfad. `tests/unit/test_atomic_write_safety_220.py`, `tests/unit/test_runner_sidecar_safety.py` sowie die Parent-Swap-/Redirect-Regressionen prüfen Hardlink, Symlink, Parent-Redirect, Substitution und Replace-Failure.

Der Generations-Fast-Path ist nun an SHA-256 der tatsächlich publizierten Python-Bytes gebunden. Legacy-Meta ohne `generated_hash`, manuell veränderte Ausgabe oder Output ohne passenden Meta-Commit erzwingt Regeneration. `_copy_with_retry()` behält denselben exklusiven Descriptor bis zur Veröffentlichung und erhält die Freshness-Metadaten ohne verwertbares Close→Reopen-Fenster. Regressionen: `test_generated_file_tamper_forces_regeneration`, `test_legacy_meta_without_generated_hash_regenerates_once`, `test_output_publish_without_meta_commit_cannot_authorize_fast_path` und `test_atomic_staging_copy_detects_close_substitute_without_external_write` in `test_staging_authority_p1_220.py`.

Invalidierte Evidenz erscheint im Browser und in `results` explizit als stale beziehungsweise `release-ready: no`; normale und reine Legacy-Anzeige bleiben kompatibel. Belege: `test_browser_marks_invalidated_completed_run_stale_and_not_release_ready` und `test_results_marks_invalidated_evidence_not_release_ready`.

`validate_cache_path()` schützt jetzt auch benutzerdefinierte DB-Pfade, alle Parent-Komponenten, das DB-Blatt und SQLite-Sidecars. Neue DBs werden exklusiv vorangelegt; die absolute Dateiidentität wird vor und unmittelbar nach `sqlite3.connect`, vor Schema-/Writegrenzen, vor Commit, beim erfolgreichen Connection-Exit und unmittelbar vor Rückgabe eines Current-Run-Snapshots erneut geprüft. Damit scheitert auch der bestätigte permanente POSIX-Pfadtausch nach der letzten SQL-Abfrage geschlossen. Deterministische Hardlink-, Parent-, Connect-, Sidecar- und Post-Read-Swap-Tests stehen in `test_db_state_boundary_220.py`, insbesondere `test_load_current_run_rejects_permanent_path_swap_after_final_query`. Python `sqlite3` akzeptiert nur einen Pfad und keinen bereits sicher geöffneten Descriptor; ein vollständiger aktiv herbeigeführter Same-User-ABA exakt zwischen zwei Prüfungen kann daher ohne nativen Broker nicht kernelgarantiert ausgeschlossen werden. Diese engere Restgrenze ist kein Freibrief für permanente Swaps.

Loader wandeln defektes JSON, SQLite-Typ-/Statussemantik und Pydantic-Fehler in `CorruptCacheError` um. Zulässige persistierte Verdicts werden explizit validiert, einschließlich der historischen Anzeigezustände; neue unbekannte Status werden vor DB-Anlage abgelehnt und moderne Run-Ergebnisse dürfen keine Nicht-Verdicts sein. `completed` erfordert zwingend `plan_finalized=True`, keine Pending-Namen und einen beim Abschluss erneut geprüften exakten Plan.

Der bisherige `universe_fingerprint` enthält Generationsmetadaten und ist deshalb nicht allein aus den geladenen Planzeilen nachrechenbar. Neue Runs speichern ergänzend einen SHA-256-`plan_digest` über die vollständige geordnete Mutantennamenfolge. `load_current_run()` prüft lückenlose Ordinale und diesen Digest gegen genau die im selben Snapshot geladenen Zeilen. Migrierte Runs ohne Digest bleiben diagnostisch lesbar, dürfen CI aber nicht autorisieren. Zusätzlich muss der neueste Header-`sequence`-Wert dem `sqlite_sequence`-High-Water-Mark entsprechen; Orphan-Planzeilen oder ein gelöschter neuester Header gelten als Korruption, sodass kein älterer grüner Run resurrected wird. Zentrale Regressionen sind `test_load_current_run_revalidates_exact_ordered_plan_digest` (Delete, Reorder, Name-Austausch), `test_load_current_run_rejects_noncontiguous_plan_ordinal`, `test_load_current_run_rejects_orphan_plan_after_latest_header_rollback`, `test_cicd_export_rejects_header_high_water_rollback_and_removes_stale_artifact`, `test_cicd_export_rejects_deleted_plan_row_and_removes_stale_artifact` und `test_cicd_export_rejects_missing_migrated_plan_digest`; die früheren Legacy-/Status-/Completed-Korruptionsregressionen bleiben bestehen.

### MW220-061 bis -068: Prozessbesitz muss vor Interpreter- und Nutzcode beginnen

Unter Windows schließt `process/atomic_spawn.py` das verbleibende CreateProcess→Assign-Race mit `PROC_THREAD_ATTRIBUTE_JOB_LIST`: das Kind ist bei seiner ersten User-Mode-Beobachtung bereits Job-Mitglied. Der Multiprocessing-Bootstrap wird vor Resume vollständig in seekbarem Speicher serialisiert; `.pth`/`sitecustomize` kann `Process.start()` daher nicht über eine gefüllte Bootstrap-Pipe blockieren. Private Spawn-Innereien sind fail-closed auf CPython 3.12–3.14 begrenzt, und Resume-/Containmentfehler werden als fataler Poolfehler behandelt. Belege: `test_child_is_job_member_at_first_user_mode_observation`, `test_pool_has_no_post_create_assignment_hard_exit_window`, `test_wedged_sitecustomize_large_payload_is_contained_and_nonblocking`, `test_unknown_private_backend_fails_closed` und `test_real_task_resume_failure_is_fatal_and_stops_worker`.

Unter POSIX erzeugt `process/posix_spawn.py` Multiprocessing-Kinder bereits an der `fork_exec`-Grenze in einer neuen Session und serialisiert den Bootstrap vor dem Interpreterstart in seekbarem Speicher. Worker starten pytest hinter einem EOF-sicheren Pre-exec-Pipe-Gate: Worker-ID und PGID werden synchron publiziert, erst dann gibt der Parent den Interpreter-/Nutzcode frei. Der Executor besitzt diese PGID-Evidenz unabhängig vom Worker und kann die Testsitzung nach einem Worker-`SIGKILL` per `killpg` reapen. MW220-075 ergänzt die Liveness beim harten Tod des obersten Parents: Auf Linux setzt der private Child-Entry als erste Operation `PR_SET_PDEATHSIG` und prüft unmittelbar danach die erwartete Parent-PID; nach Eintritt übernimmt zusätzlich der EOF-Watcher und reapet die Session/Prozessgruppe. Zentrale Regressionen umfassen `test_hung_generation_is_bounded_and_supervisor_is_reaped`, `test_abort_reaps_worker_grandchild`, den realen WSL-Test `test_worker_sigkill_reaps_registered_pytest_session` sowie reale Hard-Parent-Exit-Tests für Kind und Prozessbaum unter Last.

Executor- und Typechecker-Cleanup bestehen aus unabhängigen, begrenzten Stufen; Join-, Kill-, Queue-, Prozessgruppen- oder Jobfehler überspringen spätere Ressourcen nicht und maskieren den ursprünglichen Fehler nicht (`test_cleanup_failures_do_not_skip_later_resources_or_escape`, `test_job_close_failure_does_not_skip_fallback_kill_or_mask_timeout`). Erfolgreiches Generation-`DONE` erhält einen eigenen begrenzten 15-Sekunden-Join statt des kurzen Abortbudgets (`test_done_teardown_uses_its_own_generous_bounded_timeout`). Die verbleibende POSIX-Grenze ist ausdrücklich dokumentiert: Linux besitzt die beschriebene Child-Entry-Absicherung; auf generischem POSIX ohne cgroup-/`PDEATHSIG`-Äquivalent bleibt das kleine Pre-Entry-Fenster vor Installation des EOF-Watchdogs nicht kernelgarantiert schließbar. Der bestätigte Worker-Tod bei lebendem Executor und der Linux-Hard-Parent-Exit ab privatem Child-Entry sind geschlossen.

### MW220-069 bis -071: GitHub-CI und Runtime-Metadaten

Diese drei Punkte sind lokal **implementiert und fokussiert verifiziert**. `pyproject.toml`, Lockfile und README begrenzen den Vertrag auf CPython 3.12–3.14 sowie pytest ≥ 8.2 und < 10. `.github/workflows/ci.yml` prüft Windows und Ubuntu über die Python-Matrix, hält Berechtigungen minimal, pinnt allowgelistete Actions an vollständige Commit-SHAs und trennt Lock, Quality, Security, Tests, pytest-8.2-Boundary-Kompatibilität, Audit, Build sowie installierte Wheel-/Sdist-Smokes. Die adversariale Nachschärfung entfernt eine globale Frozen-Konfiguration, damit `uv lock --check` echte Lock-Drift erkennt, führt `pip-audit` für jede OS-/Python-Kombination aus und baut zweimal offline aus einem explizit gelockten Build-Environment. `tests/unit/test_release_supply_chain.py` pinnt diese statischen Verträge. Der lokale Packaging-Handoff ist erfolgt. PR #134 führte diese CI tatsächlich teilweise aus und deckte die späteren Blocker MW220-112 bis -114 auf. Ein Follow-up-Lauf kann wegen Billing ausbleiben; er darf dann nicht als Remote-PASS behauptet werden.

### MW220-072: Composite-Lizenz und CPython-Provenienz

Die privaten Spawnadapter leiten Code und Struktur aus CPython ab. Der frühere reine ISC-/BSD-Paketvertrag war deshalb unvollständig. `LICENSE` enthält nun den vollständigen PSF-2.0-Text, den CPython-Copyright-Hinweis und eine Änderungszusammenfassung; `pyproject.toml` deklariert den Composite-Vertrag `ISC AND BSD-3-Clause AND PSF-2.0`. Die fokussierte Supply-Chain-Regression pinnt Text, Hash und Metadaten. Wheel und Sdist des MW220-105-Arbeitsbaums enthielten die Lizenz byteidentisch; nach der LF-Policy- und Teständerung folgt ein frischer Doppelbuild und nach Integration derselbe Beweis nochmals auf dem exakten Releasecommit.

### MW220-073: Reuse und CI benötigen eine vollständige Execution-Basis

Source-, Test- und Konfigurationsbytes allein autorisieren keine Wiederverwendung, wenn dieselben Imports unter anderen Paketbytes, Editables, Importpfaden, Runtime- oder Environmentwerten laufen. Die Basis umfasst deshalb zusätzlich die lesbaren Bytes installierter Distributionen und editierbarer Quellen, den geordneten effektiven `sys.path` einschließlich `.pth`- und nicht durch Distributionen beanspruchter Module, Runtime/ABI/Executable sowie ausnahmslos die vollständige geerbte Umgebung. Auch Namen der internen Mutanten-Handshake-Variablen bleiben gebunden: Vor dem Child-Start vorhandene Werte sind Teil der Parentbasis; die späteren kontrollierten Child-Overrides schaffen keine Ausnahme im Beweis. Vorübergehende interne `sys.path`-Änderungen werden vor der Pre-Completion-Revalidierung auf die ursprüngliche Reihenfolge zurückgesetzt.

Vollständigkeit ist typisierte Evidenz und kein Hashwert, der bei Inventarfehlern auf einen scheinbar normalen Digest reduziert werden darf. Kann ein Bestandteil nicht sicher gelesen oder inventarisiert werden, darf der technische Plan weiterlaufen und `completed` erreichen, aber Stats- und Verdict-Reuse bleiben deaktiviert, persistierte Basis-/Konfigurationsautorität bleibt leer und CI-Export muss fail-closed ablehnen. Verdict-Fingerprints verwenden eine versionierte volle SHA-256-Repräsentation. Die Implementierung und Regressionen haben den unabhängigen fokussierten Abschluss-Reaudit sowie die in Abschnitt 18 dokumentierte vollständige Post-MW220-111-Kandidatenmatrix bestanden.

### MW220-074/-075: Restpublisher und Hard-Parent-Liveness

Der finale Diff-Reaudit schloss die in Abschnitt 16 beschriebenen Restpublisher über den gemeinsamen Atomic-Writer und bestätigte das geschlossene Produktwriter-Inventar. Der Prozess-Reaudit schloss unter Linux den belegten Hard-Parent-Exit für Sessionkind und Prozessbaum ab privatem Child-Entry. Die generische POSIX-Pre-Entry-Restgrenze ohne Kernelprimitiv bleibt ausdrücklich bestehen; sie wird nicht als plattformweite Garantie umgedeutet.

### MW220-076/-078: Generische Typechecker sind keine beweisbar vollständige Basis

`type_check_command` ist bewusst ein generischer argv-Vertrag. Eine rein syntaktische Interpretation kann weder alle über `PATH`, `python script.py`, `python -m`, `uv run`, Shell-/npm-Wrapper oder Responsefiles erreichbaren Bytes noch deren Plugins und Konfiguration vollständig inventarisieren. Ein nicht leeres Kommando macht die Execution-Basis deshalb konservativ unvollständig: Der technische Plan und die Typklassifikation dürfen weiterlaufen, aber Stats-/Verdict-Reuse bleiben deaktiviert, `--min-score` und CI-Export lehnen fail-closed ab. Moderne Runs persistieren keine scheinbare Basisautorität. Für historische Runs erkennt `known_run_basis_incompleteness()` auch eine formal vorhandene Fingerprint-Paarung zusammen mit einem generischen Typechecker; `results` und `browse` zeigen dann ausdrücklich `execution basis incomplete; release-ready: no`. Belege liegen in `test_dependency_basis_220.py`, den CLI-/Browser-Regressionen sowie `db.py`, `cli.py` und `browser.py`.

### MW220-077: pytest erhält eine immutable, identitätsgebundene Ausführungsgrenze

Vor jeder Mutation wird genau eine pytest-Grenze Schema v2 eingefroren. Sie bindet Staging-Root, ausgewählte Config und explizite Testziele an kanonischen Pfad, Typ, `st_dev`, `st_ino` und – für Dateien – Bytesdigest. Nur Pfade oder Node-IDs sind zulässig; pytest-Optionen, `--`, benutzerdefinierte `@argfiles`, NULs, Zeilenumbrüche und Windows-drive-relative Formen werden abgelehnt. Die Grenze wird vor Runner-, Executor- und Workerstart revalidiert, ist auch bei leerer Taskliste verpflichtend und jeder Driftfehler ist poolfatal.

Der Child-Guard transportiert die eingefrorenen Identitäten statt bloßer Strings, prüft sie vor Collection sowie danach und fängt frühe `conftest.py`-Discovery ab. Ein explizites externes File autorisiert kein benachbartes oder übergeordnetes `conftest.py`; ein explizites externes Verzeichnis autorisiert nur seinen eigenen Baum, nicht Routing-Vorfahren. Eine staged Config darf über `testpaths` keine ungebundene externe Testsammlung öffnen. Config-Discovery ist auf pytest ≥ 8.2 und < 10 begrenzt; unbekannte oder nicht parsebare Versionen scheitern vor Locks, DB- oder Stagingwrites. Echte isolierte Läufe unter pytest 8.2.2 und 9.x bestanden die Boundary- und Sentinel-Verträge; eine eigene Windows-/Ubuntu-CI-Stufe hält zusätzlich die minimale unterstützte pytest-Version im Blick. Die Implementierung verwendet für selektive Multi-Root-Conftest-Steuerung auditierte private pytest-Interna; deswegen bleibt die `<10`-Grenze fail-closed und die versionsübergreifende CI-Evidenz verpflichtend.

### MW220-079/-081: Finalgates müssen auch ihre eigene Evidenz zuverlässig erzeugen

Der Workflow-Reaudit fand mit actionlint/ShellCheck SC2155 eine maskierbare Command Substitution: `export SOURCE_DATE_EPOCH="$(git log ...)"` konnte den Fehlerstatus von `git log` durch den erfolgreichen Shell-Builtin ersetzen. Zuweisung und `export` sind nun getrennt; die damaligen actionlint-/ShellCheck-/Pyflakes- und Zizmor-Zwischenläufe waren grün. Derselbe Hygiene-Reaudit entfernte das einzige unsichtbare U+00AD aus dem Git-owned Inventar; die damalige Byteprüfung meldete keine Bidi-, Zero-width-, NUL-, Control-, ungültigen UTF-8- oder Merge-Marker-Funde. Frische Abschlusswerte werden nur in Abschnitt 18 als final gewertet.

Der damalige vollständige nicht instrumentierte Testlauf war grün, während Coverage zwei E2E-Aufrufer reproduzierbar am gemeinsamen 120-Sekunden-Subprocess-Limit stoppte. Der Helper bleibt hart begrenzt, erhält aber 300 Sekunden Headroom für Coverage-Tracing und belastete Windows-Runner. Beide Fälle bestanden danach fokussiert und im damaligen vollständigen Coverage-Lauf; die Grenze ist keine Produkt-Timeoutlockerung, sondern ausschließlich ein releasegate-tauglicher Testharness-Vertrag. Die finale Coverage-Evidenz wird nach allen späteren Änderungen separat neu erhoben.

### MW220-082: Identische Guard-Publisher dürfen keine fachlichen Verdicts erzeugen

Der reale Vier-Worker-Pilot reproduzierte fünf Control-Plane-Ausfälle: Jeder Task publizierte erneut `mutants/_mutmut_phase_guard.py`. Der strikt identitätsprüfende Atomic-Writer erkannte korrekt, dass ein anderer identischer Writer seine eben publizierte Inode ersetzt hatte; unter Windows scheiterte zusätzlich ein konkurrierendes Replace mit `WinError 5`. Der Worker-Recovery-Pfad degradierte diese Fehler jedoch auf Exit 35, Dauer 0 und `suspicious`. Genau fünf Mutanten wurden nie getestet, dennoch speicherte die DB 90/90 completed und `execution_basis_complete=true`.

`ensure_atomic_bytes()` akzeptiert nun ausschließlich einen byteidentischen, über Handle sowie `lstat`/`fstat` stabil verifizierten regulären Einzel-Link-Gewinner eines expliziten Replace-/Post-Identity-Races. Symlink, Reparse Point, Hardlink, fremde Bytes und nicht verifizierbare Writer-/Pfad-/fsync-Fehler bleiben abgelehnt. Guard-Publisherfehler werden als fataler `PytestBoundaryError` transportiert; Executor und Orchestrator brechen den Run ab, zählen oder persistieren kein fachliches Verdict und lassen den Mutanten pending. Ein deterministischer Fünf-Publisher-Test erzwingt die Kollision; Worker-, Orchestrator- und DB-Regressionen pinnen die Fatal-/Pending-Wahrheit.

### MW220-083/-084: Dogfooding misst Testqualität und benötigt echte Isolation

Die vollständige Diff-/DB-Forensik des ersten Piloten klassifizierte 21 Survivors: 18 waren beobachtbare Testlücken in semantischem Datenpfad, stale-Coverage-Entfernung, Nonzero-Exit, Missing-/Empty-Diagnostik und gemessener/ungemessener Mappingsemantik; drei waren unter Windows beziehungsweise der Coverage-API echte Äquivalente. Die fünf `suspicious` waren ausschließlich der MW220-082-Race, zwei davon hätten bestehende Tests ohnehin getötet, zwei deckten zusätzliche reale Mapping-/Diagnoselücken auf und einer war ein weiteres case-only Äquivalent. Die Tests prüfen nun exakte `CoverageCollectionError`-Verträge, frische Datenpfade und Mixed Mapping. Eine DB-freie Vorprobe tötete 22/26 frühere Nicht-Kills; der erneute reale Pilot erreichte 86/90 = 95,6 % bei vier dokumentierten Äquivalenten, 0 suspicious und vollständiger Execution-Basis.

Eine angrenzende Surface-Regression las trotz gemockter Legacy-Resultate den echten Current-Run-Snapshot aus der lokalen Dogfood-DB. Sie mockt nun die vollständige Snapshot-Grenze und bestand mit absichtlich vorhandener `.mutmut-cache`; reale Entwicklungsartefakte können den synthetischen Scorevertrag nicht mehr überschreiben.

### MW220-085: Ein gelockter Build benötigt auch auf leeren Runnern einen expliziten Backend-Bootstrap

Der exakte CI-Sync `uv sync --locked --extra dev --group build --no-build-isolation` scheiterte in einer wirklich frischen externen Umgebung zunächst ohne `hatchling`. Ein reiner Hatchling-Bootstrap legte anschließend die zweite verdeckte Voraussetzung offen: Hatchlings editierbarer PEP-660-Build benötigt `editables`, das ebenfalls nicht vorinstalliert war. Der lokale Hauptbaum hatte beide Pakete bereits in seiner `.venv`; deshalb war der Workflowvertrag dort irreführend grün.

`hatchling==1.32.0` und `editables==0.5` sind nun sowohl im Build-System als auch in der gelockten Buildgruppe festgeschrieben. Quality, Tests und Audit bootstrappen vor dem vollständigen `--no-build-isolation`-Sync exakt diese Gruppe mit `--only-group build --no-install-project`. In einer neuen externen Umgebung installierte der Bootstrap beide Pins; der danach unveränderte vollständige Sync baute und installierte `mutmut-win` editierbar, und Versions-/Importsmokes waren grün. Der Release-Supply-Chain-Test pinnt Abhängigkeiten, Anzahl und Reihenfolge dieser Workflowkommandos.

### MW220-086: CLI-Tests müssen die aktuelle Snapshot-Grenze statt des Legacy-Fallbacks mocken

Der erste repräsentative Gesamtlauf auf dem nach MW220-085 finalisierten Baum stoppte in `TestResultsCommand::test_results_shows_summary`: Erwartet waren drei synthetische Zeilen, tatsächlich lieferte die reale lokale Dogfood-DB den autoritativen Current Run mit 90 Mutanten. Das Produkt verhielt sich korrekt; der Test mockte den nur noch nachrangigen `load_results()`-Fallback. Ein unabhängiger Reaudit fand 22 solche Mocks in Results-, Time-Estimate-, Deprecation-, Score- und Corrupt-Cache-Tests. Von einem 23-Test-Cluster waren 14 falsch rot; weitere Assertions bestanden nur zufällig gegen die fremden Realresultate. Drei Exporttests konnten zusätzlich echte Workspace-Locks und `mutants/mutmut-cicd-stats.json` berühren.

Results-Tests mocken nun `_load_result_snapshot_or_exit()`, Time-Estimate-Tests `_load_results_or_exit()`. Corrupt-Cache-Tests injizieren den Fehler bewusst unterhalb des echten, fehlerübersetzenden Snapshot-Helpers. Alle Exporttests wechseln in ein eigenes `tmp_path`-Workspace und besitzen dort ihren eigenen `mutants`-Root. Der vollständige 31-Test-Cluster besteht damit auch aus dem Repo-CWD bei absichtlich vorhandener 90er-Dogfood-DB; keine verbleibende `patch("mutmut_win.cli.load_results", ...)`-Stelle existiert.

### MW220-087: Lokalisierte Windows-Shellausgabe benötigt einen expliziten Unicode-Vertrag

Der Gesamtlauf meldete einen gestorbenen `subprocess._readerthread`, obwohl der zugeordnete Junction-Test selbst grün erschien. Unter deutscher CP850-Ausgabe kodiert `cmd.exe` das „ü“ in „für“ als `0x81`; `text=True` verwendete jedoch die Prozessstandardkodierung CP1252 beziehungsweise im UTF-8-Modus UTF-8, in denen dieser Bytestrom nicht strikt dekodierbar war. Alle sieben `mklink`-Aufrufer verwenden nun `cmd.exe /d /u /c` und dekodieren die dadurch garantierte umgeleitete UTF-16LE-Ausgabe explizit mit Replacement-Fallback. Erfolg und Fehlerdiagnostik wurden unter CP850 und CP65001 geprüft; 13 parametrisierte Junction-Fälle bestanden mit `PytestUnhandledThreadExceptionWarning` als Fehler.

### MW220-088: Fachliche Orchestrator-Unit-Tests dürfen kein Live-Repository auditieren

`test_orchestrator.py` prüft Ergebnisaggregation, Timeouts und Persistenz mit gemocktem Runner und Executor. Dennoch lief die vollständige Execution-Basis jedes Mal real über alle geerbten Environmentwerte, installierten Distributionen, Importpfade und den editable Clone. Die Produktgrenze verhielt sich korrekt fail-closed, als zwei aufeinanderfolgende Snapshots differierten; für diese Unit-Assertions war der externe Shared-Tree-Zustand jedoch eine unbeabsichtigte, langsame und flüchtige Abhängigkeit. Das Modul injiziert nun eine konstante vollständige `RunBasisEvidence`. Die dedizierten Basis-/Mid-Run-Drifttests bleiben unverändert real und bestanden zusammen mit dem vollständigen Orchestrator-Modul: 59/59 grün.

### MW220-089: Nur tatsächlich ausführbare Workspacebytes dürfen die Run-Basis treiben

Der anschließende Drift-Reaudit verglich die automatische Staging-Allow-/Skipgrenze mit dem projektweiten Context-Hasher. Vier generierte beziehungsweise editorinterne Bäume wurden korrekt nie nach `mutants/` gespiegelt, aber vom Hash des editable Projektbaums gelesen: `.import_linter_cache`, `.benchmarks`, `.idea` und `.vscode`. Ein parallel schreibender Linter, Benchmarklauf oder Editor konnte deshalb zwischen den zwei stabilitätsprüfenden Snapshots einen Orchestratorabbruch verursachen, obwohl kein Worker diese Bytes sah.

`WORKSPACE_EXCLUDED_DIR_NAMES` in `constants.py` ist nun die gemeinsame unveränderliche Source of Truth für automatische Staging-Walks und Projekt-/Editable-Execution-Basis. Eine parametrisierte Regression erzeugt und verändert für jeden Namen der vollständigen Menge Toolstate und beweist einen konstanten Kontextdigest; angrenzende normale Projektdateien invalidieren weiterhin. 61 Basis-/Staging-Regressionsfälle, Ruff und mypy sind grün.

### MW220-090: Ein Security-Gate darf einen unvollständigen Scan nicht als PASS akzeptieren

Der finale Security-Reaudit wertete nicht nur Semgreps Exitcode und Findings, sondern das vollständige JSON aus. Der bisher dokumentierte, unversionierte Aufruf `uvx semgrep scan --config auto --error src tests` endete mit Exit 0 und 0 Findings, obwohl `time.fixpoint_timeouts` bei 30 Sekunden 48 und selbst bei 120 Sekunden unter Default-Parallelität noch 40 Abbrüche enthielt. Semgrep 1.175.0 klassifiziert `FixpointTimeout` intern ausdrücklich als Scanfehler, der betroffene Code konnte also nicht vollständig analysiert werden. `--error` reagiert darauf nicht. Zusätzlich verschob die Split-Target-Form `src tests` unter Windows die Ignore-Relativität: 31 der 49 bewusst ausgeschlossenen Dateien unter `tests/e2e_projects/` wurden unerwartet analysiert.

Der neue getrackte, standardbibliotheksbasierte Wrapper `scripts/semgrep_release_gate.py` erzeugt aus allen Git-owned Dateien unter `src`, `tests` und `scripts` sowie `.semgrepignore` einen byteidentischen externen Root-Mirror. Er prüft Pfad-, Link-/Reparse-, Case-Kollisions-, Manifest- und TOCTOU-Invarianten, führt fest Semgrep 1.175.0 OSS mit vier Jobs, 120-Sekunden-Regelbudget, JSON- und Timingausgabe aus und akzeptiert nur die exakte dynamische Solltargetmenge. Findings außerhalb einer expliziten exakten Allowlist, `errors`, `skipped_rules`, Fixpoint-Timeouts, Rule-/Target-/Skip-/Manifest-Drift oder Baumänderung sind fatal. Der erste Root-Mirror-Repro ohne die nachfolgenden MW220-091/-092-Korrekturen bestand technisch mit 1.340 lokal auth-abhängigen Rule-IDs und 0 sichtbaren Findings; diese Zahlen sind wegen der anschließend entdeckten Suppressions- und Loginabhängigkeit ausdrücklich kein finaler Gatebeleg.

### MW220-091: Inline-Suppressionen sind keine eigenständige Security-Autorität

Der erste Wrapper-Prototyp übernahm Semgreps Defaultverhalten für `# nosemgrep`. Das Repository enthielt 18 solche Kommentare, darunter mehrere nackte Suppressionen ohne Rule-ID. Ein Angreifer oder unbeabsichtigter Edit konnte damit ein neues Finding entfernen, während JSON, Exitcode und Rule-/Targetinventar grün blieben. Der unabhängige Vollscan mit `--disable-nosem` brachte 20 strukturelle Findings zurück: ausschließlich kontrollierte Testausführungen von eigenem Codegen, zwei versionshistorische `Popen`-Hinweise, einen Import aus einer festen internen Modulliste und vier verschachtelte Pickle-Roundtrip-Matches. Kein Produktionscode-Finding wurde gefunden.

Der Gatevertrag deaktiviert Inline-Suppressionen zwingend. Zugelassen werden nur diese einzeln adjudizierten Testmatches, gebunden an normalisierten Pfad, Rule-ID, Start-/Endzeile und -spalte, SHA-256 der aus dem byteidentischen Mirror LF-normalisiert rekonstruierten vollständigen Quellzeilen sowie den LF-kanonischen Full-file-SHA der gesamten betroffenen Testdatei. Semgrep 1.175.0 lässt unter `--disable-nosem` bei allen 20 realen Resultaten `extra.is_ignored` vollständig weg; genau diese Abwesenheit ist versionsgebunden verpflichtend, jede Präsenz oder Schemaabweichung fatal. Fehlende, zusätzliche, doppelte, verschobene oder kontextveränderte Matches scheitern. Damit bleiben die Kommentare dokumentarisch sichtbar, besitzen aber keine selbstständige Gate-Autorität.

### MW220-092: Community-Regeln müssen auth-neutral und inhaltsgebunden sein

Der lokale `--config auto`-Scan war trotz `--oss-only` an einen angemeldeten Semgrep-Kontext gekoppelt: 1.856 Pro- und 1.074 Community-Regeln wurden geladen, 1.340 Rule-IDs auf dem Projekt angewandt. Ein bereinigter Runner ohne Semgrep-Token, gespeicherte Settings oder geerbte `SEMGREP_*`-Werte erhielt dagegen deterministisch 1.074 Community-Definitionen und 342 anwendbare Regeln. Der geplante GitHub-Job hätte den lokalen Rule-ID-Pin daher sicher verfehlt. Darüber hinaus beweist ein Rule-ID-Hash nicht, dass gleich benannte Remote-Regeldefinitionen inhaltlich gleich geblieben sind.

Der korrigierte Zwei-Phasen-Vertrag entfernt alle geerbten `SEMGREP_*`-Werte und verwendet ein frisches externes XDG-Konfigurationsverzeichnis. Semgrep 1.175.0 materialisiert den Community-Regelbestand einmal in vier versionsgebundenen Core-Shards; der Wrapper validiert und kanonisiert exakt 1.074 eindeutige Definitionen, pinnt ihren vollständigen Definitionshash `b6e589b3bdcdf6eb2086765c0cdb3b128bda6d9b26e42cd36852e093cd1d601e` sowie das 2.192.939-Byte-Einzelbundle `76b5a021560070925e9b86f93d2e61153b72ab6a7e306c0d49e1677bb07cbce5` und scannt Phase 2 ausschließlich offline gegen dieses Bundle. Der bereinigte Auto-Scan und der Offline-Bundlescan lieferten identisch 342 Rule-IDs (`90e5e07621bf32da358a4f056b15c1a14f48b8929a6a03099108fd5b12c198f6`), dieselben 20 allowgelisteten Testmatches, die exakte Targetmenge und 0 Errors/Skipped-Rules/Fixpoint-Timeouts. Die interne, an Semgrep 1.175.0 gebundene Dump-Schnittstelle bleibt eine bewusst dokumentierte Wartungsgrenze; jede Schema- oder Inhaltsdrift blockiert das Gate statt still den Regelsatz zu ändern.

### MW220-093 bis -096: Tool-, Git- und Pythonumgebung dürfen den Scan nicht umdefinieren

Der Red-Team-Reaudit behandelte nicht nur Semgrep-Konfiguration, sondern auch seine vorgelagerten Autoritäten. Ein alternativer `GIT_INDEX_FILE` zusammen mit `GIT_CONFIG_*`/`core.excludesFile` konnte bei weiterhin korrektem `rev-parse --show-toplevel` Dateien aus `git ls-files --cached --others --exclude-standard` entfernen. Ebenso authentisierte ein absoluter Semgrep-Launcher weder die importierten Pythonmodule noch eine gelockte Projektumgebung: `PYTHONHOME`/`PYTHONPATH` konnten Module umlenken und `sys.prefix == sys.base_prefix` ließ ein global installiertes Semgrep passieren. Schließlich war die erste Security-Gruppe ausschließlich für Python 3.13 markiert, während das Produkt CPython 3.12–3.14 unterstützt.

Der finale Vertrag entfernt case-insensitiv alle `GIT_*`, `PYTHON*`, `SEMGREP_*` und `UV_*` aus den jeweiligen Kindumgebungen, startet den Wrapper mit `python -I`, deaktiviert User-Site und unsichere Suchpfade und verlangt eine aktive virtuelle Umgebung, deren aufgelöster Prefix exakt `<repository>/.venv` entspricht. Das Semgrep-Executable muss eine reguläre Datei unmittelbar unter dem plattformspezifischen `Scripts`-/`bin`-Verzeichnis dieser Umgebung sein und wird über den Lauf hinweg identitätsgeprüft. `semgrep==1.175.0` ist unmarkiert in der Security-Gruppe und im universellen Lock für 3.12–3.14 enthalten.

### MW220-097 bis -101: Policy-, Kontext- und Credentialgrenzen müssen reproduzierbar mitgeführt werden

Der Artefakt- und Dokumentreaudit ergänzte `.semgrepignore` byteidentisch neben dem Wrapper im Sdist und vereinheitlichte README und CI auf den minimalen gelockten Security-only-Sync. Die 20 Finding-Signaturen binden nun zusätzlich den gesamten LF-kanonischen Inhalt jeder der zehn betroffenen Testdateien; eine unveränderte `exec`-/Importzeile bei geändertem Input- oder Datenflusskontext ist damit kein still erlaubtes False Positive mehr. Die Remote-Phase isoliert HOME, USERPROFILE, APPDATA, XDG- und Settingspfade, entfernt `NETRC` sowie alle auth-/toolrelevanten Variablen und legt `TMPDIR`, `TEMP` und `TMP` auf dasselbe frisch erzeugte, link-/reparsegeprüfte externe Tempverzeichnis.

### MW220-102 bis -104: Frozen Releaseverträge brauchen exakte Regressionen

Die ersten statischen Tests prüften Security-Workflowkommandos per Substring, Sdist-Member per Suffix und den Lock nur teilweise. Ein `echo` plus nachgeschalteter anderer Befehl, ein allgemeines `uvx`, ein verschachtelter Ersatzpfad oder eine gelöste Root-/Lockbindung hätte den Test bestehen können, obwohl der aktuelle reale Workflow korrekt war. Die Regressionen verlangen jetzt die exakt geordnete zweizeilige Security-`run:`-Liste, verbieten jedes `uvx`-Token, akzeptieren genau einen kanonischen Sdistroot mit exakten Wrapper-/Policypfaden und binden unmarkierte Rootgruppe, Lock-Metadaten, Semgrep 1.175.0, Registry sowie SHA-256-belegte Sdist-/Wheel-Einträge.

Der fokussierte Abschluss nach MW220-090 bis -104 bestand mit 74 Semgrep-/Supply-Chain-Tests; einschließlich Versionsmetadaten waren 76 Tests grün. Der nach MW220-105 wiederholte kanonische Security-only-Lauf auf dem `2.21.0`-Arbeitsbaum bestand mit 218 Manifestdateien (`246c60513172d789d2aa4aa5e780f5428af42579e91329adcb1fe2cbc6106cac`), 168 exakten Targets (`d54286198b9fca7419b0db6728cd5a48e67269d5f8cf9c8f2fdda1e163a92f8e`), 49 Policy-Skips, 1.074 Definitionen, 342 angewandten Rule-IDs, exakt 20/20 allowgelisteten Findings (`00a9bf8136145e5c2ccfb2db6d0c7e8ea29679fcda85907fe5c418566865af52`) und jeweils 0 unerwarteten Findings, Errors, `skipped_rules` oder Fixpoint-Timeouts.

### MW220-105: Ein Ready-Pfad ist noch kein veröffentlichter PID-Wert

Der reale Cross-Process-Locktest wartete nur auf `Path.is_file()` und las anschließend unmittelbar `int(read_text())`. Das Kind hatte die Zieldatei zu diesem Zeitpunkt bereits angelegt, aber seinen PID-Inhalt noch nicht vollständig veröffentlicht; der Elternprozess konnte deshalb reproduzierbar eine leere Zeichenfolge lesen. Beide Holder publizieren den PID nun in eine laufbezogen eindeutige Tempdatei und ersetzen den Ready-Pfad atomar. Der Parent wartet zusätzlich auf einen syntaktisch gültigen positiven PID und toleriert transiente Read-/Parsefehler bis zur Deadline. Beide Prozessfälle sowie 50 Wiederholungen des ursprünglichen Rennens bestanden. Dies korrigiert ausschließlich die Releasegate-Synchronisation und ändert keine Produktsemantik.

### MW220-106: Git-Checkoutbytes müssen plattformunabhängig sein

Der finale Diff-Reaudit fand keine `.gitattributes`, während die wirksame globale Konfiguration `core.autocrlf=true` war. Vier geänderte Dateien enthielten dadurch gleichzeitig LF und CRLF; besonders `.semgrepignore` wird byteidentisch in den Sdist übernommen und geprüft. Derselbe Commit konnte somit unter Windows und Linux unterschiedliche Policy-/Archivbytes erzeugen. Die neue exakte Policy `* text=auto eol=lf` normalisiert alle erkannten Textdateien und lässt Binärdateien unter `text=auto` unangetastet. Alle 130 Kandidatentextdateien wurden byteweise geprüft, die 20 betroffenen CRLF-/Mischdateien auf LF normalisiert und der Vertrag in `test_release_supply_chain.py` eingefroren. Ein frischer Checkout des integrierten Commits und dessen Doppelbuild bleiben der abschließende Artefaktbeweis.

### MW220-107: Releaseevidenz braucht reproduzierbare Hashprovenienz und eindeutige Snapshots

Der dokumentierte Dependency-Exportbefehl ohne `--output-file` erzeugt 7.488 stdout-Bytes in 354 Zeilen und SHA-256 `f4321c233185f561bdfcaabcf149f8bb5cf6a3c81534847eb56eb1208154f219`. Der zuvor genannte Digest `2b3920e6630733987e996c47c23457bc6713c033bc21d35a62d5452ff129cbf2` gehört dagegen zu einem 7.582-Byte-Artefakt, dessen uv-Header den absoluten externen `--output-file`-Pfad enthält. Die 7.345 Dependency-Body-Bytes sind identisch und besitzen den pfadunabhängigen SHA-256 `7deef5fd17ec5e7aa60cb18c6be87e3d1a8478af3d7e1262d0bb2155bbd1fdd6`; `pip-audit` meldet weiterhin keine bekannte Advisory. Die Tabellen nennen deshalb künftig stdout- und Body-Digest statt eines nicht reproduzierbar beschriebenen Pfadhashs. Gleichzeitig wurden veraltete Coverage-/Finalgate- und Artefaktformulierungen in klar benannte Arbeitsbaum-, Post-Finding- und integrierte-Commit-Snapshots getrennt.

### MW220-108: Maschinen-gelesener Projektzustand darf keinen alten Release steuern

`CLAUDE.md` definiert `.sprint/state.md` als zentrales Steuerungsdokument mehrerer Hooks. Dieses Frontmatter erwartete noch `feature/v2.20.0-wrk002-qualified`; das als Überblick bezeichnete `MEMORY.md` und die ausdrücklich LIVE genannte Serena-State-Datei meldeten v2.14 bis v2.20, während `project_overview.md` sogar v2.17 als live bezeichnete. Ein erster Präfixfix war unvollständig: `current_sprint` verletzte weiterhin den numerischen Hookvertrag, `sprint_backlog_written` behauptete ohne passenden Backlog `true`, gleichrangige Überschriften beendeten das vermeintliche Archiv und aktive Abschnitte beschrieben noch selektive Covering-Tests, `no tests`, Semgrep Pro, Entwicklungspause sowie die falsche Reihenfolge Merge vor Versionsbump. Sprint 38 besitzt nun einen realen Backlog; explizite LIVE-/ARCHIVE-Grenzen, vollständige aktuelle Laufzeitverträge und ein gemeinsamer maschinenlesbarer Releasefolge-Marker ersetzen die magischen Präfixe. Die Regression parst alle elf Frontmatterfelder, prüft Booltypen, Branch, Backlogexistenz, aktive Versions-/Branch-Eindeutigkeit, Archivgrenzen, reale Roadmappfade und verbotene Altverträge. Die zusätzlich aktiven Serena-Command-/Completion-Dokumente tragen nun ebenfalls v2.21.0, den fehlerfreien mypy-Vertrag und die korrekte Releasefolge. Offene Gateflags bleiben bis zum tatsächlichen Abschluss ehrlich `false`.

### MW220-109: Doppelte Installationsautorität darf nicht auseinanderlaufen

Die Git-Historie belegt, dass `_config/mutmut-win-install.md` als führende Anleitung und `_docs/installation/mutmut-win-install.md` als gepflegte Dokumentationskopie bewusst gemeinsam angelegt wurden. Nur die führende Kopie war später auf v2.21.0, Profile und den `@staticmethod`-Vertrag aktualisiert worden; die andere wies Nutzer weiterhin zur Installation von v2.14.0 an. Beide Dateien sind nun UTF-8/LF und byteidentisch. Eine Regression leitet die Version aus `pyproject.toml` ab und bindet Dokumentversion, Git-Tag, erwartete CLI-Ausgabe sowie exakte Bytegleichheit.

### MW220-110: Ein eigenständiger Acceptance-Harness braucht eine konsistente Lockbasis

Der ausdrücklich eigenständige Harness unter `_docs/nextgen_roadmap/acceptance_harness` deklarierte in `pyproject.toml` v2.20.0, während `uv.lock` Paket, Gitquelle und Rootmetadaten weiterhin auf v2.14.0 banden; `uv lock --check` endete deshalb 1. Die Dokumentation kennzeichnet v2.14.0 nun als ursprüngliche historische Basis und v2.20.0 ausdrücklich als letzte veröffentlichte Operator-Verhaltensbasis vor dem v2.21-Hardening. Der Lock wurde reproduzierbar auf Tag `v2.20.0` und den vollständigen Commit `db71e53e637114ebf893b8fb98f0a21de5998440` aktualisiert. Auch der Roadmap-Link, die Profilaufrufe und die bereits implementierten Pragma-/`do_not_mutate_patterns`-Backports sind wieder wahr. Die Regression bindet deklarierte Quelldaten, gelockte Paketversion, exakte Commitquelle, Rootmetadaten, Provenienz und diese semantischen Dokumentationsclaims; der zusätzliche Offline-`uv lock --check` ist grün.

### MW220-111: Ausführbare Entwickler-Governance darf keinen alternativen Security-PASS erzeugen

Der abschließende Claim-Reaudit fand außerhalb des bereits gehärteten CI-Pfads eine zweite ausführbare Autorität: `verify-after-agent.sh` und beide Pre-commit-Kopien scannten nur geänderte beziehungsweise gestagte Dateien mit einem direkten, registryabhängigen Semgrep-Aufruf. Fehlendes Semgrep wurde im Pre-commit-Pfad still akzeptiert; der Subagent-Hook konnte anschließend `VERIFICATION PASSED` ausgeben. `CLAUDE.md`, PostCompact-Reminder, Hook-Allowlist, Sprint-Gate, Serena-Kommandos sowie aktive DoD-/Designvorgaben hielten denselben verworfenen Pfad am Leben. Damit konnten die unter MW220-090 bis -104 geschlossenen Login-, Registry-, Timeout-, Scope- und Exitcode-Grenzen praktisch umgangen werden.

Alle drei Executor-Hooks rufen nun ausschließlich `uv run --no-sync python -I scripts/semgrep_release_gate.py` auf dem vollständigen Git-owned Release-Scope auf; fehlendes `uv`, fehlender Wrapper oder ein Gatefehler erzeugen zwingend FAILED. Die Pre-commit-Spiegel sind byteidentisch und vollständig LF-normalisiert. Settings gewähren keinen direkten Semgrep-Aufruf mehr und geben dem zweiphasigen Wrapper 600 Sekunden; Sprint- und PostCompact-Hooks können keinen historischen Commitmessage- oder Teilscanbeleg mehr in PASS-Autorität umdeuten. Aktive Entwicklerdokumente binden CPython `>=3.12,<3.15`, mutmut-win v2.21.0, Semgrep 1.175.0 und die kanonische Sequenz aus Security-only-Sync plus Wrapper. Der Wrapper materialisiert Regeln isoliert und führt danach den contentgeprüften Bundlescan offline aus; nur dieser Gesamtprozess besitzt Gate-Autorität. Die Regression `test_active_governance_uses_only_the_canonical_semgrep_release_gate` bindet exakte Hookpayloads, Spiegelbytes, Timeout, Allowlist, State-Nachweis, Versions-/Toolpins und verbietet die drei alten Raw-/Teilscan-Tokens. Der fokussierte Cluster besteht mit 11/11 Tests; alle fünf geänderten Shell-Hooks bestehen `bash -n`. Der finale kanonische Lauf auf dem eingefrorenen Post-MW220-111-Scope bestand mit 218 Manifestdateien (`45e0e74e02ef8d9fb9de4dd0a31455095890ce3d6c9ad7c11d3c5640e23a029c`), 168 Targets (`d54286198b9fca7419b0db6728cd5a48e67269d5f8cf9c8f2fdda1e163a92f8e`), 49 Policy-Skips, 1.074 Definitionen, 342 Regeln und exakt 20/20 allowgelisteten Testtreffern; unerwartete Findings, Errors, `skipped_rules` und Fixpoint-Timeouts blieben jeweils null.

### MW220-112 bis -115: Remote-Matrix und Report-Vertrag müssen Plattform- und Statusdrift sichtbar machen

Die zuvor wegen eines Billing-Problems als nicht verfügbar eingeplante GitHub-CI lief für PR #134 und anschließend für den Mergecommit tatsächlich an. Sie ist kein PASS, sondern lieferte drei neue, unabhängige Releaseblocker. Der Quality-Job `99647140872` reproduzierte mit `mypy --platform linux --no-incremental src/ scripts/` 49 Typfehler in sechs POSIX-/Prozessmodulen (MW220-112). Das lokale Windows-Gate hatte nur die Windows-Plattformzweige bewiesen und durfte deshalb nicht als plattformweiter Typnachweis gelten.

Der Ubuntu-Pytest-8.2-Boundary-Job `99647141304` meldete in `test_same_byte_config_replacement_is_identity_drift` und `test_external_test_file_same_byte_replacement_is_rejected` jeweils DID NOT RAISE; 40 angrenzende Fälle bestanden und 5 waren plattformspezifisch übersprungen. Der Reaudit widerlegte jedoch einen Produktions-TOCTOU: Linux OverlayFS verwendete nach unmittelbarem Unlink/Recreate dieselbe Geräte-/Inodeidentität und sogar dieselben beobachteten Zeitwerte wieder. Der Test hatte damit keinen identifizierbaren Austausch erzeugt. Ein Hardlink-Anker hält nun die alte Dateiidentität bis nach dem Ersatz belegt und erzwingt die beabsichtigte Negativgrenze. Der fokussierte Cluster bestand danach im Linux-CI-Container mit 42 Tests und 5 Skips sowie unter Windows mit 45 Tests und 2 Skips (MW220-113, P1).

Der kanonische Security-Job bestand auf Ubuntu, scheiterte unter Windows im Job `99647141196` jedoch fail-closed an nicht leeren `time.fixpoint_timeouts` (MW220-114). Das ist kein zulässiger Flake und kein Grund, das Gate abzuschwächen. Der reine Vier-Shard-Regelbootstrap bleibt parallel; der eigentliche vollständige Bundlescan läuft nun deterministisch mit `--jobs 1`. Target-, Regel-, Finding-, Returncode-, TOCTOU- und Timeoutverträge bleiben unverändert fail-closed, und eine nicht leere Timeoutliste meldet zusätzlich die kanonisch escapete Diagnose. Der fokussierte Wrappercluster bestand mit 70/70 Tests. Vier gleichzeitig ausgeführte lokale Wiederholungen des unveränderten Vorfixbaums bestanden ebenfalls; zusammen mit dem reproduzierbaren Remote-Fehler belegt das eine runner- und lastabhängige Nichtdeterministik, keine Entwarnung. Der reparierte reale Wrapper bestand anschließend viermal hintereinander unter Windows mit identischem Scope und ohne Fixpoint-Timeout.

Der letzte unabhängige Report-Reaudit fand danach eine weitere P2-Lücke: Der maschinen-gelesene Live-State-Test verlangte zwar `MW220-112`, prüfte das obere Ende aber nur über den beliebigen Teilstring `114` und las Analyse sowie Roadmap überhaupt nicht. Damit konnten MW220-113 fehlen und widersprüchliche Aussagen zu implementierten Fixes, Remote-Ausnahme oder Finalgates unbemerkt bleiben. MW220-115 ersetzt den schwachen Teilstring durch exakte IDs, bindet die vollständige 115er Zählung und verbietet die konkret gefundenen stale Claims.

PR #134 ist als Mergecommit `55d25dfff2225ffb3e4a2b56ead4a3c190d054cf` mit Tree `761e264a91a52bda4c284f3f36fe53954d7fff2b` integriert. Alle zuvor daraus erzeugten Artefakte wurden durch den danach begonnenen Fixzweig `fix/v2.21.0-release-blockers` als Releaseevidenz ungültig. Ein vorzeitig erzeugter Tag `v2.21.0` wurde vor jeder GitHub-Releasepublikation entfernt. Die vier zusätzlichen Fixes und die vollständige lokale Cross-Platform-Matrix sind belegt; Follow-up-Integration, integrierter Doppelbuild, annotierter Tag und GitHub-Release bleiben offen. Eine Billing-bedingt nicht verfügbare weitere Remote-CI bleibt die ausdrücklich akzeptierte Evidenzlücke und ist kein PASS.

## 17. Umsetzungsstand der dritten Welle und der finalen Reaudits

| ID | Status | Produktions- und Regressionsevidenz |
|---|---|---|
| MW220-050 | implementiert; lokales Gesamtfinalgate grün | `process/run_lock.py`, `orchestrator.py`, `cli.py`; `test_run_lock.py`, `test_run_lock_processes.py`, `test_run_surface_integration_220.py` |
| MW220-051 | implementiert; lokales Gesamtfinalgate grün | CI-Export ohne Legacy-Autorität und mit Live-Basis; `test_cicd_export_requires_live_source_test_and_config_basis`, `test_modern_completed_run_without_basis_cannot_authorize_cicd_export` |
| MW220-052 | implementiert; lokales Gesamtfinalgate grün | stabiler Basis-Doppelsnapshot plus Pre-Completion-Revalidierung; `test_initial_run_basis_must_be_a_stable_snapshot`, `test_mid_run_source_drift_is_recorded_failed_not_completed` |
| MW220-053 | implementiert; lokales Gesamtfinalgate grün | CLI-Konfigurationsreihenfolge; `test_since_commit_uses_effective_custom_tests_dir_before_filtering` |
| MW220-054 | implementiert; lokales Gesamtfinalgate grün | `atomic_file.py`, `models.py`, `mutant_diff.py`; `test_atomic_write_safety_220.py` |
| MW220-055 | implementiert; lokales Gesamtfinalgate grün | namespace-sichere Runner-/Stats-Sidecars; `test_runner_sidecar_safety.py` |
| MW220-056 | implementiert; lokales Gesamtfinalgate grün | `generated_hash` bindet Meta an Ausgabebytes; erste drei Regressionen in `test_staging_authority_p1_220.py` |
| MW220-057 | implementiert; lokales Gesamtfinalgate grün | descriptorgebundene `_copy_with_retry()`-Publikation; `test_atomic_staging_copy_detects_close_substitute_without_external_write` |
| MW220-058 | implementiert; lokales Gesamtfinalgate grün | `browser.py`, `cli.py`; `test_browser_evidence_invalidation_220.py`, `test_results_marks_invalidated_evidence_not_release_ready` |
| MW220-059 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | `db.py` exklusive Voranlage sowie Connect-/Sidecar-/Exit-/Pre-Return-Identitätsprüfungen; Hardlink-/Swap-Regressionen einschließlich `test_load_current_run_rejects_permanent_path_swap_after_final_query` |
| MW220-060 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | `db.py` domänenspezifische Korruptionsgrenze, Completed-Invarianten, `plan_digest`, Ordinal-, High-Water- und Orphanprüfung; Planmanipulations-/Header-Rollback-/stale-Artifact-Regressionen in `test_db_state_boundary_220.py` |
| MW220-061 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | `atomic_spawn.py`; `test_atomic_spawn.py`, Windows-Hard-Exit-Test in `test_pool_shutdown.py` |
| MW220-062 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | seekbarer Windows-Bootstrap in `suspended_spawn.py`; `test_wedged_sitecustomize_large_payload_is_contained_and_nonblocking` |
| MW220-063 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | Runtime-/Resume-Fail-Closed; `test_suspended_spawn.py`, `test_process_worker.py` |
| MW220-064 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | POSIX-Session vor Interpreterstart; `posix_spawn.py`, `test_generation_supervisor.py` |
| MW220-065 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | executorbesessene pytest-PGID; `test_worker_sigkill_reaps_registered_pytest_session` |
| MW220-066 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | EOF-sicheres Pre-exec-Pipe-Gate mit synchroner Worker-/PGID-Publikation; realer WSL-SIGKILL-Test in `test_pool_shutdown.py` |
| MW220-067 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | unabhängige Executor- und Typechecker-Cleanup-Stufen; `test_cleanup_failures_do_not_skip_later_resources_or_escape`, `test_job_close_failure_does_not_skip_fallback_kill_or_mask_timeout` |
| MW220-068 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | eigener DONE-Join; `test_generation_supervisor_teardown.py` |
| MW220-069 | implementiert, fokussiert verifiziert; Remote-CI ausgeführt, Gesamtmatrix blockiert | `requires-python`-/CPython-Vertrag und `test_python_metadata_matches_fail_closed_runtime_support` |
| MW220-070 | implementiert und durch reale Remote-Matrix wirksam belegt; Gesamtmatrix wegen MW220-112 bis -114 kein PASS | Windows-/Ubuntu- und CPython-3.12–3.14-Matrix, echte `uv lock --check`-Driftprüfung und matrixweites Audit; `test_ci_covers_supported_matrix_and_separate_release_gates` |
| MW220-071 | statisch und in einzelnen Remote-Build-/Smokepfaden belegt; Gesamtmatrix blockiert, Vorfix-Artefakte ungültig | SHA-gepinnte Actions, gelockter reproduzierbarer Offline-Build und installierte Wheel-/Sdist-Smokes; `test_ci_uses_only_full_sha_pinned_allowlisted_actions` |
| MW220-072 | implementiert, fokussiert und auf dem MW220-105-Artefaktsnapshot verifiziert; integrierter Rebuild ausstehend | vollständiger PSF-2.0-Text, Notice/Änderungszusammenfassung und Composite-Metadaten; `LICENSE`, `pyproject.toml`, `test_release_supply_chain.py` |
| MW220-073 | implementiert und unabhängig fokussiert reauditiert; lokales Gesamtfinalgate grün | typisierte Vollständigkeit der Dependency-/Environment-/Import-/Runtimebasis, Reuse-Sperre und CI-Ablehnung bei unvollständiger Evidenz; `stats.py`, `orchestrator.py`, `cli.py`, `test_dependency_basis_220.py` |
| MW220-074 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | restliche Stats-/CI-/Plugin-/Guard-/Proof-/Argfile-/Run-Lock-Publisher auf `atomic_file.py` migriert; geschlossenes Writer-Inventar und Parent-Swap-Regressionen |
| MW220-075 | implementiert, fokussiert verifiziert; lokales Gesamtfinalgate grün | Linux-`PR_SET_PDEATHSIG` plus Parent-PID-Racecheck am privaten Child-Entry und EOF-/`killpg`-Fallback; reale Hard-Parent-Kind-/Baumtests |
| MW220-076 | implementiert und unabhängig fokussiert reauditiert; lokales Gesamtfinalgate grün | generisches `type_check_command` erzwingt typisierte Basisunvollständigkeit, sperrt Reuse/Score-/CI-Autorität; `stats.py`, `orchestrator.py`, `test_dependency_basis_220.py` |
| MW220-077 | implementiert und durch zwei unabhängige Red-Team-Reaudits verifiziert; Ubuntu-CI deckte mit MW220-113 zwei nicht portable Same-byte-Identity-Regressionen auf, keine Produktions- oder POSIX-Identitätslücke | pytest-Boundary Schema v2, Root-/Config-/Target-Identitäten, option-safe Argfile, früher Conftest-Guard, Worker-/Executor-Fatalität, pytest-8.2/9-Realprozesse; `pytest_boundary.py`, `runner.py`, `process/executor.py`, `process/worker.py`, Boundary-/Surface-Regressionen |
| MW220-078 | implementiert und fokussiert verifiziert; lokales Gesamtfinalgate grün | zentrale Erkennung historischer generischer-Checker-Runs und explizites `release-ready: no` in CLI/Browser; `db.py`, `cli.py`, `browser.py`, Anzeige-Regressionen |
| MW220-079 | implementiert und Workflow-Reaudit grün; Remote-CI tatsächlich ausgeführt | getrennte `SOURCE_DATE_EPOCH`-Zuweisung/Export; actionlint mit ShellCheck/Pyflakes sowie Zizmor ohne Findings |
| MW220-080 | geschlossen und vollständiges Zeicheninventar grün | einziges U+00AD entfernt; Git-owned Unicode-/Bidi-/NUL-/Control-/Merge-Marker-Reaudit ohne Funde |
| MW220-081 | implementiert und fokussiert sowie im vollständigen Post-MW220-104-Coverage-Lauf verifiziert | weiterhin begrenztes 300-Sekunden-E2E-Budget; beide vorherigen Timeout-Aufrufer grün; 1.994 Tests / 44 Skips / 85 % vor den reinen Test-/Dokument-/EOL-Nachschärfungen |
| MW220-082 | implementiert, deterministisch und im realen Dogfood-Workload verifiziert | content-verifiziertes idempotentes Guard-Ensure, fataler Boundarytransport und Pending-/Abort-Semantik; Fünf-Publisher-, Worker-, Orchestrator- und reale Vier-Worker-Regressionsbelege |
| MW220-083 | implementiert und durch Mutanten-Diff sowie Realpilot verifiziert | exakte Path-/Freshness-/Exit-/Mapping-/Diagnostiktests; 86/90 killed, vier Äquivalente, 0 suspicious, 95,6 % |
| MW220-084 | implementiert und mit realer Dogfood-DB verifiziert | vollständige Current-Snapshot-Mockgrenze; isolierte Regression und komplette Surface-Suite grün |
| MW220-085 | implementiert und in einer wirklich frischen externen Umgebung sowie Remote-Buildjobs verifiziert | fest gepinnte `hatchling`-/`editables`-Buildgruppe, expliziter Bootstrap vor jedem CI-`--no-build-isolation`-Sync und statischer Reihenfolgevertrag in `test_release_supply_chain.py` |
| MW220-086 | implementiert und gegen die reale Dogfood-DB fokussiert verifiziert | 22 alte Legacy-Reader-Mocks auf Snapshot-/Command-Seams migriert, drei Export-Workspaces isoliert; 31/31 betroffene CLI-/Exporttests grün |
| MW220-087 | implementiert und unter OEM-/UTF-8-Codepages sowie striktem Warnungsgate verifiziert | sieben `mklink`-Aufrufer mit `/u` und explizitem UTF-16LE; 13/13 Junction-Varianten grün, keine Readerthread-Warnung |
| MW220-088 | implementiert und gegen die echten Basisdriftverträge abgegrenzt | stabile Basisfixture ausschließlich im fachlichen Orchestrator-Unit-Modul; 59/59 Unit- und reale Stable-/Mid-Run-Drifttests grün |
| MW220-089 | implementiert und vollständig über gemeinsame Skipmenge regressionstestgedeckt | `WORKSPACE_EXCLUDED_DIR_NAMES` für Staging und Run-Basis; parametrisierter Toolstate-Drift bleibt digestneutral, echte Projektbytes bleiben gebunden |
| MW220-090 | implementiert, fokussiert und im realen Gate verifiziert | getrackter fail-closed Semgrep-Wrapper, externer Git-owned Mirror, exakte Target-/Skip-/Rule-/TOCTOU-Verträge; Workflow-/Sdist-/Unit-Regressionsintegration |
| MW220-091 | implementiert, fokussiert und mit realen 20/20 Findings verifiziert | zwingendes `--disable-nosem`; Rule-/Path-/Span-/Lines-/Full-file-Digest-Signaturen, `extra.is_ignored` exakt abwesend |
| MW220-092 | implementiert und im auth-neutralen Offline-Bundlescan verifiziert | isolierte Settings/XDG-Grenze, 1.074 contentgepinnte Community-Definitionen, Offline-Scan mit 342 Rule-IDs |
| MW220-093 | implementiert und hostile-environment-regressionstestgedeckt | vollständiges case-insensitives `GIT_*`-Stripping verhindert alternative Index-/Config-Autorität |
| MW220-094 | implementiert und regressionstestgedeckt | `python -I`, bereinigte `PYTHON*`-Umgebung, User-Site-/Safe-Path-Vertrag |
| MW220-095 | implementiert und Lockprüfung grün | unmarkiertes `semgrep==1.175.0` für CPython 3.12–3.14; 115 gelockte Pakete |
| MW220-096 | implementiert und Toolboundary-Reaudit grün | aktive exakte Repository-`.venv`, unmittelbares `Scripts`-/`bin`-Executable und Identitätsprüfung |
| MW220-097 | implementiert und im real gebauten Sdist fokussiert verifiziert | Wrapper und `.semgrepignore` unter kanonischem Sdistroot byteidentisch |
| MW220-098 | implementiert und statisch verifiziert | README/CI: identischer Security-only-Sync plus `uv run --no-sync python -I ...` |
| MW220-099 | implementiert und Kontextdriftregression grün | LF-kanonischer Full-file-SHA für jede Finding-Signatur zusätzlich zum Matchzeilenhash |
| MW220-100 | implementiert und mixed-case Regression grün | geerbtes `NETRC` entfernt; isolierte Settings-/Homegrenzen |
| MW220-101 | implementiert und POSIX-/Windows-Environmentvertrag grün | `TMPDIR`, `TEMP` und `TMP` auf geprüftes externes Tempverzeichnis gebunden |
| MW220-102 | implementiert und statisch verifiziert | exakte Security-`run:`-Liste/-Reihenfolge und allgemeines Workflow-`uvx`-Verbot |
| MW220-103 | implementiert und im Sdist-Test verifiziert | genau ein kanonischer Archivroot; exakte Lizenz-/Wrapper-/Policypfade |
| MW220-104 | implementiert und Lockprüfung grün | Rootgruppe, Lock-Metadaten, Semgrep-Version/Registry und Distributionshash-Verträge |
| MW220-105 | implementiert und 50-fach stressverifiziert | atomarer Ready-PID-Handshake in `test_run_lock_processes.py`; beide realen Cross-Process-Fälle grün |
| MW220-106 | implementiert und statisch fokussiert verifiziert | `.gitattributes` mit LF-Policy, 130 Kandidatentextdateien inventarisiert/normalisiert; `test_git_checkout_normalizes_text_bytes_for_cross_platform_artifacts` |
| MW220-107 | implementiert und byteforensisch verifiziert | kanonischer stdout-Digest und pfadunabhängiger Dependency-Body-Digest; stale Snapshotformulierungen korrigiert |
| MW220-108 | implementiert und statisch fokussiert verifiziert | v2.21-Frontmatter/Live-State in `.sprint`, `MEMORY.md` und Serena; `test_live_repository_state_documents_match_release_version` |
| MW220-109 | implementiert und bytegenau verifiziert | beide Installationsanleitungen LF-normalisiert byteidentisch auf v2.21.0; `test_install_guides_are_byte_identical_and_pin_the_release_version` |
| MW220-110 | implementiert und mit statischem plus realem Lockgate verifiziert | Harness-Projekt/Lock/Provenienz konsistent auf der v2.20.0-Verhaltensbasis; `test_acceptance_harness_lock_matches_its_declared_release_baseline`, Offline-`uv lock --check` |
| MW220-111 | implementiert und ausführbar plus statisch verifiziert | drei Semgrep-Executor-Hooks fail-closed auf den kanonischen Vollscope-Wrapper gebunden; aktive Governance synchronisiert; 11/11 Release-Supply-Chain-Tests und `bash -n` grün |
| MW220-112 | implementiert und im lokalen Gesamtfinalgate unter beiden Plattformansichten verifiziert | plattformsichere Win32-Deklarationen und eng begrenzte Gegenplattform-Suppressions in sechs Prozessmodulen; native Windows- und `--platform linux --no-incremental`-Mypy-Läufe jeweils 38 Dateien/0 Fehler; Prozessmatrix 80 bestanden/10 übersprungen; vollständige Suite grün |
| MW220-113 | als Testportabilitätsfehler implementiert und im lokalen Gesamtfinalgate Linux/Windows-verifiziert | Hardlink-Anker in zwei Same-byte-Identity-Regressionen; Linux 42 bestanden/5 übersprungen, Windows 45 bestanden/2 übersprungen; kein Produktions-TOCTOU; vollständige Suite grün |
| MW220-114 | implementiert und in wiederholten realen Windows-Finalgates verifiziert | serieller vollständiger Bundlescan (`--jobs 1`) bei unverändertem Vier-Shard-Bootstrap; Timeoutliste bleibt fatal, Evidence wird aus den echten Command-Buildern abgeleitet; 70 Wrappertests und wiederholte reale Windows-Läufe grün |
| MW220-115 | implementiert und vollständig regressionstestverifiziert | exakte Follow-up-ID-Prüfung in allen LIVE-State-Kopien und eigener Analyse-/Roadmap-Vertrag gegen Anzahl-, Adjudikations-, Status- und Remote-Ausnahmedrift; 12 fokussierte Supply-Chain-Tests und vollständige Suite mit 2.002 Tests / 44 Skips grün |

## 18. Aktueller Freigabestatus

Die Befunde MW220-001 bis -111 besitzen gezielte Regressionen oder deterministische Byte-/Prozessbelege. Ihre frühere Post-MW220-111-Matrix mit 2.000 Tests, 44 Skips, 85 % Coverage, stabilem `.venv`, Dogfood, Semgrep und Doppelbuild bleibt historische Ursachen-/Regressionsevidenz, aber keine Artefaktautorität für den reparierten Baum. Auf `fix/v2.21.0-release-blockers` bestand die vollständige strikte Suite nach MW220-115 mit 2.002 Tests und 44 Skips; `.venv` blieb vor und nach dem Lauf exakt bei 5.119 Dateien, 126.091.419 Bytes und SHA-256 `8e5a29550f9f8a61811a63687c90c31aa962ddc8e8ab0f34af34334da9553268`. Der vollständige Coverage-Lauf vor dem reinen Report-Test MW220-115 bestand mit 2.001/44 und 85 % bei 8.524 Statements / 1.275 Missing. Ruff, Format, native Windows- und Linux-Plattform-mypy, Import-Linter, Lockprüfung, vollständiger Dependency-Audit und `git diff --check` sind grün. Gitleaks fand weder in 280 Commits noch im exakten 409-Dateien-Git-owned Worktree ein Secret. Der reparierte Dogfood-Lauf bestand mit 86/90 killed, vier äquivalenten Survivors, keinen problematischen Buckets und 95,6 %. Der reale kanonische Windows-Semgrep-Wrapper bestand wiederholt. Der letzte exakte Kandidatenlauf inventarisierte 218 Manifestdateien (SHA-256 `2915abda1e40304ac05145115cdf2feede0d8e956a665f049b0d5d7aa8a6dde1`), 49 Policy-Skips und 168 Targets (SHA-256 `d54286198b9fca7419b0db6728cd5a48e67269d5f8cf9c8f2fdda1e163a92f8e`), materialisierte 1.074 Definitionen in vier Bootstrap-Shards und scannte 342 Regeln seriell mit `--jobs 1`; exakt 20 allowgelistete Findings und jeweils null unerwartete Findings, Errors, `skipped_rules` oder Fixpoint-Timeouts. Actionlint/Zizmor konnten im letzten Recheck nicht erneut gestartet werden, weil ihre Binärdateien und Images lokal nicht verfügbar waren; der unveränderte Workflow besitzt weiterhin die frühere grüne Ausführung und statische Supply-Chain-Regressionen. MW220-115 ist durch 12 fokussierte Tests und die vollständige Strict-Suite geschlossen. Der reparierte Baum benötigt noch die Follow-up-Integration und neue Releaseartefakte; jede tatsächlich verfügbare Follow-up-CI wird adjudiziert, eine Billing-bedingt ausbleibende CI bleibt Evidenzlücke und kein PASS.

| Abschlussgate | Status |
|---|---|
| vollständige Testsuite | reparierter Post-MW220-115-Baum: 2.002 bestanden, 44 übersprungen |
| Coverage | reparierter Baum: 2.001 bestanden, 44 übersprungen, 85 %, 8.524 Statements / 1.275 Missing |
| Ruff Check und Format | reparierter Baum ohne Befund; 168 Python-Dateien bereits formatiert |
| mypy und Import Linter | native Windows- und `--platform linux --no-incremental`-Mypy-Läufe jeweils 38 Dateien/0 Fehler; Import-Linter 37 Dateien / 123 Abhängigkeiten / 1 gehaltener Vertrag |
| Lockprüfung und Dependency Audit | `2.21.0`-Lock mit 115 Paketen grün; Pip-Audit 2.10.0 über vollständigen Export ohne bekannte Advisories |
| frischer Build und Artefaktinventar | frühere Kandidatenartefakte Wheel `8a89f0f6…` und Sdist `07a5e869…` durch nachfolgende Fixes ungültig; vollständiger Doppelbuild, Inventar und Laufzeitsmokes auf dem reparierten Follow-up-Commit ausstehend |
| getrackter fail-closed Semgrep-Wrapper | serieller Vollscan implementiert; 70 Wrappertests und wiederholte reale Windows-Läufe grün; letzter exakter Kandidatenlauf: 218 Manifestdateien / 49 Policy-Skips / 168 Targets / 342 Regeln / 20 allowgelistete Findings / 0 Fehler oder Fixpoint-Timeouts |
| E2E-Umgebungsisolation | reparierter Post-MW220-115-Lauf vor/nach exakt identisch: 5.119 Dateien / 126.091.419 Bytes / SHA-256 `8e5a29550f9f8a61811a63687c90c31aa962ddc8e8ab0f34af34334da9553268` |
| dokumentierter Dogfooding-Pilot | reparierter Baum: 90 total, 86 killed, 4 äquivalente Survivors, 0 timeout/suspicious/skipped/no-tests/type-check-caught/segfault/unchecked, 95,6 %, 81,0 s |
| GitHub Issue #133 Consumer-Repro | historischer Snapshot `8296cd9a…`, genau ein `x_verify`-Mutant: completed 1/1, killed nach 1,8833385 s, 0 pending/reused/timeout/suspicious/skipped/no-tests, Orchestrator-Exit 0; Closure über MW220-047 plus #130/360-B3, kein MW220-116 |
| Git-owned Kandidateninventar | 409 Dateien; Gitleaks über Worktree und 280-Commit-Historie ohne Befund; finaler Export-/Buildinventar nach Integration ausstehend |
| Branch-/PR-Publikation | PR #134 integriert als `55d25dfff2225ffb3e4a2b56ead4a3c190d054cf`; Reparaturbranch und Follow-up-PR noch nicht integriert |
| GitHub-CI | tatsächlich ausgeführt; Quality `99647140872`, Ubuntu-Boundary `99647141304` und Windows-Security `99647141196` deckten MW220-112 bis -114 auf; kein PASS |

**Aktuelles technisches Urteil: Release-NO-GO nur noch bis zur Veröffentlichungskette.** 115 Befunde sind bestätigt; MW220-112 bis -115 sind implementiert, und die vollständige lokale Cross-Platform-Matrix ist grün. PR #134 ist zwar als `55d25dfff2225ffb3e4a2b56ead4a3c190d054cf` integriert, seine Artefakte sind durch den nachfolgenden Reparaturbranch nicht mehr releaseautoritativ. `v2.21.0`-Tag und GitHub-Release sind absent; der vorzeitige Tag wurde entfernt. Erst Follow-up-Integration, integrierter Doppelbuild, installierte Artefaktsmokes und erneuter Live-Ref-Check erlauben Tag und Release. Eine Billing-bedingt ausbleibende weitere Remote-CI bleibt akzeptierte Evidenzlücke und kein PASS. Der lokale Legacy-ZIP-Baum ist nicht autoritativ.
