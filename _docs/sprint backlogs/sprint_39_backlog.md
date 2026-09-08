# Sprint 39 Backlog

| | |
|---|---|
| **Ziel** | v2.21.1 |
| **Baseline** | veröffentlichtes v2.21.0-Tag, Commit `40b6af31da66f3544ab9d1a38d34511e7e02c79a`, Tree `9fe800a9849fe35cf87f57b2f098ee02a08cd76a` |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `main` |
| **Analyse** | `bug_reporting/ANALYSE_MUTMUTWIN221.md` |
| **Roadmap** | `bug_reporting/BUGFIXUNG_ROADMAP.md` |
| **Start** | 2026-09-02 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

Andere Python-Versionen, Implementierungen und Betriebssysteme sind nicht
unterstützt und bilden kein Releasegate. Historische Mehrversions- und
POSIX-Evidenz bleibt als solche erhalten, erweitert aber nicht den
Product-Owner-Scope.

## Arbeitsumfang

1. Sämtliche MW221-Behauptungen unabhängig gegen Code, Regressionen und reale
   Windows-/CPython-3.14.7-Läufe adjudizieren.
2. Bestätigte Zielsystembefunde sowie durch das Codex-Reaudit gefundene
   CX221-Befunde implementieren und mit negativen Gegenproben absichern.
3. Architektur-, Design-, Lizenz-, Produktbacklog- und Live-State-Verträge mit
   dem verbindlichen Zielsystem, PEP 263 und der tatsächlichen
   Releaseprovenienz synchronisieren.
4. Den final eingefrorenen Kandidatentree vollständig lokal prüfen, reviewed
   und tree-identisch integrieren, auf dem integrierten Commit erneut prüfen
   und daraus reproduzierbare Artefakte erzeugen.
5. Erst nach Doppelbuild, Hash-/Inventargleichheit und installierten Wheel-/
   Sdist-Smokes ein annotiertes Tag und den zugehörigen GitHub-Release
   veröffentlichen.

## Integrations- und Releasegates

Alle folgenden Syncs und Gates laufen mit einer frisch angelegten absoluten
`UV_PROJECT_ENVIRONMENT` außerhalb des Release-Checkouts;
`HYPOTHESIS_STORAGE_DIRECTORY` zeigt auf ein separates absolutes externes
Verzeichnis. Hypothesis 6.151.10 schreibt Cachebytes, aber keine eigene
`.gitignore`. Der Checkout darf weder `.venv`, Werkzeug-Caches mit eigener
`.gitignore` noch `.hypothesis`-Cachebytes enthalten.

- [x] Reviewed Zwei-Parent-Integration des byteidentischen Kandidatentrees in
  `main`.
- [x] Vollständige strikte Suite mit Coverage auf dem integrierten `main`-Commit
  unter Windows und exakt CPython 3.14.7 mit `uv run --no-sync pytest -q --cov=mutmut_win --cov-report=term-missing -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning` wiederholen; keine
  unerklärten Fehler, Threadwarnungen oder Skips akzeptieren.
- [x] `uv run --no-sync ruff check --no-cache .`,
  `uv run --no-sync ruff format --no-cache --check .`,
  `uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/`,
  `uv run --no-sync lint-imports --no-cache` sowie `uv lock --check` auf dem
  quieszenten integrierten `main`-Commit wiederholen.
- [x] Vollständigen gelockten Dependency-Export und Pip-Audit auf dem
  integrierten Commit ohne bekannte Advisories wiederholen.
- [x] Kanonisches Semgrep-Gate auf dem integrierten Commit mit null unerwarteten
  Findings, Errors, übersprungenen Regeln und Fixpoint-Timeouts wiederholen;
  exakte Allowlisttreffer bleiben sichtbar.
- [x] Kanonischen nativen Release-Wrapper auf dem integrierten Commit wiederholen:
  `uv sync --locked --only-group release --no-install-project`, danach
  `uv run --no-sync python -I scripts/release_native_gate.py`. Der Wrapper prüft
  die exakt drei manifestgebundenen nativen ZIP-Werkzeuge actionlint 1.7.12,
  ShellCheck 0.11.0 und Gitleaks 8.30.1 sowie das getrennt aus `uv.lock`
  gebundene Zizmor 1.30.0 offline mit `--strict-collection --no-config
  --no-ignores` in den Personas `regular` und `pedantic`; Git for Windows wird
  aus dem systemweiten HKLM-Vertrag statt Caller-PATH bezogen. Zizmor ist kein viertes Manifestasset; die lokale Bootstrapumgebung wird frisch gelockt
  synchronisiert.
- [x] Dokumentierten Dogfood-Piloten auf dem integrierten Commit ohne Recovery-/
  Problem-Buckets und mit mindestens 80 Prozent Pilot-Score wiederholen.
- [x] Reproduzierbarer Doppelbuild, identische Artefaktinventare und SHA-256
  sowie installierte Wheel-/Sdist-Smokes auf dem Zielsystem; beide Smoke-Venvs
  liegen getrennt unterhalb von `RUNNER_TEMP`, niemals im Release-Checkout.
- [x] Annotiertes Tag und GitHub-Release erst nach allen lokalen Belegen.

Publikation erfolgt ausschließlich über das annotierte Git-Tag und die
zugehörigen GitHub-Release-Artefakte. PyPI-Publishing ist kein Teil des
Produkt- oder Releasevertrags.

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
dokumentiert. Das ist eine akzeptierte Evidenzlücke, aber weder PASS noch FAIL.

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->
