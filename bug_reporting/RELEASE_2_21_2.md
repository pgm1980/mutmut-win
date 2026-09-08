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
| CI-Prüfaufbau | belegte Workflow-/Testkorrektur | Der Lock-Job stellt Windows und CPython 3.14.7 bereit. Ein bestehender Test akzeptiert beide zulässigen Meldungen derselben atomaren Schreibsperre; seine Cleanup-Assertions bleiben erhalten. |

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
Die zweite Kampagne auf Kandidat
`adeb09bbbb0b206132a0f2a161a3e8b36c38c9d5` behielt dieselben sechs
Funktionsbereiche, dasselbe Operatorprofil und den Nenner von 392 frischen
Mutanten bei. Sie endete mit 356 Kills und 36 Überlebenden, entsprechend
90,81632653061224 Prozent. Die unabhängige Prüfung bestätigte vollständige,
gültige Ergebnisbasis, unveränderte gebundene Eingaben, keine Timeouts oder
Suspicious-Ergebnisse und einen quieszenten Prozessabschluss. Damit ist die
80-Prozent-Schwelle innerhalb dieses begrenzten Kandidatenpiloten bestanden.
Der erste FAIL und seine Belege bleiben unverändert erhalten.

Externes Nachweisartefakt unterhalb des Release-Evidence-Roots:
`candidate-adeb09b/dogfood-mutation/independent-review.json`, SHA-256
`5a0d8efbd578e3d0be2da328e4caaf954557df18f036b56568b36996051901fe`.
Dieser Bericht erteilt keine integrierte Releaseautorität.

Der Pilot umfasst `_frame_signature`, `_transition` einschließlich seiner
verschachtelten Helfer, `observed_sha256`, `_Capture.record_update`,
`_ObservedHash.update` und `_print_timeout_model`. Er ersetzt weder die
allgemeine Mutationstest-DoD für alle neuen/geänderten Codebereiche noch die
integrierte Wiederholung. Weitere geänderte Bereiche in `basis_diagnostics.py`,
`cli.py`, `orchestrator.py` und `stats.py` liegen außerhalb seiner
Mutantenauswahl; daraus folgt keine Aussage über deren vorhandene Unit-Test-
oder Laufzeitcoverage. Die übrige Änderungsscope-Qualifikation bleibt offen.

## PO-Entscheidung zur einzelnen lokalen Testlücke

Der Product Owner hat am **8. September 2026** für **v2.21.2** ausdrücklich
die folgende einzelne Ausnahme akzeptiert, sofern alle übrigen Releasegates
bestanden werden:

`tests/unit/test_run_surface_integration_220.py::test_mid_run_ambient_drift_preserves_results_without_authority`

Dieser Fall bleibt wegen der dokumentierten automatischen Policy-Abweisung
`NOT_EXECUTED`. Er wird weder ausgeführt noch umgangen oder als PASS geführt.
Die Ausnahme gilt ausschließlich für die Kandidatenprüfung und deren
integrierte Wiederholung. Die vollständige übrige Zielsystemsuite mit Coverage
und sämtliche anderen Releasegates bleiben erforderlich. Die Entscheidung
erteilt keine weitere lokale Testausnahme, keine weitere Deselektion und keine
Verringerung des Mutationstestumfangs. Sie ist keine vorgezogene Attestierung
der noch offenen Gates oder Publikationsbereitschaft.

## Offene Qualifikation

Der Live-Abgleich vom 8. September 2026 belegt, dass GitHub-CI-Lauf
`34186159711` auf Main `98f053da8b20f35eb71a254b44ef06ff12cbcd86`
tatsächlich ausgeführt wurde und fehlschlug. Im Lock-Job fehlte der benötigte
Interpreter. Der Testjob meldete 2515 bestandene Tests, 15 Skips und einen
Fehler: Die Meldungsassertion erwartete nur die spätere Identitätsprüfung,
obwohl bereits die vorgelagerte Linkprüfung zulässig abweisen kann. Dieser
Lauf ist `FAIL`, nicht billingbedingt `NOT_EXECUTED`. Der Patch korrigiert
den Prüfaufbau und übernimmt genau die oben akzeptierte Deselektion in CI.
Die erfolgreiche Ausführung und die bestehenden Cleanup-Assertions müssen
am korrigierten Stand erneut belegt werden.

Der lokale Suite-Lauf auf `113ee37b94feec112a0105cd744bbfea412d3373`
endete mit 2527 bestandenen Tests, 43 ausgewiesenen Skips, genau einer
autorisierten Deselektion und einem Fehler bei der Checkout-Zeilenendprüfung.
Während des Laufs wurde ausschließlich die gebundene Datei
`.serena/project.yml` umgeschrieben; ihre CRLF-Zeilenenden lösten den Fehler
aus. Der Lauf beendete seine Prozesse quieszent und erreichte 85,46 Prozent
Coverage, bleibt aber wegen Testfehler und Eingabedrift `FAIL`.
Die finale Prüfung erfolgt in einem separaten sauberen Worktree ohne
Serena-Aktivierung. Wegen fehlendem FS-MCP und der beobachteten Serena-
Migration werden interne Datei-, Git- und statische AST-Werkzeuge verwendet.

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

Die vollständige übrige Zielsystemsuite unter der oben genau benannten
PO-Ausnahme, Coverage, gelockter Dependency-Audit, kanonisches Semgrep-Gate,
nativer Release-Wrapper, Dogfood, Doppelbuild und getrennte Installationssmokes
bleiben erforderlich. Nicht ausgeführte Prüfungen sind
`NOT_EXECUTED`, keine bestandenen Tests. Das gilt auch für eine billingbedingt
nicht gestartete GitHub-CI. Eine früher verweigerte Prüfung wird nicht durch
eine andere Aufrufweise umgangen oder als PASS ausgewiesen.

Nach Review und tree-identischer Zwei-Parent-Integration werden die Gates auf
dem integrierten Commit wiederholt. Erst danach folgen Artefakte, ein neues
annotiertes Tag und ein eigener GitHub-Release; vorhandene Tags und Assets
bleiben unverändert. PyPI-Publishing ist kein Teil dieses Releasevertrags.

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->
