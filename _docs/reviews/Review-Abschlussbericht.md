# Review-Abschlussbericht mutmut-win v2.21.4

*Abschließendes adversariales Kreuzreview (Claude) über die Einzelreviews von Claude und Astra sowie Astras Kreuzreview. Inhaltlich identisch mit [CLAUDE_CROSSREVIEW.md](CLAUDE_CROSSREVIEW.md); alle Einzelurteile, Belege und Prüfverläufe stehen in [CLAUDE_CROSSREVIEW.json](CLAUDE_CROSSREVIEW.json).*

Bezugsstand: mutmut-win v2.21.4, Commit `4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b`, Tag v2.21.4 (HEAD und Tag geprüft), Windows / CPython 3.14.7. Erstellt am 23.09.2026 in `C:/claude_codex/mutmut-win-astra`.

Geprüft wurden alle 143 Befunde meines Originalberichts, alle 118 Befunde Astras, Astras Kreuzreview mit allen 124 Paarungen, die 76 bzw. 43 Befunde ohne Ortsentsprechung sowie die 50 bzw. 3 Verwerfungen. Jedes Einzelurteil mit Codepfad, Belegen, Prüfverlauf und Restunsicherheit steht in [CLAUDE_CROSSREVIEW.json](CLAUDE_CROSSREVIEW.json).

> **Nur statisch geprüft.** Nicht ausgeführt wurden pytest, mutmut-win, Builds, Installationen und Prozessreproduktionen. Ausgeführt wurden nur kurze `python -I -c`-Prüfungen von API-, Regex- und Bibliothekssemantik sowie Auswerteskripte über die Berichte. Kein Test wird als bestanden ausgewiesen.

| Ursprung | Einträge | bestätigt | teilweise | widerlegt | nicht prüfbar | high | medium | low |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude (Originalbericht) | 143 | 8 | 103 | 23 | 9 | 3 | 50 | 58 |
| Astra | 118 | 74 | 38 | 4 | 2 | 9 | 45 | 58 |

Die Zahlen zählen Einträge, nicht Defekte. Unabhängig gezählt ergeben sich **172 Mechanismusgruppen**, davon **146 mit tragendem Defekt** (high 9, medium 56, low 81). 30 dieser Gruppen tragen Befunde aus beiden Berichten, 58 nur aus meinem Bericht und 58 nur aus Astras Bericht. Kein Eintrag beider Berichte trägt critical.

**Integrität.** Alle Nenner stimmen: 193/143/50 (Claude), 121/118/3 (Astra), 143 Urteile, 118 Status und 124 Paarungen in Astras Kreuzreview; die Paarungen und die Lückenmengen 76/43 sind identisch mit OVERLAP_CANDIDATES.json. Alle sieben Eingaben sind bytegleich zum Sitzungsbeginn (SHA-256 in `metadaten.eingaben`). Die finderlokalen `id`-Felder meines Berichts sind nicht eindeutig (16 Werte mehrfach); maßgeblich ist `bc_id`.

**Verfahren.** 1158 Agentenläufe in fünf Stufen: Blindprüfung (nur Behauptung und Ort), Gegenargument, blinde Zweitprüfung von Erreichbarkeit und Auswirkung, Adjudikation; anschließend Grenzfälle mit zwei Richtern und neutralisierten Lesarten (C1: 47 meiner Befunde, C2: 20 Astras) und eine Konsolidierung über Paarungen, Gruppen und Schwere (C). Maßgeblich ist bei Widerspruch: Gruppenadjudikation vor Schwerekalibrierung vor C1/C2 vor der Erstprüfung. Die Blindprüfer liefen teils unter Fable 5.1, später unter Opus 5 bzw. Opus 5.5. Fable 5.1 bestätigte blind 8/84 meiner und 10/16 von Astras Befunden; die Asymmetrie liegt damit an den Befunden, nicht am Modell.

**Offenlegung.** Scratchpad und persistierte Tool-Ausgaben dieser Sitzung liegen technisch unter den nominell gesperrten Bäumen `AppData/Local/Temp/claude` und `.claude/projects`. Genutzt wurden nur Artefakte dieser Sitzung; keine alten Transkripte, Agentenprotokolle oder Erinnerungen. Fehlende Begründungen meiner ursprünglichen Erhebung wurden nicht rekonstruiert.

## 1. Was belastbar bleibt

Neun Mechanismusgruppen tragen abschließend **high**. Alle sind am Code belegt; keine wurde dynamisch reproduziert.

| Gruppe | Defekt | Tragende Einträge | Kernstelle | Konfidenz |
| --- | --- | --- | --- | --- |
| M-001 | Gitignore-Pruning lässt bereits getrackte Quellen aus der Mutationsauswahl | REST-04 (bestätigt/high) | src/mutmut_win/gitignore_boundary.py:210-232 (Z. 229) mit 179-200 | hoch |
| M-002 | Wiederholte Coverage-Läufe messen Generatorcode statt Originalzeilen | FILE-01 (bestätigt/high), FILE-03 (bestätigt/medium) | src/mutmut_win/file_setup.py:1348-1351 (_mirror_is_stale, Zweig fuer eigene .meta) zusamm… | hoch |
| M-003 | Nicht kompilierbarer oder nicht parsebarer Mutantensatz verschwindet still aus dem Nenner, ohne dem Lauf die… | BC-078 (teilweise/high) | src/mutmut_win/file_setup.py:2213-2249; orchestrator.py:1242-1248 | hoch |
| M-004 | Ausscheidende Kindprozesse können Timeouts fälschlich zu Infinite-Loop-Kills machen | SPAWN-02 (bestätigt/high) | src/mutmut_win/process/loop_monitor.py:491 | hoch |
| M-005 | apply überschreibt Quelländerungen zwischen Staleness-Prüfung und Veröffentlichung | RACE-04 (bestätigt/high), CONTRACT-04 (bestätigt/high), VIEW-02 (bestätigt/high) | src/mutmut_win/mutant_diff.py:577 (einzige Pruefung) bis 617 (bedingungsloses Ersetzen);… | hoch |
| M-006 | Projektinternes .venv wird durch die Gitignore-Grenze vollstaendig aus dem Kontext-Digest gestrichen - sitecu… | BC-052 (bestätigt/high) | src/mutmut_win/stats.py:1040-1053 | hoch |
| M-007 | ZIP-Unterpfade können aus einer als vollständig ausgewiesenen Basis fehlen | STATS-03 (bestätigt/high) | src/mutmut_win/stats.py:983-990 | hoch |
| M-008 | Proof-Publikation im generierten Guard-Plugin ist nicht fehlerbehandelt: transiente Publikationsstoerung wird… | BC-003 (teilweise/high), WORK-01 (bestätigt/high) | src/mutmut_win/process/worker.py:477-479 (ungeschuetzter Aufruf) in Verbindung mit worker… | hoch |
| M-009 | PPID-Bereinigung kann nach PID-Wiederverwendung fremde Prozesse beenden | RACE-01 (bestätigt/high) | src/mutmut_win/process/worker.py:1621-1636, 1684-1690 | hoch |

Darüber hinaus tragen **56 medium-** und **81 low-Gruppen**. Belastbar sind vor allem die Gruppen, die beide Berichte unabhängig gefunden haben (Abschnitt 6), und Astras Befunde: 112 von 118 tragen, 74 davon unverändert.

Von meinen 143 Einträgen tragen 111, aber nur 8 unverändert. 48 tragen mit korrigierter Schwere, 48 mit engerer Reichweite, 7 nur als Restdefekt anderer Art.

## 2. Wo Astra recht hat

**Kritik an meinem Bericht.** Astras Kernkritik trägt vollständig (Einzelheiten in Abschnitt 4):

- Die Aggregationsregel „widerlegt nur bei beidseitiger Widerlegung“ ließ 37 Einträge mit einem widerlegenden Skeptiker durch; abschließend sind davon 15 widerlegt und 6 nicht prüfbar (SK-01).
- Bei allen fünf critical-Einträgen lehnten beide Skeptiker critical ab; keiner hält. Die Zahl von 55 Einträgen mit zwei niedrigeren Skeptikerempfehlungen ist plausibel, aber aus dem Freitext nicht exakt nachzuzählen (SK-02).
- BC-114 und BC-120 haben nur ein Verdict; BC-120 stand trotz refuted=true unter confirmed und ist abschließend widerlegt (SK-03).
- Alle 50 Verwerfungsbegründungen sind auf 600 Zeichen gekürzt (SK-04).

**Urteile zu meinen Befunden.** In 120 von 143 Fällen stimmt die Urteilsklasse (Defekt / widerlegt / nicht prüfbar) mit Astra überein, in 111 exakt. Von meinen 23 widerlegten Einträgen hatte Astra 19 ebenfalls widerlegt. Wo beide einen Defekt sehen, stimmt die Schwere in 76 von 97 Fällen.

**Nachkalibrierung BC-017 und BC-141.** Beide tragen:

- BC-017: Original high, Astra vor dem Matching teilweise/medium, Astra final teilweise/low, abschließend teilweise/low.
- BC-141: Original low, Astra vor dem Matching bestätigt/low, Astra final teilweise/medium, abschließend teilweise/medium.

**Astras Selbstkorrekturen.** Beide aufgehobenen Bestätigungen tragen: ORDER-02 ist widerlegt (repr(set)-Reihenfolge ohne Produktkonsumenten, deckungsgleich mit meinem BC-104), ORDER-03 bleibt nicht prüfbar (Reihenfolgedrift unter Windows nicht belegt, deckungsgleich mit BC-016). Von den zehn Schwereherabstufungen tragen 6 (LOCK-01, CONTRACT-03, WIN-03, VIEW-03, VIEW-04, RACE-03).

**Paarungen.** 108 der 124 Paarbeziehungen bestätige ich; alle 13 von Astra genannten semantischen Treffer außerhalb des Ortsjoins tragen.

**Stichprobe.** Alle 22 technischen Kerne der Phase-0-Stichprobe tragen. Der eingefrorene Audit zeigt 22/22, die JSON-Endfassung 20/22; das ist offen erklärt und intern konsistent.

## 3. Wo Astras Kreuzreview irrt oder zu weit geht

**Überwiderlegung meiner Befunde.** 11 Befunde, die Astra widerlegt, tragen am Code einen Defekt; 3, die Astra für nicht prüfbar hält, ebenfalls. Umgekehrt halte ich 4 von Astra widerlegte Befunde für nicht prüfbar und 4 von Astra für nicht prüfbar gehaltene für widerlegt.

| Befund | Astra | Abschließend | Tragender Kern |
| --- | --- | --- | --- |
| BC-038 | widerlegt | teilweise/low | Die behauptete Fehlwirkung traegt nicht: Laut Befund verwirft der feste 15-s-Join nach DONE eine fertige Generierung faelschlich (high/correctness). Die begrenzte, fail-closed Post-DONE-Schranke ist… |
| BC-044 | widerlegt | teilweise/low | Der Mechanismus traegt: Alle pytest-Phasen (runner.py:368) und alle Worker (worker.py:1174) laufen mit cwd=mutants im voll gehashten Staging-Baum (stats.py:663-682). Die behauptete Folge (Vertragsbru… |
| BC-048 | widerlegt | teilweise/medium | Nicht die Strenge gegenueber Schreibzugriffen der Nutzer-Testsuite ist der Defekt (dort ist fail-closed dokumentierte Absicht, file_setup.py:228-237, README.md:304; der ABA-Fall bei sauberem Teardown… |
| BC-068 | widerlegt | teilweise/low | Nur die Diagnosehaelfte traegt: In _load_setup_cfg (src/mutmut_win/config.py:489-495) umfasst die Unknown-Option-Pruefung auch aus [DEFAULT] geerbte Schluessel, weil parser.options("mutmut") die effe… |
| BC-069 | widerlegt | teilweise/low | Die Originalbehauptung ist in ihren Folgen entkräftet: kein verfälschter Score (fail-closed Clean-Run), ein Opt-in über Datei oder Unterpfad existiert, und es gibt keine veralteten Verdikte. |
| BC-070 | widerlegt | teilweise/low | Es bleibt allein ein Diagnosedefekt: Meldet os.lstat fuer mutmut-cache.db st_nlink == 0 (CPython-3.14.7-Fallback fuer eine nicht oeffenbare regulaere Datei, zugleich st_ino == st_dev == 0), bricht sr… |
| BC-079 | widerlegt | teilweise/low | Die behauptete Folge (lesbare, aber verworfene Ignore-Regeln erweitern still den gehashten/gestageten Baum, ohne complete zu senken) traegt nur fuer den ValueError-Zweig (gitignore_boundary.py:106-11… |
| BC-083 | widerlegt | teilweise/low | record_trampoline_hit verbraucht sein max_stack_depth-Budget ab dem eigenen Frame. |
| BC-098 | widerlegt | teilweise/low | Der Phase-Guard (src/mutmut_win/process/worker.py:470-471) behandelt erwartet fehlschlagende xfail-call-Reports (outcome 'skipped' + wasxfail) wie 'kein Test ausgefuehrt'. Da die autoritative Testsel… |
| BC-100 | widerlegt | teilweise/low | Der Mechanismus traegt. _popen_contained (src/mutmut_win/process/worker.py:1555-1557) reicht im Double-Zweig proc.pid ohne die Schranke isinstance(proc, _REAL_POPEN_TYPE) an _create_task_job weiter. |
| BC-129 | widerlegt | teilweise/low | read_owned_source_metadata (src/mutmut_win/models.py:430) gibt das unnormalisierte Dict zurück, obwohl derselbe Validator (models.py:354-364) großgeschriebene Digests als gültig akzeptiert und in loa… |
| BC-019 | nicht prüfbar | teilweise/low | Im regulaeren Streamingpfad ruft save_results (db.py 1647) fuer jedes einzeln persistierte Verdict create_db(path) auf, obwohl orchestrator.py 911 das Schema vor dem Event-Loop bereits angelegt hat. |
| BC-054 | nicht prüfbar | teilweise/medium | run_type_checker (src/mutmut_win/type_checking.py:386-391) parst im mypy-Zweig jede stdout-Zeile mit json.loads, ohne Leerzeilen zu ueberspringen. |
| BC-074 | nicht prüfbar | teilweise/low | validate_staging_namespace und copy_src_dir verrichten auf dem regulären Startpfad belegbar überflüssige Arbeit: pro gewalktem Verzeichnis wird dasselbe Verzeichnis zwei- bis dreimal per resolve() au… |

**Eigene Befunde zu großzügig gehalten.** Astra hält drei Bestätigungen, die am Code nicht tragen: CLI-04, FAIL-03, RES-05; TIME-02 ist nicht prüfbar. Bei 30 weiteren gehaltenen Befunden liegt die Schwere niedriger als Astras Endstand.

**Herabstufungen, die zu weit gehen.** FILE-04 bleibt medium: jeder Folgelauf ohne `--force` bricht mit einer fremden OSError ab (Gruppe M-030). OP-07, EDGE-02 und CONTRACT-06 bleiben medium, BC-139 steigt auf medium: der ungefangene ValueError aus `chr()` bricht im Default-Profil ADVANCED die Mutantenerzeugung ab (M-050).

**Stichprobe 20/22.** Technisch tragen 22/22, bei unveränderter Originalschwere aber nur 13/22. Neben LOCK-01 und CONTRACT-03 sinken MUT-01 und SPAWN-01 (high → medium) sowie ATOM-01, OP-08, LOCK-03, ORDER-01 und WORK-02 (medium → low). Die Stichprobe belegt Astras Mechanismen, nicht ihre Schwerekalibrierung.

**Konflikte verworfen gegen bestätigt.** In 5/7 von Astras sieben Zuordnungen stimmt die Richtung. Abweichend: PROC-05 (mein verworfener Befund) gegen CLI-04 und RES-05. Beide Astra-Befunde sind widerlegt, weil der Jobhandle-Rest nur im direkten API-Lauf eine Folge hat (ORCH-01, CONTRACT-05, BC-090 tragen low; Gruppenadjudikation F-FRUEHER-EXECUTOR). Astras Abgleich der 50 Verwerfungen war zudem nicht erschöpfend: Unerwähnt blieben die Kreuzbezüge BROW-05 ↔ VIEW-03, EXEC-01 ↔ RACE-02.

**Paarbeziehungen.** 16 der 124 Beziehungen weichen ab:

| Paar | Astra | Abschließend | Begründung |
| --- | --- | --- | --- |
| BC-007 ↔ ATOM-04 | verwandt | zufällige Nähe | Nach dem geltenden C1-Endurteil liegt der Restdefekt von BC-007 nicht am Sibling-Namen in Z. 172. Er liegt im retrylosen Schnellpfad von ensure_atomic_bytes: _regular_file_matches_bytes gibt bei jedem OSError False zurueck (atomic_file.py:… |
| BC-007 ↔ WIN-01 | verwandt | zufällige Nähe | WIN-01 beschreibt inhaltlich denselben Laengendefekt wie ATOM-04: Basename + 52 Zeichen ueberschreiten ab 204 Zeichen die Komponentengrenze von 255, unabhaengig von LongPathsEnabled. |
| BC-017 ↔ DATA-04 | zufällige Nähe | verwandt | Beide Befunde verletzen denselben Vertrag an derselben Grenze: load_config (config.py:542-619) soll Konfigurationsfehler als ConfigError liefern (Docstring 555-556), und der einzige Abnehmer _load_config_or_exit (cli.py:211-217) faengt aus… |
| BC-017 ↔ DATA-05 | zufällige Nähe | verwandt | DATA-05 betrifft UnicodeDecodeError, der weder vom Tupel (ConfigParserError, OSError) in _load_setup_cfg (config.py:463) noch von (tomllib.TOMLDecodeError, OSError) in load_config (config.py:572) erfasst wird; BC-017 betrifft die fehlende… |
| BC-025 ↔ EDGE-01 | verwandt | zufällige Nähe | Beide liegen in create_trampoline_wrapper, teilen aber weder Ursache noch Ausloeser noch Fix. |
| BC-025 ↔ MUT-02 | verwandt | zufällige Nähe | Beide Befunde haengen daran, dass die privaten Implementierungen im Klassenkoerper liegen (627). Die Ursachen sind trotzdem verschieden. |
| BC-066 ↔ CLI-01 | verwandt | zufällige Nähe | BC-066 ist ein Semantikfehler des Testausschlusses: nur die exakt konfigurierten tests_dir-Praefixe werden ausgeschlossen (cli.py:597-600, 611), Testdateien ausserhalb davon werden Ziele (625, 640). CLI-01 ist die fehlende Optionsgrenze/Re… |
| BC-066 ↔ CLI-02 | verwandt | zufällige Nähe | CLI-02 betrifft die Pfadbasis der Git-Ausgabe gegen das Projekt-CWD in der Existenzpruefung (cli.py:604) und fuehrt zu verlorenen echten Aenderungen (zu wenige Ziele, No-op mit Exit 0, cli.py:626-639). BC-066 betrifft die bewusst eng gefas… |
| BC-081 ↔ REST-05 | verwandt | zufällige Nähe | BC-081 ist fehlende Case-Faltung beim Matching: die Kandidaten werden unveraendert an pattern.match_file uebergeben (gitignore_boundary.py:42-45, 47-57, 222-229), pathspec kompiliert case-sensitiv. |
| BC-082 ↔ REST-04 | verwandt | zufällige Nähe | Beide ankern in der Musterschleife von _excludes (gitignore_boundary.py:224-229), teilen aber keinen Mechanismus. |
| BC-133 ↔ MUT-05 | verwandt | zufällige Nähe | Beide gehoeren zum Pragma-Feature, liegen aber in getrennten Funktionen mit getrennter Logik. |
| BC-134 ↔ EDGE-05 | zufällige Nähe | verwandt | Kein selber Defekt: BC-134 ist die Unerreichbarkeit des autoritativen Zweigs (:1578; das Bit wird in _assign_tests_to_tasks :1626 aus stats.mapping_is_authoritative uebernommen, das auf allen Produktionspfaden False ist: stats.py:111, :190… |
| BC-137 ↔ CONTRACT-07 | verwandt | zufällige Nähe | Beide Befunde liegen im finally von _process_task, haben aber sich gegenseitig ausschliessende Vorbedingungen an derselben Anweisung (worker.py:1233): BC-137 setzt voraus, dass consume_pytest_phase_guard regulaer False zurueckgibt (exit_co… |
| BC-137 ↔ PROC-01 | verwandt | zufällige Nähe | PROC-01 ist inhaltlich derselbe UnicodeDecodeError-Pfad wie CONTRACT-07 (consume_pytest_phase_guard 863-871 faengt nur OSError; Ausnahme verlaesst 1233 und ueberspringt close_job 1246, monitor.shutdown 1257, capture.close 1258-1259). BC-13… |
| BC-137 ↔ RES-01 | verwandt | zufällige Nähe | RES-01 beschreibt denselben Ausnahmeabbruch des finally durch UnicodeDecodeError aus 1233 (Folge: Monitor-Thread, Task-Job, Capture bleiben bestehen). BC-137 ist ein Diagnoseverlust im regulaer durchlaufenen finally (1234-1239 praeempiert… |
| BC-137 ↔ WORK-02 | verwandt | zufällige Nähe | WORK-02 nennt neben dem Cleanup-Leck auch eine verlorene pytest-Diagnose; diese entsteht aber auf einem anderen Weg: Die Ausnahme aus 1233 verlaesst _process_task, und worker_main (974-998) erzeugt ein synthetisches TaskCompleted mit durat… |

**Gemeinsame Schnittmenge zu eng.** Astras Tabelle nennt 26 Gruppen. Abschließend tragen 30 Gruppen Befunde aus beiden Berichten (Abschnitt 6).

**Methodenaussagen.** Belegt sind die Nenner, die 600-Zeichen-Kürzung, BC-114/BC-120, 18/5 Zitat- und Zeilenfehler (Astras Maßstab) und die eingefrorenen Audits. Plausibel, aber nicht exakt nachzählbar ist die Zahl von 55 Einträgen mit zwei niedrigeren Skeptikerempfehlungen (heuristisch mindestens 35; für alle 5 critical-Einträge einzeln belegt). Nur Selbstangabe sind die Zeitpunkte vor Fremdzugriff und der Verzicht auf critical. Die beschriebene Seed-Ziehung ließ sich mit sechs naheliegenden Lesarten nicht nachrechnen; die Beschreibung ist unterbestimmt.

## 4. Wo mein Bericht irrt

Mein Bericht hat die Schwere systematisch überzogen und schwache Kandidaten durchgelassen. Von 56 Einträgen mit critical oder high bleiben 2 high (BC-003, BC-052); kein critical hält. 23 Einträge sind widerlegt, 9 nicht prüfbar.

| Original → abschließend | high | medium | low | – (widerlegt / nicht prüfbar) |
| --- | ---: | ---: | ---: | ---: |
| critical | 1 | 3 | 1 | 0 |
| high | 1 | 29 | 8 | 13 |
| medium | 1 | 16 | 30 | 11 |
| low | 0 | 2 | 19 | 8 |

Kuratierungsfehler:

- **Aggregationsregel (SK-01):** Ein Kandidat galt nur bei beidseitiger Widerlegung als widerlegt. 36 Einträge wurden trotz eines widerlegenden Skeptikers als confirmed geführt; dazu BC-120 mit einem einzigen, widerlegenden Verdict. Endurteile dieser 37 Einträge: 15 widerlegt, 6 nicht prüfbar, 16 teilweise. Die Regel hat schwache Kandidaten systematisch durchgelassen.
- **Hauptschwere nicht an die Skeptiker angepasst (SK-02):** Alle 5 critical-Einträge (BC-001..BC-005) tragen zwei Skeptikerurteile, die critical ausdrücklich ablehnen; über alle Einträge empfehlen nach Astras Zählung bei 55 beide Skeptiker eine niedrigere Schwere. Kein Eintrag bleibt critical; von 56 critical/high bleiben 2 high (BC-003, BC-052); BC-078 steigt von medium auf high.
- **BC-114 und BC-120 (SK-03):** Beide Einträge haben nur ein Verdict (method-Feld verspricht zwei). BC-120: das einzige Verdict ist refuted=true, der Eintrag steht dennoch unter confirmed; BC-114: ein nicht widerlegendes Verdict. BC-120 abschließend widerlegt/keine, BC-114 nicht_pruefbar/keine.
- **600-Zeichen-Kürzung der Verwerfungen (SK-04):** Alle 50 refuted-why-Texte sind exakt 600 Zeichen lang (abgeschnitten). Verwerfungsbegründungen sind nicht vollständig prüfbar; es wurde nichts rekonstruiert. Konflikte verworfen-vs-bestätigt wurden über das Endurteil des bestätigten Befunds aufgelöst. Das Cluster-Screening erkannte 2 von Astras 7 Zuordnungen (PROC-05 zu CLI-04 bzw. RES-05) nicht; beide wurden nachgetragen.
- **Intra-Bericht-Widersprüche (SK-05):** 9 Fälle, in denen mein Bericht denselben Mechanismus zugleich verwirft und bestätigt (z. B. ORCH-06 verworfen, BC-104 bestätigt; beide repr(set)-Reihenfolge). Aufgelöst in konflikte (art intra_widerspruch); BC-104 abschließend widerlegt.
- **Mehrfachzählung (SK-06):** 12 Mechanismusgruppen enthalten zwei oder mehr tragende Claude-Einträge (insgesamt 35 Einträge), z. B. M-062 (Staging-/Basis-Lesefehler) mit 7 tragenden Einträgen. 143 Einträge sind keine 143 Defekte; tragend sind 111 Einträge in 88 Gruppen.
- **Zitate und Zeilen (SK-07):** Meine Blindprüfer fanden 3 nicht wörtliche Zitate und 7 falsche Hauptzeilen; Astra zählt 18 bzw. 5 (strengerer Wortlautmaßstab). Übereinstimmend beanstandet: 3 Zitate, 5 Zeilen. Kein Mechanismus fällt allein an Zitat- oder Zeilenfehlern.
- **Metadaten (SK-08):** source-Feld nennt Opus 5, der Auftrag Fable 5.1; finderlokale id-Felder sind nicht eindeutig. Nur dokumentiert, ohne Urteilswirkung.

Widerlegte Einträge meines Berichts:

| Befund | Original | Titel | Gegenbeweis |
| --- | --- | --- | --- |
| BC-014 | high | --do-not-mutate verengt das Mutantenuniversum, umgeht aber die --min-score-Subset-Sperre… | Der Mechanismus existiert (cli.py 517-519 und 714 kennen do_not_mutate nicht; cli.py 543-544 mischt das Flag additiv in die effektive MutmutConfig; config.py 395 / orchestrator.py 1142-1146 filtern vor der Generierung).… |
| BC-020 | high | Jeder Reparse-Punkt gilt als Link - Deduplizierungs- und Cloud-Volumes verlieren den komp… | (1) Totalverlust führt nicht zu einem Clean-Run: Bei 'not dry_run and result.total_mutants == 0' endet der Lauf mit 'No testable mutants were generated; mutation run failed closed.' und sys.exit(1) (src/mutmut_win/cli.p… |
| BC-032 | high | Gemessener Startup-Floor wird bei 60 s absolut gedeckelt und einprozessig gemessen, aber… | run() -> _assign_tests_to_tasks (orchestrator.py:785) setzt test_selection_is_authoritative = stats.mapping_is_authoritative (:1626), das aus jeder Produktionsquelle False ist (stats.py:111/190-191/1543/1733) -> _comput… |
| BC-040 | high | PYTHONHASHSEED wird fuer keine pytest-Phase gepinnt und ist nicht Teil der Run-Basis | Die behauptete Folge (falscher Kill bzw. geschoenter Score, als korrekt ausgewiesen, plus eine 'Determiniertheit', die die Basis zusagt, aber nicht absichert) ist kein werkzeugeigenes Fehlverhalten. |
| BC-041 | high | Das Task-Wallclock-Budget deckt das komplette Worker-Setup mit ab; pytest bekommt keine g… | Das behauptete 5,0-s-Taskbudget entsteht produktiv nie. |
| BC-042 | high | Feste Erzeugungsreihenfolge plus 12er-Cap verhungert Anker-, Klassen- und Gruppen-Mutator… | Der Mechanismus stimmt: Die fuenf Familien werden in fester Reihenfolge konkateniert (regex_mutation.py:66-70), und die Auswahlschleife bricht beim 12. gueltigen Kandidaten ab (77-84). Fuer '^[\w.-]+@[\w.-]+\.\w{2,}$' f… |
| BC-050 | high | core-Digest bindet globale sys.path-Indizes und Fehler fremder Eintraege - ambiente Aende… | Die behauptete Fehlklassifikation braucht eine Verschiebung der globalen sys.path-Indizes im ELTERNprozess zwischen zwei Basis-Snapshots desselben Prozesses. |
| BC-055 | high | 180-s-Subprozesslimit der E2E-Pipeline widerspricht der dokumentierten Coverage-Verdopplu… | Die behauptete Folge (nichtdeterministisches subprocess.TimeoutExpired, weil Coverage-Tracing die Laufzeit von ~95 s ueber 180 s treibt) hat am Bezugsstand keinen tragenden Mechanismus: (1) Coverage propagiert NICHT in… |
| BC-056 | high | E2E-Snapshot-Test macht sich rot an genau den Verdikten, die der Produktionscode als umge… | (1) Der konkret benannte Ausloeser 'Suite laeuft unter Coverage, Tracing verlangsamt die Mutanten-Worker' traegt nicht: pytest-cov 7.1.0 (uv.lock) enthaelt in engine.py/plugin.py/__init__.py weder COV_CORE noch COVERAGE… |
| BC-094 | medium | Der No-Progress-Deadline begrenzt nur wait(), nicht das nachfolgende recv() - der Parent… | Die Codeeigenschaft stimmt: Nur wait_connections bekommt das Zeitbudget (generation_supervisor.py:285-286), connection.recv() in Zeile 295 hat keins. |
| BC-095 | medium | BoundedOutputCapture.close() laesst bei einem ueberlebenden Writer Deskriptor und Drain-T… | Die behauptete Folge (Deskriptor und rechnender Drain-Thread bleiben dauerhaft zurück, ProcessMonitor nachfolgender Tasks wird verzerrt) setzt einen Schreiber voraus, der nach dem Baumabbau noch lebt, die geerbte Schrei… |
| BC-101 | medium | Absolute, projektinterne tests_dir-Eintraege verschieben die pytest-Konfigurationsgrenze… | src/mutmut_win/pytest_boundary.py: _mapped_test_start Z. 167-196 (Mapping-Zweig Z. 175-178, except/return None Z. 179-186, Staging-Eingrenzung Z. 187-191, Existenzpruefung Z. 192-196) -> _mapped_test_starts Z. 199-214 -… |
| BC-104 | medium | Generiertes sitecustomize.py enthaelt repr() einer Menge — hashseed-abhaengige Bytes in d… | Der Mechanismus ist real (runner.py:942/947, Seed-abhaengige repr-Reihenfolge per Einzeiler bestaetigt), die behauptete Folge (laufuebergreifende Drift/Fehlalarm eines Staging-Snapshot-Vergleichs bzw. eines wiederverwen… |
| BC-105 | medium | Skip-Mengen decken nur Verzeichnisse ab - volatile Werkzeug-DATEIEN wie .coverage.<host>.… | Die Folge (harter OrchestratorError bzw. 'failed' bei einer waehrend des Laufs erscheinenden, nicht ignorierten .coverage.<host>.<pid>.<rand> in der Projektwurzel) ist als Mechanismus real, aber keine Fehlwirkung, sonde… |
| BC-106 | medium | Projektbasis bindet st_mtime_ns/st_ctime_ns jeder Datei - bytegleiches Neuschreiben inval… | Der Mechanismus existiert (st_mtime_ns fliesst ueber den Projekt-Fanout in core_digest; eine reine mtime-Aenderung waehrend des Laufs fuehrt zu 'failed'), die behauptete Folge ist aber keine Fehlwirkung, sondern dokumen… |
| BC-107 | medium | Cross-Run-Basis bindet volatile Windows-Dateiattribute; das Hashen selbst kann sie veraen… | Die behauptete Folge 'Abbruch bzw. Herabstufung ohne erkennbaren Anlass' ist in beiden Zweigen am Code bzw. am dokumentierten Vertrag entkraeftet. |
| BC-120 | low | show schreibt die Nichttreffer-Prosa auf stdout und verletzt damit den eigenen Patch-Stre… | Der genannte Auslöser erreicht den else-Zweig nicht. |
| BC-127 | low | delete_results_not_in ruft als einzige Funktion kein create_db und meldet auf einer schem… | Der einzige Produktionsaufrufer von delete_results_not_in ist MutationOrchestrator._maybe_purge_stale (src/mutmut_win/orchestrator.py 1296), und alle drei Aufrufstellen von _maybe_purge_stale haben create_db(self._db_pa… |
| BC-132 | low | Dekorierte Klassen werden vollstaendig von der Mutation ausgenommen, obwohl die Begruendu… | Die Behauptung lautet: Die Klassensperre sei unbegründet und nur aus Funktionsgründen übernommen, ein Aufschneiden sei gefahrlos, und der Score beschreibe deshalb unbemerkt eine falsch verkleinerte Fläche. |
| BC-133 | low | Pragma no mutate wird stumm ignoriert, wenn direkt Satzzeichen folgen | (1) Die Grammatik ist bewusst auf ein whitespace-getrenntes Token 'mutate' festgelegt. mutation.py:1061 verlangt nach 'mutate' Zeilenende oder Whitespace, (?=$/\s). Der Autor hat also bewusst nicht die schwächere Wortgr… |
| BC-135 | low | BoundedOutputCapture.close() markiert sich auch nach abgelaufenem join als geschlossen; e… | Die behauptete Folge (Drain-Thread und Lese-fd bleiben dauerhaft zurueck, weil close() _closed unbedingt setzt) traegt am Code nicht: (1) _closed ist nicht kausal. |
| BC-136 | low | Default-Argumente schreiben Koordinationsdateien in den eigenen Hashsatz | Der behauptete Laufabbruch setzt einen Aufrufer voraus, der prepare_pytest_phase_guard ohne runtime_dir bzw. _write_pytest_argfile ohne output_dir aufruft. |
| BC-138 | low | Jede Mutation eines bereits lazy Quantifiers verwirft den ?-Marker; {n,m}? verliert die G… | (1) 'Jede Mutation verwirft den Marker': Das ist für #2 zwingend richtig (regex_mutation.py:138 'removal of the whole quantifier', Test 95-97). (2) '#6 einseitig / Greedy-Flip fehlt': #6 ist als greedy->lazy mit ausdrüc… |

Nicht prüfbar: BC-006, BC-016, BC-046, BC-049, BC-071, BC-075, BC-113, BC-114, BC-126 (Details in Abschnitt 7).

**Übersehenes und Mehrfachzählung.** 6 der neun high-Gruppen fehlen in meinem Bericht ganz (M-001, M-002, M-004, M-005, M-007, M-009). Die 111 tragenden Einträge meines Berichts entsprechen nur 88 Mechanismusgruppen, weil ich denselben Mechanismus mehrfach gemeldet habe.

## 5. Wesentliche Konflikte und ihre Auflösung

Erfasst sind 129 Konflikte: 49 Urteilskonflikte zu meinen Befunden, 38 zu Astras Befunden, 16 abweichende Paarbeziehungen, 12 Gruppeninkonsistenzen, 9 Widersprüche innerhalb meines Berichts und 5 Kreuzkonflikte verworfen gegen bestätigt. Jeder Konflikt nennt in der JSON-Datei beide Positionen, den entscheidenden Codepfad und die Auflösung.

**Gruppenadjudikationen.** Wo derselbe Mechanismus in verschiedenen Einträgen unterschiedlich beurteilt war, wurde er einmal für alle Mitglieder entschieden:

| Adjudikation | Ergebnis | Geänderte Urteile |
| --- | --- | --- |
| F-APPLY-RACE | Speichert und schliesst ein externer Schreiber (Editor-Autosave, Format-on-save, Sync-Client) im Fenster 577-617 eine Fassung S1, ersetzt apply S1 still durch Mutant(S0); S1 ist nicht im Backup (.mutmut-orig.bak enthaelt S0), und… | VIEW-02: teilweise/medium → bestätigt/high |
| F-DOPPELCLOSE | Konkreter Defekt (Grenzregel Abschnitt 1): Im vom Phasen-Guard instrumentierten pytest-Kind (worker.py:478, einziger Aufrufkontext mit fremden, fd-allozierenden Threads) kann ein Nutzer-Hintergrundthread die in Z. 204 freigegeben… | BC-060: widerlegt/keine → teilweise/low; RES-02: widerlegt/keine → teilweise/low |
| F-FRUEHER-EXECUTOR | Konkreter Defekt (ressourcenleck) nur, wo ein weiterlaufender Prozess das Handle belegbar über seinen Bedarf hinaus hält: im vom Projekt kommentierten direkten API-Lauf (orchestrator.py:184, 202, 222, 238). Dort bleibt bei einem… | RES-05: teilweise/low → widerlegt/keine |
| G-001 | Eine transient gesperrte, frisch geschriebene oder im Projektkern liegende Datei kann einen gueltigen Lauf mit der falschen Ursache 'inputs/staging files changed' abbrechen. | BC-049: teilweise/medium → nicht prüfbar/keine |
| G-002 | abbruch_gueltiger_lauf mit falsche_diagnose_fehlerkanal: jeder Folgelauf ohne --force bricht vor der Mutantenerzeugung mit einer fremden OSError (roher Traceback, cli.py Z. 739-744) ab, ohne den Typkonflikt zu nennen. | BC-077: teilweise/low → teilweise/medium |
| G-003 | Der Mirror enthaelt in einem Folgelauf ohne --force instrumentierte Generatorausgabe an Stellen, an denen der Vertrag oder die Konfiguration das unmutierte Original verlangt. | keine |
| G-004 | Nach Grenzregel ist kein konkreter Defekt belegt. | BC-135: nicht prüfbar/keine → widerlegt/keine |
| G-005 | Ein lesender Pfad (show, Browser-Diff-Fallback; bei Komponentenumleitung auch apply) löscht ohne Wurzel- oder Komponentenprüfung heilend. | CLI-07: teilweise/low → bestätigt/medium |
| G-006 | falsche_diagnose_fehlerkanal: Bei setup.cfg als wirksamer Quelle und ungueltigem [mutmut]-Wert enden run/show/apply mit rohem pydantic-Traceback und Exit 1 statt Meldung mit Exit 2 (README.md:190-194, cli.py:202-207, 507-509) und… | BC-017: teilweise/medium → teilweise/low |
| G-007 | Der Ebenenverlust ist nicht, wie Moduldocstring 18-21 verspricht, immer konservativ: (a) er erweitert still den gehashten/gestageten Baum (unnoetige Arbeit, low; im ValueError-Zweig ohne jedes Log, Kommentar 109-110 falsch), und… | keine |
| G-008 | Klammerloser CRCR-Ersatzknoten. Teilfall (a): geklammertes Integer-Literal mit Attributzugriff wird zu '0.bit_length()' o. ä. -> SyntaxError, das dateiweite Netz (file_setup.py 2228-2249) verwirft mit gedruckter Warnung alle Muta… | keine |
| G-009 | Bei vom Default abweichender Verbosity meldet der inkrementelle Cache-Vergleich faelschlich entfernte (bzw. neue) Tests und erzwingt ab dem zweiten Lauf bei jedem Aufruf eine vollstaendige Stats-Neuerhebung mit irrefuehrender Kon… | BC-045: teilweise/medium → teilweise/low |

**Verworfen gegen bestätigt (Astras sieben Zuordnungen).**

| Mein verworfener Befund | Astra-Befund | Astra: Recht hat | Abschließend | Endurteil Astra-Befund |
| --- | --- | --- | --- | --- |
| ORCH-06 | ORDER-02 | claude | claude | widerlegt/keine |
| STATS-02 | BASIS-01 | astra | astra | bestätigt/medium |
| EXEC-03 | SPAWN-01 | astra | astra | teilweise/medium |
| PROC-05 | ORCH-01 | astra | astra | teilweise/low |
| PROC-05 | CLI-04 | astra | claude | widerlegt/keine |
| PROC-05 | RES-05 | astra | claude | widerlegt/keine |
| PROC-05 | CONTRACT-05 | astra | astra | bestätigt/low |

**Widersprüche innerhalb meines Berichts.** Neunmal verwirft mein Bericht einen Mechanismus, den er an anderer Stelle bestätigt:

- claude#21:STATS-02 / BC-051 / BC-053 / BASIS-01: Derselbe Bericht bestaetigt BC-051/BC-053 (teilweise/medium) zur fehlenden ignore_boundary in den Core-Walks, Astra bestaetigt BASIS-01.
- claude#1:BASIS-03 / BC-001 / BC-029 / BC-031 / BC-028: Der verworfene Kandidat behauptet, der Ambient-Degradationspfad sei tot, sobald core_complete False ist, sodass ein transienter IO-Fehler zum harten Abbruch wird.
- claude#48:ORCH-01 / BC-134: Der Kandidat (_split_no_test_tasks: Docstring nennt nur 'Mapping existiert', Code verlangt zusaetzlich das nie gesetzte Autoritaetsbit) beruht auf derselben Tatsache wie der im selben Bericht bestaetigte BC-134 (Autoritaetsbit in src/ nie True: stats.py:111,…
- claude#7:PROC-04 / BC-100: Die Verwerfung haelt den Zustand 'proc ist kein _REAL_POPEN_TYPE, job_handle ist ein echtes Handle' fuer praktisch nicht herstellbar.
- claude#23:WRK-06 / BC-100: Gleicher Sachverhalt wie claude#7 (PROC-04). Dass das Handle beim Nicht-Popen-Objekt nicht freigegeben wird, ist am Code belegt (worker.py:1657-1662, 1202). Der Zustand ist ueber den bestaetigten BC-100-Pfad herstellbar, aber nur mit Test-Doubles.
- claude#39:EXEC-01 / BC-037 / BC-093 / RACE-02: Die normative Behauptung (synthetisches Dead-Worker-Verdikt muesste fatal sein) traegt nicht: fuer einen echten harten Worker-Tod ist das persistierte 'suspicious' mit exit 35 dokumentierte Semantik (get_events-Docstring, executor.py:36, 381-393). Soweit der…
- claude#45:CFG-01 / BC-069: CFG-01 erhebt dieselbe Behauptung wie der Ausgangsbefund BC-069 (Namen des eigenen Repos in WORKSPACE_EXCLUDED_DIR_NAMES treffen Fremdprojekte), wurde im claude-Bericht aber verworfen, waehrend BC-069 im selben Bericht als teilweise bestaetigt gefuehrt wird.
- claude#31:BROW-05 / BC-064 / VIEW-03: BROW-05 behauptet, der als 'meta files absent (DB-only fallback)' dokumentierte Zweig (browser.py:136-137) koenne nie einen Diff liefern.
- claude#4:ORCH-06 / BC-104 / ORDER-02: ORCH-06 ist inhaltlich identisch mit BC-104 (runner.py:942 repr(set(...))), das der claude-Bericht selbst als Befund fuehrt, und mit ORDER-02 im astra-Bericht; der claude-Bericht hat denselben Kandidaten also verworfen und gemeldet.

Aufgelöst wird stets über das Urteil zum bestätigten Befund; die abgeschnittenen Verwerfungsbegründungen wurden nicht ergänzt.

## 6. Gemeinsame Schnittmenge ohne Doppelzählung

30 Mechanismusgruppen tragen Befunde aus beiden Berichten (high 1, medium 17, low 12). Jede Gruppe zählt einmal, gleich wie viele Einträge sie hat; die Schwere ist die höchste tragende Endschwere der Gruppe.

| Gruppe | Schwere | Gemeinsamer Kern | Claude | Astra | In Astras Tabelle |
| --- | --- | --- | --- | --- | --- |
| M-008 | high | Proof-Publikation im generierten Guard-Plugin ist nicht fehlerbehandelt: transiente Publikationssto… | BC-003 | WORK-01 | ja |
| M-010 | medium | Gültige lange Dateinamen werden durch Siblingnamen unveröffentlichbar | BC-058 | ATOM-04, WIN-01 | nein |
| M-011 | medium | Republikation des unveraenderlichen Phase-Guard-Plugins in den eingefrorenen Staging-Baum bei jeder… | BC-010, BC-007, BC-004 | STAGE-01 | ja |
| M-015 | medium | Unlesbare untergeordnete Ignore-Datei verliert einschließende Ausnahmen | BC-079 | REST-05 | nein |
| M-018 | medium | Coverage mit relative_files wird als ungemessen abgewiesen | BC-067 | REST-02 | nein |
| M-020 | medium | --force-Cleanup ignoriert Readonly-Attribute und scheitert dauerhaft mit falscher Diagnose | BC-013 | WIN-02 | ja |
| M-021 | medium | --since-commit vergleicht repo-root-relative git-Pfade gegen das CWD und endet still mit Exit 0 | BC-015 | CLI-02 | ja |
| M-030 | medium | Typwechsel Datei<->Verzeichnis an einem konfigurierten Staging-Ziel wird nie versoehnt und bricht d… | BC-077 | FILE-04 | ja |
| M-036 | medium | Datenbank-Lock-Domaene haengt an tempfile.gettempdir() und ist damit nicht global | BC-039 | LOCK-01 | ja |
| M-038 | medium | Klassen-Stack laeuft aus dem Tritt: qualifizierte do_not_mutate_patterns greifen falsch oder gar ni… | BC-024 | MUT-04, CONTRACT-01 | ja |
| M-039 | medium | Mutiertes Modul scheitert mit NameError beim Import, wenn eine Methode im eigenen Klassenkoerper au… | BC-025 | MUT-01 | ja |
| M-045 | medium | Integer-Literal mit >4300 Dezimalstellen bricht den gesamten Lauf ab (int->str-Limit) | BC-026 | EDGE-03 | ja |
| M-046 | medium | CRCR verliert erforderliche Klammern und verändert falschen Ausdruck | BC-027, BC-086 | OP-01 | ja |
| M-050 | medium | chr()-Grenzwerte in der Zeichenklassen-Mutation ungeschuetzt | BC-139 | OP-07, EDGE-02, CONTRACT-06 | ja |
| M-054 | medium | Liveness-Sweep erklaert sauber beendete Worker fuer abgestuerzt und ersetzt ein korrektes Mutantenv… | BC-037, BC-093 | RACE-02, SPAWN-01 | ja |
| M-056 | medium | Mutantenauswahl ist unter Windows case-insensitiv - apply kann den falschen Mutanten schreiben | BC-112, BC-141, BC-084 | REST-01 | ja |
| M-060 | medium | _editable_source_path dekodiert die PEP-610-URL doppelt und liefert fuer Pfade mit literalem Prozen… | BC-108 | STATS-01, WIN-05 | ja |
| M-061 | medium | Core-Fingerprinting führt gitignorierte Laufartefakte über Import- und Editable-Bäume wieder ein | BC-051, BC-053 | BASIS-01 | ja |
| M-066 | low | Doppeltes os.close(fd) auf dem Erschoepfungspfad von _open_random_sibling kann einen fremden Deskri… | BC-060, BC-059 | ATOM-01, RES-02 | ja |
| M-067 | low | Fehlerdiagnostik folgt vorbereiteten Links auf andere Dateien | BC-057 | ATOM-02 | ja |
| M-077 | low | Wertfehler in setup.cfg [mutmut] umgehen die ConfigError-Vertragsschicht und erscheinen als roher p… | BC-017 | DATA-01, CONTRACT-02 | ja |
| M-084 | low | str.casefold() als NTFS-Identitaetsschluessel erzeugt falsche Staging-Kollisionen | BC-072 | WIN-03 | ja |
| M-090 | low | Priming-Schreibzugriff in _open_guard kollidiert mit dem mandatorischen Byte-Range-Lock eines Konku… | BC-096 | LOCK-04 | ja |
| M-099 | low | operator_regex prueft nicht, ob args[0] positional ist — Keyword-Argumente werden als Regex mutiert… | BC-087 | OP-06 | ja |
| M-104 | low | SpawnPoolExecutor belegt Job-Object-Handle und drei Multiprocessing-Queues in __init__, ohne dass e… | BC-090 | ORCH-01, CONTRACT-05 | ja |
| M-115 | low | DB-only-Diff-Fallback nimmt den ersten rglob-Treffer und kann den Mutanten der falschen Datei rende… | BC-064 | VIEW-03 | ja |
| M-117 | low | Fehlerpfad des Diff-Ladethreads prüft _loading_id nicht — veralteter Fehler überschreibt den Diff d… | BC-117 | VIEW-04, RACE-03 | ja |
| M-124 | low | collect_tests liefert still eine leere Testliste, sobald die effektive Test-Case-Verbosity nicht ex… | BC-045 | RUNNER-01 | ja |
| M-127 | low | `run_type_checker`: dokumentierte Fehler-Taxonomie deckt strukturell abweichende, aber gueltige JSO… | BC-142, BC-143 | CONTRACT-03 | ja |
| M-144 | low | _popen_contained uebergibt den synthetischen PID eines Popen-Test-Doubles an OpenProcess/AssignProc… | BC-100 | PROC-02 | nein |

## 7. Ungeklärt und gezielte spätere Prüfungen

Elf Befunde bleiben nicht prüfbar. Ihre Entscheidung hängt an Laufzeit- oder Umgebungsverhalten, das statisch nicht zu klären ist:

| Befund | Ort | Fehlende Evidenz |
| --- | --- | --- |
| BC-006 | `src/mutmut_win/atomic_file.py:53` | Nachweis, dass ein regulär schreibbares Workspace-Verzeichnis oder -Blatt unter Windows 10/11 + CPython 3.14.7 (z. B. durch einen realen Filtertreiber) bei os.lstat/os.stat auf (0,0) zurückfällt, während Path.resolve(strict=True) im selben Fenster gelingt; bz… |
| BC-016 | `src/mutmut_win/config.py:438` | Es fehlt jeder Beleg (Projektdokumentation, Code, Test oder erlaubter Einzeiler), dass ein vertragskonformes lokales Windows-Dateisystem dieselbe Menge von test*.py-Namen zwischen zwei Läufen in unterschiedlicher Reihenfolge aufzählt, ohne dass sich zugleich… |
| BC-046 | `src/mutmut_win/stats.py:448` | Es fehlt ein Nachweis, dass os.fstat unter Windows (Filtertreiber, CPython 3.14.7) im Elternprozess für eine bereits publizierte Datei in mutants/ transient eine falsche st_nlink meldet. |
| BC-049 | `src/mutmut_win/stats.py:680` | Statisch nicht feststellbar sind drei Dinge: wie haeufig die dokumentierten Stoerungen gerade im lesenden Staging-Walk des Elternprozesses an etablierten mutants/-Dateien auftreten; ob die Fehlwerte fstat gegen fstat (statt fstat gegen Pfadsicht) betreffen; u… |
| BC-071 | `src/mutmut_win/db.py:554` | Es fehlt die Laufzeitevidenz, ob unter Windows mit CPython 3.14.7 ein ungesperrtes Lesekommando seine SHARED-Sperre auf der Datei-DB länger als 5 s ohne Unterbrechung hält und dadurch das COMMIT des Laufs über die Busy-Frist hinaus auf EXCLUSIVE warten muss. |
| BC-075 | `src/mutmut_win/file_setup.py:1071` | Beleg, dass unter Windows 10/11 + Defender/Search Indexer ein CreateFile-Lesezugriff auf eine bestehende Projektquelldatei (bzw. lstat/chmod eines schreibgeschützten Staging-Leafs) real länger als ~1,5 s mit Sharing-Violation/Access-Denied abgewiesen wird, st… |
| BC-113 | `src/mutmut_win/type_checking.py:27` | Es fehlt eine Laufzeitmessung oder ein Projektbeleg, dass ein vertragskonformer mypy-/pyright-Lauf ueber den Staging-Baum mutants/ unter Windows und CPython 3.14.7 die 300 s ueberschreitet. |
| BC-114 | `tests/integration/test_generation_supervisor.py:253` | Es fehlt ein Beleg, dass eine konkrete, im Projekt dokumentierte Bedingung die 5,0-s-Grenze tatsaechlich erreicht (Grenzregel Abschnitt 2, letzter Absatz): keine Messung, kein dokumentierter Laufzeitfaktor, kein belegter roter Lauf dieses Tests. |
| BC-126 | `src/mutmut_win/db.py:626` | Nicht belegt und statisch nicht entscheidbar: ob unter Windows 10/11 bzw. Server 2016+ auf NTFS eine Quelldatei mit unpaarigem UTF-16-Surrogat im Namen existieren kann, von os.walk als solcher geliefert wird und Staging (atomic writes unter mutants/), libcst-… |
| ORDER-03 | `src/mutmut_win/config.py:438` | Ein Beleg, dass Windows auf einem vom Vertrag gedeckten lokalen Volume (README.md:22-28: lokales, identitaetsfaehiges Dateisystem; exFAT/SMB 'may be rejected') dieselbe Namensmenge in einem unveraenderten Verzeichnis zwischen zwei Laeufen in anderer Reihenfol… |
| TIME-02 | `src/mutmut_win/process/output_capture.py:89` | Nicht belegt ist, dass ein lauffähiger Python-Daemon-Thread unter Windows mit CPython 3.14.7 nach einem Event-Weckruf mehr als 1 s lang nicht eingeplant wird, während der Hauptthread in join ohne GIL wartet. |

Gezielte spätere Prüfungen:

- **Reproduktion der P1-Gruppen:** je Gruppe ein gezielter Integrationstest unter Windows (apply mit parallelem Schreiber; Proof-Publikationsfehler per Fault-Injection; veralteter Mirror ohne --force; ZIP-Importpfad und git-ignorierte .venv im Reuse-Vergleich; PPID-Wiederverwendung).
- **Offene Fragen (nicht_pruefbar):** je Eintrag die in offene_fragen genannte fehlende Evidenz erheben (meist Laufzeit-/Treiberverhalten unter Windows oder reale Checker-/Git-Ausgaben).
- **Schwere der Wettlauf-/Transientgruppen:** Auftretensrate transienter Windows-Dateifehler (Filtertreiber, AV) im Staging messen, bevor M-011/M-012/M-062 höher oder niedriger eingestuft werden.
- **Vollständige Verwerfungsbegründungen:** falls ungekürzte Fassungen existieren, die 50 Verwerfungen erneut gegen die Kreuzkonflikte prüfen (SK-04).

Offen bleiben außerdem drei Verfahrensfragen: die exakte Zahl der Einträge mit zwei niedrigeren Skeptikerempfehlungen (55 nach Astra, heuristisch mindestens 35), die Seed-Ziehung der Stichprobe und die Modellangabe im `source`-Feld meines Berichts (Opus 5 gegenüber der Bezeichnung als Fable-5.1-Bericht).

**Lücken ohne Ortsentsprechung.** Von meinen 76 Befunden ohne Astra-Kandidat haben 18 einen semantischen Partner außerhalb des Ortsjoins, 41 sind echte inhaltliche Lücken Astras, 16 sind widerlegt oder nicht prüfbar. Von Astras 43 haben 15 einen Partner in meinem Bericht, 27 sind echte Lücken meines Berichts. Astras Klassifikation `geprueft_uebersehen` trifft in 13 Fällen nicht zu, weil ein Partner existiert. Die fünf freigegebenen `bereits_unabhaengig_gefunden` (BC-004, BC-010, BC-045, BC-053, BC-077) haben alle einen Partner (STAGE-01, RUNNER-01, BASIS-01, FILE-04). Über innere Finderentscheidungen sagen die Artefakte nichts.

## 8. Abschließende Priorisierung

**Auslieferung.** Nicht auslieferungsreif ohne Behebung der 9 high-Gruppen (P1). Sie betreffen still unvollständige oder falsche Ergebnisse, die als korrekt gelten, stille Wiederverwendung auf unvollständiger Basis, Datenverlust bei apply und Fremdwirkung auf Prozesse. Die 56 medium-Gruppen (P2) umfassen Abbrüche gültiger Läufe mit falscher Diagnose, fehlerhafte oder fehlende Mutanten, still falsch gelesene Konfiguration und falsch abgegrenzten Mutations- oder Hashumfang; sie gehören in die nächste Iteration. Die 81 low-Gruppen (P3) sind überwiegend Diagnose-, Komfort- und Effizienzmängel.

**Die drei wichtigsten Risiken:**

1. **Falsche oder unvollständige Ergebnisse, die als korrekt gelten** (M-008, M-002, M-003, M-001). M-008: eine gestörte Proof-Publikation im Phase-Guard endet als Exit 3 und wird als 'killed' gespeichert, der Score steigt (BC-003, WORK-01, beide Berichte). M-002: ein veralteter Mirror enthält instrumentierte Generatorausgabe, die Coverage-Auswahl misst falsche Zeilen (FILE-01/FILE-03). M-003: eine nicht parsebare oder nicht kompilierbare Datei verliert still alle Mutanten, der Score bezieht sich auf eine unvollständige Menge (BC-078). M-001: getrackte, aber per .gitignore ausgeschlossene Quellen fallen still aus der Mutation (REST-04).
2. **Stille Wiederverwendung auf unvollständiger Basis** (M-006, M-007). Die Reuse-Basis bindet ZIP-Importpfade (STATS-03) und git-ignorierte site-packages projektinterner venvs (BC-052) nicht; Ergebnisse können nach Abhängigkeitsänderungen ohne Neuberechnung als gültig übernommen werden.
3. **Datenverlust und Fremdwirkung** (M-005, M-009, M-026). M-005: speichert ein Editor oder Sync-Client im Fenster zwischen Prüfung und Ersetzung, überschreibt apply die neue Fassung still; sie steht nicht im Backup und die CLI meldet Erfolg (RACE-04, CONTRACT-04, VIEW-02). M-009: der PPID-basierte Baum-Sweep kann einen fremden Prozess mit wiederverwendeter PPID beenden (RACE-01). M-026: ein lesender Pfad kann über eine Junction eine fremde .meta-Datei löschen (CLI-07, VIEW-01).

**P1 – vor der Auslieferung beheben (high):**

| Gruppe | Defekt | Einträge | Berichte |
| --- | --- | --- | --- |
| M-001 | GitignoreBoundary wertet ausschliesslich Ignore-Muster aus und fragt den Git-Index nie ab; eine getrackte (vor der Regel eingecheckte oder per git add -f aufgenommene) Datei unter einem nicht selbst ausgeschlossenen konfigurierten Verzeichnis faellt still aus… | REST-04 | astra |
| M-002 | Der Mirror enthaelt in einem Folgelauf ohne --force instrumentierte Generatorausgabe an Stellen, an denen der Vertrag oder die Konfiguration das unmutierte Original verlangt. | FILE-01, FILE-03 | astra |
| M-003 | create_mutants_for_file degradiert bei nicht parsebarer Quelle (2213-2226, auch fuer Engine-Validierungsfehler) und bei nicht kompilierbarem generiertem Modul (2228-2249) die ganze Datei auf mutant_names=[] mit blosser Warnung; die Unvollstaendigkeit der Muta… | BC-078 | claude |
| M-004 | ProcessMonitor summiert je Probe absolute I/O-Zaehler nur von Wurzel und aktuell lebenden Nachfahren (loop_monitor.py:486-495); classify_samples nutzt max(0, letzte - erste) als einziges I/O-Veto, so dass ein im Fenster endendes I/O-aktives Kind das Veto aufh… | SPAWN-02 | astra |
| M-005 | Speichert und schliesst ein externer Schreiber (Editor-Autosave, Format-on-save, Sync-Client) im Fenster 577-617 eine Fassung S1, ersetzt apply S1 still durch Mutant(S0); S1 ist nicht im Backup (.mutmut-orig.bak enthaelt S0), und die CLI meldet 'Applied mutan… | RACE-04, CONTRACT-04, VIEW-02 | astra |
| M-006 | _hash_effective_import_paths uebergibt fuer projektinterne Import-Roots eine abgeleitete GitignoreBoundary; ist das projektinterne .venv git-ignoriert, ist site-packages subtree_excluded und unbeanspruchte Module/.pth werden ohne reuse_safe=False ausgeblendet… | BC-052 | claude |
| M-007 | _hash_effective_import_paths behandelt ZIP-Unterpfade auf sys.path (lstat -> FileNotFoundError) als 'missing-import-root' ohne reuse_safe=False; die Archivbytes bleiben ungebunden, die Basis gilt als vollstaendig. | STATS-03 | astra |
| M-008 | Der generierte Phase-Guard-Hook pytest_runtest_logreport ruft atomic_write_bytes ohne try/except auf. | BC-003, WORK-01 | astra + claude |
| M-009 | _iter_descendants verknuepft Prozesse ausschliesslich ueber die numerische PPID, ohne create_time- oder Jobpruefung (worker.py:1621-1636). _kill_proc_tree fuehrt den Sweep auch nach dem Job-Close aus (1684-1690). Eine fremde Waise mit veralteter PPID wird get… | RACE-01 | astra |

**P2 – nächste Iteration (medium, 56 Gruppen):**

| Gruppe | Titel | Einträge |
| --- | --- | --- |
| M-010 | Gültige lange Dateinamen werden durch Siblingnamen unveröffentlichbar | ATOM-04, WIN-01, BC-058 |
| M-011 | Republikation des unveraenderlichen Phase-Guard-Plugins in den eingefrorenen Staging-Baum bei jeder einzelnen Task | BC-010, STAGE-01, BC-007, BC-004 |
| M-012 | ensure_atomic_bytes-Vorprüfung ohne Retry bricht den gesamten Lauf bei transientem Windows-Filterdriver-Fehler ab | BC-009, BC-008 |
| M-013 | create_exclusive_random_bytes prueft die als unzuverlaessig dokumentierte handle-abgeleitete st_nlink - ohne Retry | BC-011 |
| M-014 | .gitignore mit UTF-8-BOM verliert ihr erstes Muster | BC-023, BC-080 |
| M-015 | Unlesbare untergeordnete Ignore-Datei verliert einschließende Ausnahmen | REST-05, BC-079 |
| M-016 | gitignore-Matching ist case-sensitiv, Git unter Windows nicht - ignorierte Baeume landen im Basis-Hash | BC-081 |
| M-017 | GitignoreBoundary._excludes verliert Gits Verzeichnismarker-Praezedenz — ignorierte Teilbaeume werden gelaufen, gestage… | BC-082 |
| M-018 | Coverage mit relative_files wird als ungemessen abgewiesen | REST-02, BC-067 |
| M-019 | Coverage-Parallelkonfiguration lässt vorhandene Messdaten übersehen | REST-03 |
| M-020 | --force-Cleanup ignoriert Readonly-Attribute und scheitert dauerhaft mit falscher Diagnose | BC-013, WIN-02 |
| M-021 | --since-commit vergleicht repo-root-relative git-Pfade gegen das CWD und endet still mit Exit 0 | BC-015, CLI-02 |
| M-022 | --since-commit behandelt Eingaben als Git-Optionen oder Pfadspezifikationen | CLI-01 |
| M-023 | --since-commit macht Testdateien ausserhalb der konfigurierten tests_dir-Unterbaeume zu Mutationszielen | BC-066 |
| M-024 | Absolute Testpfade und '..'-Aliase umgehen den inkrementellen Testausschluss | CLI-03 |
| M-025 | --treat-timeout-as-kill verändert Gate, aber nicht ausgegebenen Run-Score | CLI-06 |
| M-026 | show kann über umgeleitete mutants-Wurzel externe Metadaten löschen | CLI-07, VIEW-01 |
| M-027 | Lesefehler vorhandener setup.cfg werden zu Standardkonfiguration | FAIL-01 |
| M-028 | Vorhandener TOML-Abschnitt mit falschem Typ wird still ignoriert | FAIL-02 |
| M-029 | Einzeilige setup.cfg-Regexe werden an Quantifizierer-Kommas zerlegt | DATA-02 |
| M-030 | Typwechsel Datei<->Verzeichnis an einem konfigurierten Staging-Ziel wird nie versoehnt und bricht den Lauf mit FileExis… | FILE-04, BC-077 |
| M-031 | _sync_tree loescht bei jedem Lauf alle *.meta-Sidecars unterhalb konfigurierter Spiegel | BC-022 |
| M-032 | Automatischer Spiegel prueft .gitignore mit descend(), die Mutationssuche mit descend_forced() — git-ignorierte Mutatio… | BC-021 |
| M-033 | _same_live_input verwechselt 'nicht ermittelbar' mit 'verschieden' und macht aus einer geloeschten Datei einen Laufabbr… | BC-073 |
| M-034 | Relative ..-Pfade umgehen Metadatenreservierung und erzeugen falsche Mutantnamen | FILE-02 |
| M-035 | Pyproject-Bereinigung löscht Tabellenmuster innerhalb gültiger TOML-Strings | FILE-06 |
| M-036 | Datenbank-Lock-Domaene haengt an tempfile.gettempdir() und ist damit nicht global | BC-039, LOCK-01 |
| M-037 | _raise_database_error stuft Umgebungsfehler (readonly, I/O-Fehler, Platte voll, cantopen) als Cache-Korruption ein und… | BC-018 |
| M-038 | Klassen-Stack laeuft aus dem Tritt: qualifizierte do_not_mutate_patterns greifen falsch oder gar nicht | BC-024, MUT-04, CONTRACT-01 |
| M-039 | Mutiertes Modul scheitert mit NameError beim Import, wenn eine Methode im eigenen Klassenkoerper aufgerufen wird | BC-025, MUT-01 |
| M-040 | Private Keyword-only-Parameter werden mit falschem Schlüssel weitergereicht | MUT-02, EDGE-01 |
| M-041 | NFKC-äquivalente Funktionsnamen kollidieren trotz unterschiedlicher Mutanten-IDs | MUT-06 |
| M-042 | len/isinstance werden nur nach Namen erkannt und loeschen den kompletten Argument-Teilbaum | BC-085 |
| M-043 | Block-Pragmas enden vorzeitig an Kommentaren und Mehrzeilenstring-Inhalten | MUT-05 |
| M-044 | Generator-Lambdas verändern fälschlich Identität umgebender Funktion | MUT-03 |
| M-045 | Integer-Literal mit >4300 Dezimalstellen bricht den gesamten Lauf ab (int->str-Limit) | BC-026, EDGE-03 |
| M-046 | CRCR verliert erforderliche Klammern und verändert falschen Ausdruck | OP-01, BC-027, BC-086 |
| M-047 | _safe_unwrap behandelt nackte Dezimal-Integer als überall sichere Atome | OP-02 |
| M-048 | Unary-Mutation erzeugt ungültige positive Vorzeichen in Match-Literalen | OP-03 |
| M-049 | String-Case-Mutationen verändern Hex-Escape-Schreibweise ohne Laufzeitänderung | OP-04 |
| M-050 | chr()-Grenzwerte in der Zeichenklassen-Mutation ungeschuetzt | BC-139, OP-07, EDGE-02, CONTRACT-06 |
| M-051 | re.VERBOSE ist der Regex-Engine unbekannt: Kommentartext wird mutiert (garantierte Aequivalente) und eine Klammer im Ko… | BC-043 |
| M-052 | Regex-Kommentare erzeugen wirkungslose Operator-Mutanten | OP-09 |
| M-053 | Forced-Fail-Gate prueft nur den globalen fail-Sentinel, nicht die namensbasierte Mutantenauswahl | BC-089 |
| M-054 | Liveness-Sweep erklaert sauber beendete Worker fuer abgestuerzt und ersetzt ein korrektes Mutantenverdikt durch exit 35 | BC-037, RACE-02, BC-093, SPAWN-01 |
| M-055 | Akzeptierte Workerzahlen über 61 verhindern unter Windows die Generierung | EDGE-04 |
| M-056 | Mutantenauswahl ist unter Windows case-insensitiv - apply kann den falschen Mutanten schreiben | BC-112, REST-01, BC-141, BC-084 |
| M-057 | TUI-Browser startet einen kompletten Mutationslauf als uneingehegten Kindprozess ohne Job Object | BC-012 |
| M-058 | action_retest_module testet bei Mutanten aus einer Paket-__init__.py den gesamten Paketbaum nach | BC-065 |
| M-059 | mypy-Report-Parser scheitert an mypys Summary-Zeile — Typpruefer-Filter bricht jeden Lauf ab | BC-054 |
| M-060 | _editable_source_path dekodiert die PEP-610-URL doppelt und liefert fuer Pfade mit literalem Prozentzeichen den falsche… | STATS-01, WIN-05, BC-108 |
| M-061 | Core-Fingerprinting führt gitignorierte Laufartefakte über Import- und Editable-Bäume wieder ein | BASIS-01, BC-051, BC-053 |
| M-062 | Doppelter Basis-Snapshot macht einen einseitigen transienten Lesefehler zum harten Laufabbruch | BC-005, BC-047, BC-001, BC-029, BC-031, BC-028, BC-088 |
| M-063 | Type-Checker laeuft mit cwd=mutants/ ohne Cache-Umleitung und zerstoert damit die eigene Staging-Evidenz | BC-048, BC-033, BC-034 |
| M-064 | Distributionsbasis hasht jede Datei jeder Distribution ohne Groessen- oder Relevanzgrenze, und der Orchestrator fuehrt… | BC-109 |
| M-065 | Nur Containment- und Boundary-Fehler gelten als fatal; jede andere Umgebungsstoerung im Worker wird zum persistierten M… | BC-099 |

**P3 – nachrangig (low, 81 Gruppen):** vollständig in `gesamturteil.priorisierung.P3_nachrangig` der JSON-Datei.

