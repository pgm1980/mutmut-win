# Arbeitsauftrag an GPT-6 Astra — zweite Sanierungsinitiative für mutmut-win

**Finaler Arbeitsauftrag.** Der Product Owner hat GPT-6 Astra als Empfänger bestimmt. S3 ist abgeschlossen und mit dem vollständigen Manifest gebunden. Die historischen Berichte bleiben erhalten.

## Auftrag und verbindliche Ausgangsbasis

Du übernimmst die Bugfixing- und Sanierungsinitiative für **mutmut-win v3.1.0**. Behebe die belegten Produktfehler, stärke die erforderlichen Testorakel und kläre offene Verifikationsfragen. Ein Releaseabschluss benötigt eigene terminale Nachweise der tatsächlich finalen Version.

- Repository: `C:\claude_codex\mutmut-win`.
- Plattformvertrag: ausschließlich Windows und **exakt CPython 3.14.7**.
- S3-Reviewobjekt: Tag `v3.1.0`, Commit `9426088634589d70bcbbbc49e4d382091c621056`.
- Main beim S3-Start: `fef1b61358dd6f860dbc7d9ec353c5334905d02e`. `src`, `tests`, `pyproject.toml` und `uv.lock` waren zwischen diesen beiden Commits identisch.
- S3-Ordner: `C:\claude_codex\mutmut-win\_docs\reviews\external-review-v3.1.0\sol-cross-cross-review`.

Lies zuerst `FINAL-VERDICT.md`, `FINAL-FINDINGS.json`, `MASTER-REGISTER.json`, `T6-MATRIX.json`, `REPRODUKTIONSANHANG.md` und `SHA256-MANIFEST.json` im S3-Ordner. Prüfe das vollständige Manifest. Ergänzende genaue Grenzen stehen in `RESTGRENZEN.json`; die Karten in `FINAL-FINDINGS.json` sind für die finale Priorität maßgeblich.

Prüfe anschließend den aktuellen Branch, HEAD, Dirty-Zustand, Source-/Lockhashes, laufende Prozesse und bereits vorhandene Receipts. Der Originalcheckout enthielt schon vor S3 fremde ungetrackte Artefakte, gelöschte Dokumente und ignorierte Caches. Bewahre diesen Vorbestand. Verwende für Implementierung einen isolierten sauberen Checkout oder Worktree. Die vier fremden Reviewordner, der Feldbericht, die ursprünglichen Prompts und das Handover sowie die versiegelte S3-Evidenz bleiben erhalten.

Ein `UNENTSCHIEDBAR`-Eintrag ist zuerst ein Prüfauftrag. Seine vorläufige P-Stufe macht ihn nicht zu einem bewiesenen Produktfehler. Dedupliziere über den technischen Mechanismus und die Register-IDs. Eine bestätigte Testschwäche ist von einem aktuellen Src-Defekt zu unterscheiden.

Der Abschlussstand umfasst **31 belegte Produktmechanismen**, davon **drei P1**, **18 Testschwächen**, eine Dokumentabweichung und **220 offene Verifikationskarten**. Das S3-Gesamturteil lautet **NO-GO**. Die ungekürzte Tag-Vollsuite endet **Exit 1**, mit **3860 passed, 1 failed, 45 skipped, 1 xfailed und 87 % Line-Coverage**. Der einzelne Fehler ist die refabhängige Governance-Assertion in `test_release_supply_chain.py:547`; sie wird nicht als zusätzlicher Src-Tagdefekt ausgegeben. Alle fünf DB-Nachprüfungspaare sind terminal: vier erkannte Nichtäquivalente, eine äquivalente SQL-Großschreibung. Ruff, Format, mypy, Importcontracts und nativer Wrapper bestehen im frischen Tag-Scope; der kanonische Semgrep-Wrapper scheitert in zwei Läufen. Der ungefilterte Dependency-Audit meldet 14 Advisories; ein Policy-PASS ignoriert diese 14. Diese Werte sind Ausgangsevidenz und keine Abnahme Deiner späteren Änderungen.

Original-/Frozen-Integrität ist mit genauer Vorzustandsgrenze geprüft: Originalstatus unverändert, 15/15 ausgewählte T0-Eingaben, S1b 123/123 und aktuelles S2b 2125/2125 manifestgebundene Dateien. Für S1a/S2a wird ohne vollständiges Vorhermanifest kein rückwirkender Vollbeweis behauptet. Das geschützte Endinventar `evidence/logs/t7-protected-end-inventory.json` bindet 2489 Dateien als zusätzliche zukünftige Erhaltungsbaseline.

## Direkter Klärungskanal zum finalen Reviewer

**PO-Anweisung vom 9. Oktober 2026:** Bei Unklarheiten in den Übergabedokumenten, Rückfragen zu Befunden oder weiterem Klärungsbedarf soll die GPT-6-Astra-Sanierungssession dem finalen Reviewer **GPT-6.1 Sol** direkt eine Nachricht schicken. Der PO autorisiert diese fachbezogenen Rückfragen ausdrücklich. Erteile diese Anweisung auch Deinen Subagenten; die Hauptsession bündelt deren Fragen.

Verbindliches Ziel ist diese bestehende Review-Session:

- Titel: **Erstelle konsolidiertes S3-Review**.
- Technische Thread-/Session-ID für den Nachrichtenaufruf: **`01a11c92-5bd7-7290-ba30-84ef23c1c1d6`**.
- Host: **`local`**.
- [Review-Session öffnen](codex://threads/01a11c92-5bd7-7290-ba30-84ef23c1c1d6).

Verwende die native Codex-Nachrichtenfunktion **`mcp__codex_app__send_message_to_thread`**, beziehungsweise das auf Deiner Oberfläche verfügbare gleichwertige Nachrichtenwerkzeug. Übergebe die obige ID als `threadId`, `hostId="local"` und den vollständigen Klärungstext als `prompt`. Lasse `model` und `thinking` weg, damit die Review-Session ihre Einstellungen behält. Prüfe die Rückmeldung des Werkzeugs; ein fehlgeschlagener Versand ist keine übermittelte oder beantwortete Frage. Eine neue Review-Session ist dafür nicht erforderlich.

Jede Rückfrage enthält Deine eigene Thread-ID, die betroffenen S3-/R-/M-IDs, den absoluten Dokumentpfad mit 1-basierter Zeile oder Kapitel, die genaue Unklarheit, Deine bisherige Interpretation und gegebenenfalls den gebundenen Receipt beziehungsweise Sourcehash. Formuliere die konkrete fachliche Entscheidung, die Du klären möchtest. Sammle zusammengehörige Fragen in einer Nachricht; unterscheide Verständnisfragen von neuen technischen Gegenbelegen. Setze unabhängig klärbare Arbeit fort und lasse die betroffene Entscheidung bis zur Klärung offen.

Beispiel für `prompt`:

> PO-autorisierte Rückfrage aus der GPT-6-Astra-Sanierung zu S3-XXX / R-YYYY. Absender-Thread: [eigene ID]. Dokument: [absoluter Pfad], Zeile/Kapitel: [Ort]. Unklarheit: [präzise Frage]. Bisherige Interpretation: [Lesart]. Eigener Beleg: [Receipt und Sourcebindung]. Bitte kläre [konkreter Entscheidungspunkt].

Dokumentiere die Frage und die erhaltene Klärung im Sanierungsledger. Eine Antwort erläutert die vorhandene S3-Evidenz oder bezeichnet nötige zusätzliche Prüfung; sie ersetzt weder Deinen eigenen Rot-/Grünnachweis noch ein finales Gate. Die versiegelten S3-Dateien bleiben erhalten. Ergänzende Klärungsreceipts entstehen in einem neuen Sanierungsordner.

Die Ziel-ID, der Titel und der Host wurden am 9. Oktober 2026 über die aktuelle Desktop-Threadliste geprüft. Die Aufruffelder stammen aus dem in dieser Session verfügbaren nativen Werkzeugvertrag. Der Öffnungslink folgt dem dokumentierten [Desktop-Threadlinkformat](https://learn.chatgpt.com/docs/app/commands).

## Was aus Fables Beurteilung beibehalten werden soll

Der PO verlangt ausdrücklich, die Erfahrungen aus **Fable 5.1, `REVIEW-fable-5.1.md`, Abschnitt 4** in diese Initiative mitzunehmen. Die Originalquelle liegt unter `C:\claude_codex\mutmut-win\_docs\reviews\external-review-v3.1.0\fable-5.1\REVIEW-fable-5.1.md:313` und bleibt eingefroren. Nachfolgend sind ihre Arbeitsregeln auf GPT-6 Astra und die S3-Ergebnisse angepasst.

Fable bewertet die bisherigen Codefixes überwiegend positiv und nennt präzise Fixorte, vorhandene echte Rotbeweise, die Fail-closed-Grundhaltung und nachvollziehbare M-ID-Kommentare als Stärken. Die dortigen Zahlen **24 geprüfte Fixorte und 22 Rotbeweise** sind Angaben dieses Erstberichts, keine zusätzliche S3-Vollprüfung aller Gruppen. Bewahre funktionierende Fixes und nachweislich wirksame Backstops. Erhalte insbesondere den Widerruf von Autorität bei Interrupt, die Exportsperre bei unvollständiger Basis und klare Domänenfehler.

Fables zentrale Kritik betrifft **Nebenwirkungen, Nachweisführung und Orakelstärke**. Diese drei Punkte werden für Astra zu prüfbaren Abnahmebedingungen. Aussagen über die Leistungsfähigkeit einzelner Modelle sind dafür nicht erforderlich.

| Erfahrung aus Fable §4.2 | Verbindliche Umsetzung für Astra | S3-Präzisierung |
|---|---|---|
| Verifikationsstatus ohne zugehöriges Artefakt | Ein Status entsteht nur aus auffindbaren, sourcegebundenen Rot-/Grün-Receipts mit passenden Node-IDs. | Die pauschale Aussage „17 Gruppen ohne jeden Test“ ist zu weit. Die Population enthält auch Dokumentkorrekturen; drei aktuelle kausale Fixgegenproben sind geschützt. Jede Gruppe einzeln prüfen. |
| Fix ohne Nebenwirkungsprüfung | Fehlerkanäle, Retries, Interrupt-Halbstände, Ressourcen und gesunde Positivarme gehören zur Fixabnahme. | AF-01, AF-04/B-02 und AF-05 sind unterschiedliche Abläufe. Erhaltenes Stable-Backup ist kein irreversibler Originalverlust. |
| Fix nur an einer Fundstelle | Alle Produktionsaufrufer und Nachbarstellen derselben Mechanik identifizieren, behandeln oder begründet ausschließen. | Ein neuer sicherer Helper genügt nicht, wenn davor noch ein unbedingtes Cleanup ausgeführt wird. |
| Behauptung ersetzt Messung | Widerlegungen, Äquivalenz und historische Ursachen benötigen geeignete Gegenkontrollen. | Aktuelle Pydantic-/Textual-Korridore funktionieren. Die Ursachen der historischen 136/20-Fails bleiben offen. |
| Anomalien nur im Rohlog | Fehler, unvollständige Basis, falsche Sourcebindung, Abbrüche und ausgeschlossene Fälle stehen auch im Receipt-Fazit. | Der historische DB-Score 16,4 % stammt von einem anderen Commit und einer fehlerhaften Stats-Phase; er qualifiziert den Tag nicht. |
| Schwache oder tautologische Orakel | Inhalt und Autorität prüfen; tatsächlichen Produktcode und voll qualifizierte Mutanten aktivieren. | Lokale Sabotagebelege sind keine zusätzlichen P1-Produktfehler. Vorhandene fremde Backstops berücksichtigen. |
| Feste Budgets und fehlendes Aufräumen | Budgets begründen, Last dokumentieren, Pipes bedienen und Prozessbäume/Handles/Queues zuverlässig schließen. | Ein Lastfehler allein beweist keinen deterministischen Produktfehler und keine universelle Performancezahl. |
| Mutation-Gates als Rechtfertigung | Erreichbarkeit, Aktivierung, Population und Survivor einzeln untersuchen. | **0 Kills beweisen allein keine Testlücke.** S3 hat einen Survivor unter dem echten `sys.version_info` als äquivalent bestätigt. |
| Release-Hygiene | Source-, Ref-, Lock- und Umgebungsvertrag explizit prüfen. | Der Release-State-Test hängt an beweglichen Refs. Ein historischer Tag muss nicht der heutige Main-Tip sein. S3 synchronisierte die gelockte Build-Gruppe für die Wheel-Tests. |

## Die 21 Arbeitsregeln aus Fable §4.3, für Astra präzisiert

Die folgende Nummerierung erhält die Zuordnung zur Originalquelle, Zeilen 340–384. Sie übernimmt die brauchbaren Kontrollen und korrigiert die in S3 erkannten Absoluta.

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

## Reihenfolge und konkrete Fixabnahme

**Zuerst die drei P1-Produktmechanismen S3-001 bis S3-003.** Für jeden Fix: unveränderte Rotkontrolle, kausale Änderung, Grünkontrolle, gesunder Gegenarm und vollständige CLI-/Run-/Scorebindung.

- **S3-001, Umgebungsreuse:** S3 zeigt strict 3 Kills/100 % → lax Reuse 3 Kills/100 %, vollständige Basis und Mindestscore-Exit 0; derselbe lax Neulauf zeigt 3 Survivors/0 % und Exit 1. Verdiktrelevante Eingabeänderungen dürfen keinen identischen Kontext vortäuschen. Eine erweiterte Allowlist ist ohne konservativen Vertrag für unbekannte relevante Inputs kein Vollständigkeitsbeweis. Sichere gesunden Reuse; protokolliere Hashbindungen und keine unnötigen Umgebungs-Klartexte.
- **S3-002, Kindcoverage:** Die unterstützte Option `mutate_only_covered_lines=true` verliert im echten Spawnkind ausgeführte Linien: 3 Kills/100 %/grünes Mindestscore-Gate gegenüber 14 Mutanten/4 Kills/10 Survivors/28,57 %/rotem Gate. Default ist false. Binde Parent-/Kindmessdaten, Pfadidentität und Mergevollständigkeit. Fehlende Messdaten dürfen das autorisierte Universum nicht still verkleinern.
- **S3-003, endliche CPU-Arbeit:** Derselbe echte Token überlebt bei ausreichendem Budget nach 81,30 s natürlich. Mit 60-s-Budget wird er nach Timeout und Prozessbaum-Kill aufgrund von 19 CPU-Samples und `medium`-Konfidenz als Endlosschleifen-Kill gezählt. Das macht 2 Kills/100 %/Exit 0 statt 1 Kill/1 Survivor/50 %/Exit 1. Hohe CPU ohne I/O beweist keine Nichttermination. Prüfe das endliche Kontrollpaar und zusätzlich eine **echte unbegrenzte CPU-Schleife als Full-CLI-Kontrolle** mit nachgewiesenem Cleanup und erhaltener Forensik. Dieser zusätzliche Infinite-Full-CLI-Arm wurde in S3 nicht ausgeführt.

Danach folgen die materiellen **P2-Produktkarten S3-004 bis S3-015**, wichtige P2-Testkarten und schließlich die P3-Karten nach ihren konkreten Kriterien. Die finalen Karten bestimmen die Priorität; Fables historische Reihenfolge wird nicht ungeprüft übernommen. N-01/MC-01 ist in S3 P2, Statsfallback P2. Offene N-03- oder weitere Quellclaims werden vor einer Reparatur geprüft.

**Feldblocker Bug 3 / FRB-01:** Maßgeblich ist der Produktaufruf während Collection. Body und `@given`-Body funktionieren; Importkonstante, eager Strategie und Parametrisierung blockieren die Forced-Fail-Proofattribution. `continue-on-collection-errors` plus `maxfail=0` hilft im geprüften Mischkorridor, nicht in der reinen Importzeit-Suite. Fixture-Setup ist ein geprüfter projektseitiger Workaround. Die Sourcekontrolle am Parent `f8054e1` ist unter denselben heutigen Abhängigkeiten grün. Prüfe bei einer Collection-Proof-Lösung echte Exceptionidentität, Chaining/ExceptionGroups, unrelated Fehler, gleichnamige Fauxexceptions, Warn-/Tailtext, skips und xfails. Ein beliebiger Fehlertail ist kein Proof.

**Atomic-Ownership und Apply:** S3 belegt lokale fremde Fixturebytes-Löschung bei echtem Hardlink/Identitätswechsel und kontrolliertem Scheduling. Eine Rechte- oder Remotegrenze und die Häufigkeit sind nicht belegt. Sichere alle Cleanupaufrufer, insbesondere die in S3 bezeichneten Orte `atomic_file.py:380` und `:989`; bestätige die aktuellen Orte per Serena. Unbedingtes vorgelagertes Unlink kann einen sicheren späteren Helper umgehen. Gesunde Positivkontrollen müssen erhalten bleiben. Bei AF-05 bleibt ein Stable-Backup erhalten, obwohl der normale Quellpfad fehlt. AF-01 scheitert vor Displacement; AF-04/B-02 scheitert nach Mutation bei Backup-Promotion. Diese Abläufe getrennt abnehmen.

**Export:** Eine Sharing-Violation kann ein altes grünes Artefakt stehen lassen; der geprüfte Export endet dennoch Exit 1. Prüfe Artefaktfrische und Exitautorität getrennt. Ein zusätzlicher Always-upload-Consumertrigger darf nicht als bereits bewiesenes Falschgrün eines korrekt auf Exit prüfenden CI ausgegeben werden.

**Offene Verifikation:** Jede offene Quell-ID erhält ein begründetes Endurteil oder eine präzise verbleibende Grenze. Für Feldbug 1 und 2 sind fehlende Inputs vor einem Ursachenclaim zu sichern. Für Bug 2 werden Befehle/CWD, Konfiguration vor/nach, vollständige Ausgaben/Exits/Imports, Run-/Generationsbasis und Mutantennamen, Staging/Sidecars sowie minimale Quellen mit gleicher Pfadtopologie benötigt. Vor deren Sicherung keine produktiven Cache- oder Verdiktbytes löschen.

## Projektwerkzeuge und integrierte Finalgates

Lies `AGENTS.md`/`CLAUDE.md` und die führenden Architektur-, Design- und Testverträge. Prüfe `serena-mutmut-win` mit `initial_instructions` und aktivem Projekt vor Codearbeit. Nutze symbolbasierte Navigation vor Änderungen und Context7 vor neuen oder unsicheren APIs. Verwende die im Projekt verlangten Reasoningwerkzeuge für komplexe Abwägungen; die Entscheidung und überprüfbare Begründung gehören in die Dokumentation.

Setze vor jedem Kandidaten- und Finalgate eine **frische absolute `UV_PROJECT_ENVIRONMENT` außerhalb des Checkouts**. Auch `HYPOTHESIS_STORAGE_DIRECTORY`, pytest-`basetemp`, Coverageausgabe und Werkzeugcaches sind extern. Alle Ausführungen erfolgen über `uv run`. Synchronisiere die gelockte Gruppe für den jeweiligen Zweck; teile keine Dev-, Security- und Releaseumgebung.

Pflicht sind Ruff-Lint und Formatcheck auf jede geänderte Datei mit 0 Findings, mypy strict mit 0 Errors, pytest mit Hypothesis, Architekturcontracts über import-linter und Mutation Testing des Projekts auf jeden geänderten Codepfad. Mutation Score mindestens 80 %; verbleibende Survivor technisch adjudizieren und niedrigere Ergebnisse ausdrücklich begründen. Neue öffentliche APIs benötigen Typen und Google-Style-Docstrings. Datenstrukturen folgen den Pydantic-Projektregeln. Keine unbegründeten `noqa`, unspezifischen `type: ignore`, globalen Regelabschaltungen oder `unittest.TestCase`.

Kanonisches Securitygate, aus einer frisch gelockt synchronisierten externen Umgebung:

```powershell
uv sync --locked --only-group security --no-install-project
uv run --no-sync python -I scripts/semgrep_release_gate.py
```

Kanonisches natives Releasegate, mit eigener frischer externer Umgebung:

```powershell
uv sync --locked --only-group release --no-install-project
uv run --no-sync python -I scripts/release_native_gate.py
```

Der native Wrapper prüft die drei manifestgebundenen ZIP-Werkzeuge und Zizmor 1.30.0 offline in `regular` und `pedantic`; Git stammt aus dem HKLM-Vertrag. Raw- oder Changed-file-Scans ersetzen keinen kanonischen Semgrep-PASS. Kläre den aktuellen Semgrep-Fehlschlag und berichte den vollständigen gelockten Dependency-Audit getrennt von der genauen CI-Allowlist: Policy-Exit 0 mit 14 ignorierten Advisories ist kein ungefilterter sauberer Audit.

Führe abschließend eine eigene **vollständige pytest-Coverage-Suite** am finalen Source-/Lock-/Teststand aus, dazu Ruff, Format, mypy strict, Importcontracts, kanonische Security- und native Gates, vollständigen Dependency-Audit und die erforderliche Mutationsevidenz. Skips, xfails, Hostflakiness und nicht ausgeführte Arme erhalten konkrete Grenzen. Historische Greens und addierte Teilreplays qualifizieren den finalen Release nicht. Performancebehauptungen brauchen tatsächliche Benchmarks mit Lastbindung.

## Agenten und Abgabe

Nutze parallele Agenten für unabhängige Aufgaben. Parallele Editagenten arbeiten in getrennten Worktrees. Jeder Prompt enthält die vollständigen Projektstandards, die fünf Projektsektionen und ein explizites Schrittlimit. Prüfe Kernaussagen und Gates nach Rückkehr selbst. Bei Failure erst den Fehler und die tatsächlichen Outputs verstehen; höchstens zwei gezielte Korrekturversuche, anschließend die Ursache selbst lösen oder eine genaue externe Grenze melden.

Liefere eine maschinenlesbare Sanierungsbilanz **S3-ID → Source-/Commitbindung → mechanismusspezifisches Rot/Grün → integriertes Gate → Mutationsevidenz**. Je Aussage: 1-basierte Sourceorte, Receiptpfad, Kommando, CWD, Runtime, Sourcehash, Start, Ende und Exit. Trenne Produktfehler, Testschwächen, Dokumentkorrekturen und offene Verifikation. Schließe mit den tatsächlich verbleibenden Risiken und einer nachvollziehbaren Abnahmeentscheidung.

