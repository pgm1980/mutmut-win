# Sprint 40 Backlog

| | |
|---|---|
| **Ziel** | v2.21.2 |
| **Baseline** | v2.21.1, Integrationscommit `e91d338f9457b9d6526463fb0f835fab5d82736e`; anschließende Governancekorrektur `98f053da8b20f35eb71a254b44ef06ff12cbcd86` |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `main` |
| **Analyse** | `bug_reporting/RELEASE_2_21_2.md` |
| **Roadmap** | `bug_reporting/RELEASE_2_21_2.md` |
| **Start** | 2026-09-08 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

## Abschluss am 2026-09-13

PR #137, der geprüfte Integrationscommit `3de6a2c776bddc2792aab6dcdaab4d8a3cae5fb3`, das annotierte
Tag `v2.21.2` und der GitHub-Release sind bestätigt. Alle neun vereinbarten
lokalen Gates und beide frischen Download-Installationen sind abgeschlossen.
Der datierte Abschluss mit C-/M-, Artefakt-, Download- und Issues-Belegen steht
im aktuellen Abschnitt von `bug_reporting/RELEASE_2_21_2.md`. Eine erfolgreiche
Hosted-CI ist gemäß der am 13. September bestätigten PO-Ausnahme nicht erforderlich;
ausgeführte CI-FAILs und die exakte lokale NOT_EXECUTED-Ausnahme bleiben sichtbar.
Die folgenden Pilotabsätze beschreiben die damaligen Zwischenstände.

## Arbeitsumfang

1. Die bereits implementierte Timeout-Anzeigekorrektur und die explizit
   aktivierbare Basisdiagnose aus `03e1d26362eb807a854a4b6ada72a07089c586ed`
   als eigenen Patchkandidaten qualifizieren. Die Timeoutzuweisung und die
   Entscheidung über die Autorität eines Laufs werden nicht umdefiniert.
2. Die Diagnosegrenzen, Laufzeitkosten und externe Ausgabedatei dokumentieren;
   historische Basisentwertungen bleiben nicht reproduziert und ursächlich
   ungeklärt. Ein bestätigter Produktbug ist daraus nicht abgeleitet.
3. Version, Installationspins, CI-Artefaktprüfung und aktive Governance auf den
   Nachfolger synchronisieren, ohne historische Sprint-39-Register zu ändern.
4. Den finalen Kandidatentree vollständig prüfen, reviewed und tree-identisch
   integrieren, integrierte Gates wiederholen und reproduzierbare Artefakte
   mitsamt getrennten Wheel-/Sdist-Installationssmokes erzeugen.

Die fokussierten Implementierungs- und Diagnoseläufe des Vorgängers sind
ergänzende Evidenz. Sie erfüllen die folgenden Releasegates nicht vorab.

Der zweite begrenzte Kandidatenpilot auf
`adeb09bbbb0b206132a0f2a161a3e8b36c38c9d5` wurde unabhängig mit 356 Kills aus
392 frischen Mutanten, 90,81632653061224 Prozent, vollständiger gültiger Basis
und quieszentem Abschluss bestätigt. Auswahl und Nenner blieben gegenüber dem
ersten Pilot mit 276 Kills und 116 Überlebenden unverändert; dessen FAIL bleibt
erhalten. Umfang und exakter Nachweis stehen in `bug_reporting/RELEASE_2_21_2.md`.
Der Sechs-Funktionen-Pilot ersetzt weder die allgemeine Mutationstest-DoD für
alle neuen/geänderten Codebereiche noch die integrierte Wiederholung.

## Eng begrenzte PO-Ausnahme vom 8. September 2026

Für v2.21.2 hat der Product Owner ausschließlich den folgenden Fall als
`NOT_EXECUTED` wegen der dokumentierten automatischen Policy-Abweisung
akzeptiert, sofern alle übrigen Releasegates bestanden werden:

`tests/unit/test_run_surface_integration_220.py::test_mid_run_ambient_drift_preserves_results_without_authority`

Die Ausnahme gilt für Kandidat und integrierte Wiederholung. Der Fall wird
nicht ausgeführt, umgangen oder als PASS ausgewiesen. Die vollständige übrige
Zielsystemsuite mit Coverage und sämtliche weiteren Gates bleiben Pflicht.
Keine weitere lokale Testausnahme, Deselektion oder Verringerung des
Mutationstestumfangs ist damit genehmigt. Alle Abschlusscheckboxen blieben bis
zum tatsächlich nachgewiesenen Abschluss am 13. September 2026 offen.

## Integrations- und Releasegates

Alle Syncs und Gates laufen mit einer frisch angelegten absoluten
`UV_PROJECT_ENVIRONMENT` außerhalb des Release-Checkouts;
`HYPOTHESIS_STORAGE_DIRECTORY` zeigt auf ein separates absolutes externes
Verzeichnis. Der Checkout enthält weder `.venv` noch Werkzeug-Caches mit
eigener `.gitignore` oder `.hypothesis`-Cachebytes.

- [x] Reviewed Zwei-Parent-Integration des byteidentischen Kandidatentrees in
  `main` nach den vollständigen Kandidatengates.
- [x] Vollständige übrige strikte Suite mit Coverage auf dem integrierten Commit
  unter Windows und exakt CPython 3.14.7, mit ausschließlich der oben
  autorisierten Ausnahme: `uv run --no-sync pytest -q --cov=mutmut_win --cov-report=term-missing -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning --deselect=tests/unit/test_run_surface_integration_220.py::test_mid_run_ambient_drift_preserves_results_without_authority`;
  keine unerklärten Fehler, Threadwarnungen oder Skips akzeptieren. Jede nicht
  ausgeführte Prüfung bleibt als Evidenzlücke sichtbar.
- [x] `uv run --no-sync ruff check --no-cache .`,
  `uv run --no-sync ruff format --no-cache --check .`,
  `uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/`,
  `uv run --no-sync lint-imports --no-cache` sowie `uv lock --check` auf dem
  quieszenten integrierten Commit wiederholen.
- [x] Vollständigen gelockten Dependency-Export und Pip-Audit auf dem
  integrierten Commit ohne bekannte Advisories wiederholen.
- [x] Kanonisches Semgrep-Gate auf dem integrierten Commit mit null unerwarteten
  Findings, Errors, übersprungenen Regeln und Fixpoint-Timeouts wiederholen;
  exakte Allowlisttreffer bleiben sichtbar.
- [x] Kanonischen nativen Release-Wrapper wiederholen:
  `uv sync --locked --only-group release --no-install-project`, danach
  `uv run --no-sync python -I scripts/release_native_gate.py`. Die drei
  manifestgebundenen nativen ZIP-Werkzeuge und das separat aus `uv.lock`
  gebundene Zizmor 1.30.0 müssen bestehen. Zizmor läuft offline mit
  `--strict-collection --no-config --no-ignores` in den Personas `regular` und
  `pedantic`; Zizmor ist kein viertes Manifestasset.
- [x] Geänderten Code adversarial prüfen, Regressionen und dokumentierten
  Dogfood-Piloten ohne Recovery-/Problem-Buckets und mit mindestens 80 Prozent
  Pilot-Score auf dem integrierten Stand belegen.
- [x] Reproduzierbarer Doppelbuild, identische Inventare und SHA-256 sowie
  getrennte installierte Wheel-/Sdist-Smokes auf dem Zielsystem; die Umgebungen
  liegen außerhalb des Release-Checkouts.
- [x] Annotiertes Tag und GitHub-Release erst nach allen lokalen Belegen.

Publikation erfolgt über annotiertes Git-Tag und GitHub-Release-Artefakte.
PyPI-Publishing ist kein Teil des Produkt- oder Releasevertrags.

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
dokumentiert. Das ist eine akzeptierte Evidenzlücke, aber weder PASS noch FAIL.
Der am 8. September live geprüfte Main-Lauf `34186159711` wurde dagegen
ausgeführt und ist `FAIL`. Die beiden belegten Prüfaufbaufehler und ihre
Korrekturen stehen im Release-Dossier; aktuelle CI wird anhand ihrer
tatsächlichen Ausführung bewertet.

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->
