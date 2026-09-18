# Sprint 42 Backlog

| | |
|---|---|
| **Ziel** | v2.21.4 |
| **Baseline** | v2.21.3, Integrationscommit `fcb159334e3ded52791da369e558a543cd499704`, Tree `b956fd29d0f6ba439e9d37709927950f74b00e51` |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v2.21.4-nested-gitignore-resolution` |
| **Start** | 2026-09-18 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

## Auslöser

Beim Nachholen des in v2.21.3 ausgelassenen Mutationstestings wurde ein
Defekt in genau dem Modul gefunden, das v2.21.3 eingeführt hat:
`gitignore_boundary._excludes` löst Muster gegen den walk-root-relativen
Pfad auf statt gegen den Pfad relativ zum Verzeichnis der jeweiligen
`.gitignore`. Eine Root-`.gitignore` hat eine leere Base — deshalb ist der
Defekt dort und in allen mitgelieferten Fixtures unsichtbar.

## Arbeitsumfang

- [x] `_excludes` löst Muster relativ zur eigenen Ignore-Datei auf; Probes aus `relative` statt aus `candidate`
- [x] Vier Regressionstests für verschachtelte `.gitignore`-Semantik, jeweils gegen den ungepatchten Stand als fehlschlagend nachgewiesen
- [x] Toten Code `enter_forced` entfernen (kein Aufrufer, kein Test, kein Export; 26 unkillbare Mutanten)
- [x] Mutationstesting mit gezielten Gates je Modul, Kills über Gates vereinigt, Score ≥ 80 % oder dokumentierte Survivors
- [x] Governance-Suite von Dokumentationsdateien entkoppeln — kein Test setzt noch eine Doku-Datei voraus
- [x] Vollständige lokale Gates (Vollsuite, Ruff, Format, mypy, Import-Linter, pip-audit, Semgrep, Native)
- [x] Version, Installationspins und Dokumente auf v2.21.4 synchronisieren
- [x] Kandidat reviewt und tree-identisch nach `main` integrieren, integrierte Finalgates wiederholen
- [x] Annotierten Tag `v2.21.4` setzen und GitHub-Release mit Notes veröffentlichen (kein PyPI)

## Governance-Hinweis

Release-Evidenz erfordert `UV_PROJECT_ENVIRONMENT` und
`HYPOTHESIS_STORAGE_DIRECTORY` als absolute externe Verzeichnisse;
der Checkout darf weder `.venv`, Werkzeug-Caches mit eigener
`.gitignore` noch `.hypothesis`-Cachebytes enthalten.

Release-Evidenz wird ausschließlich im GitHub-Release-Body geführt. Ein
`bug_reporting/RELEASE_<version>.md` wird nicht mehr angelegt.

## Akzeptanzkriterien

- Ein verankertes Muster in einer verschachtelten `.gitignore` prunt seinen
  Teilbaum; ein unverankertes Muster trifft nie eine Vorfahren-Komponente.
  Beide Richtungen sind durch Tests gepinnt, die ohne den Fix fehlschlagen.
- Mutation Score je berührtem Modul dokumentiert; Survivors mit Begründung
  ausgewiesen, Äquivalenzmutanten als solche benannt.
- Alle Gates grün auf Kandidat UND Integration.

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot.

Gate-Kommandos: `uv run --no-sync ruff check --no-cache .`,
`uv run --no-sync ruff format --no-cache --check .`,
`uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/`,
`uv run --no-sync lint-imports --no-cache`,
`uv sync --locked --only-group security --no-install-project` gefolgt von
`uv run --no-sync python -I scripts/semgrep_release_gate.py`,
`uv sync --locked --only-group release --no-install-project` gefolgt von
`uv run --no-sync python -I scripts/release_native_gate.py`.
Zizmor 1.30.0 läuft offline mit `--strict-collection --no-config --no-ignores`
in den Personas `regular` und `pedantic`; Zizmor ist kein viertes Manifest-Asset.
