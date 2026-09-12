# Release-Dossier: mutmut-win v2.21.2

**Stand:** 2026-09-12T23:23:01.019128+00:00 / 2026-09-13T01:23:01.019128+02:00
**Status:** released; vereinbarte lokale Qualifikation und veröffentlichte Downloads bestätigt.
**Scope:** Windows und exakt CPython 3.14.7.
**Branch:** `main`
**Statusautorität:** `.sprint/state.md` und datierter externer GitHub-Readback.

## Tatsächlicher Abschluss

[PR #137](https://github.com/pgm1980/mutmut-win/pull/137) integriert Kandidat
`6f7d431071a928709d67d17cecce62e9c6d75f92` als echten Zwei-Eltern-Merge `3de6a2c776bddc2792aab6dcdaab4d8a3cae5fb3`.
Eltern: `98f053da8b20f35eb71a254b44ef06ff12cbcd86`, `6f7d431071a928709d67d17cecce62e9c6d75f92`. Beide Trees sind `3086a3b3ec4ad2e983297692fea3f090d440c602`.
Das annotierte Tag `v2.21.2`, Objekt `7de6101e0faf7a5029e105fbddd2bacfcf64f8d6`, bleibt direkt auf M.
Dieser ausschließlich dokumentierende Housekeeping-Schritt folgt M; er ändert kein Releaseartefakt.

[GitHub-Release](https://github.com/pgm1980/mutmut-win/releases/tag/v2.21.2), ID `387731784`,
publiziert 2026-09-12T23:13:40Z / 2026-09-13T01:13:40+02:00.
Der Readback vom 2026-09-12T23:14:30.929073+00:00 bestätigt genau fünf Assets, identische
Downloadbytes und übereinstimmende GitHub-SHA-256-Digests. Vorhandene Tags bleiben unverändert.
Die frische vollständige Issues-Abfrage ergab null offene Repository-Issues.

## Die neun vereinbarten Gates

1. Reviewter Kandidat C und realer Zwei-Eltern-Merge M mit identischem Tree: bestanden.
2. Kandidat und M: jeweils 2.548 bestanden, 43 einzeln erklärte Skips und die exakt
   akzeptierte einzelne NOT_EXECUTED-Prüfung. Coverage C 85,55 %, M 85,56 %.
   Separater pytest-8.2.2-Kompatibilitätsnachweis: 45 bestanden, zwei begründete Skips;
   M frisch ausgeführt, Kandidat gemäß dokumentierter Input-/Runtime-Äquivalenz gebunden.
3. Ruff Check/Format, mypy strict, Import-Linter und Lock-Prüfung auf C und M: bestanden.
4. Vollständiger gelockter Export und Audit: bestanden, keine bekannten Advisories.
   M-Export SHA-256 `56d652215797acef3307d59f7ea9849c4146e9b71aa9d62f5c7427598e813da4`.
5. Kanonisches Semgrep: bestanden; 234 Ziele, 346 Regeln, 22 exakte Allowlisttreffer,
   null unerwartete Findings, Fehler, übersprungene Regeln oder Timeouts.
6. Kanonischer nativer Release-Wrapper mit manifestgebundenen Werkzeugen und
   separat gelocktem Zizmor in beiden Personas: bestanden.
7. Adversariale Reviews, verstärkte Regressionen und drei getrennte Mutationstestpopulationen:

| Population | Kandidat C | Integration M |
|---|---|---|
| Sechs Funktionsfamilien / 392 | 360 killed, 32 survived; 91,8367 % | 360 killed, 32 survived; 91,8367 % |
| 23 Observer-/Stats-Familien / 565 | 492 killed, 73 survived; 87,0796 % | 492 killed, 73 survived; 87,0796 % |
| Geänderte Pipeline-Anweisung / 13 | 11 killed, 2 survived; 84,6154 % | 11 killed, 2 survived; 84,6154 % |

Die beiden vollständigen Diagnosekampagnen haben gültige vollständige Ergebnisbasis
und keine Timeout-, Suspicious-, Skipped-, No-Test-, Crash- oder Unchecked-Buckets.
Die Pipeline-Prüfung belegt ihre festgelegte Änderungsstelle mit 13 abgeschlossenen
Varianten. Kein aggregierter oder projektweiter Score; Survivors und bestehende
Generatorgrenzen bleiben im jeweiligen dokumentierten Umfang erhalten.

8. Zwei unabhängige saubere Builds von M: Wheel und Sdist bytegleich. Exakte
   Git-Provenienz aller 40 Produktdateien und 239 Sdist-Gitdateien, Inventare,
   RECORD, Metadaten, Epoch, Twine strict und Wheel-Inhaltsprüfung bestanden.
   Je getrennte frische lokale Wheel-/Sdist-Installationen sowie anschließend
   frische Installationen beider tatsächlicher GitHub-Downloads bestanden:
   Baseline, jeweils fünf von fünf Mutanten getötet, echte 60-Sekunden-Timeoutanzeige,
   vier stabile Diagnosesnapshots/drei Übergänge, gültige Datenbankautorität,
   unveränderte gebundene Eingaben und regulär leere eigene Prozess-Jobs.
9. Annotiertes Tag, GitHub-Release und fünf Assets nach den lokalen Gates veröffentlicht
   und vollständig zurückgelesen. Kein PyPI-Publishing.

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `SDIST-INVENTORY.txt` | 13769 | `2bc6b23eee6d663bb665cef66d58bb4aad2581f3e4f7bab2e1facfcf6ebd7681` |
| `SHA256SUMS` | 192 | `9c64d8076477d4f1390e3032fd52f1fd0ad0820fd0db33bfb832a2da61cba01a` |
| `WHEEL-INVENTORY.txt` | 1304 | `b05484344ea8c07af506534930b6e0dceadc3587825538700d6d2532f7d8d181` |
| `mutmut_win-2.21.2-py3-none-any.whl` | 310422 | `4f580fe1f5ac06eb99f2a6b293d99799ec5cdbfeb888d99e98b6df87fecc13f6` |
| `mutmut_win-2.21.2.tar.gz` | 787063 | `e124da7c0750eb564bf99043d763613f7b958d8ad15944364cc18f9ccb80a596` |

## Akzeptierte Grenzen und erhaltene Fehlschläge

Die erfolgreiche Hosted-GitHub-CI ist aufgrund der expliziten PO-Ausnahme vom
13. September 2026 keine Freigabebedingung. Billingbedingt nicht gestartete Jobs
bleiben NOT_EXECUTED; tatsächlich fehlgeschlagene Läufe bleiben FAIL.
PR-Lauf `34718687182` ist FAIL und wird nicht als bestandene Evidenz verwendet.
Ein späterer ausschließlich CI-bezogener Entwurf wurde nicht in M übernommen.

`tests/unit/test_run_surface_integration_220.py::test_mid_run_ambient_drift_preserves_results_without_authority`
bleibt unter der PO-Entscheidung vom 8. September 2026 für C und M NOT_EXECUTED.
Die automatische Policy-Abweisung wurde nicht umgangen oder in PASS umbenannt.

Die historischen Basisentwertungen sind nicht reproduziert; ihre Ursache bleibt
unbekannt und ist kein bestätigter Produktbug. Die neue Diagnose beweist ihre
historische Ursache nicht. Diagnosevollständigkeit und Ergebnisautorität sind getrennt.

Frühere Test-/Harness-FAILs bleiben unverändert belegt. Die finale Pipeline-Prüfung
korrigierte ausschließlich einen veralteten externen Planpin und die automatische
Aufnahme des großen Evidenzverzeichnisses in `sys.path` mit anschließendem Hashen. Produkt-/Test-/Variantenbytes
und Budgets blieben unverändert. Der externe Archivprüfer benötigte den expliziten
Git-Revisionsseparator für lange Windows-Pfade und die feste v2.21.2-Erwartung für
`_docs/basis_diagnostics.md`; seine vollständigen Byte-/Inventarprüfungen blieben erhalten.
Diese belegten Harnessursachen erklären nicht rückwirkend die historischen Basisereignisse.

## Maschinenlesbare Abschlussbelege

Die folgenden lokalen externen Belege binden Rohdateien und native Prozessabschlüsse.
Sie wurden vor dem Housekeeping gelesen; sie sind keine zusätzlichen Release-Assets.

- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\prepublication-qualification.json` — SHA-256 `815d101e4d2896f72d68c2a4364743af4b5576634111f20f4a2f4dc9e1275d10`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\integrated-local-qualification.json` — SHA-256 `0294afbb2c94ebc3931c1dfe1b05f85c09d9c81864359c8391b1753c25577850`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\artifacts\independent-review.json` — SHA-256 `6ac1d719d275b3eba8331340d1492d604365aea77d5c761d83c2265865e8b7c8`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\artifacts\installed-smokes-independent-review.json` — SHA-256 `9257ff25b582aa0e997a86e271d75ff91465b9367c80249058bae2a7dbbe679e`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\artifacts\continuation-completion.json` — SHA-256 `8f709be38b8b88dc1e2419ee271c6bab3df2494467756d1625bb71b132560ae3`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\public-readback\completion.json` — SHA-256 `76a7b67637608ffa68090fc63a8f65e9f13c58400481759a5fa52afd27570bec`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\public-readback-process\completion.json` — SHA-256 `4c2e783e62b45a09fbacf002007e894dcb452558762c12bb61ed48a89aafa52c`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\published-install-setup.json` — SHA-256 `fef6f39d2cbbdeb9e981849be1c4d48bcae8d2692eac42aff0f7a0d28beef989`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\artifacts\wheel-features\completion.json` — SHA-256 `03d5ffe306aeb3aa2cd54e3fe8eccc47cdc07bf840d35ec8f9a68119f37af386`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\artifacts\wheel-features\feature-result.json` — SHA-256 `f0a8211bed6dba08fe8fc0a4498e952500327afc083e2df05d35a79757248c25`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\artifacts\sdist-features\completion.json` — SHA-256 `71c4efe1d758c8c24595f62e2e7e03da8515d5fd1f0d9a2c0e33275692f72acb`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\artifacts\sdist-features\feature-result.json` — SHA-256 `43a4c466192c50364f4fbcaaf29a5e0716d1ffd231f042b2a427d40b9f119b89`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\published-wheel-features\completion.json` — SHA-256 `d3d6d3174666072b56c44c616014bbe294885923f0e98fd0ee38b8c23473ba91`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\published-wheel-features\feature-result.json` — SHA-256 `7bae5c9eeeb3d413cf5c73d478d1edd3d53629d1ece0a7565e46826e788c19d8`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\published-sdist-features\completion.json` — SHA-256 `2116160bae01975170c1dd4aa115f743f5e5d4a5cb0d2f7a0976f8cf5457f019`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\published-sdist-features\feature-result.json` — SHA-256 `2c530967bddfad09603e291b9cd96cc66998e126cb23404aa5c64689155c865f`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\issues-readback.json` — SHA-256 `5992c08d48641c80b262c283953cead4374c61898473797c9b90aa1ebd1ac5ed`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\candidate-qualification-6f7d431-20260912.json` — SHA-256 `01c540ea86b9aa54b2fdfafa621bc6011886c6417bd5d59c4cc331c386338efb`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\full-suite\independent-review.json` — SHA-256 `0fb5805b4425086c56b15149ab4cde811d0f264626f7ffb902aada36b1c32afd`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\remaining-gates\root-raw-review.json` — SHA-256 `a9bac51842bc1053ec3dc34596fc6cb398f26b42062be1ef6712f74d1e9cf7c0`.
- `C:\Users\pmitt\AppData\Local\Temp\mmw-floor-3de6a2c\root-raw-review.json` — SHA-256 `745ef5f12733dbefc49aac3e3643bee109d4d15845646fec82c5891b7f739cbb`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\candidate-3de6a2c-observer-completion-v2\observer-mutation\independent-review.json` — SHA-256 `867af167089d3db539d404d715f2617021e33e30f4862dc29b4d35ca2d7836e0`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\candidate-3de6a2c-pilot-completion-v2\dogfood-mutation\independent-review.json` — SHA-256 `8f7b22c2fd176ad60da02137ddfde8f81f69fc06c62b31dbd7c42d42d22851cd`.
- `C:\Users\pmitt\AppData\Local\Temp\mutmut-win-v2212-release-20260908\integrated-3de6a2c-completion-v2\pipeline-tests-safe-path\independent-review.json` — SHA-256 `a15361ac258db59882b4c83fb0d773fb0d5498ecdb994255ba14f5213378e434`.

## Historischer Vorqualifikationsstand

Die folgenden ursprünglichen Abschnitte werden unverändert als damaliger Stand
erhalten. Ihre offenen Gates und früheren Kandidatenwerte sind keine aktuellen Statusaussagen.

<details>
<summary>Historischer Stand vor der abschließenden Qualifikation</summary>

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

</details>
