# BUG_COLLECTION.md

Befundlage mutmut-win, Stand `v2.21.4`.

## Was dieses Dokument ist

Eine vollständige, benannte Befundsammlung. Es ersetzt die stillschweigende
Annahme „ist wohl in Ordnung" durch eine Liste, an der man arbeiten kann.

Es ist **keine** Freigabeerklärung. Die Zusage „enthält keinerlei Bugs mehr" ist
für eine Codebasis dieser Größe nicht einlösbar, und niemand sollte sie geben.
Einlösbar ist etwas anderes, und das ist das Ziel dieses Dokuments:

- eine **dokumentierte Befundlage** statt stillschweigender Annahmen,
- eine **gemessene Fehlerrate** statt „grün beim letzten Versuch",
- **reproduzierbare** Gates, bei denen ein roter Lauf einen echten Defekt bedeutet.

Solange der dritte Punkt offen ist, beweist kein grüner Lauf etwas. Deshalb steht
er in der Priorisierung vor allem anderen.

## Bezugsstand

| | |
|---|---|
| Version | `v2.21.4` |
| Tag | `83915fb42658ec7d5c840afaaf76503b259230a6` |
| Commit | `4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b` |
| Tree | `aa9bdf1135cf622e67da42f740b50713d1a44b94` |
| Plattform | Windows, CPython 3.14.7 |
| Erhebungsdatum | 2026-09-18 |

Gates auf genau diesem Commit: Suite 2603 passed / 43 skipped / 0 failed;
Semgrep-Releasegate `pass` mit 0 unerwarteten Findings; nativer Release-Gate OK;
pip-audit ohne bekannte Vulnerabilities; ruff, ruff format, mypy strict und
import-linter sauber.

**Alle Befunde in diesem Dokument sind gegen diesen grünen Stand erhoben.** Das
ist der Punkt: die Gates sind grün, und die Liste ist trotzdem lang. Ein grüner
Gate-Lauf ist eine notwendige, keine hinreichende Bedingung.

## Methode

Drei Quellen, unterschiedlich belastbar — die Unterscheidung steht bei jedem
Befund dabei:

**(1) Adversariales Multi-Agenten-Review.** 412 Agenten über die gesamte
Codebasis, in drei Spuren: Nichtdeterminismus als priorisierte Frage,
15 Modulcluster, 6 Querschnittslinsen. Jeder Befund wurde von einem zweiten,
unabhängigen Agenten gegengeprüft, dessen Auftrag das *Widerlegen* war.
Ergebnis: **193 Kandidaten, davon 143 bestätigt und 50 widerlegt** — eine
Widerlegungsquote von 26 %, die zeigt, dass die Gegenprüfung real gefiltert hat.
Zwei Agenten sind an Parse-Fehlern gescheitert (`GEN-01`, `CLI-05`); ihre
Bereiche sind nicht abgedeckt.

**(2) Eigene Nachprüfung am Quelltext.** Die in Kapitel A und B ausführlich
behandelten Befunde habe ich selbst gegen `src/` gelesen und verifiziert. Sie
sind mit **[quellgeprüft]** markiert.

**(3) Beobachtungen aus dem Releaselauf selbst** — Kapitel I. Diese sind am
härtesten, weil sie am laufenden System auftraten.

### Konfidenzstufen

| Stufe | Bedeutung |
|---|---|
| **[quellgeprüft]** | Ich habe den Mechanismus selbst im Quelltext nachgelesen und bestätigt. |
| **[beobachtet]** | Trat während dieser Sitzung real auf. |
| **[gegengeprüft]** | Von zwei unabhängigen Agenten bestätigt, nicht am laufenden System reproduziert. |

Kein Befund in diesem Dokument ist durch einen fehlschlagenden Test belegt. Das
ist die größte Lücke der Erhebung, und Kapitel K benennt sie.

### Verteilung

| Schwere | Anzahl |
|---|---|
| kritisch | 5 |
| hoch | 51 |
| mittel | 58 |
| niedrig | 29 |
| **gesamt** | **143** |

| Kategorie | Anzahl |
|---|---|
| correctness | 50 |
| api-contract | 19 |
| error-handling | 17 |
| toctou | 15 |
| windows | 12 |
| race | 10 |
| performance | 7 |
| resource-leak | 6 |
| test-flakiness | 3 |
| nondeterminism | 3 |
| phase-order | 1 |

Die Befunde häufen sich dort, wo die Maschinerie am dichtesten ist:
`stats.py` (17), `atomic_file.py` (12), `orchestrator.py` (11),
`file_setup.py` (11), `process/worker.py` (9), `process/executor.py` (8),
`cli.py` (8).

---

## Priorisierung

Zwei Klassen stehen vor allem anderen, aus verschiedenen Gründen.

**Klasse 1 — das Werkzeug meldet falsche Zahlen (Kapitel A).**
Das höchste Produktrisiko. Ein Mutation-Testing-Werkzeug, das einen
überlebenden Mutanten als `killed` meldet, behauptet eine Testqualität, die
nicht existiert. Der Anwender merkt nichts. Er trifft Entscheidungen auf einer
Zahl, die zu gut ist. Für ein Werkzeug, dessen einziger Zweck die Messung von
Testgüte ist, ist das der schwerstmögliche Fehler — schwerer als jeder Absturz,
weil ein Absturz sichtbar ist.

**Klasse 2 — Nichtdeterminismus (Kapitel B).**
Das höchste Prozessrisiko. Solange ein roter Lauf sowohl „echter Defekt" als
auch „Virenscanner hatte kurz ein Handle" bedeuten kann, lässt sich kein
einziger Fix aus diesem Dokument verifizieren. Deshalb kommt Kapitel B in der
*Bearbeitung* zuerst: es ist die Voraussetzung dafür, dass die Arbeit an allen
anderen Kapiteln überhaupt beweisbar wird.

Danach: Windows-Semantik (C), Prozesshygiene (D), Skalierung (E), dann der Rest.

---

## Kapitel A — Score-Integrität: das Werkzeug kann falsche Zahlen melden

Diese Befunde teilen eine Eigenschaft: **sie sind still.** Der Lauf endet
erfolgreich, eine Zahl wird gedruckt, und die Zahl ist falsch.

### A1 — Transienter Publikationsfehler wird zu einem falschen `killed`

`src/mutmut_win/process/worker.py:478` · BC-003 · kritisch · **[quellgeprüft]**

Im generierten Guard-Plugin ruft der Hook `pytest_runtest_logreport()` die
Funktion `atomic_write_bytes(...)` ohne `try`/`except` auf. Diese kann Fehler
werfen, die *nicht* wiederholt werden: `AtomicPublicationRaceError` und
`UnsafeAtomicWriteError`. Nur `AtomicReplaceError` wird retryt.

Ablauf: Mutant M überlebt, alle zugeordneten Tests sind grün, pytest würde
Exit 0 liefern. Beim ersten `call`-Report trifft die Sentinel-Publikation ein
Filtertreiber-Fenster. Die Exception entkommt dem Hook, pytest bricht mit
`INTERNALERROR` ab, Exit 3. Der Worker wertet Exit 3 als **`killed`**.

Ein überlebender Mutant wird als getötet gezählt. Der Score steigt. Niemand
erfährt davon. Das Modul dokumentiert die Störrate selbst mit „roughly 1 failure
per 5000 publications" — bei einem Lauf über einige tausend Mutanten ist das
kein theoretischer Fall.

Die Richtung ist zusätzlich falsch: fehlender Proof ist der *beabsichtigte*
fail-closed-Zustand (Exit 0 → 35 `suspicious`). Ein `INTERNALERROR` dreht den
fail-closed-Pfad in einen fail-open-Pfad um.

**Fix:** Publikation im Hook vollständig kapseln; bei Fehler `_proof_published`
nicht setzen und still zurückkehren. Der fehlende Proof erledigt den Rest.

### A2 — Korrektes Verdikt wird durch ein fabriziertes ersetzt

`src/mutmut_win/process/executor.py:366` · BC-037 · hoch · [gegengeprüft]

Der Liveness-Sweep erklärt sauber beendete Worker für abgestürzt. Zwischen
`queue.Empty` und `worker.is_alive()` liegt ein TOCTOU-Fenster: ein echtes,
kurz danach eintreffendes Verdikt wird zugunsten des fabrizierten Exit 35
verworfen (BC-093, `process/executor.py:326`).

### A3 — Mutanten verschwinden still aus dem Nenner

`src/mutmut_win/file_setup.py:2232` · mittel · [gegengeprüft]

Ein nicht kompilierbarer oder nicht parsebarer Mutantensatz fällt aus dem
Nenner heraus, **ohne dass dem Lauf die Autorität entzogen wird**. Der Score
wird über eine kleinere Grundmenge berechnet und als vollwertig ausgewiesen.

Verwandt, gleiche Wirkung: `node_mutation.py:69` (`NM-01`, hoch) — der
CRCR-Operator verliert die Klammern des Originalliterals und erzeugt einen
Mutanten mit `SyntaxError`; **die gesamte Datei fällt aus der Mutation**.

### A4 — Der Lauf bricht an einem Zahlenliteral ab

`src/mutmut_win/node_mutation.py:46` · hoch · [gegengeprüft]

Ein Integer-Literal mit mehr als 4300 Dezimalstellen bricht den kompletten Lauf
ab (CPython-`int`→`str`-Limit). Kein Teilergebnis, kein Skip der Datei.

### A5 — `re.VERBOSE` ist der Regex-Mutation unbekannt

`src/mutmut_win/regex_mutation.py:396` · hoch · [gegengeprüft]

Kommentartext in `re.VERBOSE`-Patterns wird mutiert. Das erzeugt garantierte
Äquivalente — Mutanten, die per Konstruktion niemals getötet werden können und
den Survivor-Zähler dauerhaft aufblähen. Eine Klammer im Kommentar löscht
umgekehrt die gesamte Mutationsfläche des Patterns.

Daneben (`RX-01`, hoch, `regex_mutation.py:66`): eine feste Erzeugungsreihenfolge
mit 12er-Cap lässt Anker-, Klassen- und Gruppen-Mutatoren bei typischen Patterns
verhungern — ganze Mutatorklassen kommen nie zum Zug, ohne dass das irgendwo
sichtbar wird.

### A6 — Ausschlussmuster greifen falsch

`src/mutmut_win/mutation.py:304` · hoch · [gegengeprüft]

Der Klassennamen-Stack läuft aus dem Tritt; qualifizierte
`do_not_mutate_patterns` greifen falsch oder gar nicht. Konsequenz in beide
Richtungen: entweder wird mutiert, was der Anwender ausgeschlossen hat, oder es
wird ausgeschlossen, was er mutiert haben wollte.

Ebenfalls Mutationsfläche: `mutation.py:449` (`MUT-06`, niedrig) nimmt
**dekorierte Klassen vollständig** von der Mutation aus, obwohl die Begründung
im Code nur Funktionsdekoratoren betrifft. In einer Codebasis mit
`@dataclass` oder `@define` fällt damit ein erheblicher Teil des Produktivcodes
stillschweigend aus der Messung.

### A7 — Leere Testliste ohne Fehlermeldung

`src/mutmut_win/runner.py:495` · hoch · [gegengeprüft]

`collect_tests` liefert still eine leere Testliste, sobald die effektive
Test-Case-Verbosity nicht exakt `-1` ist. Keine Tests → keine Kills → jeder
Mutant überlebt, und der Lauf meldet das als Ergebnis.

Gleiche Klasse: `hit_recording.py:68` (`HR-01`, mittel) — `max_stack_depth`
verbraucht das Budget mit mutmut-eigenen Frames; die Werte 1 bis 4 verwerfen
stillschweigend *jeden* Stats-Hit.

### A8 — Dokumentierter Nenner ≠ implementierter Nenner

`src/mutmut_win/models.py:490` · niedrig · [gegengeprüft]

`MutationRunResult.score`: der dokumentierte Nenner enthält `unchecked` nicht,
die Implementierung zieht ihn ab. Für sich genommen harmlos — in einer Liste,
in der es um die Glaubwürdigkeit genau dieser Zahl geht, gehört es benannt.

---

## Kapitel B — Nichtdeterminismus: warum ein roter Lauf nichts beweist

Dies ist die Spur, die dem Review als priorisierte Frage vorgegeben war, und sie
hat geliefert. Der Befund ist **nicht** „da ist irgendwo eine Race Condition".
Der Befund ist ein zusammenhängender, benennbarer Mechanismus mit einer Wurzel
und fünf Verstärkern.

### Die Wurzel: ein Lesefehler wird als Byte-Änderung gemeldet

`src/mutmut_win/stats.py:458` · BC-005 · kritisch · **[quellgeprüft]**

`_hash_context_file` fängt pauschal:

```python
except (OSError, RuntimeError, UnicodeError, ValueError) as exc:
    record_error("hash-file", exc, path=str(path))
    hasher.update(b"unreadable:")
    hasher.update(type(exc).__qualname__.encode("ascii", errors="replace"))
    hasher.update(b"\0")
    return False
```

Kein Retry. Kein Backoff. Keine Unterscheidung zwischen „diese Datei ist weg"
und „diese Datei war für 3 ms nicht öffenbar, weil Defender ein Handle hielt".

Das `return False` propagiert nach oben: `_hash_context_tree` setzt
`complete=False`. Und dann, `orchestrator.py:115-127`:

```python
current = build_staging_context_evidence()
if not current.complete or current != expected:
    raise OrchestratorError(
        "executable staging files changed after mutant generation; the run cannot "
        "authorize cached verdicts, score gates, or CI/CD export"
    )
```

**`not current.complete` löst dieselbe Meldung aus wie `current != expected`.**
Der Lauf bricht mit der Behauptung ab, Staging-Dateien hätten sich geändert —
eine Behauptung, die der Code an dieser Stelle nie festgestellt hat. Er weiß
nur, dass er eine Datei nicht lesen konnte.

Das ist der Grund, warum die vier TOCTOU-Fehlschläge dieser Sitzung beim
Wiederholungslauf sämtlich grün wurden: es hatte sich nie etwas geändert.

Bemerkenswert ist die Asymmetrie. Auf der **Schreibseite** hat das Projekt
ausgereifte Retry-Leitern — `atomic_file.py` führt
`_SIBLING_VALIDATION_RETRY_DELAYS`, `_REPLACE_RETRY_DELAYS` und
`_PARENT_CAPTURE_RETRY_DELAYS` und dokumentiert die beobachtete Störrate
ausdrücklich. Auf der **Leseseite** gibt es nichts dergleichen. Dieselbe
Windows-Realität, die auf der einen Seite sorgfältig behandelt wird, ist auf der
anderen unbehandelt.

**Fix:** transiente Lesefehler von echter Drift trennen. Für die wiederholbaren
Windows-Fälle (`ERROR_SHARING_VIOLATION`, `ERROR_LOCK_VIOLATION`,
`ERROR_ACCESS_DENIED` auf einer existierenden regulären Datei) eine begrenzte
Retry-Schleife mit Backoff, analog `_REPLACE_RETRY_DELAYS`. Und —
unabhängig davon, sofort und billig — **`complete=False` und `!=expected` in
zwei verschiedene Fehlermeldungen trennen** (`STAGE-02`,
`orchestrator.py:122`). Allein das hätte uns heute Stunden gespart.

### Verstärker 1: der doppelte Basis-Snapshot

`src/mutmut_win/orchestrator.py:302` · BC-001 · kritisch · [gegengeprüft]

`_stable_run_basis_evidence` berechnet die Ausführungsbasis **zweimal
hintereinander** und vergleicht die Ergebnisse. Der Digest enthält bei einem
Lesefehler den Marker `unreadable:<Typ>` statt des Inhalts. Tritt der transiente
Fehler nur in *einem* der beiden Durchläufe auf — bei zwei Durchläufen von je
15 bis 23 Sekunden unter Last der Normalfall —, unterscheiden sich die Digests,
obwohl sich keine einzige Eingabe geändert hat.

Der Stabilitätsbeweis, der Drift ausschließen soll, **erzeugt** die Drift. Er
verdoppelt außerdem das Zeitfenster, in dem ein Fehler auftreten kann.

Gleiche Klasse am Laufende: `orchestrator.py:453` (`ORCH-03`, hoch) — ein
transienter Lesefehler verwirft dort einen **vollständig gerechneten Lauf** als
`failed`. Die gesamte Arbeit ist verloren.

### Verstärker 2: der Executor verändert den eingefrorenen Baum

`src/mutmut_win/process/executor.py:173` · BC-002 · kritisch · **[quellgeprüft]**

Vier unabhängige Agenten haben diesen Befund gefunden (`EXEC-01`, `ORCH-01`,
`EXEC-02`, `WRK-05`, `STAG-02`). Er ist der sauberste der ganzen Sammlung, weil
er keine Race Condition braucht — er ist eine reine Reihenfolgeverletzung.

Der Orchestrator friert den Staging-Baum ein:

```python
# orchestrator.py:621
staging_evidence = build_staging_context_evidence()
```

Und `build_staging_context_evidence` hasht:

```python
skip_dirs=frozenset(),
root_skip_dirs=frozenset(),
hash_file_timestamps=True,
hash_directory_timestamps=True,
hash_link_counts=True,
```

Also **alles** unterhalb `mutants/`, inklusive Datei- und
Verzeichniszeitstempeln und Link-Counts.

Danach ruft `SpawnPoolExecutor.start()` als eine seiner ersten Handlungen:

```python
_sweep_stale_artifacts(Path("mutants"))
```

und `unlink()`t dort alle Treffer von `mutmut_out_*.log` und
`mutmut_tests_*.txt`. Ich habe nachgeprüft: `_skip_context_file` filtert
ausschließlich Run-Lock-Dateien, diese Muster **nicht**. Sie sind Teil des
gehashten Satzes.

Wenn der Sweep also etwas findet — und sein eigener Docstring sagt, dass der
Audit „four orphaned logs in a real tree" vorgefunden hat —, dann ändert er den
Dateisatz *und* die mtime von `mutants/`. Die nachfolgenden Prüfungen in
`orchestrator.py:848` und `:980` schlagen zwangsläufig fehl. Der komplette Lauf
ist verloren, nachdem die gesamte Arbeit getan war.

**Fix:** Den Sweep dorthin verlegen, wo der Baum noch veränderlich ist — vor
`build_staging_context_evidence()`, am natürlichsten in
`purge_staging_runtime_artifacts()`, das dort ohnehin schon läuft.

### Verstärker 3: der gehashte Baum ist zugleich das Arbeitsverzeichnis

`src/mutmut_win/runner.py:368` · hoch · **[quellgeprüft]**

Alle pytest-Phasen und alle Mutations-Worker starten mit `cwd="mutants"` —
genau dem Baum, der bytegenau inklusive Zeitstempeln gehasht und nach jeder
Phase gegen den Snapshot geprüft wird.

Der Phase-Guard entschärft nur **bekannte** Plugin-Ausgaben (basetemp, xmlpath,
log_file, htmlpath, json_report_file, report_log). Er kann nichts gegen einen
gewöhnlichen Anwendertest tun, der `open("report.csv", "w")` aufruft, eine
SQLite-Datei anlegt oder ein Verzeichnis erzeugt — und sie im Teardown sauber
wieder entfernt. Der Test ist korrekt. Der Lauf bricht trotzdem ab.

**Das ist ein Fremdprojekt-Risiko ersten Ranges.** Jedes Zielprojekt mit einem
Test, der relativ zum Arbeitsverzeichnis schreibt, lässt mutmut-win scheitern —
mit einer Fehlermeldung, die dem Anwender Staging-Drift vorwirft.

Gleiche Wurzel, weitere Fundstellen: `orchestrator.py:1689` (`TYPECHK-01`,
`ORCH-01`, hoch) — der Type-Checker läuft mit `cwd=mutants/` ohne
Cache-Umleitung und schreibt seinen Cache in das eingefrorene Staging.
`worker.py:846` (BC-004, kritisch) — das unveränderliche Guard-Plugin wird bei
**jeder einzelnen Task** neu in den eingefrorenen Baum publiziert, also bei
4000 Tasks 4000-mal. `atomic_file.py:172` (`ATOM-03`, hoch) — die
Publikations-Siblings liegen unter einem Namen im gemessenen Baum, den der
Fingerprint nicht filtert.

### Verstärker 4: instabile Windows-Metadaten im Fingerprint

`src/mutmut_win/stats.py:680` · hoch · [gegengeprüft]

Der Staging-Fingerprint bindet `st_nlink` (`hash_link_counts=True`,
quellgeprüft). Das Projekt dokumentiert an anderer Stelle selbst, dass die
handle-abgeleitete `st_nlink`-Beobachtung unter Windows unzuverlässig ist —
und behandelt sie hier trotzdem als Beweis für Staging-Drift, mit hartem
Laufabbruch (`STAGE-01`, `STAG-01`, `ATOM-02`).

Dazu passt `atomic_file.py:53` (`WIN-01`, hoch): der Identitäts-Tripwire hat
keinen Null-Guard, obwohl Windows für nicht öffenbare Pfade `st_dev=0` und
`st_ino=0` liefert — zwei Nullen vergleichen sich gleich, die Identitätsprüfung
ist in genau dem Moment blind, in dem sie greifen müsste.

Und `stats.py:339` / `:343` (`BASIS-06`, `STATS-05`, mittel): die Projektbasis
bindet `st_mtime_ns`/`st_ctime_ns` jeder Datei — ein **bytegleiches**
Neuschreiben invalidiert einen abgeschlossenen Lauf. Volatile
Windows-Dateiattribute sind ebenfalls gebunden, und das Hashen selbst kann sie
verändern.

### Verstärker 5: der Hash-Seed ist nicht gepinnt

`src/mutmut_win/process/worker.py:1072` · hoch · **[quellgeprüft]**

`PYTHONHASHSEED` wird nirgends in `src/` oder `scripts/` gesetzt — ich habe
danach gesucht, es existiert nicht. Keine pytest-Phase bekommt einen gepinnten
Seed, und der Seed ist auch nicht Teil der Run-Basis.

Das wäre für sich schon unschön. Zusammen mit `runner.py:942` wird es konkret:

```python
dirs_repr = repr(set(real_src_dirs))
```

Das generierte `sitecustomize.py` enthält das `repr()` einer **Menge**. Deren
Iterationsreihenfolge hängt bei Strings am Hash-Seed. Diese Datei wird nach
`mutants/` geschrieben — in den Baum, der bytegenau gehasht wird.

Folge: bei mindestens zwei Einträgen unterscheidet sich die
Ausführungsbasis zwischen zwei Läufen **ohne jede Änderung am Projekt**.
Zwischengespeicherte Verdikte werden nie wiederverwendet. Das erklärt das
Symptom, dass Stats bei jedem Lauf vollständig neu erhoben werden
(`RUN-02`, `STAT-02`).

Dritter im Bunde: `config.py:438` (`ORCH-ORD-02`, hoch) — `also_copy` erhält
Default-Einträge aus einem **unsortierten** `project_dir.glob("test*.py")` und
wird wörtlich in den Run-Basis-Digest gehasht. Quellgeprüft; die Zeile lautet
exakt so.

### Verstärker 6: der Basisumfang ist an drei Stellen verschieden

Drei Baumläufe über projektinterne Bäume, drei verschiedene Verträge:

| Fundstelle | `ignore_boundary` | Folge |
|---|---|---|
| `stats.py:1310` Projektlauf | `project_boundary` | korrekt |
| `stats.py:1048` `_hash_effective_import_paths` | `_project_descended_boundary(...)` | schneidet ein projektinternes `.venv` **vollständig** heraus (`BASIS-04`) |
| `stats.py:874` `_hash_project_import_core` | **keine** | git-ignorierte, volatile Dateien landen im harten core-Digest (`BASIS-02`) |

Die Wirkung ist in beide Richtungen falsch. `BASIS-04`: ein
`.venv/Lib/site-packages/sitecustomize.py`, das bei jedem Interpreterstart läuft
und das Verhalten jedes Workers verändert, invalidiert die Basis **nie** — die
Gitignore-Grenze ist eine Staging-Semantik und darf nicht über
Ausführungsrelevanz entscheiden. `BASIS-02`: eine `Thumbs.db`, die Windows beim
Öffnen des Ordners im Explorer anlegt, invalidiert sie **sofort**.

Dazu `BASIS-01` (`stats.py:846`, hoch): der core-Digest bindet globale
`sys.path`-**Indizes**. Fügt irgendetwas im Elternprozess einen ambienten
Eintrag vor den Projekteinträgen ein — ein spät importiertes pytest-Plugin, ein
`sys.path.insert(0, ...)` in einer Bibliothek —, verschieben sich alle
projektinternen Indizes. Eine ambiente Änderung wird als Projektänderung
fehlklassifiziert, also als *terminal* statt als tolerierbar. Genau die
Unterscheidung, für die der core-Digest laut seinem eigenen Docstring existiert.

---

## Kapitel C — Windows-Semantik

Ein Windows-nativer Port wird an genau diesen Stellen gemessen.

### C1 — Jeder Reparse-Punkt gilt als Link

`src/mutmut_win/file_setup.py:154` · hoch · [gegengeprüft]

Die Link-Erkennung behandelt **jeden** Reparse-Punkt als Link. Auf einem Volume
mit Windows-Datendeduplizierung oder unter einem Cloud-Ordner (OneDrive,
Dropbox, Egnyte) trägt ein großer Teil aller Dateien einen Reparse-Punkt, ohne
in irgendeinem Sinne ein Link zu sein. Folge: **der komplette Quellbaum geht
verloren.**

Das ist der Befund mit dem größten Ausrollrisiko in dieser Sammlung. Ein
Dateiserver mit aktivierter Deduplizierung und ein OneDrive-synchronisierter
Projektordner sind beides Normalfälle in Unternehmensumgebungen — und in beiden
verhält sich das Werkzeug nicht etwa langsam oder unzuverlässig, sondern
verarbeitet den Quellcode nicht.

Verwandt: `file_setup.py:1417` (`FS-05`, mittel) — der konfigurierte Kopierpfad
besitzt die Junction-/Reparse-Abwehr des automatischen Pfads nicht; `os.walk`
läuft unter Windows in Junctions hinein.

### C2 — `apply` kann den falschen Mutanten in den Quellcode schreiben

`src/mutmut_win/test_mapping.py:84` · mittel · [gegengeprüft]

`match_mutant_names` nutzt `fnmatch` statt `fnmatchcase` und matcht Mutantennamen
unter Windows damit **case-insensitiv** (`NAME-01`, `TM-01`). Dasselbe in
`mutant_diff.py:126` (`MD-01`): `resolve_mutant` ist case-insensitiv, was
entweder zu einer falschen Mehrdeutigkeitsmeldung führt oder — schlimmer — zum
**stillen Anwenden eines nicht benannten Mutanten**.

`mutmut-win apply` schreibt in den Arbeitsbaum des Anwenders. Ein Befund dieser
Klasse ist kein Anzeigefehler, sondern eine Quellcodeänderung, die niemand
angefordert hat. In einem Projekt mit `Parser.py` und `parser.py`, oder mit
`test_Foo` und `test_foo`, reicht das aus.

Dazu `cli.py:1107` (`CLI-04`, niedrig): `apply` meldet im Erfolgsfall das
Glob-Muster statt des tatsächlich angewandten Mutanten. Die Diagnose, mit der
man den Fehler bemerken würde, fehlt also genau dort.

### C3 — `.gitignore` mit UTF-8-BOM verliert ihr erstes Muster

`src/mutmut_win/gitignore_boundary.py:91` · hoch · [gegengeprüft]

Unter Windows erzeugen Notepad, Visual Studio und diverse PowerShell-Pipelines
Dateien mit BOM. Das erste Muster einer solchen `.gitignore` wird still
entwertet (`GIT-01`, `WIN-05`).

Daneben (`WIN-04`, mittel, `gitignore_boundary.py:107`): das Matching ist
case-sensitiv, Git unter Windows ist es nicht — ignorierte Bäume landen im
Basis-Hash. Und (`GI-01`, mittel, `:228`): `_excludes` verliert Gits
Verzeichnismarker-Präzedenz; ignorierte Teilbäume werden gelaufen, gestagt und
gehasht.

Dieses Modul war bereits die Quelle des in `v2.21.4` behobenen Defekts. Die
Sammlung zeigt, dass dort weitere Abweichungen von Gits Semantik liegen. Eine
Gegenüberstellung der vollständigen `gitignore`-Spezifikation mit der
Implementierung wäre hier lohnender als das Nachziehen von Einzelfällen.

### C4 — Weitere Windows-Fundstellen

| Ort | Befund |
|---|---|
| `file_setup.py:519` | `str.casefold()` als NTFS-Identitätsschlüssel erzeugt falsche Staging-Kollisionen |
| `atomic_file.py:172` | Atomare Publikation verbraucht 52 Zeichen MAX_PATH-Budget ohne jede Langpfad-Behandlung |
| `cli.py:151` | `--force`-Cleanup ignoriert Readonly-Attribute und scheitert dauerhaft mit falscher Diagnose |
| `file_setup.py:1071` | Staging-Kopie gibt nach 1,5 s Gesamtbackoff auf, obwohl der eigene Docstring Defender als Ursache benennt |
| `db.py:384` | Transiente Windows-Zustände werden nur für Sidecars toleriert; für das Datenbank-Leaf führt derselbe Zustand zur Fehldiagnose „is a hardlink (0 links)" |

---

## Kapitel D — Prozess- und Ressourcenhygiene

### D1 — Der TUI-Browser startet einen uneingehegten Lauf

`src/mutmut_win/browser.py:597` · hoch · [gegengeprüft] · **erklärt eine
Beobachtung aus Kapitel I**

Jeder andere Produktionslauncher im Repository fällt geschlossen aus, wenn kein
kill-on-close Job Object hergestellt werden kann: `worker._popen_contained`,
`type_checking._run_type_check_process`, `SpawnPoolExecutor.__init__`,
`generation_supervisor`. Alle vier verweigern den Start.

`BrowserApp` nicht. Die Taste für `action_retest_module` startet
`python -m mutmut_win run <modul>.*` als gewöhnlichen Kindprozess — ohne Job
Object. Dieser Lauf erzeugt seinerseits `max_children` Worker und deren
pytest-Kinder. Wird der TUI-Prozess hart beendet, hält niemand mehr die Kette.

Das deckt sich exakt mit der Beobachtung aus Kapitel I: sechs verwaiste
mutmut-Prozesse, 274 und 362 Minuten alt, die abgeschossene Läufe überlebt
hatten — entgegen dem Job-Object-Versprechen des Werkzeugs.

**Fix:** dieselbe Regel anwenden, die überall sonst gilt — einhegen oder
fail-closed abbrechen.

### D2 — Weitere Lecks und Blockaden

| Ort | Befund | Schwere |
|---|---|---|
| `process/generation_supervisor.py:501` | Fester 15-s-Join verwirft eine **vollständig erfolgreiche** Mutantengenerierung | hoch |
| `process/run_lock.py:717` | Datenbank-Lock-Domäne hängt an `tempfile.gettempdir()` und ist damit nicht global | hoch |
| `process/generation_supervisor.py:295` | No-Progress-Deadline begrenzt nur `wait()`, nicht das nachfolgende `recv()` — der Parent kann **unbegrenzt** blockieren | mittel |
| `process/executor.py:99` | Job-Object-Handle und drei Multiprocessing-Queues werden in `__init__` belegt, ohne `finally`/`__exit__`/`__del__` auf dem Fehlerpfad | mittel |
| `process/output_capture.py:89` | `close()` lässt bei einem überlebenden Writer Deskriptor und Drain-Thread dauerhaft zurück | mittel |
| `process/worker.py:1557` | `_popen_contained` übergibt den synthetischen PID eines Popen-Test-Doubles an `OpenProcess`/`AssignProcessToJobObject` | mittel |
| `atomic_file.py:221` | Doppeltes `os.close(fd)` auf dem Erschöpfungspfad kann einen **fremden** Deskriptor schließen | mittel |
| `atomic_file.py:155` | `_dump_sibling_diagnostics` schreibt symlinkfolgend an einen vorhersagbaren Namen im gemeinsamen Temp-Verzeichnis | mittel |

Die letzten beiden verdienen einen eigenen Blick: ein doppeltes `os.close()` auf
einen wiederverwendeten Deskriptorwert ist die Sorte Fehler, die als
unerklärlicher Fehler ganz woanders auftaucht. Und ein symlinkfolgender Schreibzugriff auf einen vorhersagbaren Namen in `%TEMP%` ist auf einem Mehrbenutzersystem eine Sicherheitsfrage, keine Hygienefrage.

---

## Kapitel E — Skalierung und Laufzeit

### E1 — Die Ausführungsbasis wird pro Lauf fünfmal vollständig berechnet

`src/mutmut_win/orchestrator.py:350` · hoch · **[beobachtet]**

`_installed_distribution_basis` hasht den **Inhalt jeder Datei jeder
installierten Distribution**. `_build_stats_context_evidence` ruft das zusätzlich
zum kompletten Projektbaum-Walk auf. Diese Gesamtarbeit wird **fünfmal pro Lauf**
ausgelöst: zweimal im Stabilitätsbeweis beim Start, dreimal danach.

Das ist keine Theorie. Genau dieses Verhalten hat in dieser Sitzung einen Lauf
zum Stillstand gebracht: mit 131 Paketen in der Umgebung — darunter Semgrep mit
mehreren hundert MB nativer Artefakte — blieb der Prelude minutenlang blockiert,
bevor eine einzige Mutation begonnen hatte. Der StallWatchdog hat Stacks
gedumpt. Mit einer schlanken Umgebung (61 Pakete) fiel dieselbe Phase auf
14,3 Sekunden.

**Das ist für Anwender ein Blocker, kein Komfortproblem.** Ein Zielprojekt mit
einer üblichen Entwicklungsumgebung — Semgrep, Playwright, torch, ein
CUDA-Wheel — erlebt das Werkzeug als „hängt beim Start".

**Fix:** Distributionsanteil vom projektlokalen Anteil trennen und pro Prozess
memoisieren; für die Drift, die der zweite Snapshot erkennen soll, genügt ein
Metadaten-Check statt eines Vollinhalts-Hashes.

Verwandt: `stats.py:1150` (`STATS-06`) — keine Größen- oder Relevanzgrenze;
`stats.py:1419` (`BASIS-07`) — `core_seen` startet leer, der gesamte Projektbaum
wird pro Snapshot ein zweites Mal vollständig gelesen, was zugleich das
Race-Fenster aus Kapitel B vergrößert.

### E2 — Jedes einzelne Verdikt kostet 35 bis 112 ms in der Event-Loop

`src/mutmut_win/db.py:1647` · hoch · [gegengeprüft]

Jedes persistierte Verdikt kostet zwei SQLite-Verbindungen, einen kompletten
Schemadurchlauf und **15 vollständige Dateisystem-Baumvalidierungen** —
gemessen 35 bis 112 ms, serialisiert in der Orchestrator-Event-Loop.

Bei 4000 Mutanten sind das zwischen 2,3 und 7,5 Minuten reine Persistenzzeit,
die nicht parallelisiert ist und in der keine Mutation läuft.

Dazu `db.py:554` (`DB-04`, mittel): kein `busy_timeout`, kein WAL, kein Retry —
**jede** SQLite-Sperrkonkurrenz beendet nach 5 Sekunden den gesamten Lauf.

### E3 — Weitere Kostenstellen

| Ort | Befund |
|---|---|
| `file_setup.py:891` | `validate_staging_namespace` läuft dreimal pro Lauf über den gesamten Projektbaum, O(automatische Eingaben × konfigurierte Wurzeln) |
| `basis_diagnostics.py:355` | `register_input_root` ist pro gehashter Datei quadratisch in der Zahl der Eingabeverzeichnisse |
| `atomic_file.py:585` | Jede Staging-Datei wird vollständig in den Speicher gelesen |
| `atomic_file.py:428` | `_capture_parent_identity` wiederholt auch **permanente** Ablehnungen und stallt 16,1 s pro Schreibvorgang |

---

## Kapitel F — CLI, Konfiguration, Persistenz

### F1 — `--since-commit` endet still mit Exit 0

`src/mutmut_win/cli.py:604` · hoch · [gegengeprüft]

`--since-commit` vergleicht repo-root-relative git-Pfade gegen das aktuelle
Arbeitsverzeichnis. Stimmen die nicht überein — also immer, wenn man das
Werkzeug nicht exakt im Repository-Wurzelverzeichnis aufruft —, findet es keine
geänderten Dateien und beendet sich **erfolgreich mit Exit 0**.

In einer CI-Pipeline bedeutet das: das Gate ist grün, weil nichts geprüft wurde.
Das ist die gefährlichste Form eines Fehlers in einem Qualitätswerkzeug.

Verwandt: `cli.py:611` (`CLI-01`, mittel) — `--since-commit` macht Testdateien
außerhalb der konfigurierten `tests_dir`-Unterbäume zu Mutationszielen.

### F2 — `--do-not-mutate` umgeht die Subset-Sperre

`src/mutmut_win/cli.py:517` · hoch · [gegengeprüft]

`--do-not-mutate` verengt das Mutantenuniversum, umgeht aber die
`--min-score`-Subset-Sperre und die `is_full_run`-Kennzeichnung. Ein Score über
einer selbst gewählten Teilmenge wird als vollwertiger Lauf gewertet — man kann
sich das Gate also durch Ausschließen der schlecht getesteten Module grün
konfigurieren, ohne dass das Werkzeug widerspricht.

### F3 — Umgebungsfehler werden als Cache-Korruption diagnostiziert

`src/mutmut_win/db.py:534` · hoch · [gegengeprüft]

`_raise_database_error` stuft readonly-Dateisysteme, I/O-Fehler, volle Platten
und `cantopen` als **Cache-Korruption** ein und fordert den Anwender auf, das
Ergebnisverzeichnis zu löschen.

Die Diagnose ist falsch, und der Rat ist schädlich: wer bei voller Platte seine
Ergebnisse löscht, verliert Daten und behebt nichts.

### F4 — Der Typprüfer-Filter bricht jeden Lauf ab

`src/mutmut_win/type_checking.py:388` · hoch · [gegengeprüft]

Der mypy-Report-Parser scheitert an mypys eigener Summary-Zeile. Wenn das in der
gemeldeten Allgemeinheit zutrifft, ist der Typprüfer-Filter im Auslieferungszustand unbenutzbar. Dieser Befund gehört als erster verifiziert, weil er
entweder trivial zu beheben oder gar nicht vorhanden ist.

Dazu `type_checking.py:417` (`TC-02`, niedrig): `parse_pyright_report` stürzt mit
`AttributeError` ab, wenn ein unbekannter Checker ein JSON-Array liefert.

### F5 — Fremdprojekt-Verzeichnisse werden unwiderruflich ausgeschlossen

`src/mutmut_win/constants.py:159` · mittel · [gegengeprüft]

`WORKSPACE_EXCLUDED_DIR_NAMES` enthält hartcodierte Verzeichnisnamen **des
mutmut-win-Repositories selbst** und schließt gleichnamige Verzeichnisse in
Fremdprojekten unwiderruflich aus. Ein Zielprojekt mit einem eigenen `scripts/`
oder `benchmarks/` verliert diese Bäume ohne Meldung.

Für ein Werkzeug, das an Entwicklerteams ausgeliefert werden soll, ist ein
hartcodierter Verweis auf die eigene Repository-Struktur ein Konstruktionsfehler,
kein Einzelfall.

### F6 — Konfigurationsfehler

| Ort | Befund | Schwere |
|---|---|---|
| `config.py:539` | Wertfehler in `setup.cfg [mutmut]` umgehen die `ConfigError`-Schicht und erscheinen als roher pydantic-Traceback | hoch |
| `config.py:469` | `ConfigParser`-`[DEFAULT]`-Einträge werden still als `[mutmut]`-Konfiguration übernommen und erzeugen falsche Unknown-Option-Warnungen | mittel |
| `config.py:297` | `mutation_profile` akzeptiert einen TOML-Boolean still als `Profile.ADVANCED` | niedrig |
| `config.py:88` | `guess_paths_to_mutate` kann den **leeren Pfad** als Mutationswurzel zurückgeben | niedrig |
| `code_coverage.py:57` | Coverage-Gating vergleicht nicht aufgelöste Pfade gegen `coverage.py`-Schlüssel (realpath) — Fehlabbruch mit irreführender Meldung | mittel |
| `pytest_boundary.py:178` | Absolute, projektinterne `tests_dir`-Einträge verschieben die pytest-Konfigurationsgrenze in den Staging-Spiegel, während pytest den Live-Baum sammelt | mittel |

---

## Kapitel G — Vertrags- und Dokumentationsabweichungen

19 Befunde der Kategorie `api-contract`. Für sich genommen selten gefährlich,
in der Summe aber ein Vertrauensproblem: wo der Docstring etwas anderes sagt als
der Code, ist beides unbrauchbar als Grundlage für eine Entscheidung.

| Ort | Abweichung |
|---|---|
| `stats.py:1713` | `_run_stats_collection`: Docstring verspricht Rückgabe des Caches bei Fehlschlag, Code liefert leere Stats — und die Meldung suggeriert das Gegenteil |
| `stats.py:1646` | `collect_or_load_stats`: Docstring verspricht inkrementelle Neuerhebung „nur für neue Tests", Code erhebt immer die volle Suite |
| `orchestrator.py:1577` | `_apply_timeouts`: der dokumentierte „selected test time"-Budgetzweig ist **unerreichbar**, jede Task bekommt das Full-Suite-Budget |
| `models.py:490` | `MutationRunResult.score`: dokumentierter Nenner ≠ implementierter Nenner |
| `mutant_diff.py:577` | `apply_mutant`: Raises-Docstring nennt mtime als Stale-Kriterium, der Code vergleicht SHA-256 |
| `code_coverage.py:103` | Moduldocstring beschreibt den Coverage-Datenpfad innerhalb `mutants/`, die Implementierung schreibt bewusst außerhalb |
| `db.py:626` | Schreibgrenze permissiver als Lesegrenze: `_prepare_result` validiert `mutant_name` gar nicht, `load_results` meldet denselben Namen als Cache-Korruption |
| `mutation.py:378` | `len`/`isinstance` werden nur nach Namen erkannt und löschen den kompletten Argument-Teilbaum |
| `node_mutation.py:506` | `operator_regex` prüft nicht, ob `args[0]` positional ist — Keyword-Argumente werden als Regex mutiert, der echte `pattern=` bleibt unmutiert |
| `type_checking.py:27` | Typprüfer-Budget ist als einziges Phasenbudget hartkodiert und nicht konfigurierbar |
| `orchestrator.py:750` | Forced-Fail-Gate prüft nur den globalen fail-Sentinel, nicht die namensbasierte Mutantenauswahl |
| `gitignore_boundary.py:70` | Unlesbare oder von pathspec abgelehnte Regeln erweitern still den gehashten Baum, ohne die Vollständigkeitsmeldung zu senken |
| `process/worker.py:853` | Default-Argumente schreiben Koordinationsdateien in den eigenen Hashsatz |

Der letzte Eintrag gehört sachlich zu Kapitel B.

---

## Kapitel H — Die Testsuite selbst

Drei Befunde betreffen nicht das Produkt, sondern seinen Nachweis. Sie sind der
Grund, warum die Suite auch ohne Produktfehler rot werden kann.

| Ort | Befund | Schwere |
|---|---|---|
| `tests/integration/test_e2e_pipeline_validation.py:57` | 180-s-Subprozesslimit widerspricht der dokumentierten Coverage-Verdopplung der Schwesterdatei (300 s) | hoch |
| `tests/integration/test_e2e_pipeline_validation.py:211` | Der E2E-Snapshot-Test macht sich rot an genau den Verdikten, die der Produktionscode selbst als **umgebungsabhängig** deklariert | hoch |
| `tests/integration/test_generation_supervisor.py:253` | Lastempfindliche Wanduhr-Assertions um zwei verschachtelte kalte Windows-`spawn`s | mittel |

Der mittlere ist der aufschlussreichste: ein Test, der auf Werten besteht, die
der Produktionscode ausdrücklich nicht garantiert, kann nur durch Glück grün
sein. Beobachtet: 95 s Ist-Laufzeit gegen ein 180-s-Budget — ein Faktor 1,9 auf
einer unbelasteten Maschine ist kein Sicherheitsabstand.

---

## Kapitel I — In dieser Sitzung selbst beobachtet

Diese Punkte sind nicht aus einem Review abgeleitet. Sie sind am laufenden
System passiert. **[beobachtet]**

| # | Beobachtung | Zuordnung |
|---|---|---|
| I-1 | **Vier TOCTOU-Fehlschläge** während der Releasevorbereitung, auf vier verschiedenen Tests. Jeder einzelne wurde beim Wiederholungslauf grün; zwei vollständige Läufe desselben Trees waren komplett grün. | Kapitel B, Wurzel |
| I-2 | **Sechs verwaiste mutmut-Prozesse**, 274 und 362 Minuten alt, die abgeschossene Läufe überlebt hatten — entgegen dem Job-Object-Versprechen. | D1 |
| I-3 | **Prelude-Blockade** mit 131 Paketen in der Umgebung; StallWatchdog dumpte Stacks. Mit 61 Paketen: 14,3 s. | E1 |
| I-4 | **Engine-Selbstmutation**: ~25 Minuten pro Mutant im suitenweiten Lauf, weil das mutierte Modul Teil der eigenen Staging-/Fingerprint-Maschinerie ist. Gezielte Gates: ~1 Minute. | — |
| I-5 | **Tote API-Fläche**: `_root` wird nie gelesen, `StallWatchdog.timeout` wird nie gelesen. | — |
| I-6 | **Dokumentationslücke**: Statements auf Modulebene erzeugen keine Mutanten. Nirgends dokumentiert. | — |
| I-7 | **Offene Survivor**: 41 in `gitignore_boundary` (davon 15 in `descend_forced`), 3 äquivalente im Watchdog. | — |
| I-8 | **Evidenzlücke `v2.21.3`**: die Angabe „2593 passed" im Release-Body ist nie belegt worden. Sie wurde im Release-Body als nicht nachgemessen annotiert, statt sie durch eine geratene Zahl zu ersetzen. | Kapitel K |
| I-9 | **Stale Caches im Checkout**: `tests/unit/__pycache__/` enthält `.pyc`-Dateien für **CPython 3.13** und pytest 8.2.2 vom 30.08./01.09. Sie sind gitignoriert und damit vertragskonform, belegen aber, dass in diesem Checkout unter einer Runtime getestet wurde, die der Produktvertrag (`==3.14.7`) ausschließt. | — |
| I-10 | **CI-Vorbefund**: der GitHub-CI-Testjob schlägt seit mindestens 2026-09-08 sporadisch fehl, über `v2.21.2` und `v2.21.3` hinweg. Das ist keine Regression von `v2.21.4`. | Kapitel B |

I-4 verdient eine Anmerkung, weil sie die Methodik betrifft: solange ein Modul
Teil der Werkzeugmaschinerie ist, ordnet der suitenweite Mutationslauf Kills
nicht korrekt zu. Der ehrliche Nachweis ist ein **gezieltes Gate** mit genau den
Contract-Tests des Moduls als einzigem `--tests-dir`. Diese Regel gilt für jede
weitere Mutationsmessung an diesem Projekt.

---

## Kapitel J — Geprüft und widerlegt

50 Kandidaten wurden von der Gegenprüfung verworfen. Sie stehen hier, damit
niemand sie ein zweites Mal untersucht. Jeder Eintrag bedeutet: *ein Agent hielt
das für einen Defekt, ein zweiter hat am Quelltext gezeigt, dass es keiner ist.*

| Ort | Behauptung | Herkunft |
|---|---|---|
| `src/mutmut_win/atomic_file.py` | Replace- und Validierungs-Retryleitern budgetieren 0,18 s bzw. 0,11 s fuer eine Stoerung, die drei Zeilen tiefer als sekundenlang dokumentiert ist | ATOM-01 |
| `src/mutmut_win/basis_diagnostics.py` | Pro component_scope entstehen ein json.dumps und eine vollstaendige Ahnenkette; _transition serialisiert sie erneut je Capture-Paar | DIAG-02 |
| `src/mutmut_win/browser.py` | Der als DB-only dokumentierte Diff-Fallback kann konstruktionsbedingt nie einen Diff liefern | BROW-05 |
| `src/mutmut_win/code_coverage.py` | gather_coverage schliesst die coverage-SQLite-Verbindung nie; das Temp-Verzeichnis bleibt unter Windows dauerhaft liegen | COV-01 |
| `src/mutmut_win/constants.py` | Ausschlussliste enthaelt Verzeichnisnamen des eigenen Repos und trifft Fremdprojekte | CFG-01 |
| `src/mutmut_win/db.py` | _write_transaction validiert die Dateiidentitaet erst nach conn.commit(); eine Ausnahme dort meldet einen bereits dauerhaften Schreibvorgang als Fehlschlag und hinterlaesst bei begin_run einen blockierenden aktiven Run | DB-03 |
| `src/mutmut_win/file_setup.py` | walk_all_files sortiert weder Verzeichnisse noch Dateien — Mutanten-Plan, Ordinale und Plan-Digest folgen der Dateisystemreihenfolge | ORCH-ORD-06 |
| `src/mutmut_win/file_setup.py` | create_mutants_for_file ueberschattet das Modul 'stat' mit einer lokalen Variablen | FS-07 |
| `src/mutmut_win/file_setup.py` | Transient gesperrte Live-Quelldatei fuehrt zum Loeschen ihrer gestagten Kopie | WIN-08 |
| `src/mutmut_win/file_setup.py` | Staging-Kollisionspruefung wird fail-open, wenn Path.samefile auf Null-Identitaeten trifft | WIN-02 |
| `src/mutmut_win/file_setup.py` | Ahnenweite Reparse-Ablehnung und resolve-Gleichheit sperren subst-, Netz- und Junction-Pfade mit falscher Diagnose aus | WIN-09 |
| `src/mutmut_win/file_setup.py` | get_mutant_name loescht den kompletten Pfad, wenn der Suffix leer ist | NAME-02 |
| `src/mutmut_win/hit_recording.py` | Fehlgeschlagener Config-Load im Trampolin-Kernel cached dauerhaft 'unbegrenzte Stacktiefe' und ignoriert damit still die konfigurierte max_stack_depth | HIT-01 |
| `src/mutmut_win/orchestrator.py` | Der dokumentierte Ambient-Degradationspfad ist tot, sobald core_complete False ist - ein transienter IO-Fehler wird zum harten Abbruch | BASIS-03 |
| `src/mutmut_win/orchestrator.py` | SpawnPoolExecutor belegt Job-Handle und drei IPC-Queues im Konstruktor, aber shutdown() liegt ausserhalb des try-Blocks | PROC-05 |
| `src/mutmut_win/orchestrator.py` | Bei leerem --mutant-names-Treffer werden keine 'skipped'-Zeilen geschrieben | ORCH-05 |
| `src/mutmut_win/orchestrator.py` | `_split_no_test_tasks`: Docstring nennt nur "Mapping existiert", Code fordert zusaetzlich ein nie gesetztes Authority-Bit - Status `no tests` hat keinen Produzenten | ORCH-01 |
| `src/mutmut_win/process/executor.py` | Pool-Watchdog bricht den Lauf nach absoluten 60 s ab, obwohl Worker gesund sind — erstes Lebenszeichen kommt erst nach Popen | EXEC-01 |
| `src/mutmut_win/process/executor.py` | Ein nach dem Sweep eintreffendes TaskStarted eines bereits abgehakten Workers blockiert die Aufgabe dauerhaft und entwaffnet den Idle-Watchdog | EXEC-03 |
| `src/mutmut_win/process/executor.py` | Poolweite 60-s-Idle-Toleranz kann einen gesunden Lauf abbrechen, weil TaskStarted erst nach dem kompletten Task-Setup gesendet wird | EXEC-04 |
| `src/mutmut_win/process/executor.py` | Idle-Collapse-Watchdog sieht Worker nicht, die im Task-Setup stecken, und bricht gesunde Läufe ab | EXEC-01 |
| `src/mutmut_win/process/executor.py` | Synthetisiertes Dead-Worker-Verdikt wird als vollwertiges Fachurteil persistiert; der Lauf endet als 'completed' mit voller Export-Autoritaet | EXEC-01 |
| `src/mutmut_win/process/generation_supervisor.py` | _assign_windows_job ist toter Code und haelt den nicht-atomaren assign-after-spawn-Pfad offen | PROC-06 |
| `src/mutmut_win/process/generation_supervisor.py` | Abort-Diagnostik und Fallback-Kill sehen nur den Schnappschuss VOR dem Kill - waehrend des Aborts entstandene Prozesse bleiben unsichtbar | GS-03 |
| `src/mutmut_win/process/generation_supervisor.py` | Generation-Supervisor faehrt seinen ProcessPoolExecutor auf keinem Fehlerpfad herunter; der atexit-Hook von concurrent.futures blockiert dann den Prozessaustritt | GEN-01 |
| `src/mutmut_win/process/job_object.py` | close_job() prueft den CloseHandle-Rueckgabewert nicht - die einzige Kill-Primitive kann stumm fehlschlagen | PROC-02 |
| `src/mutmut_win/process/job_object.py` | close_job() ignoriert den Rueckgabewert von CloseHandle und meldet Containmenterfolg, den es nicht geprueft hat | JOB-01 |
| `src/mutmut_win/process/job_object.py` | close_job verwirft den CloseHandle-Rueckgabewert; ein fehlgeschlagener Kernel-Reap ist von einem erfolgreichen nicht unterscheidbar | JOB-01 |
| `src/mutmut_win/process/job_object.py` | `create_kill_on_close_job`: der gemeldete Win32-Fehlercode wird vom vorgelagerten CloseHandle ueberschrieben | JOB-01 |
| `src/mutmut_win/process/loop_monitor.py` | take_samples_snapshot iteriert die deque, die der Monitor-Thread gleichzeitig befüllt — Timeout-Verdikt kippt auf 'suspicious' | MON-01 |
| `src/mutmut_win/process/output_capture.py` | BoundedOutputCapture.close() gilt als abgeschlossen, obwohl der Reader-Thread den Lese-Deskriptor erst später schliesst | CAP-01 |
| `src/mutmut_win/process/run_lock.py` | Nur 0,5 s Geduld fuer die Freigabe des Guard-Locks eines nachweislich toten Vorbesitzers | LOCK-01 |
| `src/mutmut_win/process/run_lock.py` | refresh_identity gibt bei Teilfehlschlag auch den bereits gehaltenen Pfad-Lock frei | RL-04 |
| `src/mutmut_win/process/worker.py` | Worker besitzt keinen Eltern-Liveness-Fallback und blockiert unbegrenzt in task_queue.get() | PROC-03 |
| `src/mutmut_win/process/worker.py` | _kill_proc_tree verwirft ein lebendes Job-Handle ersatzlos, sobald subprocess.Popen ersetzt wurde | PROC-04 |
| `src/mutmut_win/process/worker.py` | Per-Task-Deadline startet vor dem gesamten Task-Setup und wird auf 1 ms geklemmt — verbrauchtes Setup wird als TIMEOUT-Verdikt gewertet | WRK-01 |
| `src/mutmut_win/process/worker.py` | _kill_proc_tree gibt bei Nicht-Popen-Objekten das Job-Handle nicht frei, obwohl der Aufrufer es als konsumiert verbucht | WRK-06 |
| `src/mutmut_win/process/worker.py` | _process_task legt TemporaryDirectory und BoundedOutputCapture rund 100 Zeilen vor dem schuetzenden try an; jeder Setup-Fehler umgeht cleanup() und close() | WRK-01 |
| `src/mutmut_win/pytest_boundary.py` | pytest-Versionsparser der Boundary ist strenger als das Versions-Gate des Orchestrators | BOUND-01 |
| `src/mutmut_win/runner.py` | mutants/sitecustomize.py wird aus repr(set(...)) erzeugt und ist prozessuebergreifend nicht byte-reproduzierbar | ORCH-06 |
| `src/mutmut_win/runner.py` | Generiertes Stats-Plugin iteriert das global geteilte Hit-Set ohne Schutz gegen Hintergrund-Threads des Zielprojekts | STATS-01 |
| `src/mutmut_win/stats.py` | Staging-Digest bindet alles unter mutants/ inklusive Verzeichnis-mtimes, aber ini-addopts-Reportausgaben werden nicht umgeleitet | BASIS-05 |
| `src/mutmut_win/stats.py` | Path.cwd() ist der implizite Projektwurzel-Vertrag der gesamten Basis- und Staging-Pruefung | BASIS-09 |
| `src/mutmut_win/stats.py` | Sortierschluessel der Distributions-Basis ist nicht total — Digest faellt auf die nicht garantierte os.listdir-Reihenfolge zurueck | ORCH-ORD-01 |
| `src/mutmut_win/stats.py` | Zweite Stelle derselben Asymmetrie: _hash_project_import_core prunt projektinterne Import-Roots nicht gitignore-basiert | STATS-02 |
| `src/mutmut_win/test_mapping.py` | `match_mutant_names`: Docstring garantiert "each candidate appears at most once", die Implementierung dedupliziert nicht | TM-01 |
| `src/mutmut_win/trampoline.py` | Trampolin wirft bei unbekannter Mutant-ID einen nackten KeyError, ununterscheidbar von einem echten Kill | MUT-04 |
| `tests/integration/test_job_object_kill_on_close.py` | Das README-Versprechen 'if the parent dies, the kernel reaps every worker' ist durch keinen Test abgedeckt | PROC-07 |
| `tests/test_architecture.py` | 120-s-Budget fuer den cache-losen import-linter-Lauf, der im Releaselauf ebenfalls Coverage-Tracing erbt | TEST-02 |
| `tests/unit/test_hit_recording.py` | Absolute Import-Dauer-Assertion (< 1,0 s) in einem Unit-Test, der im Releaselauf unter Coverage-Tracing faehrt | TEST-01 |

---

## Kapitel K — Lücken dieser Erhebung

Was dieses Dokument **nicht** leistet, ausdrücklich benannt:

1. **Kein einziger Befund ist durch einen fehlschlagenden Test belegt.** Alle
   143 sind durch Quelltextlektüre begründet — von mir für Kapitel A und B, von
   je zwei unabhängigen Agenten für den Rest. Der nächste Schritt für jeden
   Befund, der angefasst wird, ist ein Test, der ihn *zuerst* rot zeigt.
2. **Zwei Bereiche sind nicht abgedeckt**: die Agenten `GEN-01` und `CLI-05`
   sind an Parse-Fehlern gescheitert. Ihre Zuständigkeiten (Mutantengenerierung
   bzw. ein CLI-Ausschnitt) haben nur die Abdeckung durch die übrigen Spuren.
3. **Keine Fehlerrate gemessen.** „Sporadisch" ist keine Zahl. Ohne N
   Wiederholungen desselben Trees und eine Fehlerquote pro Test lässt sich nicht
   sagen, ob eine Änderung das Problem behoben oder nur verschoben hat.
4. **Keine Fremdprojekt-Validierung.** Alle Beobachtungen stammen von mutmut-win
   auf sich selbst. Gerade die Befunde C1, E1, F1 und F5 treffen aber
   Fremdprojekte härter als dieses Repository.
5. **Die Widerlegungen sind nicht von mir nachgeprüft.** Kapitel J beruht auf
   Agentenurteil.
6. **Schwereeinstufungen sind Agentenurteil**, außer bei den in Kapitel A und B
   ausführlich behandelten Befunden.

---

## Empfohlene Reihenfolge

Ein Vorschlag, kein Beschluss.

**Schritt 0 — Diagnose trennen (Stunden, nicht Tage).**
`complete=False` und `!= expected` in zwei verschiedene Fehlermeldungen
trennen (`orchestrator.py:122`). Das behebt keinen einzigen Defekt, aber es
macht ab sofort jede Fehlermeldung wahr. Ohne diesen Schritt untersucht man
weiter Phantome.

**Schritt 1 — Fehlerrate messen.**
Denselben Tree N-mal laufen lassen, Fehlschläge pro Test zählen. Erst danach
existiert eine Baseline, gegen die sich jede weitere Änderung beweisen lässt.

**Schritt 2 — Kapitel B abarbeiten**, in dieser Reihenfolge: Wurzel (Retry auf
der Leseseite), dann BC-002 (Sweep vor den Snapshot), dann BC-004
(Guard-Publikation aus dem Task-Pfad), dann `st_nlink` aus dem Fingerprint, dann
der Arbeitsverzeichnis-Schnitt.

**Schritt 3 — Kapitel A abarbeiten.** Ab hier sind Fixes verifizierbar, weil
Schritt 2 den Unterschied zwischen „rot" und „echt rot" hergestellt hat.

**Schritt 4 — C1, E1, F1, F5** vor jeder Auslieferung an Teams: das sind die
vier Befunde, die ein Fremdprojekt am ehesten sofort treffen.

---

## Anhang — Vollständiger Index

Alle 143 bestätigten Befunde, sortiert nach Schwere, dann Datei, dann Zeile. Die
Spalte *Herkunft* nennt die Kennung des Review-Agenten; diese Kennungen sind
über verschiedene Prüfspuren hinweg **nicht eindeutig** — mehrfach auftretende
Kennungen wie `ORCH-02` oder `EXEC-02` bezeichnen unabhängige Befunde
verschiedener Agenten. Eindeutig ist allein die Spalte `BC-nnn`.

Die Befundtexte im Anhang sind unverändert aus dem Review übernommen und
verwenden durchgehend ASCII-Transliteration (`ae`, `oe`, `ue`).

| # | Schwere | Kategorie | Ort | Befund | Herkunft |
|---|---|---|---|---|---|
| BC-001 | kritisch | race | `src/mutmut_win/orchestrator.py:302` | Doppelter Basis-Snapshot macht einen einseitigen transienten Lesefehler zum harten Laufabbruch | ORCH-03 |
| BC-002 | kritisch | toctou | `src/mutmut_win/process/executor.py:173` | start() veraendert den bereits fingerprinteten mutants/-Baum und laesst den kompletten Lauf nachtraeglich als Stagingdrift durchfallen | EXEC-01 |
| BC-003 | kritisch | error-handling | `src/mutmut_win/process/worker.py:478` | Proof-Publikation im generierten Guard-Plugin ist nicht fehlerbehandelt: transiente Publikationsstoerung wird zu Exit 3 und damit zu einem falschen 'killed' | WRK-02 |
| BC-004 | kritisch | toctou | `src/mutmut_win/process/worker.py:846` | Republikation des unveraenderlichen Phase-Guard-Plugins in den eingefrorenen Staging-Baum bei jeder einzelnen Task | WRK-01 |
| BC-005 | kritisch | error-handling | `src/mutmut_win/stats.py:458` | Staging-Validierung meldet voruebergehend unlesbare Dateien als Byte-Aenderung | ORCH-02 |
| BC-006 | hoch | windows | `src/mutmut_win/atomic_file.py:53` | Identitaets-Tripwire ohne Null-Guard: Windows liefert st_dev=0/st_ino=0 fuer nicht oeffenbare Pfade | WIN-01 |
| BC-007 | hoch | toctou | `src/mutmut_win/atomic_file.py:172` | Publikations-Siblings liegen unter einem im Staging-Fingerprint nicht gefilterten Namen im gemessenen Baum | ATOM-03 |
| BC-008 | hoch | race | `src/mutmut_win/atomic_file.py:295` | ensure_atomic_bytes-Vorprüfung ohne Retry bricht den gesamten Lauf bei transientem Windows-Filterdriver-Fehler ab | ATOM-01 |
| BC-009 | hoch | race | `src/mutmut_win/atomic_file.py:483` | ensure_atomic_bytes umgeht die Parent-Capture-Retrykette und faellt bei transientem resolve-Fehler sofort durch | ATOM-01 |
| BC-010 | hoch | toctou | `src/mutmut_win/atomic_file.py:483` | Idempotenter Guard-Publish schreibt bei transientem Vorprüfungs-False neu und zerstört den Staging-Fingerprint | STAGE-01 |
| BC-011 | hoch | race | `src/mutmut_win/atomic_file.py:546` | create_exclusive_random_bytes prueft die als unzuverlaessig dokumentierte handle-abgeleitete st_nlink - ohne Retry | ATOM-02 |
| BC-012 | hoch | resource-leak | `src/mutmut_win/browser.py:597` | TUI-Browser startet einen kompletten Mutationslauf als uneingehegten Kindprozess ohne Job Object | PROC-01 |
| BC-013 | hoch | windows | `src/mutmut_win/cli.py:151` | --force-Cleanup ignoriert Readonly-Attribute und scheitert dauerhaft mit falscher Diagnose | CLI-01 |
| BC-014 | hoch | api-contract | `src/mutmut_win/cli.py:517` | --do-not-mutate verengt das Mutantenuniversum, umgeht aber die --min-score-Subset-Sperre und die is_full_run-Kennzeichnung | CLI-03 |
| BC-015 | hoch | correctness | `src/mutmut_win/cli.py:604` | --since-commit vergleicht repo-root-relative git-Pfade gegen das CWD und endet still mit Exit 0 | CLI-02 |
| BC-016 | hoch | nondeterminism | `src/mutmut_win/config.py:438` | also_copy erhaelt Default-Eintraege aus unsortiertem glob() und wird woertlich in den Run-Basis-Digest gehasht | ORCH-ORD-02 |
| BC-017 | hoch | error-handling | `src/mutmut_win/config.py:539` | Wertfehler in setup.cfg [mutmut] umgehen die ConfigError-Vertragsschicht und erscheinen als roher pydantic-Traceback | CFG-01 |
| BC-018 | hoch | error-handling | `src/mutmut_win/db.py:534` | _raise_database_error stuft Umgebungsfehler (readonly, I/O-Fehler, Platte voll, cantopen) als Cache-Korruption ein und fordert zum Loeschen des Ergebnisverzeichnisses auf | DB-02 |
| BC-019 | hoch | performance | `src/mutmut_win/db.py:1647` | Jedes persistierte Verdict kostet 2 SQLite-Verbindungen, einen kompletten Schemadurchlauf und 15 vollstaendige Dateisystem-Baumvalidierungen (gemessen 35-112 ms, serialisiert in der Orchestrator-Event-Loop) | DB-01 |
| BC-020 | hoch | windows | `src/mutmut_win/file_setup.py:154` | Jeder Reparse-Punkt gilt als Link - Deduplizierungs- und Cloud-Volumes verlieren den kompletten Quellbaum | WIN-03 |
| BC-021 | hoch | correctness | `src/mutmut_win/file_setup.py:1201` | Automatischer Spiegel prueft .gitignore mit descend(), die Mutationssuche mit descend_forced() — git-ignorierte Mutationswurzeln werden mutiert, aber nie gestagt | FS-02 |
| BC-022 | hoch | correctness | `src/mutmut_win/file_setup.py:1487` | _sync_tree loescht bei jedem Lauf alle *.meta-Sidecars unterhalb konfigurierter Spiegel | FS-01 |
| BC-023 | hoch | correctness | `src/mutmut_win/gitignore_boundary.py:92` | .gitignore mit UTF-8-BOM verliert ihr erstes Muster | GIT-01 |
| BC-024 | hoch | correctness | `src/mutmut_win/mutation.py:304` | Klassen-Stack laeuft aus dem Tritt: qualifizierte do_not_mutate_patterns greifen falsch oder gar nicht | MUT-01 |
| BC-025 | hoch | correctness | `src/mutmut_win/mutation.py:973` | Mutiertes Modul scheitert mit NameError beim Import, wenn eine Methode im eigenen Klassenkoerper aufgerufen wird | MUT-02 |
| BC-026 | hoch | correctness | `src/mutmut_win/node_mutation.py:46` | Integer-Literal mit >4300 Dezimalstellen bricht den gesamten Lauf ab (int->str-Limit) | NUM-01 |
| BC-027 | hoch | correctness | `src/mutmut_win/node_mutation.py:69` | CRCR verliert die Klammern des Originalliterals und erzeugt einen SyntaxError-Mutanten — die ganze Datei faellt aus der Mutation | NM-01 |
| BC-028 | hoch | toctou | `src/mutmut_win/orchestrator.py:302` | Basis-Fingerprint ist die einzige Phase ohne Zeitbudget; sein doppelter Durchlauf oeffnet ein TOCTOU-Fenster, das mit der Umgebungsgroesse waechst | ORCH-02 |
| BC-029 | hoch | toctou | `src/mutmut_win/orchestrator.py:302` | Nicht lesbare Datei wird als geaenderte Datei gewertet: einmaliger OSError im Prelude bricht den Lauf hart ab | ORCH-02 |
| BC-030 | hoch | performance | `src/mutmut_win/orchestrator.py:350` | Die Ausfuehrungsbasis wird pro Lauf fuenfmal vollstaendig ueber Projektbaum und alle installierten Distributionen berechnet | ORCH-05 |
| BC-031 | hoch | error-handling | `src/mutmut_win/orchestrator.py:453` | Transienter Lesefehler am Laufende verwirft einen vollstaendig gerechneten Lauf als 'failed' | ORCH-03 |
| BC-032 | hoch | correctness | `src/mutmut_win/orchestrator.py:1492` | Gemessener Startup-Floor wird bei 60 s absolut gedeckelt und einprozessig gemessen, aber auf cpu_count() parallele Worker angewandt | ORCH-01 |
| BC-033 | hoch | phase-order | `src/mutmut_win/orchestrator.py:1689` | Type-Checker laeuft mit cwd=mutants/ ohne Cache-Umleitung und zerstoert damit die eigene Staging-Evidenz | ORCH-01 |
| BC-034 | hoch | toctou | `src/mutmut_win/orchestrator.py:1689` | os.chdir in mutants/ lässt den Type-Checker seinen Cache in das eingefrorene Staging schreiben | TYPECHK-01 |
| BC-035 | hoch | toctou | `src/mutmut_win/process/executor.py:173` | Executor loescht nach dem Staging-Snapshot Dateien aus dem gehashten Satz | ORCH-01 |
| BC-036 | hoch | toctou | `src/mutmut_win/process/executor.py:173` | executor.start loescht Dateien in mutants/, nachdem der Staging-Fingerabdruck inklusive Verzeichnis-Zeitstempeln genommen wurde | EXEC-02 |
| BC-037 | hoch | race | `src/mutmut_win/process/executor.py:366` | Liveness-Sweep erklaert sauber beendete Worker fuer abgestuerzt und ersetzt ein korrektes Mutantenverdikt durch exit 35 | EXEC-02 |
| BC-038 | hoch | correctness | `src/mutmut_win/process/generation_supervisor.py:501` | Fester 15-s-Join verwirft eine vollstaendig erfolgreiche Mutantengenerierung | GS-01 |
| BC-039 | hoch | correctness | `src/mutmut_win/process/run_lock.py:717` | Datenbank-Lock-Domaene haengt an tempfile.gettempdir() und ist damit nicht global | RL-03 |
| BC-040 | hoch | nondeterminism | `src/mutmut_win/process/worker.py:1072` | PYTHONHASHSEED wird fuer keine pytest-Phase gepinnt und ist nicht Teil der Run-Basis | ORCH-ORD-03 |
| BC-041 | hoch | correctness | `src/mutmut_win/process/worker.py:1196` | Das Task-Wallclock-Budget deckt das komplette Worker-Setup mit ab; pytest bekommt keine garantierte Mindestlaufzeit | WRK-03 |
| BC-042 | hoch | correctness | `src/mutmut_win/regex_mutation.py:66` | Feste Erzeugungsreihenfolge plus 12er-Cap verhungert Anker-, Klassen- und Gruppen-Mutatoren bei typischen Patterns | RX-01 |
| BC-043 | hoch | correctness | `src/mutmut_win/regex_mutation.py:396` | re.VERBOSE ist der Regex-Engine unbekannt: Kommentartext wird mutiert (garantierte Aequivalente) und eine Klammer im Kommentar loescht die gesamte Mutationsflaeche | RX-02 |
| BC-044 | hoch | api-contract | `src/mutmut_win/runner.py:368` | Der byte- und metadatengenau gehashte Staging-Baum ist zugleich das Arbeitsverzeichnis beliebiger Nutzertests | ORCH-04 |
| BC-045 | hoch | correctness | `src/mutmut_win/runner.py:495` | collect_tests liefert still eine leere Testliste, sobald die effektive Test-Case-Verbosity nicht exakt -1 ist | RUN-01 |
| BC-046 | hoch | race | `src/mutmut_win/stats.py:448` | In-Run-Staging-Snapshot behandelt die unter Windows nachweislich instabile st_nlink-Beobachtung als Beweis fuer Staging-Drift und bricht den Lauf hart ab | STAGE-01 |
| BC-047 | hoch | toctou | `src/mutmut_win/stats.py:457` | Transiente I/O-Fehler werden in den Fingerprint einkodiert und als 'Eingaben haben sich geändert' fehlinterpretiert | BASIS-01 |
| BC-048 | hoch | correctness | `src/mutmut_win/stats.py:671` | Staging-Evidenz bindet Verzeichnis-Zeitstempel und ALLE Dateien in mutants/ — legitime Test-Nebeneffekte im Arbeitsverzeichnis brechen den Lauf ab | STATS-03 |
| BC-049 | hoch | race | `src/mutmut_win/stats.py:680` | Staging-Fingerprint bindet st_nlink, obwohl das Projekt transiente Windows-Fehlmeldungen selbst dokumentiert | STAG-01 |
| BC-050 | hoch | correctness | `src/mutmut_win/stats.py:846` | core-Digest bindet globale sys.path-Indizes und Fehler fremder Eintraege - ambiente Aenderungen werden als Projektaenderung fehlklassifiziert | BASIS-01 |
| BC-051 | hoch | correctness | `src/mutmut_win/stats.py:874` | _hash_project_import_core laeuft als einziger Baumlauf ohne GitignoreBoundary - git-ignorierte, volatile Dateien landen im harten core-Digest | BASIS-02 |
| BC-052 | hoch | correctness | `src/mutmut_win/stats.py:1048` | Projektinternes .venv wird durch die Gitignore-Grenze vollstaendig aus dem Kontext-Digest gestrichen - sitecustomize.py und verwaiste .pth-Dateien invalidieren die Basis nie | BASIS-04 |
| BC-053 | hoch | correctness | `src/mutmut_win/stats.py:1219` | Core-Digest bindet git-ignorierte Bytes des editierbaren Quellbaums, die der kombinierte Digest bewusst prunt | STATS-01 |
| BC-054 | hoch | api-contract | `src/mutmut_win/type_checking.py:388` | mypy-Report-Parser scheitert an mypys Summary-Zeile — Typpruefer-Filter bricht jeden Lauf ab | TC-01 |
| BC-055 | hoch | test-flakiness | `tests/integration/test_e2e_pipeline_validation.py:57` | 180-s-Subprozesslimit der E2E-Pipeline widerspricht der dokumentierten Coverage-Verdopplung der Schwesterdatei (300 s) | TIME-01 |
| BC-056 | hoch | test-flakiness | `tests/integration/test_e2e_pipeline_validation.py:211` | E2E-Snapshot-Test macht sich rot an genau den Verdikten, die der Produktionscode als umgebungsabhaengig deklariert | TIME-02 |
| BC-057 | mittel | correctness | `src/mutmut_win/atomic_file.py:155` | _dump_sibling_diagnostics schreibt symlinkfolgend an einen vorhersagbaren Namen im gemeinsamen Temp-Verzeichnis | ATOM-06 |
| BC-058 | mittel | windows | `src/mutmut_win/atomic_file.py:172` | Atomare Publikation verbraucht 52 Zeichen MAX_PATH-Budget ohne jede Langpfad-Behandlung | WIN-07 |
| BC-059 | mittel | toctou | `src/mutmut_win/atomic_file.py:204` | _open_random_sibling schliesst denselben fd-Wert zweimal, wenn die Sibling-Validierung erschoepft; dazwischen wird eine Diagnosedatei geoeffnet | ATOM-01 |
| BC-060 | mittel | resource-leak | `src/mutmut_win/atomic_file.py:221` | Doppeltes os.close(fd) auf dem Erschoepfungspfad von _open_random_sibling kann einen fremden Deskriptor schliessen | ATOM-05 |
| BC-061 | mittel | performance | `src/mutmut_win/atomic_file.py:428` | _capture_parent_identity wiederholt auch permanente Ablehnungen und stallt 16,1 s pro Schreibvorgang | ATOM-04 |
| BC-062 | mittel | resource-leak | `src/mutmut_win/atomic_file.py:585` | Jede Staging-Datei wird vollstaendig in den Speicher gelesen | COPY-01 |
| BC-063 | mittel | performance | `src/mutmut_win/basis_diagnostics.py:355` | register_input_root ist pro gehashter Datei quadratisch in der Zahl der Eingabeverzeichnisse | DIAG-01 |
| BC-064 | mittel | correctness | `src/mutmut_win/browser.py:161` | DB-only-Diff-Fallback nimmt den ersten rglob-Treffer und kann den Mutanten der falschen Datei rendern | ORCH-ORD-04 |
| BC-065 | mittel | correctness | `src/mutmut_win/browser.py:621` | action_retest_module testet bei Mutanten aus einer Paket-__init__.py den gesamten Paketbaum nach | BROW-01 |
| BC-066 | mittel | correctness | `src/mutmut_win/cli.py:611` | --since-commit macht Testdateien ausserhalb der konfigurierten tests_dir-Unterbaeume zu Mutationszielen | CLI-01 |
| BC-067 | mittel | correctness | `src/mutmut_win/code_coverage.py:57` | Coverage-Gating vergleicht nicht aufgeloeste Pfade gegen coverage.py-Schluessel (realpath) — Fehlabbruch mit irrefuehrender Meldung | CV-01 |
| BC-068 | mittel | correctness | `src/mutmut_win/config.py:469` | ConfigParser-[DEFAULT]-Eintraege werden still als [mutmut]-Konfiguration uebernommen und erzeugen falsche Unknown-Option-Warnungen | CFG-02 |
| BC-069 | mittel | api-contract | `src/mutmut_win/constants.py:159` | WORKSPACE_EXCLUDED_DIR_NAMES enthaelt hartcodierte Verzeichnisnamen des mutmut-win-Repos und schliesst gleichnamige Fremdprojektverzeichnisse unwiderruflich aus | CONST-01 |
| BC-070 | mittel | windows | `src/mutmut_win/db.py:384` | _inspect_cache_leaf toleriert transiente Windows-Zustaende nur fuer Sidecars; fuer das Datenbank-Leaf fuehrt derselbe Zustand ohne Wiederholung zur Fehldiagnose 'is a hardlink (0 links)' | DB-07 |
| BC-071 | mittel | race | `src/mutmut_win/db.py:554` | Kein busy_timeout, kein WAL und kein Retry: jede SQLite-Sperrkonkurrenz beendet nach 5 Sekunden den gesamten Lauf | DB-04 |
| BC-072 | mittel | windows | `src/mutmut_win/file_setup.py:519` | str.casefold() als NTFS-Identitaetsschluessel erzeugt falsche Staging-Kollisionen | WIN-06 |
| BC-073 | mittel | toctou | `src/mutmut_win/file_setup.py:716` | _same_live_input verwechselt 'nicht ermittelbar' mit 'verschieden' und macht aus einer geloeschten Datei einen Laufabbruch | FS-03 |
| BC-074 | mittel | performance | `src/mutmut_win/file_setup.py:891` | validate_staging_namespace laeuft dreimal pro Lauf ueber den gesamten Projektbaum und ist O(automatische Eingaben x konfigurierte Wurzeln) | FS-04 |
| BC-075 | mittel | windows | `src/mutmut_win/file_setup.py:1071` | Staging-Kopie gibt nach 1,5 s Gesamtbackoff auf, obwohl der eigene Docstring Defender als Ursache benennt | FS-01 |
| BC-076 | mittel | windows | `src/mutmut_win/file_setup.py:1417` | Konfigurierter Kopierpfad besitzt die Junction-/Reparse-Abwehr des automatischen Pfads nicht; os.walk laeuft unter Windows in Junctions hinein | FS-05 |
| BC-077 | mittel | error-handling | `src/mutmut_win/file_setup.py:1454` | Typwechsel Datei<->Verzeichnis an einem konfigurierten Staging-Ziel wird nie versoehnt und bricht den Lauf mit FileExistsError bzw. OSError ab | FS-06 |
| BC-078 | mittel | correctness | `src/mutmut_win/file_setup.py:2232` | Nicht kompilierbarer oder nicht parsebarer Mutantensatz verschwindet still aus dem Nenner, ohne dem Lauf die Autoritaet zu entziehen | GEN-01 |
| BC-079 | mittel | api-contract | `src/mutmut_win/gitignore_boundary.py:70` | Unlesbare oder von pathspec abgelehnte .gitignore-Regeln erweitern still den gehashten und gestageten Baum, ohne die Vollstaendigkeitsmeldung zu senken | GITIGN-01 |
| BC-080 | mittel | windows | `src/mutmut_win/gitignore_boundary.py:91` | UTF-8-BOM in .gitignore entwertet stillschweigend die erste Regel | WIN-05 |
| BC-081 | mittel | windows | `src/mutmut_win/gitignore_boundary.py:107` | gitignore-Matching ist case-sensitiv, Git unter Windows nicht - ignorierte Baeume landen im Basis-Hash | WIN-04 |
| BC-082 | mittel | correctness | `src/mutmut_win/gitignore_boundary.py:228` | GitignoreBoundary._excludes verliert Gits Verzeichnismarker-Praezedenz — ignorierte Teilbaeume werden gelaufen, gestaged und gehasht | GI-01 |
| BC-083 | mittel | correctness | `src/mutmut_win/hit_recording.py:68` | max_stack_depth verbraucht das Budget mit mutmut-eigenen Frames — Werte 1..4 verwerfen stillschweigend jeden Stats-Hit | HR-01 |
| BC-084 | mittel | windows | `src/mutmut_win/mutant_diff.py:126` | resolve_mutant ist unter Windows case-insensitiv: falsche Mehrdeutigkeit bzw. stilles Anwenden eines nicht benannten Mutanten | MD-01 |
| BC-085 | mittel | api-contract | `src/mutmut_win/mutation.py:378` | len/isinstance werden nur nach Namen erkannt und loeschen den kompletten Argument-Teilbaum | MUT-03 |
| BC-086 | mittel | correctness | `src/mutmut_win/node_mutation.py:72` | CRCR-Mutant unter ** traegt nicht den beabsichtigten Konstantenwert (-1 ** 2 parst als -(1 ** 2)) | NM-02 |
| BC-087 | mittel | api-contract | `src/mutmut_win/node_mutation.py:506` | operator_regex prueft nicht, ob args[0] positional ist — Keyword-Argumente werden als Regex mutiert, der echte pattern= bleibt unmutiert | NM-03 |
| BC-088 | mittel | error-handling | `src/mutmut_win/orchestrator.py:122` | _validate_staging_unchanged faltet 'Snapshot unvollstaendig' und 'echte Drift' in eine einzige, falsch attribuierende Fehlermeldung | STAGE-02 |
| BC-089 | mittel | api-contract | `src/mutmut_win/orchestrator.py:750` | Forced-Fail-Gate prueft nur den globalen fail-Sentinel, nicht die namensbasierte Mutantenauswahl | ORCH-04 |
| BC-090 | mittel | resource-leak | `src/mutmut_win/process/executor.py:99` | SpawnPoolExecutor belegt Job-Object-Handle und drei Multiprocessing-Queues in __init__, ohne dass ein finally, __exit__ oder __del__ sie auf dem Fehlerpfad freigibt | EXEC-01 |
| BC-091 | mittel | correctness | `src/mutmut_win/process/executor.py:172` | Der Pool-Start loescht Worker-Altlasten aus mutants/ nachdem der Staging-Evidenz-Snapshot genommen wurde | WRK-05 |
| BC-092 | mittel | correctness | `src/mutmut_win/process/executor.py:173` | Executor loescht Altartefakte innerhalb des bereits eingefrorenen Staging-Baums | STAG-02 |
| BC-093 | mittel | toctou | `src/mutmut_win/process/executor.py:326` | TOCTOU zwischen queue.Empty und worker.is_alive(): ein echtes, kurz danach eintreffendes Verdikt wird zugunsten des fabrizierten verworfen | EXEC-02 |
| BC-094 | mittel | toctou | `src/mutmut_win/process/generation_supervisor.py:295` | Der No-Progress-Deadline begrenzt nur wait(), nicht das nachfolgende recv() - der Parent kann unbegrenzt blockieren | GS-02 |
| BC-095 | mittel | resource-leak | `src/mutmut_win/process/output_capture.py:89` | BoundedOutputCapture.close() laesst bei einem ueberlebenden Writer Deskriptor und Drain-Thread dauerhaft zurueck | OC-01 |
| BC-096 | mittel | race | `src/mutmut_win/process/run_lock.py:267` | Priming-Schreibzugriff in _open_guard kollidiert mit dem mandatorischen Byte-Range-Lock eines Konkurrenten | RL-02 |
| BC-097 | mittel | error-handling | `src/mutmut_win/process/run_lock.py:486` | AtomicReplaceError entkommt WorkspaceRunLock.acquire() als roher PermissionError und umgeht die Domaenen-Fehlerbehandlung | RL-01 |
| BC-098 | mittel | correctness | `src/mutmut_win/process/worker.py:470` | xfail- und Laufzeit-Skip-Reports publizieren keinen Ausfuehrungs-Proof, obwohl der Testkoerper lief | WRK-04 |
| BC-099 | mittel | error-handling | `src/mutmut_win/process/worker.py:988` | Nur Containment- und Boundary-Fehler gelten als fatal; jede andere Umgebungsstoerung im Worker wird zum persistierten Mutantenurteil 'suspicious' | WRK-01 |
| BC-100 | mittel | correctness | `src/mutmut_win/process/worker.py:1557` | _popen_contained uebergibt den synthetischen PID eines Popen-Test-Doubles an OpenProcess/AssignProcessToJobObject - genau die Invariante, die _kill_proc_tree schuetzt | POPEN-01 |
| BC-101 | mittel | api-contract | `src/mutmut_win/pytest_boundary.py:178` | Absolute, projektinterne tests_dir-Eintraege verschieben die pytest-Konfigurationsgrenze in den Staging-Spiegel, waehrend pytest den Live-Baum sammelt | PB-01 |
| BC-102 | mittel | correctness | `src/mutmut_win/runner.py:450` | collect_tests ohne Staging vererbt die Elternumgebung: PYTEST_ADDOPTS wirkt doppelt und die Cache-Isolation entfaellt komplett | RUN-03 |
| BC-103 | mittel | correctness | `src/mutmut_win/runner.py:884` | Stats-Plugin erfasst Dauern nur fuer die call-Phase; niemals ausgefuehrte Tests erzwingen bei jedem Lauf eine vollstaendige Stats-Neuerhebung | RUN-02 |
| BC-104 | mittel | nondeterminism | `src/mutmut_win/runner.py:942` | Generiertes sitecustomize.py enthaelt repr() einer Menge — hashseed-abhaengige Bytes in der ausfuehrbaren Staging-Evidenz | ORCH-ORD-05 |
| BC-105 | mittel | correctness | `src/mutmut_win/stats.py:296` | Skip-Mengen decken nur Verzeichnisse ab - volatile Werkzeug-DATEIEN wie .coverage.<host>.<pid>.<rand> bleiben Basis-Eingabe | BASIS-08 |
| BC-106 | mittel | correctness | `src/mutmut_win/stats.py:339` | Projektbasis bindet st_mtime_ns/st_ctime_ns jeder Datei - bytegleiches Neuschreiben invalidiert einen abgeschlossenen Lauf | BASIS-06 |
| BC-107 | mittel | toctou | `src/mutmut_win/stats.py:343` | Cross-Run-Basis bindet volatile Windows-Dateiattribute; das Hashen selbst kann sie veraendern | STATS-05 |
| BC-108 | mittel | correctness | `src/mutmut_win/stats.py:487` | _editable_source_path dekodiert die PEP-610-URL doppelt und liefert fuer Pfade mit literalem Prozentzeichen den falschen Quellbaum | STATS-04 |
| BC-109 | mittel | performance | `src/mutmut_win/stats.py:1150` | Distributionsbasis hasht jede Datei jeder Distribution ohne Groessen- oder Relevanzgrenze, und der Orchestrator fuehrt das pro Lauf zweimal aus | STATS-06 |
| BC-110 | mittel | performance | `src/mutmut_win/stats.py:1419` | core_seen startet leer - der gesamte Projektbaum wird pro Snapshot ein zweites Mal vollstaendig gelesen und vergroessert das Race-Fenster | BASIS-07 |
| BC-111 | mittel | api-contract | `src/mutmut_win/stats.py:1713` | `_run_stats_collection`: Docstring verspricht Rueckgabe des Caches bei Fehlschlag, Code liefert leere Stats - und die Meldung suggeriert das Gegenteil | STAT-01 |
| BC-112 | mittel | correctness | `src/mutmut_win/test_mapping.py:84` | Mutantenauswahl ist unter Windows case-insensitiv - apply kann den falschen Mutanten schreiben | NAME-01 |
| BC-113 | mittel | api-contract | `src/mutmut_win/type_checking.py:27` | Typpruefer-Budget ist als einziges Phasenbudget hartkodiert und nicht konfigurierbar | TYPE-01 |
| BC-114 | mittel | test-flakiness | `tests/integration/test_generation_supervisor.py:253` | Lastempfindliche Wanduhr-Assertions um zwei verschachtelte kalte Windows-spawns im Generation-Supervisor-Test | GEN-01 |
| BC-115 | niedrig | error-handling | `src/mutmut_win/basis_diagnostics.py:338` | Jeder Publikationsfehler verwirft den kompletten Diagnosereport und meldet nur den Exception-Typnamen | DIAG-03 |
| BC-116 | niedrig | error-handling | `src/mutmut_win/browser.py:164` | Fallback-Scan bricht bei nicht-UTF-8-kodierten Dateien im Staging-Baum ab (UnicodeDecodeError ist kein OSError) | BROW-04 |
| BC-117 | niedrig | race | `src/mutmut_win/browser.py:563` | Fehlerpfad des Diff-Ladethreads prüft _loading_id nicht — veralteter Fehler überschreibt den Diff des aktuell markierten Mutanten | BROW-02 |
| BC-118 | niedrig | error-handling | `src/mutmut_win/browser.py:564` | Diff-Ladethread wirft nach App-Ende eine unbehandelte RuntimeError aus call_from_thread | BROW-03 |
| BC-119 | niedrig | error-handling | `src/mutmut_win/cli.py:800` | --dry-run --min-score scheitert mit der Fehlmeldung 'Execution basis incomplete' statt als Optionskonflikt abgelehnt zu werden | CLI-06 |
| BC-120 | niedrig | correctness | `src/mutmut_win/cli.py:1045` | show schreibt die Nichttreffer-Prosa auf stdout und verletzt damit den eigenen Patch-Stream-Vertrag | CLI-05 |
| BC-121 | niedrig | correctness | `src/mutmut_win/cli.py:1107` | apply meldet das Glob-Muster statt des tatsaechlich angewandten Mutanten | CLI-04 |
| BC-122 | niedrig | error-handling | `src/mutmut_win/cli.py:1357` | export-cicd-stats wirft einen rohen OSError, wenn mutants/ fehlt | CLI-02 |
| BC-123 | niedrig | api-contract | `src/mutmut_win/code_coverage.py:103` | `code_coverage`-Moduldocstring beschreibt den Coverage-Datenpfad innerhalb von `mutants/`, die Implementierung schreibt bewusst ausserhalb | CCOV-01 |
| BC-124 | niedrig | correctness | `src/mutmut_win/config.py:88` | guess_paths_to_mutate kann den leeren Pfad als Mutationswurzel zurueckgeben | CFG-03 |
| BC-125 | niedrig | correctness | `src/mutmut_win/config.py:297` | mutation_profile akzeptiert einen TOML-Boolean still als Profile.ADVANCED | CFG-04 |
| BC-126 | niedrig | api-contract | `src/mutmut_win/db.py:626` | Die Schreibgrenze ist permissiver als die Lesegrenze: _prepare_result validiert mutant_name ueberhaupt nicht, waehrend load_results jeden leeren oder surrogatbehafteten Namen als Cache-Korruption meldet | DB-05 |
| BC-127 | niedrig | correctness | `src/mutmut_win/db.py:1785` | delete_results_not_in ruft als einzige Funktion kein create_db und meldet auf einer schemalosen Datenbankdatei Korruption statt zu migrieren | DB-06 |
| BC-128 | niedrig | correctness | `src/mutmut_win/file_setup.py:1064` | `_copy_with_retry`: 6 statt `max_attempts` Versuche, letzter ohne Backoff, und der Docstring nennt eine Kopierfunktion, die nicht mehr benutzt wird | FSET-01 |
| BC-129 | niedrig | correctness | `src/mutmut_win/models.py:430` | read_owned_source_metadata gibt nicht normalisierte Hex-Digests zurueck, obwohl derselbe Validator sie im Schwesterpfad lowercased | MOD-01 |
| BC-130 | niedrig | api-contract | `src/mutmut_win/models.py:490` | `MutationRunResult.score`: dokumentierter Nenner enthaelt `unchecked` nicht, die Implementierung zieht ihn ab | MODELS-01 |
| BC-131 | niedrig | api-contract | `src/mutmut_win/mutant_diff.py:577` | `apply_mutant`: Raises-Docstring nennt mtime als Stale-Kriterium, der Code vergleicht SHA-256 | MDIF-01 |
| BC-132 | niedrig | api-contract | `src/mutmut_win/mutation.py:449` | Dekorierte Klassen werden vollstaendig von der Mutation ausgenommen, obwohl die Begruendung nur Funktionsdekoratoren betrifft | MUT-06 |
| BC-133 | niedrig | correctness | `src/mutmut_win/mutation.py:1061` | Pragma no mutate wird stumm ignoriert, wenn direkt Satzzeichen folgen | MUT-05 |
| BC-134 | niedrig | api-contract | `src/mutmut_win/orchestrator.py:1577` | `_apply_timeouts`/`_print_timeout_model`: dokumentierter "selected test time"-Budgetzweig ist unerreichbar, jede Task bekommt das Full-Suite-Budget | ORCH-02 |
| BC-135 | niedrig | resource-leak | `src/mutmut_win/process/output_capture.py:89` | BoundedOutputCapture.close() markiert sich auch nach abgelaufenem join als geschlossen; ein weiterschreibender entkommener Nachfahre laesst Thread und Lese-fd dauerhaft zurueck | CAP-01 |
| BC-136 | niedrig | api-contract | `src/mutmut_win/process/worker.py:853` | Default-Argumente schreiben Koordinationsdateien in den eigenen Hashsatz | ORCH-07 |
| BC-137 | niedrig | error-handling | `src/mutmut_win/process/worker.py:1236` | Der Neutralisierungspfad ueberschreibt die aufgezeichnete pytest-Ausgabe und macht den Befund undiagnostizierbar | WRK-07 |
| BC-138 | niedrig | correctness | `src/mutmut_win/regex_mutation.py:153` | Jede Mutation eines bereits lazy Quantifiers verwirft den ?-Marker; {n,m}? verliert die Greedy/Lazy-Dimension vollstaendig | RX-03 |
| BC-139 | niedrig | correctness | `src/mutmut_win/regex_mutation.py:271` | chr()-Grenzwerte in der Zeichenklassen-Mutation ungeschuetzt | RX-01 |
| BC-140 | niedrig | api-contract | `src/mutmut_win/stats.py:1646` | `collect_or_load_stats`: Docstring verspricht inkrementelle Neuerhebung "nur fuer neue Tests", Code erhebt immer die volle Suite | STAT-02 |
| BC-141 | niedrig | windows | `src/mutmut_win/test_mapping.py:84` | match_mutant_names matcht Mutantennamen unter Windows case-insensitiv (fnmatch statt fnmatchcase) | TM-01 |
| BC-142 | niedrig | error-handling | `src/mutmut_win/type_checking.py:414` | `run_type_checker`: dokumentierte Fehler-Taxonomie deckt strukturell abweichende, aber gueltige JSON-Reports nicht ab | TC-01 |
| BC-143 | niedrig | error-handling | `src/mutmut_win/type_checking.py:417` | parse_pyright_report stuerzt mit AttributeError ab, wenn ein unbekannter Checker ein JSON-Array liefert | TC-02 |
