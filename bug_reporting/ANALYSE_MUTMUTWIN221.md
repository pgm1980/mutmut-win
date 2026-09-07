# Adversariales Vier-Augen-Review: mutmut-win v2.21.0 → v2.21.1

**Stand:** 2026-09-07
**Autoritative Basis:** annotiertes Tag `v2.21.0`, Commit
`40b6af31da66f3544ab9d1a38d34511e7e02c79a`, Tree
`9fe800a9849fe35cf87f57b2f098ee02a08cd76a`
**Fixzweig:** `fix/v2.21.1-windows314`
**Verbindlicher Product-Owner-Scope:** Windows und exakt CPython 3.14.7
**Status:** v2.21.1 ist ein unveröffentlichter Arbeitsstand. Ein erster
commit-genauer Kandidatenlauf deckte CX221-063 auf; dessen Korrektur und das
vollständige Windows-/CPython-3.14.7-Finalgate sind erneut offen.

## 1. Executive Verdict

Claudes Bericht ist weder pauschal zu verwerfen noch ungeprüft zu übernehmen.
Die zwei dort als plattformweite P0-Totalausfälle hervorgehobenen Befunde
MW221-001 und MW221-002 sind technisch plausibel beziehungsweise dynamisch
belegt, liegen aber außerhalb des verbindlichen Produktvertrags. Sie begründen
für Windows mit CPython 3.14.7 kein Release-NO-GO. Der frühere Metadaten-, CI-
und Dokumentationsvertrag, der Python 3.12/3.13 sowie POSIX versprach, war
gleichwohl sachlich falsch und wird in v2.21.1 auf das echte Zielsystem verengt.

Auf dem Zielsystem ist v2.21.0 nicht katastrophal, aber auch nicht fehlerfrei.
Der exakte lokale Gesamtlauf unter Windows/CPython 3.14.7 endete mit **3
fehlgeschlagenen, 2.000 bestandenen und 43 übersprungenen Tests in 2.204,60 s**.
Zwei Fehler waren veraltete Python-3.14-Testorakel; der dritte reproduzierte die
Stats-Selbstinvalidierung MW221-007. Daneben wurden insbesondere der
8.3-Pfadalias-False-Positive, die semantische Apply-Korruption, nichtautoritative
Subset-Exporte und mehrere Mutations-/Dateikodierungsgrenzen bestätigt.

Die fünf vom Reviewer nach der Scope-Korrektur als besonders relevant genannten
Punkte werden wie folgt adjudiziert:

| Befund | Urteil für Windows/3.14.7 | Stand im v2.21.1-Arbeitsstand |
|---|---|---|
| MW221-004, 8.3-/Alias-False-Positive | bestätigt | identitätsbasierte Pfadprüfung an Atomic-, DB-, Staging- und pytest-Grenzen implementiert; Finalgate offen |
| MW221-005, Apply-Signaturkorruption | bestätigt | öffentliche Signatur, Defaults, Annotationen, Dekoratoren und Quellkontext bleiben erhalten; Show-Diff bezieht sich wieder auf echte Quelle |
| MW221-007, toter Verdict-Reuse | bestätigt | generiertes `mutants/` bleibt als Pfadeintrag gebunden, seine abgeleiteten Bytes werden nicht rekursiv in den Stats-Digest aufgenommen |
| MW221-008, Vollsuite je Mutant | bestätigte Laufzeitregression; selektive Auslassung oder Intra-Suite-Umsortierung wäre unsicher | Mapping-Hints priorisieren nur Mutanten-Tasks; pytest behält seine native Testreihenfolge und `--maxfail=1` beendet echte Kills früh, während Survivors weiterhin die vollständige Suite durchlaufen |
| MW221-010, Subset-Score-Export | bestätigt | Runs persistieren `is_full_run`; Legacy- und Subset-Runs dürfen keinen Vollrun-CI-Export autorisieren; CLI `results` und Browser kennzeichnen die angezeigte Population ausdrücklich als Subset und als nicht release-ready |

## 2. Provenienz und Releasezustand

Der lokale Tag ist ein annotiertes Tagobjekt
`9ef4baec9a16af4e368f8f4a66ddbf0df064ab3c` und dereferenziert auf den oben
genannten Commit. Der öffentliche GitHub-Release
[`mutmut-win v2.21.0`](https://github.com/pgm1980/mutmut-win/releases/tag/v2.21.0)
wurde am 2026-09-01 um 00:08:11 UTC veröffentlicht. Die im alten Live-State
enthaltene Aussage, Tag und Release seien nicht vorhanden, war daher falsch.
Das bestehende Tag `v2.21.0` ist unveränderliche Releaseprovenienz: Es darf für
den Nachfolger weder verschoben, gelöscht noch auf einen anderen Commit
umgebogen werden. v2.21.1 erhält nach seinen Finalgates ein eigenes annotiertes
Tag.

Die vom Claude-Review berichteten Artefakthashes und Byteinventare wurden in der
vorangegangenen Reviewphase nachvollzogen. Sie beweisen die Provenienz des
publizierten v2.21.0-Wheels/Sdists, aber nicht die Korrektheit des nachfolgenden
v2.21.1-Arbeitsbaums. Für v2.21.1 müssen Doppelbuild, Inventar, Hashes und
Installed-Artifact-Smokes nach dem finalen Commit neu erhoben werden.

## 3. Adjudikation des MW220-Fixclaim-Ledgers

Die gelieferte Datei `MW221_FIXCLAIM_LEDGER.md` enthält die formale MW220-ID-
Menge **exakt und lückenlos von MW220-001 bis MW220-115**; außerhalb dieser
115er-Menge gibt es keinen weiteren MW220-Produktionsbefund. Ihre im Chat
genannte Verteilung war rechnerisch inkonsistent:
72 `VERIFIED_FIXED`, **29** (nicht 30)
`VERIFIED_FIXED_WITH_RESIDUAL_RISK`, 8 `REGRESSED`, 4 `PARTIALLY_FIXED`, 1
`CLAIM_MISFRAMED_OR_NOT_APPLICABLE` und 1
`UNVERIFIABLE_EVIDENCE_GAP` ergeben 115.

Nach Anwendung des verbindlichen Zielscopes lautet die Arbeitsklassifikation:

| Status | Anzahl | Einordnung |
|---|---:|---|
| verifiziert behoben | 75 | auf dem Zielsystem belegte Closure |
| verifiziert mit Restgrenze | 29 | überwiegend dokumentierte oder fail-closed Grenzen |
| regressiert | 4 | MW220-009/-042/-054/-057; im Wesentlichen gemeinsame Windows-Aliasursache |
| teilweise behoben | 3 | MW220-071/-108/-115; Release-/Governancevertrag |
| Claim falsch gerahmt | 1 | MW220-041 |
| für Zielsystem nicht anwendbar | 3 | MW220-064/-065/-075, POSIX-spezifisch |
| Summe | 115 | 104/115 auf dem Zielsystem substanziell verifiziert |

MW220-108 und MW220-115 waren nicht dauerhaft geschlossen: Die LIVE-Dokumente
behaupteten nach der tatsächlichen Veröffentlichung weiterhin, v2.21.0 sei nicht
getaggt oder released. Gleichzeitig verlangte der Governance-Test konkrete
Kandidaten-Prosa und `tests_passed: true`/`housekeeping_done: false`. Eine
ehrliche Statusänderung oder der Sprintabschluss hätte dadurch die Suite rot
gemacht. Diese wiedereröffnete Defektklasse ist MW221-019.

## 4. Scope-korrigierte MW221-Finding-Matrix

Die Statuswerte beschreiben den gegenwärtigen Fixzweig, nicht einen bereits
veröffentlichten Release. `VERIFIED_FIXED` bedeutet, dass Code, gezielte
Regression und das quieszente lokale Kandidatengesamtgate vorliegen; die
integrierte Wiederholung und Veröffentlichung bleiben davon getrennt.

| ID | Prio | Status | Scope-korrigierte Adjudikation / Fixstand |
|---|---:|---|---|
| MW221-001 | P0 | OUT_OF_TARGET | Windows 3.12 `chmod(..., follow_symlinks=False)`; nicht Teil des Windows/3.14.7-Vertrags. Metadaten versprechen 3.12 nicht mehr. |
| MW221-002 | P0 | OUT_OF_TARGET | POSIX-`fork_exec`-Arity unter 3.12/3.13; POSIX und frühere Interpreter sind explizit unsupported. |
| MW221-003 | P0 | OPEN_PROCESS | v2.21.0 wurde vor Ende der real ausgeführten roten Matrix publiziert. Für v2.21.1 bleiben lokale Finalgates und Live-Ref-Prüfung zwingend; billing-blockierte neue CI ist weder PASS noch FAIL. |
| MW221-004 | P1 | IMPLEMENTED_PENDING_FINAL | Windows-Aliase werden über Komponenten-/Objektidentität statt Textgleichheit geprüft; vier Konsumentenfamilien angepasst. Reale 8.3-Deckung bleibt volumenabhängig. |
| MW221-005 | P1 | IMPLEMENTED_PENDING_FINAL | Apply/Show arbeiten wieder von der öffentlichen Originaldefinition und erhalten Signatur, Annotationen, Defaults, Dekoratoren und führenden Kontext. |
| MW221-006 | P1 | IMPLEMENTED_PENDING_FINAL | Pragma-Scan behandelt `SyntaxError`-Unterklassen einschließlich `TabError`/`IndentationError` kontrolliert. |
| MW221-007 | P1 | IMPLEMENTED_PENDING_FINAL | Abgeleitetes Staging wird nicht selbst gehasht; der v2.21.0-Gesamtlauffehler besitzt eine Regression. |
| MW221-008 | P1 | MIXED | Nichtautoritäres Mapping darf keinen Test auslassen oder die pytest-Reihenfolge verändern. Seine Dauern priorisieren ausschließlich Mutanten-Tasks; innerhalb jedes Tasks bleibt die native Vollsuite erhalten und `--maxfail=1` beendet nach dem ersten Fehler. Timeout und Reuse-Fingerprint bleiben an die Vollsuite gebunden. Damit sinkt die Laufzeit vieler Kills, eine beweisbar vollständige selektive Ausführung existiert aber weiterhin nicht. |
| MW221-009 | P1 | REJECTED_AS_BUG | Ein beliebiger generischer Typechecker kann keine Releaseautorität beweisen; Sperre von Reuse/Score/Export ist der beabsichtigte fail-closed Vertrag. |
| MW221-010 | P1 | IMPLEMENTED_PENDING_FINAL | Vollrun-Autorität wird persistiert; Browser-Retest, CLI-Subset und Legacy-Runs können keinen Vollscore exportieren. CLI `results` und Browser kennzeichnen den Subset-Scope, beziehen Total/Score ausdrücklich nur auf diese Population und weisen `release-ready: no` aus. |
| MW221-011 | P1 | IMPLEMENTED_PENDING_FINAL | `git diff --name-only -z` erhält nicht-ASCII-Dateinamen ohne C-Quoting-Verlust. |
| MW221-012 | P1 | ACCEPTED_LIMITATION | Breite Environment-Bindung senkt Reuse, verhindert aber stale Verdicts. Spätere Whitelist-Optimierung benötigt eigene Sicherheitsanalyse. |
| MW221-013 | P1 | MIXED | Der Claim bündelte zwei Verträge: Fachliche Core-Drift in Source, Tests, Config oder projektinternen Importbytes bleibt absichtlich terminal. Die tatsächlich überbreite Behandlung reiner Ambient-Drift ist korrigiert: diagnostische Resultate bleiben `completed`, verlieren aber atomar Basis-, Reuse-, Score- und Exportautorität; ein Fehler beim Entzug lässt den Run recoveryfähig `running`. |
| MW221-014 | P1 | IMPLEMENTED_PENDING_FINAL | Symlink-/Junction-Source-Layouts bleiben aus Sicherheitsgründen ungestagt, werden aber nicht mehr still verworfen, sondern diagnostiziert. |
| MW221-015 | P1 | OUT_OF_TARGET | POSIX-Multi-User-Lockroot; außerhalb des Produktvertrags. |
| MW221-016 | P1 | OUT_OF_TARGET | POSIX-3.14-Gated-Launch-Race; außerhalb des Produktvertrags. |
| MW221-017 | P1 | IMPLEMENTED_PENDING_FINAL | Fake-`Popen`-Objekte dürfen keinen realen PID-/Tree-Sweep auslösen; gefährdete Tests mocken den Cleanup-Seam. |
| MW221-018 | P1 | IMPLEMENTED_PENDING_FINAL | E2E-Referenz verlangt mindestens einen echten Survivor und schließt Timeout/Suspicious als Ersatz-Kills aus. |
| MW221-019 | P1 | IMPLEMENTED_PENDING_FINAL | Governance prüft Struktur und Zustandsübergänge statt feste Bool-Werte, Branches, Commits oder Erfolgsprosa; LIVE-State ist auf v2.21.1 in Arbeit gestellt. |
| MW221-020 | P2 | IMPLEMENTED_PENDING_FINAL | PEP-263-Encoding wird beim Lesen, Generieren, Anzeigen und Anwenden berücksichtigt; nicht darstellbare generierte Bytes wechseln kontrolliert auf UTF-8. |
| MW221-021 | P2 | IMPLEMENTED_PENDING_FINAL | `typing_extensions.cast` wird wie `typing.cast` als semantisch äquivalenter Wrapper behandelt. |
| MW221-022 | P2 | ACCEPTED_LIMITATION | Async-Generatoren und PEP-695-Generika werden bewusst nicht trampolinisiert, weil ihre Protokoll- beziehungsweise Funktions-lokale Type-Parameter-Semantik ohne eigenen Operatorvertrag nicht erhaltbar ist; Regressionen pinnen den konservativen Skip statt still falsche Mutanten zu erzeugen. |
| MW221-023 | P2 | IMPLEMENTED_PENDING_FINAL | Methodenargumente werden ohne `None`-Sentinel vollständig weitergereicht. |
| MW221-024 | P2 | IMPLEMENTED_PENDING_FINAL | Parameterlose und `*args`-Staticmethods/Instanzmethoden werden nicht mehr pauschal ausgelassen. |
| MW221-025 | P2 | IMPLEMENTED_PENDING_FINAL | Quellnamen mit reserviertem `__mutmut_`-Delimiter werden reversibel in einen disjunkten Hex-Namensraum kodiert; Mapping und Runtime-Dispatch dekodieren dieselbe Identität. |
| MW221-026 | P2 | IMPLEMENTED_PENDING_FINAL | Regex-Quantifier-Mutation berücksichtigt Zeichenklassen; Validierung wird nicht von der öffentlichen `re`-Cache-Reihenfolge abhängig gemacht. |
| MW221-027 | P2 | IMPLEMENTED_PENDING_FINAL | Docstrings werden strukturell über Parent-Metadaten erkannt, unabhängig von Quote-Stil. |
| MW221-028 | P2 | IMPLEMENTED_PENDING_FINAL | Pragmaerkennung verlangt den exakten Kommentarvertrag und matcht keine Lookalikes wie `no mutated`. |
| MW221-029 | P2 | REJECTED_AS_BUG | `mutation_run` existierte in v2.20.0 noch nicht. `plan_finalized DEFAULT 1` betrifft daher nur Zwischen-/Entwicklungsschemata aus der unveröffentlichten Implementierungsphase und keine Migration einer veröffentlichten Nutzer-DB. Solche Dev-DBs werden nicht als unterstützter Datenvertrag übernommen. |
| MW221-030 | P2 | IMPLEMENTED_PENDING_FINAL | SQLite-Busy/Locked wird als konkurrierender Zugriff diagnostiziert und nicht mehr als Aufforderung zum Cachelöschen. |
| MW221-031 | P2 | IMPLEMENTED_PENDING_FINAL | Plan-Dublettenerkennung nutzt ein Set statt einer quadratischen Listensuche. |
| MW221-032 | P2 | IMPLEMENTED_PENDING_FINAL | `apply` löst den Mutantennamen vor jeder Evidenzinvalidierung auf; ein Tippfehler löscht kein CI-Artefakt. |
| MW221-033 | P2 | ACCEPTED_LIMITATION | Die Legacy-Verdict-Zeilen werden vor `apply` absichtlich fail-closed invalidiert, damit alte Rows keinen stale Export oder Score mehr autorisieren. Das kostet Retention historischer Verdicts, ist aber der konservative Sicherheitsvertrag und kein offener Korrektheitsbug. |
| MW221-034 | P2 | ACCEPTED_LIMITATION | Legacy-Meta ohne moderne Hashprovenienz wird konservativ invalidiert; die Diagnose kann verbessert werden, Wiederverwendung wäre aber nicht autoritativ. |
| MW221-035 | P2 | IMPLEMENTED_PENDING_FINAL | Dotenv-Dateien bleiben aus dem Staging ausgeschlossen, ihre Bytes binden aber den Einweg-Basisdigest. |
| MW221-036 | P2 | IMPLEMENTED_PENDING_FINAL | Generische Namen wie `build`, `dist`, `html`, `bug_reporting` und `_docs` werden nur am Workspace-Root pauschal ausgeschlossen, nicht in jedem Source-Unterbaum. |
| MW221-037 | P2 | IMPLEMENTED_PENDING_FINAL | Staging und Run-Basis schließen jetzt dieselbe vollständige SQLite-Namespace-Familie aus: DB, `-journal`, `-wal` und `-shm`. |
| MW221-038 | P2 | REJECTED_AS_BUG | Ein Prozess-Exit 0 ohne tatsächlich ausgeführte Tests darf keinen fachlichen Kill autorisieren; Suspicious/Abbruch ist fail-closed. |
| MW221-039 | P2 | ACCEPTED_LIMITATION | Der behauptete Abbruch eines gesunden Zielsystemlaufs wurde nicht dynamisch reproduziert. Der 60-s-Watchdog greift nur bei wartenden Tasks ohne In-flight-Arbeit; ein theoretisch länger blockierter Launch bleibt eine dokumentierte Availability-Grenze, aber kein bestätigter Releasebug. |
| MW221-040 | P2 | ACCEPTED_LIMITATION | `st_ino=0`/nicht beweisbare Reparse-Identität wird fail-closed abgelehnt. README dokumentiert exFAT/SMB/OneDrive/Reparse als mögliche, nicht pauschal unterstützte Windows-Grenze. |
| MW221-041 | P2 | IMPLEMENTED_PENDING_FINAL | Config-Tokenisierung deaktiviert `shlex`-Kommentartrunkierung; `#` bleibt Bestandteil valider Optionen/Pfade. |
| MW221-042 | P2 | IMPLEMENTED_PENDING_FINAL | `tests_dir`-Node-IDs werden vor der `--since-commit`-Filterung auf den Dateipfad normalisiert. |
| MW221-043 | P2 | IMPLEMENTED_PENDING_FINAL | Ein gültiger Diff ohne geänderte Mutationstargets ist jetzt ein diagnostizierter Exit-0-No-op; ungültige Git-Refs bleiben Exit 2 und JSON-Ausgabe bleibt maschinenlesbar. |
| MW221-044 | P2 | ACCEPTED_LIMITATION | Click-Mindeststand und bewusst geänderte Exitcodes sind Kompatibilitätskosten; auf dem exakt gelockten Zielsystem ist kein zusätzlicher Korrektheitsbruch belegt. |
| MW221-045 | P2 | MIXED | Pytest-8.2.2 nutzt ein hashgepinntes Windows/3.14-Overlay; Semgrep scannt nun Benchmarks und alle selbstgeschriebenen E2E-Fixtures; Git-Inventar ignoriert globale/systemweite Config sowie `.git/info/exclude`; `cancel-in-progress` gilt nur für PRs. Der Registry-Bootstrap kann mit Semgrep 1.175 nicht zugleich `auto` und `--metrics off` nutzen und bleibt bis zu einem vendorten Regelbundle dokumentierte Grenze. |
| MW221-046 | P2 | MIXED | Die zwei Python-3.14-Orakel, Survivor-Blindheit und Fake-PID-Cleanup sind korrigiert; weitere tautologische/no-op/global-Mock-Testschulden bleiben offen. |

Die aus den 46 Matrixzeilen abgeleitete Statussumme ist: 27
`IMPLEMENTED_PENDING_FINAL`, 7 `ACCEPTED_LIMITATION`, 3 `REJECTED_AS_BUG`, 4
`OUT_OF_TARGET`, 4 `MIXED` und 1 `OPEN_PROCESS`. Damit bleibt genau ein
Claudebefund als Prozessarbeit bis zum Abschluss der Veröffentlichung offen; die
Codex-Follow-ups werden separat gezählt.

## 5. Getrennte Codex-Follow-up-Findings

Die folgenden Befunde entstanden erst beim Reaudit und Bugfixing nach Claudes
46er Register. Sie werden bewusst nicht als zusätzliche MW221-Nummern geführt
und verändern weder Claudes ID-Menge noch deren Statussumme.

Das getrennte Codex-Register umfasst damit exakt CX221-001 bis CX221-063. Die
Prioritätsverteilung lautet 2 P0, 56 P1 und 5 P2; alle 63 stehen bis zum
erneuten lokalen Kandidatengesamtgate auf `IMPLEMENTED_PENDING_FINAL`.

| ID | Prio | Status | Befund und aktueller Fixstand |
|---|---:|---|---|
| CX221-001 | P1 | IMPLEMENTED_PENDING_FINAL | Der Projektroot wurde als bereits vollständig gehashter `sys.path`-Baum markiert, obwohl generische Root-Verzeichnisse wie `build/` dort übersprungen wurden. War `project/build` zugleich ein expliziter Importroot, konnten dessen importierbare Bytes wechseln, ohne den Dependency-Digest zu ändern. Der Coverage-Shortcut bindet nun die tatsächliche Root-Skipmenge; explizit importierte ausgeschlossene Unterbäume werden separat vollständig gehasht. |
| CX221-002 | P1 | IMPLEMENTED_PENDING_FINAL | Die neue Root-only-Ausnahme für generische Namen durfte versteckte Toolverzeichnisse nicht ebenfalls freigeben: verschachtelte `.claude`, `.codex`, `.serena`, `.git` und vergleichbarer Toolstate konnten sonst in ausführbares Staging geraten. Eine eigene rekursive Ausschlussmenge hält versteckten Toolstate in jeder Tiefe draußen, während fachliche Pakete namens `build`, `html` oder `dist` unter Sourcebäumen erlaubt bleiben. |
| CX221-003 | P1 | IMPLEMENTED_PENDING_FINAL | Die `--since-commit`-Abgrenzung von `tests_dir` verglich Pfadkomponenten case-sensitiv. Unter Windows konnte daher `Tests/test_mod.py` trotz konfiguriertem `tests/` als Produktionssource mutiert werden. Beide Seiten werden nun komponentenweise mit Windows-`normcase` verglichen; Node-ID-Normalisierung aus MW221-042 bleibt erhalten. |
| CX221-004 | P1 | IMPLEMENTED_PENDING_FINAL | `show` beziehungsweise Browser-Diff validierte den in der `.meta` gespeicherten `source_hash` nicht. Nach einer Sourceänderung konnte es aus aktuellem öffentlichen Quelltext und einem veralteten Staging-Mutanten einen plausibel wirkenden, aber nie für diese Source generierten Hybrid-Diff anzeigen; `apply` lehnte denselben Zustand bereits ab. Anzeige und Apply verwenden nun denselben generation-time Hash-Guard; stale `show` bricht ohne Diff ab und besitzt eine CLI-/Render-Regression. |
| CX221-005 | P1 | IMPLEMENTED_PENDING_FINAL | Ein Quellbezeichner, der exakt auf `__mutmut` endete, bildete den reservierten Trenner erst beim Anhängen der Mutanten-ID. Dadurch konnte `apply` auf eine andere Funktion auflösen. Jede Grenzbildung mit dem reservierten Namensraum wird nun vor der Mutanten-ID reversibel kodiert; ein Apply-/Show-E2E pinnt die exakte Ursprungsdefinition. |
| CX221-006 | P1 | IMPLEMENTED_PENDING_FINAL | Reservierter Trennertext in qualifizierten Modul- oder Paketkomponenten durfte nicht als lokaler Mutanten-Suffix interpretiert werden. Parser und Test-Mapping trennen jetzt ausschließlich den letzten lokalen numerischen Suffix und bewahren den qualifizierten Pfad bytegenau. |
| CX221-007 | P1 | IMPLEMENTED_PENDING_FINAL | Explizit konfigurierte externe Test-/Fixture-/Importbäume wurden in Randfällen nur mit der Workspace-Root-Skiplogik inventarisiert. Dadurch konnten staged Bytes in generisch benannten Unterverzeichnissen dem Basisdigest entgehen. Externe Bäume werden nun vollständig nach ihren tatsächlich veröffentlichten Bytes gehasht. |
| CX221-008 | P1 | IMPLEMENTED_PENDING_FINAL | Semgrep 1.175.0 kann die unter CPython 3.14 gültige ungeklammerte PEP-758-Form für mehrere Exceptiontypen nicht vollständig parsen. Das kanonische Gate brach deshalb fail-closed mit zwei `PartialParsing`-Errors ab. Die betroffenen Releasequellen bewahren nun explizite Klammern trotz Ruff-3.14-Formatierung; ein AST-Guard verbietet die vom gepinnten Scanner nicht unterstützte Form im gesamten Scanscope. Scan- oder Allowlistregeln wurden nicht gelockert. |
| CX221-009 | P1 | IMPLEMENTED_PENDING_FINAL | Das inkrementelle Staging besaß keine vollständige Eigentümermenge: gelöschte Source-, Fixture- und Rootdateien sowie fremde Ghost-Artefakte konnten unter `mutants/` fortleben. Der Neuaufbau pruned nun den vollständig tool-owned Baum einschließlich verwaister Sidecars und Windows-read-only-Dateien. Read-only-Ziele werden nur nach nachgewiesener contained Non-Reparse-Identität und `st_nlink == 1` ersetzt; Dev/Inode werden erneut validiert und ein fehlgeschlagener Publish stellt den vorherigen Modus nur am identischen Objekt wieder her. Externe Hardlink-Ziele bleiben unverändert und werden fail-closed abgelehnt. |
| CX221-010 | P1 | IMPLEMENTED_PENDING_FINAL | `source_hash` allein belegte nicht, dass die aktuell gelesenen generierten Bytes dieselben waren, aus denen der Mutant erzeugt wurde. Ein persistierter, validierter `generated_hash` bindet nun Show, Apply und Run an exakt dieselbe reguläre Stagingdatei; fehlende, fremde oder driftende Provenienz wird fail-closed abgelehnt. |
| CX221-011 | P1 | IMPLEMENTED_PENDING_FINAL | Einzelne Hashprüfungen ließen Drift in nicht mutierten Fixtures, Konfigurationen oder Zusatzdateien zwischen autoritativen Phasen offen. Ein stabiler Digest des vollständigen ausführbaren Stagingbaums wird nach Generation eingefroren und auf allen erfolgreichen Pfaden vor beziehungsweise nach Clean-, Stats-, Forced-Fail-, Reuse- und Workerphase erneut geprüft. |
| CX221-012 | P1 | IMPLEMENTED_PENDING_FINAL | Der Governance-Skip für Self-Dogfood hätte an einem beliebigen Git-losen Checkout eine False-Green-Lücke erzeugen können. `test_release_supply_chain.py` überspringt Governance nur in einem eindeutig erkennbaren, vom Tool generierten Staging mit Mutmut-Fingerprint; normale ZIP-/Git-lose Arbeitsbäume bleiben prüfpflichtig. |
| CX221-013 | P1 | IMPLEMENTED_PENDING_FINAL | Root-Ausschlüsse konnten gemeinsam mit einem bereits vorhandenen Stagingbaum Dateien unsichtbar machen und einen unveränderten Digest vortäuschen. Root-Policy, explizite Roots und vollständige Staging-Ownership werden nun getrennt adjudiziert; ausgeschlossene Projekt-Unterbäume, die tatsächlich importierbar oder staged sind, bleiben digestgebunden. |
| CX221-014 | P1 | IMPLEMENTED_PENDING_FINAL | Eine beliebige gleichnamige `.meta`-Fixture konnte als Toolmetadaten fehlklassifiziert werden oder zusammen mit einem fremden Companion Eigentum vortäuschen. Nur schema-validierte, paarweise an Source und `generated_hash` gebundene Sidecars besitzen Autorität; normale `.meta`-Fixtures bleiben Nutzerdaten. |
| CX221-015 | P1 | IMPLEMENTED_PENDING_FINAL | Stateful pytest-/Tool-Caches konnten Auswahl und Resultate über Runs hinweg beeinflussen oder in den eigenen Basisdigest geraten. Runtime-Caches werden vor Ausführung entfernt beziehungsweise in isolierte Verzeichnisse umgeleitet; cachegesteuerte pytest-Optionen dürfen keine ungebundene Teilmenge autorisieren. |
| CX221-016 | P1 | IMPLEMENTED_PENDING_FINAL | Windows behandelt die Python-Endung case-insensitiv. Zunächst war nur der `--since-commit`-Ingress korrigiert; `walk_source_files()` und `should_ignore_for_mutation()` verwarfen `MODULE.PY` danach weiterhin still. Alle drei Selektionsgrenzen nutzen nun Casefolding. Eine reale Temp-Git-/CLI-Gegenprobe trug `MODULE.PY` durch Dry-run, Generation, Staging, Metadaten, 16 Mutanten und `show`; die lokale Regression verlangt zusätzlich einen positiven Dry-run-Mutantencount ohne Filesystemwrite. |
| CX221-017 | P1 | IMPLEMENTED_PENDING_FINAL | Der Staging-Digest band primär Pfade und Inhalte, aber nicht jede beobachtbare Datei-/Verzeichnis-Metadatenänderung. Leere Verzeichnistopologie, Dateiart, Modus und relevante Zeit-/Identitätsdaten fließen nun in die Drift-Evidenz ein, sodass Content-ABA oder Datei-/Verzeichniswechsel nicht als stabil gelten. |
| CX221-018 | P1 | IMPLEMENTED_PENDING_FINAL | Sichtbare Root-Artefakte, Runtime-Caches und lose `.pyc`/`.pyo`-Dateien konnten je nach Erzeugungszeitpunkt entweder ungebunden ausgeführt oder aus dem Digest ausgeblendet werden. Ausführbare Root-/Fixturebytes werden vollständig gebunden; ausschließlich klar definierter abgeleiteter Runtimezustand wird vor dem Snapshot rekursiv entfernt. |
| CX221-019 | P1 | IMPLEMENTED_PENDING_FINAL | Die Coverage-Vorphase lief vor dem autoritativen Staging-Snapshot. Ein Test oder Plugin konnte deshalb Fixture-, Config- oder Modulbytes ändern und der spätere Snapshot hätte den manipulierten Zustand als Basis gesegnet. Nun wird bereits vor Coverage ein vollständiger Snapshot genommen und unmittelbar danach unverändert validiert. |
| CX221-020 | P1 | IMPLEMENTED_PENDING_FINAL | Wiederverwendete Verdicts blieben in Fehler-, Hard-Kill-Recovery- und späten Driftpfaden teilweise als cachefähig markiert; selbst ein Fehler beim Widerruf konnte den Run bereits terminalisieren und so jede spätere Recovery überspringen. Jeder unvollständige Run widerruft nun vor dem Terminalstatus. Scheitert genau dieser Widerruf, bleibt der Run bewusst `running`, bis der nächste Lock-Eigentümer revoke-first recovered. |
| CX221-021 | P1 | IMPLEMENTED_PENDING_FINAL | Zulässige pytest-Ausgaben wie JUnit, `basetemp`, Logfiles, pytest-cov-HTML/XML/JSON und echte pytest-benchmark-Saves wurden relativ zum ausführbaren `mutants/`-CWD erzeugt. Der folgende Staging-Check brach dadurch gewöhnliche Konfigurationen ab; beim Benchmark-URI entstand unter Windows sogar ein falscher relativer `Users/...`-Baum. Bekannte Report-, Temp- und Pluginziele werden jetzt vor Pluginstart beziehungsweise durch den frühen Guard auf einen frischen externen Runtime-Root umgebogen. |
| CX221-022 | P1 | IMPLEMENTED_PENDING_FINAL | Ein selektiver Namens-, Pfad- oder `--since-commit`-Lauf konnte seinen Teilscore mit `--min-score` als Projektgate autorisieren; ein einzelner getöteter Mutant ergab damit einen falschen grünen 100-%-Gatewert. Die drei Selektionsformen werden in Kombination mit `--min-score` jetzt vor Git, Generation und Ausführung mit Exit 2 abgelehnt. |
| CX221-023 | P1 | IMPLEMENTED_PENDING_FINAL | Der Cross-run-Projektfingerprint band bei Verzeichnissen trotz Root-Ausschlüssen `st_size`/`st_nlink`. Auf NTFS änderte allein das erstmalige Erzeugen der ausgeschlossenen `.mutmut-cache` die Projektroot-Größe von 0 auf 4096 und invalidierte damit den eigenen ersten Lauf. Stabile Projekt-/Import-Verzeichnisdigests binden nun Modus und Windows-Attribute sowie die explizite enthaltene Topologie; nur die strikte In-run-Staging-Evidenz bindet zusätzlich Größe, Linkzahl und Zeiten. |
| CX221-024 | P1 | IMPLEMENTED_PENDING_FINAL | Tool-eigene `.py.meta`-Publikationen wechseln absichtlich zwischen generation-only und reichen Ergebnisbytes. Atomic Replace änderte dabei Datei- und Parent-Zeitstempel, wodurch jeder identische Folgelauf Stats- und Verdict-Reuse wieder selbst invalidierte. Cross-run-Digests binden für den generierten Baum stabile Semantik ohne Publikationszeiten; der separate In-run-Digest behält die vollständige Zeit-/ABA-Erkennung. |
| CX221-025 | P1 | IMPLEMENTED_PENDING_FINAL | Konfigurierte DB-/Cache-Ausschlüsse galten im Workspace-Inventar, wurden aber nicht an alle sekundären `sys.path`-, Editable- und Distribution-Walks weitergegeben. Dadurch konnte eine ausgeschlossene SQLite-Datei den eigenen Kontextfingerprint verändern. Dieselbe kanonische Ausschlussmenge wird nun durch jeden Dependency-/Import-Walk propagiert; eine Gegenprobe trennt ausgeschlossene DB-Bytes von benachbarten ausführbaren Runtimebytes. |
| CX221-026 | P1 | IMPLEMENTED_PENDING_FINAL | Der einzige Basisdigest unterschied fachliche Projektänderungen nicht von flüchtiger Ambient-Metadaten-Drift. Ein zusätzlicher Core-Digest bindet Config, Source, Tests und tatsächlich importierbare Projektbytes. Core-Drift bleibt terminal; reine Ambient-Drift bewahrt Resultate nur diagnostisch und entzieht in einer SQLite-Transaktion Basis- sowie historische Reuse-Autorität. |
| CX221-027 | P0 | IMPLEMENTED_PENDING_FINAL | Ein zunächst erwogener Fast-first-Hook sortierte pytest-Items anhand nichtautoritativer Mappingdaten um. Das hätte bei reihenfolgeabhängigen Suites False Survivors beziehungsweise False Kills erzeugt und diese über den Vollsuite-Fingerprint wiederverwendbar gemacht. Die Intra-Suite-Umsortierung wurde vollständig entfernt: pytest behält seine native Reihenfolge; Hints beeinflussen nur die Reihenfolge unabhängiger Mutanten-Tasks, während `--maxfail=1` nach dem ersten Fehler sicher abbricht. |
| CX221-028 | P1 | IMPLEMENTED_PENDING_FINAL | Der Phase-Guard schrieb seinen Ausführungsbeweis auch für einen im Call-Body übersprungenen Test. Eine nur aus Runtime-Skips bestehende Auswahl konnte dadurch Exit 0 als fachlichen Survivor akzeptieren. Der Guard autorisiert jetzt ausschließlich nicht übersprungene Call-Reports; eine reale pytest-Gegenprobe verlangt bei ausschließlich Call-time-Skips den fail-closed Phasenfehler. |
| CX221-029 | P1 | IMPLEMENTED_PENDING_FINAL | Die vier DB-/Sidecar-Ausschlüsse wurden an den automatischen Source-Mirror, aber nicht an `also_copy`/`extra_paths` übergeben. Eine explizit oder in einem konfigurierten Verzeichnis erneut gespiegelte DB konnte so ausführbare Stagingbytes ändern, obwohl Full- und Core-Basis identisch blieben. Exakte Ausschlüsse gelten jetzt für beide Mirrorpfade; vorhandene ausgeschlossene Stagingkopien werden sicher entfernt. |
| CX221-030 | P1 | IMPLEMENTED_PENDING_FINAL | Ein initial wegen reiner Ambient-Instabilität diagnostisch deautorisierter Lauf berechnete später einen stabilen Stats-Kontext und konnte dadurch dennoch Stats sowie historische Verdicts wiederverwenden; bei unverändert unvollständiger Endbasis hätten sogar frisch erzeugte Verdicts im Folgelauf wieder Autorität erlangt. Die initiale Autoritätsentscheidung wird nun bis in die Pipeline propagiert: Stats werden frisch gesammelt, frühere Verdicts nie übernommen und vor jedem erfolgreichen Abschluss einer initial unvollständigen Basis werden aktuelle sowie historische Fingerprints atomar entzogen – auch wenn Anfangs- und Endsnapshot identisch sind. Score und Export bleiben gesperrt. |
| CX221-031 | P1 | IMPLEMENTED_PENDING_FINAL | Die Release-Pin-Governance leitete den Kandidatenzustand aus frei änderbarer Prosa ab, akzeptierte jeden vom Paketstand abweichenden Guide-/CLAUDE-Ref und prüfte bei CLAUDE nur den ersten Treffer; README-Befehle waren ungebunden. Der kanonische aktive Ref muss nun entweder exakt der Paketversion oder ihrem unmittelbaren Patchvorgänger derselben Major-/Minor-Serie entsprechen. Beide README- und CLAUDE-Installationsformen müssen denselben Guide-Ref tragen; beliebig alte, künftige oder serienfremde Pins scheitern. Die tatsächliche Remoteexistenz bleibt ein separates Live-Gate unmittelbar vor Remote-Writes. |
| CX221-032 | P1 | IMPLEMENTED_PENDING_FINAL | Nach Entfernung der unsicheren Intra-Suite-Umsortierung transportierte der Worker die vollständigen nichtautoritativen `tests_dir`-Targets wieder direkt in `argv`. Eine ausreichend große, aber valide Zielmenge überschritt unter Windows die 32.767-Zeichen-Grenze und endete vor pytest mit WinError 206. Autoritative Auswahl und nichtautoritative Vollsuite verwenden nun dieselbe private Runtime-Argfile; deren Zeilen bewahren die konfigurierte Reihenfolge exakt. Eine synthetische Zielmenge oberhalb des Windows-Limits pinnt vollständigen Inhalt, Reihenfolge und kurze Prozesskommandozeile. |
| CX221-033 | P2 | IMPLEMENTED_PENDING_FINAL | Zwei Sicherheitstest-Setups waren nach verschärften Vorbedingungen nicht mehr zielgenau: Der Parent-Swap-Test rief den Phase-Guard mit einem unvollständigen Report-Double ohne `skipped` auf; der `--force`-Teillöschtest besaß keinen gültigen Mutationsroot und traf deshalb die absichtlich vorgezogene Konfigurationsprüfung statt der Löschgrenze. Das Double bildet den realen nicht übersprungenen pytest-Call nun mit `skipped=False` ab, und der Force-Test stellt eine minimale valide Quelle bereit. Beide Orakel erreichen wieder die jeweils behauptete Produktschranke; Produktcode wurde dafür nicht gelockert. |
| CX221-034 | P1 | IMPLEMENTED_PENDING_FINAL | Der langlebige Project-/Dependency-/`sys.path`-Basisdigest band bei jeder regulären Datei `st_nlink`. Da uv Paketbytes über Hardlinks teilt, änderte das Erzeugen oder Löschen einer beliebigen anderen uv-Umgebung die Linkzahl hunderter Dateien im bereits installierten Zielvenv, obwohl Inode, Bytes, Größe, Zeiten und Attribute gleich blieben. Dadurch flappte die unmittelbare Export-Doppelaufnahme und gültige Run-Evidenz wurde rein durch externes uv-Churn entwertet. Cross-run-Digests und ihr Path-Reopen-Vergleich ignorieren nun ausschließlich die Linkzahl; Bytes, Pfadidentität und übrige Metadaten bleiben gebunden. Der strikte In-run-Staging-Digest behält die Linkzahl zur Hardlink-/TOCTOU-Erkennung. Alias-add/remove-, Write-through-, Export-Doppelsnapshot- und Strict-Staging-Regressionen pinnen beide Vertragsseiten. |
| CX221-035 | P2 | IMPLEMENTED_PENDING_FINAL | Ein Strict-Staging-Test behauptete, ein vollständig zwischen zwei Polling-Snapshots erzeugtes und wieder gelöschtes leeres Verzeichnis müsse auf NTFS zwingend einen geänderten Parent-Zeitstempel hinterlassen. Das Orakel flappte dynamisch in 4/10 Wiederholungen; ein zwischen Snapshots vollständig verschwundenes ABA ist ohne garantierte Filesystemmetadaten oder Ereignisüberwachung nicht beobachtbar. Der Test trennt nun die beweisbaren Verträge: vorhandene leere Topologie ändert den Digest, eine explizite Parent-Zeitänderung wird gebunden und ein Dateimoduswechsel bleibt sichtbar. Der Produktdigest wurde nicht gelockert. |
| CX221-036 | P1 | IMPLEMENTED_PENDING_FINAL | Die Semgrep-Allowlist band den vollständigen Finding-Dateikontext nach `str.splitlines()`-Normalisierung. Dadurch kollidierten nicht nur CRLF/LF, sondern auch semantisch relevante Unicode-Zeilentrenner wie U+2028: Ein dynamischer Gegenversuch änderte kompilierbare Testbytes und AST-Struktur bei identischem Allowlist-Filehash. Die Normalisierung vereinheitlicht nun ausschließlich CRLF beziehungsweise bare CR zu LF; alle anderen Unicodezeichen bleiben digestwirksam. Eine U+2028-Negativregression pinnt den Bypass. |
| CX221-037 | P1 | IMPLEMENTED_PENDING_FINAL | Windows-Casing wurde zwar für `.PY`-Selektion korrigiert, aber `get_mutant_name()` entfernte konfigurierte Layoutroots und den finalen `__init__`-Stem weiterhin case-sensitiv. Dadurch erzeugten `SRC/pkg/__INIT__.PY` und die Runtime verschiedene Mutanten-Tokens; der Mutant blieb wirkungslos. Layoutroot und finaler Init-Stem folgen nun Windows-Identität. Ein echter Subprozess importiert das generierte Package und beweist, dass genau der qualifizierte Token den Mutanten aktiviert. Die weitergehende Challenge, beliebig anders geschriebene Package-/Modulnamen müssten ebenfalls normalisiert werden, wurde dynamisch verworfen: CPython 3.14 importiert auf Windows `PKG` nicht als `pkg`; Python-Identifier bleiben bewusst case-sensitiv. |
| CX221-038 | P1 | IMPLEMENTED_PENDING_FINAL | Der flache Staging-Namensraum überschrieb legitime Projektdateien wie `mod.py.meta`, `sitecustomize.py`, `_mutmut_stats_plugin.py`, `_mutmut_phase_guard.py`, `.mutmut-config-fingerprint` und `mutmut-cicd-stats.json`; gleichnamige Module, Packages, Resource-Namespaces oder `.pyd` unter vorgeordneten `src`-/`source`-Roots konnten interne pytest-Guards shadowen beziehungsweise selbst vom Helper verdrängt werden. Ein zentraler read-only Planpreflight modelliert automatische und konfigurierte Mirrors mit Windows-Identität und bricht vor `--force`, Cache, Executor oder Kopie als Konfigurationsfehler ab. Auch data-only Namespacepfade sind reserviert, weil `importlib.resources` sonst statt der Projektressource das spätere Toolmodul auflöst; lose `.pyc`/`.pyo` werden zusätzlich vor jedem Helper-/Testimport rekursiv entfernt. Direct API, Dry-run und Kopiergrenze prüfen denselben Vertrag erneut; Nutzerbytes bleiben unangetastet. |
| CX221-039 | P2 | IMPLEMENTED_PENDING_FINAL | Die strukturelle Docstring-Erkennung aus MW221-027 hielt jede führende `SimpleString`/`ConcatenatedString`-Expression für einen Docstring. Python weist jedoch Bytes-Literalen und f-String-Verkettungen kein `__doc__` zu; echte Mutanten wurden still unterdrückt und die Trampolin-Wrapperkopie führte f-String-Seiteneffekte im Clean-Pfad doppelt aus. Umgekehrt ist ein konstanter String vor einem Semikolon trotz weiterer Small Statements ein echter Docstring. Visitor und Wrapper prüfen nun konstanten `str` und die erste Statementposition; der Wrapper kopiert ausschließlich den String und lässt Folgestatements genau einmal in der privaten Implementierung laufen. Generierte Laufzeitproben verlangen korrekten `__doc__` und exakt einen Seiteneffekt. |
| CX221-040 | P1 | IMPLEMENTED_PENDING_FINAL | Der korrigierte LIVE-State-Test akzeptierte bei `branch: main` bereits irgendein prosaisches `main`, verbot qualifizierte alte Refs wie `origin/fix/...` nicht und band den Prosa-Branch nicht an den Checkout. Auch zulässige Pending-/Open-Statuswerte oder ein vorzeitig gesetztes `CLOSED_PROCESS` hätten einen scheinbar finalen Report zertifizieren können. Der geschlossene Vertrag verwendet exakt normierte `in_progress`-, `candidate_validated`- und `released`-Zustände, maschinenreine LIVE-Blöcke und einen neutralen externen Publikationsblock; die Zielversion darf außerhalb davon ausschließlich in Git-Pins, Fixbranch, Versionsfeld und Frontmatter vorkommen. Der Git-Vertrag akzeptiert den exakten Quellbranch oder ausschließlich einen Zwei-Eltern-Merge mit diesem Branch als zweitem Parent und byteidentischem Tree. Im Post-Release-Zustand bindet ein Provenienzdatensatz Kandidatencommit/-tree, Integrationscommit/-tree und ein exakt benanntes annotiertes Tag; der Housekeeping-Commit muss dessen direkter Ein-Eltern-Nachfolger sein und darf ausschließlich die eng allowgelisteten State-/Memory-/Reportdateien verändern. `started_at` ist strikt ISO `YYYY-MM-DD`, der Memory-Refresh darf nicht älter sein. Sobald das Finalgate als bestanden markiert wird, sind offene Produkt-/Pending-Statuswerte verboten und alle CX-Findings müssen `VERIFIED_FIXED` sein. MW221-003 bleibt bis zum tatsächlichen Release/Housekeeping zwingend `OPEN_PROCESS` und muss danach `CLOSED_PROCESS` sein. Negative Branch-, Ref-, Parent-, Tree-, Tag-, Diff- und Lifecycle-Gegenproben pinnen den Vertrag. |
| CX221-041 | P1 | IMPLEMENTED_PENDING_FINAL | Der Typechecker-Filter las generierte Stagingquellen unabhängig von ihrem PEP-263-Cookie strikt als UTF-8. Eine auf Windows gültige CP1252-Quelle, die einen Typecheckerfehler enthält, brach deshalb nach erfolgreicher Generierung mit rohem `UnicodeDecodeError` ab. Der Filter dekodiert nun dieselben Bytes über `tokenize.detect_encoding` wie Generation, Show und Apply; eine reale CP1252-Regression mit `café` bindet die fehlerhafte Mutante korrekt an den Checkerbefund. |
| CX221-042 | P1 | IMPLEMENTED_PENDING_FINAL | Absolute `extra_paths` außerhalb des Projektroots wurden von der Stagingkopie bewusst übersprungen, aber `Path("mutants") / absolute` verwarf anschließend sowohl im Clean-/Stats-Runner als auch im Worker den Stagingpräfix und nahm das echte Live-Original in `PYTHONPATH` auf. Selbst nach dem ersten Fix blieb derselbe Bypass über ein geerbtes `PYTHONPATH` bestehen; außerdem ließen lange und 8.3-kurze Schreibweisen von CWD und Konfigurationspfad Planner, Kopie, Cleanup, Runner und Worker unterschiedlich relativieren. Eine zentrale kanonische Mappingfunktion ist nun für alle fünf Grenzen maßgeblich, verwirft externe absolute, rootrelative und drive-relative Windows-Eingaben und bildet interne Aliase auf dieselbe Stagingadresse ab. Beide Prozesspfade ersetzen geerbtes `PYTHONPATH` vollständig durch ihre expliziten Stagingroots. Parent-/Worker-, echter Kindimport- und reale 8.3-Kreuzproben prüfen den Vertrag unter Windows 3.14.7. |
| CX221-043 | P1 | IMPLEMENTED_PENDING_FINAL | Die Releasekette unterschied Kandidaten- und integrierte Finalgates nicht durch einen maschinenlesbaren Sequenzmarker. Den reproduzierbaren Builds fehlte außerdem ein vollständiges sortiertes Artefakt-/SHA-256-Inventar, und der Windows-Smoke belegte nicht, dass Wheel und Sdist tatsächlich exakt die erwartete Paketversion installierten. Der Sequenzmarker bindet nun integrierte Finalgates und reproduzierbare Artefakte vor dem Tag. Beide Builds erzeugen, protokollieren, vergleichen und publizieren `SHA256SUMS` sowie sortierte Wheel-/Sdist-Inventare; der Windows-Smoke prüft die Hashliste vor der Installation und verlangt für beide installierten Artefakte exakt `mutmut-win, version 2.21.1`. Die fokussierte Workflow-Governance ist implementiert; das vollständige Finalgate bleibt offen. |
| CX221-044 | P1 | IMPLEMENTED_PENDING_FINAL | Die Abschlusssequenz forderte zusätzliche lokale Security-, Supply-Chain-, Reproduzierbarkeits- und Installed-Artifact-Gates, ohne für alle Werkzeuge und Aufrufe reproduzierbare Pins beziehungsweise kanonische Befehle festzulegen. Eine gelockte `release`-Gruppe bindet nun `check-wheel-contents==0.6.3`, `pyflakes==3.4.0`, `twine==7.0.0` und `zizmor==1.30.0`; ein stdlib-basierter Windows-Runner lädt actionlint 1.7.12, ShellCheck 0.11.0 und Gitleaks 8.30.1 ausschließlich aus allowgelisteten offiziellen HTTPS-Assets, prüft SHA-256 vor sicherer Extraktion und bindet exakte Versionsausgaben. Der netzfähige Semgrep-Bootstrap erhält statt einer Denylist nur Proxy-/CA-/OS-/Locale-Werte, einen konstruierten Venv-PATH und isolierte Git-/Toolzustände; beliebige Credentials, Caller-PATH und COMSPEC werden nicht weitergereicht. Gitleaks prüft sauberen vollständigen Worktree und Historie einschließlich Git-ignorierter Policydateien. Der Supply-Chain-Test pinnt Root-Metadaten, Registry sowie exakte Sdist- und Windows-Wheelnamen/-Hashes; Build und Securityjob hängen mechanisch von den vollständigen lokalen Qualitätsgates ab. Der kanonische Native-Lauf auf dem sauberen Implementierungscommit `4daed987742d24b420285fec46fc91bc2e1189a4` bestand vollständig; die Wiederholung auf dem integrierten Releasebaum bleibt zwingend offen. |
| CX221-045 | P1 | IMPLEMENTED_PENDING_FINAL | Automatische Projektmirrors und konfigurierte `also_copy`-/`extra_paths`-Mirrors konnten denselben flachen Stagingtarget besitzen; selbst ein fehlender konfigurierter Input hatte Cleanup-Autorität und konnte gerade kopierte Livebytes löschen. Der read-only Preflight plant Dateien, Verzeichnisse und Missing-Cleanup-Roots und erlaubt Target-Sharing nur für dieselbe Live-Identität oder eine konsistente Ancestor-/Descendant-Abbildung derselben Quelle. Sonst erfolgt der Abbruch vor jeder Veränderung von `mutants/`. |
| CX221-046 | P2 | IMPLEMENTED_PENDING_FINAL | `dry_run` las gültige PEP-263-Quellen pauschal als UTF-8 und zählte dieselbe physische Datei bei überlappenden Roots oder Windows-Alias mehrfach, während die reale Generation dekodierte und deduplizierte. Die Preview verwendet nun dieselbe Encoding-Erkennung und eine strict-resolved Source-Identity-Deduplizierung, ohne den Workspace zu beschreiben. |
| CX221-047 | P1 | IMPLEMENTED_PENDING_FINAL | `show > mutant.patch` konnte durch Textausgabe CRLF, fehlendes EOF-Newline, PEP-263-/BOM-Bytes und Unicode-Zeilentrenner verändern; die Ausgabe war damit kein verlässlicher Git-Patch. Hunkbildung trennt ausschließlich an physischem LF, emittiert korrekte `No newline at end of file`-Marker, kodiert nur Patchmetadaten als UTF-8, bewahrt Hunkbytes im Quellencoding und schreibt stdout binär. Forensik bleibt ausschließlich auf stderr. Reale CP1252-, UTF-8-BOM-, CRLF-/LF-/EOF- und Git-Apply-Gegenproben sind vorhanden. |
| CX221-048 | P1 | IMPLEMENTED_PENDING_FINAL | Leere Live-Verzeichnisse wurden beim ersten Mirror nicht materialisiert und nach ihrem Entfall als leere Staging-Shells nicht entfernt. Dadurch wich PEP-420-/`find_spec`-Semantik vom Livebaum ab und konnte Mutationsergebnisse verfälschen. Automatische und konfigurierte leere Verzeichnisse werden nun erzeugt; entfallene Shells werden bottom-up entfernt, während Stagingroot, vorhandene Liveverzeichnisse und explizite Mirrorroots erhalten bleiben. |
| CX221-049 | P1 | IMPLEMENTED_PENDING_FINAL | `_rewrite_coding_cookie` verwendete `str.splitlines()`: NEL, VT, FF oder U+2028 auf physischer Zeile 1 konnten den echten PEP-263-Cookie auf LF-Zeile 2 verdecken und nach UTF-8-Fallback ein falsches Legacy-Encoding publizieren. Die Rekonstruktion zählt ausschließlich physische LF-Grenzen und aktualisiert exakt die ersten zwei zulässigen Cookiezeilen. |
| CX221-050 | P1 | IMPLEMENTED_PENDING_FINAL | Aktive Architektur-, Design-, Lizenz- und Testsuppressionsdokumente trugen weiterhin den verworfenen Mehrversionsvertrag oder pauschale UTF-8-Quellannahmen. Die aktiven Verträge nennen nun einheitlich Windows und exakt CPython 3.14.7, unterscheiden PEP-263-Quelltext von UTF-8-Metadaten und beschreiben GitHub Releases statt PyPI als Publikationskanal. |
| CX221-051 | P1 | IMPLEMENTED_PENDING_FINAL | Die Reviewberichte behaupteten fälschlich ein viertes natives, über die GitHub-Release-API verifiziertes Zizmor-ZIP. Tatsächlich umfasst das native Manifest nur actionlint, ShellCheck und Gitleaks; Zizmor 1.30.0 stammt hashgebunden als Sdist sowie Windows-/Linux-Wheel aus PyPI beziehungsweise `uv.lock`. |
| CX221-052 | P1 | IMPLEMENTED_PENDING_FINAL | Der verbindliche Sprint-39-Backlog fehlte, während der alte Governancevertrag sein Fehlen selbst bestätigen konnte; aktive Product-/Serena-Metadaten hinkten dem Releaseprozess hinterher. Ein exakt benannter Sprintbacklog und verschärfte Existenz-/Inhaltsprüfungen binden Scope, Branch, Reviewquellen, `NOT_EXECUTED`-Semantik und die vollständige Releasefolge; aktive Metadaten werden synchronisiert. |
| CX221-053 | P1 | IMPLEMENTED_PENDING_FINAL | Der lokal verpflichtende Releasewrapper prüfte nur actionlint, ShellCheck, Pyflakes und Gitleaks, während Zizmor regular/pedantic ausschließlich im potenziell billing-blockierten Workflow lief. Der Wrapper löst nun Zizmor 1.30.0 ausschließlich aus der aktiven gelockten Umgebung auf und führt beide Personas offline in derselben minimalen Umgebung aus; negative Versions-, Pfad-, Persona- und Orchestrierungsregressionen binden den Vertrag. |
| CX221-054 | P1 | IMPLEMENTED_PENDING_FINAL | Die Report-Governance verlangte sechs Supply-Chain-Digests nur als freie Teilstrings; vertauschte Tool-/Artefaktzuordnungen oder irrelevante Anhänge blieben grün. Beide Berichte besitzen nun einen markierten, eindeutig parsbaren Sechs-Zeilen-Provenienzblock, dessen relationale Abbildung direkt gegen Native-Manifest und `uv.lock` geprüft wird. |
| CX221-055 | P1 | IMPLEMENTED_PENDING_FINAL | Tokenbasierte Dokumenttests ließen trotz CX221-050/-052 einen normativen Linux-Benchmark, eine ungebundene Buildsequenz, falsche Velocitysummen, den verworfenen `re._parser`-Entwurf, Promptmarkup, veraltete Strukturgrößen und vorgehakte Sprintgates passieren. Die aktiven Verträge werden semantisch synchronisiert; strukturierte Negativtests binden Windows-Scope, GitHub-only-Kanal, Releasefolge, Velocityarithmetik, offenen Sprintplan und nichtvolatile Strukturmetadaten. |
| CX221-056 | P1 | IMPLEMENTED_PENDING_FINAL | Der PSF-Hash schützte erst den Lizenztext ab dessen Überschrift; CPython-Herkunft, Anpassungsbeschreibung, Copyright und Anwendbarkeit davor waren nur lose Teilstrings. Zusätzlich zum unveränderten PSF-Text wird nun der gesamte zusammenhängende CPython-Derivatabschnitt ab seiner Herkunftsüberschrift positions- und contentgebunden gehasht. |
| CX221-057 | P1 | IMPLEMENTED_PENDING_FINAL | Der echte Coverage-Volltest benötigte 51:37 Minuten; vom 60-Minuten-CI-Joblimit blieben damit nur 8:23 Minuten für Checkout und zwei Locked-Sync-Phasen. Das Testjoblimit wird auf 120 Minuten angehoben und durch den Workflowvertrag gepinnt, ohne den ausgefallenen Remote-Lauf als ausgeführt zu werten. |
| CX221-058 | P1 | IMPLEMENTED_PENDING_FINAL | Die Governance verlangte im aktiven Sprintbacklog dauerhaft neun offene Checkboxen und denselben Branch wie im LIVE-State, erlaubte den Backlog aber nicht im Post-Release-Housekeeping. Ein wahrheitsgemäßer `released`-Zustand mit Branch `main` und abgeschlossenen Gates war dadurch unerreichbar. Der aktive Sprintpfad wird nun eng aus einer positiven ASCII-Sprintnummer abgeleitet; bis `candidate_validated` müssen exakt neun Post-Candidate-Gates offen sein, bei `released` exakt neun geschlossen. Genau dieser Backlog ist im direkten docs-only Housekeeping-Child erlaubt und verpflichtend. |
| CX221-059 | P0 | IMPLEMENTED_PENDING_FINAL | Der isolierte Windows-/CPython-3.14.7-Dogfood beendete zwar 91/91 Mutanten, wurde aber wegen echter Stagingdrift terminal als `failed` gespeichert. `_generate_mutants()` hatte `mutants/src` in den Eltern-`sys.path` eingefügt; Windows-Spawn-Worker erbten ihn und erzeugten nach dem eingefrorenen Snapshot vier `__pycache__`-Dateien im ausführbaren Staging. Die Steuerungs- und Generationsprozesse behalten nun ausschließlich den Live-Engine-Importpfad; nur pytest-Kinder erhalten Staging über ihre explizite Umgebung. Ein Spawn-Preparation-Test bindet unveränderten Elternpfad und verbietet jeden geerbten `mutants/`-Pfad. Der erste identische Recheck endete `completed` mit 80/11 und deckte vier echte Testlücken auf; nach deren Regressionen erreichte der zweite reale Vier-Worker-Lauf 91/91, 90 killed, einen Windows-äquivalenten `mutants`/`MUTANTS`-Survivor, null Problem-Buckets, vollständige Basis, 98,9 Prozent und kein Staging-`__pycache__`. Die Wiederholung auf dem integrierten Commit bleibt Teil des offenen Finalgates. |
| CX221-060 | P1 | IMPLEMENTED_PENDING_FINAL | Zizmor lief offline und in zwei Personas, konnte aber weiterhin Repositorykonfiguration und Inline-Ignores berücksichtigen. Native Wrapper und beide direkten Build-Prüfungen erzwingen jetzt zusätzlich `--no-config` und `--no-ignores`; globale Workflow-, Dokument-, Command- und Orchestrierungsregressionen verhindern ein stilles Zurückfallen. |
| CX221-061 | P1 | IMPLEMENTED_PENDING_FINAL | Der native Releasewrapper nahm `git.exe` aus dem vom Aufrufer kontrollierten `PATH`; ein Fake-Git mit Exit 0 konnte Checkoutsauberkeit, Historienvollständigkeit und das Gitleaks-Inventar vortäuschen. Git for Windows wird nun fail-closed aus dem systemweiten HKLM-Installationsvertrag aufgelöst, auf dessen `cmd/git.exe` begrenzt und durch eine strikt einzeilige Git-for-Windows-Versionsausgabe validiert. Caller-PATH besitzt keine Auswahlhoheit mehr. |
| CX221-062 | P2 | IMPLEMENTED_PENDING_FINAL | Der Native-Asset-Downloader validierte nur Start- und finale URL; ein erlaubtes Ziel konnte intern über einen fremden Host oder einen HTTP-Downgrade erreicht werden. Ein eigener Redirect-Handler prüft nun jeden bereits aufgelösten Hop vor dem Folgen gegen denselben HTTPS-/Host-/Credential-Vertrag. Zwei erlaubte Hops bleiben möglich; fremder Host, Downgrade und Userinfo brechen vor dem Download ab. |
| CX221-063 | P1 | IMPLEMENTED_PENDING_FINAL | Die Release-Gate-Sequenz isolierte ihre Werkzeugzustände nicht vollständig: Import-Linter und Ruff erzeugten checkout-lokale Cacheverzeichnisse mit eigener `.gitignore`; eine projektlokale uv-Umgebung sowie pytest- und mypy-Caches hätten denselben Konflikt ausgelöst. Zusätzlich schreibt Hypothesis 6.151.9 dynamisch bestätigt checkout-lokale `.hypothesis`-Cachebytes, in dieser Version jedoch keine eigene `.gitignore`. Das später laufende Provenienz-Gate wies den vermeintlich sauberen Kandidaten bei 64 Prozent der Suite korrekt ab. Der In-Suite-Import-Linter deaktiviert seinen Cache nun programmatisch; CI und lokale Releaseverträge nutzen eine externe uv-Projektumgebung, ein ebenfalls externes `HYPOTHESIS_STORAGE_DIRECTORY`, cachelose Ruff-/Import-Linter-/pytest-Läufe und mypy mit deaktiviertem Windows-Cacheziel `nul`. Wheel- und Sdist-Smoke-Venvs liegen getrennt unterhalb von `RUNNER_TEMP`, niemals im Release-Checkout. Die Regressionen binden die exakten Workflowbefehle, den AST-Aufruf `lint_imports(no_cache=True)`, eine `lstat`-/Reparse-sichere Hidden-Ignore-Inventarisierung und die case-insensitive Windows-Identität verborgener `.gitignore`-Pfade. Damit verhindern Workflow-, Quell- und Hidden-Ignore-Verträge die Rückkehr checkout-lokaler Cachekontrollen; gezielte und vollständige Revalidierung bleiben offen. |

Die zusätzliche Challenge, eine nach dem gelockten Sync lokal manipulierte
Same-Version-Installation von Zizmor oder Pyflakes als eigenen Produktbug zu
führen, wurde nicht übernommen: der frisch mit `uv sync --locked --only-group
release --no-install-project` erzeugte Release-Interpreter samt Umgebung ist wie
Windows, CPython und `uv` ein expliziter Bootstrap-Trust-Root. Ein Angreifer mit
Schreibzugriff auf diesen Trust-Root könnte ebenso Interpreter oder laufenden
Gateprozess ersetzen. Die finale Evidenz muss deshalb aus einer frischen,
gelockten Releaseumgebung stammen; ein bloß vorgefundenes langlebiges Venv
autorisiert keinen Release.

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

Das Native-Manifest enthält bewusst nur die ersten drei GitHub-Assets. Zizmor
kommt aus der gelockten PyPI-Abhängigkeit; das manylinux-Wheel ist ausschließlich
Buildhost-Provenienz und keine Linux-Runtime-Zusage. Diese Werkzeugprovenienz
ersetzt weder aktuelle Kandidatenevidenz noch die finale Wiederholung nach dem
letzten Diff-Freeze.

## 6. MW221-019 sowie MW220-108/-115: Ursachenbeweis und Korrektur

Der alte Test `test_live_repository_state_documents_match_release_version`
verlangte nicht nur Datentypen und Konsistenz, sondern konkrete volatile Werte:
den Branch `fix/v2.21.0-release-blockers`, zwei alte Commit-/Tree-IDs,
`tests_passed is True`, `semgrep_passed is True`,
`housekeeping_done is False` und konkrete Sätze wie „wiederholte reale
Windows-Läufe grün“. Damit prüfte die Suite die Wiederholung einer Behauptung,
nicht deren Wahrheit. Der Test konnte weder den externen GitHub-Releasezustand
beweisen noch einen ehrlichen Übergang von „in Arbeit“ zu „fertig“ tolerieren.

Der neue Vertrag prüft stattdessen:

- vollständiges und typisiertes Frontmatter mit exakt normierten
  `in_progress`-, `candidate_validated`- und `released`-Übergängen;
- ein strikt formatiertes ISO-Startdatum, einen nicht älteren Memory-Refresh
  sowie phasegenaue Gate- und Housekeepingflags;
- maschinenreine, vollständig normierte LIVE-Blöcke ohne freie Statusprosa;
- genau einen neutralen externen Publikationsblock je unveränderlicher
  Verbraucherdokumentation; außerhalb davon ist die Zielversion nur in
  geschlossenen Strukturkontexten wie Git-Pin, Fixbranch, Versionsfeld und
  State-Frontmatter zulässig;
- den exakten Kandidatenbranch oder seinen byteidentischen Zwei-Eltern-Merge;
  nach Veröffentlichung zusätzlich Kandidaten-/Integration-Commit und -Tree,
  exakt benanntes annotiertes Tag sowie einen direkten docs-only
  Housekeeping-Nachfolger;
- vollständige, eindeutige MW220-, MW221- und CX221-ID-Mengen sowie zulässige
  Lifecycle-Statuswerte.

Eine Online-Abfrage des GitHub-Releases gehört bewusst nicht in die hermetische
Unit-Suite. Sie bleibt ein explizites Live-Gate unmittelbar vor Remote-Writes.

## 7. Evidenzmatrix

| Evidenz | Ergebnis | Autorität |
|---|---|---|
| v2.21.0 vollständige Windows/CPython-3.14.7-Suite | 3 failed, 2.000 passed, 43 skipped, 2.204,60 s | dynamischer Ausgangsbeweis; kein PASS |
| Fehlerklassifikation | zwei stale 3.14-Orakel, einmal MW221-007 | dynamisch plus Code-/Diff-Tracing |
| v2.21.0 publiziertes Wheel | realer Fixture-Consumer: 14 completed, 7 killed, 7 survived, keine problematischen Buckets | installierte Zielsystemevidenz für den Ausgangsrelease |
| v2.21.0 GitHub-CI | real ausgeführt und rot: Quality `99647140872`, Ubuntu-Boundary `99647141304`, Windows-Security `99647141196`; MW220-112 bis -114 | tatsächliche Remoteevidenz; ausdrücklich kein CI-PASS |
| v2.21.0 lokale Qualitäts-/Securitygates nach den CI-Fixes | Ruff, Format, mypy 3.14, Import-Linter, Lock, Pip-Audit und kanonisches Semgrep-Gate lokal grün | historische lokale Releasebaum-Evidenz; hebt die rote CI nicht auf und besitzt keine v2.21.1-Autorität |
| v2.21.1 vollständige strikte Arbeitsbaumsuite | Windows/CPython 3.14.7: 2.303 passed, 43 skipped, 0 failed, 40:34 min; `PytestUnhandledThreadExceptionWarning` als Fehler behandelt | vollständige lokale Implementierungsevidenz; sauberer Kandidatencommit noch ausstehend |
| v2.21.1 historische commit-genaue Coverage-Implementierungssuite | Commit `4daed987742d24b420285fec46fc91bc2e1189a4`: 2.303 passed/43 skipped/0 failed; 9.727 Statements, 1.450 Missing, 85 %, 43:51 min | vollständige lokale Implementierungsevidenz für diesen früheren Commit; keine aktuelle Kandidatenautorität |
| v2.21.1 Quality/Dependency-Arbeitsbaumgates | Ruff Check 0, Format 172/172, mypy 39 Dateien/0 Fehler, Import-Linter 1/1 Vertrag, `uv lock --check` 133 Pakete, Pip-Audit 0 bekannte Schwachstellen | lokale Implementierungsevidenz; keine Remote-CI-Behauptung |
| v2.21.1 kanonisches Semgrep-Arbeitsbaumgate | 225 Manifestdateien, 224 Targets, 346 Regeln, exakt 22/22 allowgelistete Testtreffer, 0 unerwartete Findings/Errors/Skipped-Rules/Fixpoint-Timeouts | kanonischer lokaler Securitybeweis; auf Kandidaten- und Integrationscommit zu wiederholen |
| v2.21.1 historisches Native-Release-Gate | sauberer Commit `4daed987742d24b420285fec46fc91bc2e1189a4` in frisch gelockter CPython-3.14.7-Releaseumgebung: actionlint, ShellCheck, Pyflakes, Zizmor regular/pedantic und Gitleaks Worktree/History bestanden | commit-gebundene lokale Implementierungsevidenz für diesen früheren Commit; keine aktuelle Kandidatenautorität und auf dem späteren integrierten Commit zu wiederholen |
| v2.21.1 CX221-059-Dogfood-Recheck | Windows/CPython 3.14.7, vier Worker: Exit 0; `completed` 91/91, 90 killed, 1 Windows-äquivalenter Survivor, 0 timeout/suspicious/skipped/no-tests/type-check/segfault/unchecked, Basis vollständig, 98,9 %, 99,9 s, 0 Runtimeartefakte im Staging | dynamischer Fix- und Testqualitätsbeweis auf dem Arbeitsbaum; integrierte Wiederholung bleibt offen |
| v2.21.1 erster commit-genauer Finalgateversuch | auf Commit `56a94e38bb72f486895ac19f689c77e42b7f0503` bei 64 Prozent nach dem echten CX221-063-Provenienzfehler gestoppt | negative dynamische Evidenz; keine Kandidatenfreigabe und kein Produkt-PASS |
| v2.21.1 GitHub CI | kann billingbedingt nicht anlaufen; dann Status `NOT_EXECUTED` | akzeptierte Evidenzlücke; weder PASS noch FAIL |

## 8. Releaseentscheidung und offene Gates

v2.21.1 bleibt **NO-GO**. Der frühere Windows-/CPython-3.14.7-Arbeitsbaum hat
die vollständige strikte Suite, Coverage, Ruff/Format, mypy, Import-Linter,
Lock/Audit, das kanonische Semgrep-Gate und den Dogfood-Piloten bestanden. Der
commit-genaue Kandidatenlauf deckte danach CX221-063 auf. Noch offen sind dessen
gezielte und vollständige Revalidierung, der neue saubere Kandidatencommit,
Push und Review-Integration, die erneuten Gates und der Dogfood-Recheck auf dem
integrierten Commit, reproduzierbarer Doppelbuild, echte Installed-Artifact-
Smokes, annotiertes Tag und GitHub-Release in genau dieser Reihenfolge.

Eine aus finanziellen Gründen nicht verfügbare neue GitHub-CI blockiert nach der
ausdrücklichen Product-Owner-Entscheidung nicht. Sie darf jedoch an keiner Stelle
als grün, bestanden oder anderweitig positiv belegt bezeichnet werden.
