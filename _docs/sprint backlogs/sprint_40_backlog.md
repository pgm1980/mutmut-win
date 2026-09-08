# Sprint 40 Backlog

| | |
|---|---|
| **Ziel** | v2.21.2 |
| **Baseline** | v2.21.1, Integrationscommit `e91d338f9457b9d6526463fb0f835fab5d82736e`; anschließende Governancekorrektur `98f053da8b20f35eb71a254b44ef06ff12cbcd86` |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `codex/v2.21.2` |
| **Analyse** | `bug_reporting/RELEASE_2_21_2.md` |
| **Roadmap** | `bug_reporting/RELEASE_2_21_2.md` |
| **Start** | 2026-09-08 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

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

## Integrations- und Releasegates

Alle Syncs und Gates laufen mit einer frisch angelegten absoluten
`UV_PROJECT_ENVIRONMENT` außerhalb des Release-Checkouts;
`HYPOTHESIS_STORAGE_DIRECTORY` zeigt auf ein separates absolutes externes
Verzeichnis. Der Checkout enthält weder `.venv` noch Werkzeug-Caches mit
eigener `.gitignore` oder `.hypothesis`-Cachebytes.

- [ ] Reviewed Zwei-Parent-Integration des byteidentischen Kandidatentrees in
  `main` nach den vollständigen Kandidatengates.
- [ ] Vollständige strikte Suite mit Coverage auf dem integrierten Commit unter
  Windows und exakt CPython 3.14.7: `uv run --no-sync pytest -q --cov=mutmut_win --cov-report=term-missing -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning`;
  keine unerklärten Fehler, Threadwarnungen oder Skips akzeptieren. Jede nicht
  ausgeführte Prüfung bleibt als Evidenzlücke sichtbar.
- [ ] `uv run --no-sync ruff check --no-cache .`,
  `uv run --no-sync ruff format --no-cache --check .`,
  `uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/`,
  `uv run --no-sync lint-imports --no-cache` sowie `uv lock --check` auf dem
  quieszenten integrierten Commit wiederholen.
- [ ] Vollständigen gelockten Dependency-Export und Pip-Audit auf dem
  integrierten Commit ohne bekannte Advisories wiederholen.
- [ ] Kanonisches Semgrep-Gate auf dem integrierten Commit mit null unerwarteten
  Findings, Errors, übersprungenen Regeln und Fixpoint-Timeouts wiederholen;
  exakte Allowlisttreffer bleiben sichtbar.
- [ ] Kanonischen nativen Release-Wrapper wiederholen:
  `uv sync --locked --only-group release --no-install-project`, danach
  `uv run --no-sync python -I scripts/release_native_gate.py`. Die drei
  manifestgebundenen nativen ZIP-Werkzeuge und das separat aus `uv.lock`
  gebundene Zizmor 1.30.0 müssen bestehen. Zizmor läuft offline mit
  `--strict-collection --no-config --no-ignores` in den Personas `regular` und
  `pedantic`; Zizmor ist kein viertes Manifestasset.
- [ ] Geänderten Code adversarial prüfen, Regressionen und dokumentierten
  Dogfood-Piloten ohne Recovery-/Problem-Buckets und mit mindestens 80 Prozent
  Pilot-Score auf dem integrierten Stand belegen.
- [ ] Reproduzierbarer Doppelbuild, identische Inventare und SHA-256 sowie
  getrennte installierte Wheel-/Sdist-Smokes auf dem Zielsystem; die Umgebungen
  liegen außerhalb des Release-Checkouts.
- [ ] Annotiertes Tag und GitHub-Release erst nach allen lokalen Belegen.

Publikation erfolgt über annotiertes Git-Tag und GitHub-Release-Artefakte.
PyPI-Publishing ist kein Teil des Produkt- oder Releasevertrags.

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
dokumentiert. Das ist eine akzeptierte Evidenzlücke, aber weder PASS noch FAIL.

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->
