# ASTRA: adversariales Review von mutmut-win v2.21.4

Bezugsstand: Commit `4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b`, Tag `v2.21.4`. Prüfzeitraum: 19. September 2026. Zielplattform: Windows mit CPython 3.14.7. Arbeitsverzeichnis: `C:/claude_codex/mutmut-win-astra`. Umfang: 40 Pythonmodule mit 25.957 Quellzeilen.

## Methode und Unabhängigkeit

Dieses Review wurde unabhängig vom Vergleichsbericht durchgeführt. Die 26 Finder erhielten frische Kontexte (fork_turns=none); kein Finder erhielt Ergebnisse eines anderen Finders. Nach Abschluss aller Finder wurde jeder der 121 eingereichten Kandidaten einschließlich Überschneidungen und eines zurückgezogenen Claims zwei neuen Skeptikern mit den Perspektiven Korrektheit und Erreichbarkeit zugewiesen. Ein zusätzlicher rein technischer Dispatcher verteilte Einzelbefunde und transportierte Urteile; er nahm keine fachliche Bewertung vor. Jeder Skeptiker erhielt genau einen Kandidaten und keine Finderhistorie, weiteren Befunde oder fremden Urteile. Der Root führte Zusammenführung, Quellenkontrolle, Priorisierung und Schema-Prüfung aus. Einzelne kurze, ausdrücklich erlaubte Python-Sprach- beziehungsweise API-Faktenchecks sind in den jeweiligen Urteilen ausgewiesen; sie ersetzen keine Reproduktion des Projektverhaltens.

Damit umfasst die fachliche Prüfung 268 getrennte Agentenkontexte (26 Finder und 242 Skeptiker), zusätzlich zum technischen Dispatcher und dem koordinierenden Root. Die vier verfügbaren Ausführungsslots wurden in Wellen genutzt; Kontexttrennung und vollständige Einzelzuordnung blieben dabei erhalten.

Die Haupttexte der Befunde wurden nach der Gegenprüfung eingegrenzt und redaktionell präzisiert; die individuellen Urteile bleiben in der JSON-Fassung unverändert. Beide Urteile beziehen sich auf denselben eingefrorenen ursprünglichen Kandidaten. In den Belegen markieren Auslassungspunkte getrennte Ausschnitte; Dateipräfixe dienen als Ortsangaben.

Fünf rein technische Übertragungsabweichungen einzelner Skeptikeraufträge wurden vor deren Urteil im selben Kontext korrigiert: ein Tippfehler im vorgeschriebenen Auftrag, ein bedeutungsloser Zusatz hinter dem Befund, eine fehlende JSON-Escape-Ebene im Codezitat, eine sprachliche Abweichung in einem zusätzlichen Grenzensatz und ein weiterer Tippfehler in diesem Grenzabsatz. Die Korrekturen enthielten keine weiteren Befunde oder Urteile; es wurden dafür keine Ersatzskeptiker eingesetzt. Ein bereits abgeschlossener Finder-Kontext wurde ausschließlich administrativ beendet, um einen blockierten Slot freizugeben.

Bei einem Erreichbarkeitsurteil (RES-01) fügte die technische Übertragung versehentlich das Wort „ab“ in eine Begründung ein. Der Dispatcher meldete den ursprünglichen Agentenwortlaut vor der Übernahme; dieses zusätzliche Wort wurde entfernt. Bewertung, Konfidenz und sämtliche fachlichen Aussagen blieben dabei unverändert.

Kein fremder Reviewbericht wurde geöffnet, gesucht oder angefordert. Die Lektüre eines historischen, als „external QA“ markierten Quellkommentars führte vorsorglich zu einer Unterbrechung. Der Nutzer stellte ausdrücklich klar: „Ja, Quellkommentare sind erlaubt; Review fortsetzen.“ Danach wurde in denselben getrennten Finder-Kontexten weitergearbeitet. Externe Memory-Dateien und fremde Arbeitsdateien wurden nicht geöffnet oder durchsucht. Die ausdrücklich erlaubten API-Faktenchecks verwendeten das im Auftrag vorgegebene Python-Environment. Eine zweite vorsorgliche Unterbrechung betraf historische Review-/QA-Passagen in README.md:510–537. Der Nutzer gab auch diese ausdrücklich frei: „Ja, Freigabe auch für README-Passagen. Weiter.“ Vor dieser Freigabe öffnete der Root die gemeldeten Passagen nicht. Danach wurden beide ursprünglichen Skeptiker in ihren bisherigen getrennten Kontexten fortgesetzt; spätere gezielte README-Suchen des Root konnten auch freigegebene historische Passagen umfassen.

Die vom Auftrag festgelegte Entscheidungsregel ist bewusst keine Einstimmigkeitsregel: Zwei Widerlegungen oder zwei technisch ausgefallene Urteile führen zu widerlegt; alle anderen Kombinationen führen zu bestätigt. Ein bestätigter Eintrag mit einem Widerspruch ist deshalb kein Konsens. Solche Einträge werden sichtbar markiert und in der Konfidenz herabgesetzt. Bestätigt bedeutet hier Annahme nach diesem Protokoll, nicht dynamisch reproduziert.

hoch: Mechanismus, relevante Aufrufer und erreichbarer Auslöser sind am gelesenen Code klar belegt; mittel: relevante Rahmenbedingung, Fremd-API-Semantik, konkretes Interleaving oder ein Urteil bleibt unsicher; niedrig: wesentliche Reichweite unbewiesen, ausschließlich strittige Annahme oder technische Prüfungslücke. Eine hohe statische Konfidenz ersetzt keinen Laufbeleg. Die endgültige Schwere ist das zusammengeführte Urteil des Root; abweichende Schwereempfehlungen der Skeptiker bleiben unverändert sichtbar. Gleichartige Auslöser und Folgen wurden über Findergrenzen hinweg abgeglichen.

Der unveränderte Kandidatenbestand wurde vor der Gegenprüfung mit SHA-256 `95d99887d2ba754a62ec988f1509a2ed246c8eaf582166173c42b2e815e22746` eingefroren. 121 Kandidatenpaare und 242 individuelle Skeptikeraufträge sind im Prüfprotokoll unten zugeordnet.

## Ergebniszahlen

**121 eingereichte Kandidaten: 118 bestätigt, 3 widerlegt.** Die Zähleinheit ist der einzelne Kandidat. Unabhängig gefundene Überschneidungen werden für den mechanischen Vergleich beibehalten; die Zahl ist keine Anzahl voneinander verschiedener Defekte.

| Schwere | Bestätigte Kandidaten |
| --- | ---: |
| critical | 0 |
| high | 12 |
| medium | 76 |
| low | 30 |

| Kategorie | Bestätigte Kandidaten |
| --- | ---: |
| correctness | 39 |
| resource-leak | 17 |
| error-handling | 16 |
| race | 12 |
| api-contract | 11 |
| windows | 7 |
| nondeterminism | 5 |
| phase-order | 4 |
| performance | 3 |
| toctou | 3 |
| test-flakiness | 1 |

Bestätigte Kandidaten mit einem widersprechenden Skeptiker: **0**. Technisch fehlende Einzelurteile: **0**.

## Eigene Priorisierung

Zuerst würde ich den verlorenen Zwischenstand beim Anwenden eines Mutanten beheben (VIEW-02): Ein regulärer Editor-Speichervorgang kann überschrieben werden, und das eigens erzeugte Backup enthält ebenfalls nur den alten Stand. Das gefährdet die Arbeit des Nutzers unmittelbar.

Danach würde ich die Terminierung fremder Prozesse durch ungeprüfte PPID-Zuordnung schließen (RACE-01). Eine noch lebende Waise kann eine Eltern-PID tragen, die erst später einem mutmut-Kind zugeteilt wird. Der vorhandene Job und die gültige Identität dieser Waise legitimieren deren Beendigung nicht; beim Typechecker ist dieser Pfad sogar nach regulärem Abschluss erreichbar.

An dritter Stelle stehen Pfade, die technische Fehler in einen gezählten Kill umwerten. WORK-01 betrifft einen Fehler bei der Proof-Veröffentlichung, SPAWN-02 das verlorene Fortschrittsveto bei einem erreichten Timeout. Hier ist die Gefahr ein besser aussehender Score trotz fehlender Aussage über die Tötung des Mutanten.

Unmittelbar danach folgt FILE-01: Ein normaler zweiter Lauf mit Coverage kann auf bereits instrumentierten Dateien messen und diese Zeilen später auf die unveränderte Originalquelle beziehen. Ein Fingerprint über diesen konsistenten Zustand repariert die falsche Phasenfolge nicht. Anschließend würde ich die fehlende Erfassung externer ZIP-Importquellen (STATS-03), die Gitignore-bedingt verkleinerte Mutationsauswahl (REST-04) und die Sperrdomäne gemeinsam benutzter Datenbanken (LOCK-01) schließen.

Ressourcen- und Darstellungsfehler bleiben relevant, werden aber nach ihrer belegten Lebensdauer und Wirkung behandelt. Ein bis zum Hostende verlorener Handle erhält deshalb nicht allein wegen des beobachteten Waisenproblems dieselbe Priorität wie ein falscher Kill oder eine überschriebene Quelländerung.

**Abgleich einzelner Schwerebewertungen.**

- **DATA-03, STATS-02 → low:** Bereits beschädigte oder manuell veränderte lokale Caches; keine Entstehung durch normale Zeitmessungen, kein falsches Ergebnis belegt. Die beiden DATA-03-Skeptiker empfehlen medium; der Root bewertet die gleichartige Folge wie STATS-02.
- **VIEW-01, CLI-07 → medium:** Unerwartete Löschung erfordert eine vorbereitete Umleitung, den aus einer ausgewählten Quelle abgeleiteten Sidecar-Pfad, korruptionsauslösenden Inhalt und ausreichende Rechte. Beide VIEW-01-Skeptiker empfehlen high; die beiden CLI-07-Skeptiker medium. Die konkrete Wirkung wird trotz zusätzlichem Browser-Fallback einheitlich eingeordnet.
- **ATOM-03, WIN-04 → low:** Begrenzte Restdateien nach fehlgeschlagenem Copy; erfolgreiche übergeordnete Stagingbereinigung kann sie entfernen. Kein Datenverlust oder falsches Ergebnis belegt; entspricht der Korrektur des Erreichbarkeitsskeptikers.
- **EDGE-04 → medium:** Vollständiger, sichtbar gemeldeter Generierungsabbruch auf betroffenen Windows-Systemen; --max-children 61 oder kleiner bietet einen direkten Workaround. Der Korrektheitsskeptiker empfiehlt medium, der Erreichbarkeitsskeptiker hält high für vertretbar.
- **DATA-01, CONTRACT-02 → low:** Die ungültige INI-Konfiguration wird abgelehnt, aber im falschen Fehlerkanal. JSON-Fehlerobjekt und zugesagter Exitcode fehlen; keine falschen Ergebnisse oder verlorenen Nutzerdaten belegt. DATA-01-Skeptiker empfehlen low, CONTRACT-02-Skeptiker medium; der Root ordnet den identischen Mechanismus einheitlich low ein.
- **OP-07, EDGE-02, CONTRACT-06 → medium:** Gleiche gültige Eingaben brechen die tatsächliche Neugenerierung im Standardprofil ab; die Vertragslinse beschreibt keine geringere Auswirkung. Die vier OP-07/EDGE-02-Skeptiker empfehlen medium, die beiden CONTRACT-06-Skeptiker wegen Seltenheit low. Der Root gewichtet den vollständigen Generierungsabbruch und ordnet alle drei einheitlich medium ein.

## Einordnung der beobachteten Anomalien

**Sporadische Basis- und Staging-Abbrüche.** BASIS-01 und STAGE-01 wurden von beiden Skeptikern angenommen. Sie liefern konkrete Mechanismen für eigenen Logdatei-Drift beziehungsweise bytegleiche Helper-Neuveröffentlichung nach einem transienten Lesefehler. Keiner wurde als Ursache der gemeldeten vier Ausfälle nachgewiesen. TIME-01 bleibt als Defektclaim widerlegt mangels belegter Budgetunzulänglichkeit; die gemeldeten Timeouts werden dadurch nicht ausgeschlossen.

**Stundenlang überlebende Worker.** Der reguläre Windows-Pfad bindet neue Prozesse atomar an Job Objects. Die bestätigten Task-Cleanup- und Wrapper-Ausnahmen beweisen kein Überleben nach nachgewiesenem Tod des tatsächlichen Jobinhabers. PID-/PPID-, Job-/Handle- und zeitliche Prozessspuren der beobachteten Vorfälle fehlen; die Ursache bleibt offen.

**Langer Fingerprint-Prelude.** Die Quellenlektüre bestätigt breite Distributionsdatei-Hashes und wiederholte Basisaufnahmen. Ohne Ausführung oder Profiling sind weder Endlosigkeit noch die konkrete Verteilung der Kosten belegt. Die genannten Paketanzahlen und Laufzeiten stammen aus dem Auftrag.

**Gitignore-Fix von v2.21.4.** Die korrigierte Auflösung relativ zur jeweiligen Ignore-Datei beseitigt weder die in BASIS-01 belegten Core-Aufrufe ohne Ignore-Boundary noch die fehlende Berücksichtigung bereits getrackter Dateien in REST-04. Damit können verschiedene Teile derselben Pipeline unterschiedliche Dateimengen betrachten. Zusätzliche Core-Walks können ausgeschlossene Inhalte weiterhin hashen; daraus folgt keine vollständige Unsichtbarkeit dieser Inhalte in jeder Basis. REST-05 belegt außerdem, dass ein Lesefehler an einer tieferen Ignore-Datei deren einschließende Negation verlieren kann; die zugesagte konservative Übererfassung ist dadurch nicht durchgehend gewahrt.

**Modulstatements und Score-Oberfläche.** MUT-07 bestätigt die ausdrücklich im Auftrag genannte Dokumentationslücke. Der Ausschluss selbst ist beabsichtigt und durch einen vorhandenen Test gesichert; die README beschreibt bereits die Funktionsoberfläche, erläutert Modulzuweisungen/-verzweigungen und ihren fehlenden Beitrag zum Score-Nenner jedoch nicht ausdrücklich. Kein Berechnungsdefekt.

Mehrere voneinander unabhängige Prüffragen laufen auf eine Grenze der Wiederverwendung hinaus: Der Kopierpfad erhält Generatorausgabe, solange die ursprüngliche Quelldatei denselben Hash hat. Das ist vor einer erneuten Coverage-Messung (FILE-01) und nach der dateiweisen Abwahl (FILE-03) unzureichend. Damit ist ein Einfluss früherer Läufe auf einen Folgeversuch statisch belegt. Ob dies die im Auftrag genannten sporadischen Suitefehler verursacht hat, bleibt offen; dafür fehlen die jeweiligen Stagingzustände und Laufspuren.

Die Operatorbefunde unterscheiden drei Folgen: kontextwidrige Ersetzungen beziehungsweise ungültige Ausgabe mit gewarntem dateiweitem Fallback (OP-01 bis OP-03), vermeidbare äquivalente Mutanten oder falsche Argumentzuordnung (OP-04 bis OP-06 und OP-09) sowie vorgezogene Generierungsfehler beziehungsweise Ressourcenaufwand (OP-07/OP-08). Der vorhandene Syntaxschutz schützt den Originalcode, erhält jedoch nicht die anderen gültigen Mutanten derselben Datei. Diese Unterschiede bestimmen die Schwere und die Reihenfolge der Behebung.

LOCK-01 betrifft die Zuordnung der Sperren zu einer gemeinsamen Datenbank. Eine sichere Sperrdatei schützt nur Prozesse, die dieselbe Datei auswählen: Unterschiedliche effektive Temp-Wurzeln teilen die Sperrdomäne. Die SQL-Transaktionen selbst bleiben serialisiert; der belegte Fehler ist die unberechtigte Recovery eines lebenden Runs.

SPAWN-01 zeigt einen verbleibenden Hängerpfad trotz eigener Watchdogs: Die Registrierung einer toten PID kann ihrer Taskzuordnung vorauseilen. Der danach verwaiste Eintrag deaktiviert ausgerechnet die Idle-Prüfung, die gesunde laufende Tasks schützen soll. Der Befund setzt einen zusätzlichen dauerhaft lebenden stillen Worker voraus und wurde nicht als Ursache eines beobachteten Vorfalls nachgewiesen.

SPAWN-02 betrifft Ergebniswahrheit nach einem erreichten Timeout. Der Prozessbaum wird ohnehin beendet; fehlerhaft ist, dass wegfallende absolute Kinderzähler das Fortschrittsveto beseitigen können und der Timeout anschließend als Infinite-Loop-Kill zählt. Der Bericht unterscheidet diese Umwertung ausdrücklich von einer vorzeitigen Terminierung.

Ressourcenbefunde sind nach Lebensdauer zu unterscheiden: fehlgeschlagene Konstruktionen und frühe API-Enden können rohe Handles bis zum Ende eines langlebigen Hosts verlieren; Task-Cleanup-Fehler können Nachfahren innerhalb eines noch lebenden Pools erhalten. Der äußere Job bleibt in diesen Fällen eine relevante Gegenbedingung. Aus einem solchen Leck folgt kein Nachweis der im Auftrag beobachteten Waisen nach dem Tod des tatsächlichen Jobinhabers.

RACE-01 ergänzt die Lebenszyklusbefunde um ein anderes Risiko: Ein globaler numerischer PPID-Graph ist unter Windows kein ausreichender Eigentumsnachweis für eine Terminierung. Gerade die ergänzende Bereinigung außerhalb des bereits vorhandenen Jobs kann einen fremden Prozess erfassen. Der Befund erklärt die beobachteten mutmut-Waisen nicht und setzt ausreichende Rechte zur Terminierung des fremden Prozesses voraus.

RACE-02 liefert einen eigenständigen Mechanismus für zeitabhängige Ergebnisabweichungen: Ein normal beendeter Worker kann allein wegen der Reihenfolge von Queue-Timeout und Liveness-Prüfung als abgestürzt gelten. Ein vollständig übertragenes Ergebnis genügt nicht, solange der Parent es vor der Synthese nicht verarbeitet. Auch dieser Ablauf ist statisch belegt, aber keinem der im Auftrag genannten konkreten Ausfälle zugeordnet.

## Bestätigte Befunde

### Ausführungsbasis, Staging und Coverage

<a id="mod-stats-stats-03"></a>

#### STATS-03: ZIP-Unterpfade können aus einer als vollständig ausgewiesenen Basis fehlen

**high · correctness · Konfidenz mittel** — `mod:stats` — [src/mutmut_win/stats.py:986](C:/claude_codex/mutmut-win-astra/src/mutmut_win/stats.py:986)

**Mechanismus.** zipimport-Suchpfade können ZIP-Unterverzeichnisse bezeichnen, die keine regulären OS-Pfade sind. Liefert Windows lstat FileNotFoundError, wird nur missing-import-root gebunden und reuse_safe bleibt unverändert; zugrunde liegendes ausführbares Archiv fehlt im Hash.

**Fehlerszenario.** Eine unveränderte ausführbare .pth-Zeile ergänzt C:\external\plugins.zip\vendor in Parent- und Child-sys.path. Das externe Archiv liegt außerhalb aller anderen Hashbäume und ist keine inventarisierte Distribution. Änderungen an vendor/helper.py können Tests ändern, aber denselben vollständigen Kontextdigest und die Wiederverwendung alter Verdicts erlauben. Direkte ZIP-Pfade werden korrekt gehasht. Die Windows-Fehlerklasse ist mit einem reinen Dateipräfix-API-Check bestätigt; ein vollständiger ZIP-/Verdict-Lauf wurde nicht reproduziert.

**Wörtlicher Beleg:**

```python
except FileNotFoundError:
                        # A truly absent sys.path entry is a fully observed state
                        # and can affect resolution order. A broken link is not
                        # equivalent and is handled by the successful lstat path.
                        hasher.update(b"missing-import-root\0")
```

**Fixskizze.** Archivbasierte Suchpfade vor Missing-Einstufung erkennen, Archiv plus Präfix binden; nicht auflösbare aktive Importer als unvollständig behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Ein externes, anderweitig nicht gehashtes ZIP-Archiv kann über einen unveränderten ZIP-Unterverzeichnispfad in sys.path ausführbaren Testinput liefern, während die Kontextbildung diesen Pfad unter Windows als vollständig beobachtet fehlend behandelt. Archivänderungen können dadurch den Kontextdigest unverändert lassen und alte Verdicts wiederverwendbar halten. Die Windows-Fehlerklasse ist durch einen reinen Dateipräfix-API-Faktencheck bestätigt; ein vollständiger ZIP-/Verdict-Reproduktionslauf wurde nicht durchgeführt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Ein externes, anderweitig nicht gehashtes ZIP-Archiv kann über einen ausführbar hinzugefügten sys.path-Unterpfad importierbar sein, während dessen OS-Unterpfad unter Windows/CPython 3.14.7 als FileNotFoundError behandelt wird. Dadurch können Archivänderungen bei ansonsten unveränderter, vollständiger Basis denselben Kontextdigest und die Wiederverwendung alter Verdicts ermöglichen. Die Windows-Fehlerklasse ist durch einen reinen Dateisystem-API-Faktencheck bestätigt; ein vollständiger Projektlauf wurde nicht reproduziert.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Zielcommit 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b und Version 2.21.4 bestätigt. Das Zitat stimmt wörtlich; der Exception-Zweig beginnt in stats.py:986, das hasher.update steht in Zeile 990. Der erlaubte reine API-Faktencheck unter Windows/CPython 3.14.7 mit dem vorhandenen Dateipräfix src/mutmut_win/stats.py/vendor ergab is_file=False, is_dir=False und bei lstat FileNotFoundError, errno=2, winerror=3. Damit ist die entscheidende Windows-Fehlerklasse für einen Pfad unter einer regulären Datei bestätigt. Die Laufzeitdokumentation von zipimport.zipimporter bestätigt ausdrücklich Suchpfade innerhalb eines ZIP-Archivs. Der untersuchte Zweig bindet ausschließlich den Pfad und missing-import-root, weder Archivbytes noch Archivmetadaten, und setzt reuse_safe nicht zurück. Gegenprüfungen: Direkte Archivpfade werden in stats.py:951–965 gehasht; zusätzliche Verzeichnis- und Distributionshashes schützen nur bei anderweitiger Abdeckung, die das Szenario ausdrücklich ausschließt. Der Projektkern überspringt externe Pfade in stats.py:841–843. Auch die Child-Grenze widerlegt den Befund nicht: runner.py:662 startet Python ohne -S; die PYTHONPATH-Bereinigung verhindert keine ausführbare .pth-Zeile. Der sitecustomize-Blocker entfernt lediglich Originalquellverzeichnisse, nicht beliebige externe Archivpfade (runner.py:929–957). Vollständigkeit und Wiederverwendung hängen anschließend an den betroffenen Digest-/Complete-Werten (stats.py:1424–1426; orchestrator.py:353,807). Testabdeckung: test_dependency_basis_220.py:628 prüft reale Verzeichnisse, Modulbytes, Pfadreihenfolge und geänderte .pth-Dateibytes; Zeile 1305 prüft defekte Symlinks. Beide erfassen keine unveränderte .pth-Datei mit verändertem externem ZIP-Unterpfad. Keine entsprechende ZIP-Unterpfad-Abdeckung in den durchsuchen Python-Tests gefunden. Keine Tests oder Prozessreproduktionen ausgeführt.

**Erreichbarkeit:** HEAD entspricht 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b. Das Zitat stimmt wörtlich mit stats.py:986–990 überein. Der erlaubte reine API-Faktencheck unter Windows/CPython 3.14.7 ergab für den Unterpfad vendor unter der vorhandenen regulären Datei pyproject.toml tatsächlich FileNotFoundError, errno=2, winerror=3. Damit ist die entscheidende Windows-Fehlerklasse belegt, ohne ZIP-Dateien anzulegen oder Projektcode auszuführen. stats.py:951–990 bindet bei diesem Pfad nur Pfadtext und missing-import-root; weder Archivbytes noch ein unvollständiger Zustand werden erfasst. Die nachfolgenden Baumdurchläufe erfassen ausschließlich erkannte Verzeichnisse. Gegenprüfungen liefern keinen allgemeinen Schutz: Direkte Archivpfade werden gehasht, andere Hashbäume oder Distributionsinventare könnten das Archiv ebenfalls erfassen, sind im ausdrücklich beschriebenen externen Szenario aber ausgeschlossen. runner.py:759 und worker.py:1080 entfernen PYTHONPATH; dies verhindert keine beim Interpreterstart ausgeführte .pth-Zeile. Der generierte Filter entfernt ausschließlich Einträge, die den echten Projektquellverzeichnissen entsprechen (runner.py:929–957), keinen beliebigen externen ZIP-Unterpfad. Bei ansonsten vollständiger Basis bleibt der Kontext wiederverwendbar (stats.py:1425–1426); orchestrator.py:807–827 verwendet diese Freigabe für alte Verdicts. tests/unit/test_dependency_basis_220.py:628–666 prüft gewöhnliche Importverzeichnisse, Modulbytes, Reihenfolge und Änderungen der .pth-Datei selbst, aber keine unveränderte ausführbare .pth-Datei mit geändertem externem ZIP-Unterpfad. Ein einschlägiger ZIP-Unterpfad-Regressionstest wurde in den durchsuchten Python-Tests nicht gefunden. Keine Tests oder Prozessreproduktionen ausgeführt.

<a id="mod-file-setup-file-01"></a>

#### FILE-01: Wiederholte Coverage-Läufe messen Generatorcode statt Originalzeilen

**high · phase-order · Konfidenz hoch** — `mod:file-setup` — [src/mutmut_win/file_setup.py:1349](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:1349)

**Mechanismus.** _mirror_is_stale erhält gültige Generatorausgabe bei gleichem Live-Quellhash. Der Orchestrator kopiert und misst Coverage vor Neugenerierung (orchestrator.py:1127–1165). Der Runner misst vorhandene Staging-Dateien. Gemessene Zeilen werden unverändert auf die Live-Quelle angewendet (orchestrator.py:1175–1207; mutation.py:364), obwohl mutation.py:546 zuvor den mehrzeiligen Helfer sowie zusätzliche Funktionsvarianten einfügt. Die unveränderte Staging-Prüfung und der erst danach ausgewertete Coverage-Fingerprint korrigieren diese Zuordnung nicht.

**Fehlerszenario.** Erster Lauf erzeugt Mutanten. Zweiter unveränderter Lauf mit mutate_only_covered_lines=true behält generiertes Modul. Coverage liefert Helfer-/verschobene Funktionszeilen; ausgeführte Originalzeilen werden herausgefiltert oder nicht ausgeführte durch gleiche Nummer eingeschlossen. Mutantenbestand hängt vom vorhandenen Staging ab. Das betrifft normale Wiederholungsläufe ohne --force; eine Änderung des Bestands ist nicht für jedes Modul zwingend.

**Wörtlicher Beleg:**

```python
    if owned_metadata is not None:
        recorded = owned_metadata["source_hash"]
        return not isinstance(recorded, str) or recorded != _content_hash(source)
```

**Fixskizze.** Vor Coverage Originalbytes bereitstellen oder getrennten Originalmirror messen; Generation-Reuse erst danach entscheiden. Zwei vollständige unveränderte Coverage-Läufe vergleichen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Bei Wiederholungsläufen ohne --force können erhaltene generierte Staging-Module als Coverage-Grundlage dienen. Deren Zeilennummern werden ohne Rückabbildung zum Filtern der Live-Quelle verwendet. Dadurch kann sich der Mutantenbestand trotz unveränderter Quellen und Tests ändern; eine Änderung tritt nicht zwangsläufig bei jedem Modul auf.
- Erreichbarkeit: angenommen, Konfidenz hoch. Bei einem erneuten Lauf mit mutate_only_covered_lines=true ohne --force können unveränderte, zuvor generierte Stagingmodule als Coveragequelle dienen. Deren Zeilennummern werden ohne Rückabbildung auf die Live-Quelle angewendet, sodass der Mutantenbestand vom vorhandenen Staging abhängt. Der Helferverweis :544–546 gehört zu src/mutmut_win/mutation.py.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am Ziel-HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat in file_setup.py:1349–1351 wörtlich. copy_src_dir überspringt die Aktualisierung eines vorhandenen Targets bei unverändertem Quellhash (1298–1309). Der normale Wiederholungslauf muss keine Bereinigung durchführen; --force ist ausdrücklich optional (cli.py:684). Die Coverage-Sammlung erfolgt vor der Generierung (orchestrator.py:1127–1165 gegenüber 1222–1227). runner.py:585–601 führt coverage mit leerem MUTANT_UNDER_TEST aus, verwendet aber die Staging-Importpfade (780–785) und cwd="mutants" (368). Das leere Kennzeichen aktiviert lediglich die generierte Originalfunktionskopie über den Trampolin; es stellt weder Originalbytes noch Originalzeilennummern her. mutation.py:546 fügt den mehrzeiligen Helfer vor Funktionen ein; zusätzlich werden Funktionsvarianten eingefügt (586–588). code_coverage.py:119–126 übernimmt gemessene Zeilennummern unverändert. file_setup.py:2137–2142 liest hingegen die Live-Quelle und reicht diese zusammen mit den gemessenen Nummern an die Generierung weiter (2203–2207); mutation.py:364–365 filtert nach deren ursprünglichen Positionen. Die geprüften Gegenmechanismen helfen nicht: purge_staging_runtime_artifacts entfernt Cacheartefakte, keine generierten Python-Module; die Staging-Prüfung erkennt Änderungen während Coverage, nicht falsche Ausgangszeilennummern; Coverage-Fingerprints können Neugenerierung auslösen, korrigieren aber deren bereits falsche Linienbasis nicht. Testabdeckung: test_staging_hygiene.py:968–990 bestätigt ausdrücklich den Erhalt generierter Inhalte. test_code_coverage.py verwendet künstlich geschriebene Coverage-Daten und gemockte Runner. Der namensgleiche Integrationstest test_e2e_reference.py:233–252 generiert ausdrücklich ohne Coverage-Filter. In den durchsuchten Tests ist kein Vergleich zweier vollständiger unveränderter Coverage-Läufe enthalten. Keine Tests oder Reproduktionen ausgeführt. high ist für die mögliche stille Verfälschung des Mutantenbestands angemessen.

**Erreichbarkeit:** Am verifizierten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat in src/mutmut_win/file_setup.py:1349–1351 wörtlich. Der Zustand ist durch normale aufeinanderfolgende Läufe erreichbar: create_mutants_for_file speichert Generatorausgabe mit source_hash, generation_fingerprint und generated_hash (2252–2275). read_owned_source_metadata akzeptiert diese unveränderte Ausgabe nach Prüfung ihres Hashes (models.py:383–430). copy_src_dir überspringt anschließend das erneute Kopieren (file_setup.py:1298–1309), weil _mirror_is_stale bei unveränderter Live-Quelle False liefert. Die automatische Bereinigung entfernt lediglich Laufzeitverzeichnisse und Bytecode, keine generierten .py-Dateien (228–261); die vollständige Löschung von mutants erfolgt nur bei --force (cli.py:684–693). Der Orchestrator sammelt Coverage vor der Generierung und vor der Fingerprintentscheidung (1127–1185). Der Runner startet coverage im Arbeitsverzeichnis mutants (runner.py:368, 570–601) mit dessen Importpfaden (731–785). MUTANT_UNDER_TEST='' wählt zwar den Originalfunktionskörper, stellt dessen ursprüngliche Zeilennummern aber nicht wieder her. mutation.py:546 fügt den mehrzeiligen Helfer ein; 636–637 serialisiert das veränderte Modul. code_coverage.py:119–126 übernimmt die gemessenen Zeilen unverändert; orchestrator.py:1179–1207 reicht sie an die Mutation der Live-Quelle weiter, deren Positionen mutation.py:364 filtert. Aktive Gegenprüfung: Der Coverage-Fingerprint kann die Wiederverwendung verhindern, wird jedoch erst nach der fehlerhaften Messung geprüft und erzwingt dann Generierung mit eben diesen Zeilen. Die Staging-Prüfung vergleicht lediglich den Zustand vor und nach Coverage (orchestrator.py:115–126, 1165), nicht Generatorausgabe gegen Originalquelle. Tests: test_staging_hygiene.py:968–990 bestätigt ausdrücklich das Beibehalten generierter Ausgabe. test_coverage_gating.py:51–87 misst einmalig einen frisch mit Originalcode bestückten Mirror; test_code_coverage.py:66–83 verwendet simulierte Messdaten. test_review_cache_integrity.py:126–137 prüft Fingerprintänderungen, keinen vollständigen zweiten Coverage-Lauf. test_e2e_reference.py:233–251 generiert ausdrücklich ohne Coveragefilter. Damit liefern diese Tests keinen Gegenbeweis. Keine Tests oder Prozessreproduktionen ausgeführt; das Urteil beruht auf dem statisch durchgängigen Aufrufpfad. High ist wegen des unbemerkt falschen Mutantenbestands angemessen.

<a id="mod-rest-rest-04"></a>

#### REST-04: Gitignore-Pruning lässt bereits getrackte Quellen aus der Mutationsauswahl

**high · correctness · Konfidenz hoch** — `mod:rest` — [src/mutmut_win/gitignore_boundary.py:229](C:/claude_codex/mutmut-win-astra/src/mutmut_win/gitignore_boundary.py:229)

**Mechanismus.** GitignoreBoundary wertet ausschließlich Ignore-Muster aus und kennt den Gitindex nicht. Dadurch werden auch bereits getrackte Dateien ausgeschlossen, obwohl der Quellvertrag dies verbietet. Discovery, automatische Kopie und die mit dieser Boundary arbeitenden Fingerprint-Walks übernehmen die Entscheidung. descend_forced wird aufgerufen, neutralisiert die geerbten Regeln bei einem selbst nicht ausgeschlossenen konfigurierten Verzeichnis aber nicht.

**Fehlerszenario.** src/pkg/generated.py ist bereits getrackt oder wurde mit git add -f aufgenommen. Ein Root-Muster /src/pkg/generated.py passt, während paths_to_mutate=['src'] den selbst nicht ausgeschlossenen Ordner auswählt. Die Datei fehlt dann aus Mutationsliste und automatischem Staging. Existieren weitere reguläre Quellen und benötigen die Tests die ausgelassene Datei nicht, kann der verkleinerte Bestand als vollständiger Lauf bewertet werden. Explizite Einzelauswahl beziehungsweise eine passende Force-Ausnahme verhindert diesen Fall. Die Originaldatei bleibt erhalten. Zusätzliche Core-Import- oder Editable-Walks ohne Ignore-Boundary können ihren Inhalt weiterhin hashen; eine vollständige Unsichtbarkeit in jeder RunBasisEvidence wird nicht behauptet.

**Wörtlicher Beleg:**

```python
if _safe_pattern_match(pattern, probe) is not None:
                        decision = bool(getattr(pattern, "include", True))
            if decision is not None:
                return decision
```

**Fixskizze.** Getrackte Pfade und ihre Verzeichnispräfixe erfassen und vom Ignore-Pruning ausnehmen. Bei fehlender Indexinformation konservativ handeln und den Fall 'getrackt, danach ignoriert' über Discovery, Staging und Basis hinweg absichern.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Gitignore-Pruning lässt bereits getrackte Dateien innerhalb konfigurierter Verzeichnisbäume aus Discovery, Staging und Fingerprint aus, sofern ein Ignoremuster passt und keine explizite Einzelauswahl oder einschlägige Force-Ausnahme greift. descend_forced wird aufgerufen, neutralisiert die Regeln bei einer selbst nicht ausgeschlossenen Wurzel jedoch nicht. Die Originaldateien im Arbeitsverzeichnis werden dadurch nicht gelöscht.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Gitignore-Pruning lässt bereits getrackte Quellen innerhalb eines nicht ausgeschlossenen Mutationverzeichnisses aus Discovery, automatischem Staging und Run-Basis aus. Ohne anderweitigen Zugriff auf die fehlende Quelle kann ein regulärer vollständiger Lauf den verkleinerten Bestand bewerten. Die Originaldatei im Arbeitsverzeichnis wird dadurch nicht gelöscht.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** HEAD entspricht 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b. Das Zitat steht wörtlich in gitignore_boundary.py:228–231; Zeile 229 enthält die Entscheidung. Die Boundary speichert ausschließlich Verzeichnis-, Muster- und Ausschlusszustand (128–149), keinen Gitindex. Bei paths_to_mutate=['src'] und einem Muster src/pkg/generated.py bleibt der bereits getrackte Status deshalb unbeachtet. Gegenbeweis geprüft: descend_forced wird durchaus aufgerufen (file_setup.py:130), setzt die geerbten Regeln aber nur zurück, wenn der konfigurierte Verzeichniseintrag selbst ausgeschlossen ist (gitignore_boundary.py:193–200). Für das nicht ausgeschlossene src greift diese Ausnahme nicht. Discovery überspringt die Datei unmittelbar und ohne Warnung (file_setup.py:480–482); die automatische Kopie prüft denselben Ausschluss (1272), ebenso der Kontext-Fingerprint (stats.py:635–640). Auch konfigurierte Verzeichnisbäume verwenden diese Boundary beim Hashing (1392–1409). Eine ausdrücklich konfigurierte Einzeldatei wäre dagegen ausgenommen (file_setup.py:442–445), was das beschriebene Verzeichnis-Szenario nicht widerlegt. Ein erfolgreicher Lauf mit verkleinertem Bestand ist erreichbar, wenn andere mutierbare Module vorhanden sind und die Tests das ausgelassene Modul nicht benötigen; die Vollständigkeitsklassifikation der CLI berücksichtigt keine solchen Ausschlüsse (cli.py:714). Die vorhandenen Boundary- und Integrationstests erstellen Dateien und Ignoremuster ohne Gitindex. test_gitignore_staging_integration.py:97–108 prüft lediglich explizit konfigurierte ignorierte Wurzeln, 166–184 die Entfernung zuvor kopierter Dateien und 194–202 den unveränderten Digest ausgeschlossener Inhalte. Keiner dieser Tests prüft tracked-then-ignored. Die Behauptung widerspricht außerdem dem ausdrücklichen Quellvertrag, getrackte Dateien niemals auszulassen (gitignore_boundary.py:18–21). Ausschließlich statische Prüfung; keine Tests oder Reproduktionen ausgeführt.

**Erreichbarkeit:** Am geprüften HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat wörtlich; es umfasst gitignore_boundary.py:228–231, die angegebene Zeile 229 enthält die Zuweisung. Die Boundary lädt ausschließlich Ignoredateien und besitzt keine Information über getrackte Pfade. Der stärkste Gegenbeweis ist descend_forced(): Ausdrücklich konfigurierte, selbst ausgeschlossene Verzeichnisse umgehen vorgelagerte Muster (179–200); ausdrücklich konfigurierte Einzeldateien werden ebenfalls direkt entdeckt (file_setup.py:442–445). Diese Ausnahmen schützen das beschriebene Szenario jedoch nicht: Bei paths_to_mutate=['src'] und dem Root-Muster /src/pkg/generated.py sind src und pkg nicht ausgeschlossen; generated.py wird anschließend durch file_setup.py:481–482 übersprungen. Das funktioniert auch bei einer bereits getrackten Datei, weil deren Indexstatus nirgends abgefragt wird. Derselbe Ausschluss wirkt beim automatischen Kopieren (1272–1273) und beim Fingerprinting (stats.py:635–640, 1309–1317, 1392–1409). Die reguläre Mutationsliste entsteht wiederum ausschließlich aus walk_source_files (orchestrator.py:1134–1147). Ein erreichbarer erfolgreicher Lauf benötigt weitere reguläre Quellen und Tests, die generated.py weder importieren noch anderweitig voraussetzen; ein fehlgeschlagener Import würde den Fehler dagegen sichtbar machen. Die CLI klassifiziert den Lauf anhand der Auswahloptionen als vollständig (cli.py:714), ohne einen Vergleich mit dem Gitindex. Die geprüften Boundary- und Integrationstests behandeln Muster, explizite Einträge, Staging und Digest-Ausschlüsse; ihre Fixtures erzeugen keinen Gitindex. Insbesondere test_explicit_entry_pointing_at_ignored_tree_is_force_included deckt nur den bereits ausgeschlossenen Konfigurationseintrag ab. Eine Regression für tracked-then-ignored fehlt dort. Bewertung ausschließlich durch Quell- und Testinspektion; keine Tests ausgeführt.

<a id="nondet-basis-toctou-basis-01"></a>

#### BASIS-01: Core-Fingerprinting führt gitignorierte Laufartefakte über Import- und Editable-Bäume wieder ein

**medium · correctness · Konfidenz hoch** — `nondet:basis-toctou` — [src/mutmut_win/stats.py:874](C:/claude_codex/mutmut-win-astra/src/mutmut_win/stats.py:874)

**Mechanismus.** Die normalen Projekt- und sys.path-Walks verwenden GitignoreBoundary. Die Core-Walks in _hash_project_import_core (874–883) und für projektinterne Editable-Installationen (1219–1227) übergeben dagegen kein ignore_boundary. Gitignorierte Dateien verändern dadurch core_digest, obwohl sie aus dem Kontext-Digest und automatischen Staging ausgeschlossen sind. RunBasisEvidence wird als ganzes Dataclass-Objekt verglichen; ausschließlich solcher Drift kann als Änderung ausführbarer Projekteingaben zum Abbruch führen.

**Fehlerszenario.** Ein Projekt ignoriert run.log und startet python -m mutmut_win run mit Ausgabeumleitung in diese lesbare Datei. Die Projektwurzel liegt auf sys.path. Der Core-Walk bindet run.log trotzdem. Eigene Fortschrittsmeldungen nach der initialen Basisaufnahme vergrößern die Datei; die abschließende Aufnahme unterscheidet sich im core_digest und markiert den Lauf als failed. Ein projektinternes Editable eröffnet denselben Pfad. Gleichzeitig schreibende Prozesse können bereits den Doppelvergleich destabilisieren. Die Beteiligung an den gemeldeten Vorfällen ist unbewiesen.

**Wörtlicher Beleg:**

```text
stats.py:528: ignore_boundary: GitignoreBoundary | None = None,
stats.py:874–883:
if not _hash_context_tree(
                    hasher,
                    resolved,
                    label_prefix=f"project-import:{index}:{relative.as_posix() or '.'}",
                    seen=seen,
                    excluded=excluded,
                    skip_dirs=_CONTEXT_SKIP_DIRS,
                    root_skip_dirs=root_skip_dirs,
                ):
stats.py:1219–1227:
and not _hash_context_tree(
                    core_hasher,
                    editable_path,
                    label_prefix=f"project-editable:{identity}",
                    seen=core_seen,
                    excluded=excluded,
                    skip_dirs=_CONTEXT_SKIP_DIRS,
                    root_skip_dirs=_CONTEXT_ROOT_SKIP_DIRS,
                )
orchestrator.py:350–352:
basis_evidence = self._stable_run_basis_evidence()
            watchdog.progress()
            print(f"Execution basis fingerprinted in {time.monotonic() - basis_started:.1f}s")
```

**Fixskizze.** Beide Core-Walks mit derselben GitignoreBoundary wie die korrespondierenden Kontext-Walks ausführen; Dotenv-Ausnahme und explizite Eingaben bewahren. Gesamtes RunBasisEvidence mit Projektwurzel auf sys.path beziehungsweise Editable und einer ignorierten wachsenden Logdatei prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei einem tatsächlich gestarteten Mutationslauf, beispielsweise python -m mutmut_win run > run.log, kann eine lesbare, gitignorierte und nicht ausdrücklich konfigurierte Logdatei innerhalb eines projektinternen Import- oder Editable-Baums ausschließlich den core_digest verändern. Erreicht der Lauf ansonsten den Abschlussvergleich, wird er dadurch als failed erfasst. python -m mutmut_win ohne das Unterkommando run startet diesen Lauf nicht. Ein Zusammenhang mit konkreten gemeldeten Vorfällen bleibt unbewiesen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Eine lesbare, gitignorierte und anderweitig nicht ausgeschlossene Laufdatei kann über projektinterne Import- oder Editable-Bäume ausschließlich den core_digest verändern und einen ansonsten erfolgreichen Mutationslauf als failed enden lassen. Der konkrete CLI-Aufruf benötigt den Unterbefehl run, beispielsweise python -m mutmut_win run > run.log; python -m mutmut_win allein startet keine Mutationspipeline. Die Beteiligung an konkreten Vorfällen bleibt unbewiesen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-staging-toctou-stage-01"></a>

#### STAGE-01: Transienter Lesefehler kann eingefrorene Guard-Dateien bytegleich ersetzen und den eigenen Staging-Abbruch auslösen

**medium · phase-order · Konfidenz mittel** — `nondet:staging-toctou` — [src/mutmut_win/atomic_file.py:302](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:302)

**Mechanismus.** _regular_file_matches_bytes liefert sowohl bei abweichenden/fehlenden Bytes als auch bei OSError des lesenden os.open False. ensure_atomic_bytes veröffentlicht daraufhin per replace eine neue Datei. Für den Phase-Guard geschieht Ensure vor jeder pytest-Phase und jedem Mutationstask nach dem Staging-Snapshot; auch das Stats-Plugin wird erneut sichergestellt. Die bytegleiche Ersetzung kann Zeitstempel verändern, die der Staging-Digest ausdrücklich bindet; eine beobachtbare Änderung jeder Verzeichnismetadatenart auf NTFS ist nicht garantiert.

**Fehlerszenario.** Der Snapshot enthält den richtigen Guard. Ein späteres os.open schlägt einmal durch eine vorübergehende Windows-Dateisperrung fehl. Die Sperre endet vor der anschließenden Veröffentlichung oder erlaubt Ersetzung. Ensure ersetzt identische Bytes erfolgreich und mindestens ein gebundener Metadatenwert ändert sich; die pytest-Phase kann bestehen, aber die nächste Staging-Prüfung bricht wegen selbst verursachter Metadatenänderung ab. Eine Zuordnung zu den beobachteten Vorfällen ist nicht bewiesen.

**Wörtlicher Beleg:**

```text
atomic_file.py:299–306:
fd = os.open(path, flags)
    except FileNotFoundError:
        return False
    except OSError:
        # An unreadable/busy leaf cannot prove that the requested bytes are
        # already published.  The strict writer (or its original error) must
        # decide the operation instead.
        return False
atomic_file.py:483–486:
if _regular_file_matches_bytes(path, payload):
        return
    try:
        atomic_write_bytes(path, payload)
atomic_file.py:391: temp_path.replace(path)
process/worker.py:782: ensure_atomic_bytes(plugin_path, _PYTEST_PHASE_GUARD_SOURCE.encode("utf-8"))
stats.py:678–680:
hash_file_timestamps=True,
        hash_directory_timestamps=True,
        hash_link_counts=True,
orchestrator.py:123–125:
if not current.complete or current != expected:
        raise OrchestratorError(
            "executable staging files changed after mutant generation; the run cannot "
```

**Fixskizze.** Helper vor Snapshot veröffentlichen; spätere produktive Aufrufe ausschließlich prüfen lassen. Transiente Lesefehler begrenzt erneut lesen, aber keine eingefrorene Datei ersetzen. Fehlende, abweichende oder dauerhaft unprüfbare Helper als Boundary-Fehler behandeln. Regression für einmaligen os.open-Fehler nach Snapshot ergänzen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein vorübergehender OSError beim lesenden os.open eines bereits korrekten, eingefrorenen Guards oder Stats-Plugins kann eine bytegleiche Neuveröffentlichung auslösen. Ändert diese vom Staging-Digest erfasste Metadaten, verwirft die nächste Staging-Prüfung den ansonsten erfolgreichen Lauf. Nicht jeder Lesefehler und nicht jeder Metadatenwechsel ist damit zwangsläufig erfasst; insbesondere ist eine stets beobachtbare Änderung der Verzeichnismetadaten auf NTFS nicht garantiert.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-ordering-determinism-order-01"></a>

#### ORDER-01: Legitime Metadaten-Fixture wird abhängig von os.walk-Reihenfolge gelöscht

**medium · nondeterminism · Konfidenz hoch** — `nondet:ordering-determinism` — [src/mutmut_win/file_setup.py:1307](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:1307)

**Mechanismus.** copy_src_dir verarbeitet files unsortiert und erkennt .py.meta anhand Inhalt und bestehendem staged Companion als engine-owned. Ein gültiger Metadaten-Datensatz kann selbst erlaubte Projekt-Fixture sein. Companion-Refresh löscht diese ohne Prüfung ihrer eigenständigen Zugehörigkeit zu Live-Eingaben; vorher abgearbeitete Fixture wird nicht erneut kopiert.

**Fehlerszenario.** Nur src/ wird mutiert. fixtures/other.py und fixtures/other.py.meta sind unselektierte Live-Eingaben; Meta hat gültiges SourceFileMutationData-Schema und beide Hashes passen zum alten other.py. Beide bereits gestaged, dann nur live other.py geändert. Walk-Reihenfolge Meta vor Python: Meta erst behalten, danach beim Python-Refresh gelöscht. Python vor Meta: Meta danach erneut kopiert. Test liest die Fixture und scheitert nur in erster Reihenfolge. Kein zusätzlicher also_copy-Refresh von fixtures. Betroffen ist ausschließlich die Staging-Kopie; die Live-Fixture bleibt erhalten. Die konkrete Reihenfolge auf einem Windows-Dateisystem wurde nicht experimentell belegt.

**Wörtlicher Beleg:**

```python
                        meta_path = Path(str(target_path) + ".meta")
                        owned_meta = read_owned_source_metadata(meta_path) is not None
                        _copy_with_retry(source_path, target_path)
                        print(f"     updated: {source_path} (source changed since last run)")
                        # Invalidate only a proven mutation sidecar.  A project
                        # fixture named like ``runtime.meta`` is an independent
                        # expected target and must survive companion updates.
                        if owned_meta and meta_path.exists():
                            _unlink_staging_file(meta_path)
```

**Fixskizze.** Eigenständige Live-Eingaben vorab bestimmen und nie als abgeleitete Sidecars löschen; Eigentümerschaft an aktuelle Mutationtargets binden. Beide Walk-Reihenfolgen mit gültiger unselektierter .py.meta-Fixture abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Eine zulässige, vollständig schema- und hashkonforme .py.meta-Fixture neben einer unselektierten Python-Datei kann beim inkrementellen Refresh abhängig von der Dateireihenfolge aus dem Staging gelöscht werden. Die Live-Fixture bleibt erhalten; betroffen ist der Testeingabestand dieses Laufs.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-stats-stats-01"></a>

#### STATS-01: Editable-Quellpfade werden doppelt URL-dekodiert

**medium · correctness · Konfidenz hoch** — `mod:stats` — [src/mutmut_win/stats.py:487](C:/claude_codex/mutmut-win-astra/src/mutmut_win/stats.py:487)

**Mechanismus.** url2pathname dekodiert Prozentsequenzen selbst. Vorgeschaltetes unquote verändert gültige Dateinamen mit literalem %xx und bindet falschen Editable-Quellbaum.

**Fehlerszenario.** Eine installierte Editable-Distribution besitzt die gültige Datei-URL file:///C:/deps/demo%2520repo für das reale Verzeichnis C:/deps/demo%20repo. Die doppelte Dekodierung hasht stattdessen C:/deps/demo repo. Fehlt dieses Ziel, wird die Basis unnötig unvollständig. Existiert es, kann der tatsächliche Quellbaum ungebunden bleiben und die Basis dennoch vollständig erscheinen, wenn ein Import-Finder den echten externen Baum erschließt und weder Projekt-, Konfigurations-, Distributionsdatei- noch sys.path-Bäume ihn anderweitig erfassen. Die stärkere Finder-Folge ist statisch hergeleitet, nicht durch eine Installation oder einen Projektlauf reproduziert.

**Wörtlicher Beleg:**

```python
raw_path = urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
```

**Fixskizze.** parsed.path genau einmal mit url2pathname dekodieren; Literal-%20/%25 und existierenden falsch dekodierten Nachbar abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Editable-Datei-URLs werden doppelt dekodiert. Bei einem literalen %20 im Quellverzeichnis wird der falsche Baum verwendet. Fehlt dieser, wird die Basis unnötig unvollständig. Existiert er, kann complete=True trotz fehlender Bindung des tatsächlichen Quellbaums entstehen, sofern dieser über einen Finder erreichbar ist und weder durch Distribution-Dateiinventar noch Projekt-, Konfigurations- oder sys.path-Bäume anderweitig erfasst wird.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Editable-URLs mit kodierten literalen Prozentsequenzen werden doppelt dekodiert. Ein fehlender falsch dekodierter Zielbaum macht die Basis unvollständig. Existiert dieser Zielbaum, kann die Basis trotz fehlender Bindung des echten Quellbaums vollständig erscheinen, sofern dieser auch über keine anderen erfassten Projekt-, Konfigurations-, Distributions- oder Importbäume abgedeckt wird; die Finder-Variante ist statisch hergeleitet, nicht als vollständiger Lauf reproduziert.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-file-setup-file-02"></a>

#### FILE-02: Relative ..-Pfade umgehen Metadatenreservierung und erzeugen falsche Mutantnamen

**medium · correctness · Konfidenz hoch** — `mod:file-setup` — [src/mutmut_win/file_setup.py:842](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:842)

**Mechanismus.** Die Konfiguration prüft das aufgelöste Containment, behält aber die relative Schreibweise. Die Einzeldatei-Discovery reicht diese weiter: Der Namespace reserviert src/../src/mod.py.meta, während die automatische Kopie src/mod.py.meta plant. _staging_key entfernt nur leere und '.'-Komponenten, sodass verschiedene Schlüssel dasselbe Ziel erreichen. get_mutant_name zerlegt ebenfalls den unnormalisierten Pfad.

**Fehlerszenario.** Eine vorhandene, nicht ausgeschlossene Einzeldatei src/mod.py ist als paths_to_mutate=['src/../src/mod.py'] konfiguriert; daneben liegt eine nicht ignorierte Fixture src/mod.py.meta. Der Preflight übersieht die Kollision; die Fixture wird kopiert und ihre Staging-Kopie durch save_generation_metadata ersetzt. Die Originalfixture im Projekt bleibt erhalten. Auch ohne Fixture erzeugt get_mutant_name beispielsweise '...src.mod.x_f__mutmut_1' statt 'mod.x_f__mutmut_1'.

**Wörtlicher Beleg:**

```python
    for source in walk_source_files(config):
        if config.should_ignore_for_mutation(source):
            continue
        metadata_target = Path(f"{source}.meta")
        exact_owners[_staging_key(metadata_target)] = f"mutation metadata for {source}"
```

**Fixskizze.** Nach Containment eine kanonische projektrelative Identität durch Discovery, Reservierung, Generation, Metadaten und Namen verwenden. Vor Publish gegen Nutzerfixtures prüfen; '..'-Aliase abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein innerhalb des Projekts verbleibender relativer '..'-Alias kann die Metadatenreservierung umgehen und falsche qualifizierte Mutantnamen erzeugen. Bei einer gleichnamigen, automatisch kopierten Fixture wird deren Staging-Kopie durch Metadaten ersetzt; die Originalfixture außerhalb von mutants bleibt erhalten.
- Erreichbarkeit: angenommen, Konfidenz hoch. Ein projektinterner relativer '..'-Alias in paths_to_mutate umgeht bei einer vorhandenen, nicht ausgeschlossenen Einzeldatei die Metadatenreservierung und erzeugt falsche qualifizierte Mutantnamen. Eine mitkopierte, nicht ignorierte Fixture src/mod.py.meta kann während der Generation im Staging ersetzt werden; die ursprüngliche Fixture im Projekt wird dadurch nicht überschrieben.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-file-setup-file-03"></a>

#### FILE-03: Inzwischen abgewählte Quelldateien behalten frühere Instrumentierung

**medium · correctness · Konfidenz hoch** — `mod:file-setup` — [src/mutmut_win/file_setup.py:1639](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:1639)

**Mechanismus.** Erhaltung früherer Generatorausgabe bindet Quellhash, nicht aktuelle Mutationseignung. Löschpass behält Sidecar bei erwartetem Companion. Orchestrator regeneriert nur aktuelle Auswahl; Konfigurationsfingerprint restauriert abgewählte Dateien nicht.

**Fehlerszenario.** Nach einem Lauf wird src/old.py dateiweise per do_not_mutate oder paths_to_mutate ausgeschlossen, bleibt aber als unveränderte Abhängigkeit im automatisch gespiegelten Quellbaum. Ein Folgelauf ohne --force behält dort Generatorausgabe und Sidecar. Solange mindestens ein anderer Mutant ausgewählt bleibt, kann ein Testaufruf allein der ausgeschlossenen old.py die Forced-fail-Prüfung durch MutmutProgrammaticFailException erfüllen. Ohne verbleibende Mutanten wird diese Phase nicht erreicht. Introspektion der ausgeschlossenen Funktionen sieht ebenfalls die alte Instrumentierung.

**Wörtlicher Beleg:**

```python
                if name.casefold().endswith(".meta"):
                    companion = Path(str(staged)[: -len(".meta")]).absolute()
                    if (
                        companion in expected_absolute
                        and read_owned_source_metadata(staged) is not None
                    ):
                        continue
```

**Fixskizze.** Aktuelle Mutationsberechtigung im Mirror beachten; abgewählte Generatorausgaben durch Originale ersetzen und nur eigene Sidecars entfernen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Eine zuvor instrumentierte, unveränderte Quelldatei behält nach Ausschluss über do_not_mutate oder paths_to_mutate ihre Generatorausgabe und Sidecar im Staging. Bleibt mindestens ein anderer Mutant ausgewählt und rufen Tests ausschließlich die ausgeschlossene instrumentierte Datei auf, kann diese allein die Forced-fail-Prüfung erfüllen. Auch die Introspektion dieser ausgeschlossenen Datei bleibt durch die Instrumentierung beeinflusst.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei einem Folgelauf ohne --force können unveränderte, zuvor instrumentierte und weiterhin automatisch gespiegelte Quelldateien nach dateiweiser Abwahl ihre Instrumentierung behalten. Bei mindestens einem verbleibenden Mutanten kann die Forced-fail-Prüfung allein durch einen Aufruf der inzwischen ausgeschlossenen Datei erfüllt werden.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-file-setup-file-04"></a>

#### FILE-04: Datei-Verzeichnis-Typwechsel blockieren inkrementellen Mirror

**medium · correctness · Konfidenz hoch** — `mod:file-setup` — [src/mutmut_win/file_setup.py:1267](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:1267)

**Mechanismus.** Kopierphase materialisiert aktuellen Typ vor Bereinigung alten Typs. Datei am Verzeichnisziel lässt mkdir scheitern; Verzeichnis am Dateiziel kann atomic_copy_file nicht ersetzen. _sync_tree und Einzeldatei-also_copy haben gleiche Lücke.

**Fehlerszenario.** Der erste Lauf spiegelt fixtures/payload als Datei. Vor dem nächsten Lauf wird der Livepfad durch ein gültiges Verzeichnis mit Fixtures ersetzt; ohne --force scheitert der Lauf beim mkdir auf der alten Staging-Datei. Die Umkehr scheitert beim Datei-über-Verzeichnis-Ersatz oder bereits bei der Frischeprüfung. Ein Force-Neuaufbau beseitigt den Zustand; Datenverlust oder ein falsch ausgewiesenes Ergebnis sind nicht belegt.

**Wörtlicher Beleg:**

```python
            target_directory = Path("mutants") / root_str
            _validated_staging_destination(target_directory, mutants_root)
            target_directory.mkdir(exist_ok=True, parents=True)
```

**Fixskizze.** Zieltyp vor Materialisierung vergleichen und nachweislich stagingeigenen abweichenden Eintrag sicher bereinigen. Beide Richtungen in automatischen/konfigurierten Bäumen abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Datei-/Verzeichniswechsel zwischen zwei inkrementellen Läufen werden vor der Materialisierung nicht aufgelöst und können den Lauf abbrechen. In Richtung Verzeichnis → Datei erfolgt der Abbruch beim atomaren Ersatz oder bereits bei der Frischeprüfung.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-file-setup-file-05"></a>

#### FILE-05: Automatisch ignorierte Verzeichnisse bleiben als importierbare Hüllen zurück

**medium · nondeterminism · Konfidenz hoch** — `mod:file-setup` — [src/mutmut_win/file_setup.py:1670](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:1670)

**Mechanismus.** Automatischer Kopier-/Löschpass entfernt ignorierte Dateien, bei leeren Verzeichnissen prüft _sync_deleted_sources aber nur Live-Existenz/Linkstatus, nicht Ignore oder geplante Verzeichnisse. Existierendes ausgeschlossenes Verzeichnis bleibt erhalten.

**Fehlerszenario.** optionalpkg/ im Projektstamm wird zunächst automatisch gespiegelt und anschließend gitignoriert; das Live-Verzeichnis bleibt bestehen und ist nicht explizit zur Kopie konfiguriert. Der Folgelauf lässt eine leere mutants/optionalpkg-Hülle zurück, ein frischer Aufbau nicht. Verzeichnisexistenztests unterscheiden sich unmittelbar; ohne anderweitigen gleichnamigen Importanbieter kann auch find_spec wegen des leeren PEP-420-Namensraums unterscheiden. Ein konkretes falsches Mutationsergebnis wurde dadurch nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
                source_directory_is_current = source_directory.is_dir() and not _is_link_or_reparse(
                    source_directory
                )
            except OSError:
                source_directory_is_current = False
            if source_directory_is_current:
                continue
```

**Fixskizze.** Erwartete Verzeichnisse führen oder Ignoregrenze im automatischen Löschpass identisch prüfen; ungeplante leere Hüllen entfernen, erlaubte Leerordner bewahren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-file-setup-file-06"></a>

#### FILE-06: Pyproject-Bereinigung löscht Tabellenmuster innerhalb gültiger TOML-Strings

**medium · correctness · Konfidenz hoch** — `mod:file-setup` — [src/mutmut_win/file_setup.py:1905](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:1905)

**Mechanismus.** Ungeankerter Regex ohne TOML-Stringzustand behandelt '[tool.uv.sources]' in Mehrzeilenstrings als Tabelle und entfernt Inhalt einschließlich Stringende bis nächster '['-Zeile oder EOF. Veröffentlichung erfolgt ohne TOML-Nachvalidierung.

**Fehlerszenario.** Eine gültige pyproject.toml enthält einen Dokumentations- oder Vorlagen-Mehrzeilenstring mit dem Text [tool.uv.sources]. Der standardmäßig ausgeführte Sanitizer entfernt dessen Inhalt samt Stringabschluss, obwohl keine echte uv-Tabelle existieren muss. Im Staging entstehen dadurch ungültiges TOML oder veränderte Konfigurationsdaten; die spätere pytest-Konfigurationsprüfung kann den Lauf abbrechen. Die Originaldatei bleibt unberührt.

**Wörtlicher Beleg:**

```python
    cleaned = re.sub(
        r"\[tool\.uv\.sources(?:\.[^\]]+)?\]\s*\n(?:(?!\[)[^\n]*\n?)*",
        "",
        content,
    )
```

**Fixskizze.** TOML-Syntax statt Textregex verwenden, nur echte Tabelle entfernen und Ergebnis vor Publish parsen; Tabellenmuster in Strings/Kommentaren erhalten.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Der standardmäßig ausgeführte Sanitizer kann Tabellenmuster innerhalb gültiger TOML-Mehrzeilenstrings entfernen und dadurch die staged pyproject.toml beschädigen. Eine Syntaxprüfung erfolgt nicht vor dem Schreiben; die spätere pytest-Konfigurationsprüfung kann die Beschädigung erkennen und den Lauf abbrechen. Die Originaldatei bleibt unberührt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-rest-rest-02"></a>

#### REST-02: Coverage mit relative_files wird als ungemessen abgewiesen

**medium · correctness · Konfidenz hoch** — `mod:rest` — [src/mutmut_win/code_coverage.py:120](C:/claude_codex/mutmut-win-astra/src/mutmut_win/code_coverage.py:120)

**Mechanismus.** gather_coverage normalisiert gemessene Dateinamen nur mit normcase, bildet seine Nachschlageschlüssel jedoch stets als absolute Pfade unter mutants. Der Coverage-Aufruf übernimmt die Projektkonfiguration und erzwingt keine absolute Speicherung. Relative Messpfade passen deshalb nicht zu den absoluten Schlüsseln.

**Fehlerszenario.** mutate_only_covered_lines=true und [tool.coverage.run] relative_files=true in der automatisch kopierten pyproject.toml liefern relative Messpfade wie src/pkg/mod.py. Bei ausschließlich solchen Messpfaden bricht gather_coverage trotz ausgeführtem Quellcode mit 'measured no coverage' ab. Entsprechendes gilt für [coverage:run] in setup.cfg; eine .coveragerc mit [run] muss etwa über also_copy ins Staging übernommen werden.

**Wörtlicher Beleg:**

```python
measured = {
            os.path.normcase(f): set(coverage_data.lines(f) or [])
            for f in coverage_data.measured_files()
        }

    covered_lines: dict[str, set[int]] = {}
    for filename in source_files:
        covered_lines[_normalized_key(filename)] = measured.get(_normalized_key(filename), set())
```

**Fixskizze.** Relative Messpfade gegen das tatsächliche Coverage-Arbeitsverzeichnis auflösen oder die interne Speicheroption verbindlich setzen; die übernommenen Konfigurationsformate gezielt absichern.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei mutate_only_covered_lines=true und wirksamer Coverage-Konfiguration relative_files=true, beispielsweise [tool.coverage.run] relative_files=true in der automatisch kopierten pyproject.toml, ordnet gather_coverage relative Messpfade den absoluten Staging-Schlüsseln nicht zu und bricht trotz ausgeführtem Quellcode mit 'measured no coverage' ab. Die ursprüngliche Schreibweise [run] gilt für eine .coveragerc; diese wird nicht standardmäßig kopiert und muss beispielsweise über also_copy ins Staging gelangen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Erreichbar mit relative_files=true in einer übernommenen Coverage-Konfiguration, insbesondere [coverage:run] in setup.cfg oder [tool.coverage.run] in pyproject.toml. Eine alleinige .coveragerc mit [run] wird nicht standardmäßig kopiert; dafür muss ihre Übernahme beispielsweise über also_copy ausdrücklich konfiguriert sein.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-rest-rest-03"></a>

#### REST-03: Coverage-Parallelkonfiguration lässt vorhandene Messdaten übersehen

**medium · correctness · Konfidenz hoch** — `mod:rest` — [src/mutmut_win/code_coverage.py:111](C:/claude_codex/mutmut-win-astra/src/mutmut_win/code_coverage.py:111)

**Mechanismus.** gather_coverage erwartet die Datei .coverage.mutmut mit exakt diesem Namen. Der Coverage-Unterprozess übernimmt parallel=true aus der Projektkonfiguration; --data-file legt dabei nur den Basisnamen fest und verhindert die angehängten Host-/PID-/Zufallssuffixe nicht. Eine Zusammenführung der Dateien erfolgt nicht.

**Fehlerszenario.** Eine serielle Testsuite läuft erfolgreich mit mutate_only_covered_lines=true und [tool.coverage.run] parallel=true in der automatisch kopierten pyproject.toml. Coverage schreibt .coverage.mutmut.<Suffix> in das frische Ausgabeverzeichnis. Der Aufrufer findet den suffixlosen Namen nicht und bricht mit 'produced no data file' ab. Entsprechendes gilt für setup.cfg oder eine tatsächlich ins Staging übernommene .coveragerc.

**Wörtlicher Beleg:**

```python
data_file = (Path(output_name) / ".coverage.mutmut").absolute()
        exit_code = runner.run_coverage_collection(data_file)
        if exit_code != 0:
            raise CoverageCollectionError(
                f"coverage collection run failed with exit code {exit_code} — "
                f"the test suite must pass before mutate_only_covered_lines can "
                f"measure it."
            )
        if not data_file.exists():
            raise CoverageCollectionError(
                "coverage collection produced no data file — coverage did not record anything."
            )
```

**Fixskizze.** Für die interne Einzelprozessmessung den Parallelmodus verbindlich deaktivieren oder ausschließlich die frisch erzeugten Ausgabedateien kontrolliert zusammenführen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Wenn die im Coverage-Unterprozess wirksame Konfiguration parallel=true setzt, kann eine erfolgreiche serielle Testsuite ausschließlich eine Datei .coverage.mutmut.<Suffix> erzeugen. gather_coverage verlangt jedoch den exakten Basisnamen und meldet deshalb fälschlich, Coverage habe nichts aufgezeichnet. Sicher erreichbar ist dies über die standardmäßig kopierte pyproject.toml beziehungsweise setup.cfg; eine ausschließlich vorhandene .coveragerc muss zusätzlich tatsächlich ins Staging gelangen oder anderweitig als Coverage-Konfiguration wirksam sein.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei wirksam im Coverage-Unterprozess geladener Parallelkonfiguration – etwa in der standardmäßig kopierten pyproject.toml/setup.cfg oder einer über also_copy bereitgestellten .coveragerc – weist mutate_only_covered_lines einen erfolgreichen seriellen Messlauf als fehlende Datendatei zurück, weil ausschließlich der unsuffigierte Basisname geprüft wird.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-rest-rest-05"></a>

#### REST-05: Unlesbare untergeordnete Ignore-Datei verliert einschließende Ausnahmen

**medium · error-handling · Konfidenz hoch** — `mod:rest` — [src/mutmut_win/gitignore_boundary.py:95](C:/claude_codex/mutmut-win-astra/src/mutmut_win/gitignore_boundary.py:95)

**Mechanismus.** Eine unlesbare .gitignore-Ebene wird wie eine fehlende Ebene behandelt. enter() erhält dabei die Regeln ihrer Eltern. Enthält die verlorene Ebene eine einschließende Negation, bleibt somit die ausschließende Elternregel wirksam. Das verletzt den dokumentierten Vertrag, bei Lesefehlern konservativ eher zu viel zu erfassen.

**Fehlerszenario.** Die Root-.gitignore enthält *.py, src/.gitignore enthält !keep.py, und paths_to_mutate=['src'] ist konfiguriert. Wird ausschließlich die untergeordnete Ignore-Datei vorübergehend unlesbar, entfällt ihre Negation. Da src selbst nicht ausgeschlossen ist, setzt descend_forced die Elternregel nicht zurück. walk_all_files überspringt die weiterhin lesbare keep.py. Ein erfolgreich abgeschlossener Gesamtlauf mit falschem Ergebnis ist damit noch nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
except (OSError, UnicodeDecodeError) as exc:
        logger.warning(
            "Ignoring unreadable .gitignore at %s (%s); it excludes nothing",
            ignore_file,
            type(exc).__name__,
        )
        return None
```

**Fixskizze.** Fehlende und unlesbare Ignore-Ebenen unterscheiden. Bei einer unlesbaren Ebene entweder kontrolliert abbrechen oder geerbte Ausschlüsse im betroffenen Teilbaum nicht als verlässlich behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-windows-win-02"></a>

#### WIN-02: --force kann regulär erzeugte schreibgeschützte Staging-Fixtures nicht entfernen

**medium · windows · Konfidenz hoch** — `lens:windows` — [src/mutmut_win/cli.py:151](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:151)

**Mechanismus.** Das reguläre Staging bewahrt den schreibgeschützten Quellmodus über atomic_copy_file und chmod. --force verwendet dagegen rmtree(ignore_errors=True) ohne die bereits an anderer Stelle vorhandene Readonly-Behandlung. Wiederholtes Löschen beseitigt das Windows-Readonly-Attribut nicht.

**Fehlerszenario.** Eine schreibgeschützte runtime.cfg wird über also_copy erfolgreich ins Staging übernommen. Der nächste --force-Lauf kann andere Dateien entfernen, scheitert aber auch ohne fremden offenen Handle an dieser Fixture. Nach drei begrenzten Löschversuchen endet er mit Exitcode 1 und der Meldung 'Could not fully remove mutants/ (files in use?); refusing to run with stale state.'. Solange das Attribut besteht, bleibt der Fehler wiederholbar. Es entsteht kein unbegrenzter Hänger und kein falscher Erfolg.

**Wörtlicher Beleg:**

```python
for delay in (0.0, *_FORCE_CLEANUP_RETRY_DELAYS):
        if delay:
            time.sleep(delay)
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return True
    return False
```

**Fixskizze.** Nachgewiesen eigene reguläre Readonly-Blätter unter Beachtung der Identitäts-, Reparse- und Hardlinkprüfungen beschreibbar machen und löschen. Echte Sperren weiterhin kontrolliert ablehnen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. --force kann eine regulär über also_copy gestagte schreibgeschützte Datei unter Windows nicht entfernen und bricht nach drei Löschversuchen mit Exitcode 1 ab. Es handelt sich um einen reproduktionsbedürftigen, durch Code und vorhandene Staging-Tests klar gestützten Abbruchpfad, nicht um einen unbegrenzten Hänger.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Unter Windows kann eine regulär über also_copy gestagte schreibgeschützte Datei den anschließenden --force-Lauf dauerhaft mit Exit 1 blockieren, solange ihr Readonly-Attribut bestehen bleibt. Die Ausgabe `Could not fully remove mutants/ (files in use?); refusing to run with stale state.` vermutet eine Dateisperre lediglich als mögliche Ursache.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-windows-win-03"></a>

#### WIN-03: Unicode-casefold meldet für verschiedene NTFS-Dateien falsche Kollision

**medium · windows · Konfidenz hoch** — `lens:windows` — [src/mutmut_win/file_setup.py:520](C:/claude_codex/mutmut-win-astra/src/mutmut_win/file_setup.py:520)

**Mechanismus.** _staging_key verwendet vollständiges Unicode-casefold mit Mehrzeichenabbildungen wie ß→ss. Das entspricht nicht der NTFS-Namensidentität. Verschiedene Zielnamen erhalten dadurch denselben Schlüssel; die anschließende samefile-Prüfung erkennt ihre Quellen zutreffend als verschiedene Dateien und löst deshalb eine falsche Kollisionsablehnung aus.

**Fehlerszenario.** Ein also_copy-Verzeichnis enthält die beiden gewöhnlichen, getrennten Dateien maße.json und masse.json; keine Ignore-Regel schließt sie aus. Beide Zielschlüssel werden zu masse.json gefaltet. Der Preflight sammelt den vermeintlichen Konflikt und beendet den regulären CLI-Lauf mit StagingNamespaceCollisionError beziehungsweise Exitcode 2. Tatsächliche Aliase desselben Dateiobjekts werden durch samefile geschützt, dieses Paar jedoch nicht.

**Wörtlicher Beleg:**

```python
return tuple(part.casefold() for part in path.parts if part not in {"", "."})

...

        target_key = _staging_key(target)
        previous = target_owners.get(target_key)
        if previous is not None and not _same_live_input(previous[0], source):
            collisions.add(
```

**Fixskizze.** Einen zur Windows-Dateinamensidentität passenden Vergleich ohne vollständige Mehrzeichenfaltung verwenden und mit tatsächlicher Dateiidentität verbinden. Sowohl verschiedene ß/ss-Namen als auch echte Case-Aliase absichern.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-windows-win-05"></a>

#### WIN-05: Editable-Datei-URLs werden doppelt dekodiert

**medium · correctness · Konfidenz hoch** — `lens:windows` — [src/mutmut_win/stats.py:487](C:/claude_codex/mutmut-win-astra/src/mutmut_win/stats.py:487)

**Mechanismus.** url2pathname dekodiert Prozentsequenzen bereits selbst. Das vorgeschaltete unquote interpretiert daher auch Prozentsequenzen ein zweites Mal, die zum wörtlichen Verzeichnisnamen gehören. Der falsch aufgelöste Pfad wird unmittelbar als Editable-Quellbaum gehasht.

**Fehlerszenario.** Eine installierte Editable-Abhängigkeit liegt unter C:\work\dep%20copy; ihre gültige file-URL enthält dep%2520copy. Der Code untersucht stattdessen C:\work\dep copy. Fehlt dieser Nachbar, scheitert die strikte Pfadauflösung und reuse_safe wird False. Selbst wenn der tatsächliche Quellbaum später über sys.path erfasst wird, bleibt die Basis unvollständig und erhält no-reuse:. Belegt ist in diesem Szenario die unnötige Wiederverwendungssperre, kein falsches Mutationsergebnis.

**Wörtlicher Beleg:**

```python
raw_path = urllib.request.url2pathname(urllib.parse.unquote(parsed.path))
    if os.name == "nt" and len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    return Path(raw_path)
```

**Fixskizze.** parsed.path genau einmal durch url2pathname dekodieren und wörtliche Prozentsequenzen im Verzeichnisnamen absichern.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-ordering-determinism-order-02"></a>

#### ORDER-02: Generierter sitecustomize-Quelltext hängt vom zufälligen Python-Hashseed ab

**low · nondeterminism · Konfidenz hoch** — `nondet:ordering-determinism` — [src/mutmut_win/runner.py:942](C:/claude_codex/mutmut-win-astra/src/mutmut_win/runner.py:942)

**Mechanismus.** repr(set(real_src_dirs)) verwirft SOURCE_ROOT_NAMES-Reihenfolge und serialisiert hashabhängige Mengenreihenfolge in ausführbaren Quelltext; keine anschließende Kanonisierung.

**Fehlerszenario.** Ein unverändertes Projekt hat verschiedene src/- und source/-Verzeichnisse. Python-Prozesse mit unterschiedlichen Hashseeds können unterschiedliche _shadow-Zeilen und damit sitecustomize.py-Bytes/Inhaltshashes erzeugen. Importfilterwirkung bleibt gleich; falsches Mutationsurteil oder regulärer Cacheausfall sind hiermit nicht bewiesen.

**Wörtlicher Beleg:**

```python
        dirs_repr = repr(set(real_src_dirs))
        blocker_source = (
            f"# Auto-generated by mutmut-win — removes editable-install .pth paths\n"
            f"import os\n"
            f"import sys\n"
            f"_shadow = {dirs_repr}\n"
```

**Fixskizze.** Die sortierten eindeutigen Pfade als Tupelliteral serialisieren oder generierten Code set([...]) mit einer sortierten Listenliteral-Darstellung erzeugen; nicht erneut repr einer Menge verwenden. Beide Source-Roots und verschiedene Seeds vergleichen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-ordering-determinism-order-03"></a>

#### ORDER-03: Unsortierte automatisch ergänzte Testdateien verändern den Kontextfingerprint

**low · nondeterminism · Konfidenz mittel** — `nondet:ordering-determinism` — [src/mutmut_win/config.py:438](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:438)

**Mechanismus.** Path.glob-Ergebnisse werden ungeordnet an also_copy angehängt. _build_stats_context_evidence serialisiert config.model_dump; json.dumps(sort_keys=True) sortiert keine Liste. Spätere Baumsortierung und separater Generierungsfingerprint entfernen den abweichenden Konfigurationsanteil nicht.

**Fehlerszenario.** Root enthält test_a.py und test_b.py. Unterschiedliche zulässige Glob-Reihenfolgen erzeugen bei gleicher Nutzerkonfiguration andere also_copy-Listen und Kontextfingerprints. collect_or_load_stats sammelt unnötig neu; abweichender tests_fingerprint verhindert Verdict-Reuse. Kein behaupteter Exportfehler, da dieser gespeicherte Konfiguration rekonstruiert. Erforderlich ist eine tatsächlich andere Aufzählungsreihenfolge; ein spontaner Wechsel auf dem konkret eingesetzten Windows-Dateisystem wurde nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
    ] + [str(p.relative_to(project_dir)) for p in project_dir.glob("test*.py")]
    return config.model_copy(update={"also_copy": config.also_copy + default_also_copy})
```

**Fixskizze.** Nur automatisch gefundene test*.py-Pfade stabil sortieren, explizite Nutzerreihenfolge bewahren; umgekehrte Glob-Reihenfolge auf gleiche effektive Konfiguration und Digests prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low. Wenn die Windows-Verzeichnisaufzählung dieselben automatisch ergänzten test*.py-Pfade in anderer Reihenfolge liefert, ändern sich bei ansonsten gleichen Eingaben Kontext- und Tests-Fingerprint. Dadurch können ansonsten wiederverwendbare Statistiken und Verdicts unnötig neu berechnet werden. Eine spontane Reihenfolgeänderung auf dem konkret eingesetzten Dateisystem ist nicht nachgewiesen.
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low. Automatisch ergänzte Root-Testpfade sind nicht kanonisch geordnet. Wenn die Dateisystem-Aufzählung bei identischen Dateinamen und Inhalten eine andere Reihenfolge liefert, ändern sich Kontextfingerprint und davon abgeleitete Verdict-Fingerprints unnötig. Ein spontaner Reihenfolgenwechsel bei unverändertem lokalen Windows-Dateisystem ist damit nicht nachgewiesen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-stats-stats-02"></a>

#### STATS-02: Große JSON-Ganzzahlen lassen Stats-Cache-Lader abstürzen

**low · error-handling · Konfidenz hoch** — `mod:stats` — [src/mutmut_win/stats.py:161](C:/claude_codex/mutmut-win-astra/src/mutmut_win/stats.py:161)

**Mechanismus.** Typprüfung akzeptiert große int-Werte. math.isfinite konvertiert nach float und kann OverflowError auslösen; duration_by_test und stats_time fangen dies nicht ab, sodass None-Fallback für ungültigen Cache verlassen wird.

**Fehlerszenario.** Ein bearbeiteter oder beschädigter, syntaktisch gültiger mutmut-stats.json-Cache enthält eine positive Zahl mit etwa 401 Dezimalstellen in stats_time oder duration_by_test. JSON parst, math.isfinite wirft OverflowError, und collect_or_load_stats bricht statt neu zu sammeln ab. Reguläre Zeitmessungen erzeugen diesen Zustand nicht nachweislich.

**Wörtlicher Beleg:**

```python
or not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not math.isfinite(value)
```

**Fixskizze.** Gemeinsamer Zahlenvalidator mit OverflowError-Fallback; sehr große positive/negative JSON-Ints testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Ein syntaktisch gültiger, aber numerisch ungültiger lokaler Stats-Cache mit einer übergroßen Ganzzahl in stats_time oder duration_by_test verursacht einen unbehandelten OverflowError und verhindert die vorgesehene Neusammlung. Betroffen ist die Robustheit gegenüber bearbeiteten oder beschädigten Caches; reguläre Zeitmessungen erzeugen diesen Zustand nicht nachweislich.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-data-data-03"></a>

#### DATA-03: Große JSON-Integer durchbrechen Metadaten-Heilung

**low · error-handling · Konfidenz hoch** — `mod:data` — [src/mutmut_win/models.py:346](C:/claude_codex/mutmut-win-astra/src/mutmut_win/models.py:346)

**Mechanismus.** Die Zahlenvalidierung akzeptiert zunächst Integer und übergibt sie math.isfinite. Eine 401-stellige JSON-Ganzzahl wird erfolgreich eingelesen, erzeugt bei der Float-Konvertierung aber OverflowError. load fängt um die Feldvalidierung nur TypeError und ValueError; Rücksetzung und Heilung werden dadurch übersprungen. source_mtime verwendet dieselbe fehlbare Prüfung wie die Dauerfelder.

**Fehlerszenario.** Eine ansonsten gültige .py.meta wird manuell verändert oder anderweitig beschädigt und enthält eine 401-stellige Ganzzahl in durations_by_key, estimated_durations_by_key oder source_mtime. Die Besitzprüfung kann weiterhin bestehen; der Ladezugriff scheitert jedoch ohne Heilung. Im Generierungs-Fastpath wird dies auf höherer Ebene zu einem kontrollierten Generierungsfehler, während auch show/apply beim Laden betroffen sind. Wiederholte Fastpath-Läufe bleiben beeinträchtigt; eine erzwungene Regenerierung ohne Fastpath kann die Metadaten ersetzen. Reguläre Zeitmessungen erzeugen solche Werte nicht nachweislich; falsche Mutationsergebnisse oder Datenverlust sind damit nicht belegt.

**Wörtlicher Beleg:**

```python
or not math.isfinite(value)
```

**Fixskizze.** OverflowError in die Zahlen- und Korruptionsbehandlung aufnehmen. An der früheren JSON-Parsergrenze auch den ValueError für Ganzzahlen jenseits des aktivierten CPython-Ziffernlimits behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Eine bestehende, ansonsten gültige .py.meta kann durch einen nachträglich eingetragenen übergroßen Integer in einem der genannten Felder die zugesagte Korruptionsheilung umgehen. Wiederholte Ladezugriffe schlagen fehl; Generierung über den Fastpath endet kontrolliert mit einem Fehler. Dies gilt nicht zwingend für jeden späteren Lauf: Eine erzwungene Neugenerierung mit allow_fast_path=False kann die Metadaten ersetzen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Manuell veränderte oder anderweitig korrumpierte Metadaten mit einem 401-stelligen Integer in einem der genannten Felder umgehen die Heilung und verhindern betroffene Ladezugriffe. Wiederholte Läufe mit aktivem Generierungsfastpath bleiben betroffen. Die Blockade ist nicht ausnahmslos dauerhaft: Eine Regenerierung mit allow_fast_path=False, etwa nach geändertem Konfigurationsfingerprint (orchestrator.py:1185–1187), kann die betroffenen Metadaten ersetzen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-08"></a>

#### EDGE-08: Windows-Umgebungswerte mit unpaarigen Surrogaten brechen die Basisberechnung

**low · windows · Konfidenz mittel** — `lens:boundaries` — [src/mutmut_win/stats.py:702](C:/claude_codex/mutmut-win-astra/src/mutmut_win/stats.py:702)

**Mechanismus.** Der Umgebungshash iteriert sämtliche os.environ-Einträge und kodiert Namen und Werte als UTF-8 mit surrogateescape. Dieser Fehlerhandler bildet nur U+DC80 bis U+DCFF ab; ein unpaariges U+D800 löst UnicodeEncodeError aus. _installed_distribution_basis ruft den Umgebungshash vor seinem lokalen Fehlerfang auf; auch Diagnose-Wrapper reichen den Fehler weiter.

**Fehlerszenario.** Wenn die Windows-Prozessumgebung einen Zusatzwert mit dem einzelnen Codepunkt U+D800 enthält, scheitert die Basisberechnung vor der Mutation an dessen Kodierung. Reine API-Checks bestätigen die Darstellbarkeit im Python-Windows-Umgebungsencoder und in einem Wide-Character-Puffer. Die tatsächliche Vererbung dieses Werts über einen Windows-Prozessstart wurde nicht reproduziert und bleibt eine Grenze dieses Szenarios.

**Wörtlicher Beleg:**

```python
encoded_name = name.encode("utf-8", errors="surrogateescape")
encoded_value = value.encode("utf-8", errors="surrogateescape")
```

**Fixskizze.** Windows-Werte verlustfrei kodieren, beispielsweise UTF-8 mit surrogatepass und versionierter Hashsemantik; POSIX-surrogateescape-Semantik getrennt erhalten.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low.
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

### Prozesslebenszyklus, Sperren und Ressourcen

<a id="mod-locking-lock-01"></a>

#### LOCK-01: Abweichende Temp-Verzeichnisse entkoppeln Sperren derselben Datenbank

**high · race · Konfidenz hoch** — `mod:locking` — [src/mutmut_win/process/run_lock.py:717](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/run_lock.py:717)

**Mechanismus.** Die Pfad- und Dateiidentitätslocks einer Datenbank liegen unter dem prozesslokal ermittelten tempfile.gettempdir(). Verschiedene effektive Temp-Wurzeln erzeugen trotz gleicher Datenbank verschiedene Guard- und Ownerdateien; die Besitzerprüfung sieht nur die jeweilige Temp-Domäne. Der Workspace-Lock bindet nur denselben cwd. Nach dem vermeintlich exklusiven DB-Erwerb beendet die Recovery jeden vorhandenen running-Datensatz ohne weitere Prozessbesitzerprüfung.

**Fehlerszenario.** Zwei Windows-Prozesse in verschiedenen Workspaces verwenden über MutationOrchestrator(..., db_path=...) dieselbe reguläre absolute Custom-DB. tempfile.gettempdir() liefert tatsächlich verschiedene nutzbare Verzeichnisse; bloß unterschiedliche TMP/TEMP-Werte reichen bei gemeinsamer vorrangiger Einstellung oder gleichem Fallback nicht. Prozess B erwirbt getrennte DB-Locks, invalidiert den noch lebenden Run A und markiert ihn als aborted. Logisch überlappende Runs sind möglich; die einzelnen SQLite-Schreibtransaktionen bleiben serialisiert.

**Wörtlicher Beleg:**

```python
temp_root = Path(tempfile.gettempdir()).resolve(strict=True)
...
lock_root = temp_root / _DATABASE_LOCK_DIRNAME
...
paths = [lock_root / f"0-path-{path_digest}.run.lock"]
...
paths.append(lock_root / f"1-file-{identity_digest}.run.lock")
```

**Fixskizze.** DB-Sperrdomäne unabhängig von Prozess-Temp, z.B. benannte Windows-Kernelsperren für Pfad/Dateiidentität; verschiedene cwd/Temp mit gleicher DB abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Zwei Windows-Prozesse in verschiedenen Workspaces können dieselbe reguläre absolute Custom-DB über die Orchestrator-API verwenden und bei unterschiedlichen effektiven tempfile.gettempdir()-Ergebnissen getrennte DB-Locks erwerben. Erreicht der zweite Prozess die Recovery während des ersten laufenden Runs, kann er diesen fälschlich invalidieren und als aborted markieren. Unterschiedliche TMP/TEMP-Werte allein reichen nicht, falls beispielsweise ein gemeinsames vorrangiges TMPDIR oder bereits gecachte identische Temp-Pfade wirksam sind. Möglich sind logisch überlappende Writer; SQLite-Schreibtransaktionen bleiben serialisiert.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Zwei Prozesse in verschiedenen Workspaces können über MutationOrchestrator(..., db_path=<derselbe reguläre absolute DB-Pfad>) getrennte DB-Sperren erwerben, wenn tempfile.gettempdir() in beiden Prozessen unterschiedliche nutzbare Verzeichnisse liefert. Läuft der erste Run bereits, kann der zweite dessen DB-Status fälschlich auf aborted setzen. Unterschiedliche TMP/TEMP-Werte genügen nur, wenn keine gemeinsame höher priorisierte Temp-Einstellung oder ein Fallback beide Prozesse wieder auf dasselbe Verzeichnis führt. Gemeint sind überlappende logische Run-Writer, nicht gleichzeitig aktive SQLite-Schreibtransaktionen.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am bestätigten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stehen alle vier zitierten Anweisungen wörtlich in run_lock.py:717,721,756,767; sie bilden keinen zusammenhängenden Block. Beide DB-Sperrpfade hängen vollständig vom prozesslokal ermittelten tempfile.gettempdir() ab. Bei verschiedenen effektiven Temp-Wurzeln stimmen zwar die DB-Digests überein, die Guarddateien und Owner-Metadaten jedoch nicht. Die aktive PID-Prüfung in WorkspaceRunLock.acquire(), Zeilen 582–588, liest ausschließlich den jeweiligen lokalen Owner-Pfad und erkennt den Besitzer der anderen Temp-Wurzel daher nicht. Der Workspace-Lock wird seinerseits aus Path.cwd() abgeleitet (73–79). Ein gemeinsamer regulärer absoluter Custom-DB-Pfad ist über MutationOrchestrator(..., db_path=...) erreichbar (orchestrator.py:150–165); validate_cache_path prüft Dateityp, Links und Identität, verlangt aber keine Zugehörigkeit zum aktuellen Workspace (db.py:288–431). Nach Erwerb der getrennten Locks erreicht Prozess B _recover_abandoned_run (orchestrator.py:249–257,345). Diese Funktion prüft lediglich status == 'running', invalidiert Reuse-Fingerprints und beendet den gefundenen Run als 'aborted' (528–539), ohne dessen Prozessbesitzer zu prüfen. Gegenbeweise wurden geprüft: BEGIN IMMEDIATE und der eindeutige running-Index schützen einzelne Transaktionen beziehungsweise gleichzeitige running-Zeilen (db.py:211–217,581,881–884), verhindern aber diese irrtümliche Recovery nicht. SQLite serialisiert weiterhin Schreibtransaktionen; ein gleichzeitiger physischer SQLite-Schreibzugriff ist damit nicht belegt. Logisch überlappende Runs bleiben möglich. Die Tests test_absolute_database_uses_same_lock_domain_from_different_workspaces (test_run_lock.py:609–626) und test_live_database_holder_excludes_hardlink_alias_across_processes (test_run_lock_processes.py:131–157) verwenden dieselbe Temp-Domäne; der Kindprozess erbt die Umgebung. Sie widerlegen den Befund nicht und decken unterschiedliche effektive Temp-Wurzeln nicht ab. Keine Tests oder Prozessreproduktionen ausgeführt.

**Erreichbarkeit:** Am Zielcommit 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmen alle vier zitierten Codezeilen wörtlich; sie stehen in run_lock.py:717, 721, 756 und 767, also nicht zusammenhängend. Beide Datenbanksperren hängen vom durch tempfile.gettempdir() bestimmten Verzeichnis ab. Unterschiedliche tatsächlich ausgewählte Temp-Verzeichnisse ergeben trotz identischem Datenbankpfad und identischer Dateiidentität unterschiedliche Sperrdateien. Die Besitzerprüfung in WorkspaceRunLock.acquire(), Zeilen 582–588, liest ausschließlich die lokale Sperrdatei und entdeckt deshalb keinen Besitzer in der anderen Temp-Domäne. Der Workspace-Lock hängt seinerseits vom kanonischen cwd ab (Zeilen 71–79). Der reale Einstieg ist die öffentliche MutationOrchestrator-API mit db_path, orchestrator.py:150–165. validate_cache_path() prüft Datei- und Verzeichnissicherheit, bindet einen regulären absoluten Custom-DB-Pfad aber nicht an den aktuellen Workspace (db.py:419–445). Nach Erwerb beider Sperren erreicht run() die Recovery (orchestrator.py:250–257, 345). Diese liest den aktuellen running-Datensatz, entzieht dessen Cache-Wiederverwendung und setzt ihn ohne Prozessbesitzerprüfung auf aborted (528–539). Aktiv gesuchter Gegenbeweis: SQLite erzwingt nur einen running-Datensatz und serialisiert einzelne Schreibtransaktionen (db.py:211–219, 576–612, 882–884). Das verhindert diese Falsch-Recovery nicht, weil sie den vorhandenen Datensatz ausdrücklich beendet und damit den nächsten Run zulässt. save_results() ordnet Ergebnisse zudem der aktuell laufenden DB-Run-ID zu, ohne eine erwartete Aufrufer-Run-ID entgegenzunehmen (1604–1670); überlappende logische Writer sind somit möglich, auch wenn SQLite gleichzeitige Schreibtransaktionen serialisiert. Die Tests decken gemeinsame Temp-Domänen ab: test_run_lock.py:609 ändert nur cwd; test_run_lock_processes.py:131 startet den Kindprozess ohne abweichende Temp-Umgebung. test_run_surface_integration_220.py:245 prüft Recovery eines künstlich hinterlassenen Runs, und der Hardlink-Test ab Zeile 353 scheitert bereits an der Hardlink-Sicherheitsprüfung. Keiner dieser Tests widerlegt das Szenario einer regulären gemeinsamen DB bei unterschiedlichen Temp-Domänen. Keine Tests oder Prozessreproduktionen ausgeführt. high ist für den erreichbaren Verlust der gegenseitigen Run-Ausschließung und die falsche Beendigung eines lebenden Runs angemessen.

<a id="mod-spawn-spawn-01"></a>

#### SPAWN-01: Verspätetes TaskStarted eines erfassten toten Workers kann Pool dauerhaft blockieren

**high · race · Konfidenz hoch** — `mod:spawn` — [src/mutmut_win/process/executor.py:366](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/executor.py:366)

**Mechanismus.** Der Liveness-Sweep merkt eine tote PID dauerhaft, auch wenn deren TaskStarted noch nicht verarbeitet wurde. Ein später gelesenes Started wird trotzdem in in_flight aufgenommen. Weitere Sweeps überspringen die bereits behandelte PID; der verwaiste Eintrag verhindert zugleich den Idle-Watchdog, dessen Bedingung in_flight_tasks == 0 verlangt. Auf Windows ergänzt der Containment-Kanal keine Taskzuordnung.

**Fehlerszenario.** Queue.get meldet Empty; danach überträgt Worker A sein Started vollständig und stirbt hart, bevor der Elternprozess die Liveness prüft. Der erste Sweep erfolgt noch vor Ablauf der Idle-Grace und merkt A ohne Task. Der nächste Queue-Read verarbeitet das bereits übertragene Started; ein Completed folgt nicht mehr. Bleibt mindestens ein anderer Worker B dauerhaft lebendig und ohne weitere Ereignisse, etwa im Bootstrap, greifen weder All-dead-Abbruch noch Idle-Watchdog: get_events wartet unbegrenzt. Normale abgefangene Task-Exceptions oder ein später doch eintreffendes Completed genügen für dieses Szenario nicht.

**Wörtlicher Beleg:**

```python
            if worker.is_alive() or pid in handled_dead_pids:
                continue
            handled_dead_pids.add(pid)
```

**Fixskizze.** Bekannte tote PIDs nur für einmalige Prozessbereinigung überspringen; verspätete Starts weiterhin erkennen und synthetisch abschließen. Die Reihenfolge Empty, Todserfassung, Started und dauerhaft stiller lebender Peer deterministisch prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Ein bereits vollständig übertragenes, aber erst nach der Todeserfassung verarbeitetes TaskStarted kann einen dauerhaft verwaisten in_flight-Eintrag erzeugen. Ein unbegrenztes Warten folgt, wenn kein zugehöriges Completed mehr kommt, der erste Sweep vor Ablauf der Idle-Grace erfolgt und mindestens ein anderer Worker dauerhaft lebendig ohne weitere Ereignisse bleibt.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am geprüften HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat wörtlich: executor.py:366–368 enthält 'if worker.is_alive() or pid in handled_dead_pids:', 'continue' und 'handled_dead_pids.add(pid)'. Die PID wird auch ohne zugeordneten in_flight-Eintrag dauerhaft erfasst. Der entscheidende Gegenbeweis fehlt: Queue.get() mit Empty und die anschließende Liveness-Prüfung sind nicht atomar. Nach Empty kann Worker A sein Started vollständig übertragen und anschließend hart sterben, bevor der Elternprozess is_alive() prüft. Dafür muss nach dem Tod kein Feeder mehr laufen. Das bereits übertragene Started wird beim nächsten get() gelesen und in Zeile 344 ohne Prüfung gegen handled_dead_pids eingetragen. Bei weiteren Sweeps verhindert Zeile 366 dessen synthetischen Abschluss. Ein lebender, dauerhaft im Bootstrap hängender Worker B verhindert den All-dead-Abbruch in Zeile 292; der verwaiste Eintrag verhindert über Zeile 72 zugleich dauerhaft den Idle-Abbruch. Voraussetzung ist, dass der erste Sweep vor Ablauf der Startup-Grace erfolgt und kein späteres Completed für A existiert. Das ist bei hartem Prozessabbruch nach Started erreichbar; normale Exceptions werden dagegen in worker.py:974–997 abgefangen und sind kein ausreichendes Fehlerszenario. worker.py:1194–1197 bestätigt, dass Started vor dem workerseitigen wait(timeout) gesendet wird; mit dem Tod von A entfällt diese Timeout-Instanz. Der Windows-Startpfad wartet nicht auf abgeschlossenen Bootstrap (suspended_spawn.py:132–145). orchestrator.py:943–960 konsumiert den Generator ohne zusätzliche Frist; finally/shutdown greift erst bei Verlassen der Schleife. Vorhandene Tests widerlegen den Befund nicht: test_worker_liveness.py:62–82 verarbeitet Started vor dem ersten Sweep; Zeilen 84–119 prüfen ein verspätetes Completed, keinen verspäteten Start. test_pool_collapse_127.py:237–270 prüft den gemischten Pool erst nach vollständigem Started/Completed-Paar. Zeilen 272–304 und 307–327 bestätigen ausdrücklich die deaktivierte Idle-Grenze bei einem in_flight-Eintrag. Die entscheidende Reihenfolge Empty → Todserfassung ohne Task → verspätetes Started → dauerhaft lebender stiller Peer ist damit nicht abgedeckt. High ist für den möglichen unbegrenzten Stillstand des gesamten Mutationslaufs vertretbar; Critical wäre nicht belegt. Ausschließlich statische Prüfung, keine Tests oder Prozessreproduktionen ausgeführt.

**Erreichbarkeit:** Am bestätigten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat in executor.py:366–368 wörtlich. Der Ablauf ist erreichbar: Nach dem Timeout von Queue.get() kann der Elternprozess unterbrochen werden; A kann anschließend sein TaskStarted vollständig übertragen und vor dem Liveness-Sweep hart sterben. Das erfordert keine Nachrichtenübertragung nach dem Tod. Der Sweep speichert A auch bei leerem in_flight dauerhaft in handled_dead_pids. Der nächste Queue-Read nimmt das verspätet verarbeitete Started in executor.py:343–344 ohne Prüfung dieser Menge auf. Weitere Sweeps überspringen A; damit bleibt der Eintrag erhalten. Auf Windows bietet _drain_containment_events keine zusätzliche Absicherung, sondern kehrt in Zeile 399–400 unmittelbar zurück. Bleibt B lebendig und still, verhindert er den All-dead-Abbruch (292), während der verwaiste Eintrag den Idle-Watchdog deaktiviert (72, 310–314). Der Windows-Startpfad wartet ausdrücklich nicht auf abgeschlossenen Bootstrap: suspended_spawn.py:132–157 serialisiert vor ResumeThread und kehrt danach zurück. Ein hängender Bootstrap von B schließt den Zustand daher nicht aus. Worker-Recovery (worker.py:974–997) fängt gewöhnliche Exceptions ab, jedoch keinen harten Prozessabbruch; die Timeout-Überwachung läuft selbst in A (1194–1197). Der finally-Aufruf von shutdown im Orchestrator (944–960) wird erst beim Verlassen der Ereignisschleife erreicht. Gegenbelege gesucht: test_worker_liveness.py:62–119 deckt bereits verarbeitetes Started und verspätetes Completed ab; test_pool_collapse_127.py:237–270 deckt einen stillen Peer nach vollständigem Abschluss ab. Keiner dieser Tests bildet Empty → Tod erkannt → Started ohne Completed ab. Die Tests sind für ihre jeweiligen Fälle aussagekräftig, lassen aber diese Reihenfolge offen. Keine Tests oder Prozessreproduktionen ausgeführt; die Bestätigung beruht auf dem erreichbaren Kontrollfluss.

<a id="mod-spawn-spawn-02"></a>

#### SPAWN-02: Ausscheidende Kindprozesse können Timeouts fälschlich zu Infinite-Loop-Kills machen

**high · correctness · Konfidenz hoch** — `mod:spawn` — [src/mutmut_win/process/loop_monitor.py:491](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/loop_monitor.py:491)

**Mechanismus.** Jede Probe summiert absolute I/O-Zähler ausschließlich des Hauptprozesses und aktuell lebender Kinder. Diese Baumsumme kann beim Ende eines Kindes sinken. classify_samples verwendet lediglich den letzten minus den ersten messbaren Wert und begrenzt das Ergebnis nach unten auf null. Dadurch verliert bereits beobachteter I/O-Fortschritt seine Wirkung als Veto. Die gespeicherten Proben selbst bleiben erhalten; der CPU-Cache akkumuliert keine I/O-Deltas ausgeschiedener Kinder.

**Fehlerszenario.** Ein ausgabearmer Test hält durch seinen Elternprozess den mittleren CPU-Wert über 70 Prozent. Ein I/O-aktives Kind endet im Beobachtungsfenster; die sechs Baumsummen lauten beispielsweise 11000, 11500, 12000, 1300, 1600, 1800. Trotz beobachteter Fortschritte wird die Endpunktdifferenz auf null gesetzt. Überschreitet der Test sein Zeitbudget, beendet der Worker den Prozessbaum wie bei jedem Timeout und kann ihn danach unter Windows fälschlich als killed_by_infinite_loop klassifizieren. Dieser Status zählt als killed. Ein vorzeitiger zusätzlicher Prozessabbruch wird durch den Fehler nicht verursacht.

**Wörtlicher Beleg:**

```python
                for child in self._proc.children(recursive=True):
                    cpu += self._cached_cpu_percent(child)
                    child_io = self._io_ops(child)
                    if child_io is not None:
                        io_ops = child_io if io_ops is None else io_ops + child_io
```

**Fixskizze.** I/O-Deltas pro Prozessidentität akkumulieren und bereits gemessenen Fortschritt ausgeschiedener Kinder bewahren. Einen monotonen Baumzähler publizieren und die Klassifikation bei Kindprozesswechseln prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Endet innerhalb des ausgewerteten Beobachtungsfensters ein I/O-aktiver Kindprozess, kann sein wegfallender absoluter Zähler bereits beobachteten Fortschritt in der Endpunktdifferenz verdecken. Bei zusätzlich ausreichendem CPU-Mittelwert und geringem messbarem Output kann dadurch ein regulär erreichter Timeout fälschlich als killed_by_infinite_loop gewertet werden. Der Monitor beendet den Prozess nicht vorzeitig: Der Worker beendet den Prozessbaum erst beim ohnehin erreichten Timeout und klassifiziert anschließend falsch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Endet ein I/O-Kind während des ausgewerteten Beobachtungsfensters, können fallende Summen absoluter Prozesszähler bereits gemessenen Fortschritt im Endpunktvergleich verdecken. Überschreitet der weiterhin CPU-intensive, ausgabearme Test anschließend sein Zeitbudget, kann der vorhandene Timeout fälschlich als killed_by_infinite_loop gewertet und im Kill-Zähler berücksichtigt werden. Die gespeicherten Proben bleiben erhalten; verloren geht ihre Fortschrittswirkung in der Klassifikation.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am bestätigten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b (v2.21.4) stimmt das Zitat wörtlich mit src/mutmut_win/process/loop_monitor.py:491–495 überein. Jede Probe beginnt in Zeile 486 erneut mit dem absoluten I/O-Zähler des Hauptprozesses und addiert ausschließlich die aktuell gefundenen Kinder. Es gibt keine gespeicherten I/O-Deltas ausgeschiedener Prozesse; der Prozesscache dient nur der CPU-Messung. Zeile 287 berechnet tatsächlich max(0, letzter messbarer Wert minus erster messbarer Wert). Die angegebene Folge ergibt daher 0, obwohl mehrere beobachtete Anstiege jeweils die Fortschrittsschwelle 100 überschreiten. Die Suche nach Gegenbeweisen ergibt keine kompensierende Prüfung: Die Mindestzahl von fünf Proben wird erfüllt; ein dauerhaft CPU-intensiver Hauptprozess oder anderer stabiler Nachkomme kann trotz wechselnder I/O-Kinder den CPU-Mittelwert über 70 % halten. CPU-Priming neuer Kinder verhindert das Szenario deshalb nicht zwingend. Bei messbarem konstantem Output entfällt das I/O-Veto; unter Windows wird die Statusprüfung ausdrücklich deaktiviert (worker.py:1214). Die Konfidenzbegrenzung auf medium verhindert den IL-Status nicht. worker.py:1217–1220 übernimmt diesen als EXIT_CODE_INFINITE_LOOP; orchestrator.py:2197–2200 und stats.py:1902–1906 zählen ihn als killed. Die vorhandenen Tests in test_classifier_honesty.py prüfen monoton steigende, konstante und fehlende I/O-Werte, jedoch keinen Zählerrückgang durch Kindprozessende. test_loop_monitor.py und test_il_detection.py enthalten ebenfalls keinen solchen Fall. Es handelt sich um eine konkrete Abdeckungslücke, nicht um einen widerlegenden Test. Ausschließlich statisch geprüft; keine Tests oder Prozessreproduktionen ausgeführt.

**Erreichbarkeit:** Am Zielcommit 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat wörtlich mit src/mutmut_win/process/loop_monitor.py:491–495 überein. Jede Probe beginnt mit dem aktuellen absoluten Elternzähler (:486) und addiert die aktuell gefundenen Kinder. Eine Akkumulation ausgeschiedener Kinder existiert nicht; der Cache :499–503 betrifft lediglich Prozessinstanzen für CPU-Messungen. classify_samples berechnet tatsächlich ausschließlich max(0, letzter−erster) (:286–287). Für die angegebene Folge ergibt das 0 trotz zwischenzeitlich beobachteter Zuwächse über 100 Operationen. Damit entfällt das I/O-Veto (:303–312). Die sechs Proben erfüllen die Mindestzahl fünf. Ein normaler Test kann diesen Zustand mit einem weiterhin rechnenden Elternprozess und einem während des Beobachtungsfensters endenden I/O-Kind erreichen; CPU-Priming neuer Kinder verhindert ihn wegen der CPU-Arbeit des Elternprozesses nicht. Auf Windows deaktiviert der Aufrufer das Statuskriterium (worker.py:1214). Wesentliche Einschränkung: Der Klassifikator läuft ausschließlich nach einem bereits eingetretenen Timeout; worker.py:1197–1206 beendet den Prozessbaum vorher. Der Fehler verursacht daher keinen zusätzlichen vorzeitigen Prozessabbruch, sondern die falsche Umwertung eines Timeouts zum IL-Kill (:1217–1222). Die erwähnten Zeilen 2197–2200 stehen in orchestrator.py und zählen diesen Status tatsächlich als killed; stats.py:1902–1906 übernimmt ihn ebenfalls. Tests in test_classifier_honesty.py:140–185 prüfen nur monoton steigende, konstante oder fehlende I/O-Zähler und den Schwellenwert. Der Kindprozess-Test :197–215 fixiert I/O auf null. test_il_detection.py prüft einen dauerhaft rechnenden beziehungsweise schlafenden Prozess, keinen Kindprozesswechsel. Damit liefern die vorhandenen Tests keinen Gegenbeweis. Ausschließlich statisch geprüft; keine Tests oder Prozessreproduktionen ausgeführt.

<a id="lens-races-race-01"></a>

#### RACE-01: PPID-Bereinigung kann nach PID-Wiederverwendung fremde Prozesse beenden

**high · race · Konfidenz hoch** — `lens:races` — [src/mutmut_win/process/worker.py:1621](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:1621)

**Mechanismus.** Der globale Prozessgraph ordnet Nachkommen ausschließlich über numerische PPIDs zu. Er prüft weder Erstellungszeiten entlang der Elternkanten noch die Jobmitgliedschaft. _kill_proc_tree führt diesen Sweep auch nach dem Schließen eines vorhandenen Jobs aus; das Typechecker-Cleanup ergänzt seine normale children()-Abfrage um dieselben ungeprüften Treffer. Die Identitätssicherung von psutil schützt den erfassten Prozess selbst, nicht die irrtümlich angenommene Elternbeziehung.

**Fehlerszenario.** Ein fremder Prozess mit PID P startet C und endet. C lebt mit der gespeicherten PPID P weiter. Später erhält ein mutmut-pytest- oder Typechecker-Prozess dieselbe PID P. Bei einem Worker-Timeout beziehungsweise beim Typechecker-Cleanup auch nach regulärem Abschluss wird C als Nachkomme erfasst und bei ausreichenden Terminierungsrechten beendet. Der frühere Elternprozess kann bereits lange vor dem Start des mutmut-Kinds beendet worden sein; dessen Start teilt die alte PID erneut zu. Es ist keine weitere PID-Wiederverwendung während des Cleanupfensters erforderlich. Der normale erfolgreiche Windows-Workerabschluss mit vorhandenem Job führt diesen Sweep dagegen nicht aus. Tatsächlich eingetretener Datenverlust und eine Ursache der gemeldeten Worker-Waisen sind nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
    children_by_ppid: dict[int, list[Any]] = {}
    for proc in psutil.process_iter(["pid", "ppid"]):
        with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            children_by_ppid.setdefault(proc.info["ppid"], []).append(proc)

    descendants: list[Any] = []
    pending = [root_pid]
    seen: set[int] = set()
    while pending:
        current = pending.pop()
        for child in children_by_ppid.get(current, []):
            if child.pid in seen:
                continue
            seen.add(child.pid)
            descendants.append(child)
            pending.append(child.pid)
```

**Fixskizze.** Bei erfolgreicher Job-Zuordnung die Terminierung auf nachgewiesene Jobmitglieder begrenzen. Fallback-Terminierungen nur anhand belegter Prozessidentitäten und überprüfter Elternkanten autorisieren; numerische PPIDs allein reichen nicht.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Unter Windows kann ein globaler PPID-Sweep fremde, noch lebende Prozesse mit einer inzwischen wiederverwendeten Eltern-PID als Nachkommen erfassen und bei ausreichenden Terminierungsrechten beenden. Betroffen sind insbesondere Worker-Timeouts und das Typechecker-Cleanup auch nach regulärem Abschluss; der normale erfolgreiche Windows-Worker-Abschluss verwendet dagegen ausschließlich Job-Cleanup.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Unter Windows kann die globale PPID-Bereinigung bei Worker-/Runner-Timeouts beziehungsweise Abbrüchen und beim Typechecker auch nach erfolgreichem Abschluss fremde, bereits vorhandene Waisen beenden, wenn deren gespeicherte Eltern-PID inzwischen dem mutmut-Kind zugeteilt wurde. Erfolgreiche Windows-Workerabschlüsse mit vorhandenem Job führen diesen Scan nicht aus.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am bestätigten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b entspricht das Zitat wörtlich worker.py:1621–1636. Die Zuordnung verwendet ausschließlich numerische PPIDs; weder Eltern-Erstellungszeiten noch Jobmitgliedschaft werden geprüft. Der aktive Gegenbeweis reicht nicht aus: _kill_proc_tree schließt zwar zuerst einen vorhandenen Job (1664–1668), führt anschließend aber dennoch den globalen Sweep und child.kill() aus (1684–1690). Die Schutzprüfung für Popen-Testdoubles (1657–1662) greift bei AtomicJobPopen nicht, denn diese Klasse erbt von subprocess.Popen (atomic_spawn.py:281). Ein normaler Worker-Abschluss verwendet tatsächlich nur Job-Cleanup (worker.py:1240–1247); der behauptete gefährliche Pfad ist jedoch bei Worker-Timeouts erreichbar (1198–1201). Beim Typechecker ergänzt _snapshot_process_tree sogar nach root.children(recursive=True) ungeprüfte globale PPID-Treffer (type_checking.py:133–168); _terminate_type_checker_tree beendet diese trotz vorhandenem Job (187–208) und wird sowohl bei Fehlern als auch nach regulärem Abschluss aufgerufen (318–330). Die Identitätssicherung eines psutil.Process kann die falsche Elternzuordnung nicht korrigieren: Der erfasste Fremdprozess C ist selbst unverändert vorhanden. Ein bereits verwaister Prozess mit inzwischen wiederverwendeter Eltern-PID genügt; eine Wiederverwendung während des Cleanupfensters ist nicht erforderlich. Die untersuchten Tests liefern keinen Gegenbeweis: tests/integration/test_kill_proc_tree.py:66–118 prüft echte Nachkommen, tests/unit/test_process_worker.py:121–134 ausschließlich Testdouble-PIDs; tests/unit/test_type_checking.py:488–516 mockt den Snapshot und prüft den Kill-Fallback. Ein Regressionstest mit einem fremden, älteren Prozess und passender verwaister PPID wurde nicht gefunden. Ausschließlich statisch geprüft; keine Tests oder Prozessreproduktionen ausgeführt. High ist für mögliches Beenden fremder Prozesse angemessen, Critical wäre durch diese Evidenz nicht begründet.

**Erreichbarkeit:** Der Zielcommit ist 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b. Das Codezitat stimmt wörtlich mit worker.py:1621–1636 überein. Der Scan verknüpft ausschließlich numerische PPIDs; weder Eltern-Erstellungszeiten noch Jobmitgliedschaft werden geprüft. _kill_proc_tree schließt zwar in 1664–1668 den Job, führt anschließend aber unabhängig davon in 1684–1690 den Scan und child.kill() aus. AtomicJobPopen erbt tatsächlich von subprocess.Popen (atomic_spawn.py:281), sodass die Schutzprüfung gegen Testdoubles in worker.py:1657 diesen Produktionspfad nicht ausschließt. psutil ist reguläre Abhängigkeit (pyproject.toml:34). Erreichbarer Aufruf ist insbesondere der normale Mutationstimeout (worker.py:1197–1201). Als Gegenbeweis geprüft: Beim erfolgreichen Windows-Workerabschluss wird lediglich der Job geschlossen (1240–1247); dieser konkrete Pfad führt keinen PPID-Scan aus. Beim Typechecker erfolgt der fehleranfällige globale Scan hingegen zusätzlich zur children()-Abfrage (type_checking.py:133–168), und jedes gefundene Mitglied wird trotz vorhandenen Jobs beendet (187–208); dies geschieht auch nach erfolgreichem Abschluss (325–330). Das Szenario benötigt keine Wiederverwendung der aktuellen mutmut-PID während des Cleanups: Ein noch lebender fremder Prozess C kann die gespeicherte PPID eines bereits vor dem mutmut-Kind verstorbenen Prozesses tragen. Erhält das spätere mutmut-Kind diese PID, wird C unmittelbar falsch zugeordnet. Ein offenes Handle auf das aktuelle mutmut-Kind verhindert diese frühere Wiederverwendung nicht. C selbst muss seine PID überhaupt nicht gewechselt haben; seine eigene psutil-Prozessidentität kann deshalb vollkommen gültig sein. Voraussetzung für die tatsächliche Beendigung sind ausreichende Prozessrechte. Der historische Kommentar worker.py:1611–1617 bestätigt die Windows-PPID-Eigenschaft, beschränkt die Gefahr jedoch unzutreffend auf ein kurzes Recyclingfenster. Die vorhandenen Tests prüfen echte eigene Nachkommen (tests/integration/test_kill_proc_tree.py:66–113; test_success_process_tree_cleanup.py:64–84), synthetische PIDs (tests/unit/test_process_worker.py:121–134) oder mocken die Erfassung (test_type_checking.py:488–515). Sie prüfen keine bereits vorhandenen fremden Waisen mit wiederverwendeter Eltern-PID. Keine Tests oder Prozessreproduktionen ausgeführt. High ist für die mögliche Beendigung fremder Prozesse angemessen; ein tatsächlich eingetretener Datenverlust ist nicht nachgewiesen.

<a id="nondet-process-lifecycle-proc-01"></a>

#### PROC-01: Fehler beim Lesen des pytest-Nachweises überspringt die Prozessbereinigung

**medium · error-handling · Konfidenz hoch** — `nondet:process-lifecycle` — [src/mutmut_win/process/worker.py:1233](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:1233)

**Mechanismus.** Der finally-Block liest zuerst den veränderlichen Phase-Nachweis und schließt erst danach den Task-Job. consume_pytest_phase_guard fängt OSError, aber keinen UnicodeDecodeError. Dieser überspringt close_job, monitor.shutdown und capture.close. worker_main behandelt ihn als nichtfatalen Taskfehler und arbeitet weiter; der ganzzahlige Jobhandle bleibt im lebenden Worker offen.

**Fehlerszenario.** Ein pytest-Hook oder getesteter Code hinterlässt nach dem letzten Call-Report ungültige UTF-8-Bytes in der über die Umgebung bekannten Sentinel-Datei und einen Hintergrundprozess. pytest endet regulär ohne Timeout. Der Worker meldet Recovery und arbeitet weiter, während der Nachkomme bis Worker-/Poolende weiterlebt. Dies erklärt kein Überleben nach nachgewiesenem Tod des Hauptprozesses, da dessen äußerer Pool-Job weiterhin schützt.

**Wörtlicher Beleg:**

```text
worker.py:1232–1233:
finally:
        phase_executed = consume_pytest_phase_guard(phase_marker_path, phase_marker_token)
worker.py:866–868:
return marker_path.read_text(encoding="utf-8") == expected_token
    except OSError:
        return False
worker.py:974: except Exception as exc:
worker.py:988: fatal = isinstance(exc, (ProcessContainmentError, PytestBoundaryError))
```

**Fixskizze.** Cleanup in einem äußeren finally unabhängig von Nachweisauswertung garantieren; ungültige Kodierung als ungültigen Nachweis behandeln. Regression mit beschädigtem Sentinel und lebendem Nachkommen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-process-lifecycle-proc-02"></a>

#### PROC-02: Popen-Wrapper aktiviert den nichtatomaren Kompatibilitätspfad für echte Prozesse

**medium · race · Konfidenz hoch** — `nondet:process-lifecycle` — [src/mutmut_win/process/worker.py:1555](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:1555)

**Mechanismus.** Ein Identitätsvergleich der globalen subprocess.Popen-Referenz wählt atomare Erzeugung oder nachträgliche Job-Zuweisung. Ein nach Modulimport installierter transparenter Wrapper wird wie ein Testdouble behandelt und erzeugt echte Prozesse im CreateProcess→Assign-Fenster. type_checking.py verwendet dieselbe Unterscheidung.

**Fehlerszenario.** Ein einbettender Host installiert nach Import im tatsächlich startenden Prozess einen transparenten Popen-Wrapper. Bei einer direkt vom Hauptprozess gestarteten Collection-/pytest-Phase stirbt der Hauptprozess nach Popen-Rückkehr und vor _create_task_job. Der suspendierte Prozess ist noch keinem mutmut-Job zugeordnet und kann ohne externen Job zurückbleiben. Das zusätzliche Worker-Szenario setzt einen auch im Worker installierten Wrapper voraus; eine alleinige Änderung im Hauptprozess wird durch Windows-spawn nicht übernommen. Im Workerpool schützt der äußere Job weiterhin gegen Hauptprozessende; bei Worker-Ende kann der Taskprozess bis Poolende bestehen. Der unveränderte CLI-Lauf verwendet den atomaren Pfad.

**Wörtlicher Beleg:**

```text
worker.py:60: _REAL_POPEN_TYPE = subprocess.Popen
worker.py:1555–1557:
if subprocess.Popen is not _REAL_POPEN_TYPE:
        proc = subprocess.Popen(cmd, **kwargs)  # noqa: S603
        job_handle = _create_task_job(proc.pid)
worker.py:1559: _resume_after_containment(proc, job_handle)
type_checking.py:262: atomic_windows_launch = sys.platform == "win32" and subprocess.Popen is _REAL_POPEN_TYPE
```

**Fixskizze.** Produktionsstarts immer atomar ausführen; Testdoubles über explizit injizierte interne Startfunktion einbinden oder unbekannte Startimplementierungen geschlossen ablehnen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Der Fehler setzt einen nach Import des betreffenden Moduls installierten Popen-Wrapper voraus, der echte Prozesse erzeugt. Ohne solchen Austausch bleibt der atomare Produktionspfad aktiv. Für das zusätzliche Worker-Szenario muss der Wrapper auch im jeweiligen Worker installiert sein; eine alleinige Änderung im Hauptprozess wird durch Windows-spawn nicht automatisch übernommen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Die Lücke setzt eine nach Import im tatsächlich startenden Prozess ausgetauschte subprocess.Popen-Referenz voraus. Der unveränderte CLI-Lauf benutzt den atomaren Pfad. Ein ausschließlich im Hauptprozess installierter Wrapper wird unter Windows-spawn nicht automatisch in Worker übernommen; die Aussage zum Worker-Ende gilt nur, wenn auch dort der Wrapper aktiv ist.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-timing-assumptions-time-02"></a>

#### TIME-02: Abgelaufenes Drain-Thread-Join wird ungeprüft als vollständige Ausgabe behandelt

**medium · race · Konfidenz mittel** — `nondet:timing-assumptions` — [src/mutmut_win/process/output_capture.py:89](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/output_capture.py:89)

**Mechanismus.** close wartet höchstens eine Sekunde auf den Reader, prüft dessen Ende nicht und setzt immer _closed=True. Aufrufer werten unmittelbar danach womöglich unvollständige Ausgabe aus. Spätere close-Aufrufe warten nicht nach. Entscheidend ist, dass der Reader auch bis zur tatsächlichen Momentaufnahme noch zurückliegt; der Join-Timeout allein beweist keinen Ausgabeverlust. Späteres Drain korrigiert bereits gespeicherte Texte nicht.

**Fehlerszenario.** Child schreibt kleine Schlussausgabe und endet, Drain-Thread bleibt unter Last länger als eine Sekunde zurück. runner.py:412–426 erhält unvollständigen Tail, Forced-Fail-Marker fehlt bei :647–649, Orchestrator bricht ab. type_checking.py:332–342 kann ebenfalls leere Ausgabe als leere Mypy-Befundliste parsen. Bestehender Test deckt Empty-read/Stop-Race ab, nicht abgelaufenes Join.

**Wörtlicher Beleg:**

```python
    def close(self, timeout: float = 1.0) -> None:
        """Stop after draining currently available data; never wait unboundedly."""
        if self._closed:
            return
        self.close_writer()
        self._stop.set()
        self._reader.join(max(0.0, timeout))
        self._closed = True
```

**Fixskizze.** Reader-Abschluss explizit feststellen; unvollständige Ausgabe als Zustand/Fehler propagieren oder nach beendetem Baum synchronisiert final drainen. Angehaltenen Reader deterministisch prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Wenn der Reader über das Join-Zeitlimit hinaus und bis zur anschließenden Momentaufnahme zurückbleibt, können Aufrufer unvollständige Ausgabe als endgültig auswerten. Der Reader kann später noch weiterarbeiten; bereits gespeicherte Diagnosetexte beziehungsweise CompletedProcess-Ausgaben werden dadurch nicht korrigiert. Das ist ein bedingter Ablauf, kein zwangsläufiger Fehler bei jedem close().
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: medium. Bei einer Reader-Verzögerung über das einsekündige Join-Zeitfenster hinaus kann bereits geschriebene Schlussausgabe in der anschließenden Momentaufnahme fehlen. Der Fehler tritt nur auf, wenn der Reader die betreffenden Bytes auch bis zur tatsächlichen Auswertung noch nicht eingetragen hat; ein Join-Timeout allein bedeutet nicht zwangsläufig Ausgabeverlust. Die reale Häufigkeit unter Windows und CPython 3.14.7 ist nicht belegt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-worker-work-02"></a>

#### WORK-02: Ungültiger UTF-8-Proof überspringt Job- und Monitor-Bereinigung

**medium · resource-leak · Konfidenz hoch** — `mod:worker` — [src/mutmut_win/process/worker.py:1233](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:1233)

**Mechanismus.** Das strikte UTF-8-Lesen fängt nur OSError. Das eigene finally des Lesehelpers löscht lediglich die Markerdatei; es unterdrückt keinen UnicodeDecodeError. Der Fehler aus der ersten Worker-finally-Operation überspringt deshalb Jobclose, Baumcleanup, Monitor-Shutdown und Capture-Close. worker_main meldet suspicious mit fatal=False und kann weiterarbeiten.

**Fehlerszenario.** Ein Fixture-Finalizer überschreibt nach der einmaligen Proof-Publikation den über die Umgebung bekannten Marker mit b'\xff', gegebenenfalls nur für Mutationstasks, und hinterlässt einen Hintergrundprozess. Bei regulärem Ende ohne Timeout scheitert die Decodierung; Task-Jobhandle, Nachfahren und laufender Monitor können bis Workerende beziehungsweise Pool-Shutdown bestehen bleiben. Capture bleibt insbesondere aktiv, wenn ein Nachfahre den Pipe-Writer offen hält. Auf dem Timeoutpfad wurde der Prozessbaum bereits vor dem fehlerhaften Lesen bereinigt.

**Wörtlicher Beleg:**

```python
    try:
        return marker_path.read_text(encoding="utf-8") == expected_token
    except OSError:
        return False
...
    finally:
        phase_executed = consume_pytest_phase_guard(phase_marker_path, phase_marker_token)
        if exit_code == 0 and not phase_executed:
            exit_code = 35
```

**Fixskizze.** Cleanup durch äußerstes finally garantieren; begrenzte Bytefolge vergleichen oder Decodierungsfehler behandeln; beschädigten Proof mit Cleanup-Assertions testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein nach Veröffentlichung mit ungültigem UTF-8 überschriebener Proof lässt beim regulären Prozessabschluss die verbleibende Worker-Bereinigung ausfallen. Taskjob und gegebenenfalls Hintergrundprozesse sowie gestartete Monitor-/Capture-Ressourcen bleiben bis zu ihrer späteren Beendigung bestehen, während der Worker mit suspicious zur nächsten Aufgabe übergeht. Auf dem Timeoutpfad ist der Prozessbaum bereits bereinigt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein nach Veröffentlichung mit ungültigem UTF-8 überschriebener Proof überspringt bei einem ohne Timeout beendeten Worker-Testprozess die verbleibende Task-Bereinigung. Task-Jobhandle, vorhandene Nachfahren und ein laufender Monitor können bis Workerende beziehungsweise Pool-Shutdown bestehen bleiben; Capture bleibt insbesondere bei weiterhin offenem geerbtem Pipe-Writer aktiv. Der Worker meldet suspicious und kann weitere Tasks bearbeiten.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-locking-lock-02"></a>

#### LOCK-02: Synchrones Pickling im Hauptprozess umgeht Generation-Timeout

**medium · api-contract · Konfidenz hoch** — `mod:locking` — [src/mutmut_win/process/generation_supervisor.py:652](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/generation_supervisor.py:652)

**Mechanismus.** Die Deadline wird nur im aufrufenden Thread ausgewertet. Nach dem READY-Handshake serialisiert Connection.send Argumente und Worker synchron; ein langsames __reduce__/__getstate__ verhindert währenddessen sowohl die Deadlineprüfung als auch das Cleanup. Auch die Ergebnisrekonstruktion in recv läuft synchron im Wächter. Der generische API-Vertrag verlangt picklbare Argumente, begrenzt deren Serialisierungsdauer jedoch nicht.

**Fehlerszenario.** Ein direkter API-Aufrufer übergibt ein gültiges Argument, dessen __reduce__ erst nach 60 Sekunden beispielsweise (int, (1,)) zurückgibt. Gelingt der vorherige Handshake innerhalb des konfigurierten Drei-Sekunden-Budgets, blockiert der Elternprozess anschließend trotzdem mindestens 60 Sekunden im send-Aufruf. Langsame Rekonstruktion wirkt entsprechend, wenn sie den Elternprozess erreicht; eine bereits im Supervisor blockierende Rekonstruktion kann dagegen überwacht werden. Ein solcher CLI-Auslöser ist für die überwiegend einfachen Orchestrator-Argumente nicht belegt.

**Wörtlicher Beleg:**

```python
parent_connection.send((_START, arguments, worker))

while True:
    message = _wait_for_wire_event(
        _as_connection(parent_connection),
        process,
        deadline=progress_deadline,
    )
```

**Fixskizze.** Freie Serialisierung und Rekonstruktion aus dem Deadlinewächter auslagern oder zulässige Wiretypen begrenzen. Initiale Serialisierung, Übertragung und Rekonstruktion getrennt budgetieren; der vorhandene PPE-Test deckt nur spätere Serialisierung im Supervisor ab.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Synchrone Serialisierung im aufrufenden Prozess kann den Generation-Timeout und dessen Cleanup beliebig verzögern; bei dauerhaft blockierendem Pickling bleiben beide aus. Synchrone Ergebnisrekonstruktion in recv besitzt dieselbe Überwachungslücke.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Die öffentliche generische Supervisor-API kann ihr No-Progress-Zeitbudget bei langsamer initialer Argumentserialisierung im aufrufenden Prozess überschreiten. Langsame Ergebnisrekonstruktion kann denselben Effekt verursachen, sofern sie den Elternprozess erreicht; eine bereits im Supervisor blockierende Rekonstruktion kann dagegen vom Elternprozess abgebrochen werden.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-locking-lock-03"></a>

#### LOCK-03: Fehler nach Owner-Publikation vergiftet weitere Lock-Erwerbe

**medium · error-handling · Konfidenz hoch** — `mod:locking` — [src/mutmut_win/process/run_lock.py:591](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/run_lock.py:591)

**Mechanismus.** _write_owner kann den acquired-Record bereits atomar veröffentlichen und bei einer anschließenden Leaf- oder Parent-Prüfung scheitern. _guard_fd und _owner werden erst nach seiner erfolgreichen Rückkehr gesetzt. Der Fehlerpfad entriegelt und schließt den Guard, lässt aber den eigenen acquired-Record bestehen. release bleibt mangels _guard_fd wirkungslos; ein erneuter Erwerb erkennt den darin genannten eigenen Prozess als lebend.

**Fehlerszenario.** Nach erfolgreichem Owner-Replace schlägt unter Windows eine spätere lstat- oder Parent-Prüfung transient fehl. Ein langlebiger API-Host fängt den Fehler und versucht den Erwerb erneut: Obwohl kein Run läuft und der Betriebssystem-Guard frei ist, bleibt dieser Lock-Bereich bis zum Hostende oder einer anderen Bereinigung des Records blockiert. Ein gewöhnlicher CLI-Aufruf, dessen Prozess nach dem Fehler endet, verursacht diese dauerhafte Selbstblockade nicht.

**Wörtlicher Beleg:**

```python
owner = _current_owner()
owner_identity = _write_owner(self.path, owner)
self._guard_fd = fd
self._owner = owner
self._owner_identity = owner_identity
return self
except BaseException:
    if guard_locked and fd >= 0:
        with contextlib.suppress(OSError):
            _unlock_guard(fd)
    if fd >= 0:
        os.close(fd)
    raise
```

**Fixskizze.** Einen möglicherweise bereits veröffentlichten eigenen Token im Fehlerpfad berücksichtigen. Unter gehaltenem Guard ausschließlich nachweislich eigene Ownerdaten zurückrollen oder einen überprüfbaren Erwerbsrest für sicheres Cleanup bewahren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Wenn nach erfolgreicher Veröffentlichung des eigenen acquired-Records eine Nachprüfung fehlschlägt und der aufrufende Prozess weiterlebt, bleibt der Lock-Bereich trotz freiem Betriebssystem-Guard für weitere Erwerbe gesperrt, bis der Owner-Prozess endet oder der Record anderweitig bereinigt wird. Ein gewöhnlicher CLI-Aufruf, dessen Prozess nach dem Fehler endet, verursacht diese dauerhafte Selbstblockade nicht.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-spawn-spawn-03"></a>

#### SPAWN-03: Fehlgeschlagene Capture-Initialisierung verliert beide Pipe-Deskriptoren

**medium · resource-leak · Konfidenz hoch** — `mod:spawn` — [src/mutmut_win/process/output_capture.py:35](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/output_capture.py:35)

**Mechanismus.** Nach erfolgreichem os.pipe() fehlt ein Rollback für die folgenden Initialisierungsschritte. Scheitern set_blocking oder Thread.start vor dem tatsächlichen Readerstart, läuft dessen finally nicht. Der Konstruktor liefert kein Objekt zurück, dessen close der Aufrufer erreichen könnte; die beiden als Ganzzahlen gespeicherten Deskriptoren besitzen keinen automatischen Finalizer.

**Fehlerszenario.** Unter Ressourcenknappheit scheitert Thread.start mit RuntimeError, nachdem beide Pipe-Deskriptoren erzeugt wurden. Sie bleiben bis zum Worker-Prozessende offen. Gelingt die nichtfatale Fehlerberichterstattung weiterhin, etwa mit einem bereits laufenden Queue-Feeder nach früheren Aufgaben, kann derselbe Worker weitere Mutanten versuchen und pro erneutem Konstruktorfehler zwei zusätzliche Deskriptoren verlieren. Diese Fortsetzung ist unter Ressourcenknappheit möglich, aber nicht garantiert.

**Wörtlicher Beleg:**

```python
        self._read_fd, self._write_fd = os.pipe()
        os.set_blocking(self._read_fd, False)
```

**Fixskizze.** Ab os.pipe eine Ausnahmebereinigung einrichten und beide Deskriptoren bis zur erfolgreichen Eigentumsübergabe zuverlässig schließen. Fehler bei set_blocking und vor dem tatsächlichen Threadstart gezielt prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Nach erfolgreichem os.pipe() verliert eine Capture-Konstruktion, die vor dem tatsächlichen Readerstart scheitert, beide Deskriptoren bis zum Prozessende. Ein Worker kann nach erfolgreicher nichtfataler Fehlerberichterstattung weitere Aufgaben bearbeiten und dabei zusätzliche Deskriptoren verlieren.
- Erreichbarkeit: angenommen, Konfidenz hoch. Scheitert nach erfolgreichem os.pipe() die Capture-Initialisierung vor dem tatsächlichen Readerstart, bleiben beide Pipe-Deskriptoren bis zum Prozessende offen. Bei Threadstartfehlern kann derselbe Worker weitere Mutanten versuchen und weitere Deskriptoren verlieren, sofern Ereignisübermittlung und übrige Vorbereitung weiterhin gelingen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-atomic-atom-01"></a>

#### ATOM-01: Doppeltes Schließen kann wiederverwendeten Dateideskriptor schließen

**medium · race · Konfidenz hoch** — `mod:atomic` — [src/mutmut_win/atomic_file.py:222](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:222)

**Mechanismus.** Bei fehlgeschlagener Siblingvalidierung schließt Zeile 204 den Deskriptor, ohne den gespeicherten Besitz aufzuheben. Bei ausgeschöpften Versuchen führen Diagnose und UnsafeAtomicWriteError in den äußeren Handler, der dieselbe Nummer in Zeile 222 erneut schließt. suppress(OSError) schützt nur einen weiterhin ungültigen Deskriptor; bei zwischenzeitlicher Wiedervergabe kann der zweite Close erfolgreich sein.

**Fehlerszenario.** Die Validierung erschöpft ihre Versuche. Nach dem ersten Close öffnet ein anderer Thread desselben Prozesses eine Datei und erhält dieselbe Deskriptornummer. Der zweite Close schließt diese fremde Datei; deren weitere Nutzung kann fehlschlagen. Ein solcher Hintergrundthread kann beispielsweise aus einer Session-Fixture stammen, während der pytest-Guard den atomaren Schreiber verwendet. Ohne Wiedervergabe bleibt der zweite Close folgenlos; der normale continue-Retry erreicht ihn nicht. Die Häufigkeit des erforderlichen Interleavings wurde nicht gemessen.

**Wörtlicher Beleg:**

```python
        except BaseException:
            # The validation-failure path already closed and unlinked its own
            # fd before deciding to retry or fail; suppressing the second
            # close keeps every exit route uniform.
            with contextlib.suppress(OSError):
                os.close(fd)
```

**Fixskizze.** Den Besitz unmittelbar nach jedem Close aufheben, beispielsweise durch fd=None, und die gemeinsame Ausnahmebereinigung nur für weiterhin besessene Deskriptoren ausführen. Wiedervergabe zwischen den beiden bisherigen Close-Stellen gezielt prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei Erschöpfung der Siblingvalidierung wird dieselbe Deskriptornummer zweimal geschlossen. Wird sie zwischenzeitlich innerhalb desselben Prozesses neu vergeben, kann der zweite Close einen fremden offenen Deskriptor schließen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei ausgeschöpfter Siblingvalidierung wird ein bereits geschlossener Deskriptor erneut geschlossen. Erhält ein anderer Thread desselben Prozesses zwischenzeitlich dieselbe Nummer, kann dessen Datei geschlossen werden. Ohne diese Wiedervergabe bleibt der zweite Close durch suppress(OSError) folgenlos.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-atomic-atom-02"></a>

#### ATOM-02: Fehlerdiagnostik folgt vorbereiteten Links auf andere Dateien

**medium · correctness · Konfidenz mittel** — `mod:atomic` — [src/mutmut_win/atomic_file.py:155](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:155)

**Mechanismus.** Die Diagnose verwendet einen festen Dateinamen im effektiven Temp-Verzeichnis und öffnet ihn direkt zum Anhängen. Die Link-, Identitäts- und Parent-Prüfungen des eigentlichen Atomic-Writers gelten für diesen separaten Pfad nicht. Ein vorhandener Hardlink oder verfolgter Symlink kann deshalb Schreibzugriffe auf seinen beschreibbaren Referenten lenken. Das anschließend ausgelöste UnsafeAtomicWriteError macht bereits angehängte Bytes nicht rückgängig.

**Fehlerszenario.** mutmut-sibling-diag.jsonl ist im verwendeten Temp-Verzeichnis bereits ein Hard- oder Symlink auf eine andere beschreibbare Datei. Erst wenn zusätzlich fünf Validierungen frisch angelegter Siblings scheitern, hängt die Diagnose JSON an deren Referenten an und kann dessen Inhalt beschädigen. Ein gewöhnlicher Open- oder Replace-Fehler genügt nicht. Vorhandene Regressionstests erreichen den Diagnosepfad deterministisch und prüfen die Ausgabe nicht; eine verlässliche Produktionsauslösung oder Privilegienüberschreitung ist nicht belegt.

**Wörtlicher Beleg:**

```python
        target = Path(_tempfile.gettempdir()) / "mutmut-sibling-diag.jsonl"
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
```

**Fixskizze.** Eine zufällige, exklusiv angelegte Diagnosedatei in einem geprüften Verzeichnis oder einen bereits sicher geöffneten Kanal verwenden. Die Diagnose darf dabei nicht rekursiv vom gerade fehlgeschlagenen Atomic-Writer abhängen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Wenn fünf Sibling-Validierungen scheitern und im verwendeten Temp-Verzeichnis bereits ein Hard-/Symlink namens mutmut-sibling-diag.jsonl auf eine für den Prozess beschreibbare Datei liegt, hängt der Diagnosepfad JSON an diese Datei an. Das kann deren Inhalt beschädigen. Der Befund setzt sowohl den vorbereiteten Link als auch die gesonderte Validierungserschöpfung voraus; eine Privilegienüberschreitung oder regelmäßige Auslösung im Normalbetrieb ist nicht belegt.
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: medium. Bei erschöpfter Siblingvalidierung hängt die Fehlerdiagnostik ungeprüft JSON an eine vorab verlinkte mutmut-sibling-diag.jsonl im effektiven Tempverzeichnis an und verändert dadurch deren beschreibbaren Referenten. Vorhandene Regressionstests erreichen diesen Fehlerpfad deterministisch; die entsprechende Auslösung außerhalb der Tests ist nicht nachgewiesen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-atomic-atom-04"></a>

#### ATOM-04: Gültige lange Dateinamen werden durch Siblingnamen unveröffentlichbar

**medium · windows · Konfidenz hoch** — `mod:atomic` — [src/mutmut_win/atomic_file.py:172](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:172)

**Mechanismus.** Der temporäre Geschwistername enthält den vollständigen Zieldateinamen und weitere 52 Zeichen einschließlich des 32-stelligen Zufallstokens. Ein auf NTFS zulässiger ASCII-Dateiname ab 204 Zeichen erzeugt damit eine Komponente über der Grenze von 255 Zeichen. Die Prüfungen auf sichere Eltern und reguläre Dateien kürzen diesen Namen nicht.

**Fehlerszenario.** Eine gewöhnliche, nicht ignorierte Projektdatei besitzt einen 220 Zeichen langen ASCII-Dateinamen. Beim erstmaligen Staging oder einer nötigen Aktualisierung wird ein 272 Zeichen langer temporärer Name erzeugt; dessen Anlage scheitert und der Lauf bricht ab. Die atomare Funktion selbst wiederholt diesen Längenfehler nicht, der übergeordnete Kopierer versucht jedoch erneut gleich lange Namen. Bereits unveränderte Staging-Dateien beziehungsweise identische ensure_atomic_bytes-Ziele können die Veröffentlichung umgehen. Datenverlust ist daraus nicht belegt.

**Wörtlicher Beleg:**

```python
        temp_path = path.with_name(f".{path.name}.mutmut-atomic-{token}.tmp")
```

**Fixskizze.** Einen konstant kurzen Präfix mit Zufallstoken oder einen ausreichend gekürzten beziehungsweise gehashten Zielnamen für Siblings verwenden. Exklusive Anlage mit O_EXCL und die übrigen Eigentumsprüfungen bewahren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei notwendiger atomarer Veröffentlichung auf NTFS scheitern gültige ASCII-Zieldateinamen ab 204 Zeichen, weil der temporäre Geschwistername den vollständigen Namen um 52 Zeichen verlängert. Das betrifft insbesondere das erstmalige Staging entsprechender Projektdateien. Kopierwiederholungen beheben den Fehler nicht; unveränderte, bereits vorhandene Dateien können die Veröffentlichung umgehen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Beim erstmaligen Staging oder notwendigen Aktualisieren einer Datei mit einem ASCII-Dateinamen von 204 bis 255 Zeichen kann die atomare Veröffentlichung auf NTFS nicht erfolgen, weil der temporäre Geschwistername weitere 52 Zeichen benötigt. Ein 220 Zeichen langer Zielname erzeugt einen unzulässigen temporären Namen mit 272 Zeichen. Die Wiederholungen des Staging-Kopierers ändern diese Länge nicht.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-races-race-02"></a>

#### RACE-02: Regulärer Workerabschluss kann als Absturz gewertet werden

**medium · race · Konfidenz hoch** — `lens:races` — [src/mutmut_win/process/executor.py:282](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/executor.py:282)

**Mechanismus.** queue.Empty beschreibt nur den Zustand beim abgelaufenen Queue-Aufruf. Der anschließende Sweep prüft is_alive() ohne erneutes Lesen der Ereignisqueue und ohne einen normalen Exitcode 0 auszunehmen. Ein noch nicht verarbeitetes TaskCompleted lässt den alten in_flight-Eintrag bestehen; daraus entsteht ein synthetisches Ergebnis mit Exitcode 35.

**Fehlerszenario.** TaskStarted der letzten Aufgabe ist verarbeitet. Der Parent erhält queue.Empty und wird kurz nicht eingeplant. Währenddessen beendet der Worker pytest, publiziert TaskCompleted vollständig, nimmt den bereits bereitgestellten None-Sentinel und endet regulär. Der Parent setzt dann das Ergebnis auf suspicious. Bei der letzten Aufgabe erreicht finished bereits die Gesamtzahl, sodass die echte Completion ungelesen bleibt; bei weiteren Schleifendurchläufen wird sie ausdrücklich verworfen. Der Orchestrator persistiert das synthetische Ergebnis.

**Wörtlicher Beleg:**

```python
                synthetic_events = self._sweep_dead_workers(in_flight, handled_dead_pids)
                for synthetic_event in synthetic_events:
                    synthesized.add(synthetic_event.mutant_name)
                    finished += 1
                    yield synthetic_event
```

**Fixskizze.** Nach beobachtetem Workerende die bis dahin publizierten Ereignisse vor einer Synthese verarbeiten. Einen belastbaren Protokollabschluss für vollständig übermittelte Ereignisse und verspätete Starts verwenden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Eine normale Workerbeendigung zwischen Queue-Timeout und anschließender Liveness-Prüfung kann eine echte Completion durch suspicious ersetzen. Beim letzten Task bleibt die echte Completion ungelesen, weil finished bereits die Gesamtzahl erreicht; nur bei weiteren Schleifendurchläufen wird sie durch executor.py:326–331 ausdrücklich verworfen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-windows-win-01"></a>

#### WIN-01: Atomare Temporärnamen überschreiten NTFS-Komponentenlimit für gültige Dateinamen

**medium · windows · Konfidenz hoch** — `lens:windows` — [src/mutmut_win/atomic_file.py:172](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:172)

**Mechanismus.** Der Atomic-Writer verlängert den vollständigen Zielbasename um 52 ASCII-Zeichen. Das NTFS-Limit von 255 UTF-16-Einheiten pro Namenskomponente gilt unabhängig von der Unterstützung langer Gesamtpfade. Bereits ein gültiger ASCII-Basename mit 204 Zeichen erzeugt somit einen unzulässigen temporären Namen.

**Fehlerszenario.** Eine über also_copy konfigurierte Fixture hat einen gültigen Basisnamen mit 220 ASCII-Zeichen. Beim ersten Staging oder einem erforderlichen Update bildet _open_random_sibling daraus eine Komponente mit 272 Zeichen; os.open scheitert. Der Kopierwrapper wiederholt die gleich lange Namensbildung und bricht schließlich ab. Eine bereits vorhandene unveränderte Kopie kann den Kopierpfad dagegen überspringen.

**Wörtlicher Beleg:**

```python
token = secrets.token_hex(16)
        temp_path = path.with_name(f".{path.name}.mutmut-atomic-{token}.tmp")
        try:
            fd = os.open(temp_path, flags, 0o600)
```

**Fixskizze.** Einen kurzen zufälligen temporären Namen oder einen fest begrenzten Zielpräfix verwenden. O_EXCL und die Identitätsprüfungen beibehalten.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-01"></a>

#### RES-01: Fehler beim Phasenmarkerlesen überspringt die explizite Worker-Bereinigung

**medium · resource-leak · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/process/worker.py:1233](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:1233)

**Mechanismus.** Die erste Anweisung im finally-Block liest den Phasenmarker strikt als UTF-8. Der Helper fängt nur OSError; UnicodeDecodeError propagiert nach seinem eigenen Versuch, den Marker zu entfernen. Dadurch werden das nachfolgende Schließen des Task-Jobs, Monitorshutdown und Captureclose übersprungen. worker_main meldet suspicious mit fatal=false und kann weitere Aufgaben verarbeiten.

**Fehlerszenario.** Ein nur für einen konkreten MUTANT_UNDER_TEST-Wert aktiver Sessionfinish-Hook überschreibt den über die Umgebung bekannten Marker nach dessen Veröffentlichung mit ungültigen UTF-8-Bytes. Nach regulärem pytest-Ende bleibt der Task-Jobhandle offen, und ein bereits laufender Monitor kann weiterlaufen. Nachkommen und eine von ihnen offen gehaltene Capture-Pipe können ebenfalls fortbestehen. Der übergeordnete Pool begrenzt ihre Lebensdauer; der Marker-Unlink wird weiterhin versucht, und Capture kann sich bei EOF selbst beenden. Im Timeoutpfad ist der Task-Job bereits vorher geschlossen. Ein Überleben nach dem Tod des tatsächlichen Pool-Jobinhabers ist nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
    finally:
        phase_executed = consume_pytest_phase_guard(phase_marker_path, phase_marker_token)
```

**Fixskizze.** Die Ressourcenfreigabe in ein äußerstes finally legen, das unabhängig von der Markerdiagnostik ausgeführt wird. Ungültige Kodierung als fehlenden gültigen Nachweis behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Enthält der Phasenmarker nach regulärem pytest-Ende ungültige UTF-8-Bytes, überspringt UnicodeDecodeError die nachfolgende explizite Worker-Bereinigung. Der Windows-Task-Jobhandle und ein bereits gestarteter Monitor können bis zum Worker-/Pool-Ende bestehen bleiben; Hintergrundnachkommen und deren offene Capture-Pipe können ebenfalls fortbestehen. Marker-Unlink wird weiterhin versucht, die Capture-Pipe kann bei EOF selbst schließen, und im Timeoutpfad ist der Task-Job bereits bereinigt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Nach regulärem pytest-Ende kann ein nur für einen konkreten Mutanten aktiver Sessionfinish-Hook den bekannten Marker mit ungültigen UTF-8-Bytes überschreiben. Der resultierende UnicodeDecodeError überspringt die explizite Aufgabenbereinigung. Das Windows-Jobhandle und gegebenenfalls Nachkommen sowie ein bereits laufender Monitor bleiben während weiterer Aufgaben bestehen. Capture bleibt insbesondere dann aktiv, wenn ein Nachkomme den geerbten Pipe-Schreibhandle offen hält; ohne diesen Umstand kann es sich über EOF selbst schließen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-02"></a>

#### RES-02: Validierungsfehler kann bereits wiederverwendeten Dateideskriptor schließen

**medium · race · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/atomic_file.py:222](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:222)

**Mechanismus.** Ein fehlgeschlagener Validierungsversuch schließt fd zunächst in Zeile 204, behält dessen Zahlenwert aber bei. Erschöpfung der Versuche oder eine Ausnahme vor dem continue, etwa KeyboardInterrupt im Retry-Sleep, führt anschließend zum zweiten Close im BaseException-Handler. suppress(OSError) schützt keinen inzwischen wiedervergebenen gültigen Deskriptor.

**Fehlerszenario.** Nach dem ersten Close innerhalb desselben fehlgeschlagenen Validierungsversuchs erhält ein anderer Thread dieses Prozesses die freigegebene CRT-Deskriptornummer für eine eigene Datei. Retry-Erschöpfung oder ein Interrupt vor dem continue schließt dann diese fremde Ressource. Ein erreichbarer Mehrthread-Kontext ist die atomare Phasenmarker-Publikation im pytest-Prozess, während Hintergrundthreads der getesteten Anwendung Dateien öffnen. Eine Wiedervergabe nur zwischen früheren, bereits erfolgreich fortgesetzten Wiederholungen genügt nicht; Validierungsabweichung und Wiedervergabe sind zusätzliche Voraussetzungen.

**Wörtlicher Beleg:**

```python
        except BaseException:
            # The validation-failure path already closed and unlinked its own
            # fd before deciding to retry or fail; suppressing the second
            # close keeps every exit route uniform.
            with contextlib.suppress(OSError):
                os.close(fd)
```

**Fixskizze.** Die Ownership beim ersten Close unmittelbar aufheben und nur einen weiterhin eigenen Deskriptor freigeben. Möglichst eine einzige exception-sichere Freigabestelle verwenden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Wenn nach dem Close in atomic_file.py:204 innerhalb desselben fehlgeschlagenen Validierungsversuchs ein anderer Thread desselben Prozesses die Deskriptornummer übernimmt, kann Retry-Erschöpfung oder eine Ausnahme vor dem continue den fremden Deskriptor durch atomic_file.py:222 schließen. Eine zwischen früheren, erfolgreich fortgesetzten Wiederholungen erfolgte Wiedervergabe allein genügt nicht.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-03"></a>

#### RES-03: Fehlgeschlagener Capture-Konstruktor verliert beide Pipe-Deskriptoren

**medium · resource-leak · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/process/output_capture.py:35](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/output_capture.py:35)

**Mechanismus.** Nach erfolgreichem os.pipe() folgen die Nonblocking-Umstellung, weitere Initialisierung und Thread.start() ohne Rollback. Scheitert der Aufbau vor dem tatsächlichen Readerstart, gibt es weder einen gestarteten Reader mit finally noch einen fertigen Kontextmanager, dessen __exit__ aufgerufen werden könnte. Die rohen Integer-Deskriptoren werden bei Objektfreigabe nicht automatisch geschlossen.

**Fehlerszenario.** Wegen Ressourcenknappheit scheitert etwa der native Threadstart, obwohl die Pipe zuvor erfolgreich angelegt wurde. Im regulären Worker liegt die Capture-Konstruktion vor dem zugehörigen try/finally. worker_main kann RuntimeError als nichtfatal melden und weitere Aufgaben verarbeiten, sofern diese Recovery selbst gelingt. Wiederholte fehlgeschlagene Konstruktionen verlieren dann weitere Deskriptoren bis zum Prozessende. Ein gewöhnlicher erfolgreicher Aufbau ist nicht betroffen.

**Wörtlicher Beleg:**

```python
        self._read_fd, self._write_fd = os.pipe()
        os.set_blocking(self._read_fd, False)
        self._state_lock = threading.Lock()
        self._tail = bytearray()
        self._total_bytes = 0
        self._stop = threading.Event()
        self._closed = False
        self._reader = threading.Thread(
            target=self._drain,
            name="mutmut-output-capture",
            daemon=True,
        )
        self._reader.start()
```

**Fixskizze.** Den Aufbau ab os.pipe() exception-sicher gestalten. Noch eigene Deskriptoren bei Fehlern schließen und einen gegebenenfalls bereits gestarteten Reader gezielt beenden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Scheitert die Initialisierung nach erfolgreichem os.pipe() und vor dem tatsächlichen Readerstart, bleiben beide Pipe-Deskriptoren bis zum Prozessende offen. Wiederholte solche Fehler können im weiterlaufenden Worker zusätzliche Deskriptoren verlieren.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Nach erfolgreichem os.pipe() verliert BoundedOutputCapture beide Deskriptoren, wenn eine nachfolgende Initialisierung vor dem tatsächlichen Readerstart fehlschlägt. Besonders ein wegen Ressourcenknappheit scheiternder Threadstart ist über den regulären Workerpfad erreichbar; gelingt dessen Recovery, können weitere fehlgeschlagene Konstruktionen zusätzliche Deskriptoren bis zum Prozessende zurücklassen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-07"></a>

#### RES-07: Interrupt bei der Freigabe kann weitere Datenbank-Locks offenlassen

**medium · resource-leak · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/process/run_lock.py:817](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/run_lock.py:817)

**Mechanismus.** DatabaseRunLocks.release ruft die einzelnen Freigaben nacheinander ohne unabhängige finally-Stufen auf. Ein einzelner WorkspaceRunLock schließt zwar seinen eigenen Deskriptor, kann KeyboardInterrupt aus der Metadatenpublikation aber weiterreichen. Dann werden die übrigen Locks und _locks.clear() nicht erreicht. Zusätzlich steht die Konstruktion eines weiteren Locks außerhalb des Erwerbs-Rollbacks.

**Fehlerszenario.** Bei vorhandener Datenbank sind Pfad- und Identitätslock gehalten. Während der zuerst ausgeführten Freigabe des Identitätslocks trifft Ctrl-C etwa in einem Retry-Sleep ein. Dessen eigener Deskriptor wird geschlossen, der verbliebene Pfadlock jedoch nicht. Fängt ein langlebiger Host den Interrupt ab und läuft ohne erneuten expliziten Freigabeversuch weiter, kann dieser Lock Folgeaufrufe blockieren. Gewöhnliche abgefangene Metadatenfehler genügen nicht; ein Interrupt im Kontextkörper wird regulär bereinigt, und das Prozessende gibt die Handles frei. Der zusätzliche Konstruktor-Rollbackfehler betrifft eine Ausnahme im zweiten Konstruktor während des initialen __enter__; bei refresh_identity greift der bereits betretene äußere Kontext.

**Wörtlicher Beleg:**

```python
    def release(self) -> None:
        for lock in reversed(tuple(self._locks.values())):
            lock.release()
        self._locks.clear()
```

**Fixskizze.** Jede Lock-Freigabe unabhängig ausführen und den ersten Fehler erst nach den übrigen Freigaben weiterreichen. Konstruktion und Erwerb gemeinsam in den initialen Rollback aufnehmen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein während der Einzel-Lock-Freigabe weitergereichter KeyboardInterrupt kann die Freigabe der übrigen Datenbank-Locks verhindern. Gewöhnliche abgefangene Dateisystemfehler lösen diesen Abbruch nicht aus. Dauerhafte Auswirkungen setzen einen weiterlaufenden Prozess ohne erneuten expliziten Freigabeversuch voraus.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. KeyboardInterrupt während der ersten Einzelfreigabe kann bei gehaltenem Pfad- und Inodelock den Pfadlock im weiterlaufenden Host offenlassen. Gewöhnliche abgefangene Metadatenfehler reichen dafür nicht aus. Ein separater Rollback-Mangel besteht bei einer Ausnahme im zweiten Konstruktor während des initialen Erwerbs, nicht generell bei refresh_identity().

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-09"></a>

#### RES-09: Browser startet Diff-Threads ohne anwendungsseitige Parallelitätsgrenze

**medium · performance · Konfidenz mittel** — `lens:resources` — [src/mutmut_win/browser.py:566](C:/claude_codex/mutmut-win-astra/src/mutmut_win/browser.py:566)

**Mechanismus.** Jedes verarbeitete Mutanten-Highlight startet einen neuen Thread. _loading_id wird erst nach dem vollständigen Laden und Berechnen des Diffs geprüft; überholte Berechnungen werden nicht abgebrochen. Der Renderer liest und parst das generierte Modul sowie die Originalquelle erneut, ohne begrenzte Warteschlange oder Wiederverwendung dieser Arbeit.

**Fehlerszenario.** Bei schnellen tatsächlichen Auswahlwechseln in gültigen großen Modulen dauern Diffs länger als die Abstände zwischen den Highlights. Weitere Threads starten, während vorherige noch rechnen; ihre Modulrepräsentationen und ihr Ressourcenbedarf können sich überlagern. Fertige Threads enden, und eine gedrückte Pfeiltaste erzeugt am Tabellenende nicht zwingend weitere Highlights. Ein konkreter Ressourcenabsturz oder dauerhaft endloses Wachstum wurde nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
        thread = Thread(target=_load_thread, daemon=True)
        thread.start()
```

**Fixskizze.** Die Berechnung auf einen oder wenige Worker begrenzen und noch nicht gestartete überholte Anforderungen durch die neueste ersetzen. Verifizierte Modulparses gegebenenfalls wiederverwenden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Jedes verarbeitete Mutanten-Highlight startet einen eigenen Diff-Thread ohne anwendungsseitige Parallelitätsgrenze. Treffen weitere Highlights vor Abschluss früherer Berechnungen ein, können sich Threads und deren vollständige Modulrepräsentationen überlagern; überholte Berechnungen werden nicht abgebrochen. „Unbegrenzt“ bezeichnet die fehlende konfigurierte Obergrenze, kein zwingend endloses Wachstum. Gedrückte Pfeiltasten erzeugen nur solange weitere Highlights, wie die Auswahl tatsächlich wechselt. Ein möglicher Fehler von Thread.start läge außerhalb des Fehlerhandlers des Workers, ist hier jedoch nicht reproduziert.
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: medium. Jedes verarbeitete Mutanten-Highlight startet einen eigenen Diff-Thread ohne anwendungsseitige Parallelitätsgrenze. Bei schnellen Auswahlwechseln und langsamen Diff-Berechnungen können sich ausstehende Threads und deren Ressourcenbedarf ansammeln; veraltete Anforderungen rechnen weiter. Ein konkreter Ressourcenabsturz und dauerhaft unbegrenztes Wachstum sind nicht nachgewiesen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-04"></a>

#### EDGE-04: Akzeptierte Workerzahlen über 61 verhindern unter Windows die Generierung

**medium · windows · Konfidenz hoch** — `lens:boundaries` — [src/mutmut_win/process/generation_supervisor.py:245](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/generation_supervisor.py:245)

**Mechanismus.** max_children wird ungekappt an ProcessPoolExecutor übergeben. Dessen Windows-Grenze beträgt 61 Worker. Die Konfiguration prüft lediglich >=1; der Standardwert übernimmt os.cpu_count ohne Obergrenze.

**Fehlerszenario.** max_children=62 wird akzeptiert. Wenn os.cpu_count() mehr als 61 liefert, ist bereits der automatische Standard betroffen, etwa 64 auf einem entsprechenden Windows-System. Sobald mindestens eine Quelldatei tatsächlich zur Generierung ansteht, scheitert die Executor-Konstruktion vor dem ersten submit mit ValueError. Eine leere Dateiliste umgeht den Aufruf; ein expliziter Wert bis 61 ermöglicht den Lauf.

**Wörtlicher Beleg:**

```text
generation_supervisor.py:245:
pool = ProcessPoolExecutor(max_workers=max_children, mp_context=spawn_context)

config.py:26:
return max(1, os.cpu_count() or 1)

config.py:153–155:
max_children: int = Field(
    default_factory=_default_max_children,
    ge=1,
```

**Fixskizze.** Effektive Workerzahl des Windows-Generationsexecutors auf dessen Grenze und Zahl der Aufgaben begrenzen; automatische Standards auf Systemen mit mehr als 61 CPUs absichern.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Unter Windows/CPython 3.14.7 scheitert jeder Generierungslauf mit mindestens einer Quelldatei, wenn die akzeptierte Konfiguration max_children > 61 enthält. Das betrifft auch den unveränderten Standardwert, sofern os.cpu_count() mehr als 61 liefert.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-contracts-contract-07"></a>

#### CONTRACT-07: Ungültige UTF-8-Ausführungsmarke überspringt Task-Cleanup

**medium · resource-leak · Konfidenz hoch** — `lens:contracts` — [src/mutmut_win/process/worker.py:1233](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:1233)

**Mechanismus.** consume_pytest_phase_guard liest strikt als UTF-8 und fängt nur OSError. Sein eigenes finally versucht weiterhin, die Marke zu entfernen, unterdrückt UnicodeDecodeError aber nicht. Der Aufruf als erste Operation im Task-finally verhindert danach Jobclose, Monitor-Shutdown sowie explizites Capture- und Runtime-Cleanup. worker_main meldet den Fehler als nichtfatales suspicious und kann weiterarbeiten. Das Jobhandle ist ein Integer ohne automatische Jobfreigabe.

**Fehlerszenario.** Ein Test-Plugin oder Fixture-Teardown überschreibt nach der ersten Proof-Veröffentlichung die über MUTMUT_PYTEST_PHASE_SENTINEL_PATH bekannte Marke mit ungültigen UTF-8-Bytes und hinterlässt einen Hintergrundprozess. Auf einen konkreten MUTANT_UNDER_TEST-Wert begrenzt, lässt dies vorherige Clean-/Stats-/Fail-Phasen passieren. Bei normalem pytest-Ende ohne bereits erfolgte Timeoutbereinigung bleibt der Task-Job offen; Nachkommen können während weiterer Mutanten bis Workerende beziehungsweise Pool-Shutdown weiterlaufen. Die Capture kann bei EOF selbst enden, TemporaryDirectory besitzt einen Finalizer; ein dauerhaftes Runtime-Verzeichnisleck und ein Überleben nach dem Tod des Pool-Jobinhabers sind hier nicht belegt.

**Wörtlicher Beleg:**

```python
    try:
        return marker_path.read_text(encoding="utf-8") == expected_token
    except OSError:
        return False
    finally:
        with contextlib.suppress(OSError):
            marker_path.unlink()
```

**Fixskizze.** Proof begrenzt als Bytes vergleichen oder Decodierungsfehler ungültig werten; Cleanup unabhängig von Proofauswertung in finally garantieren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein im Mutantenlauf nach erster Veröffentlichung mit ungültigem UTF-8 überschriebener Proof lässt UnicodeDecodeError aus dem Task-finally entweichen. Der weiterlaufende Worker überspringt insbesondere das Schließen seines Task-Job-Handles, sodass vorhandene Hintergrundnachkommen bis zum Worker-Ende beziehungsweise Pool-Shutdown weiterlaufen können. Auch die expliziten Monitor-, Capture- und Runtime-Cleanup-Aufrufe entfallen; daraus folgt nicht zwingend ein dauerhaft zurückbleibendes Runtime-Verzeichnis, da TemporaryDirectory zusätzlich automatische Bereinigung besitzt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Eine nach der ersten Veröffentlichung mit ungültigen UTF-8-Bytes überschriebene Ausführungsmarke überspringt bei normalem pytest-Ende den expliziten Task-Cleanup. Dadurch bleibt insbesondere das Windows-Task-Job-Handle offen; zurückgelassene Nachkommen können während weiterer Mutanten bis zum Worker-Ende beziehungsweise Pool-Shutdown weiterlaufen. Ein dauerhafter Runtime-Verzeichnisverlust folgt daraus nicht zwingend, weil TemporaryDirectory einen eigenen Finalizer besitzt; auch die Capture kann bei EOF selbst enden. Der zentrale Job-Cleanup-Fehler bleibt davon unberührt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-process-lifecycle-proc-03"></a>

#### PROC-03: Executor-Konstruktor verliert Jobhandle bei nachfolgendem Initialisierungsfehler

**low · resource-leak · Konfidenz hoch** — `nondet:process-lifecycle` — [src/mutmut_win/process/executor.py:107](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/executor.py:107)

**Mechanismus.** Der Konstruktor erzeugt einen nativen Jobhandle vor mehreren multiprocessing-Ressourcen ohne Rollback. Scheitert eine Queue-Erzeugung, erhält der Aufrufer keinen Executor zum Herunterfahren. Für den als int gespeicherten Handle existiert kein Finalizer.

**Fehlerszenario.** In einem langlebigen einbettenden Prozess gelingt CreateJobObjectW, danach scheitert Queue-/Pipe-/Semaphore-Erzeugung durch Ressourcenknappheit. Wiederholte Konstruktionen verlieren je einen Jobhandle. Noch keine Worker vorhanden, daher keine Erklärung der beobachteten Waisen.

**Wörtlicher Beleg:**

```text
executor.py:99: self._job_handle = create_kill_on_close_job()
executor.py:107: self._mp_ctx = multiprocessing.get_context("spawn")
executor.py:116: self._containment_queue: Any = self._mp_ctx.SimpleQueue()
```

**Fixskizze.** Konstruktor mit ExitStack/Exception-Rollback aufbauen und bei jedem nachfolgenden Fehler bereits erzeugte Ressourcen schließen; Queue-Fehler nach Job-Erzeugung abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-timing-assumptions-time-04"></a>

#### TIME-04: Grandchild-Test ersetzt bestätigten Prozessstart durch sleep(1) und kann falsch grün werden

**low · nondeterminism · Konfidenz hoch** — `nondet:timing-assumptions` — [tests/unit/test_job_object.py:107](C:/claude_codex/mutmut-win-astra/tests/unit/test_job_object.py:107)

**Mechanismus.** Eine feste Sekunde ersetzt Bereitschaftsmeldung/Enkel-PID; anschließend wird ausschließlich Ende des direkten Kindes geprüft.

**Fehlerszenario.** Unter Startlast erreicht der Interpreter den Enkel-Spawn erst nach Ablauf der festen Sekunde. Der Test schließt vorher das Job Object und besteht aufgrund des Root-Exits, obwohl noch kein Enkel existierte. Andere Integrationstests synchronisieren den Start anhand von PIDs und prüfen Enkelprozesse ausdrücklich; dieser Befund belegt daher keine allgemeine Abdeckungslücke oder defekte Produktionsbereinigung.

**Wörtlicher Beleg:**

```python
        # Give the grandchild time to spawn.
        import time

        time.sleep(1)

        # Close Job handle — must kill proc AND its grandchild.
        close_job(job)
        exit_code = proc.wait(timeout=10)
        assert exit_code is not None
```

**Fixskizze.** Enkel-PID/Ready-Marker empfangen, Existenz vor Close und Ende danach explizit prüfen; begrenzte Fristen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Der Grandchild-Unit-Test verwendet eine feste Wartezeit ohne Spawn-Bestätigung und prüft anschließend nur das direkte Kind. Dadurch kann er erfolgreich sein, obwohl der angekündigte Enkel-Testfall nicht ausgeführt wurde.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Der Grandchild-Test synchronisiert den Enkel-Spawn nicht und bestätigt ausschließlich das Ende des direkten Kindes. Deshalb kann er bestehen, ohne die behauptete Enkel-Terminierung geprüft zu haben; ein unter Startlast verzögerter Enkel-Spawn ist ein möglicher, hier nicht reproduzierter Auslöser.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-orchestrator-orch-01"></a>

#### ORCH-01: Vorzeitig erzeugte Executor verlieren bei frühen Pipeline-Enden ihren Jobhandle

**low · resource-leak · Konfidenz hoch** — `mod:orchestrator` — [src/mutmut_win/orchestrator.py:937](C:/claude_codex/mutmut-win-astra/src/mutmut_win/orchestrator.py:937)

**Mechanismus.** Die CLI konstruiert einen SpawnPoolExecutor einschließlich Windows-Jobhandle vor der Pipeline und injiziert ihn. Frühe Rückgaben und Fehler umgehen den einzigen shutdown-Aufruf im späteren Dispatch-try/finally. Ein zusätzlicher Boundary-Konfigurationsfehler liegt auch nach der späten Standardkonstruktion noch vor diesem Freigabebereich. Der Integer-Jobhandle besitzt keinen Finalizer.

**Fehlerszenario.** Ein langlebiger Windows-Host ruft die CLI wiederholt auf oder injiziert je Aufruf einen neuen echten Executor. Wenn die Pipeline vor Dispatch zurückkehrt oder scheitert und der Host nicht selbst shutdown ausführt, bleibt jeweils ein Jobhandle bis zum Prozessende offen. Direkte Orchestrator-Aufrufe mit lazy Standardexecutor erzeugen vor den frühen Rückgaben noch keinen Executor; dort betrifft die Lücke nur Fehler nach dessen später Konstruktion, insbesondere die Boundary-Konfiguration. Für diese Pfade sind noch keine gestarteten Poolworker nachgewiesen.

**Wörtlicher Beleg:**

```python
        executor = self._get_executor()
        configure_boundary = getattr(executor, "configure_pytest_boundary", None)
        if callable(configure_boundary):
            configure_boundary(self._runner.pytest_boundary_data)
        interrupted = False
        try:
            executor.start(tasks_with_timeouts)
```

**Fixskizze.** CLI-Executor erst bei Dispatch anlegen; gesamte Nutzung inkl. Boundary unter finally. Ownership injizierter Executor konsistent auf allen run-Ausgängen behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Bei wiederholten Aufrufen im selben Windows-Prozess bleibt pro neu erzeugtem, injiziertem SpawnPoolExecutor ein Jobhandle offen, wenn die Pipeline vor dem Dispatch zurückkehrt oder scheitert und der Aufrufer nicht selbst shutdown() ausführt. Die CLI erzeugt solche Executor vorzeitig und besitzt keinen eigenen Cleanup. Ohne Injection betrifft die Lücke nur Fehler nach der späten Konstruktion und vor Eintritt in den bestehenden try/finally-Block, insbesondere die Boundary-Konfiguration.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Normale CLI-Läufe konstruieren einen Windows-Executor vor der Pipeline und lassen dessen Jobhandle bei Rückgaben oder Fehlern vor dem Dispatch bis zum Prozessende offen. In langlebigen Hosts können diese Handles pro Aufruf akkumulieren. Direkte Aufrufe mit lazy Standardexecutor sind von den frühen Rückgaben nicht betroffen; dessen Boundary-Konfiguration liegt allerdings ebenfalls außerhalb der garantierten Freigabe. Für diese Pfade sind keine bereits gestarteten Worker nachgewiesen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-cli-cli-04"></a>

#### CLI-04: Früh erzeugter Executor bleibt bei Läufen ohne Workerphase ungeschlossen

**low · resource-leak · Konfidenz hoch** — `mod:cli` — [src/mutmut_win/cli.py:725](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:725)

**Mechanismus.** Die CLI allokiert vor orchestrator.run einen Executor, der unter Windows bereits ein rohes Jobhandle besitzt. Das shutdown-finally liegt erst in der späteren Workerphase; frühe Fehler und Rückgaben ohne Dispatch erreichen es nicht. Ein Finalizer für dieses ganzzahlige Handle fehlt. Ein dauerhaftes Leck sämtlicher Queue-Ressourcen ist damit nicht zusätzlich nachgewiesen.

**Fehlerszenario.** Vollständiger Reuse oder früher Fehler bei wiederholten Click-Aufrufen in langlebigem Host lässt rohe Jobhandles bis Prozessende offen. Einmalige CLI begrenzt Leck auf eigene Lebensdauer.

**Wörtlicher Beleg:**

```python
executor = (
                None
                if dry_run
                else SpawnPoolExecutor(max_workers=config.max_children, config=config)
            )
```

**Fixskizze.** Executor erst vor Dispatch erzeugen oder ab Konstruktion umfassend mit finally/ExitStack verwalten; idempotentes shutdown auf allen Ausgängen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Reale CLI-Läufe verlieren unter Windows bei Rückkehr oder Fehler vor der Workerphase das bereits erzeugte rohe Jobhandle. Wiederholte Aufrufe im selben langlebigen Prozess akkumulieren diese Handles. Ein dauerhaftes Leck sämtlicher Queue-Ressourcen ist damit nicht zusätzlich nachgewiesen.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-locking-lock-04"></a>

#### LOCK-04: Gleichzeitige Erstinitialisierung des Guards liefert rohen Windows-Zugriffsfehler

**low · race · Konfidenz mittel** — `mod:locking` — [src/mutmut_win/process/run_lock.py:267](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/run_lock.py:267)

**Mechanismus.** Das Initialisierungsbyte wird anhand einer zuvor erfassten Dateigröße geschrieben, bevor der eigene Byte-Range-Lock erworben wurde. Zwei Prozesse können Größe 0 sehen; A initialisiert und sperrt das Byte, während B erst danach seinen bereits beschlossenen Schreibzugriff ausführt. Die zwischenliegenden Identitätsprüfungen aktualisieren die verwendete Größe nicht. _open_guard reicht einen möglichen OSError weiter, bevor _try_lock_guard den Konflikt übersetzen könnte.

**Fehlerszenario.** Bei den ersten zwei gleichzeitig gestarteten Läufen pausiert Prozess B nach fstat auf dem leeren Guard. A initialisiert und sperrt Byte 0; B schreibt nach seiner Fortsetzung anhand des alten Stat-Ergebnisses in das nun gesperrte Byte. Ein dadurch entstehender Windows-OSError entkommt unverändert statt als RunLockHeldError; die CLI fängt hier nur MutmutWinError. Der konkrete Ausnahmeuntertyp wurde nicht reproduziert. Betroffen ist die Diagnose des abgewiesenen Laufs, nicht die Exklusivität.

**Wörtlicher Beleg:**

```python
        handle_stat = _verify_open_leaf(fd, path, label="guard")
        if handle_stat.st_size == 0:
            # ``msvcrt.locking`` needs a concrete byte range.  Identity and
            # link-count checks happen before this first write so an attacker-
            # controlled leaf can never receive the initial byte.
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b"\0")
            os.fsync(fd)
```

**Fixskizze.** Die Erstinitialisierung koordinieren oder einen erwartbaren Schreibkonflikt nach Identitätsprüfung in den regulären Lockfehler übersetzen. Das Interleaving fstat(B), lock(A), write(B) gezielt prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low. Bei gleichzeitigem erstmaligem Guard-Erwerb kann eine veraltete Größenprüfung einen Schreibversuch auf das inzwischen gesperrte Initialisierungsbyte auslösen. Der dadurch mögliche Windows-OSError wird unverändert weitergereicht, statt als regulärer Lockkonflikt diagnostiziert zu werden. Der konkrete Untertyp PermissionError ist hier nicht reproduziert.
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low. Bei gleichzeitigem Erstzugriff auf einen noch leeren Guard kann ein Prozess anhand einer veralteten Größenaufnahme in das inzwischen durch einen anderen Prozess gesperrte Byte schreiben. Ein dadurch ausgelöster Windows-OSError entkommt unverändert statt als RunLockHeldError; der konkrete Untertyp PermissionError ist hier nicht dynamisch bestätigt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-spawn-spawn-04"></a>

#### SPAWN-04: Queue-Aufbaufehler im Pool-Konstruktor verliert Windows-Jobhandle

**low · resource-leak · Konfidenz hoch** — `mod:spawn` — [src/mutmut_win/process/executor.py:107](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/executor.py:107)

**Mechanismus.** Der Konstruktor erzeugt das Windows-Jobhandle vor drei Queue-Ressourcen. Für Fehler in Queue() oder SimpleQueue() existieren weder Rollback noch Finalizer. Bei fehlgeschlagenem __init__ erhält der Aufrufer keine Instanz für shutdown; dessen Zustandsfelder sind zudem noch nicht vollständig aufgebaut.

**Fehlerszenario.** CreateJobObjectW gelingt, danach scheitert die Anlage einer Pipe oder eines Synchronisationsobjekts. Ein weiterlaufender Host fängt den Fehler ab und versucht die Konstruktion erneut; dabei können sich Jobhandles bis zum Prozessende ansammeln. Zu diesem Zeitpunkt wurden noch keine Worker gestartet. Beim gewöhnlichen abbrechenden CLI-Prozess beendet das Prozessende die Leckdauer.

**Wörtlicher Beleg:**

```python
        self._mp_ctx = multiprocessing.get_context("spawn")
        self._task_queue: multiprocessing.queues.Queue[dict[str, object] | None] = (
            self._mp_ctx.Queue()
        )
        self._event_queue: multiprocessing.queues.Queue[dict[str, object]] = self._mp_ctx.Queue()
```

**Fixskizze.** Die Konstruktion mit einer Ausnahmebereinigung aufbauen und jede erzeugte Ressource sofort darin registrieren. Bei nachfolgenden Fehlern alle bereits übernommenen Ressourcen schließen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-atomic-atom-03"></a>

#### ATOM-03: Fehlgeschlagene Veröffentlichung lässt schreibgeschützte Tempdateien zurück

**low · resource-leak · Konfidenz hoch** — `mod:atomic` — [src/mutmut_win/atomic_file.py:282](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:282)

**Mechanismus.** atomic_copy_file übernimmt den Quellmodus; _atomic_write_attempt setzt ihn vor der Veröffentlichung auf den privaten Sibling. Bei einer schreibgeschützten Quelle ist damit auch der Sibling schreibgeschützt. Scheitert replace, versucht _cleanup_owned_temp lediglich unlink und unterdrückt den Windows-PermissionError. Weitere atomare Versuche erzeugen neue Namen, ohne diese Vorgänger selbst zu entfernen.

**Fehlerszenario.** Eine reguläre schreibgeschützte Projektdatei wird kopiert, während ein anhaltender Dateilock das Replace verhindert. Jeder fehlgeschlagene Veröffentlichungsversuch kann einen vollständigen schreibgeschützten Sibling hinterlassen. Bei den Standard-Retrygrenzen sind bis zu 30 solcher Dateien pro vollständig gescheiterter _copy_with_retry-Ausführung möglich. Bricht der Lauf vorher ab, wird die spätere Stagingbereinigung nicht erreicht. Erfolgreiche automatische Kopier- oder Baumsynchronisation kann die Reste dagegen anschließend entfernen; beim einzelnen konfigurierten Dateikopierpfad ist dies nicht gewährleistet. Datenverlust oder falsche Mutationsergebnisse sind daraus nicht belegt.

**Wörtlicher Beleg:**

```python
    if _identity(current) == identity:
        with contextlib.suppress(OSError):
            path.unlink()
```

**Fixskizze.** Für einen nachweislich eigenen, unveränderten und einfach verlinkten Sibling den Schreibschutz vor dem Unlink sicher aufheben. Die bestehenden Identitäts- und Linkschutzregeln bewahren und die Kombination aus schreibgeschützter Quelle und echtem Replacefehler prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Fehlgeschlagene atomare Kopien schreibgeschützter Dateien lassen unter Windows pro gescheitertem Replaceversuch einen schreibgeschützten Sibling zurück. Ein später erfolgreicher atomarer Versuch beseitigt diese Vorgänger nicht. Übergeordnete Staging-Löschdurchläufe können sie anschließend entfernen; bei vorzeitigem Abbruch oder einzelnen konfigurierten Dateikopien ist diese Bereinigung nicht gewährleistet.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Beim atomaren Kopieren einer schreibgeschützten Quelle können fehlgeschlagene Replace-Versuche schreibgeschützte private Tempdateien hinterlassen. Der atomare Retrypfad entfernt frühere Hinterlassenschaften nicht. Bei einem Abbruch vor der nachgelagerten Stagingbereinigung bleiben sie bestehen; erfolgreich abgeschlossene automatische oder Baum-Synchronisation kann sie dagegen entfernen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-races-race-05"></a>

#### RACE-05: Ctrl-C während Windows-Start wird zu Infrastrukturfehler

**low · error-handling · Konfidenz hoch** — `lens:races` — [src/mutmut_win/process/suspended_spawn.py:180](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/suspended_spawn.py:180)

**Mechanismus.** Der Windows-Startadapter fängt nach dem inneren Cleanup BaseException ab und verpackt damit auch KeyboardInterrupt und SystemExit als ProcessContainmentError. Die regulären Aufrufer reichen diese bereits umgewandelte Ausnahme weiter. Der Orchestrator erkennt den ursprünglichen Interrupt nicht mehr; die CLI behandelt ihn als Infrastrukturfehler.

**Fehlerszenario.** Während der Bootstrap-Serialisierung beim Start des Generierungs-Supervisors oder eines Mutationsworkers löst Ctrl-C im Elternprozess KeyboardInterrupt aus. Nach der Bereinigung wird daraus ProcessContainmentError. Bei erfolgreicher Statuspersistierung steht der Run auf failed statt interrupted; die CLI meldet den Containmentfehler und endet mit Exitcode 1. Vergleichbare Verpackungen existieren beim atomaren pytest- und Typechecker-Start. Ein falscher erfolgreicher Lauf oder Datenverlust ist damit nicht belegt.

**Wörtlicher Beleg:**

```python
    except BaseException as exc:
        raise ProcessContainmentError(
            "Could not create, assign, and resume a contained Windows worker process."
        ) from exc
```

**Fixskizze.** Das Cleanup für BaseException beibehalten, anschließend KeyboardInterrupt und SystemExit unverändert weiterreichen. Nur gewöhnliche Startfehler in ProcessContainmentError umwandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-failclosed-fail-03"></a>

#### FAIL-03: Ein einzelner messbarer Ausgabestand wird als nachgewiesener Stillstand gewertet

**low · correctness · Konfidenz hoch** — `lens:failclosed` — [src/mutmut_win/process/loop_monitor.py:307](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/loop_monitor.py:307)

**Mechanismus.** Die Mindestanzahl gilt für sämtliche Samples, nicht für die Samples mit messbarem output_bytes. Bei mindestens fünf Gesamtsamples, aber genau einem Ausgabewert, ergibt letzter minus erster Wert null. bool(measurable) reicht anschließend als Nachweis geringen Ausgabewachstums, obwohl kein zweiter Messpunkt vorliegt.

**Fehlerszenario.** Der vorhandene ProcessMonitor-log_path-Pfad misst die Ausgabe einmal erfolgreich. Später ist die Logdatei entfernt oder unzugänglich; stat()-Fehler werden als None in weiteren Samples erfasst. Bei ausreichend hoher CPU und ohne wirksames I/O-Veto kann classify_samples daraus killed_by_infinite_loop statt timeout machen. Eine entsprechende Erreichbarkeit im regulären Worker ist nicht belegt: Dieser verwendet capture.total_bytes, das unter Lock stets einen ganzzahligen Zähler liefert.

**Wörtlicher Beleg:**

```python
    measurable = [s.output_bytes for s in samples if s.output_bytes is not None]
    output_growth = max(0, measurable[-1] - measurable[0]) if measurable else 0

...

    output_ok = bool(measurable) and output_growth < thresholds.output_threshold and not io_active
```

**Fixskizze.** Mindestens zwei zeitlich verschiedene erfolgreiche Ausgabemessungen und ausreichende Abdeckung des Fensters verlangen. Andernfalls die Beobachtung als unzureichend behandeln und beim Timeout bleiben.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Der Klassifikator kann bei mindestens fünf Gesamtsamples, aber genau einer erfolgreichen Ausgabemessung, einen IL-Verdict liefern. Dies ist über direkte Nutzung von classify_samples beziehungsweise den vorhandenen ProcessMonitor-log_path-Pfad erreichbar. Eine entsprechende Erreichbarkeit im regulären Worker von v2.21.4 ist nicht belegt; dessen Ausgabezähler vermeidet die behaupteten stat()-Ausfälle.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-windows-win-04"></a>

#### WIN-04: Fehlgeschlagene Readonly-Veröffentlichung hinterlässt eigene Tempdateien

**low · resource-leak · Konfidenz hoch** — `lens:windows` — [src/mutmut_win/atomic_file.py:282](C:/claude_codex/mutmut-win-astra/src/mutmut_win/atomic_file.py:282)

**Mechanismus.** atomic_copy_file übernimmt den schreibgeschützten Quellmodus bereits vor replace auf den eigenen temporären Sibling. Scheitert die Veröffentlichung, prüft das Cleanup zwar dessen Identität, versucht jedoch nur unlink und unterdrückt OSError. Das Readonly-Attribut wird nicht entfernt. Der nächste Versuch verwendet einen neuen Namen; die Behandlung des bestehenden Ziels macht den Sibling nicht beschreibbar.

**Fehlerszenario.** Eine einzelne schreibgeschützte Fixture ist über also_copy konfiguriert. Der erste Replace-Versuch scheitert vorübergehend an einer Dateisperre; ein späterer Versuch veröffentlicht erfolgreich. Der erste schreibgeschützte Sibling bleibt zurück, weil dieser Einzeldateipfad keine unmittelbare Geschwisterbereinigung durchführt. Mehrere fehlgeschlagene Versuche können mehrere Reste erzeugen. Erfolgreiche Verzeichnis- beziehungsweise Quellbaumsynchronisation kann solche Dateien nachträglich entfernen; eine unbegrenzte Ansammlung über alle normalen Läufe ist nicht belegt.

**Wörtlicher Beleg:**

```python
if _identity(current) == identity:
        with contextlib.suppress(OSError):
            path.unlink()

...

        if mode is not None:
            temp_path.chmod(mode, follow_symlinks=False)
            _checked_temp(temp_path, temp_identity)
```

**Fixskizze.** Nach dem Schließen des Handles ausschließlich den identitätsgeprüften eigenen Temp-Sibling beschreibbar machen und erneut entfernen. Unbekannte Blätter weiterhin unangetastet lassen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Ein fehlgeschlagener atomarer Kopierversuch einer schreibgeschützten Quelldatei kann unter Windows seinen eigenen schreibgeschützten Temp-Sibling hinterlassen, auch wenn ein Retry erfolgreich veröffentlicht. Nachgelagerte Baum-Bereinigungen können diesen Rest entfernen; insbesondere beim konfigurierten Einzeldatei-Kopierpfad bleibt er nach Rückkehr bestehen. Eine unbegrenzte Ansammlung über sämtliche normalen Läufe ist damit nicht belegt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Bei atomarer Veröffentlichung mit readonly-Quellmodus kann ein fehlgeschlagener Replace-Versuch seinen eigenen readonly-Temp-Sibling zurücklassen, auch wenn ein späterer Versuch erfolgreich ist. Bei einzeln konfigurierten also_copy-Dateien fehlt anschließend eine unmittelbare Sibling-Bereinigung; mehrere fehlgeschlagene Versuche können mehrere Restdateien erzeugen. Eine unbegrenzte Ansammlung über sämtliche Staging-Pfade ist nicht belegt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-04"></a>

#### RES-04: Queue-Initialisierungsfehler verliert zuvor erzeugten Pool-Job

**low · resource-leak · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/process/executor.py:108](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/executor.py:108)

**Mechanismus.** Der Pool-Job wird vor den beiden Queues und der SimpleQueue erzeugt. Deren Konstruktion liegt außerhalb eines Rollbacks; create_kill_on_close_job liefert nur einen rohen Integerhandle ohne automatische Freigabe. Bei fehlgeschlagenem __init__ erhalten die Aufrufer keine vollständig aufgebaute Instanz, die sie regulär per shutdown bereinigen könnten.

**Fehlerszenario.** Unter Windows gelingt die Jobanlage, anschließend scheitert eine Queue-Konstruktion bei der Pipe- oder Synchronisationsanlage. Worker wurden zu diesem Zeitpunkt noch nicht gestartet; das leere Jobhandle bleibt bis zum Ende des Hosts offen. Wiederholte fehlgeschlagene Konstruktionen akkumulieren Handles nur innerhalb desselben weiterlaufenden Prozesses. Getrennte normale CLI-Aufrufe begrenzen den Verlust jeweils durch ihr Prozessende.

**Wörtlicher Beleg:**

```python
        self._task_queue: multiprocessing.queues.Queue[dict[str, object] | None] = (
            self._mp_ctx.Queue()
        )
        self._event_queue: multiprocessing.queues.Queue[dict[str, object]] = self._mp_ctx.Queue()
```

**Fixskizze.** Den Konstruktor durch ExitStack oder einen BaseException-Rollback absichern und die Ressourcen-Ownership erst nach vollständigem Aufbau übertragen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Scheitert unter Windows nach erfolgreicher Jobanlage eine Queue-Konstruktion, bleibt ein leerer Jobhandle bis zum Ende des aufrufenden Prozesses offen. Worker wurden dann noch nicht gestartet. Mehrere Handles akkumulieren nur bei wiederholten Versuchen innerhalb desselben fortbestehenden Prozesses; separate CLI-Aufrufe akkumulieren sie nicht über Prozessenden hinweg.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Scheitert unter Windows nach erfolgreicher Jobanlage einer der Queue-Konstruktoren, bleibt ein leeres Jobhandle bis zum Ende des Hostprozesses offen. Wiederholte Versuche akkumulieren Handles nur innerhalb desselben fortbestehenden Prozesses, nicht über getrennte CLI-Aufrufe hinweg.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-05"></a>

#### RES-05: Früh angelegter CLI-Executor bleibt bei vorzeitigem Pipeline-Ende offen

**low · resource-leak · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/cli.py:725](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:725)

**Mechanismus.** Die CLI erzeugt den Windows-Executor samt Jobhandle vor orchestrator.run(). Seine einzige Freigabe liegt im späteren Dispatch-finally; der CLI-ExitStack registriert kein Executor-Shutdown. Frühe Fehler nach der Konstruktion und erfolgreiche Rückkehr ohne Dispatch umgehen diese Freigabe. Die verzögerte Standarderzeugung des Orchestrators hilft beim bereits injizierten CLI-Executor nicht.

**Fehlerszenario.** Ein langlebiger Host beziehungsweise CliRunner führt wiederholt einen vollständig aus dem Cache wiederverwendeten Lauf aus oder fängt einen Clean-Test-, Forced-Fail- oder anderen Orchestrator-Fehler vor dem Dispatch ab. Pro betroffenem Aufruf kann ein Jobhandle bis zum Hostende offen bleiben. --dry-run und CLI-Vorprüfungen, die bereits vor der Executor-Konstruktion abbrechen, sind ausgenommen. Bei eigenständigen CLI-Prozessen begrenzt die Betriebssystemfreigabe beim Prozessende die Auswirkung.

**Wörtlicher Beleg:**

```python
            executor = (
                None
                if dry_run
                else SpawnPoolExecutor(max_workers=config.max_children, config=config)
            )
```

**Fixskizze.** Auch in der CLI den verzögerten Orchestratoraufbau verwenden oder unmittelbar nach Konstruktion einen Shutdown-Callback im ExitStack registrieren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Bei regulären CLI-Läufen wird ein Windows-Jobhandle vor orchestrator.run() angelegt. Fehler nach dieser Erzeugung und vor dem Dispatch-finally sowie erfolgreiche Läufe ohne Dispatch, insbesondere vollständiger Cache-Reuse, schließen es nicht. Wiederholte Aufrufe im selben Hostprozess akkumulieren solche Handles. CLI-Vorprüfungen vor der Executor-Erzeugung und --dry-run sind nicht betroffen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Reale CLI-Läufe erzeugen den Windows-Executor vor orchestrator.run. Frühe Fehler nach dieser Konstruktion sowie erfolgreiche Rückkehr ohne Dispatch umgehen dessen Shutdown und lassen den Jobhandle bis zum Prozessende offen. Dry-run und bereits vor der Konstruktion abgewiesene CLI-Eingaben sind nicht betroffen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-06"></a>

#### RES-06: Typechecker-Setup kann Jobhandle vor geschütztem Launch verlieren

**low · resource-leak · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/type_checking.py:249](C:/claude_codex/mutmut-win-astra/src/mutmut_win/type_checking.py:249)

**Mechanismus.** Der Typechecker legt sein Windows-Jobhandle vor der Einrichtung der Laufzeit-Unterverzeichnisse an. configure_ephemeral_pytest_environment führt mehrere mkdir-Aufrufe aus; der try-Block mit Job-Cleanup beginnt erst danach. Die äußeren Kontextmanager verwalten nur das temporäre Verzeichnis und die Captures, nicht den rohen Jobhandle.

**Fehlerszenario.** Die Runtimewurzel und der leere Job sind bereits angelegt. Beim anschließenden Anlegen von pytest-cache, python-cache oder hypothesis tritt ein Platz- beziehungsweise Zugriffsfehler oder ein Interrupt auf. Die vorhandenen Kontextmanager bereinigen ihre eigenen Ressourcen, aber das Jobhandle bleibt bis zum Ende des Hosts offen. Ein Typechecker-Kindprozess ist zu diesem Zeitpunkt noch nicht gestartet.

**Wörtlicher Beleg:**

```python
        job_handle = _create_type_checker_job()
        checker_environment = _type_checker_environment()
        configure_ephemeral_pytest_environment(checker_environment, Path(runtime_name))
```

**Fixskizze.** Den Job erst nach dem übrigen Setup erzeugen oder ihn unmittelbar nach seiner Erstellung in ein übergeordnetes finally beziehungsweise einen ExitStack aufnehmen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-resources-res-08"></a>

#### RES-08: Erzwungener Worker-Abbruch hinterlässt externe Runtime-Verzeichnisse

**low · resource-leak · Konfidenz hoch** — `lens:resources` — [src/mutmut_win/process/worker.py:1032](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:1032)

**Mechanismus.** Das pro Task erzeugte TemporaryDirectory liegt außerhalb des Staging-Baums und wird nur vom Worker verwaltet. Eine harte Prozessbeendigung überspringt dessen finally und Finalizer. Der Parent kennt den Runtime-Pfad nicht; sein späterer Sweep bereinigt ausschließlich bestimmte alte Log- und Argdateien unter mutants.

**Fehlerszenario.** Ein unterbrochener Lauf erreicht die fünfsekündige Shutdown-Frist, während ein Worker mit angelegtem Runtime-Verzeichnis noch lebt. Der Parent beendet ihn tatsächlich hart, bevor runtime_context.cleanup ausgeführt wird. Das Verzeichnis mutmut-win-worker-runtime-* und seine bereits erzeugten Inhalte können zurückbleiben und sich bei wiederholten harten Abbrüchen ansammeln. Ctrl-C allein garantiert diesen Fall nicht: Rechtzeitige reguläre Bereinigung entfernt das Verzeichnis. Cache-, Argument- und Reportinhalte hängen vom Lauf ab; PYTHONDONTWRITEBYTECODE=1 kann den angelegten Python-Cache leer halten.

**Wörtlicher Beleg:**

```python
    runtime_context = tempfile.TemporaryDirectory(
        prefix="mutmut-win-worker-runtime-",
        ignore_cleanup_errors=True,
    )
    runtime_dir = Path(runtime_context.name)
```

**Fixskizze.** Einen vom Parent verwalteten Runtime-Root je Run verwenden und nach dem Reaping bereinigen. Für einen harten Parent-Abbruch eine spätere Bereinigung anhand verifizierter Run-Identitäten vorsehen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Wird ein Worker mit bereits angelegtem Task-Runtime-Verzeichnis tatsächlich hart beendet, beispielsweise nach Ablauf der Shutdown-Grace eines unterbrochenen Laufs, bleibt dieses Verzeichnis einschließlich seiner bereits erzeugten Inhalte zurück. Ein Ctrl-C allein garantiert den Leak nicht; eine rechtzeitige reguläre Abwicklung durch den Worker bereinigt ihn. Wiederholte harte Abbrüche können solche Verzeichnisse akkumulieren.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Wird ein aktiver Worker nach Ablauf der Shutdown-Frist tatsächlich hart beendet, bevor runtime_context.cleanup() ausgeführt wurde, kann sein mutmut-win-worker-runtime-* im temporären Verzeichnis zurückbleiben. Weitere Läufe bereinigen solche Verzeichnisse nicht. Die Cache-Unterverzeichnisse werden ausdrücklich angelegt; ihr Inhalt sowie Args und Reports hängen vom Lauf ab. Insbesondere verhindert PYTHONDONTWRITEBYTECODE=1 gewöhnliche Python-Bytecode-Schreibzugriffe, sodass der Python-Cache auch leer bleiben kann.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-05"></a>

#### EDGE-05: Endlicher Timeout-Multiplikator kann unbrauchbare unendliche Budgets erzeugen

**low · correctness · Konfidenz hoch** — `lens:boundaries` — [src/mutmut_win/orchestrator.py:1587](C:/claude_codex/mutmut-win-astra/src/mutmut_win/orchestrator.py:1587)

**Mechanismus.** Die Konfiguration verbietet einen unmittelbar unendlichen Multiplikator, prüft aber nicht das Multiplikationsergebnis. Weder model_copy noch die spätere MutationTask-Validierung verwerfen das so entstandene unendliche Budget. Der Windows-Wait versucht int(timeout * 1000) und wirft OverflowError. worker_main meldet dies als Worker-Recovery mit exit_code=35; suspicious bezeichnet diesen Infrastrukturfehler korrekt, ersetzt aber die angeforderte Testbewertung.

**Fehlerszenario.** Die zulässige Einstellung timeout_multiplier=1e308 und ein erfolgreicher Clean Run von mindestens zwei Sekunden lassen das volle Suitebudget bei normaler nicht autoritativer Testzuordnung zu Infinity überlaufen. Betroffene Mutanten erhalten suspicious mit ausgewiesener OverflowError-Diagnose. Es entstehen dadurch keine fälschlich bestätigten killed- oder survived-Ergebnisse.

**Wörtlicher Beleg:**

```python
timeout = max(_FALLBACK_TIMEOUT, clean_wall_seconds * multiplier)
...
task.model_copy(update={"estimated_time": estimated, "timeout_seconds": timeout})
```

**Fixskizze.** Berechnete Budgets auf Endlichkeit und unterstützte Wait-Darstellung prüfen; vor Dispatch als Konfigurationsfehler ablehnen oder begrenzte Wait-Abschnitte verwenden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Ein zulässiger sehr großer endlicher Timeout-Multiplikator kann berechnete Budgets zu Infinity überlaufen lassen. Dadurch scheitert das Windows-Warten und betroffene Mutanten werden ohne abgeschlossene Testbewertung als suspicious mit OverflowError-Diagnose erfasst. suspicious kennzeichnet dabei den tatsächlich entstandenen Infrastrukturfehler; es handelt sich nicht um fälschlich bestätigte killed- oder survived-Ergebnisse.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Ein zulässiger endlicher Timeout-Multiplikator kann bei der Budgetberechnung überlaufen und unter Windows Testbewertungen durch suspicious-Ergebnisse mit ausgewiesenem Worker-recovery/OverflowError ersetzen. suspicious bezeichnet dabei zutreffend einen technischen Fehler; der Defekt ist die fehlende frühzeitige Zurückweisung des unbrauchbaren Budgets.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-contracts-contract-05"></a>

#### CONTRACT-05: Fehlgeschlagene Boundary-Prüfung lässt neu erzeugten Pool-Job offen

**low · resource-leak · Konfidenz hoch** — `lens:contracts` — [src/mutmut_win/orchestrator.py:940](C:/claude_codex/mutmut-win-astra/src/mutmut_win/orchestrator.py:940)

**Mechanismus.** _get_executor erzeugt beim direkten API-Aufruf ohne injizierten Executor einen SpawnPoolExecutor mit Windows-Jobhandle. Die anschließende Boundary-Prüfung liegt vor dem try/finally mit shutdown. Bei vorheriger Config-Drift kann schon die Argumentauswertung self._runner.pytest_boundary_data werfen; bei späterer Änderung kann configure_pytest_boundary selbst scheitern. Der äußere Fehlerpfad aktualisiert den Laufstatus, schließt das Jobhandle aber nicht. Für dieses ganzzahlige Handle existiert kein Finalizer.

**Fehlerszenario.** Ein API-Lauf hat noch Mutationstasks und passiert die vorgelagerten Prüfungen. Danach ersetzt ein anderer Prozess eine gebundene Konfigurationsdatei, sodass die erneute Prüfung nach Executor-Erzeugung korrekt ablehnt. Der noch vor executor.start entstandene Jobhandle bleibt bis zum Hostende offen. Mehrere Lecks erfordern mehrere Versuche, die jeweils bis zur Erzeugung gelangen und erst danach scheitern; bloßes Wiederholen mit weiterhin ungültiger Konfiguration wird gegebenenfalls früher abgewiesen. Verwaiste Worker oder dauerhaft verlorene Queues sind dadurch nicht belegt.

**Wörtlicher Beleg:**

```python
        executor = self._get_executor()
        configure_boundary = getattr(executor, "configure_pytest_boundary", None)
        if callable(configure_boundary):
            configure_boundary(self._runner.pytest_boundary_data)
        interrupted = False
        try:
            executor.start(tasks_with_timeouts)
```

**Fixskizze.** Cleanup-Bereich direkt nach Executor-Erzeugung beginnen und Boundary-Konfiguration darin ausführen; CLI bei Bedarf erzeugen lassen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Scheitert nach erfolgreicher Executor-Erzeugung der Boundary-Export oder configure_pytest_boundary() in orchestrator.py:940, bleibt der Windows-Jobhandle des intern erzeugten Executors bis zum Prozessende offen. Wiederholte API-Läufe können jeweils einen weiteren Handle verlieren, sofern sie erneut diesen Abschnitt erreichen. Der Befund belegt ein Jobhandle-Leck, keine laufenden verwaisten Worker und kein dauerhaftes Queue-Leck.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Beim direkten API-Lauf ohne injizierten Executor bleibt ein neu erzeugtes Windows-Jobhandle offen, wenn die erneute Boundary-Prüfung auf orchestrator.py:940 fehlschlägt; das kann schon bei der Auswertung von pytest_boundary_data geschehen. Erreichbar ist dies bei Config-Drift nach der letzten vorgelagerten Prüfung und vor beziehungsweise während dieser Validierung. Mehrere verlorene Handles erfordern mehrere Versuche, die jeweils bis zur Executor-Erzeugung gelangen und erst anschließend an dieser Validierung scheitern. Bloßes Wiederholen mit derselben weiterhin ungültigen Boundary wird bereits früher abgewiesen und erzeugt daher nicht zwingend weitere Handles.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

### Laufsteuerung, Datenhaltung und Ergebniswahrheit

<a id="mod-worker-work-01"></a>

#### WORK-01: Fehlgeschlagene Proof-Publikation wird als getöteter Mutant gespeichert

**high · error-handling · Konfidenz hoch** — `mod:worker` — [src/mutmut_win/process/worker.py:478](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py:478)

**Mechanismus.** Der generierte pytest-Hook lässt Fehler aus atomic_write_bytes entweichen. Der interne pytest-Fehler erzeugt Exitcode 3; der Worker korrigiert einen fehlenden Proof jedoch nur bei Exitcode 0 und meldet 3 ohne fatal-Markierung zurück. constants.py:233 klassifiziert diesen Code als killed; orchestrator.py:2142–2172 persistiert das Ergebnis.

**Fehlerszenario.** Nach erfolgreichem Clean-Lauf und Worker-Setup besteht ein ansonsten überlebender Mutant einen Test. Die erste Proof-Publikation scheitert anschließend an einem isolierten Dateizugriffsfehler; die begrenzten Wiederholungen enden vor dem Task-Timeout. Bleiben Worker-Abschluss, Staging und Ergebnisdatenbank funktionsfähig, wird der pytest-interne Exit 3 als Kill persistiert und erhöht den Score. Ein voller Datenträger ist nur dann ein geeignetes Beispiel, wenn die Ergebnisablage weiter beschreibbar ist, etwa bei einem separaten TEMP-Laufwerk.

**Wörtlicher Beleg:**

```python
    if marker_path and proof:
        atomic_write_bytes(Path(marker_path), proof.encode("utf-8"))
        _proof_published = True
...
        phase_executed = consume_pytest_phase_guard(phase_marker_path, phase_marker_token)
        if exit_code == 0 and not phase_executed:
            exit_code = 35
```

**Fixskizze.** Proof-Publikationsfehler dediziert übertragen und als fatal behandeln; kein killed persistieren. Fehler nach bestandenem Test gezielt injizieren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Scheitert die erste Proof-Publikation nach einem ausgeführten Testaufruf im pytest-Kindprozess und bleiben Worker-Abschluss sowie Ergebnispersistenz funktionsfähig, wird dessen interner Fehler mit Exit 3 als killed gespeichert. Für das Beispiel eines vollen Datenträgers muss insbesondere die Ergebnisablage weiterhin beschreibbar sein, etwa bei einem separaten TEMP-Laufwerk.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Scheitert die erste Proof-Veröffentlichung im pytest-Kindprozess nach erfolgreichem Setup vor Ablauf des Task-Timeouts und bleiben Ergebnisdatenbank sowie Staging funktionsfähig, kann der dadurch ausgelöste pytest-Exit 3 als regulärer Kill persistiert werden. Ein sonst überlebender Mutant erhöht dadurch fälschlich den Score.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am Zielcommit 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmen beide Codezitate wörtlich: worker.py:477–479 und :1233–1235. Der generierte pytest_runtest_logreport-Hook lässt Fehler von atomic_write_bytes ungefangen entweichen. Die atomare Schreibfunktion propagiert Schreib-/fsync-Fehler sowie nach begrenzten Wiederholungen anhaltende Replace-Fehler (atomic_file.py:243–250, :384, :434–467). Der daraus entstehende pytest-interne Fehler mit Exit 3 gelangt über proc.wait() zum Worker; fehlender Proof korrigiert ausschließlich Exit 0. consume_pytest_phase_guard unterdrückt Lesefehler (:863–871), und TaskCompleted wird ohne fatal gesetzt (:1274–1282; models.py:91–92: default=False). constants.py:233 ordnet Exit 3 tatsächlich killed zu; orchestrator.py:2142–2178 erhöht den Zähler und persistiert diesen Status. Gegenprüfungen widerlegen den Befund nicht: Die fatale Guard-Publikationsbehandlung (:780–787) schützt die vorherige Installation der Plugin-Datei, nicht die spätere Proof-Publikation im Kindprozess. Das Runtime-Verzeichnis entsteht separat über TemporaryDirectory (:1032–1036), der Proof liegt darin (:1114–1117, :853–856). Ein späterer lokaler Dateizugriffsfehler kann daher auftreten, obwohl Clean-Lauf und Vorbereitung erfolgreich waren. Testabdeckung: test_process_worker.py:217–241 prüft ausschließlich die Plugin-Installation mittels ensure_atomic_bytes; test_surface_hardening_220.py:745–768 prüft fehlenden Proof bei Exit 0. test_runner_sidecar_safety.py:297–336 erwartet ausdrücklich eine aus dem Proof-Hook entweichende Ausnahme, prüft aber deren spätere Ergebniszuordnung nicht. Kein gezielter Test der vollständigen Fehlerkette gefunden. Ausschließlich statisch geprüft; keine Tests oder Reproduktionen ausgeführt.

**Erreichbarkeit:** Am bestätigten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b vorhanden. Die Zitate stimmen wörtlich, stammen aber aus zwei getrennten Stellen: worker.py:477–479 und :1233–1235. Der Hook fängt Veröffentlichungsfehler nicht ab. atomic_file.py:457–466 wiederholt AtomicReplaceError begrenzt und wirft ihn anschließend weiter; Schreibfehler aus :373–384 können unmittelbar entweichen. Aktiver Gegenbeweis: Die fatale Behandlung in worker.py:779–787 schützt ausschließlich die vorherige Installation der Plugin-Datei mittels ensure_atomic_bytes. Sie schützt nicht atomic_write_bytes im späteren pytest-Hook. Dessen Ausnahme entsteht im Kindprozess; der Worker erhält über proc.wait() lediglich dessen Exitcode (:1197). Bei pytest-Exit 3 greift die Proof-Korrektur ausdrücklich nicht. TaskCompleted wird ohne fatal erzeugt (:1274–1282); models.py:91–92 setzt dafür False. executor.py:335–341 bricht nur bei fatal ab; constants.py:233 ordnet 3 tatsächlich killed zu, orchestrator.py:2150 und :2168–2181 zählen und persistieren dieses Ergebnis. Erreichbar ist insbesondere ein ansonsten überlebender Mutant mit einem einzigen bestandenen Test, dessen erste Proof-Veröffentlichung nach erfolgreichem Worker-Setup an einem isolierten Dateizugriffsfehler scheitert. Die begrenzten Wiederholungen müssen vor dem Task-Timeout enden. Clean-Lauf und Worker benutzen getrennte Laufzeitverzeichnisse; die spätere Staging-Prüfung erfasst gemäß stats.py:663–680 nur mutants/. Ein voller Datenträger ist dagegen nur dann ein tragfähiges Persistenzbeispiel, wenn die Ergebnisdatenbank weiterhin beschreibbar bleibt, etwa bei separatem Temp-Laufwerk. Testabdeckung: test_process_worker.py:217–241 prüft den vorgelagerten ensure_atomic_bytes-Fehler, nicht den Proof-Hook. test_runner_sidecar_safety.py:237–294 prüft erfolgreiche einmalige Veröffentlichung; :297–336 erwartet eine entweichende Hook-Ausnahme bei Parent-Austausch, verfolgt aber keine Ergebniszuordnung. test_atomic_transient_retry.py:69–80 bestätigt erschöpfte Wiederholungen. test_surface_hardening_220.py:745–768 prüft ausschließlich Exit 0 ohne Proof. Kein passender Test für Proof-Publikationsfehler → Exit 3 → gespeicherten Kill gefunden. Ausschließlich statische Prüfung; keine Tests oder Reproduktionen ausgeführt.

<a id="mod-orchestrator-orch-02"></a>

#### ORCH-02: Ctrl-C während abschließender Basisprüfung hinterlässt laufenden Run

**medium · error-handling · Konfidenz hoch** — `mod:orchestrator` — [src/mutmut_win/orchestrator.py:438](C:/claude_codex/mutmut-win-astra/src/mutmut_win/orchestrator.py:438)

**Mechanismus.** KeyboardInterrupt/BaseException-Behandlung umfasst nur _run_pipeline. Abschließende doppelte Fingerprint-Prüfung liegt außerhalb und fängt nur OrchestratorError. Ctrl-C überspringt Wiederverwendungswiderruf und interrupted-Persistenz; äußere Locks werden freigegeben.

**Fehlerszenario.** Workerergebnisse sind gespeichert. Ctrl-C während abschließendem _stable_run_basis_evidence lässt Datenbankstatus running und historische tests_fingerprint bestehen. Nächster Lauf repariert als aborted, nicht interrupted. Recovery verhindert unsicheren Folgereuse; kein Score-/Export-Bypass behauptet.

**Wörtlicher Beleg:**

```python
        if terminal_status == "completed":
            execution_basis_deauthorized = False
            try:
                live_basis = self._stable_run_basis_evidence()
            except OrchestratorError:
                invalidate_cached_reuse_for_run(self._db_path, self._active_run_id)
                finish_run(self._db_path, self._active_run_id, "failed")
                raise
```

**Fixskizze.** Abbruchbehandlung über gesamte aktive Run-Lebensdauer inkl. Abschlussprüfung/Finalisierung legen; erst Reuse widerrufen, dann interrupted persistieren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-orchestrator-orch-03"></a>

#### ORCH-03: Umgeleitete Textausgabe kann Lauf vor Mutantenerzeugung abbrechen

**medium · api-contract · Konfidenz hoch** — `mod:orchestrator` — [src/mutmut_win/orchestrator.py:587](C:/claude_codex/mutmut-win-astra/src/mutmut_win/orchestrator.py:587)

**Mechanismus.** Die Pipeline greift ungeschützt auf sys.stdout.line_buffering und bei False auf sys.stdout.reconfigure zu. io.StringIO besitzt unter CPython 3.14.7 line_buffering=False, aber kein reconfigure; der konkrete Fehler liegt daher beim zweiten Zugriff. Die zuvor aufgerufene defensive Encoding-Hilfsfunktion unterdrückt nur ihren eigenen Attributfehler und ersetzt den Stream nicht.

**Fehlerszenario.** Ein ansonsten gültiger API-Lauf innerhalb von contextlib.redirect_stdout(io.StringIO()) scheitert nach dem Vorlauf vor _generate_mutants() mit AttributeError in Zeile 587. Der Lauf wird bei erfolgreicher Fehlerpersistierung als failed erfasst. Andere alternative Ausgabestreams können schon beim line_buffering-Zugriff in Zeile 586 scheitern.

**Wörtlicher Beleg:**

```python
        if not sys.stdout.line_buffering:
            sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
        _ensure_tolerant_stdout()
```

**Fixskizze.** line_buffering defensiv über getattr und reconfigure nur aufrufbar verwenden; regulären umgeleiteten Textstream abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei contextlib.redirect_stdout(io.StringIO()) scheitert MutationOrchestrator.run nach erfolgreichem Vorlauf vor der Mutantenerzeugung an sys.stdout.reconfigure(line_buffering=True) in Zeile 587. StringIO besitzt unter CPython 3.14.7 line_buffering=False, aber kein reconfigure. Der bereits vorgelagerte Aufruf von _ensure_tolerant_stdout verhindert diesen späteren AttributeError nicht.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein ansonsten gültiger API-Lauf innerhalb von contextlib.redirect_stdout(io.StringIO()) scheitert unter Windows/CPython 3.14.7 vor der Mutantenerzeugung in orchestrator.py:587 mit AttributeError, weil StringIO zwar line_buffering=False, jedoch kein reconfigure besitzt. Die bereits vorgelagert aufgerufene defensive Encoding-Hilfsfunktion verhindert diesen Fehler nicht. Andere alternative Streams können schon beim Attributzugriff in Zeile 586 scheitern.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-db-db-02"></a>

#### DB-02: Legacy-Fallback kombiniert Runentscheidung und Ergebnisse aus verschiedenen Snapshots

**medium · race · Konfidenz hoch** — `mod:db` — [src/mutmut_win/db.py:1528](C:/claude_codex/mutmut-win-astra/src/mutmut_win/db.py:1528)

**Mechanismus.** load_current_run beendet Lesetransaktion vor zweiter Verbindung load_results im None-Fallback. Dazwischen kann erster moderner Run historische Ergebnisse verändern. current=None wird mit moderner/geerbter Mischpopulation zurückgegeben; Dateiidentität bleibt gleich.

**Fehlerszenario.** Legacy-Cache m1/m2; Browser liest keinen Run, parallel erster moderner Teilrun schreibt m1. Zweite Abfrage liefert neues m1 plus altes m2 ohne Runidentität/Teilrunhinweis. Browser-Fallback :417–419 nutzt dies bei fehlenden Metadaten; CLI hat ähnlichen Pfad. Export ist durch Locks und Legacy-Ablehnung geschützt, kein CI-PASS-Bypass.

**Wörtlicher Beleg:**

```python
    current = load_current_run(path)
    if current is None:
        return None, load_results(path)
```

**Fixskizze.** Runentscheidung und Legacy-Abfrage in einer SQLite-Lesetransaktion; CLI-Duplikat konsistent umstellen; deterministisches Interleaving abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-runner-runner-01"></a>

#### RUNNER-01: Erlaubte Verbosity-Optionen verfälschen gesammelte Testliste

**medium · api-contract · Konfidenz hoch** — `mod:runner` — [src/mutmut_win/runner.py:446](C:/claude_codex/mutmut-win-astra/src/mutmut_win/runner.py:446)

**Mechanismus.** collect_tests stellt -q vor konfigurierte pytest-Argumente und parst stdout-Zeilen mit '::', sofern sie nach strip() weder mit '=' noch mit 'WARNING' beginnen. Weiteres -q oder -v kann die Ausgabe in Dateizählung beziehungsweise Baumdarstellung ändern und so bei gewöhnlichen Testnamen eine leere Node-ID-Liste liefern. Fremder Text mit '::' kann umgekehrt als Node-ID eingehen.

**Fehlerszenario.** pytest_add_cli_args=['-q'] oder addopts=-q bei vorhandenen Tests und ansonsten wiederverwendbarem, nichtleerem Stats-Cache: Collection gelingt, der Textparser liefert jedoch []. Der Vergleich behandelt gecachte Tests als entfernt und erhebt die Stats bei jedem unveränderten Folgelauf erneut. Ein unmittelbar falscher Mutationsscore ist daraus nicht belegt.

**Wörtlicher Beleg:**

```python
cmd = [*pytest_cmd, "--collect-only", "-q", "--no-header"]
        cmd.extend(self._configured_pytest_args())
...
            if "::" in line and not line.startswith("=") and not line.startswith("WARNING"):
                tests.append(line)
        return sorted(tests)
```

**Fixskizze.** item.nodeid strukturiert durch Collection-Hook in private Datei publizieren statt Terminaltext parsen; Verbosity/Farbe/'::'-Rauschen abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Erlaubte zusätzliche Verbosity-Optionen können collect_tests() trotz vorhandener Tests eine leere oder verunreinigte Node-ID-Liste liefern lassen. Bei ansonsten wiederverwendbarem, nichtleerem Stats-Cache verursacht dies auf jedem unveränderten Folgelauf erneut eine vollständige Stats-Erhebung.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Erlaubte Verbosity-Optionen können die textbasierte Collection verfälschen. Bei sonst unveränderten Eingaben, nichtleerem wiederverwendbarem Stats-Cache und erneut erreichtem Stats-Schritt bewirkt eine dadurch leere Testliste wiederholte vollständige Stats-Sammlungen. Fremde stdout-Zeilen mit '::' werden akzeptiert, sofern sie nach strip() weder mit '=' noch mit 'WARNING' beginnen. Nachgewiesene Folge ist unnötige Ausführung; falsche Mutantenbewertungen sind daraus nicht belegt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-runner-runner-02"></a>

#### RUNNER-02: Benutzeroptionen können notwendigen Forced-Fail-Nachweis unterdrücken

**medium · correctness · Konfidenz hoch** — `mod:runner` — [src/mutmut_win/runner.py:630](C:/claude_codex/mutmut-win-astra/src/mutmut_win/runner.py:630)

**Mechanismus.** --tb=line und -rfE stehen vor frei konfigurierten Args und können überschrieben werden, Nachweis sucht weiter Exceptionnamen im Text.

**Fehlerszenario.** pytest_add_cli_args=['--tb=no','-rN']; ein gewöhnlicher Test erreicht ein Trampolin, das im Forced-Fail-Modus tatsächlich MutmutProgrammaticFailException auslöst. Die späteren pytest-Optionen unterdrücken Traceback und Fehlerkurzbericht, sodass der Fehlerstatus ohne Marker zurückkommt. Der Runner setzt Attribution=False und der Orchestrator bricht fälschlich mit ForcedFailError ab; das Gate wird dadurch nicht umgangen.

**Wörtlicher Beleg:**

```python
cmd = [*self._guarded_pytest_cmd(), "--tb=line", "-q", "-x", "-rfE"]
        cmd.extend(self._configured_pytest_args())
...
        self._forced_fail_attributed = exit_code != 0 and FORCED_FAIL_MARKER in (
            self._last_diagnostic_output or ""
        )
```

**Fixskizze.** Kurzfristig zwingende Darstellungsoptionen nach Userargs vor Targets setzen; langfristig Exceptiontyp strukturiert nachweisen statt Tailtext.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Die zulässige Konfiguration pytest_add_cli_args=['--tb=no', '-rN'] kann einen korrekt ausgelösten Forced-Fail unsichtbar machen und dadurch den Mutationslauf fälschlich mit ForcedFailError abbrechen. Das Gate wird nicht umgangen; es entsteht eine falsche Zurückweisung.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-runner-runner-03"></a>

#### RUNNER-03: Exceptionname im Testnamen genügt als falscher Trampoline-Nachweis

**medium · correctness · Konfidenz hoch** — `mod:runner` — [src/mutmut_win/runner.py:647](C:/claude_codex/mutmut-win-astra/src/mutmut_win/runner.py:647)

**Mechanismus.** Attribution ist Teilstringtest im gesamten Diagnostiktail; unterscheidet Exceptiontyp nicht von Node-ID/Assertion/Ausgabe. Phasenguard beweist nur Testaufruf.

**Fehlerszenario.** Suite importiert mutierte Funktion nie. test_MutmutProgrammaticFailException prüft env MUTANT_UNDER_TEST!='fail'. Clean/Stats bestehen, Forced-Fail wirft nur AssertionError. Summary enthält Marker im Testnamen; AttributionTrue, Gate akzeptiert ohne Trampoline.

**Wörtlicher Beleg:**

```python
self._forced_fail_attributed = exit_code != 0 and FORCED_FAIL_MARKER in (
            self._last_diagnostic_output or ""
        )
```

**Fixskizze.** Privaten phasengebundenen Nachweis nur für tatsächlich beobachteten MutmutProgrammaticFailException publizieren; Node-ID-Marker/AssertionError regressiv prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-contracts-contract-03"></a>

#### CONTRACT-03: Defekte Checker-Reports verlassen trotz gültigem JSON den Domain-Fehlerkanal

**medium · error-handling · Konfidenz hoch** — `lens:contracts` — [src/mutmut_win/type_checking.py:422](C:/claude_codex/mutmut-win-astra/src/mutmut_win/type_checking.py:422)

**Mechanismus.** run_type_checker prüft Exitcode und JSON-Syntax, ruft die Reportparser danach aber außerhalb des JSONDecodeError-Handlers auf. parse_pyright_report prüft nur den äußeren Schlüssel generalDiagnostics; eine Fehlerdiagnose mit fehlenden Pflichtfeldern verursacht KeyError statt des zugesagten TypeCheckCommandError. Die Aufrufer stellen das Arbeitsverzeichnis wieder her und markieren den Lauf als fehlgeschlagen, werfen dieselbe Ausnahme aber weiter. Der CLI-Handler für MutmutWinError erzeugt deshalb kein JSON-Fehlerobjekt. Vergleichbare direkte Pflichtfeldzugriffe bestehen für Pyrefly, mypy und ty.

**Fehlerszenario.** Ein defekter oder inkompatibler konfigurierter Checker beziehungsweise Wrapper liefert bei akzeptiertem Exitcode den syntaktisch gültigen Report {"generalDiagnostics":[{"severity":"error"}]}. Generische Befehle sind zulässig und verwenden den Pyright-Parser als Fallback; diagnostic["file"] wirft KeyError. Der Lauf scheitert sichtbar, aber der Domain-Fehlerkanal und die strukturierte CLI-Fehlerausgabe fehlen. Eine solche Ausgabe eines korrekt arbeitenden Standardcheckers und ein fälschlich erfolgreicher Abschluss sind nicht belegt.

**Wörtlicher Beleg:**

```python
        TypeCheckingError(
            file_path=Path(diagnostic["file"]),
            line_number=diagnostic["range"]["start"]["line"] + 1,
            error_description=diagnostic["message"],
        )
```

**Fixskizze.** Report-/Diagnoseschemata validieren und Schemafehler samt Ursache in TypeCheckCommandError überführen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="nondet-timing-assumptions-time-03"></a>

#### TIME-03: Windows-Integrationstest setzt nicht abgesicherte CPU-Zuteilung für IL-Erkennung voraus

**low · test-flakiness · Konfidenz mittel** — `nondet:timing-assumptions` — [tests/integration/test_il_detection.py:131](C:/claude_codex/mutmut-win-astra/tests/integration/test_il_detection.py:131)

**Mechanismus.** Der Integrationstest verlangt nach einem festen Beobachtungsfenster ein Infinite-Loop-Verdikt. Die Klassifikation erfordert weiterhin mindestens 70 Prozent gemessene mittlere Prozess-CPU. Warmup, Affinität und HIGH_PRIORITY_CLASS reduzieren Störungen, reservieren aber keine CPU-Zeit und prüfen die tatsächliche Zuteilung nicht; ihre Einstellfehler werden unterdrückt.

**Fehlerszenario.** Zwei parallele Windows-Testläufe in getrennten Arbeitsverzeichnissen wählen bei gleichem erlaubtem CPU-Satz denselben letzten logischen Prozessor und dieselbe hohe Priorität. Wenn die konkurrierenden Busy-Loops den gemessenen Mittelwert eines Laufs unter 70 Prozent halten, liefert der Detektor vertragsgemäß timeout, während der Integrationstest dies als Detektorfehler beanstandet. Ein tatsächlicher aktueller CI-Ausfall oder Produktfehler wurde nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
    assert verdict == "killed_by_infinite_loop", (
        f"Real busy-loop subprocess wrongly classified as {verdict!r}. "
        f"This is the canonical Bug #5 / Issue #71 case — if it fails the IL "
        f"detector is broken."
    )
```

**Fixskizze.** Tatsächlich gemessene CPU-Samples zurückgeben und Vorbedingung des erwarteten Verdicts prüfen; Lastbedingungen gesondert behandeln, Grenzwerte mit synthetischen Samples testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low. Der Windows-Integrationstest kann bei CPU-Konkurrenz, die den gemessenen Prozess-CPU-Mittelwert trotz der vorhandenen Stabilisierung unter 70 Prozent hält, einen korrekten Timeout fälschlich als Detektorfehler beanstanden. Dies ist eine verbleibende bedingte Flakiness-Möglichkeit, kein nachgewiesener aktueller CI-Ausfall oder Produktfehler.
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: low. Der Windows-Integrationstest verlangt nach festem Beobachtungsfenster ein IL-Verdikt, ohne die dafür erforderliche gemessene CPU-Auslastung abzusichern. Bei konkurrierender Last gleicher hoher Priorität auf dem gewählten Prozessor kann er ein vertragsgemäßes timeout fälschlich als Detektordefekt melden.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-db-db-01"></a>

#### DB-01: Implementierte Altschema-Migration hinterlässt falschen Default für neue Runs

**low · correctness · Konfidenz hoch** — `mod:db` — [src/mutmut_win/db.py:889](C:/claude_codex/mutmut-win-astra/src/mutmut_win/db.py:889)

**Mechanismus.** Der Migrationspfad für eine vorhandene mutation_run-Tabelle ohne plan_finalized ergänzt die Spalte mit dauerhaftem DEFAULT 1. begin_run lässt diese Spalte beim INSERT aus; set_run_plan lehnt den dadurch bereits als finalisiert markierten neuen Run ab. CREATE TABLE IF NOT EXISTS ersetzt den bestehenden Default nicht.

**Fehlerszenario.** Eine Datenbank mit mutation_run, aber ohne plan_finalized, wird über den ausdrücklich implementierten Migrationspfad geöffnet. Nach der Migration scheitert ein regulärer Run auf dieser weiterhin verwendeten Datenbank bei der Planfestlegung. Die geprüften veröffentlichten Vorgänger erzeugen dieses Schema nicht: v2.20.0 hat keine mutation_run-Tabelle; v2.21.0 bis v2.21.3 haben die Spalte bereits mit DEFAULT 0. Tabelle und Spalte wurden laut lokaler Historie gemeinsam eingeführt. Ein normaler Upgrade-Ausfall dieser Releases ist deshalb nicht belegt; neue Datenbanken und start_run mit explizitem Wert sind nicht betroffen.

**Wörtlicher Beleg:**

```python
    "ALTER TABLE mutation_run ADD COLUMN plan_finalized INTEGER NOT NULL DEFAULT 1"
...
            INSERT INTO mutation_run
                (run_id, status, started_at, basis_fingerprint, basis_config_json, is_full_run)
            VALUES (?, ?, ?, ?, ?, ?)
...
        if row is None or bool(row[0]):
            raise RunStateError(f"mutation run {run_id!r} already has a finalized plan")
```

**Fixskizze.** begin_run schreibt plan_finalized explizit 0; Migrationstest um neuen vollständigen Run auf migrierter DB ergänzen, historische Zeilen bleiben finalisiert.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Datenbanken mit bereits vorhandener mutation_run-Tabelle ohne plan_finalized behalten nach der Migration DEFAULT 1. Jeder reguläre Orchestrator-Lauf, der auf dieser unverändert weiterverwendeten Datenbank bis zur Planfestlegung gelangt, scheitert dort. Nicht betroffen sind neue Datenbanken, alte Caches ohne mutation_run-Tabelle sowie der separate start_run-Aufruf mit ausdrücklich gesetztem plan_finalized.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Der ausdrücklich implementierte Migrationspfad für eine vorhandene mutation_run-Tabelle ohne plan_finalized hinterlässt DEFAULT 1 und verhindert nachfolgende reguläre Runs auf dieser Datenbank. Dass ein veröffentlichtes Vorgängerrelease dieses Altschema tatsächlich erzeugt hat, ist anhand der lokalen Historie nicht nachgewiesen; die geprüften Release-Upgrades sind nicht betroffen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

### Mutationen und unterstützte Python-Semantik

<a id="mod-mutation-mut-01"></a>

#### MUT-01: Methodenaufrufe während Klassenerzeugung treffen auf ungebundene Trampoline-Referenzen

**high · phase-order · Konfidenz hoch** — `mod:mutation` — [src/mutmut_win/mutation.py:631](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:631)

**Mechanismus.** Die Wrapper laden Originalfunktion und Mutantentabelle aus Modulvariablen, die erst nach dem ClassDef gesetzt werden. Python kann Methoden jedoch bereits während der Klassenerzeugung aufrufen; __init__ wird nicht von der Instrumentierung ausgeschlossen.

**Fehlerszenario.** Ein undekoriertes Enum E mit A=1 und mutationsfähigem __init__(self, value): self.extra=value+1 ruft den instrumentierten Konstruktor bereits während der Member-Erzeugung auf. Die globale *_orig_ref ist noch nicht gebunden; der gültige Originalimport scheitert ohne aktiven Mutanten mit NameError. __init_subclass__ selbst wird ausdrücklich nicht instrumentiert. Ein entsprechendes Callback-Szenario benötigt deshalb einen indirekten frühen Aufruf einer anderen instrumentierten Methode der gerade entstehenden Klasse.

**Wörtlicher Beleg:**

```python
                result.append(cls.with_changes(body=cls.body.with_changes(body=mutated_body)))
                result.extend(class_lookup_nodes)
...
        return cst.Name(f"{mangled_name}_orig_ref")
...
            cst.Arg(cst.Name(f"{mangled_name}_mutants")),
```

**Fixskizze.** Referenzen vor möglichen Erzeugungsaufrufen verfügbar machen, Enum-Member/__class__-Zellen bewahren oder betroffene Konstruktionen konservativ skippen; entsprechende Callbacks testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. Instrumentierte Methoden können vor Abschluss ihrer Klassendefinition auf noch ungebundene globale Trampolinreferenzen zugreifen. Konkret betroffen ist ein mutationsfähiger Enum.__init__, der während der Member-Erzeugung ausgeführt wird: Der ansonsten gültige Import scheitert bereits ohne aktiven Mutanten mit NameError. __init_subclass__ wird selbst nicht instrumentiert; entsprechende Callback-Szenarien erfordern dessen frühen Aufruf einer anderen instrumentierten Methode der entstehenden Klasse.
- Erreichbarkeit: angenommen, Konfidenz hoch. Instrumentierte Methoden einer gerade entstehenden Klasse können vor Initialisierung ihrer Modulreferenzen aufgerufen werden. Konkret bricht ein undekoriertes Enum mit A=1 und mutierbarem __init__(self, value) während der Member-Erzeugung mit NameError ab, auch ohne aktiven Mutanten. __init_subclass__ selbst ist ausgeschlossen; entsprechende Callback-Szenarien benötigen einen indirekten Aufruf einer bereits instrumentierten Methode der gerade entstehenden Klasse.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Ziel-HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b bestätigt. Die Zitate stimmen wörtlich: mutation.py:631–632 emittiert die vollständige Klasse vor class_lookup_nodes; :973 liefert die globale *_orig_ref-Referenz; :981 liest die globale Mutantentabelle. Die Referenzzuweisung wird erst in :797–808 als nachgelagerter Lookup erzeugt. __init__ ist in der Ausschlussmenge :28–37 nicht enthalten; auch die weiteren Ausschlussprüfungen enthalten keinen Enum-Schutz. Ein gewöhnliches Enum mit A=1 und __init__(self, value): self.extra=value+1 erhält deshalb einen Wrapper. Bei der Member-Erzeugung ruft Enum diesen Konstruktor vor Abschluss der Klassendefinition auf. Bereits die Argumentauswertung des Trampolinaufrufs scheitert an der noch nicht gebundenen *_orig_ref, bevor trampoline.py:141–144 den Zustand ohne aktiven Mutanten behandeln könnte. Gegenbeweis zur pauschalen Callback-Erweiterung: __init_subclass__ selbst wird ausdrücklich ausgeschlossen; test_wrapper_codegen.py:40–52 prüft dies. Dieser Schutz verhindert jedoch keine Aufrufe anderer instrumentierter Methoden der gerade entstehenden Klasse durch einen solchen Hook. Die Enum-Tests in test_class_body_injection.py:36–57 prüfen Member-Unversehrtheit und describe() nach abgeschlossener Klassenerzeugung, keinen Enum-Konstruktor. Kein exakt passender Regressionstest gefunden. Nur statische Prüfung; keine Tests oder Reproduktionen ausgeführt.

**Erreichbarkeit:** HEAD entspricht 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b. Die Zitate stimmen wörtlich: Klassenanweisung und anschließende Lookup-Ausgabe stehen in mutation.py:631–632, der orig_ref-Zugriff in Zeile 973 und das mutants-Argument in Zeile 981. Die orig_ref-Zuweisung wird in 797–808 erzeugt und ebenfalls erst nach der Klasse ausgegeben. Der Enum-Fall ist erreichbar: __init__ fehlt in NEVER_MUTATE_FUNCTION_NAMES (28–37); eine undekorierte Enum-Klasse wird nicht ausgeschlossen. Bereits die Zahl 1 in value + 1 erzeugt einen echten Mutanten (node_mutation.py:35–46), sodass die Abbruchpfade für fehlende Mutationen hier nicht helfen. Standardmäßig sind Namensausschlüsse leer und die Beschränkung auf abgedeckte Zeilen deaktiviert (config.py:133–134, 213–214). Ein erlaubter reiner Sprachfaktencheck mit CPython 3.14.7 bestätigte: Beim Enum-Konstruktoraufruf für A=1 ist E noch nicht im Modul gebunden; der unveränderte Konstruktor liefert anschließend extra=2. Im erzeugten Wrapper scheitert deshalb bereits die Auswertung des orig_ref-Arguments vor Eintritt in den Trampoline-Helper. Dessen Originalpfad bei fehlendem aktivem Mutanten kann nicht schützen. Gegenbeweis zur pauschalen Callback-Aussage: __init_subclass__ selbst wird ausdrücklich übersprungen (mutation.py:35, 375–379). tests/unit/test_wrapper_codegen.py:40–52 prüft genau diesen Ausschluss, aber keinen Rückruf auf eine gerade entstehende Unterklassenmethode. Die Enum-Tests in tests/unit/test_class_body_injection.py:36–57 prüfen Mitglieder und einen erst nach vollständiger Klassenerzeugung aufgerufenen describe-Aufruf; sie decken keinen Enum-Konstruktor ab. Die gefundenen Enum-E2E-Fixtures haben ebenfalls keinen eigenen Konstruktor. Keine Tests oder Projektreproduktionen ausgeführt. High ist für den deterministischen Importabbruch bei regulären Enum-Konstruktoren vertretbar.

<a id="mod-mutation-mut-02"></a>

#### MUT-02: Private Keyword-only-Parameter werden mit falschem Schlüssel weitergereicht

**medium · correctness · Konfidenz hoch** — `mod:mutation` — [src/mutmut_win/mutation.py:955](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:955)

**Mechanismus.** Die Schlüssel des Keyword-Dicts stammen aus den rohen Parameternamen. Anders als Python-Identifier werden sie weder klassenprivat gemangelt noch nach NFKC normalisiert. Die Implementierung erwartet den kompilierten Namen, während der Stringschlüssel unverändert bleibt.

**Fehlerszenario.** Eine reguläre eingerückte Klasse C besitzt die Methode f(self, *, __value=1) mit dem Rumpf return __value+1. Ursprünglich liefert C().f() den Wert 2. Der generierte Wrapper reicht {'__value': 1} an die Implementierung weiter, deren kompilierter Parameter _C__value heißt; bereits der Clean-Aufruf scheitert mit TypeError. Entsprechend können NFKC-normalisierte Parameter-Identifier und ihre unverändert übernommenen Stringschlüssel auseinanderfallen.

**Wörtlicher Beleg:**

```python
    kwargs: list[cst.DictElement | cst.StarredDictElement] = [
        cst.DictElement(cst.SimpleString(f"'{p.name.value}'"), p.name)
        for p in function.params.kwonly_params
    ]
```

**Fixskizze.** Für Keywordschlüssel die tatsächlich kompilierten Parameternamen verwenden und dabei NFKC-Normalisierung sowie privates Klassen-Mangling berücksichtigen. Die zugehörigen Werte weiterhin als CST-Namensreferenzen erzeugen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei einer zur Mutation ausgewählten Methode einer mehrzeiligen Klasse, beispielsweise "class C:\n    def f(self, *, __value=1):\n        return __value + 1", verwendet der Wrapper den rohen Keywordschlüssel __value statt des kompilierten Parameternamens _C__value. Dadurch scheitert bereits C().f() im Clean-Pfad mit TypeError. Der zusätzliche NFKC-Fall wurde nicht separat zur Laufzeit verifiziert.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-mutation-mut-03"></a>

#### MUT-03: Generator-Lambdas verändern fälschlich Identität umgebender Funktion

**medium · correctness · Konfidenz hoch** — `mod:mutation` — [src/mutmut_win/mutation.py:1199](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:1199)

**Mechanismus.** IsGeneratorVisitor grenzt verschachtelte FunctionDef-Knoten ab, berücksichtigt aber den eigenen Gültigkeitsbereich einer Lambda-Funktion nicht. Ein yield innerhalb eines Lambdas markiert dadurch eine normale äußere Funktion als Generator; deren Wrapper erhält yield from.

**Fehlerszenario.** Eine ansonsten zur Mutation zugelassene normale Funktion f enthält maker=lambda: (yield 1) und gibt anschließend 2 zurück. Der öffentliche Wrapper wird fälschlich zur Generatorfunktion: f() liefert einen Generator statt 2; erst dessen Iteration versucht yield from 2 und löst TypeError aus. Eine entsprechende async-Funktion bleibt ausführbar, wird aber unbegründet von der Mutation ausgeschlossen.

**Wörtlicher Beleg:**

```python
    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool | None:  # noqa: N802
        # do not recurse into inner function definitions
        if self.original_function != node:
            return False
        return None

    # ARG002: libcst CSTVisitor requires the node parameter in visitor methods
    def visit_Yield(self, node: cst.Yield) -> bool | None:  # noqa: N802, ARG002
        self.is_generator = True
        return False
```

**Fixskizze.** Yield tatsächlichem Scope zuordnen, Lambda-Bodies ausnehmen, äußere Default-Ausdrücke korrekt beachten; beide Fälle testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Eine ansonsten zur Mutation zugelassene synchrone Funktion mit Generator-Lambda wird fälschlich als Generator instrumentiert. f() liefert dann ein Generatorobjekt statt 2; erst die Iteration löst beim Delegieren an 2 einen TypeError aus. Eine entsprechende Coroutine wird unbegründet von der Mutation ausgeschlossen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Bei einer zur Mutation ausgewählten normalen Funktion mit Generator-Lambda im Body wird der öffentliche Wrapper fälschlich zur Generatorfunktion. f() liefert dann einen Generator statt 2; erst dessen Iteration versucht 'yield from 2' und löst TypeError aus. Eine entsprechende async-Funktion bleibt ausführbar, wird jedoch unbegründet von der Mutation ausgeschlossen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-mutation-mut-04"></a>

#### MUT-04: Übersprungene innere Klasse entfernt Klassenstack des Elternknotens

**medium · api-contract · Konfidenz hoch** — `mod:mutation` — [src/mutmut_win/mutation.py:304](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:304)

**Mechanismus.** Der Klassenstack wird erst nach der Skip-Prüfung erweitert; on_leave poppt dagegen bei jedem ClassDef und nichtleerem Stack. LibCST ruft on_leave auch nach on_visit(False) auf. Eine übersprungene innere Klasse entfernt dadurch den Stackeintrag der äußeren Klasse; nachfolgende Methoden verlieren den qualifizierten Namen für ihre Ausschlussprüfung. Der relevante Callbackvertrag wurde durch zwei isolierte API-Faktenchecks bestätigt.

**Fehlerszenario.** Eine regulär eingerückte Klasse A enthält zuerst die innere Klasse Skip und anschließend die Methode m(self) mit return 1. Die Muster ^A\.Skip$ und ^A\.m$ sollen beide ausschließen. Skip wird vor dem Push übersprungen, beim Leave wird aber A gepoppt. Danach wird die Methode nur als m geprüft und trotz passendem qualifiziertem Ausschlussmuster mutiert.

**Wörtlicher Beleg:**

```python
        if self._skip_node_and_children(node):
            return False
...
        if isinstance(node, cst.ClassDef):
            self._class_stack.append(node.name.value)
...
        if isinstance(original_node, cst.ClassDef) and self._class_stack:
            self._class_stack.pop()
```

**Fixskizze.** Stack an tatsächlich betretene ClassDef-Identitäten binden oder qualifizierte Namen aus Parent-Metadaten; übersprungene innere Klasse vor Geschwistermethode testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Eine über do_not_mutate_patterns übersprungene innere Klasse leert vorzeitig den Klassenstack ihres Elternknotens. Nachfolgende direkte Methoden können dadurch trotz passendem qualifiziertem Ausschlussmuster mutiert werden. Der dafür maßgebliche LibCST-Vertrag wurde durch einen isolierten API-Faktencheck bestätigt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei einer regulär eingerückten äußeren Klasse A mit ausgeschlossener innerer Klasse Skip und anschließender Methode m(self): return 1 entfernt on_leave(Skip) den Stackeintrag von A. Dadurch greift ein Ausschlussmuster ^A\.m$ nicht mehr. Der hierfür entscheidende LibCST-Callbackvertrag wurde durch einen isolierten API-Faktencheck bestätigt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-mutation-mut-05"></a>

#### MUT-05: Block-Pragmas enden vorzeitig an Kommentaren und Mehrzeilenstring-Inhalten

**medium · api-contract · Konfidenz hoch** — `mod:mutation` — [src/mutmut_win/mutation.py:1087](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:1087)

**Mechanismus.** _pragma_block_range verwendet die Einrückung physischer, nichtleerer Zeilen. Ausgerückte Kommentare oder innere Zeilen eines Mehrzeilenstrings bilden keinen Python-Dedent, beenden aber den Scanner. Die Tokenisierung schützt lediglich die Pragma-Erkennung, nicht die Bestimmung der Blockgrenze.

**Fehlerszenario.** Gültiger Python-Code enthält 'def f(): # pragma: no mutate block', danach eine nicht eingerückte Kommentarzeile und schließlich das eingerückte 'return 1'. Der Scanner schützt nur die Kopfzeile; die Return-Zeile bleibt mutierbar. Entsprechend kann ein ausgerückter Inhalt eines mehrzeiligen Strings den Pragma-Bereich vorzeitig beenden. Das Ausschließen der Kopfzeile verhindert die weitere Traversierung der gewöhnlichen Funktion nicht.

**Wörtlicher Beleg:**

```python
    while cursor < len(lines):
        if lines[cursor].strip() == "":
            cursor += 1
            continue
        if _indent_width(lines[cursor]) <= base:
            break
        last_body = cursor
        cursor += 1
```

**Fixskizze.** Suitegrenze aus Tokens/CST-Position statt physischer Einrückung; Kommentare/Strings bilden keinen Dedent.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Block-Pragmas können an nichtleeren Kommentarzeilen oder Mehrzeilenstring-Inhaltszeilen mit Einrückung kleiner oder gleich der Kopfzeile vorzeitig enden. Dadurch bleiben nachfolgende, weiterhin zur Python-Suite gehörende Anweisungen entgegen dem Pragma mutierbar. Das konkrete Rückgabebeispiel lautet 'return 1'.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-mutation-mut-06"></a>

#### MUT-06: NFKC-äquivalente Funktionsnamen kollidieren trotz unterschiedlicher Mutanten-IDs

**medium · correctness · Konfidenz hoch** — `mod:mutation` — [src/mutmut_win/mutation.py:556](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:556)

**Mechanismus.** Definitionszählung und private Symbole verwenden rohe CST-Namen. Python normalisiert Identifier hingegen nach NFKC: Unterschiedliche Schreibweisen erhalten getrennt Ordinal 1, kollidieren aber als kompilierte Bindungen. Die Kollisionsprüfung normalisiert ebenfalls nicht. Das erste Belegfragment steht in mutation.py:556–558, das zweite in trampoline.py:120–122.

**Fehlerszenario.** Gültiger Quelltext definiert zunächst 'def K(): return 1', speichert dann 'first = K' und definiert in einer weiteren Zeile 'def Ｋ(): return 2' (U+FF2B). Ursprünglich liefert first() weiterhin 1 und K() nun 2. Nach der Instrumentierung kollidieren x_K__mutmut_orig und x_Ｋ__mutmut_orig; nach vollständigem Laden ruft first() den zweiten Originalrumpf auf und liefert 2. Stats und Aktivierung können ebenfalls falsch zugeordnet werden. Je nach Tests fällt schon der vorgeschaltete Testlauf aus; ein unbemerkt erfolgreicher Gesamtlauf ist nicht zwingend.

**Wörtlicher Beleg:**

```python
            top_definition_key = (None, func.name.value)
            definition_counts[top_definition_key] += 1
            definition_ordinal = definition_counts[top_definition_key]
...
    else:
        prefix = "x_"
        mangled = f"{prefix}{name}"
```

**Fixskizze.** Private Symbole auch nach Python-Normalisierung eindeutig kodieren; NFKC bei Allokation/Kollision, Rohschreibweise für Quellenbezug bewahren; gespeicherte Aliase testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei zwei mutierbaren Definitionen mit den Schreibweisen K und Ｋ kollidieren die erzeugten privaten Python-Bindungen trotz unterschiedlicher Mutanten-ID-Strings. Das Szenario muss syntaktisch korrekt als 'def K(): return 1\nfirst = K\ndef Ｋ(): return 2\n' geschrieben werden. Nach der Instrumentierung verwendet first() den zweiten Originalrumpf; Zuordnung und Aktivierung der Mutanten können ebenfalls verfälscht werden.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei zwei tatsächlich mutierten Funktionen mit unterschiedlich geschriebenen, NFKC-äquivalenten Namen kollidieren die generierten privaten Python-Bindungen trotz unterschiedlicher textueller Mutanten-IDs. Gültiges Beispiel: "def K(): return 1\nfirst = K\ndef Ｋ(): return 2\n". Nach vollständigem Laden des generierten Moduls ruft first() den zweiten Originalrumpf auf und liefert 2 statt 1. Je nach Testabdeckung kann dies bereits einen vorgeschalteten Testlauf scheitern lassen; ein unbemerkt erfolgreicher Gesamtlauf ist nicht zwingend.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-01"></a>

#### OP-01: CRCR verliert erforderliche Klammern und verändert falschen Ausdruck

**medium · correctness · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/node_mutation.py:72](C:/claude_codex/mutmut-win-astra/src/mutmut_win/node_mutation.py:72)

**Mechanismus.** _crcr_literal erzeugt Literale oder UnaryOperation-Knoten, ohne notwendige Originalklammern oder Klammern um negative Ersatzwerte zu erhalten. Im umgebenden Ausdruck ändern sich dadurch Bindung oder Syntax.

**Fehlerszenario.** Im standardmäßig verwendeten Profil advanced oder in all wird die Zahlbasis von 'return 2 ** x' durch -2 ** x statt (-2) ** x ersetzt; bei x=2 ergeben sich -4 statt 4. In 'return (2).bit_length()' kann eine CRCR-Ersetzung die Klammern verlieren und 0.bit_length() erzeugen. Der Syntaxschutz warnt und verwirft dann sämtliche Mutanten dieser Datei, während er deren Originalcode wiederherstellt; andere Dateien des Laufs sind davon nicht insgesamt betroffen.

**Wörtlicher Beleg:**

```python
if value < 0:
        return cst.UnaryOperation(operator=cst.Minus(), expression=literal)
    return literal
```

**Fixskizze.** Originalklammern übernehmen, negative Literale kontextsicher klammern; _parenthesized_minus behandelt Name-Potenzfall bereits. Vollständige Ausdrücke testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. CRCR erzeugt in advanced/all kontextwidrige Ersatzknoten: `def f(x): return 2**x` erhält für den Ersatzwert -2 die falsche Bindung `-2**x`; `def f(): return (2).bit_length()` kann syntaktisch ungültige Ausgabe erzeugen. Der vorhandene Dateischutz warnt und verwirft dann sämtliche Mutanten dieser betroffenen Datei.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. CRCR verliert bei Zahlersetzungen Originalklammern und klammert neue negative Ausdrücke nicht. In normalen Funktionsrümpfen entstehen dadurch falsch gebundene Potenzmutanten oder syntaktisch ungültige Attributzugriffe. Der Syntaxschutz verwirft sämtliche Mutanten der betroffenen Datei mit Warnung, nicht sämtliche Mutanten des gesamten Laufs.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-02"></a>

#### OP-02: _safe_unwrap behandelt nackte Dezimal-Integer als überall sichere Atome

**medium · correctness · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/node_mutation.py:300](C:/claude_codex/mutmut-win-astra/src/mutmut_win/node_mutation.py:300)

**Mechanismus.** Integer-Knoten gehören zu _ATOMIC_UNWRAP_TYPES und werden ohne zusätzliche Klammern zurückgegeben. Vor einem anschließenden Attributpunkt kann ein nackter Dezimal-Integer jedoch lexikalisch ungültig sein.

**Fehlerszenario.** In einem zur Mutation ausgewählten Funktionskörper kann abs(1).bit_length() unter advanced/all zu einem Attributzugriff mit nacktem Dezimal-Integer werden; bei (~1).bit_length() ist die Unary-Entfernung bereits unter basic aktiv. Es entsteht ungültiges 1.bit_length(). Der Dateischutz erhält den Originalquelltext, verwirft aber mit Warnung sämtliche Mutanten dieser Datei.

**Wörtlicher Beleg:**

```python
if (
        isinstance(expression, cst.GeneratorExp)
        or not isinstance(expression, _ATOMIC_UNWRAP_TYPES)
        or rendered_multiline
    ):
        return expression.with_changes(lpar=[cst.LeftParen()], rpar=[cst.RightParen()])
    return expression
```

**Fixskizze.** Dezimal-Integer klammern oder Einbettungskontext berücksichtigen; numerische Attributbasis prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Das Entklammern eines nackten Dezimal-Integer vor einem unmittelbar anschließenden Attributpunkt kann ungültigen Quelltext erzeugen. Im normalen Dateierzeugungspfad werden daraufhin sämtliche Mutanten dieser Datei mit Warnung verworfen; die Originaldatei bleibt erhalten.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. In einem tatsächlich mutierten Funktionskörper kann das Entfernen von abs(1) unter ADVANCED oder von (~1) bereits unter BASIC einen ungeklammerten Dezimal-Integer vor einem unmittelbar anschließenden Attributpunkt erzeugen. Der anschließende Dateischutz erhält den Originalquelltext, verwirft aber mit Warnung sämtliche erzeugten Mutanten der betroffenen Datei.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-03"></a>

#### OP-03: Unary-Mutation erzeugt ungültige positive Vorzeichen in Match-Literalen

**medium · correctness · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/node_mutation.py:349](C:/claude_codex/mutmut-win-astra/src/mutmut_win/node_mutation.py:349)

**Mechanismus.** Der generische UnaryOperation-Operator wirkt auch innerhalb von MatchValue. Numerische Patterns erlauben ein Minuszeichen, aber kein unäres Plus; die Ersetzung Minus→Plus berücksichtigt diesen Kontext nicht.

**Fehlerszenario.** Ein negatives numerisches Match-Pattern wie case -1 innerhalb einer zur Mutation zugelassenen Funktion erzeugt bereits unter basic den ungültigen Mutanten case +1. Bei aktivem Coverage-Filter muss die Pattern-Zeile für diesen Pfad abgedeckt sein. Der Syntaxschutz übernimmt daraufhin mit Warnung den Originaltext und leert die gesamte Mutantennamenliste dieser Datei.

**Wörtlicher Beleg:**

```python
cst.Minus: cst.Plus,
```

**Fixskizze.** Signed Pattern-Literal als Einheit mutieren; positive Werte ohne Plus und CRCR innerhalb negativer Pattern grammatisch behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Ein negatives numerisches Match-Pattern innerhalb einer zur Mutation zugelassenen Funktion kann bereits im Profil basic durch Minus→Plus ungültig werden. Der dateiweite Syntaxschutz verwirft daraufhin sämtliche erzeugten Mutanten dieser Datei und übernimmt das Original mit Warnung.
- Erreichbarkeit: angenommen, Konfidenz hoch. Ein negatives numerisches Match-Pattern innerhalb einer zur Mutation zugelassenen Funktion kann bereits im Basic-Profil einen syntaktisch ungültigen Plus-Pattern-Mutanten erzeugen. Der dateiweite Syntaxschutz übernimmt daraufhin den Originaltext in die Staging-Ausgabe, verwirft sämtliche Mutantennamen dieser Datei und meldet eine Warnung.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-04"></a>

#### OP-04: String-Case-Mutationen verändern Hex-Escape-Schreibweise ohne Laufzeitänderung

**medium · correctness · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/node_mutation.py:141](C:/claude_codex/mutmut-win-astra/src/mutmut_win/node_mutation.py:141)

**Mechanismus.** NON_ESCAPE_SEQUENCE schützt nur die Zeichen direkt hinter einem Backslash; die restlichen Zeichen mehrstelliger Escapes werden weiterhin in ihrer Groß-/Kleinschreibung verändert. Bei Hexziffern ändert dies den Laufzeitwert nicht. Der Vergleich des generierten Quelltexts erkennt diese Äquivalenz nicht.

**Fehlerszenario.** Eine tatsächlich getestete Funktion gibt ein nicht-rohes Python-Stringliteral mit dem Escape \xff zurück. Der Operator veröffentlicht daraus unter anderem die Schreibweise \xFF mit identischem Stringwert. Entsprechendes gilt für Bytes-Literale und passende Unicode-Escapes in Strings. Solche ausgeführten äquivalenten Mutanten können überleben und den Score senken. Rawstrings fallen nicht unter diesen Gleichwertigkeitsnachweis.

**Wörtlicher Beleg:**

```python
NON_ESCAPE_SEQUENCE = re.compile(r"((?<!\\)[^\\]+)")
...
            lambda x: NON_ESCAPE_SEQUENCE.sub(lambda match: match.group(1).upper(), x),
```

**Fixskizze.** Vollständige Escapesequenzen schützen, ausgewertete Werte auf Gleichheit prüfen; Rawstrings semantisch gesondert.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei nicht-rohen String- und Bytes-Literalen können Case-Mutationen ausschließlich die Buchstabenschreibweise innerhalb mehrstelliger Hex-Escapes verändern und dadurch äquivalente Mutanten veröffentlichen. Dasselbe gilt für passende Unicode-Escapes in Stringliteralen. Der Score-Effekt setzt ausgeführte Tests voraus; Rawstrings fallen nicht unter diesen Gleichwertigkeitsnachweis.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-06"></a>

#### OP-06: Regex-Operator mutiert bei Keyword-Aufrufen falsches Argument

**medium · api-contract · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/node_mutation.py:506](C:/claude_codex/mutmut-win-astra/src/mutmut_win/node_mutation.py:506)

**Mechanismus.** node.args[0] wird unabhängig von seinem Keyword als Pattern behandelt, obwohl die Schreibreihenfolge von Keywordargumenten frei ist.

**Fehlerszenario.** Bei re.sub(repl="a+", pattern="x", string=value) verändert der Regex-Operator das zuerst geschriebene repl-Literal etwa zu "a", während das eigentliche Pattern unverändert bleibt. Bei re.search(string="a+", pattern="x") kann er entsprechend den Suchtext verändern. Der Fall setzt ein zuerst geschriebenes Stringliteral-Argument ungleich pattern voraus; steht pattern zuerst, arbeitet die Auswahl korrekt, und bei einem ersten Nichtliteral erzeugt dieser Operator keine Regexmutanten.

**Wörtlicher Beleg:**

```python
first_arg = node.args[0]
    if not isinstance(first_arg.value, cst.SimpleString):
        return
```

**Fixskizze.** Das explizite pattern-Keyword oder den tatsächlich ersten positionalen, nicht expandierten Parameter bestimmen und genau diesen Argumentknoten ersetzen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Bei unterstützten re.*-Aufrufen mit einem zuerst geschriebenen Stringliteral-Keywordargument ungleich pattern wendet operator_regex seine Patternmutationen auf dieses andere Argument an. Dadurch können beispielsweise repl oder string verändert werden, während ein späteres pattern-Argument unberücksichtigt bleibt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-07"></a>

#### OP-07: Unicode-Grenzbereiche brechen Regex-Generierung mit ValueError ab

**medium · error-handling · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/regex_mutation.py:271](C:/claude_codex/mutmut-win-astra/src/mutmut_win/regex_mutation.py:271)

**Mechanismus.** Die Codepoints von Regex-Bereichsgrenzen werden ohne Prüfung der Unicode-Grenzen inkrementiert oder dekrementiert. chr(0x110000) beziehungsweise chr(-1) wirft bereits vor der Regex-Validierung ValueError. file_setup reicht den Fehler als Generierungsfehler weiter.

**Fehlerszenario.** Bei frischer Generierung unter advanced/all erreicht ein nicht ausgeschlossener re.*-Aufruf den Regex-Operator mit einem gewöhnlichen Stringliteral für einen Singleton-Bereich an U+0000 oder U+10FFFF. Die ausgewerteten Zeichen führen zu chr(-1) beziehungsweise chr(0x110000); ValueError bricht die Generierung ab. Dieselben Escape-Schreibweisen in Rawstrings belegen diesen konkreten Fehler nicht. BASIC, ausgeschlossene Funktionen oder ein verwendbarer Generierungscache können den Operator umgehen.

**Wörtlicher Beleg:**

```python
for lo2, hi2 in ((lo + 1, hi), (lo, hi - 1)):
                new_body = body[: m.start()] + chr(lo2) + "-" + chr(hi2) + body[m.end() :]
```

**Fixskizze.** Vor chr den Bereich 0 bis 0x10FFFF und lo2 <= hi2 prüfen; nur den unzulässigen Kandidaten lokal verwerfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei einer tatsächlich zur Mutation ausgewählten re.*-Anweisung mit gewöhnlichem Stringliteral für einen Singleton-Bereich U+10FFFF oder U+0000 bricht die frische Generierung im Profil advanced/all mit ValueError ab. Ausnahmen wie basic-Profil, ausgeschlossene Funktionen oder ein verwendbarer Generierungscache können den betroffenen Operator umgehen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei aktivem ADVANCED-/ALL-Profil kann ein nicht ausgeschlossener re.*-Aufruf mit einem gewöhnlichen Stringliteral für eine Singleton-Range an U+0000 oder U+10FFFF die Mutantengenerierung mit ValueError abbrechen. Die genannten Python-Escapes müssen vor der Regex-Mutation ausgewertet sein; dieselben Escape-Schreibweisen in Raw-Strings belegen diesen konkreten chr-Fehler nicht.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-08"></a>

#### OP-08: Regex-Mutantenlimit begrenzt vorgelagerte quadratische Materialisierung nicht

**medium · performance · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/regex_mutation.py:66](C:/claude_codex/mutmut-win-astra/src/mutmut_win/regex_mutation.py:66)

**Mechanismus.** Fünf Submutatoren bauen vollständige Listen von Patternkopien auf. Erst danach begrenzt MAX_MUTATIONS_PER_PATTERN die Ausgabe auf zwölf Kandidaten. Linear viele Mutationsstellen verursachen damit quadratischen Speicherbedarf und Kopieraufwand.

**Fehlerszenario.** Ein ausgeschriebenes Regex-Stringliteral aus 10000 Wiederholungen von 'a?' enthält 20000 Zeichen. Im normalen ADVANCED-Pfad erzeugt allein der Quantifier-Submutator zunächst 30000 vollständige Strings mit zusammen 600020000 Zeichen, bevor das Ergebnislimit von zwölf greift. Speicher- und Kopierkosten wachsen dadurch quadratisch. Ein MemoryError ist abhängig vom verfügbaren Speicher möglich, aber weder gemessen noch zwingend. Der Ausdruck re.compile('a?' * 10000) ist kein passendes Beispiel: Dieser Nichtliteral-Ausdruck wird vom Operator übersprungen.

**Wörtlicher Beleg:**

```python
mutations.extend(_mutate_quantifiers(pattern))
    mutations.extend(_mutate_char_classes(pattern))
    mutations.extend(_mutate_anchors(pattern))
    mutations.extend(_mutate_classes(pattern))
    mutations.extend(_mutate_groups(pattern))
```

**Fixskizze.** Submutatoren als Iteratoren ausführen, Kandidaten laufend validieren und deduplizieren und nach zwölf gültigen Ergebnissen abbrechen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei langen ausgeschriebenen Regex-Stringliteralen mit linear vielen Mutationsstellen entstehen bereits vor Anwendung des Rückgabelimits quadratische Speicher- und Kopierkosten. Das 20000-Zeichen-Beispiel erzeugt im Quantifier-Submutator 30000 vollständige Kandidatenstrings mit rund 600 Millionen Zeichen. Ein MemoryError ist abhängig vom verfügbaren Speicher möglich, für dieses Beispiel aber weder zwingend noch gemessen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein ausgeschriebenes 20000-Zeichen-Regexliteral aus 10000 Wiederholungen von 'a?' verursacht im regulären ADVANCED-Aufrufpfad bereits vor der Ergebnisbegrenzung 30000 vollständige Kandidatenstrings mit insgesamt 600020000 Zeichen. Die quadratischen Speicher- und Kopierkosten sind aus dem Code ableitbar. Ein MemoryError ist abhängig vom verfügbaren Speicher möglich, für dieses Beispiel jedoch nicht nachgewiesen oder zwingend.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-09"></a>

#### OP-09: Regex-Kommentare erzeugen wirkungslose Operator-Mutanten

**medium · correctness · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/regex_mutation.py:129](C:/claude_codex/mutmut-win-astra/src/mutmut_win/regex_mutation.py:129)

**Mechanismus.** Der Scanner berücksichtigt Escapes und Zeichenklassen, aber keine (?#...)-Kommentare. Quantifier-, Shorthand- und Anchor-Mutationen verändern dadurch ignorierten Kommentartext. Kompilierung und Quelltextvergleich erkennen die Äquivalenz nicht.

**Fehlerszenario.** In einer gewöhnlichen zu mutierenden Funktion verändert der Operator re.fullmatch(r"a(?#\d+)", value) is not None unter anderem zu den Patterns a(?#\d) oder a(?#\D+). Für alle Stringeingaben bleibt der boolesche Matchwert gleich. Der Text eines Patternobjekts kann dagegen separat beobachtet werden; die Gleichwertigkeitsbehauptung ist deshalb auf den angegebenen Boolkontext begrenzt.

**Wörtlicher Beleg:**

```python
for match in _QUANTIFIER_RE.finditer(pattern):
        if _in_class(match.start(), class_spans):
            # Inside ``[...]`` these glyphs are literals (or class syntax),
            # never repetition operators.
            continue
```

**Fixskizze.** Kommentarbereiche tokenisieren und alle Submutatoren aussparen lassen; Inline-Verbose/VERBOSE-Kontext ergänzen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-01"></a>

#### EDGE-01: Unicode-normalisierte Keyword-only-Parameter brechen den unveränderten Funktionsaufruf

**medium · correctness · Konfidenz hoch** — `lens:boundaries` — [src/mutmut_win/mutation.py:955](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:955)

**Mechanismus.** Die Weiterleitung verwendet den ursprünglichen LibCST-Parameternamen als Stringschlüssel. CPython normalisiert Bezeichner beim Kompilieren nach NFKC, Stringschlüssel jedoch nicht. Bei abweichender Quellschreibweise unterscheiden sich deshalb der Parametername der privaten Implementierung und das übergebene Keyword.

**Fehlerszenario.** Die tatsächlich instrumentierte Funktion def f(*, K=1): return K + 1 verwendet das Kelvin-Zeichen K. Im unveränderten Original liefert f(K=2) den Wert 3. Der generierte Quelltext enthält dagegen {'K': K}; CPython normalisiert den Bezeichner auf der Wertseite zu K, lässt den Stringschlüssel aber unverändert. Das private Original akzeptiert K und erhält stattdessen K. Ruft ein Clean-Run-Test diese Funktion auf, entsteht TypeError.

**Wörtlicher Beleg:**

```python
cst.DictElement(cst.SimpleString(f"'{p.name.value}'"), p.name)
for p in function.params.kwonly_params
```

**Fixskizze.** Keywordschlüssel aus der NFKC-normalisierten Python-Parameteridentität erzeugen und die internen Kollisionsprüfungen entsprechend absichern.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei instrumentierten Funktionen mit Keyword-only-Parametern, deren Quellschreibweise von ihrer NFKC-Normalform abweicht, bricht die Weiterleitung bereits beim unveränderten Aufruf. Der generierte Quelltext enthält genauer {'K': K}; CPython normalisiert den Bezeichner auf der Wertseite zu K, den Stringschlüssel hingegen nicht. Ruft der Clean Run diese Funktion auf, entsteht TypeError.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei einer tatsächlich instrumentierten Funktion mit einem durch NFKC veränderten Keyword-only-Parameternamen scheitert bereits die unveränderte Originalausführung über den Wrapper. Im Beispiel erzeugt der CST-Code textuell {'K': K}; CPython normalisiert nur den rechten Bezeichner zu K, nicht den Stringschlüssel. Ein Clean-Run-Test mit f(K=2) erhält deshalb TypeError statt 3. Der Clean Run scheitert nur, wenn die betreffende Funktion tatsächlich aufgerufen wird.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-02"></a>

#### EDGE-02: Regex-Einzelzeichenbereiche an Unicode-Grenzen brechen die Generierung ab

**medium · correctness · Konfidenz hoch** — `lens:boundaries` — [src/mutmut_win/regex_mutation.py:271](C:/claude_codex/mutmut-win-astra/src/mutmut_win/regex_mutation.py:271)

**Mechanismus.** Die Range-Mutationen bilden chr(lo + 1) beziehungsweise chr(hi - 1), bevor sie die Kandidaten als Regex validieren. Für den Bereich U+0000–U+0000 entsteht chr(-1), für U+10FFFF–U+10FFFF chr(0x110000). Der ValueError entkommt dem Operator und der späteren Syntaxfehlerbehandlung.

**Fehlerszenario.** Bei einer frischen Generierung mit aktivem Regex-Operator (advanced oder all) enthält eine zur Mutation ausgewählte Funktion re.compile("[\x00-\x00]") oder re.compile("[\U0010ffff-\U0010ffff]") als nicht rohes Python-Stringliteral. Beide Ausgangspattern sind gültig; evaluated_value liefert die tatsächlichen Endpunktzeichen. Der Worker meldet den Dateifehler, und der Orchestrator verweigert die Veröffentlichung der gesamten neuen Mutantenmenge. Basic, Ausschlussregeln, passende Wiederverwendung oder rohe Escape-Schreibweisen vermeiden diesen konkreten Pfad. Ein Unicode-Endpunkt in einem anderen gültigen Bereich genügt nicht.

**Wörtlicher Beleg:**

```python
for lo2, hi2 in ((lo + 1, hi), (lo, hi - 1)):
    new_body = body[: m.start()] + chr(lo2) + "-" + chr(hi2) + body[m.end() :]
```

**Fixskizze.** Vor der chr-Konstruktion 0 <= lo2 <= hi2 <= 0x10ffff prüfen und unzulässige Kandidaten lokal überspringen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei tatsächlicher Neugenerierung einer zur Mutation ausgewählten Funktion mit aktivem Regex-Operator (advanced oder all) lassen gültige nicht rohe Stringliterale wie re.compile("[\x00-\x00]") oder re.compile("[\U0010ffff-\U0010ffff]") die Regex-Mutation mit ValueError scheitern. Dadurch bricht der Orchestrator den Generierungsschritt ab und verweigert die Veröffentlichung eines neuen Mutantenuniversums.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei einer frischen Generierung mit ADVANCED oder ALL bricht ein nicht ausgeschlossener re.*-Aufruf mit einem Stringliteral, dessen ausgewertetes Pattern den Bereich U+0000–U+0000 oder U+10FFFF–U+10FFFF enthält, die Generierung der betroffenen Datei ab und verhindert die Veröffentlichung der gesamten neuen Mutantenmenge. Bloßes Vorkommen eines Unicode-Endpunkts in einem anderen gültigen Bereich reicht nicht aus.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-03"></a>

#### EDGE-03: Große gültige Hexliterale überschreiten bei der Dezimalserialisierung CPythons Ziffernlimit

**medium · correctness · Konfidenz hoch** — `lens:boundaries` — [src/mutmut_win/node_mutation.py:46](C:/claude_codex/mutmut-win-astra/src/mutmut_win/node_mutation.py:46)

**Mechanismus.** Der Basisoperator serialisiert den erhöhten Integer mit repr in Dezimalschreibweise. CPythons standardmäßiges Dezimalziffernlimit betrifft diese Konvertierung, obwohl das ursprüngliche Hex-, Oktal- oder Binärliteral gültig ist. Der ValueError wird weder im Besucher noch durch die auf ParserSyntaxError und CSTValidationError begrenzte Dateibehandlung abgefangen; die neue Mutantenmenge wird nicht veröffentlicht. CRCR hat bei str(magnitude) dieselbe Schwäche, wird im normalen Ablauf aber bereits durch den Basisoperator überlagert.

**Fehlerszenario.** Bei CPython 3.14.7 mit Standardlimit 4300 enthält ein nicht ausgeschlossener Funktionskörper ein Hexliteral aus 0x und 3600 F-Ziffern. Bei tatsächlicher Neugenerierung erreicht bereits das Basic-Profil den Operator: Addition um eins gelingt, die anschließende Dezimalserialisierung benötigt jedoch 4335 Ziffern und wirft ValueError. Die Generierung bricht ab.

**Wörtlicher Beleg:**

```python
new_value = node.evaluated_value + 1
...
yield node.with_changes(value=repr(new_value))
...
cst.Integer(str(magnitude)) if isinstance(value, int) else cst.Float(repr(magnitude))
```

**Fixskizze.** Große Integer in einer vom Ziffernlimit unabhängigen Basis serialisieren, beispielsweise hex; CRCR entsprechend behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-07"></a>

#### EDGE-07: Regex-Limit greift erst nach quadratischem Speicherverbrauch

**medium · performance · Konfidenz hoch** — `lens:boundaries` — [src/mutmut_win/regex_mutation.py:66](C:/claude_codex/mutmut-win-astra/src/mutmut_win/regex_mutation.py:66)

**Mechanismus.** Alle Untergeneratoren materialisieren vollständige Listen mit einer vollständigen Patternkopie pro Änderung. MAX_MUTATIONS_PER_PATTERN wird erst anschließend angewandt. Bei Patternlänge n mit proportional vielen Quantifizierern entsteht quadratischer Zwischenspeicher für höchstens zwölf Resultate.

**Fehlerszenario.** Bei Neugenerierung oder Cache-Miss enthält eine nicht ausgeschlossene Funktion ein tatsächlich ausgeschriebenes Regex-Stringliteral aus 10000 a+-Paaren, also 20000 Zeichen. Im standardmäßigen ADVANCED-Profil erzeugt allein _mutate_quantifiers 40000 vollständige Strings mit zusammen 800030000 Zeichen, bevor das Limit von zwölf Ergebnissen greift. Ressourcenknappheit kann den Lauf scheitern lassen; mehrere gleichzeitig generierte Dateien mit solchen Mustern erhöhen den Gesamtbedarf. Ein Speicherfehler oder Timeout bei genau dieser Größe wurde nicht gemessen und ist nicht zwingend. BASIC und passende Wiederverwendung vermeiden diesen Erzeugungspfad.

**Wörtlicher Beleg:**

```python
mutations.extend(_mutate_quantifiers(pattern))
mutations.extend(_mutate_char_classes(pattern))
mutations.extend(_mutate_anchors(pattern))
mutations.extend(_mutate_classes(pattern))
mutations.extend(_mutate_groups(pattern))
...
if len(valid) >= MAX_MUTATIONS_PER_PATTERN:
    break
```

**Fixskizze.** Untergeneratoren lazy auswerten und nach zwölf validierten unterschiedlichen Resultaten abbrechen; tatsächliche Erzeugungszahl begrenzen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei erstmaliger Generierung beziehungsweise Cache-Miss verursacht ein langes Regex-Stringliteral mit proportional vielen Quantifizierern quadratischen Zwischenspeicher, obwohl höchstens zwölf Mutationen zurückgegeben werden. Das Beispiel erfordert ungefähr 800 MB allein für ASCII-Zeicheninhalte zuzüglich Verwaltungsdaten und temporärer Objekte. Ressourcenknappheit oder Überschreiten des Generierungszeitlimits können den Mutationslauf scheitern lassen; ein Timeout bei genau 20000 Zeichen ist nicht zwingend belegt. Parallel bearbeitete Dateien mit solchen Mustern erhöhen den Gesamtbedarf. Eine Beschädigung oder dauerhafte Blockierung des Quellbaums ist damit nicht nachgewiesen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Im Standardprofil erzeugt ein tatsächlich ausgeschriebenes, 20000 Zeichen langes Regex-Stringliteral aus 10000 a+-Paaren vor der Ergebnisbegrenzung rund 800 Millionen Zeichen Zwischenspeicher. Das kann bei begrenztem Speicher oder mehreren gleichzeitig betroffenen Dateiarbeitern die Generierung erheblich belasten oder fehlschlagen lassen. Ein Speicherfehler beziehungsweise Generationstimeout bei genau dieser Größe ist ohne Laufmessung nicht garantiert; ein dauerhaftes Blockieren des Quellbaums ist nicht belegt.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-contracts-contract-01"></a>

#### CONTRACT-01: Übersprungene verschachtelte Klassen beschädigen den Ausschlusskontext äußerer Methoden

**medium · api-contract · Konfidenz hoch** — `lens:contracts` — [src/mutmut_win/mutation.py:304](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutation.py:304)

**Mechanismus.** on_visit beendet ausgeschlossene ClassDef-Knoten vor dem Push auf _class_stack. on_leave entfernt bei jedem ClassDef einen vorhandenen Eintrag. LibCST ruft on_leave auch nach on_visit=False auf; dasselbe Modul nutzt dies ausdrücklich im ChildReplacementTransformer. Eine übersprungene innere Klasse entfernt dadurch den äußeren Kontext.

**Fehlerszenario.** Outer enthält zuerst die per ^Inner$ ausgeschlossene innere Klasse Inner und danach eine gewöhnliche Methode excluded mit mutierbarem Körper, etwa return 1 + 2. Bei do_not_mutate_patterns=['^Inner$', '^Outer\\.excluded$'] entfernt das Verlassen von Inner den äußeren Stackeintrag. excluded wird anschließend ohne Outer-Präfix geprüft und trotz des qualifizierten Ausschlussmusters mutiert. Die spätere Verarbeitung unterstützt diese direkte äußere Methode und prüft die Muster nicht erneut.

**Wörtlicher Beleg:**

```python
        if isinstance(original_node, cst.ClassDef) and self._class_stack:
            self._class_stack.pop()
```

**Fixskizze.** Stackeinträge an tatsächlich gepushte ClassDef-Identitäten binden; nur dieselbe Identität beim Verlassen entfernen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-contracts-contract-06"></a>

#### CONTRACT-06: Regex-Bereichsmutationen an Unicode-Grenzen brechen Generierung ab

**medium · correctness · Konfidenz hoch** — `lens:contracts` — [src/mutmut_win/regex_mutation.py:271](C:/claude_codex/mutmut-win-astra/src/mutmut_win/regex_mutation.py:271)

**Mechanismus.** _mutate_classes bildet lo+1 und hi-1 und ruft chr ohne Bereichsprüfung auf. Ein Einpunktbereich U+0000–U+0000 verlangt chr(-1), der Einpunktbereich U+10FFFF–U+10FFFF verlangt chr(0x110000). operator_regex übergibt den ausgewerteten Inhalt eines normalen Python-Stringliterals. Der ValueError entsteht vor Regex- und Literalvalidierung; weder der Besucher noch die auf CST-Ausnahmen begrenzte Dateibehandlung fangen ihn ab.

**Fehlerszenario.** Eine nicht ausgeschlossene Funktion enthält re.compile("[\x00-\x00]") als normales Stringliteral, sodass der ausgewertete Pattern zwei NUL-Zeichen enthält. Bei tatsächlicher Neugenerierung im standardmäßigen ADVANCED-Profil scheitert der zweite Bereichskandidat an chr(-1); entsprechend scheitert der obere Einpunktbereich am ersten Kandidaten. Der Fehler erreicht die Generierungsaufsicht und verhindert die Veröffentlichung der neuen Mutantenmenge. BASIC, ein Ausschluss oder passende Wiederverwendung vermeiden den Pfad; ein rohes Literal mit weiterhin enthaltenen Backslash-Escapes ist kein gleiches Beispiel.

**Wörtlicher Beleg:**

```python
            lo, hi = ord(m.group(1)), ord(m.group(2))
            for lo2, hi2 in ((lo + 1, hi), (lo, hi - 1)):
                new_body = body[: m.start()] + chr(lo2) + "-" + chr(hi2) + body[m.end() :]
                results.append(f"{before}[{mark}{new_body}]{after}")
```

**Fixskizze.** Vor chr beide Werte auf Unicode-Bereich prüfen; ungültige Kandidaten überspringen; ausgewertete Stringliterale testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-mutation-mut-07"></a>

#### MUT-07: Modulstatements fehlen als ausdrückliche Mutation-surface-Grenze

**low · api-contract · Konfidenz hoch** — `mod:mutation` — [README.md:372](C:/claude_codex/mutmut-win-astra/README.md:372)

**Mechanismus.** Direkt auf Modulebene stehende ausführbare Statements werden keiner äußeren Funktion zugeordnet und erzeugen keine veröffentlichten Mutanten. Die README beschreibt die unterstützte Funktionsoberfläche bereits positiv, benennt Modulstatements und ihren fehlenden Beitrag zum Score-Nenner aber nicht ausdrücklich. Dies ist ausschließlich die im Auftrag genannte Dokumentationspräzisierung, kein Architektur-, Generierungs- oder Berechnungsdefekt. Der zweite Beleg stammt aus mutation.py:1040–1042.

**Fehlerszenario.** Ein Nutzer mutiert ein Modul mit Konstantenzuweisungen, Importzeitkonfiguration oder Modulverzweigungen. Diese Bereiche bleiben unverändert und tragen nicht zum Mutantenbestand beziehungsweise Score-Nenner bei; der Limit-Abschnitt erklärt diese konkrete Grenze nur implizit über die beschriebene Funktionsoberfläche.

**Wörtlicher Beleg:**

```text
**Mutation-surface limits:** the trampoline mechanism rewrites top-level
functions and top-level-class methods. The two kinds of nesting differ:
...
    for mut in mutations:
        if mut.contained_by_top_level_function:
            grouped[mut.contained_by_top_level_function].append(mut)
```

**Fixskizze.** Modulstatements/Initialisierungslogik explizit als nicht mutiert und außerhalb Score-Nenner dokumentieren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Reine Dokumentationspräzisierung: Direkt auf Modulebene stehende ausführbare Statements erzeugen keine veröffentlichten Mutanten und tragen deshalb nicht zum Score-Nenner bei. Die bestehende Funktionsgrenze impliziert dies bereits, benennt es aber nicht ausdrücklich. Daraus folgt kein Architektur- oder Berechnungsdefekt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Eng begrenzte Dokumentationslücke: Der Limit-Abschnitt sollte ausdrücklich erklären, dass Modulzuweisungen und Modulverzweigungen unverändert bleiben, keine veröffentlichten Mutanten erzeugen und deshalb nicht zum Score-Nenner beitragen. Ein Generierungs- oder Berechnungsfehler ist damit nicht nachgewiesen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-operators-op-05"></a>

#### OP-05: Float-Inkrementierung veröffentlicht durch Rundung unveränderte Literale

**low · correctness · Konfidenz hoch** — `mod:operators` — [src/mutmut_win/node_mutation.py:40](C:/claude_codex/mutmut-win-astra/src/mutmut_win/node_mutation.py:40)

**Mechanismus.** Bei großen endlichen Floatwerten kann die Addition von 1 wegen der Rundung denselben Wert liefern. Der Operator prüft lediglich die Endlichkeit; eine abweichende repr-Schreibweise übersteht den Vergleich mit dem Originalquelltext.

**Fehlerszenario.** Eine gewöhnliche zur Mutation zugelassene Funktion mit 'return 1e20' erhält eine Implementierung mit 'return 1e+20', obwohl Addition von 1 denselben Float ergibt. Entsprechendes gilt für große Imaginärliterale bei Addition von 1j. Voraussetzung ist eine von repr abweichende Originalschreibweise; bereits kanonisches 1e+20 wird als identisch gerenderter Kandidat entfernt. Im normalen Funktionsverhalten bleibt der veröffentlichte Mutant äquivalent.

**Wörtlicher Beleg:**

```python
        new_value = node.evaluated_value + 1
        # 1e400 is a legal literal evaluating to inf, but repr(inf) is not a
        # valid float token — with_changes would raise CSTValidationError and
        # kill mutant generation for the whole file (issue #78 / A1-NM-007).
        if isinstance(new_value, float) and not math.isfinite(new_value):
            return
        yield node.with_changes(value=repr(new_value))
```

**Fixskizze.** Vor der Veröffentlichung new_value == original_value ausschließen, auch im Zweig für Imaginärliterale.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Bei endlichen Float- und Imaginärliteralen, deren Addition von 1 beziehungsweise 1j zum gleichen Zahlenwert rundet und deren ursprüngliche Schreibweise von repr abweicht, veröffentlicht operator_number einen im normalen Funktionsverhalten äquivalenten Mutanten. Beispiel: 'def f(): return 1e20' wird zu einer Implementierung mit 'return 1e+20'.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Bei großen endlichen Float- und Imaginärliteralen kann die Inkrementierung wertgleich bleiben. Weicht ihre ursprüngliche Schreibweise von repr ab, beispielsweise in einer gültigen Funktion mit 'return 1e20', wird ein im normalen Funktionsverhalten äquivalenter Mutant mit 'return 1e+20' veröffentlicht. Bereits identisch gerenderte Kandidaten werden dagegen herausgefiltert.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

### CLI, Konfiguration und Darstellung

<a id="mod-presentation-view-02"></a>

#### VIEW-02: apply überschreibt zwischenzeitliche Quelländerungen ohne Sicherung

**high · toctou · Konfidenz hoch** — `mod:presentation` — [src/mutmut_win/mutant_diff.py:617](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutant_diff.py:617)

**Mechanismus.** apply prüft die Quellbytes nur beim anfänglichen Einlesen gegen source_hash. Anschließend verarbeitet es Staging-Code und CST, erstellt das Backup aus denselben alten Bytes und ersetzt die Quelle. Der Atomic-Writer prüft Elternverzeichnis und eigene temporäre Veröffentlichung, vergleicht den bisherigen Zielinhalt aber nicht mit der ursprünglich gelesenen Version.

**Fehlerszenario.** Nachdem apply die gültige Quellfassung S0 gelesen hat, speichert und schließt ein Editor oder Formatter die geänderte Fassung S1, während apply noch das Mutantenmodul parst oder den neuen Quelltext aufbaut. Die spätere erfolgreiche Veröffentlichung ersetzt S1 durch den Mutanten aus S0. Auch die Backup-Datei enthält nur S0; die zwischenzeitlich gespeicherte Änderung wird von mutmut-win nicht gesichert. Workspace- und Datenbanksperren verhindern diesen Editorzugriff nicht, da sie andere Guard-Dateien sperren.

**Wörtlicher Beleg:**

```python
    atomic_write_bytes(source_path, applied_bytes, mode=source_mode)
```

**Fixskizze.** Die Veröffentlichung an die überprüfte Quellversion binden und bei Drift abbrechen, ohne neue Inhalte zu überschreiben. Eine erneute Prüfung vor dem Schreiben verkleinert das Fenster lediglich; eine vollständige Garantie erfordert ein geeignetes Dateisperr- oder Versionsprotokoll.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am geprüften HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat in src/mutmut_win/mutant_diff.py:617 wörtlich: atomic_write_bytes(source_path, applied_bytes, mode=source_mode). Die einzige Quellinhaltprüfung erfolgt beim Aufruf in Zeile 577; der Helfer liest und vergleicht die Bytes in Zeilen 57–65. Danach werden ausschließlich diese gespeicherten Bytes verarbeitet, einschließlich beider CST-Parses in Zeilen 588–589. Das Backup in Zeile 611 enthält ebenfalls source_bytes vom ursprünglichen Einlesen. Ein abgeschlossener Editor-/Formatter-Speichervorgang zwischen diesem Einlesen und der Veröffentlichung kann deshalb überschrieben werden, ohne dass dessen Inhalt im Backup landet. Aktiv geprüfte Gegenmaßnahmen widerlegen dies nicht: atomic_file.py:388–403 prüft Verzeichnis und temporäre Datei, ersetzt das Ziel in Zeile 391 und kontrolliert danach die Identität der eigenen Veröffentlichung. Es vergleicht weder vorherige Zielbytes noch die ursprüngliche Zielidentität. Die CLI hält zwar WorkspaceRunLock und DatabaseRunLocks (cli.py:1073–1076); diese sperren jedoch separate Guard-Dateien (process/run_lock.py:503–505, 547–550), nicht die Quelldatei. Ein bereits beendeter Speichervorgang eines Editors wird dadurch nicht ausgeschlossen. Testabdeckung: test_source_protection.py:143–163 verändert die Quelle bereits vor apply_mutant und prüft korrekt die anfängliche Hashprüfung. Zeilen 130–141 prüfen das Backup bei unveränderter Quelle. test_atomic_write_safety_220.py:229–254 prüft einen fehlgeschlagenen Replace; der Befund betrifft einen erfolgreichen Replace nach zwischenzeitlicher Änderung. In den gesichteten einschlägigen Tests fehlt diese zeitliche Konstellation. Es wurden keine Tests oder Reproduktionen ausgeführt. High ist wegen möglichem Verlust zwischenzeitlicher Quelländerungen angemessen.

**Erreichbarkeit:** Am geprüften HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat in src/mutmut_win/mutant_diff.py:617 wörtlich: atomic_write_bytes(source_path, applied_bytes, mode=source_mode). Die einzige Quellinhaltsprüfung erfolgt über Zeile 577 und _read_source_bytes_matching_staging:57–66. Anschließend werden Quelle und Mutantenmodul geparst (588–589) und der neue Modulinhalt erzeugt (608). Das Backup erhält ausdrücklich die zuvor gelesenen source_bytes (611), keine erneut eingelesene Quelle. Der Atomic-Writer kontrolliert Elternverzeichnis und temporäre Datei; atomic_file.py:391 ersetzt das Ziel mit temp_path.replace(path). Die nachgelagerte Identitätsprüfung (397–403) erkennt keine bereits vor dieser Ersetzung abgeschlossene Änderung. Der normale CLI-Pfad ist erreichbar (cli.py:1073–1102). Seine Workspace-/DB-Sperren sperren separate Guard-Dateien beziehungsweise datenbankbezogene Sperrpfade (process/run_lock.py:499–505, 547–550, 754–767), nicht die Quelldatei. Ein Editor oder Formatter kann deshalb nach dem anfänglichen Lesen speichern und seine Datei schließen, während apply noch verarbeitet; eine anschließend erfolgreiche Ersetzung überschreibt diese Änderung. test_source_protection.py:143–163 prüft ausschließlich Drift vor dem apply-Aufruf. Der Backup-Test (130–141) enthält keinen konkurrierenden Schreibzugriff. Die einschlägigen Atomic-Write-Tests prüfen Linkschutz und fehlgeschlagene Ersetzungen; einen Test für Quelländerungen zwischen Lesen und Veröffentlichung habe ich nicht gefunden. Nur statisch geprüft, keine Tests oder Reproduktionen ausgeführt. High ist für möglichen Verlust zwischenzeitlich gespeicherter Quelländerungen angemessen.

<a id="lens-races-race-04"></a>

#### RACE-04: Apply überschreibt während der CST-Verarbeitung gespeicherte Quelländerungen

**high · toctou · Konfidenz hoch** — `lens:races` — [src/mutmut_win/mutant_diff.py:617](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutant_diff.py:617)

**Mechanismus.** Die Quelle wird einmal eingelesen und gegen den Erzeugungshash geprüft. Danach arbeiten Decodierung, CST-Verarbeitung und Körpervergleich ausschließlich mit diesen Bytes. Backup und abschließende Veröffentlichung verwenden ebenfalls nur den eingelesenen Stand. Der Atomic-Writer schützt seine temporäre Datei und die Veröffentlichung, prüft aber nicht die erwartete bisherige Zielversion; die Workspace- und Datenbanksperren betreffen separate Guard-Dateien.

**Fehlerszenario.** Apply liest den gültigen Stand S0. Während der anschließenden Verarbeitung speichert ein Editor S1 in derselben Quelldatei und schließt seinen Handle. Apply sichert anschließend S0 im Backup und ersetzt die Quelle erfolgreich durch mutate(S0). Die zwischenzeitlich gespeicherten Änderungen aus S1 gehen verloren und sind auch nicht im eigenen Backup enthalten.

**Wörtlicher Beleg:**

```python
    backup_path = source_path.with_name(source_path.name + ".mutmut-orig.bak")
    atomic_write_bytes(backup_path, source_bytes, mode=source_mode)
    try:
        applied_bytes = new_module.code.encode(source_encoding)
    except UnicodeEncodeError as exc:
        msg = f"applied mutant cannot be represented in source encoding {source_encoding}: {exc}"
        raise MutationParseError(msg) from exc
    atomic_write_bytes(source_path, applied_bytes, mode=source_mode)
```

**Fixskizze.** Die Quellversion bis zur Veröffentlichung absichern und erkannte Änderungen als StaleStagingError ablehnen. Eine erneute Hashprüfung allein verkleinert das Zeitfenster; die vollständige Garantie benötigt eine Koordination von Schreiben und Ersetzen unter Windows.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am geprüften HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b steht das Zitat wörtlich in src/mutmut_win/mutant_diff.py:610–617; Zeile 617 enthält tatsächlich den abschließenden atomic_write_bytes-Aufruf. Die Quellbytes werden in Zeile 577 einmal eingelesen und gegen den Erzeugungshash geprüft; die Hilfsfunktion verwendet dafür read_bytes() und SHA-256 (Zeilen 51–66). Danach arbeiten Decodierung, beide CST-Parser, Körpervergleich und deep_replace ausschließlich mit diesem eingelesenen Stand. Insbesondere vergleicht _public_mutant_function (Zeilen 345–352) den gespeicherten ursprünglichen Funktionskörper mit dem bereits erzeugten Quell-CST, nicht erneut mit der Datei. Das Backup erhält in Zeile 611 ebenfalls nur die zuvor gelesenen Bytes. Ein späterer Vergleich mit dem aktuellen Quellinhalt fehlt. Der Atomic-Writer kontrolliert Parent und temporäre Datei und ersetzt das Ziel in atomic_file.py:391 mittels temp_path.replace(path); die Prüfung in Zeilen 397–403 bestätigt erst anschließend die Identität der eigenen Veröffentlichung. Sie entdeckt keine vorher abgeschlossene Editorspeicherung. Auch die CLI-Locks in cli.py:1073–1076 liefern keinen Gegenbeweis: WorkspaceRunLock sperrt seine gesonderte Guard-Datei (process/run_lock.py:521, 547–555), DatabaseRunLocks ausschließlich Datenbank-Lockpfade. Die Quelldatei bleibt während der CST-Verarbeitung nicht gesperrt. Damit ist die beschriebene Reihenfolge mit erfolgreicher, bereits geschlossener Editorspeicherung erreichbar: S1 wird durch mutate(S0) ersetzt, während das Backup S0 enthält. test_source_protection.py:143–163 prüft Änderungen vor Beginn von apply_mutant; test_atomic_write_safety_220.py:184–212 und 229–254 prüfen sichere Backup-Ersetzung beziehungsweise fehlgeschlagene Veröffentlichung. Diese Tests decken eine Quelländerung zwischen Einlesen und Veröffentlichung nicht ab; ein entsprechender Test wurde bei der gezielten Suche nicht gefunden. Keine Tests oder Reproduktionen ausgeführt. High ist für diesen möglichen Verlust zwischenzeitlich gespeicherter Quelländerungen angemessen.

**Erreichbarkeit:** Am Ziel-HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b bestätigt. Das Zitat stimmt wörtlich und steht in mutant_diff.py:610–617; Zeile 617 ist der abschließende atomic_write_bytes-Aufruf. Die einzige Quellinhaltsprüfung erfolgt über _read_source_bytes_matching_staging (Zeilen 51–66), aufgerufen in Zeile 577. Danach werden ausschließlich die eingelesenen Bytes verarbeitet: beide CST-Parses in Zeilen 588–589, deep_replace in Zeile 608, Backup aus source_bytes in Zeile 611. Eine erneute Inhaltsprüfung oder eine gehaltene Quelldateisperre fehlt. Als Gegenbeweise geprüft: Der CLI-Kontext in cli.py:1074–1077 hält WorkspaceRunLock und DatabaseRunLocks; deren Windows-Sperre betrifft jedoch separate Guard-Dateien (process/run_lock.py:275–281, 499–505, 547–550), nicht die bearbeitete Quelldatei. atomic_file.py:388–403 prüft Parent und privaten temporären Pfad, ersetzt dann mit temp_path.replace(path) und kontrolliert anschließend die neu veröffentlichte Identität. Diese Nachkontrolle erkennt keinen zuvor gespeicherten und inzwischen überschriebenen Editorstand. Das Szenario ist daher über den regulären CLI-Apply erreichbar: gültiges Staging zu S0, Editor speichert S1 nach dem initialen Lesen und schließt seinen Handle, anschließend erfolgreiche Ersetzung durch mutate(S0). Eine möglicherweise vorübergehende Windows-Dateisperre widerlegt dieses ausdrücklich abgeschlossene Speichern nicht. Die Tests test_apply_refuses_stale_mutants (test_source_protection.py:143–163) und test_apply_creates_backup_with_original_content (:130–141) prüfen Drift vor Aufruf beziehungsweise unveränderten Ausgangsinhalt. test_apply_replace_failure_keeps_source_and_cleans_private_sibling (test_atomic_write_safety_220.py:229–254) prüft einen fehlgeschlagenen Replace. Der CLI-Lock-Test (test_run_surface_integration_220.py:303–316) prüft konkurrierende Lock-Nutzer. Keiner dieser Tests deckt den Editor-Save zwischen initialem Lesen und Veröffentlichung ab; ein entsprechender Regressionstest wurde bei der gezielten Testsuche nicht gefunden. High ist für möglichen Verlust gespeicherter Quelländerungen angemessen. Ausschließlich statisch geprüft; keine Tests oder Prozessreproduktionen ausgeführt.

<a id="lens-contracts-contract-04"></a>

#### CONTRACT-04: apply überschreibt Quelländerungen zwischen Staleness-Prüfung und Veröffentlichung

**high · toctou · Konfidenz hoch** — `lens:contracts` — [src/mutmut_win/mutant_diff.py:617](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutant_diff.py:617)

**Mechanismus.** apply_mutant prüft den Quellhash einmal in Zeile577, liest/parst danach Module und baut CST-Ersetzung. Vor Replace wird die Quelle nicht erneut an diese Version gebunden. atomic_write_bytes prüft Parent/temp/publizierte Identität, nicht die bisherigen Zielbytes. Backup enthält nur frühen Snapshot.

**Fehlerszenario.** Während apply nach der Quellmomentaufnahme eine größere generierte Datei verarbeitet, speichert ein Editor eine Änderung an der Quelle und schließt seinen Schreibhandle vor der Veröffentlichung. Das erfolgreiche Replace überschreibt sie mit dem aus dem alten Snapshot gebauten Mutanten; auch das Backup enthält nur diesen alten Snapshot. Workspace- und Datenbanksperren betreffen separate Guarddateien und koordinieren den Editor nicht. Ein weiterhin offener Editorhandle kann das Replace verhindern; der Befund betrifft das beschriebene erfolgreiche Interleaving.

**Wörtlicher Beleg:**

```python
    backup_path = source_path.with_name(source_path.name + ".mutmut-orig.bak")
    atomic_write_bytes(backup_path, source_bytes, mode=source_mode)
    try:
        applied_bytes = new_module.code.encode(source_encoding)
    except UnicodeEncodeError as exc:
        msg = f"applied mutant cannot be represented in source encoding {source_encoding}: {exc}"
        raise MutationParseError(msg) from exc
    atomic_write_bytes(source_path, applied_bytes, mode=source_mode)
```

**Fixskizze.** Veröffentlichung an erwartete Quellidentität und geprüften Inhalt binden; bei Konflikt ohne Überschreiben abbrechen. Windows-Handle-/Sharing-Strategie prüfen; zusätzliche Vorabprüfung allein verkleinert nur das Fenster.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

**Zusätzliche Prüfbegründung:**

**Korrektheit:** Am geprüften HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat wörtlich mit src/mutmut_win/mutant_diff.py:610–617 überein. Die Quellbytes werden in Zeile 577 einmal gelesen und gegen den Generierungshash geprüft; anschließend entstehen CST, Backup und Ausgabe vollständig aus diesem Snapshot. Als mögliche Gegenbeweise geprüft: read_verified_generated_bytes validiert ausschließlich die Staging-Datei (file_setup.py:1380–1389), und _public_mutant_function vergleicht bereits eingelesene CST-Knoten (mutant_diff.py:349–352), nicht die aktuelle Quelldatei. atomic_file.py:388–403 prüft Elternverzeichnis, temporäre Datei und nach replace die Identität der eigenen Veröffentlichung; vor temp_path.replace(path) in Zeile 391 fehlt jede Prüfung der bisherigen Zielbytes oder Zielidentität. Die CLI-Sperren in cli.py:1073–1076 sperren separate Workspace-/Datenbank-Guarddateien (run_lock.py:79, 275–281, 499–505), nicht die Quelldatei. Ein Editor kann deshalb nach der Snapshot-Lektüre speichern und seinen Schreibhandle schließen; erfolgt danach replace erfolgreich, gehen seine gespeicherten Änderungen am Quellpfad verloren. Das Backup enthält ebenfalls nur den früheren Snapshot. Windows-Sharingverletzungen können einzelne Abläufe verhindern, schließen diesen Ablauf aber nicht aus. test_source_protection.py:143–163 prüft Änderungen vor Aufruf von apply_mutant; der Backuptest :130–141 prüft einen unveränderten Ausgangszustand. test_atomic_write_safety_220.py:229–254 erzwingt einen fehlgeschlagenen replace, und test_run_surface_integration_220.py:303–316 prüft die kooperative Workspace-Sperre. Diese Tests widerlegen die beschriebene Konkurrenz zwischen Snapshot und erfolgreicher Veröffentlichung nicht; eine genau diesen Ablauf abdeckende Regression wurde nicht gefunden. Ausschließlich statisch geprüft, keine Tests oder Reproduktionen ausgeführt. Die Schwere high ist für diesen bedingten Verlust gespeicherter Quelländerungen angemessen.

**Erreichbarkeit:** HEAD entspricht 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b. Das Belegzitat stimmt wörtlich mit src/mutmut_win/mutant_diff.py:610–617 überein. Die einzige Quellinhaltsprüfung erfolgt über Zeile 577: _read_source_bytes_matching_staging liest in Zeile 57 mittels read_bytes(), vergleicht in Zeilen 58–59 den Hash und gibt ausschließlich die gelesenen Bytes zurück. Es bleibt kein Quellhandle bis zur Veröffentlichung offen. Auch die zusätzliche Originalkörperprüfung in Zeilen 349–352 vergleicht lediglich bereits eingelesene CST-Module. Ein normaler Editor kann daher nach dieser Momentaufnahme eine Änderung speichern und seinen Schreibhandle vor der Veröffentlichung schließen. Anschließend ersetzt atomic_file.py:391 mit 'temp_path.replace(path)' die inzwischen geänderte Quelle. Die Prüfungen davor betreffen Parent und temporäre Datei; Zeilen 397–403 kontrollieren danach ausschließlich die Identität der neu veröffentlichten Datei. Dieses Interleaving erfüllt sämtliche Prüfungen. Der CLI-Pfad ist über cli.py:1063–1102 erreichbar; seine Workspace-/Datenbanksperren sperren separate Guard-Dateien (process/run_lock.py:499–550, 771–806), nicht die Quelldatei. Das Backup enthält ausdrücklich source_bytes aus der frühen Momentaufnahme. test_source_protection.py:143–163 prüft nur eine Änderung vor dem apply-Aufruf; der Backuptest in Zeilen 130–141 enthält keine zwischenzeitliche Änderung. test_atomic_write_safety_220.py:184–212 und 229–254 decken Linkschutz beziehungsweise fehlgeschlagenes Replace ab, keinen erfolgreich abgeschlossenen Editor-Speichervorgang zwischen Lesen und Replace. Der Locktest test_run_surface_integration_220.py:303–316 prüft ausschließlich kooperierende Workspace-Sperren. Kein Gegenbeweis gefunden. High ist wegen möglichem Verlust gespeicherter Quelländerungen angemessen. Die Aussage betrifft ein erreichbares Interleaving, nicht jeden parallelen Speichervorgang; insbesondere kann ein noch offener Editorhandle Replace blockieren. Prüfung ausschließlich statisch; keine Tests oder Reproduktionen ausgeführt.

<a id="mod-cli-cli-01"></a>

#### CLI-01: --since-commit behandelt Eingaben als Git-Optionen oder Pfadspezifikationen

**medium · api-contract · Konfidenz hoch** — `mod:cli` — [src/mutmut_win/cli.py:578](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:578)

**Mechanismus.** Der als Commit deklarierte Wert wird ohne vorherige Commit-Auflösung oder Optionsgrenze an git diff übergeben. Eine gültige Git-Option oder Pfadspezifikation kann Exitcode 0 liefern und entgeht deshalb der Rückgabecodeprüfung.

**Fehlerszenario.** run --since-commit=--output=report.txt kann eine vorhandene beschreibbare Reportdatei durch Git-Ausgabe überschreiben. Git-stdout bleibt leer; die CLI meldet anschließend einen erfolgreichen No-op beziehungsweise ein leeres JSON-Ergebnis. Ein vorhandener Ordner ohne gleichnamige Revision kann stattdessen nur unstaged Pfadänderungen auswählen. Die Kombination mit --min-score wird vorgelagert abgewiesen; ein Projekt-Score-Gate-Bypass ist damit nicht belegt.

**Wörtlicher Beleg:**

```python
["git", "diff", "--name-only", "-z", since_commit]
```

**Fixskizze.** Mit git rev-parse --verify --end-of-options Commit auflösen, nur Objekt-ID an diff geben und Revisions-/Pfadgrenze -- setzen; Optionen und Nicht-Ref-Pfade abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. --since-commit übergibt einen ungeprüften String als Git-Argument. Dadurch sind Git-Optionen mit Dateischreibwirkung und existierende Pfadargumente erreichbar. Beim --output-Beispiel bleibt das Git-stdout leer; die CLI selbst gibt anschließend ihre No-op-Meldung beziehungsweise ein leeres Ergebnis als JSON aus.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-cli-cli-02"></a>

#### CLI-02: Inkrementelle Läufe aus Git-Unterprojekten verlieren geänderte Quelldateien

**medium · correctness · Konfidenz mittel** — `mod:cli` — [src/mutmut_win/cli.py:604](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:604)

**Mechanismus.** git diff --name-only liefert normalerweise gitwurzelrelative Namen. CLI behandelt sie projekt-cwd-relativ; --relative oder Umrechnung fehlt.

**Fehlerszenario.** Der Aufruf erfolgt mit gültigem --since-commit aus services/api eines Monorepos. Bei standardmäßig gitwurzelrelativer Diff-Ausgabe meldet Git services/api/src/mod.py; exists prüft unter dem Projekt-cwd den doppelt präfigierten Pfad und verwirft die reale Änderung. Werden dadurch alle Kandidaten entfernt, endet der Lauf erfolgreich als No-op. Aufruf aus der Gitwurzel oder diff.relative=true vermeiden diesen konkreten Mechanismus; ein Score-Gate wird wegen des Verbots von --min-score mit --since-commit nicht bestanden. Die Git-Semantik wurde nicht dynamisch reproduziert.

**Wörtlicher Beleg:**

```python
if not name.casefold().endswith(".py") or not Path(name).exists():
                    return False
```

**Fixskizze.** Diff auf Projektverzeichnis beziehen oder Git-Wurzel kontrolliert nach Projektpfad umrechnen; Unterprojekt mit echter Git-Semantik abdecken.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: medium. Bei Aufrufen von --since-commit aus einem Git-Unterprojekt werden gitwurzelrelative Diff-Pfade ohne Umrechnung als projektrelative Pfade behandelt. Unter üblicher Git-Konfiguration können dadurch vorhandene geänderte Quelldateien verworfen werden und der Lauf erfolgreich als No-op enden.
- Erreichbarkeit: angenommen, Konfidenz mittel. Vorgeschlagene Schwere: medium. Bei einem Aufruf mit gültigem --since-commit aus einem Git-Unterprojekt und standardmäßig gitwurzelrelativer Diff-Ausgabe verwirft die CLI tatsächlich geänderte Python-Quelldateien, deren gitwurzelrelativer Name unter dem Projekt-cwd nicht existiert. Werden dadurch alle Kandidaten verworfen, endet der Lauf irrtümlich erfolgreich als No-op.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-cli-cli-03"></a>

#### CLI-03: Absolute Testpfade und '..'-Aliase umgehen den inkrementellen Testausschluss

**medium · correctness · Konfidenz hoch** — `mod:cli` — [src/mutmut_win/cli.py:598](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:598)

**Mechanismus.** Testausschluss vergleicht nur Path.parts nach äußerem Separatorstrip. Absolute Pfade und '..' bleiben anders als Git-Namen, obwohl Config/pytest sie erlauben. Discovery hat keinen weiteren tests_dir-Ausschluss.

**Fehlerszenario.** tests_dir=['tests/../tests'] oder ein vollständig absoluter projektinterner Testpfad ist konfiguriert. Git meldet eine vorhandene geänderte tests/test_mod.py mit mutierbarem Funktionsinhalt; der Präfixvergleich scheitert. Ohne zusätzliches do_not_mutate-Muster wird die Testdatei als paths_to_mutate ausgewählt und ihre Staging-Kopie mutiert. Die Originaldatei bleibt unverändert. Gewöhnliche '.'-Komponenten sind nicht betroffen, da Path.parts sie bereits normalisiert.

**Wörtlicher Beleg:**

```python
tests_dir_parts = tuple(
                _comparison_parts(target.split("::", 1)[0].strip("/").strip("\\"))
                for target in config.tests_dir
            )
```

**Fixskizze.** Node-ID abtrennen und Tests/Änderungen auf gleiche kanonische Projektbasis normalisieren; absolute interne Pfade und '..' testen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei --since-commit umgehen absolute interne tests_dir-Pfade und relative Schreibweisen mit '..' den Testausschluss. Ohne zusätzliche Ausschlussmuster können dadurch geänderte Testdateien als Mutationsquellen ausgewählt und ihre Staging-Kopien mutiert werden. Eine Veränderung der ursprünglichen Testdatei ist damit nicht belegt.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Vollständig absolute projektinterne tests_dir-Pfade sowie relative Pfade mit auflösbaren '..'-Komponenten umgehen bei --since-commit den Testausschluss. Betroffene geänderte Testdateien werden ohne zusätzliches do_not_mutate-Muster als Mutationsquellen ausgewählt und können in mutants/ instrumentiert werden. Die Originaldateien werden dadurch nicht überschrieben. Nicht jede normalisierbare Schreibweise ist betroffen: gewöhnliche '.'-Komponenten normalisiert Path.parts bereits.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-cli-cli-05"></a>

#### CLI-05: Ctrl-C vor Workerphase verletzt dokumentierten Exit-130-Vertrag

**medium · error-handling · Konfidenz hoch** — `mod:cli` — [src/mutmut_win/cli.py:738](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:738)

**Mechanismus.** Die CLI behandelt einen Interrupt nur über result.was_interrupted. Einen frühen KeyboardInterrupt persistiert der Orchestrator und wirft ihn anschließend erneut; die CLI fängt nur MutmutWinError. Click übersetzt den weitergereichten Interrupt in Abort und Exitcode 1, sodass reguläre JSON-Ausgabe und Exitcode 130 unerreicht bleiben.

**Fehlerszenario.** Ctrl-C während Generation, Clean-Run oder Stats führt zu Exitcode 1 und bei --output json zu keinem Ergebnisdatensatz. Ein Interrupt im Workerloop liefert dagegen Exitcode 130 und einen Teilbericht. README.md:190–194 verspricht allgemein Exitcode 130.

**Wörtlicher Beleg:**

```python
result = orchestrator.dry_run() if dry_run else orchestrator.run()
        except MutmutWinError as exc:
```

**Fixskizze.** KeyboardInterrupt nach dem Cleanup an der CLI einheitlich auf Exitcode 130 abbilden; für JSON einen definierten Interruptdatensatz oder Teilsnapshot ausgeben. Tatsächlich geworfene frühe Interrupts prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-cli-cli-06"></a>

#### CLI-06: --treat-timeout-as-kill verändert Gate, aber nicht ausgegebenen Run-Score

**medium · api-contract · Konfidenz hoch** — `mod:cli` — [src/mutmut_win/cli.py:756](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:756)

**Mechanismus.** Run-JSON und Text verwenden result.score mit treat_timeout_as_kill=False. Erst das Score-Gate verwendet das Flag, das nicht an den Orchestrator weitergereicht wird.

**Fehlerszenario.** Ein vollständiger, qualifizierter Lauf bearbeitet zehn Mutanten: fünf Kills und fünf reguläre Timeouts. Mit --treat-timeout-as-kill --min-score 100 --output json besteht das Gate nach der ausdrücklich gewählten Policy, während der ausgegebene score 50.0 bleibt. Die Textzusammenfassung zeigt ebenfalls 50 %, das Kommando results mit demselben Flag dagegen 100 %. Der Befund betrifft widersprüchliches Reporting, nicht einen Gate-Erfolg entgegen der gewählten Policy.

**Wörtlicher Beleg:**

```python
click.echo(result.model_dump_json(indent=2))
...
gate_score = result.compute_score(treat_timeout_as_kill=treat_timeout_as_kill)
```

**Fixskizze.** Effektive Scoring-Policy und Gate-Score konsistent in Text/JSON ausgeben oder eindeutig zusätzlich zu Rohscore benennen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-cli-cli-07"></a>

#### CLI-07: show kann über umgeleitete mutants-Wurzel externe Metadaten löschen

**medium · correctness · Konfidenz hoch** — `mod:cli` — [src/mutmut_win/cli.py:1036](C:/claude_codex/mutmut-win-astra/src/mutmut_win/cli.py:1036)

**Mechanismus.** show prüft für mutants lediglich is_dir, ohne die Wurzel auf Umleitung zu prüfen oder einen Lock zu erwerben. resolve_mutant lädt Quellmetadaten standardmäßig mit heal_corrupt=True; ungültiges JSON oder ein abgelehntes Schema führt über _discard_corrupt_meta zu unlink. Eine Junction besteht die is_dir-Prüfung.

**Fehlerszenario.** Eine gültige Konfiguration nennt die reguläre lokale Quelle src/mod.py. mutants ist eine vorbereitete Windows-Junction auf ein externes Verzeichnis; dort existiert eine lesbare und löschbare src/mod.py.meta mit ungültigem JSON oder abgelehntem Schema. Schon show mit einem letztlich nicht passenden Mutantennamen kann diese externe Datei während der Auflösung löschen. Ein vorheriger erfolgreicher Lauf und ein Wettlauf sind dafür nicht nötig; die Wirkung ist auf die passend abgeleiteten Metadatenpfade begrenzt.

**Wörtlicher Beleg:**

```python
resolved_name, data = resolve_mutant(mutant_name, config)
...
m = SourceFileMutationData(path=str(path))
        m.load()
...
with contextlib.suppress(OSError):
            self.meta_path.unlink()
```

**Fixskizze.** Vor Metadatenberührung umgeleitete Wurzeln ablehnen; lesende Auflösung heal_corrupt=False, Heilung nur unter Schreiblock.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-data-data-02"></a>

#### DATA-02: Einzeilige setup.cfg-Regexe werden an Quantifizierer-Kommas zerlegt

**medium · correctness · Konfidenz hoch** — `mod:data` — [src/mutmut_win/config.py:479](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:479)

**Mechanismus.** Der generische INI-Listenparser trennt jeden einzeiligen Listenwert an allen Kommas und wird auch für do_not_mutate_patterns verwendet. Ein Regex-Quantifizierer wie {1,3} wird dadurch in zwei Fragmente zerlegt. Beide können weiterhin gültige reguläre Ausdrücke sein; der Validator prüft nur deren Kompilierbarkeit und erkennt den Bedeutungswechsel nicht.

**Fehlerszenario.** setup.cfg ist die wirksame Konfiguration und enthält einzeilig do_not_mutate_patterns=^f[0-9]{1,3}$. Die gewöhnlichen mutierbaren Funktionen f1 und f123 sollen ausgeschlossen werden. Tatsächlich werden '^f[0-9]{1' und '3}$' geladen; beide kompilieren, treffen diese Namen aber nicht, sodass die Funktionen mutiert werden. Ein mehrzeiliger Parserwert mit eingerückter Fortsetzungszeile umgeht den Kommasplit.

**Wörtlicher Beleg:**

```python
return [x.strip() for x in result.split(",") if x.strip()]
```

**Fixskizze.** Für Regexlisten eine eindeutige Darstellung über Zeilen oder definierte Quotierung verwenden. Vorhandene einfache Kommalisten kompatibel behandeln und Quantifizierer-Kommas gezielt prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-presentation-view-01"></a>

#### VIEW-01: Lesende Mutantenauflösung kann Sidecars außerhalb des Workspace löschen

**medium · phase-order · Konfidenz hoch** — `mod:presentation` — [src/mutmut_win/mutant_diff.py:125](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutant_diff.py:125)

**Mechanismus.** resolve_mutant lädt Sidecars mit dem Standard heal_corrupt=True, bevor es den angefragten Namen abgleicht. Ungültiges JSON oder abgelehnte Feldtypen können dabei zur Löschung führen. show prüft vorher lediglich is_dir; die spätere Prüfung generierten Codes kommt zu spät. Der Browser schützt zwar seine Metadatenübersicht mit Eigentumsprüfung und heal_corrupt=False, kann denselben heilenden Auflösungspfad aber beim Diff-Fallback erreichen.

**Fehlerszenario.** Eine reguläre lokale Quelle src/mod.py ist konfiguriert. mutants oder eine übergeordnete Komponente des Sidecar-Pfads, etwa mutants/src, ist als Junction oder Verzeichnissymlink auf einen externen Ordner umgeleitet. Liegt dort eine lesbare und löschbare mod.py.meta mit Inhalt, der die Korruptionsbehandlung auslöst, kann schon show mit unbekanntem Namen diese Datei löschen. Ohne Umleitung betrifft eine fremde Fixture nur den entsprechend abgeleiteten .py.meta-Pfad. Im Browser gilt der Pfad für DB-Mutanten ohne zugeordnete Metadatenquelle; das bloße Laden der Übersicht ist abgesichert.

**Wörtlicher Beleg:**

```python
        m = SourceFileMutationData(path=str(path))
        m.load()
        matches.extend((key, m) for key in match_mutant_names([pattern], m.exit_code_by_key))
```

**Fixskizze.** Anzeige und Namensauflösung ohne heilende Schreibzugriffe ausführen. Wurzel und Pfadkomponenten vor jedem Metadatenzugriff prüfen; löschende Heilung ausschließlich unter einem ausdrücklichen Schreib- und Eigentumsvertrag erlauben.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. show kann beim Auflösen auch eines unbekannten Mutantennamens eine beschädigte Sidecar-Datei außerhalb des Workspace löschen, wenn mutants oder ein übergeordneter Sidecar-Verzeichnisbestandteil durch eine Junction beziehungsweise einen Verzeichnissymlink umgeleitet ist und entsprechende Dateirechte bestehen. Ohne Umleitung betrifft dies eine fremde Fixture nur an dem aus einer ausgewählten lokalen Python-Quelle abgeleiteten .py.meta-Pfad. Im Browser betrifft der belegte Auflösungspfad die Diff-Anzeige aus DB-Ergebnissen ohne Metadatenzuordnung, nicht die geschützte Metadatensuche selbst.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: high. show kann bereits bei einem unbekannten Mutantennamen einen vorhandenen, löschbaren Sidecar für eine konfigurierte lokale Quelle außerhalb des Workspace löschen, wenn mutants oder eine Sidecar-Elternkomponente dorthin umgeleitet ist und der Inhalt die Korruptionsbehandlung auslöst. Die Browser-Diffanzeige erreicht denselben Pfad für angezeigte DB-Mutanten ohne zugeordneten Metadatenpfad; das bloße Laden der Browserübersicht ist dagegen abgesichert.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-presentation-view-03"></a>

#### VIEW-03: Fallback kann den Diff eines anderen Moduls anzeigen

**medium · correctness · Konfidenz hoch** — `mod:presentation` — [src/mutmut_win/browser.py:166](C:/claude_codex/mutmut-win-astra/src/mutmut_win/browser.py:166)

**Mechanismus.** Scheitert die qualifizierte Auflösung, entfernt der Browser das Modulpräfix und verwendet den ersten passenden lokalen Funktionsnamen. Der Renderer prüft die Quell- und Staging-Hashes dieses gefundenen Moduls sowie dessen ursprünglichen Funktionsrumpf, aber nicht die Mitgliedschaft des angeforderten vollständig qualifizierten Mutantennamens in seinen Metadaten.

**Fehlerszenario.** Der aktuelle persistierte Run-Snapshot enthält b.x_f__mutmut_1. Nach Verlust nur von mutants/b.py.meta bleibt a.py mit gültigen Metadaten und demselben lokalen Mutantennamen erhalten. Die Auswahl von b unter '(metadata missing)' zeigt den Diff von a, falls der Fallback a zuerst findet. Ein bloßer historischer DB-Eintrag ohne aktuellen Run-Snapshot genügt bei vorhandenen a-Metadaten nicht.

**Wörtlicher Beleg:**

```python
        if f"def {local_name}" in content:
            return mutant_diff.render_function_diff(py_file.relative_to(mutants_dir), mutant_name)
```

**Fixskizze.** Den vollständig qualifizierten Mutantennamen mit dem Metadateninhaber abgleichen und bei fehlendem Herkunftsnachweis einen Fehler anzeigen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Enthält der aktuelle gespeicherte Run b.x_f__mutmut_1, fehlt dessen Metadatei und existiert ein unverändertes a-Modul mit gültigen Metadaten sowie demselben lokalen Mutantennamen, kann die Auswahl von b unter '(metadata missing)' den Diff von a anzeigen, wenn a beim Fallback zuerst gefunden wird. Ein bloßer historischer DB-Eintrag ohne Run-Snapshot genügt bei vorhandenen a-Metadaten nicht.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Enthält der aktuelle persistierte Run-Snapshot b.x_f__mutmut_1, fehlen dessen Metadaten und findet der Browser-Fallback zuerst ein anderes gültig generiertes Modul a mit demselben lokalen Mutantennamen, kann die Auswahl von b den Diff aus a anzeigen. Der erforderliche Herkunftsabgleich wird nach dem fehlgeschlagenen qualifizierten Lookup nicht wiederholt. Der Zustand ist über die ausdrücklich unterstützte Anzeige unzugeordneter aktueller Mutanten erreichbar.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-presentation-view-04"></a>

#### VIEW-04: Verspätete Diff-Ergebnisse überschreiben aktuelle Auswahl

**medium · race · Konfidenz hoch** — `mod:presentation` — [src/mutmut_win/browser.py:564](C:/claude_codex/mutmut-win-astra/src/mutmut_win/browser.py:564)

**Mechanismus.** Der Fehlerpfad veröffentlicht sein Ergebnis ohne Prüfung von _loading_id. Im Erfolgsfall liegt die Prüfung vor der Syntax-Aufbereitung und dem späteren UI-Callback; ein zwischenzeitlicher Auswahlwechsel wird bei der Veröffentlichung nicht erneut geprüft.

**Fehlerszenario.** Der Benutzer wechselt von A zu B. Nachdem der B-Diff erschienen ist, scheitert der noch laufende A-Thread etwa an einer inzwischen geänderten Quelldatei. Beschreibung und Markierung bleiben bei B, während dessen Diff durch den A-Fehler ersetzt wird. Auch ein erfolgreiches altes Ergebnis kann bei passender Reihenfolge zwischen Prüfung und Veröffentlichung veralten. Eine Änderung persistierter Ergebnisse ist damit nicht belegt.

**Wörtlicher Beleg:**

```python
            except Exception as exc:  # show all errors inline
                self.call_from_thread(diff_view.update, f"<{type(exc).__name__}: {exc}>")
```

**Fixskizze.** Erfolg und Fehler über einen gemeinsamen UI-Callback veröffentlichen, der einen monotonen Anfragezähler prüft. So auch den Wechsel A→B→A unterscheiden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Bei überlappenden Diff-Anforderungen kann ein verspäteter Fehler einer früheren Auswahl das Diff der aktuellen Auswahl überschreiben. Auch erfolgreiche Anforderungen besitzen zwischen Auswahlprüfung und Veröffentlichung ein ungeschütztes Zeitfenster; das Auftreten hängt von der Ausführungsreihenfolge ab.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-presentation-view-06"></a>

#### VIEW-06: Überlappende Mutationspfade machen eindeutige Namen künstlich mehrdeutig

**medium · correctness · Konfidenz hoch** — `mod:presentation` — [src/mutmut_win/mutant_diff.py:126](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutant_diff.py:126)

**Mechanismus.** resolve_mutant sammelt die Treffer jedes von walk_source_files gelieferten Pfads ohne Deduplizierung. Discovery durchläuft jeden konfigurierten Root separat, und die Konfigurationsvalidierung erhält doppelte beziehungsweise überlappende Roots. Die Deduplizierung des Generierungslaufs wirkt nur auf dessen lokale Quelldateiliste.

**Fehlerszenario.** Mit paths_to_mutate=['src', 'src/pkg'] wird src/pkg/mod.py zweimal gefunden. Der normale Generierungslauf kann gültige Metadaten erstellen, aber anschließend erzeugt selbst der exakte Mutantenname im Resolver zwei identische Treffer: show und apply melden AmbiguousMutantNameError und beenden sich mit Exitcode 1. Ein identisch wiederholter Root hat dieselbe Wirkung.

**Wörtlicher Beleg:**

```python
        matches.extend((key, m) for key in match_mutant_names([pattern], m.exit_code_by_key))

    if not matches:
        raise FileNotFoundError(f"Could not find mutant {pattern}")
    if len(matches) > 1:
```

**Fixskizze.** Quelldateien vor der Metadatenauflösung nach kanonischer Windows-Dateiidentität deduplizieren und nur Treffer verschiedener Dateien als mehrdeutig behandeln.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-rest-rest-01"></a>

#### REST-01: Mutantenauswahl ignoriert unter Windows die Groß- und Kleinschreibung

**medium · windows · Konfidenz hoch** — `mod:rest` — [src/mutmut_win/test_mapping.py:84](C:/claude_codex/mutmut-win-astra/src/mutmut_win/test_mapping.py:84)

**Mechanismus.** fnmatch.fnmatch normalisiert Namen unter Windows mit normcase. Mutantennamen enthalten dagegen Python-Bezeichner, deren Groß- und Kleinschreibung relevant ist. Die vorgelagerte exakte Mitgliedschaftsprüfung betrifft nur den jeweiligen Kandidaten; weitere Kandidaten werden auch bei einer Eingabe ohne Globs über fnmatch verglichen.

**Fehlerszenario.** Ein Modul enthält foo und Foo, beide mit einem Mutantenindex 1. Die exakte Eingabe pkg.mod.x_Foo__mutmut_1 wählt auch pkg.mod.x_foo__mutmut_1 aus. run übernimmt beide in den Auswahlumfang; show und apply lehnen den eigentlich eindeutigen Namen als mehrdeutig ab.

**Wörtlicher Beleg:**

```python
if candidate in pattern_list
        or any(fnmatch.fnmatch(candidate, pattern) for pattern in pattern_list)
```

**Fixskizze.** Bezeichner mit fnmatchcase vergleichen und exakte sowie Glob-Auswahlen mit ausschließlich in der Groß- und Kleinschreibung verschiedenen Funktionen absichern.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Unter Windows ignoriert die Mutantenauswahl auch bei exakter Namenseingabe die Groß-/Kleinschreibung weiterer Kandidaten. Existieren foo und Foo mit demselben Mutantenindex, werden beide ausgewählt; run nimmt beide in den Auswahlumfang auf, während show/apply die Anfrage als mehrdeutig ablehnen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-races-race-03"></a>

#### RACE-03: Veralteter Browser-Thread überschreibt Diff neuerer Auswahl

**medium · race · Konfidenz hoch** — `lens:races` — [src/mutmut_win/browser.py:559](C:/claude_codex/mutmut-win-astra/src/mutmut_win/browser.py:559)

**Mechanismus.** Die Auswahl-ID wird im Hintergrund vor dem UI-Dispatch geprüft. Die Auswahl kann nach dieser Prüfung noch wechseln; der später ausgeführte Callback prüft sie nicht erneut. Der Fehlerpfad besitzt gar keinen Guard. Beschreibung und Ziel einer Aktion stammen separat aus der aktuellen Tabellenzeile.

**Fehlerszenario.** A besteht die Auswahlprüfung und wird vor seinem Dispatch unterbrochen. Anschließend wählt der Benutzer B; Beschreibung und Diff von B erscheinen. Der spätere A-Callback ersetzt das gemeinsame Diff-Widget durch A. Alternativ kann ein verspäteter A-Fehler dieselbe Wirkung haben. Apply liest weiterhin die aktuelle Auswahl B: Die Anzeige kann irreführen, eine eigenständige Verwechslung der Apply-ID oder ein Datenverlust ist damit nicht nachgewiesen.

**Wörtlicher Beleg:**

```python
                if mutant_name == self._loading_id:
                    from rich.syntax import Syntax

                    self.call_from_thread(diff_view.update, Syntax(d, "diff"))
            except Exception as exc:  # show all errors inline
                self.call_from_thread(diff_view.update, f"<{type(exc).__name__}: {exc}>")
```

**Fixskizze.** Eine monotone Anfrage-ID unmittelbar im gemeinsamen UI-Callback prüfen, Erfolg und Fehler gleich behandeln und laufende Anfragen bei Auswahl- oder Datenwechsel invalidieren.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-failclosed-fail-01"></a>

#### FAIL-01: Lesefehler vorhandener setup.cfg werden zu Standardkonfiguration

**medium · error-handling · Konfidenz hoch** — `lens:failclosed` — [src/mutmut_win/config.py:462](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:462)

**Mechanismus.** ConfigParser.read überspringt Öffnungsfehler und liefert die tatsächlich gelesenen Dateien zurück. _load_setup_cfg ignoriert diesen Rückgabewert; der äußere OSError-Handler erfasst den bereits intern verschluckten Fehler nicht. Ohne gelesene mutmut-Sektion liefert der Helper None, worauf load_config Standardwerte übernimmt. Spätere Basisaufnahmen verwenden dieses bereits gewählte Konfigurationsobjekt und interpretieren den mutmut-Block nicht erneut.

**Fehlerszenario.** Ein nichtleerer gültiger [tool.mutmut]-Block hat keinen Vorrang. Die vorhandene setup.cfg enthält eigene Pfade, Ausschlüsse oder Testargumente; nach erfolgreicher Existenzprüfung scheitert das Öffnen kurzzeitig, etwa durch eine Windows-Lesesperre. Endet die Unlesbarkeit vor den späteren Basis- und Stagingprüfungen, kann der Lauf mit den still übernommenen Defaults fortfahren. Eine dauerhaft unlesbare Datei kann spätere Prüfungen dagegen scheitern lassen.

**Wörtlicher Beleg:**

```python
        parser.read(str(setup_cfg_path), encoding="utf-8")
    except (ConfigParserError, OSError) as exc:
        msg = f"Failed to read setup.cfg: {exc}"
        raise ConfigError(msg) from exc

...

    if not parser.has_section("mutmut"):
        return None
```

**Fixskizze.** Die benötigte Datei explizit öffnen und read_file verwenden. Nur belegte Abwesenheit als Fallback behandeln; andere Lesefehler als ConfigError melden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Wird setup.cfg als Konfigurationsquelle benötigt und scheitert ihr Öffnen nach erfolgreicher Existenzprüfung mit OSError, behandelt _load_setup_cfg() sie still wie eine Datei ohne [mutmut]-Sektion. load_config() verwendet daraufhin Standardwerte. Endet die Unlesbarkeit vor den späteren Basis- und Stagingprüfungen, erkennen diese die ursprüngliche Fehlinterpretation nicht.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Wenn kein nichtleerer gültiger [tool.mutmut]-Block Vorrang hat und ConfigParser die vorhandene setup.cfg wegen eines Öffnungsfehlers nicht lesen kann, behandelt load_config den Zustand wie eine fehlende mutmut-Sektion und übernimmt Defaults. Verschwindet das Hindernis vor den weiteren Dateiprüfungen, kann der normale Lauf mit dieser falschen Konfigurationsauswahl fortfahren.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-failclosed-fail-02"></a>

#### FAIL-02: Vorhandener TOML-Abschnitt mit falschem Typ wird still ignoriert

**medium · api-contract · Konfidenz hoch** — `lens:failclosed` — [src/mutmut_win/config.py:577](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:577)

**Mechanismus.** load_config behandelt einen vorhandenen tool.mutmut-Abschnitt mit einem falschen Typ wie einen fehlenden oder leeren Abschnitt. Eine Tabellenliste erreicht deshalb weder die Schlüsselprüfung noch die Modellvalidierung, sondern unmittelbar den INI- beziehungsweise Default-Fallback.

**Fehlerszenario.** Ein Projekt verwendet syntaktisch gültiges [[tool.mutmut]] anstelle der erwarteten Tabelle und trägt dort paths_to_mutate=['src/a.py'] sowie einen Ausschluss für src/b.py ein. Ohne setup.cfg verwirft load_config die Liste ohne Diagnose. Bei vorhandenem src-Verzeichnis wählt die Standardheuristik stattdessen src, und die Ausschlüsse bleiben leer. Die regulären weiteren Prüfungen arbeiten bereits mit dieser Ersatzkonfiguration.

**Wörtlicher Beleg:**

```python
    tool_config = data.get("tool", {}).get("mutmut", {})
    if not isinstance(tool_config, dict) or not tool_config:
        # No [tool.mutmut] section — try setup.cfg before returning defaults
        setup_cfg_config = _load_setup_cfg(project_dir)
        if setup_cfg_config is not None:
            return _apply_default_also_copy(setup_cfg_config, project_dir)
        return _apply_default_also_copy(MutmutConfig(), project_dir)
```

**Fixskizze.** Einen fehlenden Abschnitt getrennt von einem vorhandenen Abschnitt falschen Typs behandeln. Letzteren vor jedem Fallback als ConfigError ablehnen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: medium. Ein syntaktisch gültiger, für mutmut jedoch falsch typisierter tool.mutmut-Abschnitt, beispielsweise [[tool.mutmut]], wird ohne Diagnose verworfen. Bei gültiger setup.cfg oder vorhandenen Standardquellpfaden kann der Lauf deshalb andere Mutationseinstellungen einschließlich anderer Pfade und fehlender Ausschlüsse verwenden.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-boundaries-edge-06"></a>

#### EDGE-06: Doppelte Quellwurzel macht einen exakten Mutantennamen für show/apply mehrdeutig

**medium · correctness · Konfidenz hoch** — `lens:boundaries` — [src/mutmut_win/mutant_diff.py:126](C:/claude_codex/mutmut-win-astra/src/mutmut_win/mutant_diff.py:126)

**Mechanismus.** walk_source_files liefert Dateien für jeden Konfigurationseintrag erneut. Die Generierung dedupliziert mit seen_sources, resolve_mutant zählt denselben Sidecar-Treffer mehrfach. Die Mehrdeutigkeitsprüfung unterscheidet nicht zwischen mehrfach besuchtem und tatsächlich unterschiedlichem Mutanten.

**Fehlerszenario.** Mit paths_to_mutate=['src/', 'src/'] oder ['src/', 'src/pkg/'] und einer gewöhnlichen, nicht ausgeschlossenen Datei im gemeinsamen Bereich kann die Generierung gültige Metadaten erzeugen. Anschließendes show oder apply findet denselben exakten Schlüssel zweimal und scheitert mit AmbiguousMutantNameError und Exitcode 1. Die Staging-Prüfung erlaubt dieselbe reale Quelle ausdrücklich; nur die Generierung dedupliziert lokal.

**Wörtlicher Beleg:**

```python
matches.extend((key, m) for key in match_mutant_names([pattern], m.exit_code_by_key))
...
if len(matches) > 1:
```

**Fixskizze.** Quellidentitäten vor Sidecar-Laden entsprechend der Generierung deduplizieren; echte Namenskollisionen weiterhin ablehnen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-data-data-01"></a>

#### DATA-01: Ungültige setup.cfg-Werte umgehen Konfigurationsfehlerbehandlung

**low · error-handling · Konfidenz hoch** — `mod:data` — [src/mutmut_win/config.py:539](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:539)

**Mechanismus.** _load_setup_cfg reicht Pydantic-Validierungsfehler unverpackt weiter. Seine Fehlerbehandlung umfasst nur parser.read. Die entsprechende TOML-Modellvalidierung wird dagegen in InvalidConfigValueError übersetzt; die CLI fängt beim Laden ausschließlich ConfigError.

**Fehlerszenario.** Ein Projekt verwendet setup.cfg mit '[mutmut]' und 'max_children=0', ohne eine vorrangige wirksame TOML-Konfiguration. Schon run --dry-run --output json erreicht die Modellvalidierung und lässt ValidationError entweichen. Die vorgesehene Konfigurationsmeldung, das JSON-Fehlerobjekt und Exitcode 2 werden umgangen.

**Wörtlicher Beleg:**

```python
return MutmutConfig.model_validate(normalized, context={"project_root": project_dir.resolve()})
```

**Fixskizze.** Beide Konfigurationsformate über eine gemeinsame Validierungsgrenze führen und Wertefehler mit Formatkontext in InvalidConfigValueError übersetzen. Neben INI-Syntaxfehlern auch ungültige INI-Modellwerte samt CLI-Ausgabe prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Wenn setup.cfg als Konfigurationsquelle ausgewählt wird, entweichen Pydantic-Wertefehler, etwa für [mutmut] max_children=0, unverpackt aus load_config und umgehen dadurch die CLI-Konfigurationsfehlerbehandlung einschließlich JSON-Fehlerausgabe.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-data-data-04"></a>

#### DATA-04: Falscher TOML-Typ von tool führt zu unbehandeltem AttributeError

**low · error-handling · Konfidenz hoch** — `mod:data` — [src/mutmut_win/config.py:576](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:576)

**Mechanismus.** load_config setzt voraus, dass der Wert des TOML-Wurzelschlüssels tool ein Dictionary ist. Die Typprüfung betrifft erst den darunterliegenden mutmut-Wert und erfolgt nach dem ungeschützten zweiten .get. Der vorherige Handler umfasst lediglich Einlesen und TOML-Parsing.

**Fehlerszenario.** Eine pyproject.toml enthält auf oberster Ebene tool=1 oder tool=[]. Das ist gültige TOML-Syntax, aber eine fehlerhafte pyproject-Struktur. Ein direkter installierter Konsolenaufruf wie mutmut-win run --dry-run erreicht AttributeError statt ConfigError und umgeht die formatierte CLI-Konfigurationsmeldung. Eine mögliche Vorabprüfung durch uv verhindert diesen direkten Einstieg nicht.

**Wörtlicher Beleg:**

```python
tool_config = data.get("tool", {}).get("mutmut", {})
```

**Fixskizze.** Die Typen von tool und tool.mutmut getrennt vor dem Zugriff prüfen. Fehlende Abschnitte ausdrücklich von vorhandenen Werten des falschen Typs unterscheiden.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-data-data-05"></a>

#### DATA-05: Nicht decodierbare Konfiguration entkommt ConfigError-Vertrag

**low · error-handling · Konfidenz hoch** — `mod:data` — [src/mutmut_win/config.py:572](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:572)

**Mechanismus.** Die TOML-Ladegrenze fängt TOMLDecodeError und OSError; die INI-Ladegrenze fängt ConfigParserError und OSError. UnicodeDecodeError gehört zu keiner dieser Gruppen und entsteht bereits beim Decodieren vor der Formatvalidierung. Die CLI übersetzt anschließend nur ConfigError.

**Fehlerszenario.** Die tatsächlich geladene pyproject.toml oder ausgewählte setup.cfg-Fallbackdatei enthält ungültige UTF-8-Bytes, etwa eine UTF-16-BOM. Ein direkter Aufruf wie run --dry-run lässt UnicodeDecodeError entweichen und umgeht die vorgesehene Konfigurationsmeldung samt Exitcode 2. Eine vorrangige TOML-Konfiguration kann den INI-Fallback vermeiden; UTF-16 ohne BOM muss nicht zwingend diesen Decodierungsfehler auslösen.

**Wörtlicher Beleg:**

```python
except (tomllib.TOMLDecodeError, OSError) as e:
```

**Fixskizze.** UnicodeDecodeError an beiden Ladegrenzen mit Dateiname und erwartetem Encoding in ConfigError übersetzen. Ungültige UTF-8-Bytes zusätzlich zu Syntax- und Wertefehlern prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Nicht als UTF-8 decodierbare pyproject.toml-Dateien sowie tatsächlich ausgewählte setup.cfg-Fallbackdateien lassen UnicodeDecodeError statt ConfigError durch. UTF-16 mit BOM ist ein konkretes Beispiel; nicht jede UTF-16-Datei muss zwingend einen Decodierungsfehler auslösen.
- Erreichbarkeit: angenommen, Konfidenz hoch. Vorgeschlagene Schwere: low. Enthält die tatsächlich geladene Konfigurationsdatei ungültige UTF-8-Bytes, beispielsweise durch UTF-16-Speicherung mit BOM, entkommt UnicodeDecodeError dem ConfigError-/Exit-2-Vertrag. UTF-16 ohne BOM verursacht nicht zwangsläufig einen Decodierungsfehler.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="mod-presentation-view-05"></a>

#### VIEW-05: Leere Mutantentabelle behält Beschreibung und Diff vorheriger Datei

**low · correctness · Konfidenz hoch** — `mod:presentation` — [src/mutmut_win/browser.py:479](C:/claude_codex/mutmut-win-astra/src/mutmut_win/browser.py:479)

**Mechanismus.** Ein Dateiwechsel leert nur die Mutantentabelle; Beschreibung, Diff und _loading_id bleiben erhalten. Hat die neue Datei keine sichtbaren Mutanten, aktualisiert kein gültiges Mutantenauswahlereignis diese Felder.

**Fehlerszenario.** Bei show_killed=False betrachtet der Benutzer einen überlebenden Mutanten aus A und wählt anschließend Datei B mit ausschließlich getöteten Mutanten. B ist markiert und die Tabelle leer, aber die Detailanzeige enthält weiterhin A. Ein noch laufender A-Thread darf diese Anzeige weiter aktualisieren. Aktionen auf den alten Mutanten werden durch die Prüfung der leeren Tabelle verhindert.

**Wörtlicher Beleg:**

```python
        mutants_table: DataTable[str] = self.query_one("#mutants", DataTable)
        mutants_table.clear()
```

**Fixskizze.** Bei jedem Dateiwechsel die laufende Anfrage invalidieren und Beschreibung sowie Diff leeren oder einen passenden Leerhinweis anzeigen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch.
- Erreichbarkeit: angenommen, Konfidenz hoch.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

<a id="lens-contracts-contract-02"></a>

#### CONTRACT-02: Ungültige setup.cfg-Werte umgehen den zugesagten Konfigurationsfehlerkanal

**low · error-handling · Konfidenz hoch** — `lens:contracts` — [src/mutmut_win/config.py:539](C:/claude_codex/mutmut-win-astra/src/mutmut_win/config.py:539)

**Mechanismus.** _load_setup_cfg gibt Pydantic-Validierungsfehler unverändert weiter. TOML verpackt diese als InvalidConfigValueError. Der CLI-Loader fängt nur ConfigError für Meldung ohne Traceback, Exitcode2 und JSON-Fehlerobjekt.

**Fehlerszenario.** setup.cfg wird tatsächlich als Konfigurationsquelle gewählt, etwa ohne pyproject.toml oder ohne vorrangige wirksame [tool.mutmut]-Tabelle, und enthält [mutmut] mit max_children=0. Bereits run --dry-run --output json lässt ValidationError entweichen. Der vorgesehene ConfigError-Pfad mit JSON-Fehlerobjekt und Exitcode 2 wird umgangen; falsche Mutationsergebnisse werden dadurch nicht bestätigt.

**Wörtlicher Beleg:**

```python
    return MutmutConfig.model_validate(normalized, context={"project_root": project_dir.resolve()})
```

**Fixskizze.** Modellvalidierung beider Quellen gemeinsam in InvalidConfigValueError abbilden; INI-Zahlen/Regex/JSON-CLI-Fälle prüfen.

**Gegenprüfung:**

- Korrektheit: angenommen, Konfidenz hoch. Wird setup.cfg tatsächlich als Konfigurationsquelle gewählt, entkommt beispielsweise max_children=0 als Pydantic ValidationError statt InvalidConfigValueError. run --output json erreicht dadurch weder das vorgesehene JSON-Fehlerobjekt noch den Konfigurationsfehler-Exitcode 2.
- Erreichbarkeit: angenommen, Konfidenz hoch. Wenn setup.cfg als Konfigurationsquelle ausgewählt wird, lässt etwa [mutmut] mit max_children=0 einen Pydantic-ValidationError unverändert entweichen. Dadurch wird auch bei run --output json der vorgesehene ConfigError-Pfad mit JSON-Fehlerobjekt und Exitcode 2 umgangen.

Die vollständigen unveränderten Prüfbegründungen stehen im gleichnamigen Eintrag der JSON-Fassung.

## Überschneidungen unabhängiger Finder

Diese Gruppen dienen der gemeinsamen Behebung. Kandidaten und Urteile bleiben einzeln erhalten; abweichende Einschränkungen sind am jeweiligen Eintrag zu beachten.

- **Phase-Proof-Decoding überspringt Task-Cleanup:** [nondet:process-lifecycle/PROC-01](#nondet-process-lifecycle-proc-01), [mod:worker/WORK-02](#mod-worker-work-02), [lens:resources/RES-01](#lens-resources-res-01), [lens:contracts/CONTRACT-07](#lens-contracts-contract-07).
- **Jobhandle-Leck bei unvollständiger Executor-Konstruktion:** [nondet:process-lifecycle/PROC-03](#nondet-process-lifecycle-proc-03), [mod:spawn/SPAWN-04](#mod-spawn-spawn-04), [lens:resources/RES-04](#lens-resources-res-04).
- **Executor-Cleanup vor dem Ausführungs-try:** [mod:orchestrator/ORCH-01](#mod-orchestrator-orch-01), [mod:cli/CLI-04](#mod-cli-cli-04), [lens:resources/RES-05](#lens-resources-res-05), [lens:contracts/CONTRACT-05](#lens-contracts-contract-05).
- **Capture-Konstruktor verliert rohe Pipe-Deskriptoren:** [mod:spawn/SPAWN-03](#mod-spawn-spawn-03), [lens:resources/RES-03](#lens-resources-res-03).
- **Doppeltes Schließen eines wiederverwendbaren Dateideskriptors:** [mod:atomic/ATOM-01](#mod-atomic-atom-01), [lens:resources/RES-02](#lens-resources-res-02).
- **Temporäre Dateinamen überschreiten Komponentenlimit:** [mod:atomic/ATOM-04](#mod-atomic-atom-04), [lens:windows/WIN-01](#lens-windows-win-01).
- **Readonly-Temporärdatei bleibt nach fehlgeschlagenem Replace:** [mod:atomic/ATOM-03](#mod-atomic-atom-03), [lens:windows/WIN-04](#lens-windows-win-04).
- **Doppelte URL-Decodierung von Editable-Pfaden:** [mod:stats/STATS-01](#mod-stats-stats-01), [lens:windows/WIN-05](#lens-windows-win-05).
- **Lesende Mutantenauflösung heilt Metadaten vor Pfadprüfung:** [mod:cli/CLI-07](#mod-cli-cli-07), [mod:presentation/VIEW-01](#mod-presentation-view-01).
- **Apply überschreibt zwischenzeitliche Editoränderungen:** [mod:presentation/VIEW-02](#mod-presentation-view-02), [lens:races/RACE-04](#lens-races-race-04), [lens:contracts/CONTRACT-04](#lens-contracts-contract-04).
- **Verspätete Browser-Diff-Ergebnisse überschreiben Auswahl:** [mod:presentation/VIEW-04](#mod-presentation-view-04), [lens:races/RACE-03](#lens-races-race-03).
- **Doppelte Quellwurzeln ergeben falsche Mehrdeutigkeit:** [mod:presentation/VIEW-06](#mod-presentation-view-06), [lens:boundaries/EDGE-06](#lens-boundaries-edge-06).
- **Keyword-Weiterleitung benutzt nicht normalisierte Namen:** [mod:mutation/MUT-02](#mod-mutation-mut-02), [lens:boundaries/EDGE-01](#lens-boundaries-edge-01).
- **Übersprungene innere Klasse beschädigt Klassenstack:** [mod:mutation/MUT-04](#mod-mutation-mut-04), [lens:contracts/CONTRACT-01](#lens-contracts-contract-01).
- **Regex-Zeichenbereich überschreitet Unicode-Grenze:** [mod:operators/OP-07](#mod-operators-op-07), [lens:boundaries/EDGE-02](#lens-boundaries-edge-02), [lens:contracts/CONTRACT-06](#lens-contracts-contract-06).
- **Regex-Ausgabelimit schützt nicht vor quadratischer Erzeugung:** [mod:operators/OP-08](#mod-operators-op-08), [lens:boundaries/EDGE-07](#lens-boundaries-edge-07).
- **setup.cfg-Modellvalidierung umgeht ConfigError:** [mod:data/DATA-01](#mod-data-data-01), [lens:contracts/CONTRACT-02](#lens-contracts-contract-02).

## Widerlegte Kandidaten

### TIME-01: Pipeline-E2E behält ein für die berichtete Lastsituation zu knappes Gesamtbudget

[tests/integration/test_e2e_pipeline_validation.py](C:/claude_codex/mutmut-win-astra/tests/integration/test_e2e_pipeline_validation.py)

Scope: nondet:timing-assumptions. Beide Skeptiker melden refuted=true.

Korrektheit: Am Zielcommit 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat in tests/integration/test_e2e_pipeline_validation.py:52–59 wörtlich; timeout=180 steht in Zeile 57. Beide Tests verwenden den Helfer (Zeilen 107 und 142). Das Limit gilt jedoch jeweils pro subprocess.run-Aufruf. Eine tatsächliche Überschreitung unter Windows/CPython 3.14.7 ist nicht belegt: Selbst die vorausgesetzten 95 s liegen 85 s unter dem Limit; der zusätzlich angenommene Kostenfaktor 1,9 ist keine Messung. Der Nachbarhelfer dokumentiert in test_e2e.py:24–28 mögliche Coverage-Mehrkosten und setzt 300 s, belegt damit aber keine Überschreitung dieser beiden Tests. Die Fixtures sind festgelegt; fehlende Skalierung nach Mutantenzahl ist deshalb ebenfalls kein eigenständiger Defektbeleg. Die CI führt diese Tests mit Coverage aus (.github/workflows/ci.yml:142–145); eine vorgelagerte Ausnahme oder Timeout-Anpassung wurde nicht gefunden. Tests speziell zur ausreichenden Bemessung dieses Budgets wurden ebenfalls nicht gefunden. Es wurden auftragsgemäß keine Tests oder Laufzeitmessungen ausgeführt. Der Befund beschreibt somit ein plausibles Timing-Risiko, aber keinen nachgewiesenen Fehler; eine Einstufung als medium ist derzeit nicht begründet.

Erreichbarkeit: Am bestätigten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b stimmt das Zitat wörtlich: tests/integration/test_e2e_pipeline_validation.py:52–59 enthält timeout=180 in Zeile 57. Beide Tests erreichen den Helfer über Zeile 107 beziehungsweise 142–158; eine Budgetanpassung oder Timeout-Abfanglogik fehlt. Auch der Coverage-Lauf ist erreichbar: .github/workflows/ci.yml:142 führt die vollständige Suite mit --cov aus. Damit ist jedoch nur der bedingte Mechanismus bestätigt: Dauert ein Aufruf länger als 180 Sekunden, scheitert er vor seinen Ergebnisprüfungen. Die behauptete Unzulänglichkeit dieses Budgets ist nicht belegt. Der Faktor 1,9 ist eine Annahme; für die genannten 95 Sekunden fehlen hier eine verifizierte Zuordnung zum betroffenen Einzeltest und Angaben zum bereits enthaltenen Coverage-Aufwand. Der Kommentar in test_e2e.py:24–28 begründet dort 300 Sekunden, liefert aber keinen gemessenen Überschreitungsfall der beiden beanstandeten Tests. Die Fixtures sind fest vorgegeben, und my_lib wird ausdrücklich auf das basic-Profil begrenzt (Zeilen 146–153); ein beliebig wachsender Mutantenumfang ist daher kein belegtes Szenario dieses Tests. Die Suche im Testquellbaum fand keinen gezielten Test zur Angemessenheit dieses Helferbudgets. Tests und Laufzeitmessungen wurden auftragsgemäß nicht ausgeführt. Somit ist dies ein plausibler Verbesserungsansatz, aber kein nachgewiesener Flakiness-Defekt mittlerer Schwere; Widerlegung bedeutet hier ausdrücklich nicht, dass Überschreitungen ausgeschlossen wären.

### TIME-05: Zurückgenommen: 60-s-Kappung gemessener Startkosten verursacht aktuelle Produktionstimeouts

[src/mutmut_win/orchestrator.py](C:/claude_codex/mutmut-win-astra/src/mutmut_win/orchestrator.py)

Scope: nondet:timing-assumptions. Beide Skeptiker melden refuted=true.

Korrektheit: HEAD entspricht 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b. Das Zitat stimmt wörtlich mit orchestrator.py:1491–1492 überein. Der behauptete Produktionsmechanismus ist jedoch ausgeschlossen: collect_or_load_stats liefert entweder geladene Daten mit erzwungenem mapping_is_authoritative=False (stats.py:190–199), frisch gesammelte Daten mit ebenfalls False (:1733), oder MutmutStats mit Standardwert False (:111). Der Orchestrator übernimmt diese Eigenschaft für sämtliche Tasks vor der Timeoutberechnung (orchestrator.py:785 und :1626). Damit scheitert die Bedingung des selektiven Zweigs (:1578); verwendet wird zwingend max(_FALLBACK_TIMEOUT, clean_wall_seconds * multiplier) (:1587). Bei 70,01 s Clean-Lauf und Multiplikator 30 beträgt das Budget somit 2100,3 s statt 60,3 s. Der Gegenpfad über MutationTask.default=True (models.py:35–36) erklärt direkte Unit-Aufrufe, wird im regulären Ablauf aber überschrieben. Vorhandene Tests prüfen ausdrücklich das volle Budget trotz nicht autoritativer Testzuordnung (test_orchestrator.py:145–163), das Ignorieren eines gespeicherten Authority-Bits einschließlich Weitergabe von False an Tasks (test_no_tests_producer.py:100–134) sowie den mit Clean-Lauf skalierten Fallback trotz gekappter Startkosten (test_timeout_model.py:132–144). Tests wurden ausschließlich gelesen, nicht ausgeführt. Ein aktueller Produktionsfehler oder eine Einstufung als medium ist durch diesen Claim nicht begründet.

Erreichbarkeit: Am verifizierten HEAD 4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b steht das Zitat wörtlich in src/mutmut_win/orchestrator.py:1491–1492. Die Kappung existiert, verursacht aber im regulären Produktionspfad nicht das behauptete Budget. collect_or_load_stats lädt den Cache über load_stats (stats.py:1576), das einen gespeicherten Autoritätswert verwirft und ausdrücklich False setzt (190–199). Frische Erhebung setzt ebenfalls False (1733); Fehlerpfade liefern MutmutStats mit dem Default False (111, 1713–1730). Vor jeder regulären Timeoutberechnung durchlaufen sämtliche Tasks zwingend _assign_tests_to_tasks (orchestrator.py:785), das test_selection_is_authoritative aus diesem False übernimmt (1626). Auch der zunächst True lautende MutationTask-Default (models.py:35–36) bietet daher keinen Umgehungspfad. Die selektive Formel erfordert ausdrücklich task.test_selection_is_authoritative (orchestrator.py:1578); regulär gilt stattdessen max(_FALLBACK_TIMEOUT, clean_wall_seconds * multiplier) (1587). Bei 70 s Startkosten und 0,01 s Testdauer ergibt das mit Faktor 30 etwa 2100,3 s, nicht 60,3 s. Der Worker wahrt dieselbe Autoritätsbedingung (process/worker.py:1055–1064). Vorhandene Tests sichern den entscheidenden Gegenbeweis ab: test_no_tests_producer.py:100–134 prüft, dass selbst ein gespeichertes True keine selektive Auswahl aktiviert; test_orchestrator.py:145–163 verlangt bei nicht autoritativer Zuordnung das volle Clean-Run-Budget. test_timeout_model.py:59–70 bestätigt lediglich die Kappung, und die dortigen direkten Helper-Aufrufe mit künstlich autoritativen Tasks beweisen keine Produktionserreichbarkeit. Tests wurden ausschließlich gelesen und nicht ausgeführt. Die Rücknahme des ursprünglichen Produktionsclaims ist begründet.

### WORK-03: Coverage-Hooks ersetzen pytest-cov-Reportcontainer durch Liste

[src/mutmut_win/process/worker.py](C:/claude_codex/mutmut-win-astra/src/mutmut_win/process/worker.py)

Scope: mod:worker. Beide Skeptiker melden refuted=true.

Korrektheit: Als bestätigter Fehler unter den Prüfgrenzen nicht ausreichend belegt; damit ist keine Fehlerfreiheit nachgewiesen. HEAD entspricht dem Zielstand. Das Zitat stimmt wörtlich mit worker.py:342–349 überein; der zweite Block steht in 291–298. Beide ersetzen einen nichtleeren cov_report-Container durch list[str]. Die entscheidende Prämisse – pytest-cov erwartet hier bereits ein Mapping und verarbeitet die Liste anschließend inkompatibel – bleibt jedoch unbelegt: uv.lock:1450–1452 nennt pytest-cov 7.1.0, dessen Implementierung ist im erlaubten Checkout nicht vorhanden. Die Kommentare 325–328 belegen diesen Containervertrag nicht. Gegenmechanismen wurden geprüft: Die vorgelagerte CLI-Umschreibung 546–579 verhindert die spätere Containerersetzung nicht; die Laufzeitvariable wird regulär gesetzt (820, 1112–1117). Das Szenario ist damit plausibel, ein konkreter Controllerfehler oder Clean-Abbruch aber nicht nachgewiesen. test_process_worker.py:92–118 prüft ausschließlich CLI-Zeichenketten; test_runner_sidecar_safety.py:215 lediglich das Vorhandensein des Hooknamens. Beide widerlegen den Verdacht nicht und prüfen den behaupteten Pluginvertrag nicht. Keine Tests oder Reproduktionen ausgeführt. Entsprechend der Vorgabe, verbleibende Zweifel gegen einen bestätigten Befund zu entscheiden, refuted=true.

Erreichbarkeit: Am Zielcommit stimmt das Zitat wörtlich mit worker.py:342–349 überein; die zweite Umwandlung steht in 291–298. Der Aufrufpfad ist grundsätzlich erreichbar: validated_pytest_args sperrt --cov/--cov-report nicht; runner.py:299–300 setzt das Laufzeitverzeichnis und schreibt die Argumente um, während 664–666 den Guard aktiviert. Die vorgelagerte Argumentumleitung beseitigt die spätere Listenbildung nicht. Damit ist die Behauptung jedoch noch kein belegter Laufzeitfehler: Im erlaubten Checkout fehlt der pytest-cov-Parser beziehungsweise Controller, anhand dessen Mappingvertrag und konkrete nachgelagerte Fehloperation überprüft werden könnten. uv.lock:1450–1451 benennt lediglich pytest-cov 7.1.0. Der Kommentar worker.py:325–328 bestätigt die beabsichtigte frühe Ausführung, aber keinen Containervertrag. tests/unit/test_process_worker.py:92–119 prüft ausschließlich rohe CLI-Argumente und führt weder die Hooks noch den echten Coverage-Controller aus; das ist keine Widerlegung, aber auch kein Integrationsbeleg. Unter der vorgegebenen Zweifelsregel ist der behauptete Clean-Lauf-Abbruch deshalb als unbestätigter Fehler zurückzuweisen. Tests wurden nicht ausgeführt.

## Abdeckung der 26 Finder

Die folgenden Lesedeklarationen und Grenzen stammen aus den getrennten Finderkontexten; sie werden durch die Einzelgegenprüfungen und die Quellenkontrolle des Root ergänzt.

### nondet:basis-toctou — f01_basis_toctou

Eingereichte Kandidaten: BASIS-01.

**Vollständig gelesen:** stats.py; constants.py; gitignore_boundary.py; __main__.py; tests/unit/test_gitignore_staging_integration.py.

**Gezielt und im Kontext geprüft:** orchestrator.py: Basis-Aufnahmen und Driftentscheidung; worker.py: Runtime-Ausgabeumleitung; basis_diagnostics.py; test_dependency_basis_220.py; test_run_surface_integration_220.py.

**Berücksichtigte Gegenbelege:** Sortierte Walks; keine atime in Projektbasis; bekannte Caches ausgeschlossen/umgeleitet; sys.path restauriert; Distribution-Dateilisten ohne bewiesenen normalen Schreibpfad nicht als weiteren Defekt gewertet.

**Grenzen:** Keine Reproduktion, keine Vorfallkausalität bewiesen.

### nondet:staging-toctou — f02_staging_toctou

Eingereichte Kandidaten: STAGE-01.

**Vollständig gelesen:** file_setup.py; code_coverage.py; type_checker_filter.py; tests/unit/test_staging_authority_p1_220.py; tests/unit/test_atomic_transient_retry.py; tests/unit/test_runtime_isolation_221.py.

**Gezielt und im Kontext geprüft:** orchestrator.py: alle Staging-Validierungen; stats.py: Staging-Hash; runner.py/worker.py: Helper und Runtime-Dateien; atomic_file.py: Ensure/Write; models.py: Sidecars.

**Berücksichtigte Gegenbelege:** Reguläre eigene Schreibpfade erfolgen vor Snapshot oder außerhalb Staging; reiche Ergebnis-Sidecars erst nach letzter Prüfung; normale identische Helper werden nicht ersetzt.

**Grenzen:** Keine Windows-Sperrreproduktion; transiente Effekte bestehender Dateien nur statisch bewertet; andere Dateien nur gezielt gelesen.

### nondet:process-lifecycle — f03_process_lifecycle

Eingereichte Kandidaten: PROC-01, PROC-02, PROC-03.

**Vollständig gelesen:** process/job_object.py; process/executor.py; process/atomic_spawn.py; process/suspended_spawn.py; process/generation_supervisor.py; tests/unit/test_atomic_spawn.py; tests/unit/test_suspended_spawn.py; tests/unit/test_job_object.py; tests/unit/test_generation_supervisor_teardown.py; tests/integration/test_job_object_kill_on_close.py; tests/integration/test_generation_supervisor.py; tests/integration/test_pool_shutdown.py.

**Gezielt und im Kontext geprüft:** worker.py: Guards, Workerloop, Taskcleanup und Spawn; type_checking.py; runner.py; cli.py; orchestrator.py.

**Berücksichtigte Gegenbelege:** Reguläre Prozesse atomar in JOB_LIST; keine Breakaway-Limits gefunden. Jobhandles nicht vererbbar; Tod des tatsächlichen Haupt-Python schließt Pool-/Generation-Job. Shell-Ende allein ist nicht Jobinhabertod. Bestehende Tests enthalten harte Elternenden und Nachkommen.

**Grenzen:** Keine externen API-/CPython-Quellen oder Prozessreproduktion; keine PID/PPID/Job-/Handlebelege für beobachtete Waisen. Keiner der Kandidaten bestätigt deren Ursache.

### nondet:timing-assumptions — f04_timing

Eingereichte Kandidaten: TIME-01, TIME-02, TIME-03, TIME-04, TIME-05.

**Gezielt und im Kontext geprüft:** Gesamte src/tests nach timeout/sleep/retry/deadline/time_budget, monotonic/perf_counter/time, wait/join/poll, Timer/Windows-Waits, Zeitassertionen durchsucht; Kontextuell ausgewertet: Runner/Config, Orchestrator-Budget/Stats/Worker, Executor, Supervisor, Monitor, OutputCapture, Typchecker, Atomic/File-Retries, Runlock, Kill/Reaping, Watchdog; Integrationstests für E2E, IL, Jobs, Pool/Generation/Locks; Unit-Tests für Timeout, Capture, Monitor, Jobs, Worker und Runtime-Isolation.

**Berücksichtigte Gegenbelege:** Autoritäts-Flag wird aktuell immer false: TIME-05 zurückgenommen. Feste Limits allein nicht als Defekt gewertet; Performancevertrag und Mockwerte gesondert behandelt.

**Grenzen:** 95-s-Angabe stammt vom Nutzer, keine Messung. Explizite Budgetgruppen abgearbeitet, implizite Bibliotheksdefaults und dynamische Werte nicht vollständig.

### nondet:ordering-determinism — f05_ordering

Eingereichte Kandidaten: ORDER-01, ORDER-02, ORDER-03.

**Vollständig gelesen:** stats.py; file_setup.py; test_mapping.py; tests/unit/test_sitecustomize_116.py.

**Gezielt und im Kontext geprüft:** Alle src-Pythondateien: scandir/iterdir/walk/glob, Hashing, Sortierung, Sets/JSON/repr, Parallelresultate; orchestrator.py; runner.py; config.py; models.py; db.py; generation_supervisor.py; Tests für Staging, Namespace, Dependencies, Stats, Config, Run-Identität.

**Berücksichtigte Gegenbelege:** Baumhashes und Umgebung total sortiert; parallele Generation rekonstruiert Eingabeordnung; Coverage/Tests sortiert. Unsortierter Plan ist explizit geordnet gebunden und allein kein Defekt.

**Grenzen:** Keine dynamische Reproduktion oder Häufigkeitsbelege. ORDER-02 nur Byte-Nichtdeterminismus, kein Verdict-/Cachefehler bewiesen.

### mod:orchestrator — f06_orchestrator

Eingereichte Kandidaten: ORCH-01, ORCH-02, ORCH-03.

**Vollständig gelesen:** orchestrator.py; tests/unit/test_result_reuse_119.py.

**Gezielt und im Kontext geprüft:** db.py: Plan/Ergebnis/Finalisierung/Widerruf; cli.py: Executor/Lock/Gate; executor.py: Konfiguration/Start/Shutdown; job_object.py/run_lock.py; runner.py: Boundary/Forced-Fail; stats.py: Autorität/Reuse; Tests für Orchestrator, Run-Surface/Identität, Executor.

**Berücksichtigte Gegenbelege:** Ungeplante/doppelte Ergebnisse abgewehrt; unvollständige Basis deautorisiert; Recovery widerruft vor Wiederaufnahme; Mapper erlaubt keine Testauslassung.

**Grenzen:** Abhängigkeiten nur entlang relevanter Pfade gelesen; keine Ausführung.

### mod:file-setup — f07_file_setup

Eingereichte Kandidaten: FILE-01, FILE-02, FILE-03, FILE-04, FILE-05, FILE-06.

**Vollständig gelesen:** file_setup.py; code_coverage.py; tests/unit/test_gitignore_staging_integration.py; tests/integration/test_coverage_gating.py; tests/unit/test_sanitiser_113.py.

**Gezielt und im Kontext geprüft:** orchestrator.py: Discovery/Copy/Coverage/Generation; config.py/constants.py: Pfade/Skip; gitignore_boundary.py; models.py: Owned-Metadata; runner.py/mutation.py/trampoline.py; atomic_file.py/stats.py; Tests für Staging/Hygiene/Namespace/Config-Wechsel.

**Berücksichtigte Gegenbelege:** Owned-Metadata prüft Generated-Hash. _sync_tree berücksichtigt Ignore bereits; FILE-05 nur automatischer Löschpass. Coveragetest beginnt mit frischem Originalmirror; Sanitizer-Test enthält keine TOML-Strings.

**Grenzen:** Alle Kandidaten rein statisch; Aufrufer und Tests bedarfsbezogen.

### mod:stats — f08_stats

Eingereichte Kandidaten: STATS-01, STATS-02, STATS-03.

**Vollständig gelesen:** stats.py; tests/unit/test_dependency_basis_220.py; tests/unit/test_stats.py; tests/unit/test_stats_truth.py.

**Gezielt und im Kontext geprüft:** orchestrator.py/cli.py: Basisaufnahmen/Reuse/Deautorisation; runner.py/worker.py: Import- und Runtime-Isolation; file_setup.py/constants.py: Skip/Purge; Gitignore-Basistests.

**Berücksichtigte Gegenbelege:** Frisches PYCACHEPREFIX und Staging-Purge widerlegen isolierten pycache-Verdacht; direkte Archive gehasht. Normaler Abschluss liest breite Basis fünfmal, daraus folgt keine Endlosschleife.

**Grenzen:** ZIP-Unterpfad braucht Bestätigung Windows-lstat-Fehlerklasse; keine Performancemessung.

### mod:db — f09_db

Eingereichte Kandidaten: DB-01, DB-02.

**Vollständig gelesen:** db.py; tests/unit/test_run_identity_220.py; tests/unit/test_db_hardening.py.

**Gezielt und im Kontext geprüft:** orchestrator.py: Locks/Runplan/Recovery/Widerruf/Reuse; cli.py: Snapshot/results/apply/export; browser.py: Legacy; Tests für DB-Migration, Korruption, State-Boundary und Run-Surface.

**Berücksichtigte Gegenbelege:** BEGIN IMMEDIATE, eindeutiger Running-Index und DB-Locks sichern reguläre Writer. Export sperrt und lehnt Legacy ab.

**Grenzen:** Keine SQLite-Reproduktion; Nebenmodule nur zielgerichtet.

### mod:worker — f10_worker

Eingereichte Kandidaten: WORK-01, WORK-02, WORK-03.

**Vollständig gelesen:** process/worker.py; process/output_capture.py; tests/unit/test_process_worker.py.

**Gezielt und im Kontext geprüft:** runner.py: Clean/Runtime/Guard/Cleanup; executor.py: Ereignisse/fatal; models.py/orchestrator.py/constants.py: Klassifikation/Persistenz; pytest_boundary.py/atomic_file.py; Tests für Sidecar-Sicherheit, Hardening, Baumcleanup, Gate und Tasktimeouts.

**Berücksichtigte Gegenbelege:** Parent-Guard-Publikation fatal korrekt; fehlender Proof bei Exit0 getestet. Coverage-Test prüft CLI-Strings, nicht Plugincontainer. POSIX-Gate-Vermutung nicht übernommen.

**Grenzen:** WORK-03 externes API nicht im Checkout verifiziert; WORK-02 beschädigter Proof nicht reproduziert; statisch.

### mod:cli — f11_cli

Eingereichte Kandidaten: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06, CLI-07.

**Vollständig gelesen:** cli.py; tests/unit/test_cli.py; test_config_cli_truth.py; test_cli_consistency_115.py; test_cli_containment_contract.py; test_cli_basis_diagnostics.py; test_cicd_il_bucket.py; test_contract_120.py; test_treat_timeout_as_kill.py; test_closure_117.py; test_interrupt_honesty.py.

**Gezielt und im Kontext geprüft:** Run-Surface/Hardening/Orchestrator-Tests; config.py/orchestrator.py/executor.py/db.py/stats.py/models.py; test_mapping.py/mutant_diff.py/file_setup.py/pytest_boundary.py.

**Berücksichtigte Gegenbelege:** Nichtfinite Werte, Subset-Gates, Exportdrift abgewehrt; Force hat Locks/Root/Preflight. Git-Tests mocken relative Pfade; Interrupttests liefern fertiges Ergebnis.

**Grenzen:** Git-Semantik nicht dynamisch geprüft; CLI-04 begrenzt auf Prozesslebensdauer; Nebenmodule bedarfsbezogen.

### mod:mutation — f12_mutation

Eingereichte Kandidaten: MUT-01, MUT-02, MUT-03, MUT-04, MUT-05, MUT-06, MUT-07.

**Vollständig gelesen:** mutation.py; trampoline.py; tests/unit/test_mutation.py; test_wrapper_codegen.py; test_class_body_injection.py; test_staticmethod_mutation.py; test_mutation_hardening_round2.py; test_mutation_adversarial_a5.py; test_trampoline.py; test_do_not_mutate_patterns.py; test_duplicate_definitions_220.py.

**Gezielt und im Kontext geprüft:** file_setup.py: Generierung/Syntaxvalidierung; orchestrator.py: dryrun; mutant_diff.py/test_mapping.py: Identität; node_mutation.py; README/pyproject.

**Berücksichtigte Gegenbelege:** Enumtests betreffen post-creation Methoden; Generator-Gegenprobe nur nested def; Pattern-Stacks nur getrennte Top-Level-Klassen; Duplicate-Tests keine NFKC-Äquivalenz.

**Grenzen:** Externer LibCST-Visitorvertrag für MUT-04 nicht gelesen; keine Reproduktion; MUT-07 bekannter Auftragspunkt.

### mod:operators — f13_operators

Eingereichte Kandidaten: OP-01, OP-02, OP-03, OP-04, OP-05, OP-06, OP-07, OP-08, OP-09.

**Vollständig gelesen:** node_mutation.py; regex_mutation.py; tests/unit/test_safe_unwrap.py.

**Gezielt und im Kontext geprüft:** mutation.py: Visitor/Skip/Generation/Render-Dedup; file_setup.py: Exception/Syntax-Fallback; constants.py: Profile; Tests für numerische Strings/CRCR/Regex/Profile.

**Berücksichtigte Gegenbelege:** Cross-Operator-Duplikate durch Render-Dedup abgewehrt; nichtfinite Zahlen, Regex-repr/Roundtrip und Compile-Overflow geschützt.

**Grenzen:** Statisch; OP-08 Größenordnung statt Messung; OP-09 nur konkretes Matchergebnis äquivalent.

### mod:runner — f14_runner

Eingereichte Kandidaten: RUNNER-01, RUNNER-02, RUNNER-03.

**Vollständig gelesen:** runner.py; pytest_boundary.py; process/output_capture.py; tests/unit/test_runner.py; test_runner_diagnostics.py; test_runner_argfile_221.py; test_pytest_target_argfile_221.py; test_pytest_boundary_security_220.py.

**Gezielt und im Kontext geprüft:** worker.py: Guards/Args/Runtime/Testauswahl; stats.py: Cache/Autorität; orchestrator.py: Forcedfail/Zuordnung/Timeout; config.py/pyproject; Phase-Truth/Hardening-Tests.

**Berücksichtigte Gegenbelege:** Fixturemapping nicht autoritativ, kein falscher Survivor; Argfile-Zeileninjektion abgewehrt; Configdiscovery entspricht tests_dir-Vertrag; kein zusätzlicher Boundarydefekt gefunden.

**Grenzen:** pytest-Implementierung extern nicht geprüft; statische Szenarien; kurze koordinierte Unterbrechung, danach Nutzerfreigabe historischer Kommentare.

### mod:locking — f15_locking

Eingereichte Kandidaten: LOCK-01, LOCK-02, LOCK-03, LOCK-04.

**Vollständig gelesen:** process/run_lock.py; process/generation_supervisor.py; process/suspended_spawn.py; process/posix_spawn.py; process/job_object.py; tests/unit/test_run_lock.py; tests/integration/test_run_lock_processes.py; tests/integration/test_generation_supervisor.py; tests/unit/test_generation_supervisor_teardown.py.

**Gezielt und im Kontext geprüft:** orchestrator.py: Erwerb/Recovery/Generation; cli.py/db.py/atomic_file.py; Run-Surface-Tests; Alle Aufrufer von Workspace/DB-Lock, refresh_identity, run_generation_supervised.

**Berücksichtigte Gegenbelege:** Workspace schützt nur gleiches cwd; Jobcontainment stoppt keine Main-Serialization; Atomics haben post-Replace-Prüfungen; bestehende Lockkonkurrenz startet nach Ready. POSIX als ununterstützt ausgeklammert.

**Grenzen:** Windows-Byte-Locksemantik nicht reproduziert; kurze Unterbrechung wegen historischem Kommentar nach Nutzerklärung aufgehoben.

### mod:spawn — f16_spawn

Eingereichte Kandidaten: SPAWN-01, SPAWN-02, SPAWN-03, SPAWN-04.

**Vollständig gelesen:** process/executor.py; process/atomic_spawn.py; process/posix_spawn.py; process/suspended_spawn.py; process/job_object.py; process/output_capture.py; process/loop_monitor.py; tests/unit/test_atomic_spawn.py; test_suspended_spawn.py; test_bounded_output_capture_220.py; test_process_executor.py; test_worker_liveness.py; test_classifier_honesty.py; test_loop_monitor.py; test_job_object.py; tests/integration/test_job_object_kill_on_close.py.

**Gezielt und im Kontext geprüft:** worker.py: Workerloop/Cleanup/Monitor/Spawn; runner.py/type_checking.py: Capture; cli.py/orchestrator.py: Konstruktion/Dispatch/IL-Anrechnung; Poolcollapse/Shutdown/IL/Timeouttests.

**Berücksichtigte Gegenbelege:** JOB_LIST atomar. Late-Eventtest nur Completed; I/Otests monotone Werte; Capture-/Queue-Konstruktorfehler fehlen.

**Grenzen:** Alle Races/Ressourcenfehler statisch, ausschließlich Windowsbewertung; keine Reproduktion.

### mod:atomic — f17_atomic

Eingereichte Kandidaten: ATOM-01, ATOM-02, ATOM-03, ATOM-04.

**Vollständig gelesen:** atomic_file.py; basis_diagnostics.py; tests/unit/test_atomic_transient_retry.py; tests/unit/test_atomic_write_safety_220.py.

**Gezielt und im Kontext geprüft:** Diagnostiktests: Fehler/Outputschutz; StagingHygiene: readonly; Stats/Runlock: Parenttausch/Cleanup; file_setup.py: Cleanup/Copy; cli.py/stats.py/pytest_boundary.py: Diagnoseintegration.

**Berücksichtigte Gegenbelege:** basis_diagnostics vollständig ohne ausreichend konkreten eigenen Defekt; vorhandene Readonlytests betreffen Erfolg, kein Cleanup nachReplacefehler.

**Grenzen:** FD-Wiederverwendung nicht gemessen; Telemetrie benötigt vorbereitetenLink+Erschöpfung; WindowsReadonly/Namen nicht reproduziert.

### mod:data — f18_data

Eingereichte Kandidaten: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05.

**Vollständig gelesen:** config.py; models.py; constants.py; exceptions.py; tests/unit/test_config.py; test_models.py; test_constants.py; test_exceptions.py; test_config_cli_truth.py.

**Gezielt und im Kontext geprüft:** cli.py: Configfehler; file_setup.py/mutant_diff.py/browser.py: Metadaten; mutation.py: Regexmuster; orchestrator.py/worker.py: Budgets/Taskvalidation; StagingHygiene/ExceptionHygiene/Hardening132-Tests.

**Berücksichtigte Gegenbelege:** TOML-Modell-/INI-Syntaxfehler korrekt; Mehrzeilenregex bewahrt Kommas; gewöhnliche Metadatentypfehler geheilt. Keine zusätzlichen Konstanten-/Exceptionhierarchiedefekte.

**Grenzen:** Statisch; Decodierungs- und Zahlenfälle nicht ausgeführt; Nebenmodule gezielt.

### mod:presentation — f19_presentation

Eingereichte Kandidaten: VIEW-01, VIEW-02, VIEW-03, VIEW-04, VIEW-05, VIEW-06.

**Vollständig gelesen:** browser.py; mutant_diff.py; result_browser_layout.tcss; tests/unit/test_browser_diff.py; test_browser_evidence_invalidation_220.py; test_mutant_diff.py; test_source_protection.py; test_source_fidelity.py.

**Gezielt und im Kontext geprüft:** cli.py: show/apply/browse/Root; models.py: Heilung/Owned; file_setup.py: Discovery/Boundary/Verified; atomic_file.py/db.py/test_mapping.py; Tests für CLI/Duplikate/Run-Surface/Atomic/Leertabellen.

**Berücksichtigte Gegenbelege:** Hashbindung, Deklarationsschutz, Scope/Ordinal, Bytefidelity, Runautorität und Apply-Invalidierung berücksichtigt.

**Grenzen:** Textual/Rich und native Sperrsemantik nicht extern geprüft; statisch.

### mod:rest — f20_rest

Eingereichte Kandidaten: REST-01, REST-02, REST-03, REST-04, REST-05.

**Vollständig gelesen:** type_checking.py; type_checker_filter.py; code_coverage.py; test_mapping.py; hit_recording.py; gitignore_boundary.py; stall_watchdog.py; _state.py; __init__.py; __main__.py; process/__init__.py; Unit-Tests für Typechecking/Typfilter/Baseline/Coverage/Mapping/Hits/State/Gitignore; Integrationstests Coverage-Gating/Typechecker-Prozessbäume.

**Gezielt und im Kontext geprüft:** orchestrator.py/runner.py/file_setup.py/stats.py/mutant_diff.py/config.py/worker.py; Matcher-/CLI-/Watchdogtests.

**Berücksichtigte Gegenbelege:** Atomarer Windowsstart, Cleanup, Force-Include, Coverage-Gates, Baseline-Abzug und State-Reset berücksichtigt. Keine zusätzlichen Watchdog/Hit/State/Initdefekte.

**Grenzen:** 1596 Kernzeilen und2399 Testzeilen gelesen; Coverage-API nur mittel ohne Dependencyprüfung; keine Ausführung.

### lens:races — f21_races

Eingereichte Kandidaten: RACE-01, RACE-02, RACE-03, RACE-04, RACE-05.

**Gezielt und im Kontext geprüft:** Alle40 Pythonmodule per Inventar/Mustersuche erfasst; Thread/Lock/Event/Queue/Executor/Pool, Interrupt/kill/wait, globals/env/path, exists/replace/unlink/Identität; Kontextuell: Windows-Spawn, Workerprotokoll, Generation-Wire, Capture/Monitor, Workspace/DB-Locks, SQLite, Staging/Atomics, Browser, Stats/Hits/ContextVars, Coverage/Typchecker; 29 Module kontextuell gelesen, übrige11 per Referenz-/Musterinventar; Tests zu Liveness, Spawn/Interrupt, Typechecker/Workercleanup, Jobnachkommen, Locks, Capture, Atomics und Sourceprotection.

**Berücksichtigte Gegenbelege:** Kein pauschaler GIL-/Deque- oder ABA-Befund; Mapping nicht autoritativ; vorhandener CaptureEmptyRead/Stop-Race bereits behoben; POSIX ausgeklammert.

**Grenzen:** Querschnittsstellen vollständig nach Suchgruppen, keine vollständige fachliche Algorithmenprüfung; Interleavings nicht reproduziert oder quantifiziert.

### lens:windows — f22_windows

Eingereichte Kandidaten: WIN-01, WIN-02, WIN-03, WIN-04, WIN-05.

**Vollständig gelesen:** __init__.py; __main__.py; _state.py; atomic_file.py; stall_watchdog.py; process/__init__.py; process/atomic_spawn.py; process/suspended_spawn.py; process/job_object.py; process/output_capture.py.

**Gezielt und im Kontext geprüft:** Alle40 Module nach Pfadlänge/Normalisierung/Identität/Reparse/Case/Sharing/Retry/Handle/Encoding/Zeilenende inventarisiert und Treffergruppen kontextuell gelesen; Alle übrigen30 Module kontextuell; Tests StagingHygiene, AtomicSafety/Retry, FileSetup, DependencyBasis.

**Berücksichtigte Gegenbelege:** README-Grenzen für lokale stabile Identität berücksichtigt; readonly-Staging explizit getestet; Browserencoding wird abgefangen; Kommandozeilen206-Test schützt keine Basenames.

**Grenzen:** Keine vollständige Zeilenlektüre allerModule, aber paketweite Suchgruppen; Windowsfälle/API-Vertrag rein statisch; WIN-05 mittel.

### lens:failclosed — f23_failclosed

Eingereichte Kandidaten: FAIL-01, FAIL-02, FAIL-03.

**Vollständig gelesen:** __init__.py; __main__.py; _state.py; trampoline.py; exceptions.py; code_coverage.py; process/__init__.py; process/job_object.py; process/atomic_spawn.py; process/output_capture.py.

**Gezielt und im Kontext geprüft:** Alle40 Pythonmodule inventarisiert;383 Except-Blöcke,86 suppress-Stellen,kein bareexcept; Alle Except-/Suppress-/Warn-/Fallbackgruppen kontextuell, lange Bodies separat bis Ende gelesen; Aufruferverträge und Tests zu Config/Classifier/Stats/Recovery/Containment/Capture.

**Berücksichtigte Gegenbelege:** Run-Widerruf/Recovery, konservative Statsautorität, fataler Containment/Boundarypfad, unvollständige Basis korrekt; dokumentiertes Best-effort nicht pauschal beanstandet.

**Grenzen:** Keine vollständige zeilenweise Lektüre aller übrigen Module; ausschließlich vollständige Treffergruppenprüfung. FAIL-03 aktuell begrenzte Produktionsreichweite.

### lens:resources — f24_resources

Eingereichte Kandidaten: RES-01, RES-02, RES-03, RES-04, RES-05, RES-06, RES-07, RES-08, RES-09.

**Vollständig gelesen:** atomic_file.py; code_coverage.py; stall_watchdog.py; process/atomic_spawn.py; process/executor.py; process/generation_supervisor.py; process/job_object.py; process/output_capture.py; process/posix_spawn.py; process/suspended_spawn.py.

**Gezielt und im Kontext geprüft:** 40/40 Module nach Erzeugung/Freigabe/Alias/Ownership inventarisiert; Alle Gruppen: rawFDs, Bibliotheksfiles, Jobs/Prozesse/Handles, Pipes/Queues/Threads, Tempdirs, SQLite, Sockets; 18 weitere Module kontextuell; übrige12 ohne eigene Erzeugung untersuchter Ressourcen; Capture/Atomic/Executor/Typechecker/Locks/Containment/Spawn/Hygiene und Baumcleanup/Shutdown-Tests.

**Berücksichtigte Gegenbelege:** Zentraler SQLite-Kontext garantiert close; keine eigene Socketanlage. OS-/Bibliotheksfinalizer berücksichtigt. Persistente Lockguards beabsichtigt. Eigenständige CLI-Lecks durch Prozessende begrenzt.

**Grenzen:** Seltene Fehlerpfade und Browserlast nicht gemessen; nur statische Ressourcengruppenprüfung.

### lens:boundaries — f25_boundaries

Eingereichte Kandidaten: EDGE-01, EDGE-02, EDGE-03, EDGE-04, EDGE-05, EDGE-06, EDGE-07, EDGE-08.

**Vollständig gelesen:** __init__.py; __main__.py; _state.py; constants.py; models.py; code_coverage.py; hit_recording.py; regex_mutation.py; stall_watchdog.py; test_mapping.py; trampoline.py; type_checker_filter.py; type_checking.py; process/__init__.py; process/output_capture.py; process/suspended_spawn.py.

**Gezielt und im Kontext geprüft:** 40 Module per Symbol-/Suchinventar; übrige24 Module kontextuell samt Aufrufern; Leere/einzelne/doppelte/überlappende Eingaben; None/Null/negative/große Zahlen; Timeoutüberläufe; Workerobergrenzen; Unicode/NFKC/Surrogate; Kodierung/Zeilenenden; Pfadanker/Sonderzeichen; Index/Range/Division/Zwischenlisten.

**Berücksichtigte Gegenbelege:** Vorhandene Leere/Null/None/Score/Argfile/Encoding/RegexRepeatOverflow/Wrapper-Kollisionstests geprüft. Regex-CompileOverflow schützt nicht chr; Limit-Tests nur Ergebnislängen; Timeoutproperties kleine Zahlen.

**Grenzen:** Statisch. PPE/Integerlimit/UTF16-Verträge nicht extern geprüft; EDGE08 schwächer. Keine vollständige Zeilenlektüre übriger24Module behauptet.

### lens:contracts — f26_contracts

Eingereichte Kandidaten: CONTRACT-01, CONTRACT-02, CONTRACT-03, CONTRACT-04, CONTRACT-05, CONTRACT-06, CONTRACT-07.

**Gezielt und im Kontext geprüft:** 40/40 Pythonmodule: öffentliches Symbol-/Docstringinventar zuerst, dann sämtliche öffentlichen Vertragsgruppen samt Methoden/Properties, relevanten Konstruktoren/Kontextmanagern/Hooks; Quelle/Tests entlang öffentlicher Verträge: Atomics/Diagnostik/UI/CLI/Config/Mapping/DB/Staging/Metadata/Diffs/Mutation/Pipeline/Pytest/Stats/Checker/Process/Locks/Cleanup; Gezielte Tests: do_not_mutate_patterns, Config/Exceptionhygiene, Checkerparser, Apply/Staleness, Regex/Properties, Orchestrator-Shutdown, Phaseguard.

**Berücksichtigte Gegenbelege:** Gewöhnlicher Windows-Spawn-Pipe-Deadlock durch seekable Bootstrap-Dateipfad widerlegt; nicht als Kandidat aufgenommen.

**Grenzen:** Keine vollständige Volltextlektüre aller privaten Helper oder sämtlicher Tests behauptet; gezielte Callerprüfung. Statisch; keine Abhängigkeitssourcen außerhalb Repository.

## Grenzen der Erhebung

Es wurden keine Tests, Builds, Installationen, Semgrep-Läufe oder Prozessreproduktionen ausgeführt. Die gemeldeten grünen Gates, die Gleichheit mit dem anderen Prüfbaum und die beobachteten Laufzeiten beziehungsweise Waisen stammen aus dem Auftrag; sie wurden nicht unabhängig nachgestellt. Die Modulcluster wurden vollständig gelesen; die Querschnittslinsen arbeiteten ihre paketweiten Such- und Vertragsgruppen im Kontext ab. Daraus folgt keine vollständige Lektüre jedes Tests oder jeder externen Abhängigkeit. Nicht vorhandene Befunde sind kein Fehlerfreiheitsbeweis. Die Kausalität zu den konkret beobachteten sporadischen Ausfällen und stundenlangen Waisen bleibt ohne Laufspuren unbewiesen. Der unterstützte Scope ist Windows mit CPython3.14.7; POSIX-spezifische Auslöser allein rechtfertigen keinen Produktbefund.

Die Schwere bewertet den belegten Mechanismus und seine konkreten Voraussetzungen. Häufigkeit, Verteilung unter Last, Speicherhöchststände und tatsächlich verursachte Scoreabweichungen wurden nicht gemessen. Es wurden keine zusätzlichen Tests geschrieben.

Die erlaubten Sprach- und API-Faktenchecks prüfen jeweils eine eng begrenzte Prämisse, etwa eine Callback-Reihenfolge, Zahlenrundung oder Syntaxregel. Sie belegen keinen vollständigen Mutationslauf und keine Betriebssystem-Prozesskette.

Abhängigkeiten von vorhandenen Staging-Dateien oder Dateisystemreihenfolgen beweisen keine zufällige Abweichung bei vollständig identischem Gesamtzustand. Die im Auftrag genannten konkreten Ausfälle wurden nicht rekonstruiert.

Ein gemäß Protokoll widerlegter Kandidat kann auf einem echten Gegenbeweis beruhen oder mangels ausreichender Evidenz zurückgewiesen sein. Der jeweilige Grund steht bei beiden Urteilen; fehlende Evidenz ist kein Nachweis von Fehlerfreiheit.

Überschneidungen zwischen unabhängigen Findern erhöhen den Kandidatenzähler. Sie werden für den verlangten Quervergleich erhalten und gesondert gruppiert; aus diesem Zähler wird keine Anzahl einzigartiger Defekte abgeleitet.

### Erlaubte Faktenchecks

- **ORDER-03 — Erreichbarkeit:** Kurzer CPython3.14.7-Faktencheck: json.dumps(sort_keys=True) erhält Listenreihenfolge.
- **ORCH-03 — Korrektheit und Erreichbarkeit:** Kurzer CPython3.14.7-API-Faktencheck: StringIO.line_buffering=False; kein reconfigure.
- **STATS-01 — Korrektheit und Erreichbarkeit:** Kurzer Windows/CPython3.14.7-API-Faktencheck zu url2pathname mit und ohne vorgeschaltetes unquote.
- **STATS-02 — Korrektheit, Erreichbarkeit:** CPython 3.14.7: json.loads akzeptiert eine 401-stellige Ganzzahl, math.isfinite wirft OverflowError.
- **STATS-03 — Korrektheit, Erreichbarkeit:** Windows/CPython 3.14.7: lstat auf einem Unterpfad unter einer vorhandenen regulären Datei ergibt FileNotFoundError, errno=2, winerror=3. ZIP-Importverhalten nicht dynamisch reproduziert.
- **CLI-05 — Korrektheit, Erreichbarkeit:** Isolierter Click-API-Check ohne Projektimporte: KeyboardInterrupt aus einem Callback führt zu Aborted! und SystemExit(1), nicht 130.
- **MUT-01 — Erreichbarkeit:** CPython 3.14.7: Enum.__init__ für A=1 läuft, bevor E im Modul gebunden ist; unverändertes Beispiel ergibt extra=2. Keine Mutmut-Ausführung.
- **MUT-02 — Erreichbarkeit:** CPython 3.14.7: privater Klassenparameter __value kompiliert als _C__value; Originalaufruf liefert 2. Identifier K normalisiert zu K, die Stringschlüssel bleiben verschieden.
- **MUT-04 — Korrektheit, Erreichbarkeit:** Isolierte LibCST-API-Faktenchecks: on_visit(False) liefert dennoch die Folge ['visit', 'leave']; keine Projektmutation ausgeführt.
- **MUT-05 — Erreichbarkeit:** CPython 3.14.7 compile-Check: ausgerückte Kommentare beziehungsweise Mehrzeilenstring-Inhalte innerhalb der beschriebenen Funktion sind gültig und bilden keinen Suite-Dedent.
- **MUT-06 — Korrektheit, Erreichbarkeit:** CPython 3.14.7 AST-/Normalisierungschecks bestätigen K/Ｋ sowie x_Ｋ__mutmut_orig als identische normalisierte Python-Identifier. Keine Projektinstrumentierung ausgeführt.
- **OP-01 — Korrektheit:** Isolierter LibCST-/Sprachcheck: ungekoppelter negativer Zahlknoten rendert -2 ** x; x=2 ergibt -4 statt 4. Ungeklammertes 0.bit_length() wird von ast.parse als ungültiger Dezimalliteral zurückgewiesen.
- **OP-02 — Korrektheit, Erreichbarkeit:** Isolierte Sprach-/LibCST-Checks bestätigen gültige Ausgangsausdrücke, Klammern am UnaryOperation-Elternknoten und SyntaxError für 1.bit_length; (1).bit_length ist gültig.
- **OP-03 — Korrektheit, Erreichbarkeit:** CPython 3.14.7 akzeptiert case -1, verwirft case +1 mit SyntaxError; der isolierte LibCST-Check bestätigt MatchValue→UnaryOperation→Minus und die als +1 gerenderte Ersetzung.
- **OP-05 — Korrektheit, Erreichbarkeit:** Windows/CPython 3.14.7: 1e20+1==1e20 und repr liefert '1e+20'; entsprechender Wertgleichheits-/repr-Fall bei 1e20j+1j.
- **OP-06 — Korrektheit, Erreichbarkeit:** Isolierte re-API-Faktenchecks unter CPython 3.14.7 bestätigen die Gültigkeit der angegebenen Keywordreihenfolgen und Signaturen; kein Projektcode importiert.
- **OP-07 — Korrektheit, Erreichbarkeit:** CPython 3.14.7: Singleton-Regexbereiche an U+0000/U+10FFFF kompilieren; chr(-1) und chr(0x110000) werfen ValueError. Keine Projektgeneration.
- **OP-09 — Erreichbarkeit:** CPython 3.14.7 Regex-Parsercheck: Original a(?#\d+) und die beiden genannten Kommentarvarianten ergeben denselben Inhalt [(LITERAL, 97)] und null Gruppen.
- **LOCK-02 — Korrektheit, Erreichbarkeit:** CPython 3.14.7 API-/Bytecodeprüfung bestätigt synchrone ForkingPickler.dumps/loads in send/recv. Keine blockierende Serialisierung oder Prozessreproduktion ausgeführt.
- **DATA-02 — Korrektheit, Erreichbarkeit:** CPython 3.14.7: Beide durch Kommasplit entstandenen Regexfragmente kompilieren, treffen f1/f123 aber nicht; das Original trifft beide. Der Erreichbarkeitscheck bestätigt außerdem den erhaltenen ConfigParser-Zeilenumbruch bei eingerückter Fortsetzung.
- **DATA-03 — Korrektheit, Erreichbarkeit:** CPython 3.14.7: 401-stellige JSON-Ganzzahlen werden eingelesen, math.isfinite wirft OverflowError außerhalb von ValueError. Bei 5001 beziehungsweise 4301 Ziffern wirft der JSON-Parser unter dem aktivierten Ziffernlimit ValueError statt JSONDecodeError.
- **DATA-05 — Korrektheit, Erreichbarkeit:** Windows/CPython 3.14.7: speicherbasierte Standardbibliothekschecks mit tomllib.load und ConfigParser.read bestätigen UnicodeDecodeError für ungültige UTF-8-Bytes und die fehlende Zugehörigkeit zu den abgefangenen Ausnahmeklassen. Keine Projekt- oder CLI-Ausführung.
- **REST-01 — Korrektheit, Erreichbarkeit:** Windows/CPython 3.14.7: fnmatch.fnmatch trifft das nur durch foo/Foo verschiedene Namenspaar, fnmatchcase nicht. Reiner Standardbibliothekscheck, kein Projektlauf.
- **REST-03 — Korrektheit:** CPython 3.14.7 mit coverage 7.13.5: Startinitialisierung wählt bei run:parallel=True trotz explizitem Basisnamen .coverage.mutmut einen Namen mit Suffix. Keine Messung gestartet, keine Datendatei geschrieben.
- **REST-02 — Root:** coverage 7.13.5: Coverage(config_file=False, data_file=None), relative_files=True und reine Initialisierung bilden den absoluten Pfad src/mutmut_win/config.py auf src\mutmut_win\config.py ab. Keine Messung gestartet oder Datendatei geschrieben.
- **FAIL-01 — Korrektheit, Erreichbarkeit:** CPython 3.14.7: Ein rein speicherbasierter Standardbibliothekscheck mit simuliertem PermissionError beim Öffnen liefert aus ConfigParser.read() [] und has_section('mutmut') == False, ohne propagierte Ausnahme. Keine Windows-Sperrreproduktion.
- **WIN-03 — Korrektheit:** CPython 3.14.7/win32: casefold setzt maße.json und masse.json gleich, PureWindowsPath unterscheidet sie. Dies ersetzt keine NTFS-Dateisystemreproduktion.
- **WIN-05 — Korrektheit, Erreichbarkeit:** Windows/CPython 3.14.7: Path(r'C:\work\dep%20copy').as_uri() liefert dep%2520copy. url2pathname allein erhält den wörtlichen Namen; die Kombination mit unquote ersetzt %20 durch ein Leerzeichen. Keine Projektimporte oder Dateisystemreproduktion.
- **EDGE-01 — Korrektheit, Erreichbarkeit:** Windows/CPython 3.14.7: Der Parameter K wird zu K normalisiert; f(K=2) ergibt 3, während **{'K': 2} TypeError auslöst. Reiner Sprachcheck, keine Projektgeneration.
- **EDGE-02 — Korrektheit, Erreichbarkeit:** Windows/CPython 3.14.7: Beide Singleton-Ausgangspattern kompilieren und matchen ihr Endpunktzeichen. chr(-1) und chr(0x110000) werfen ValueError. Keine Projektgeneration.
- **EDGE-03 — Korrektheit, Erreichbarkeit:** Reine Sprachchecks unter Windows/CPython 3.14.7 bestätigten das Standardlimit 4300, Kompilierbarkeit des 3600-stelligen Hexliterals, gültige Addition und ValueError bei der Dezimalserialisierung mit 4335 Ziffern. Keine Projektimporte oder Prozessreproduktion.
- **EDGE-04 — Korrektheit, Erreichbarkeit:** Reine API-Inspektion unter Windows/CPython 3.14.7 bestätigte _MAX_WINDOWS_WORKERS=61 und die Konstruktorprüfung von ProcessPoolExecutor. Keine Executorinstanz und kein Worker wurden gestartet.
- **EDGE-05 — Korrektheit, Erreichbarkeit:** Sprach-/API-Checks bestätigten Endlichkeit von 1e308, Überlauf von 2.0*1e308 zu Infinity, zulässiges entsprechendes Pydantic-Feld sowie OverflowError bei Windows-Popen._wait an einem Dummyobjekt ohne Prozessanlage.
- **EDGE-08 — Korrektheit, Erreichbarkeit:** Windows/CPython3.14.7: os.environ.encodevalue und ctypes-Wide-Character-Puffer erhalten U+D800; UTF-8/surrogateescape wirft UnicodeEncodeError, während U+DC80 kodierbar ist. Kein Prozessstart und keine Reproduktion der Umgebungsvererbung.
- **CONTRACT-01 — Korrektheit, Erreichbarkeit:** Isolierte LibCST-API-Checks unter CPython3.14.7 bestätigen on_leave für ClassDef trotz on_visit=False; K nennt LibCST1.8.6. Keine Projekt-Reproduktion.
- **CONTRACT-06 — Korrektheit, Erreichbarkeit:** Reine Sprach-/re-API-Checks unter CPython3.14.7 bestätigen Gültigkeit der beiden Unicode-Einpunktbereiche und ValueError bei chr(-1) beziehungsweise chr(0x110000). Keine Projekt-Reproduktion.

## Prüfprotokoll

Jede Zeile bezeichnet zwei getrennte, frische Skeptikerkontexte. Die Reihenfolge der Urteile in der JSON-Fassung ist Korrektheit, anschließend Erreichbarkeit.

| Nr. | Kandidat | Korrektheit | Erreichbarkeit |
| ---: | --- | --- | --- |
| 1 | nondet:basis-toctou/BASIS-01 | /root/skeptic_dispatch/s001_k | /root/skeptic_dispatch/s001_e |
| 2 | nondet:staging-toctou/STAGE-01 | /root/skeptic_dispatch/s002_k | /root/skeptic_dispatch/s002_e |
| 3 | nondet:process-lifecycle/PROC-01 | /root/skeptic_dispatch/s003_k | /root/skeptic_dispatch/s003_e |
| 4 | nondet:process-lifecycle/PROC-02 | /root/skeptic_dispatch/s004_k | /root/skeptic_dispatch/s004_e |
| 5 | nondet:process-lifecycle/PROC-03 | /root/skeptic_dispatch/s005_k | /root/skeptic_dispatch/s005_e |
| 6 | nondet:ordering-determinism/ORDER-01 | /root/skeptic_dispatch/s006_k | /root/skeptic_dispatch/s006_e |
| 7 | nondet:ordering-determinism/ORDER-02 | /root/skeptic_dispatch/s007_k | /root/skeptic_dispatch/s007_e |
| 8 | nondet:ordering-determinism/ORDER-03 | /root/skeptic_dispatch/s008_k | /root/skeptic_dispatch/s008_e |
| 9 | nondet:timing-assumptions/TIME-01 | /root/skeptic_dispatch/s009_k | /root/skeptic_dispatch/s009_e |
| 10 | nondet:timing-assumptions/TIME-02 | /root/skeptic_dispatch/s010_k | /root/skeptic_dispatch/s010_e |
| 11 | nondet:timing-assumptions/TIME-03 | /root/skeptic_dispatch/s011_k | /root/skeptic_dispatch/s011_e |
| 12 | nondet:timing-assumptions/TIME-04 | /root/skeptic_dispatch/s012_k | /root/skeptic_dispatch/s012_e |
| 13 | nondet:timing-assumptions/TIME-05 | /root/skeptic_dispatch/s013_k | /root/skeptic_dispatch/s013_e |
| 14 | mod:orchestrator/ORCH-01 | /root/skeptic_dispatch/s014_k | /root/skeptic_dispatch/s014_e |
| 15 | mod:orchestrator/ORCH-02 | /root/skeptic_dispatch/s015_k | /root/skeptic_dispatch/s015_e |
| 16 | mod:orchestrator/ORCH-03 | /root/skeptic_dispatch/s016_k | /root/skeptic_dispatch/s016_e |
| 17 | mod:db/DB-01 | /root/skeptic_dispatch/s017_k | /root/skeptic_dispatch/s017_e |
| 18 | mod:db/DB-02 | /root/skeptic_dispatch/s018_k | /root/skeptic_dispatch/s018_e |
| 19 | mod:stats/STATS-01 | /root/skeptic_dispatch/s019_k | /root/skeptic_dispatch/s019_e |
| 20 | mod:stats/STATS-02 | /root/skeptic_dispatch/s020_k | /root/skeptic_dispatch/s020_e |
| 21 | mod:stats/STATS-03 | /root/skeptic_dispatch/s021_k | /root/skeptic_dispatch/s021_e |
| 22 | mod:file-setup/FILE-01 | /root/skeptic_dispatch/s022_k | /root/skeptic_dispatch/s022_e |
| 23 | mod:file-setup/FILE-02 | /root/skeptic_dispatch/s023_k | /root/skeptic_dispatch/s023_e |
| 24 | mod:file-setup/FILE-03 | /root/skeptic_dispatch/s024_k | /root/skeptic_dispatch/s024_e |
| 25 | mod:file-setup/FILE-04 | /root/skeptic_dispatch/s025_k | /root/skeptic_dispatch/s025_e |
| 26 | mod:file-setup/FILE-05 | /root/skeptic_dispatch/s026_k | /root/skeptic_dispatch/s026_e |
| 27 | mod:file-setup/FILE-06 | /root/skeptic_dispatch/s027_k | /root/skeptic_dispatch/s027_e |
| 28 | mod:worker/WORK-01 | /root/skeptic_dispatch/s028_k | /root/skeptic_dispatch/s028_e |
| 29 | mod:worker/WORK-02 | /root/skeptic_dispatch/s029_k | /root/skeptic_dispatch/s029_e |
| 30 | mod:worker/WORK-03 | /root/skeptic_dispatch/s030_k | /root/skeptic_dispatch/s030_e |
| 31 | mod:cli/CLI-01 | /root/skeptic_dispatch/s031_k | /root/skeptic_dispatch/s031_e |
| 32 | mod:cli/CLI-02 | /root/skeptic_dispatch/s032_k | /root/skeptic_dispatch/s032_e |
| 33 | mod:cli/CLI-03 | /root/skeptic_dispatch/s033_k | /root/skeptic_dispatch/s033_e |
| 34 | mod:cli/CLI-04 | /root/skeptic_dispatch/s034_k | /root/skeptic_dispatch/s034_e |
| 35 | mod:cli/CLI-05 | /root/skeptic_dispatch/s035_k | /root/skeptic_dispatch/s035_e |
| 36 | mod:cli/CLI-06 | /root/skeptic_dispatch/s036_k | /root/skeptic_dispatch/s036_e |
| 37 | mod:cli/CLI-07 | /root/skeptic_dispatch/s037_k | /root/skeptic_dispatch/s037_e |
| 38 | mod:mutation/MUT-01 | /root/skeptic_dispatch/s038_k | /root/skeptic_dispatch/s038_e |
| 39 | mod:mutation/MUT-02 | /root/skeptic_dispatch/s039_k | /root/skeptic_dispatch/s039_e |
| 40 | mod:mutation/MUT-03 | /root/skeptic_dispatch/s040_k | /root/skeptic_dispatch/s040_e |
| 41 | mod:mutation/MUT-04 | /root/skeptic_dispatch/s041_k | /root/skeptic_dispatch/s041_e |
| 42 | mod:mutation/MUT-05 | /root/skeptic_dispatch/s042_k | /root/skeptic_dispatch/s042_e |
| 43 | mod:mutation/MUT-06 | /root/skeptic_dispatch/s043_k | /root/skeptic_dispatch/s043_e |
| 44 | mod:mutation/MUT-07 | /root/skeptic_dispatch/s044_k | /root/skeptic_dispatch/s044_e |
| 45 | mod:operators/OP-01 | /root/skeptic_dispatch/s045_k | /root/skeptic_dispatch/s045_e |
| 46 | mod:operators/OP-02 | /root/skeptic_dispatch/s046_k | /root/skeptic_dispatch/s046_e |
| 47 | mod:operators/OP-03 | /root/skeptic_dispatch/s047_k | /root/skeptic_dispatch/s047_e |
| 48 | mod:operators/OP-04 | /root/skeptic_dispatch/s048_k | /root/skeptic_dispatch/s048_e |
| 49 | mod:operators/OP-05 | /root/skeptic_dispatch/s049_k | /root/skeptic_dispatch/s049_e |
| 50 | mod:operators/OP-06 | /root/skeptic_dispatch/s050_k | /root/skeptic_dispatch/s050_e |
| 51 | mod:operators/OP-07 | /root/skeptic_dispatch/s051_k | /root/skeptic_dispatch/s051_e |
| 52 | mod:operators/OP-08 | /root/skeptic_dispatch/s052_k | /root/skeptic_dispatch/s052_e |
| 53 | mod:operators/OP-09 | /root/skeptic_dispatch/s053_k | /root/skeptic_dispatch/s053_e |
| 54 | mod:runner/RUNNER-01 | /root/skeptic_dispatch/s054_k | /root/skeptic_dispatch/s054_e |
| 55 | mod:runner/RUNNER-02 | /root/skeptic_dispatch/s055_k | /root/skeptic_dispatch/s055_e |
| 56 | mod:runner/RUNNER-03 | /root/skeptic_dispatch/s056_k | /root/skeptic_dispatch/s056_e |
| 57 | mod:locking/LOCK-01 | /root/skeptic_dispatch/s057_k | /root/skeptic_dispatch/s057_e |
| 58 | mod:locking/LOCK-02 | /root/skeptic_dispatch/s058_k | /root/skeptic_dispatch/s058_e |
| 59 | mod:locking/LOCK-03 | /root/skeptic_dispatch/s059_k | /root/skeptic_dispatch/s059_e |
| 60 | mod:locking/LOCK-04 | /root/skeptic_dispatch/s060_k | /root/skeptic_dispatch/s060_e |
| 61 | mod:spawn/SPAWN-01 | /root/skeptic_dispatch/s061_k | /root/skeptic_dispatch/s061_e |
| 62 | mod:spawn/SPAWN-02 | /root/skeptic_dispatch/s062_k | /root/skeptic_dispatch/s062_e |
| 63 | mod:spawn/SPAWN-03 | /root/skeptic_dispatch/s063_k | /root/skeptic_dispatch/s063_e |
| 64 | mod:spawn/SPAWN-04 | /root/skeptic_dispatch/s064_k | /root/skeptic_dispatch/s064_e |
| 65 | mod:atomic/ATOM-01 | /root/skeptic_dispatch/s065_k | /root/skeptic_dispatch/s065_e |
| 66 | mod:atomic/ATOM-02 | /root/skeptic_dispatch/s066_k | /root/skeptic_dispatch/s066_e |
| 67 | mod:atomic/ATOM-03 | /root/skeptic_dispatch/s067_k | /root/skeptic_dispatch/s067_e |
| 68 | mod:atomic/ATOM-04 | /root/skeptic_dispatch/s068_k | /root/skeptic_dispatch/s068_e |
| 69 | mod:data/DATA-01 | /root/skeptic_dispatch/s069_k | /root/skeptic_dispatch/s069_e |
| 70 | mod:data/DATA-02 | /root/skeptic_dispatch/s070_k | /root/skeptic_dispatch/s070_e |
| 71 | mod:data/DATA-03 | /root/skeptic_dispatch/s071_k | /root/skeptic_dispatch/s071_e |
| 72 | mod:data/DATA-04 | /root/skeptic_dispatch/s072_k | /root/skeptic_dispatch/s072_e |
| 73 | mod:data/DATA-05 | /root/skeptic_dispatch/s073_k | /root/skeptic_dispatch/s073_e |
| 74 | mod:presentation/VIEW-01 | /root/skeptic_dispatch/s074_k | /root/skeptic_dispatch/s074_e |
| 75 | mod:presentation/VIEW-02 | /root/skeptic_dispatch/s075_k | /root/skeptic_dispatch/s075_e |
| 76 | mod:presentation/VIEW-03 | /root/skeptic_dispatch/s076_k | /root/skeptic_dispatch/s076_e |
| 77 | mod:presentation/VIEW-04 | /root/skeptic_dispatch/s077_k | /root/skeptic_dispatch/s077_e |
| 78 | mod:presentation/VIEW-05 | /root/skeptic_dispatch/s078_k | /root/skeptic_dispatch/s078_e |
| 79 | mod:presentation/VIEW-06 | /root/skeptic_dispatch/s079_k | /root/skeptic_dispatch/s079_e |
| 80 | mod:rest/REST-01 | /root/skeptic_dispatch/s080_k | /root/skeptic_dispatch/s080_e |
| 81 | mod:rest/REST-02 | /root/skeptic_dispatch/s081_k | /root/skeptic_dispatch/s081_e |
| 82 | mod:rest/REST-03 | /root/skeptic_dispatch/s082_k | /root/skeptic_dispatch/s082_e |
| 83 | mod:rest/REST-04 | /root/skeptic_dispatch/s083_k | /root/skeptic_dispatch/s083_e |
| 84 | mod:rest/REST-05 | /root/skeptic_dispatch/s084_k | /root/skeptic_dispatch/s084_e |
| 85 | lens:races/RACE-01 | /root/skeptic_dispatch/s085_k | /root/skeptic_dispatch/s085_e |
| 86 | lens:races/RACE-02 | /root/skeptic_dispatch/s086_k | /root/skeptic_dispatch/s086_e |
| 87 | lens:races/RACE-03 | /root/skeptic_dispatch/s087_k | /root/skeptic_dispatch/s087_e |
| 88 | lens:races/RACE-04 | /root/skeptic_dispatch/s088_k | /root/skeptic_dispatch/s088_e |
| 89 | lens:races/RACE-05 | /root/skeptic_dispatch/s089_k | /root/skeptic_dispatch/s089_e |
| 90 | lens:failclosed/FAIL-01 | /root/skeptic_dispatch/s090_k | /root/skeptic_dispatch/s090_e |
| 91 | lens:failclosed/FAIL-02 | /root/skeptic_dispatch/s091_k | /root/skeptic_dispatch/s091_e |
| 92 | lens:failclosed/FAIL-03 | /root/skeptic_dispatch/s092_k | /root/skeptic_dispatch/s092_e |
| 93 | lens:windows/WIN-01 | /root/skeptic_dispatch/s093_k | /root/skeptic_dispatch/s093_e |
| 94 | lens:windows/WIN-02 | /root/skeptic_dispatch/s094_k | /root/skeptic_dispatch/s094_e |
| 95 | lens:windows/WIN-03 | /root/skeptic_dispatch/s095_k | /root/skeptic_dispatch/s095_e |
| 96 | lens:windows/WIN-04 | /root/skeptic_dispatch/s096_k | /root/skeptic_dispatch/s096_e |
| 97 | lens:windows/WIN-05 | /root/skeptic_dispatch/s097_k | /root/skeptic_dispatch/s097_e |
| 98 | lens:resources/RES-01 | /root/skeptic_dispatch/s098_k | /root/skeptic_dispatch/s098_e |
| 99 | lens:resources/RES-02 | /root/skeptic_dispatch/s099_k | /root/skeptic_dispatch/s099_e |
| 100 | lens:resources/RES-03 | /root/skeptic_dispatch/s100_k | /root/skeptic_dispatch/s100_e |
| 101 | lens:resources/RES-04 | /root/skeptic_dispatch/s101_k | /root/skeptic_dispatch/s101_e |
| 102 | lens:resources/RES-05 | /root/skeptic_dispatch/s102_k | /root/skeptic_dispatch/s102_e |
| 103 | lens:resources/RES-06 | /root/skeptic_dispatch/s103_k | /root/skeptic_dispatch/s103_e |
| 104 | lens:resources/RES-07 | /root/skeptic_dispatch/s104_k | /root/skeptic_dispatch/s104_e |
| 105 | lens:resources/RES-08 | /root/skeptic_dispatch/s105_k | /root/skeptic_dispatch/s105_e |
| 106 | lens:resources/RES-09 | /root/skeptic_dispatch/s106_k | /root/skeptic_dispatch/s106_e |
| 107 | lens:boundaries/EDGE-01 | /root/skeptic_dispatch/s107_k | /root/skeptic_dispatch/s107_e |
| 108 | lens:boundaries/EDGE-02 | /root/skeptic_dispatch/s108_k | /root/skeptic_dispatch/s108_e |
| 109 | lens:boundaries/EDGE-03 | /root/skeptic_dispatch/s109_k | /root/skeptic_dispatch/s109_e |
| 110 | lens:boundaries/EDGE-04 | /root/skeptic_dispatch/s110_k | /root/skeptic_dispatch/s110_e |
| 111 | lens:boundaries/EDGE-05 | /root/skeptic_dispatch/s111_k | /root/skeptic_dispatch/s111_e |
| 112 | lens:boundaries/EDGE-06 | /root/skeptic_dispatch/s112_k | /root/skeptic_dispatch/s112_e |
| 113 | lens:boundaries/EDGE-07 | /root/skeptic_dispatch/s113_k | /root/skeptic_dispatch/s113_e |
| 114 | lens:boundaries/EDGE-08 | /root/skeptic_dispatch/s114_k | /root/skeptic_dispatch/s114_e |
| 115 | lens:contracts/CONTRACT-01 | /root/skeptic_dispatch/s115_k | /root/skeptic_dispatch/s115_e |
| 116 | lens:contracts/CONTRACT-02 | /root/skeptic_dispatch/s116_k | /root/skeptic_dispatch/s116_e |
| 117 | lens:contracts/CONTRACT-03 | /root/skeptic_dispatch/s117_k | /root/skeptic_dispatch/s117_e |
| 118 | lens:contracts/CONTRACT-04 | /root/skeptic_dispatch/s118_k | /root/skeptic_dispatch/s118_e |
| 119 | lens:contracts/CONTRACT-05 | /root/skeptic_dispatch/s119_k | /root/skeptic_dispatch/s119_e |
| 120 | lens:contracts/CONTRACT-06 | /root/skeptic_dispatch/s120_k | /root/skeptic_dispatch/s120_e |
| 121 | lens:contracts/CONTRACT-07 | /root/skeptic_dispatch/s121_k | /root/skeptic_dispatch/s121_e |

## Integrität und Ablieferung

Die beiden ausdrücklich beauftragten, ungetrackten Berichtsdateien waren die einzige Schreibausnahme. ASTRA_REVIEW.json enthielt zwischenzeitlich den als unbestätigt markierten Kandidatenbestand; ASTRA_BUG_COLLECTION.md das Prüfprotokoll. Beide wurden erst nach Abschluss der Prüfungen finalisiert. Quellcode, Tests und Konfiguration wurden nicht geändert; kein Commit wurde erstellt.

SHA-256 der finalen ASTRA_REVIEW.json: `673a5909320b27fbe46702c6f2925c6f16ad342036d04ba9ff5981bd6de51370`. Schema, Zähler und die Zuordnung zu 26 Findern sowie 242 getrennten Skeptikern wurden geprüft. Die abschließenden Git-Leseprüfungen bestätigen den angegebenen Commit und Tag sowie unveränderte getrackte Dateien; ausschließlich die beiden beauftragten Berichte sind ungetrackt.
