# Release-Dossier: mutmut-win v2.21.2

**Stand:** 2026-09-08
**Status:** in_progress; Implementierung übernommen, finale Releasegates offen.
**Scope:** Windows und exakt CPython 3.14.7.
**Branch:** `codex/v2.21.2`
**Statusautorität:** `.sprint/state.md` und der unmittelbar vor Publikation
live geprüfte GitHub-Zustand. Diese Datei ist kein Selbstnachweis bestandener Gates.

## Änderungen und Befundgrenzen

| Eintrag | Einordnung | Verhalten |
|---|---|---|
| Timeout-Anzeige | bestätigter Darstellungsfehler, Implementierung im Kandidaten | CLI zeigt die tatsächlich zugewiesenen Taskbudgets einschließlich Fallbackformel und gegebenenfalls Spannweite; Budgetzuweisung und Ergebnisklassifikation bleiben gleich. |
| Basisdiagnose | opt-in Diagnosefunktion, Implementierung im Kandidaten | `--basis-diagnostics` zeichnet die realen Hashbeiträge und aufeinanderfolgenden Übergänge auf; neue absolute Ausgabedatei außerhalb der gemessenen Wurzeln, Veröffentlichung nach dem Lauf. |
| Historische Basisentwertungen | kein bestätigter Produktbug | Nicht reproduziert; historische Ursache unbekannt. Diagnosevollständigkeit ist getrennt von Basisvollständigkeit und Ergebnisautorität. |

Die Diagnose ergänzt Observerdaten. Sie kann die Laufzeit erhöhen, ist kein
atomarer Beweis sämtlicher zwischenzeitlicher Änderungen und ändert bei einem
Recorderfehler nicht die Autoritätsentscheidung. Inhalte und Umgebungswerte
werden nicht als Rohwerte ausgegeben. Der Implementierungsstand stammt aus
`03e1d26362eb807a854a4b6ada72a07089c586ed`; seine fokussierte Evidenz ersetzt keine
Qualifikation des versionierten Patchkandidaten.

Die historische Untersuchungsserie 02 beendete drei Läufe mit insgesamt 630
Ausführungen derselben 210 Mutanten, zwölf stabilen Snapshots und neun
Übergängen innerhalb der Läufe. Eine erneute Basisentwertung wurde nicht
festgestellt. Die Testmanagement-Prozessprüfung korrigierte die Behandlung
wiederverwendeter numerischer PIDs anhand der nativen Erstellungsidentität;
dies ist keine Produktänderung dieses Patches. Der historische erste STOP und
seine ursprünglichen Readbacks bleiben erhalten.

Der erste vorab begrenzte Kandidatenpilot auf sechs geänderten
Funktionsbereichen beendete 392 frische Mutanten mit gültiger Basis,
276 Kills und 116 Überlebenden. Sein Score von 70,408 Prozent verfehlte
die 80-Prozent-Schwelle; dieser FAIL bleibt erhalten. Statischer Review
belegte fehlende Testassertionen für vollständige Anzeigezeilen,
Hashbeiträge, Zähler, Attribution und Übergangsdetails. Die ergänzten
Tests verwenden bekannte Eingabebytes und ein unabhängiges HMAC-Oracle
sowie veröffentlichte Berichtsdaten. Sie ändern keinen Produktcode.
Die Wirkung muss eine neue Kampagne mit denselben sechs Funktionsbereichen,
demselben Operatorprofil und unverändertem Mutantennenner belegen.
Ein ausreichender Pilot-Score ersetzt weiterhin keine vollständige
Modulabdeckung oder integrierte Releasequalifikation.

## Offene Qualifikation

Der verbindliche Umfang mit neun offenen Releasegates steht in
`_docs/sprint backlogs/sprint_40_backlog.md`. Geprüfte Kandidaten-, Integrations-
und Artefaktidentitäten werden erst nach tatsächlicher Prüfung eingetragen.
Die unveränderten Berichte `ANALYSE_MUTMUTWIN221.md` und
`BUGFIXUNG_ROADMAP.md` sowie Sprint 39 dokumentieren den Vorgänger und
bescheinigen diesem Kandidaten keinen Erfolg.

Alle Gateumgebungen sind frisch und extern: `UV_PROJECT_ENVIRONMENT` und
`HYPOTHESIS_STORAGE_DIRECTORY` zeigen auf getrennte absolute Verzeichnisse
außerhalb des Checkouts. Qualitätsbefehle sind `uv run --no-sync ruff check --no-cache .`,
`uv run --no-sync ruff format --no-cache --check .`,
`uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/` und
`uv run --no-sync lint-imports --no-cache`.

Vollständige Zielsystemtests, Coverage, gelockter Dependency-Audit, kanonisches
Semgrep-Gate, nativer Release-Wrapper, Dogfood, Doppelbuild und getrennte
Installationssmokes bleiben erforderlich. Nicht ausgeführte Prüfungen sind
`NOT_EXECUTED`, keine bestandenen Tests. Das gilt auch für eine billingbedingt
nicht gestartete GitHub-CI. Eine früher verweigerte Prüfung wird nicht durch
eine andere Aufrufweise umgangen oder als PASS ausgewiesen.

Nach Review und tree-identischer Zwei-Parent-Integration werden die Gates auf
dem integrierten Commit wiederholt. Erst danach folgen Artefakte, ein neues
annotiertes Tag und ein eigener GitHub-Release; vorhandene Tags und Assets
bleiben unverändert. PyPI-Publishing ist kein Teil dieses Releasevertrags.

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->
