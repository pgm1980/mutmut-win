# Auftrag an GLM-5.3: Sanierung und Bugfixing von mutmut-win v2.21.4

Du übernimmst die Implementierung und das Bugfixing für mutmut-win, den Windows-nativen Port von mutmut 3.5.0. Zwei unabhängige Reviews, zwei Kreuzreviews und ein abschließender Bericht haben die Defekte von Version 2.21.4 erhoben; daraus ist eine priorisierte Sanierungs-Roadmap entstanden. Deine Aufgabe: die belegten Defekte nach dieser Roadmap beheben – aber erst, nachdem du jeden einzelnen Befund selbst am Code nachgeprüft hast. Antworte und dokumentiere auf Deutsch.

## 1. Die wichtigste Regel: Nichts ungeprüft übernehmen

Der Review-Abschlussbericht, das Handover und alle zugrunde liegenden Einzel- und Kreuzberichte sind **Hypothesen über den Code, keine Tatsachen**. Du darfst sie auf keinen Fall als gegeben übernehmen. Gründe:

- Alle Reviews waren rein statisch. Kein Befund wurde dynamisch reproduziert oder durch einen Test belegt.
- Die Berichte haben sich gegenseitig widersprochen und korrigiert: Der erste Claude-Bericht führte 23 von 143 Einträgen zu Unrecht als Defekt und überzog die Schwere systematisch; Astras Kreuzreview verwarf 11 tatsächlich tragende Befunde. Auch das Abschlussurteil kann im Einzelfall falsch sein – seine Konfidenz steht je Befund in `CLAUDE_CROSSREVIEW.json`.
- Roadmap, Fix-Designs, Codeorte und Verifikationschecklisten im Handover sind Vorschläge von Review-Agenten am Stand `4d7f950`, keine geprüften Lösungen. Die Gegenprüfung hat 121 von 146 Designs nur mit Korrekturen und 1 (M-017) gar nicht akzeptiert.

Deshalb gilt ohne Ausnahme: **Jeden Befund prüfst du vor dem Fix selbst am Code, zwingend mit Serena.** Übernimm keine Zeilennummer, keinen Codepfad, keine Schwere, keine Fix-Skizze und keinen Testvorschlag ungeprüft. Ein Befund gilt für dich erst dann als bestätigt, wenn du ihn mit Serena nachvollzogen **und** mit einem Regressionstest belegt hast, der vor dem Fix aus dem richtigen Grund fehlschlägt.

Pflichtprotokoll je Mechanismusgruppe (`M-xxx`), vor jeder Codeänderung:

1. Lies die Detailkarte der Gruppe im Handover (Teil B) und das Einzelurteil in `CLAUDE_CROSSREVIEW.json`. Bei Urteil `teilweise` ist die korrigierte, engere Behauptung maßgeblich, nicht der Originaltitel.
2. Verorte die Kernstelle mit Serena: `get_symbols_overview` auf die Datei, `find_symbol` mit Rumpf für die Kernsymbole, `find_referencing_symbols` für alle Aufrufer. Serena zählt Zeilen ab 0, die Berichte ab 1. Kein Grep für Symbole.
3. Arbeite die Verifikationscheckliste der Karte vollständig ab und prüfe jedes Widerlegungskriterium ausdrücklich.
4. Verfolge den Auslöser bis zur beobachtbaren Folge: Ist der Pfad unter Windows und CPython 3.14.7 mit dokumentierter Konfiguration erreichbar? Fängt eine vorgelagerte Prüfung den Fall ab?
5. Schreibe den Regressionstest und lass ihn **vor** dem Fix laufen. Bleibt er grün oder schlägt er aus einem anderen Grund fehl, ist der Befund nicht belegt: nicht fixen, sondern melden.
6. Halte das Ergebnis fest: **bestätigt** (fixen), **abweichend** (Befund korrigieren, dann fixen, Abweichung melden), **widerlegt** (nicht fixen, Gegenbeweis mit `datei:zeile` melden) oder **nicht entscheidbar** (nicht fixen, fehlende Evidenz melden). Wird eine Gruppe widerlegt, die Vorbedingung anderer Gruppen ist, bewertest du die abhängigen neu (Prinzip P-21).

Zusätzlich:

- Befunde, die der Abschlussbericht widerlegt hat (Handover §8), und nicht prüfbare Befunde (Handover §9) setzt du nicht um. Kommst du bei eigener Prüfung zu einem anderen Ergebnis, meldest du es mit Beleg.
- Unverifizierte Zusatzbeobachtungen (Anhang des Handovers) fixt du nicht; melde sie als neue Kandidaten.
- Vertrags- und Verhaltensänderungen setzt du nur nach meiner dokumentierten Entscheidung um (Prinzip P-08 in Handover §7.1, z. B. M-003, M-008, M-016, M-036, M-041). Die Entscheidungsliste legst du mir in Phase R0 gesammelt vor.
- Achte auf ID-Kollisionen: Verworfene Kandidaten des ersten Claude-Berichts tragen Kürzel wie `ORCH-01` oder `PROC-05`, die wie Astra-IDs aussehen. Maßgeblich sind `BC-xxx`, die Astra-IDs aus `ASTRA_REVIEW.json` und die Gruppen-IDs `M-xxx`.

## 2. Ausgangslage

- Referenzstand aller Berichte: mutmut-win v2.21.4, Commit `4d7f950679e3f78d906b3b068e01a0ee5dcb5a4b`, Tag `v2.21.4`. Plattformvertrag: ausschließlich Windows, CPython genau 3.14.7.
- Berichte: `C:/claude_codex/mutmut-win-astra` (Review-Arbeitsbereich, detached HEAD auf `4d7f950`; die Berichtsdateien sind ungetrackt und werden nicht committet).
- Arbeitsrepository für die Fixes: das Projektrepository `C:/claude_codex/mutmut-win` (Origin des Review-Arbeitsbereichs, GitHub `pgm1980/mutmut-win`), sofern ich nichts anderes vorgebe. Prüfe zuerst, ob `main` noch auf `4d7f950` steht. Ist es weiter, verortest du jede Stelle per Symbolsuche neu und änderst nie blind nach Zeilennummer. Stelle sicher, dass Serena auf das Repository zeigt, in dem du änderst.
- Umfang: 146 Mechanismusgruppen mit tragendem Defekt – 9 high (P1), 56 medium (P2), 81 low (P3), kein critical. Die Roadmap ordnet sie in 51 Arbeitspakete und 5 Phasen: R0 Vorbereitung, R1 P1-Ergebnisintegrität, R2 P2, R3 P3, R4 Integration und Release-Abschluss. Jede Phase ist ein Sprint (Prinzip P-16).

## 3. Pflichtlektüre und wie du sie liest

1. `CLAUDE.md` im Arbeitsrepository – verbindliche Projektregeln (Werkzeuge, Gates, Git-Konventionen, `.sprint/state.md`).
2. `C:/claude_codex/mutmut-win-astra/HANDOVER_GLM-5.3.md` – das Handover. Es ist groß (10950 Zeilen) und hat zwei Teile:
   - **Teil A, Zeilen 1–673: vollständig lesen, bevor du beginnst.** Verifikationspflicht (§1), Referenzstand (§2), Dokumentenlandkarte (§3), Review-Historie (§4), Arbeitsprozess und Gates (§6), Roadmap mit Prinzipien P-01 bis P-21, Phasen und Arbeitspaketen (§7), nicht fixen / erst klären (§8, §9), Rückmeldeformat (§11), Navigationsindex (§13).
   - **Teil B, ab Zeile 675: je Arbeitspaket, bevor du es beginnst.** Beschreibung, Querschnittsmaßnahmen, Abnahme-Checkliste und die Detailkarten seiner Gruppen. Den Zeilenbereich jedes Pakets nennen §7.3 und §13; lies ihn in Abschnitten, nie die ganze Datei auf einmal.
3. `C:/claude_codex/mutmut-win-astra/Review-Abschlussbericht.md` – maßgebliche Übersicht der Befundlage: §1 (high-Gruppen), §4 (Fehler des ersten Claude-Berichts), §5 (Konfliktauflösungen), §7 (offene Fragen), §8 (Priorisierung).
4. `C:/claude_codex/mutmut-win-astra/CLAUDE_CROSSREVIEW.json` – Detaildaten je Befund: `konsolidierte_mechanismusgruppen`, `urteile_zu_claude`, `urteile_zu_astra` (Felder `korrigierte_behauptung`, `entscheidender_codepfad`, `quellbelege`, `verbleibende_unsicherheit`, `konfidenz`), `konflikte`, `offene_fragen`. Gezielt nach IDs lesen, nicht als Ganzes.
5. Nur zur Nachvollziehbarkeit (historisch, durch den Abschlussbericht bewertet): `ASTRA_CROSSREVIEW.md` / `.json`, `CLAUDE_REVIEW.json`, `CLAUDE_BUG_COLLECTION.md`, `ASTRA_REVIEW.json`, `ASTRA_BUG_COLLECTION.md`, `OVERLAP_CANDIDATES.json`.

Bei Widerspruch gilt: Abschlussbericht vor Astras Kreuzreview vor den Einzelberichten – über allem steht deine eigene Prüfung am Code.

## 4. Arbeitsweise

- Phasenweise, Arbeitspaket für Arbeitspaket, in der Reihenfolge der Roadmap (Handover §7.2 und §7.3). Voraussetzungen eines Pakets müssen gemergt sein; parallel nur Paare aus `parallelisierbar_mit`, Subagenten dann zwingend mit Worktree-Isolation (Prinzip P-12).
- Je Arbeitspaket: GitHub-Issue mit Checkliste je M-ID, Branch nach dem Vorschlag im Paket (`fix/<ISSUE-NR>-kurzbeschreibung` von `main`), `.sprint/state.md` nach Schema, Baseline-Gates vor der ersten Änderung.
- Je Gruppe: Pflichtprotokoll aus Abschnitt 1, dann TDD – Test rot aus dem richtigen Grund, minimaler Fix für genau die abschließende Behauptung, Test grün. Bei Parsing, Serialisierung und Validierung zusätzlich hypothesis. Ein Commit je Gruppe nach Conventional Commits, z. B. `fix(worker): … [M-008]` (Prinzip P-10).
- Je Mechanismusgruppe genau ein Fix, auch wenn mehrere Berichtseinträge denselben Defekt beschreiben (Prinzip P-09).
- Werkzeuge nach `CLAUDE.md`: Serena für jede Code-Navigation und für Refactorings (`rename_symbol`, `replace_symbol_body`); Context7 vor jeder Bibliotheks- oder stdlib-API, deren Verhalten ein Fix voraussetzt (Prinzip P-19); Chain-of-Thought-Server bei Designentscheidungen mit Alternativen (Prinzip P-20); `uv run` für alles.
- Projektvertrag wahren: fail-closed statt stiller Degradation, korrekte Fehlerkanäle und Exit-Codes, atomare Schreibpfade und Identitätsprüfungen, Staging- und Basis-Evidenz, Schichtenarchitektur (import-linter). Fixes verschieben Ergebnisse nur in die konservative Richtung (Prinzip P-07).
- Testhygiene: Tests, die `os`, `Path`, `time` oder `atomic_write_bytes` patchen, räumen vor Testende auf (Prinzip P-13). Für die zwei bekannten fragilen Tests gilt bis zu ihrer Sanierung die Sonderregel P-17.

## 5. Qualitätsgates (verbindlich, mit echter Ausgabe belegen)

Vor jedem Sync oder Gate `UV_PROJECT_ENVIRONMENT` und `HYPOTHESIS_STORAGE_DIRECTORY` auf absolute Verzeichnisse außerhalb des Checkouts setzen; im Checkout dürfen weder `.venv` noch Werkzeug-Caches noch `.hypothesis` entstehen.

```bash
uv run --no-sync ruff check --no-cache .
uv run --no-sync ruff format --no-cache --check .
uv run --no-sync mypy --no-incremental --cache-dir=nul src/
uv run --no-sync lint-imports --no-cache
uv run --no-sync pytest -p no:cacheprovider
uv run --no-sync mutmut-win run --paths-to-mutate <geänderte Module>
```

- Standard-Abnahme je Paket nach Prinzip P-04: Ruff und mypy strict ohne Befund, pytest vollständig grün, lint-imports grün, Mutation Score ≥ 80 % auf geändertem Code (Überlebende dokumentiert), kanonisches Semgrep-Gate bei jeder Änderung unter `src/`, an `pyproject.toml` oder `uv.lock`.
- Engine-Self-Mutation: Mutierst du Module der Werkzeugmaschinerie selbst (Staging, Fingerprint, Wrapper-Codegen, Worker, Trampolin), führe ein gezieltes Gate mit genau den Contract-Tests des Moduls als einzigem `--tests-dir` aus (Prinzip P-05).
- Phasengate je Sprint nach Prinzip P-16, zusätzlich `uv run --no-sync pip-audit` und die Benchmark-Vergleiche (Prinzip P-18). Vor einem Release: Coverage-Lauf und nativer Release-Wrapper laut `CLAUDE.md`.

## 6. Verbote

- Kein Fix ohne eigene Serena-Verifikation und ohne vorher roten Regressionstest.
- Keine Vertragsvariante ohne meine dokumentierte Entscheidung (P-08).
- Kein `# noqa` und kein `# type: ignore` ohne Begründung (bei `type: ignore` mit Error-Code).
- Keine Gates abschwächen, keine Tests löschen oder überspringen, keine import-linter-Contracts entfernen, kein `--no-verify`.
- Keine POSIX- oder Alt-Python-Zweige.
- Keine Änderungen an den Berichtsdateien; keine Berichtsdateien committen.
- Kein Merge nach `main` ohne meine Freigabe.
- Nichts als erledigt oder grün melden, was du nicht ausgeführt hast.

## 7. Rückmeldung je Arbeitspaket

1. Arbeitspaket, Branch, Commits.
2. Je Gruppe: Verifikationsergebnis (bestätigt / abweichend / widerlegt / nicht entscheidbar) mit Serena-Belegen (`datei:zeile`, Symbol, Aufrufer).
3. Je gefixter Gruppe: Regressionstest (rot vor dem Fix, grün danach) und der Fix in einem Satz.
4. Gate-Ergebnisse mit echter Ausgabe, Mutation Score je geändertem Modul.
5. Abweichungen vom Abschlussbericht oder vom Fix-Design mit Begründung; neu entdeckte Probleme getrennt und als unverifiziert.
6. Offene Punkte, Freigabe- und Entscheidungsbedarf.

## 8. Dein Einstieg

1. Lies `CLAUDE.md` und Teil A des Handovers vollständig. Bestätige mir kurz, dass du die Verifikationspflicht verstanden hast, und nenne Arbeitsrepository, Branch-Basis und deren HEAD.
2. Phase R0 (AP-00, Handover Teil B, Zeilen 679–710): Den Arbeitsstand gegen den Review-Stand 4d7f950 (Tag v2.21.4) abgleichen und die Baseline aller Gates festhalten. Gemeinsame Testinfrastruktur bereitstellen, die mehrere spätere APs brauchen. Entscheidungsbedarfe gesammelt an den Nutzer übergeben.
3. Phase R1 in dieser Reihenfolge: AP-00b, AP-01, AP-02, AP-03, AP-04, AP-05, AP-06, AP-07, AP-08, AP-08b. Beginne mit AP-00b „Belastbarer Grandchild-Containment-Test (Job Object) vor den Containment-Fixes“ (Gruppen M-140; Teil B, Zeilen 711–796). Prüfe zuerst **alle** Gruppen dieses Pakets mit Serena und melde mir die Verifikationsergebnisse, **bevor** du den ersten Fix committest. Danach arbeitest du nach dem Prozess oben weiter.
4. Nach jedem Arbeitspaket: Rückmeldung nach Abschnitt 7, dann auf meine Freigabe warten, bevor gemergt wird.

