# Verbindliches Handover an GLM-5.3 — S3-Sanierung mutmut-win

Stand: 9. Oktober 2026, Europe/Berlin. Auftraggeber ist der Product Owner.
Du setzt die von GPT-6 Astra begonnene Sanierung fort. Du beginnst keinen neuen
Review und erklärst den bisherigen Kandidaten nicht zum fertigen Release.
Ziel ist ein nachweislich einsatztauglicher, vollständig qualifizierter Stand.
Der aktuelle Abnahmestatus ist **NO-GO**.

## 1. Oberste Direktiven und Autorität

1. **Windows und exakt CPython 3.14.7.** Kein Linux-/POSIX-Ersatzlauf, kein
   anderer Interpreter und kein pauschales Lockupgrade.
2. **Context7, MAXential und serena-mutmut-win sind Pflichtwerkzeuge.**
   Verwende sie aktiv im nachstehend bestimmten Scope; bloße Erwähnung genügt
   nicht. Das gilt ebenso für alle Projektwerkzeuge, die Astra verwendet hat:
   uv, Git, pytest/Hypothesis/pytest-cov/pytest-benchmark, Ruff, mypy strict,
   import-linter, mutmut-win, kanonische Semgrep-/Native-Wrapper und pip-audit.
   Die Wrapper binden zusätzlich ihre nativen Tools und Zizmor. Kein anderes
   Werkzeug oder MCP-Server mit ähnlich klingendem Namen ersetzt sie still.
3. **Keine Abkürzung der Abnahme.** Ändere keine erwarteten Resultate, Budgets,
   Scopefilter, Ausnahmen, Allowlisten oder Lifecycleflags nur, um Grün zu
   erhalten. Jede sachlich notwendige Anpassung braucht eigenen Vertrag,
   Begründung und Gegenkontrolle. Zeitdruck ist kein technischer Beleg.
4. **Vorbestand bewahren.** Kein reset/clean/stash, kein Checkoutwechsel und
   keine Cache-/DB-/Verdiktlöschung im Original. Keine fremden Prozesse beenden.
   Keine eingefrorenen Reviewdateien oder historischen Receipts umschreiben.
5. **Terminale Evidenz entscheidet.** PASS setzt richtigen Import, unveränderte
   gebundene Inputs, echte Assertions und terminalen Exit voraus. FAIL,
   NOT_EXECUTED und präzise externe Grenzen bleiben sichtbar.
6. **Autonom fortsetzen, nicht autonom behaupten.** Erledige unabhängig
   klärbare Arbeit weiter. Bei einer wirklich fehlenden Entscheidung benenne
   ID, genaue Normstelle, eigene Lesart und konkret benötigte Information.
   Fehlende Toolverfügbarkeit oder Evidenz niemals als erfolgreichen Ersatzlauf ausgeben.

Normreihenfolge: aktuelle ausdrückliche PO-Entscheidungen → finaler S3-Auftrag
und finale Karten → aktuelle Projektverträge → dokumentierte Reviewerklärung
im jeweiligen Scope → historische Berichte/Beobachtungen. Widersprüche
werden dokumentiert und geklärt, nicht durch die bequemere Lesart entschieden.

Die zwei bereits entschiedenen Normfragen werden **nicht erneut aufgerollt**:

- Semgrep **1.180.0** und PyJWT **2.15.1** sind vom PO genehmigt und gelockt.
  Der historische Optionsentwurf mit ausstehender Zustimmung ist überholt.
- Der ausführbare **17-Felder-Lifecycle** bleibt erhalten; **AGENTS.md und
  CLAUDE.md** wurden beide berichtigt. In `in_progress` bleiben insbesondere
  `tests_passed`, `semgrep_passed`, `housekeeping_done` false.

Der frühere Pausencheckpoint bleibt als historische Momentaufnahme erhalten.
Der vom PO in deine Session übergebene Startprompt autorisiert deine
Fortsetzung. Astra und Sol bleiben pausiert; dieses Dokument startet sie nicht.

## 2. Exakter Einstieg und Pflichtlektüre

| Rolle | Verbindlicher Ort / Stand |
|---|---|
| Fortsetzungscheckout | `C:\Users\pmitt\.codex\worktrees\astra-s3-sanierung\mutmut-win` |
| Branch / Remote | `fix/v3.1.0-s3-sanierung`, `https://github.com/pgm1980/mutmut-win.git` |
| Letzter Dokumentcheckpoint vor Handover | `c89cff21c7d20d2c0515312d7495eb50a174725a` |
| Eigene integrierte Code-/Test-/Lock-Gates | `c37398255e71ed0748f48fe53b5a2e1b0f6ebf7d` |
| Separater CLI-/Reuse-Kandidat | `22b2eccd343791aa87d4ae2f3239c6005b9f2a1d` |
| Geschütztes Original | `C:\claude_codex\mutmut-win`, `fef1b61358dd6f860dbc7d9ec353c5334905d02e` |
| Reviewtag | `v3.1.0`, `9426088634589d70bcbbbc49e4d382091c621056` |
| Dauerhafte lokale Evidenz | `C:\claude_codex\mutmut-win-handover\2026-10-09-s3-glm53` |

Der Handover-Commit liegt **nach** c89cff2 und ändert Dokumentation, nicht die
geprüften Produktinputs. Ermittele ihn mit Git; er ist kein neuer Finalgatebeleg.
`HANDOVER-STATE.json`, `SOURCE-TEST-LOCK.json` und `LOCAL-EVIDENCE.json` binden
den Ausgangsstand. Nach dem Push muss `git ls-remote` dem lokalen HEAD entsprechen.
Kein blindes `git pull` oder Zurücksetzen bei Abweichung: erst Ursache und Ownership klären.

Vor der ersten Änderung vollständig lesen:

1. Dieses Dokument und [GLM-STARTPROMPT.md](GLM-STARTPROMPT.md).
2. [Astra-Handover/Auftrag als unveränderte Originalkopie](ASTRA-SANIERUNGSAUFTRAG-ORIGINAL.md).
   Original: `C:\claude_codex\mutmut-win\_docs\reviews\external-review-v3.1.0\sol-cross-cross-review\ASTRA-SANIERUNGSAUFTRAG.md`.
3. Im gleichen S3-Ordner: `FINAL-VERDICT.md`, `BEFUNDKATALOG.md`,
   `FINAL-FINDINGS.json`, `MASTER-REGISTER.json`, `T6-MATRIX.json`,
   `RESTGRENZEN.json`, `REPRODUKTIONSANHANG.md`, vollständiges `SHA256-MANIFEST.json`
   und die für den nächsten Mechanismus referenzierten Reproduktionsbelege.
4. Aktuelle `AGENTS.md`, `CLAUDE.md`, `.sprint/state.md`,
   `_config/development_process.md`, Architektur-/Design-/Testverträge,
   `_docs/architecture spec/adr_layer_contracts_v2.md` und Installationsvertrag
   `_docs/mutmut-win-install.md` im Fortsetzungscheckout.
5. `../PO-PAUSE.md`, `../PLAN.md`, `../SANIERUNGSLEDGER.json`,
   `KARTENINDEX.json` und sämtliche Detailledger der nächsten Arbeitspakete.
6. Reviewerantworten, besonders 019–021, sowie `p5-mutation-plan/DURCHFUEHRUNG.md`,
   `MUTATION-PLAN.json` und `M18-CALLER-SCOPE-ADDITIONAL.json` in der lokalen Evidenz.

Prüfe das **gesamte** S3-Manifest (1192 Einträge am Übergabestand), das
geschützte Endinventar (2489 Einträge) und das Handovermanifest. Einzelne
Stichproben ersetzen diese Integritätsprüfung nicht. Die lokalen Spiegel
tragen unveränderte Bytes; absolute Originalpfade innerhalb alter Receipts
bleiben absichtlich unverändert. `LOCAL-EVIDENCE.json` ordnet sie den Spiegeln zu.

Der Git-Push enthält Implementierung und Handoverdokumente. Rohlogs,
Testdatenbanken, Umgebungen und eingefrorene Reviewbäume gehören zum lokalen
Evidenzteil. Ein neuer Clone auf einem anderen Rechner ist daher allein noch
keine vollständige Übergabe. Fehlende Belege zuerst übertragen/klären.

Das lokale `source-history.bundle` erhält auch historische Agentencommits,
deren IDs nach Cherry-picks nicht unbedingt über den Remote-Sanierungsbranch
erreichbar sind. `WORKTREE-INVENTORY.json` inventarisiert die vorhandenen
Checkouts. Im alten Worktree `astra-s3-paths` liegen noch 12 uncommittete
Entwurfsdateien; sie wurden separat unter `preserved-paths-draft` samt Patch
und Hashmanifest gesichert. Dieser Vorbestand ist **kein** zusätzlicher
aktueller Fixauftrag und darf weder ungeprüft integriert noch gelöscht werden.
Fortsetzung ausschließlich am oben genannten integrierten Sanierungsbranch.

## 3. Was tatsächlich erledigt ist — und was diese Aussage begrenzt

Alle Kandidaten der **50 konkreten Karten** sind integriert: 31
Produktmechanismen, 18 Testschwächen, eine Dokumentabweichung. Das ist eine
Implementierungsbilanz, **keine 50-fache finale Abnahme**. Die 220 ursprünglich
offenen Karten (95 P2, 125 P3) besitzen individuelle Prüfregister; einzelne
haben inzwischen zusätzliche Belege, aber keine pauschale Gruppenfreigabe.

| Bereich | Implementierter / belegter Stand | Weiter erforderlich |
|---|---|---|
| S3-001 Umgebungsreuse | Kontextbindung, Inhaltsgegenlesen und gesunde Reuse-Gegenarme; zuletzt 4 echte Run-/Exportphasen: strict/same 3 Kills/100 %, changed/fresh lax 3 Survivors/0 % | Final integrierte Abnahme und Produktionsmutation; keine Universal-Atomizitätsbehauptung |
| S3-002 Kindcoverage | Kindpfade/Merge und konservative Vollsuite-Rückfälle bei fehlenden Daten; echte Covered-/All-lines-Kontrollen 14 Mutanten, 4 Kills/10 Survivors; weitere Verlust-/Übergangskontrollen | Detailledger `p1-coverage/S3-002-ledger.json` lesen; damalige Commitrollen nicht zum finalen Stand umetikettieren |
| S3-003 CPU-Timeout | CPU-Heuristik liefert keinen bewiesenen Endlosschleifen-Kill; Legacy-Reuse konservativ; endlicher enger/ausreichender Arm und echter unbegrenzter Full-CLI-Arm belegt | Finalintegration/Mutation; Infinite-Arm nicht wegen historischer `review_limits` erneut als fehlend behaupten |
| S3-007 Runtime-Namen | Guard auch im Statsfallback, Eventjournal, Prozesskontrollen; 13 unveränderte CLI-Fälle PASS auf 22b2ecc | Reine Kind-Forced-Fail-Attribution bleibt konservativ; 13 Test-PASS sind nicht 13 autorisierte Kampagnen |
| S3-016 Clean vor Typfilter | Echter Phasenaufruf, aktueller Token, Marker und Exit; identische Tests 2 FAIL/2 deselected → 4 PASS | Kein Beleg eines realen mypy-all-caught-Arms allein durch Filterdouble; Mutation offen |
| S3-020/030 | no_tests widerruft Basis; Junction-Konfiguration wird abgelehnt; Kandidat 26cadb1 integriert, echte CLI-/Exportkontrollen | Neueren `wave4_candidate` öffnen; altes Sammelfeld „No remediation execution receipt yet“ ist überholt |
| Weitere P2/P3 | Atomic/Apply, Collection-Proof, Namespace, Pfad-/Unicode-, JSON-/Preview-, DB-/Browser-, Stats-/Regex-/Template-/Typprüfungskandidaten samt Orakelstärkung integriert | Jede konkrete Karte über `candidate_evidence`/Detailledger einzeln lesen; kein pauschales DONE |
| S3-051/052 Security | Genehmigte Pins; 44 einzeln adjudizierte Semgrep-Signaturen; CI-Audit der frischen vollständigen Lockumgebung | Finaler Gatezyklus nach letzten Änderungen; keine Blanket-Allowlist und keine rückwirkende Ursachenbehauptung |
| Governance | Beide Vertragsdateien auf 17 Felder und genehmigte Pins berichtigt | Keine Releaseflags, Tag-/Main- oder Veröffentlichungsaktion ohne passende Abnahme/Autorisierung |

Eigene Gates auf **c373982**: 80 ausgewählte Vertragstests, Ruff, Format,
mypy strict (`src/` und `scripts/`, 44 Dateien), import-linter, kanonisches
Semgrep, nativer Wrapper und voller Environment-Audit: **PASS**.
Semgrep: 360 Targets, 346 Regeln, 44 exakt begründete erlaubte Findings,
0 unerwartete Findings/Parserfehler/Skips/Fixpoint-Timeouts. Audit: 130
Windows-Abhängigkeiten inklusive pip/packaging, 0 gemeldete Schwachstellen/Skips.
Der Requirementsreport mit 128 Einträgen ist kein gleich großer Nenner.
Advisory 4146 hat keine veröffentlichte erste Fixversion; das aktuelle
Auditergebnis ist kein allgemeiner Sicherheits- oder historischer Ursachenbeweis.

**Nicht ausgeführt am final integrierten Stand:** vollständige pytest-Suite
mit Coverage und Mutation des geänderten Produktionscodes. Die letzten
CLI-Fixturekampagnen ersetzen diese Produktionsmutation nicht.

Historische Fehler bleiben erhalten: P1-Vollsuite 3880 PASS / 6 FAIL /
45 SKIP / 1 XFAIL bei 87 % Coverage; vier veraltete Mockorakel wurden korrigiert,
die genaue historische Ursache zweier Basis-/Exportfehler wurde nicht bewiesen.
S3-001-Benchmark: lokale Normalbasis 10,92 → 21,29 Sekunden, erhebliche Kosten;
Linkarme nicht vergleichbar, keine Host-idle-Garantie. Zwei Markerwarnungen
im externen letzten CLI-Harness sind dokumentiert und nicht verschwunden.

### Das Ledger korrekt lesen

`review_limits`, `source_locations` und `review_reproducer` beschreiben
ursprüngliche S3-Evidenz, nicht automatisch heutige Quellorte oder Restarbeit.
Leere Sammelfelder `red`/`green`/`source_binding` bedeuten nicht, dass verlinkte
Detailledger leer wären. Zuerst `candidate_evidence`, `wave4_candidate`,
`latest_candidate_ledger`, `latest_cli_scope` und aktuelle Gatebindungen öffnen.
`KARTENINDEX.json` ist ein Navigationsindex, kein neues Fehlerurteil.
Überführe bei Abschluss jeder Karte die qualifizierten Details konsistent in
die Hauptbilanz, bewahre aber historische Aussagen als datierte Historie.
Eine bloße Statusänderung schließt keine Karte.

## 4. Verbindliche Reihenfolge mit Austrittskriterien

### Schritt A — Übernahme und Integrität, noch keine Produktänderung

Erste lesende Befehle in PowerShell; jeden Exit prüfen:

```powershell
Set-Location -LiteralPath 'C:\Users\pmitt\.codex\worktrees\astra-s3-sanierung\mutmut-win'
git status --short
git branch --show-current
git rev-parse HEAD
git remote -v
git ls-remote --heads origin refs/heads/fix/v3.1.0-s3-sanierung
git worktree list --porcelain

$handoverDir = Join-Path (Get-Location).Path '_docs\sanierung\s3\glm-5.3'
$handoverManifest = Get-Content -LiteralPath (Join-Path $handoverDir 'SHA256-MANIFEST.json') -Raw | ConvertFrom-Json
foreach ($entry in $handoverManifest.files) {
    $file = Join-Path $handoverDir $entry.path
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.sha256) {
        throw "Handover-Hashabweichung: $file"
    }
}
```

Das prüft nur das Handoverpaket. Das vollständige S3-Manifest, das geschützte
Endinventar und die lokale Evidenz bleiben zusätzlich zu prüfen. Deren
Eintragsschemata unterscheiden sich: S3/Endinventar `files[].path`, der
lokale Spiegel `entries[].mirror`; beide führen SHA256 und Größenbindung.
Keine fehlenden Dateien oder Ausnahmen aus der Schleife herausfiltern.

- Branch/HEAD/Dirty, Worktreeinventar, Source/Test/Lock, Importziel und
  CPython-Version prüfen; laufende eigene Prozesse anhand PID **und Startzeit**
  sowie CWD zuordnen. Fremde Worker erhalten. Existierende Receipts zuerst lesen.
- Handover-/S3-/Spiegelmanifest prüfen, aktuelle Tools verifizieren, Serena
  auf tatsächlichen Fortsetzungscheckout aktivieren. Kein serena-mosaic.
- `GLM-SESSION-START.json` in einem neuen eigenen Evidenzordner schreiben:
  eigene Session-ID, Herkunftscommit, Remote-HEAD, Runtime/Importziel,
  Hashprüfungen, Prozessinventar, erste konkrete Arbeitspakete und Toolgrenzen.
- Das ursprüngliche Ledger kopieren/sichern, dann den neuen Bearbeitungsstatus
  dokumentieren. Die Schlüsselmenge und Typen der 17 Sprintfrontmatterfelder
  erhalten; Werte nur gemäß nachgewiesenem Lifecycle aktualisieren.

**Austritt:** vollständige Herkunft geklärt; fehlende Eingaben präzise erfasst.
Bei ungebundenem Interpreter, fehlendem Lock oder Hashdrift keine abhängige
Produktqualifikation beginnen. Unabhängige Dokumentklärung darf fortgesetzt werden.

### Schritt B — Die fehlende integrierte Vollsuite zuerst ausführen

Eine neue externe Dev+Build-Umgebung gelockt synchronisieren. Den vollständigen
pytest-Coverage-Lauf ohne `-k`, `-m`, Teilpfade oder unbegründete Deselection
ausführen. Externe Coverage-/Hypothesis-/basetemp-Pfade und echte Start/Ende/Exit-
Receipts verwenden. Vorhandener Runner: `p6-integrated-gates/Run-IntegratedGate.ps1`,
Mode `fulltests` war vorbereitet, **nicht ausgeführt**. Vor Wiederverwendung
Hardcodierungen, Pfadlängen und frische Labels prüfen; historische Labels nicht überschreiben.

**Austritt:** terminale komplette Ergebnisliste, Coverage und Hashbindung.
Bei FAIL Ursache und Fehlertyp zuordnen; keine globalen Skips oder Assertion-
Lockerungen. Jeden notwendigen neuen Fix mit Rot → isolierter kausaler Änderung
→ Grün → Rücknahme/Gegenkontrolle durchführen. Noch keine Releasefreigabe.

### Schritt C — Restkarten adjudizieren und tatsächliche Lücken beheben

P1-Restgrenzen und aktuelle Vollsuitefehler zuerst, dann materielle P2,
danach P3 nach `FINAL-FINDINGS.json`. Für die 220 offenen Karten die
individuellen P2-/P3-Register verwenden. Jede Karte erhält ein begründetes
`BESTÄTIGT`, `ABWEICHEND`, `WIDERLEGT` oder eine präzise weiterhin
`UNENTSCHIEDBAR` bleibende Grenze samt fehlendem Input. Eine vorläufige
P-Stufe ist kein bewiesener Defekt. Gleiche technische Mechanismen dürfen
Arbeit teilen, aber keine IDs aus dem Nenner verschwinden.

Für Feldbug 1/2 fehlende Originalinputs sichern/anfordern, keine Ursache
erfinden. Für weitere Codeänderungen alle Aufrufer und Nebenwirkungen prüfen.
Die Auftragsscope-Grenzen zu Collection-Proof, Atomic/Apply und Export aus dem
Astra-Auftrag gelten weiterhin. Ein erwarteter negativer Score-Exit kann ein
bestandener Gegenarm sein; ein positiver Exit allein ist keine Inhaltsabnahme.

**Austritt:** 270 IDs vollständig bilanziert; jede offene Grenze konkret.
Nicht lokal klärbare Feldinputs blockieren nur abhängige Aussagen, nicht alle
unabhängige Arbeit. Materielle offene Abnahmekriterien verhindern die Freigabe.

### Schritt D — Produktionsmutation tatsächlich qualifizieren

`p5-mutation-plan` ist an **9ef9130** gebunden und muss vor Durchführung auf
den dann finalen Source-/Test-/Lockstand neu gebunden werden. Der vorhandene
Regex-Worktree `astra-s3-mutation-regex` steht auf **521ac83**; dort wurde
keine Mutation gestartet. Sauberen neuen Kampagnencheckout bevorzugen oder
den bestehenden kontrolliert aktualisieren; keine behauptete Bindung per Textedit.

23 geänderte Produktionsmodule, 22 mit ausführbaren Änderungen;
`exceptions.py` ist nur Docstring. Plan, Hunkinventar, Schema und zusätzlichen
M18-Aufruferscope lesen. Konkrete Testmengen über Aufrufer und tatsächliche
Aktivierung validieren. Keine pauschale Gleichsetzung „ein Modulname = erreichter Fix“.
23 ist der Ausgangsnenner, keine Obergrenze. Nach weiteren Fixes das gesamte
Änderungsinventar gegen die Ausgangsbaseline neu ermitteln und ergänzen.

- Zunächst seriell, `max_children=1`; Last und Prozessbesitz aufzeichnen.
- Vollständige Population, Run-ID, DB mit Sidecars, erzeugte Source/.py.meta,
  vollständige Tokens, Verdikte, rohe Nenner und tatsächliche Aktivierung sichern.
- Einzelmutantenläufe können aktuelle Resultate ersetzen: Gesamtlauf zuerst
  archivieren. Keine `--force`-Überschreibung historischer Evidenz.
- Mindestens 20 Survivor je Modul, sonst alle; nachvollziehbare Auswahl plus
  alle sonst nicht erreichten geänderten Mechanismen. Äquivalenz braucht echte
  Runtimegegenkontrolle. 0 Kills sind ein Prüfauftrag, kein automatischer Defekt.
- Score mindestens 80 %; darunter rohe Quote, Population, technische Ursachen
  und Rest explizit berichten. Keine stillen Nennerkorrekturen und kein
  `--treat-timeout-as-kill` als Quotenkosmetik.
- Selbst ausgeschlossene `hit_recording`/`runtime_names`, dekorierte Bodies
  und globale Templates erreichen Standardoperatoren teilweise nicht.
  **0/0 ist nicht 80 %; Helperquoten qualifizieren diese Bodies nicht.**
  Erforderliche Adapter erst begründen, Äquivalenz/Aktivierung real belegen;
  keine Pflicht zu genau einer Alias-/Extraktionsmethode und keine Blanket-Ausnahme.
  Fehlende Operatorqualifikation ausdrücklich offen halten. Manuelle Sabotage
  ist gesonderte kausale Evidenz, keine Standardmutantenpopulation.
- `--paths-to-mutate` ist ein Subset und nicht mit `--min-score` kombinierbar;
  keine erfundene CLI-Syntax. Subsetkampagne liefert keine positive
  projektweite Export-/Releaseautorität. `results --all` ist Text, kein
  unterstellter JSON-Modus. Details/Argumentarrays im gebundenen Plan prüfen.

**Austritt:** terminale tatsächliche Kampagnen mit qualifiziertem Scope und
Survivorbilanz. Instrumentierbarer, nicht ausgeführter Code bleibt NOT_EXECUTED.
Offene Operatorgrenzen werden nicht durch einen erreichten anderen Modulscore verdeckt.

### Schritt E — Finale Integration und eigene Finalgates

Nach allen Fixes und Teststärkungen einen finalen Source-/Test-/Lockstand
binden. Vollsuite+Coverage, Ruff, Formatcheck, mypy strict, import-linter,
kanonisches Semgrep, nativer Wrapper, vollständiger Dependency-Audit und
Mutationsevidenz müssen diesen Stand tragen. Wird danach relevante Source,
Testpopulation oder Lock geändert, betroffene Evidenz neu erheben; endgültiger
Abschluss braucht einen konsistenten integrierten Gatezyklus.

Skips/Xfails, Timeout-/Prozess-/Hostprobleme, Parserfehler, fehlende Reports,
unvollständige Basis und ungetestete Teile im Fazit ausweisen. Refabhängige
Governancefehler am tatsächlichen Branchvertrag prüfen; keinen Tag-Main-
Vergleich per gefälschter Ref lösen. Native/semgrep Wrapper nie umgehen.

**Austritt:** nachvollziehbares GO oder weiterhin ehrliches NO-GO mit IDs,
Restgründen und genau nächster Aktion. Ein Git-Push ist keine Releasefreigabe.

## 5. Werkzeuge, Umgebungen und Agenten

| Werkzeug | Verbindliche Verwendung |
|---|---|
| serena-mutmut-win | `initial_instructions`, aktives Projekt prüfen; `get_symbols_overview` vor neuer Datei, `find_symbol`/`find_referencing_symbols` vor Änderung; kein Grep für Symbole |
| Context7 | Vor neuen/unsicheren APIs und Versionsverhalten `resolve-library-id` → `query-docs`; Quellen/Version und angewandte Aussage festhalten |
| MAXential | Architektur/Softwaredesign mindestens 10 think-Aufrufe, komplexer Algorithmus 8, einfache Abwägung 3; bei Korrektur revise, echte Alternativen branch/merge; prüfbare Entscheidung dokumentieren |
| Git / PowerShell | Branch/HEAD/Hashes/Prozesse/Receipts; native Windows-Pfade; gezieltes Add statt blindem `git add -A` auf Original |
| uv | Alle Python-/Test-/Toolausführungen über `uv run`; gelockter Sync, keine Auto-Upgrades |
| pytest-Ökosystem | Reale Unit-/Integration-/CLI-Kontrollen, Hypothesis am Produkt, Coverage, Benchmarks nur für belegte Performanceaussagen |
| Ruff / mypy / import-linter | Alle betroffenen Dateien und integrierte Contracts, 0 Findings/Errors; keine Regelentfernung als Fix |
| mutmut-win | Tatsächliche neue/geänderte Produktionspfade mit vollständiger Population und Grenzen |
| Release-Wrapper / pip-audit | Vollständiger Git-owned Scope und vollständige Lockumgebung; keine Raw-/Teilscan-Abnahme |

Bei Toolausfall zuerst Fehler und aktiven Projektzustand dokumentieren.
Ein begründeter Read-Fallback kann Navigation ermöglichen, ersetzt jedoch
keinen geforderten Gate-PASS. Keine simulierten Toolantworten.

Pro **unabhängigem Gate** frische absolute externe `UV_PROJECT_ENVIRONMENT`.
Extern auch `HYPOTHESIS_STORAGE_DIRECTORY`, `COVERAGE_FILE`, pytest-basetemp,
`TEMP`/`TMP`, `PYTHONPYCACHEPREFIX`, uv/Ruff/mypy-Caches. `UV_LINK_MODE=copy`.
Im Releasecheckout keine `.venv` und keine Werkzeugcaches mit eigener `.gitignore`.
Innerhalb zusammengehörigem Run/Reuse/Results/Export bleibt das komplette
geerbte Environment konstant, außer der gezielt variierten Eingabe. Receipt-
Labels dürfen nicht nebenbei die Basis verändern. Keine Umgebungssecrets in Klartext loggen.

Die folgenden Befehle sind **Arbeitsanweisungen, keine bereits ausgeführten
GLM-Gates**. Je unabhängigem Gate eine frische externe Umgebung herstellen;
dessen Sync und anschließender Run verwenden dieselbe `UV_PROJECT_ENVIRONMENT`.
Runtimebindung prüfen; bei Syncfehler keinen Gate-PASS setzen.

| Zweck | Sync / Ausführung |
|---|---|
| Dev+Build | `uv sync --locked --extra dev --group build` |
| Vollsuite | `uv run --no-sync pytest --cov=mutmut_win --cov-report=term-missing -p no:cacheprovider --basetemp <EXTERNER-NEUER-PFAD>` |
| Lint | `uv run --no-sync ruff check --no-cache .` |
| Formatprüfung | `uv run --no-sync ruff format --no-cache --check .` |
| Typen | `uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/` |
| Architektur | `uv run --no-sync lint-imports --no-cache` |
| Securityumgebung | `uv sync --locked --only-group security --no-install-project` |
| Securitygate | `uv run --no-sync python -I scripts/semgrep_release_gate.py` |
| Releaseumgebung | `uv sync --locked --only-group release --no-install-project` |
| Native Gate | `uv run --no-sync python -I scripts/release_native_gate.py` |
| Voller Auditaufbau | `uv sync --locked --all-extras --all-groups --no-install-project` |
| Voller Audit | `uv run --no-sync pip-audit --strict --progress-spinner off --format json` |

Die Runtimeprobe muss `sys.platform == 'win32'`, `sys.implementation.name == 'cpython'`,
`sys.version_info[:3] == (3, 14, 7)`, Interpreterpfad und tatsächlich
importiertes `mutmut_win.__file__` prüfen. Für produktlose Security-/Release-
Umgebungen nur die dort passende Runtime-/Toolbindung verlangen.
Die native Prüfung verwendet HKLM-Git, actionlint 1.7.12, ShellCheck 0.11.0,
Gitleaks 8.30.1 und Zizmor 1.30.0 offline regular/pedantic gemäß aktuellem Wrapper.

Unabhängige Aufgaben parallel delegieren; parallele Editagenten brauchen
physisch getrennte Worktrees. Jeder Prompt enthält **KONTEXT, ZIEL,
CONSTRAINTS, MCP-ANWEISUNGEN, OUTPUT** plus den vollständigen Projektstandards-
Block aus AGENTS.md. `max_turns` nach Vertrag; unterstützt die konkrete API
dieses Feld nicht, ein explizites Schrittlimit im Prompt dokumentieren und
selbst überwachen. Keine erfundenen API-Parameter. Nach Rückkehr Kernaussagen
und geforderte Gates selbst verifizieren. Höchstens zwei gezielte Retries;
danach Ursache selbst lösen oder konkrete externe Grenze berichten.

uv-Befehlsverhalten wurde für dieses Handover mit Context7 anhand der
[offiziellen uv-Projektdokumentation](https://docs.astral.sh/uv/concepts/projects/sync/)
geprüft. Der Projektvertrag und der gelockte Windows-Aufbau bleiben führend.

## 6. Reviewerkanal und bereits erhaltene Entscheidungen

Astra-Session: `01a11fac-70d2-7880-8a58-8db2ac2df94e`.
Sol-Session: `01a11c92-5bd7-7290-ba30-84ef23c1c1d6`, host `local`,
Titel **Erstelle konsolidiertes S3-Review**. Sol hat seinen begonnenen Block
mit Antwort021 beendet und pausiert. Die Antworten liegen im Evidenzroot;
sein Pausecheckpoint liegt im `sol-pause`-Spiegel.

Seine Prüfergebnisse sind **keine finale Freigabe des späteren c373982**.
Insbesondere Security-Option 9bb1942 und die spätere Root-Adjudikation strikt
unterscheiden. Sols alte verkürzte Fehlermeldung zeigte 2/2 Beispiele; die
vollständige Diagnose hatte **19 missing / 20 extra**.

Zuerst vorhandene Antworten lesen. Sol nicht allein aufgrund der historischen
Kanalautorisation aus seiner ausdrücklich angeordneten Pause wecken. Wenn
eine neue fachliche Rückfrage wirklich nötig ist, dem PO die gebündelte Frage
zur Weiterleitung/Wiederaufnahme vorlegen. Nach ausdrücklicher Freigabe:
`mcp__codex_app__send_message_to_thread`, obige IDs, `prompt`, **kein** model
oder thinking. Fehlt dieses Werkzeug in GLMs Oberfläche, nicht ausgeben,
dass eine Nachricht gesendet wurde. Jede Frage enthält eigene Session-ID,
S3-/Register-ID, absoluten Pfad und genaue Stelle, eigene Interpretation,
Source/Receipt und konkreten Entscheidungspunkt. Versand und Antwort im Ledger.

## 7. Die 21 Arbeitsregeln — unverändert aus dem Astra-Handover

Der folgende Block wird wortgleich übernommen. Ergänzende GLM-Anweisungen
stehen außerhalb. `HANDOVER-VALIDATION.json` bindet Originaldatei und Blockhash.

<!-- ASTRA_RULES_BEGIN -->
1. **Rot vor Fix:** Sichere den mechanismusspezifischen Regressionstest und seinen Lauf gegen die unveränderte Fehlerquelle, bevor Du den Fix implementierst. Binde Commit, Sourcehash, Node-ID und erwartete Assertion. Ein Importfehler, eine fehlende API oder ein defektes Double ist kein passender Rotbeweis. Erhalte die zeitliche Trennung auch in der Commitfolge, sobald Commits für die Initiative autorisiert sind.
2. **Ledger aus Receipts:** „Verifiziert“ setzt valide Rot- und Grün-Receipts zur betreffenden Gruppe voraus. Prüfe Sourcebindung, Node-ID, terminalen Exit und tatsächlichen Fehlergrund. Eine hartkodierte Erledigtliste oder ein Verweis auf einen solchen Ledger genügt nicht.
3. **Kausale Gegenprobe:** Setze nur den relevanten Fix in einer isolierten Kopie zurück und führe die passenden Tests aus. Der neue Schutz muss rot werden; die wiederhergestellte Version muss grün sein. Ein vollständiger historischer Parentzustand wird nur behauptet, wenn er tatsächlich rekonstruiert wurde. Revert-, Reset- oder Clean-Operationen im schmutzigen Original sind ausgeschlossen.
4. **Abschluss an Evidenz binden:** Ein Issue oder Arbeitspaket ist erst fachlich geschlossen, wenn Akzeptanzkriterien, Receipts und offene Restgrenzen vollständig sind. Schließe externe Issues nur im vom PO autorisierten Arbeitsumfang.
5. **Mechanik vollständig suchen:** Nutze Serena `find_symbol` und `find_referencing_symbols` für die betroffene Funktion und ihre Aufrufer. Prüfe bekannte Nachbarstellen. `search_for_pattern` ist nur für passende Nicht-Symbol-Muster zulässig; keine Symbolsuche per Grep. Liste behandelte und bewusst ausgeschlossene Produktionspfade.
6. **Reale Fehlerklassen prüfen:** Konsultiere Context7 bei unsicheren APIs. Prüfe tatsächlich erreichbare Ausnahmearten und Windows-Fehlerbedingungen einschließlich Ziffernlimit, Rekursion, fehlendem Programm und Sharing-Violation. Ein pauschaler Catch darf keine Fehler verschlucken oder Autorität erzeugen.
7. **Neue Parameter verdrahten:** Verifiziere jede Produktionsaufrufstelle. Ein Parameter in einer Signatur ist kein implementiertes Verhalten. Tests müssen die Produktionsverdrahtung erreichen.
8. **Nebenwirkungen protokollieren:** Dokumentiere je Fix Änderungen an Ausnahmetyp, Exitcode, JSON/stdout/stderr, Retryverhalten, Interruptzuständen, Pfadidentität, Reuse-/Exportautorität und Ressourcen. Prüfe normale Erfolgsarme und die betroffenen Windows-Pfadformen. Nicht jeder Fix benötigt alle denkbaren Pfadvarianten; begründe den gewählten Scope.
9. **Orakel am Vertrag ausrichten:** Wenn Ergebnisinhalt oder Autorität Gegenstand des Tests ist, prüfe Verdikt je Mutant, Run-/Basisstatus, Score und Artefaktinhalt zusätzlich zum Exit. Ein ausdrücklich vertraglicher Exitcode-Smoke-Test darf bestehen bleiben, qualifiziert aber keine vollständige Inhaltsabnahme.
10. **Unabhängige Erwartungen:** Leite erwartete Grenzen nicht aus genau derselben Produktkonstante oder Formel ab. Ein Mock darf die zu prüfende Produktfunktion nicht ersetzen. Ein sinnvoller Seam ist zulässig, wenn sein Scope ausdrücklich benannt ist und mindestens ein unabhängiger realer Gegenarm die Aussage trägt.
11. **Mutanten wirklich aktivieren:** Verwende den vollständigen Runtime-Namen `<modul>.<funktion>__mutmut_<n>`. Kontrolliere Importpfad und erzeugtes Token. Derselbe Test ist ohne Mutante grün und mit der nicht äquivalenten Mutante aus dem erwarteten Grund rot.
12. **Properties am Produkt prüfen:** Rufe tatsächliche Produktfunktionen auf. Prüfe relevante Eingabeklassen mit Hypothesis. Eine passende Sabotage oder echte Mutante muss die Property verletzen. Eine nochmals inline berechnete Formel ist kein Produktbeleg.
13. **Abdeckungsbehauptungen belegen:** Für jede im Test genannte M-ID muss ein konkreter Mechanismus und wirksamer Schutz nachgewiesen sein. Eine Dokumentkorrektur benötigt einen passenden Dokument-/Vertragstest und keinen erfundenen Src-Rotbeweis.
14. **Testharness robust halten:** Arbeite in eigenen temporären Projekten; bediene Kindprozess-Pipes oder leite in Dateien um. Schließe Prozessbäume, Job-Handles, Queues und Executor auch bei Fehler und Interrupt. Prüfe vorhandene Worker vor einem Neustart. Zeitbudgets brauchen Lastbindung und eine nachvollziehbare Grundlage.
15. **Widerlegung mit Gegenprobe:** Decke den tatsächlichen Grenzfall und den gleichen Source-/Runtimevertrag ab. Ein Ersatzobjekt mit anderen Semantiken widerlegt keinen Befund im unterstützten Runtimevertrag.
16. **Umgebungsursachen trennen:** Prüfe bei strittigen Installations-, Framework- oder Toolhypothesen einen zweiten isolierten, korrekt gebundenen Kontrollaufbau. Halte Commit, Worktree, Lock, Venv und Editable-Ziel fest. Zwei aktuelle grüne Aufbauten erklären keine historische rote Umgebung ohne deren vollständige Rekonstruktion.
17. **Anomalien sichtbar berichten:** `RecursionError`, fehlgeschlagene Fälle, „basis changed“, Teilabbrüche, fehlende Exitdateien und INVALID-Starts gehören in die Zusammenfassung. Historische oder vorbereitete Belege dürfen nicht als aktueller terminaler PASS erscheinen.
18. **Mutation-Scope begründen:** Wähle die Tests so, dass die betroffene Produktionsmechanik erreichbar und der Mutant aktiv ist. Für eine Modulabnahme reichen einzelne Dateien nur mit begründetem Scope. Dokumentiere ausgeschlossene Contract-Tests und die vollständige Population.
19. **Survivor adjudizieren:** Prüfe je betroffenem Modul mindestens 20 Survivor, falls so viele vorhanden sind; andernfalls alle. Ziehung, Nenner, volle IDs und Rest angeben. Unterscheide äquivalent, reinen Diagnosetext und durch bestehende beziehungsweise neue Tests tötbar. Ein „äquivalent“-Urteil braucht einen geeigneten Lauf im echten Runtimevertrag.
20. **Killrate zur Untersuchung nutzen:** 0 Kills sind ein Anlass, Erreichbarkeit, Aktivierung und Äquivalenz zu prüfen. Erst danach Testlücke oder Äquivalenz urteilen. Eine niedrige Quote darf weder Testqualität rechtfertigen noch automatisch als universeller Produktfehler gelten.
21. **Releasezustand integrieren:** Prüfe `.sprint/state.md`, Lockversion, Zielbranch und refspezifischen Governancevertrag. Synchronisiere gelockt in frische externe Umgebungen. Dev- und Build-Voraussetzungen müssen für den tatsächlichen Gatebefehl vorhanden sein. Erzeuge keine `.venv`, Hypothesisbytes oder Werkzeugcaches im Releasecheckout; bewahre vorbestehende Originalartefakte.

<!-- ASTRA_RULES_END -->

## 8. Abgabeformat und Schutz vor falschem Abschluss

Je S3-ID: Klasse/Priorität, aktueller vertraglicher Mechanismus, Commit und
1-basierte Quellorte, tatsächliche Source/Test/Lockhashes, Rot-/Grün-/Rücknahme-
und gesunde Gegenarme, Produktionsaufrufer, Nebenwirkungen, Gatebelege,
Mutationspopulation/Aktivierung/Score/Survivor und konkrete Restgrenzen.
Jedes Receipt benötigt Kommando, CWD, Interpreter/Importziel, Start, Ende,
Exit, Sourcebindung vor/nach sowie vollständige Ergebnis- und Fehlergründe.

Vor deiner Abschlussmeldung beantworte belegbar:

- Sind exakt alle 270 S3-IDs erhalten und einzeln bilanziert?
- Ist jeder PASS ein auffindbares terminales Ergebnis im behaupteten Scope?
- Sind die komplette Coverage-Suite und alle nötigen Finalgates am finalen
  integrierten Stand gelaufen, ohne historische Teilgreens zusammenzurechnen?
- Sind 23 Moduländerungen plus sonstige geänderte ausführbare Gate-/Workflow-
  Flächen berücksichtigt, Doc-only und Operatorgrenzen ehrlich getrennt?
- Sind gesunde P1-Kontrollen, negative Autoritätsarme und Cleanup nachgewiesen?
- Sind bekannte Findings, Skips/Xfails, niedrige Rohquoten, fehlende Feldinputs
  und nicht ausgeführte Prüfungen im Schlussbericht sichtbar?
- Sind Original/Frozen-Bestand unverändert, eigener Checkout sauber und
  eigene Worker beendet? Sind Commit und Remote exakt gebunden?

Wenn eine erforderliche Antwort fehlt, kein „fertig“, kein grünes
Gesamturteil und keine Abschlussflags. Weiterarbeiten, soweit möglich;
andernfalls präzises NO-GO mit noch ausstehender Aktion liefern.
Ein Handoverdokument ersetzt die technische Prüfung seiner Ausführung nicht.
