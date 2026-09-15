# Sprint 41 Backlog

| | |
|---|---|
| **Ziel** | v2.21.3 |
| **Baseline** | v2.21.2, Integrationscommit `3de6a2c776bddc2792aab6dcdaab4d8a3cae5fb3`, Housekeeping `f726891` |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v2.21.3-lake-basis` |
| **Analyse** | `bug_reporting/RELEASE_2_21_3.md` |
| **Roadmap** | `bug_reporting/RELEASE_2_21_3.md` |
| **Start** | 2026-09-15 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

## Arbeitsumfang

- [ ] Fix B (primär): hierarchische `.gitignore`-Respekt für alle Staging- und Basis-Walks (`gitignore_boundary.py`, pathspec>=1.1.1,<2) inklusive git-`add -f`-Semantik, Dotenv-Carve-out und End-to-End-Nachweis
- [ ] Fix A: `--force`-Cleanup-Retry mit Backoff vor dem fail-closed Refusal
- [ ] Fix C: Run-Startup-Observability (Phase-Progress, Dauer-Ausgaben, `--debug`-Traces, Stall-Watchdog)
- [ ] Run-Robustheit: enge Atomic-Publication-Retry-Punkte, Pfad-Sicht-Link-Count, Publish-Once-Phase-Guard, dokumentiertes `clean_run_timeout`
- [ ] Mutationstesting der neuen Module mit Score-Nachweis (≥ 80 % oder dokumentierte Survivors)
- [ ] Vollständige lokale Gates (Vollsuite, Ruff, mypy, Import-Linter, Export+Audit, Semgrep, Native)
- [ ] Version, Installationspins und Dokumente auf v2.21.3 synchronisieren
- [ ] Kandidat reviewt und tree-identisch nach `main` integrieren, integrierte Finalgates wiederholen
- [ ] Annotierten Tag `v2.21.3` setzen und GitHub-Release mit Notes veröffentlichen (kein PyPI)

## Governance-Hinweis

Release-Evidenz erfordert `UV_PROJECT_ENVIRONMENT` und
`HYPOTHESIS_STORAGE_DIRECTORY` als absolute externe Verzeichnisse;
der Checkout darf weder `.venv`, Werkzeug-Caches mit eigener
`.gitignore` noch `.hypothesis`-Cachebytes enthalten.


## Akzeptanzkriterien

- Der Reporter-Fall (gitignorierter Riesenbaum in `tests/`) erreicht den
  Profil-Hint in Sekunden und stagt den Baum nie.
- Die stille Prelude ist Vergangenheit: Phasen- und Dauer-Ausgaben, Watchdog
  dokumentiert; `--force`-Cleanup absorbiert transiente Sperren.
- Alle Gates grün auf Kandidat UND Integration; Mutation-Score je neuem
  Modul dokumentiert; Dossier `bug_reporting/RELEASE_2_21_3.md` vollständig.

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot.

Gate-Kommandos: `uv run --no-sync ruff check --no-cache .`,
`uv run --no-sync ruff format --no-cache --check .`,
`uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/`,
`uv run --no-sync lint-imports --no-cache`,
`uv sync --locked --only-group release --no-install-project` gefolgt von
`uv run --no-sync python -I scripts/release_native_gate.py`.
Zizmor 1.30.0 läuft offline mit `--strict-collection --no-config --no-ignores`
in den Personas `regular` und `pedantic`; Zizmor ist kein viertes Manifest-Asset.
