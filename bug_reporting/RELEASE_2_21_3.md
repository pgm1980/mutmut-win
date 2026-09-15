# Release-Dossier: mutmut-win v2.21.3

<!-- PUBLICATION_STATE_START -->
<!-- PUBLICATION_STATE: external-live-check-required -->
Publication status for v2.21.3 is external mutable state. These immutable bytes assert neither presence nor absence; verify the exact annotated tag and matching GitHub release before use.
<!-- PUBLICATION_STATE_END -->

<!-- LIVE_STATE_START -->

<!-- RELEASE_PHASE: in_progress -->
<!-- RELEASE_PHASE_STATUS: implementation-and-final-gates-open -->
<!-- RELEASE_TARGET: v2.21.3 -->
<!-- RELEASE_BRANCH: `fix/v2.21.3-lake-basis` -->
<!-- RELEASE_ROADMAP: bug_reporting/RELEASE_2_21_3.md -->
<!-- RELEASE_PUBLICATION_AUTHORITY: canonical-external-block -->

<!-- LIVE_STATE_END -->

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

**Stand:** 2026-09-15 (in Arbeit; finalisiert beim Release)
**Status:** Kandidat in Vorbereitung (Branch `fix/v2.21.3-lake-basis`).
**Scope:** Windows und exakt CPython 3.14.7.
**Branch:** `fix/v2.21.3-lake-basis` → PR → `main`
**Statusautorität:** `.sprint/state.md` und datierter externer GitHub-Readback.

## Auslöser und Ursache (MBR-2026-09-14-01)

Externer Blocker-Report des Projekts `lean4-lsp-mcp-server`: `mutmut-win run`
hängte reproduzierbar 15–60 Minuten nach dem Force-Cleanup ohne jede Ausgabe;
`mutants/` blieb leer. Die Probe-Antwort des Reporters
(`bug_reporting/MBR-2026-09-14-01_PROBE_ANSWERS.md`) bewies per Faulthandler-
Stackdump: kein Deadlock, sondern ein endlos langsamer Walk über den korrekt
gitignorierten `tests/test_project/.lake`-Baum (120.065 Dateien / 6,53 GB).
Dessen Inhaltsänderung änderte den Basis-Digest nicht; das vollständige
Auslagern des Baums aus dem Projekt ließ den Lauf in Sekunden zum
Profil-Hint kommen.

Ursache: Fünf unabhängige Walks (Staging-Namespace-Preflight in `cli.py`,
erneute Namespace-Validierung in `orchestrator.run`, doppelter
Ausführungsbasis-Fingerprint inklusive konfigurierter Bäume und
Distributionen, `copy_src_dir`-Eigenwalk, `walk_all_files`) respektierten
`.gitignore` nicht. Nicht die Run-Locks (widerlegt: strikt non-blocking,
bounded 0,5-s-Retry; mosaic-Gegenbeweis), nicht die Executor-Konstruktion,
nicht pytest-Args, nicht `mutate_only_covered_lines` (alle lokal mit der
exakten Reporter-Konfiguration widerlegt).

## Die Fixes

1. **Hierarchische Gitignore-Boundary** (`src/mutmut_win/gitignore_boundary.py`,
   neue Runtime-Dependency `pathspec>=1.1.1,<2` — rein-Python, null Pflicht-Deps,
   MPL-2.0, Trusted Publishing, pip-audit clean). Verzeichnis-Pruning vor dem
   Abstieg; tiefere Ignore-Dateien gewinnen; explizit konfigurierte Einträge
   werden forciert (git-`add -f`-Semantik; ein selbst ignorierter Eintrag
   immunisiert seinen Subtree, ein nicht ignorierter Eintrag prunt im Inneren
   weiter); unter ausgeschlossenen Verzeichnissen bleibt alles ausgeschlossen;
   unlesbare Ignore-Dateien schließen nichts aus (fail-closed für Hashes).
   Dotenv-Carve-out: `.env*` bleibt Ausführungsbasis-Eingabe, auch wenn
   gitignoriert. Integriert in: `_hash_context_tree` (Projektbaum,
   konfigurierte Bäume, Import-Pfade, Editables), `_iter_automatic_staging_inputs`,
   `_iter_configured_staging_inputs`, `copy_also_copy_files`/`_sync_tree`
   (Löschpass entfernt prä-Fix gestagte Ignorierte; vollständig geprunte
   Verzeichnisse werden nicht materialisiert), `copy_src_dir`, `walk_all_files`.
   End-to-End-Nachweis (Repro mit 20.000 Dateien gitignoriertem `.lake`):
   Profil-Hint in Sekunden, `.lake` nie gestagt, Kopie 15 s → 0,02 s.
2. **Run-Startup-Observability**: Phase-Progress („Fingerprinting execution
   basis …", „… in N,N s"), `--debug`-Schritt-Traces auf stderr, und
   `src/mutmut_win/stall_watchdog.py` — Faulthandler-Stackdump nach 60 s
   ohne Fortschritt (wiederholend, nie prozessbeendend, Fileno-Fallback auf
   `sys.__stderr__`). Der Watchdog hat während dieser Arbeit zwei echte
   60-s-Datei-Open-Blockaden unter Maschinenlast sichtbar gemacht — exakt
   der Diagnosegewinn, den der Reporter gefordert hatte.
3. **`--force`-Cleanup-Retry**: drei Entfernungsversuche mit Backoff
   (1 s, 2 s) vor dem bestehenden fail-closed Refusal (Nebenbefund A).
4. **Atomic-Publication-Transienz-Härtung** (vorbestehende Defekte, durch die
   Mutationstest-Läufe erstmals erreicht): drei enge, vollständig
   revalidierende Retry-Punkte — Sibling-Validierung, Replace, Parent-Capture
   (lange Leiter ≈ 16 s) — plus Pfad-Sicht-Entscheidung für den
   Link-Count (Handle-Sicht meldete transiente Zwei-Links für frische
   `O_EXCL`-Inodes, CX221-071-Familie). Churn-Reproducer: 1/5000 → 0/20000.
   Sicherheits-Tripwires unverändert: der gebundene Substitutionstest
   (`test_runner_sidecar_safety`) erzwingt weiterhin sofortiges Feuern;
   ein blanket Retry über `UnsafeAtomicWriteError` wurde von ebendiesem Test
   zurückgewiesen und verworfen.
5. **Phase-Guard publiziert einmal pro Phase** statt pro Test-Report:
   identische Re-Publizierung beweist nichts zusätzlich, fütterte aber
   Filtertreiber/IO mit Tausenden frischer Temporärdateien pro Phase und
   hat unter Last die gesamte Phase ausgehungert (Beweis: kein
   Sentinel-INTERNALERROR mehr nach dem Fix). Erstpublikation bleibt
   voll strikt.
6. **`clean_run_timeout = 2700`** dokumentiert im Dogfood-Config: Der Default
   300 s brach jede Volldogfood in der Clean-Phase ab (gestagte Unit-Suite
   braucht je nach Last 15–45 min).

Begleitende Governance: Dependency-Export-Pin auf
`ac6f3bde717885b420da8a146c72400613f5c7af4bfa5200f5984b2c1d65c07e` aktualisiert
(pathspec-Aufnahme); PEP-758-Bare-Multi-Excepts geklammert und mit
`# fmt: skip` fixiert (Ruff-Formatierer entfernt bei py314 sonst die Klammern,
die der gelockte Semgrep-1.175-Parser braucht); `.serena/project.yml`
LF-normalisiert.

## Regressionen (neu)

- `tests/unit/test_gitignore_boundary.py` (14): Hierarchie, Negation,
  Ankerung, Fail-closed, Subtree-Sperre, Force-Descent.
- `tests/unit/test_gitignore_staging_integration.py` (10): Automatische und
  konfigurierte Spiegel, Kopie, Sync-Migration, Digest-Invarianz,
  Dotenv-Carve-out, gitignore-bindet-Basis.
- `tests/unit/test_mbr_startup_fixes.py` (9): Retry/Backoff (A), Watchdog,
  Prelude-Prints, Debug-Traces (C).
- `tests/unit/test_atomic_transient_retry.py` (11): Replace-Retry,
  Sibling-Flap, Parent-Capture, Link-Count-Divergenz, Erfolgs-ohne-Sleep.
- `tests/unit/test_runner_sidecar_safety.py` erweitert: Publish-Once-Vertrag.

## Gates

[Ausführung in Phase 3: `uv run --no-sync ruff check --no-cache .`,
`uv run --no-sync ruff format --no-cache --check .`,
`uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/`,
`uv run --no-sync lint-imports --no-cache`,
`uv run --no-sync pytest -p no:cacheprovider`, pip-audit,
Semgrep-Gate, Native-Gate — Ergebnisse werden hier dokumentiert.]

Release-Evidenz erfordert `UV_PROJECT_ENVIRONMENT` und
`HYPOTHESIS_STORAGE_DIRECTORY` als absolute externe Verzeichnisse;
der Checkout darf weder `.venv`, Werkzeug-Caches mit eigener
`.gitignore` noch `.hypothesis`-Cachebytes enthalten.

## Mutation Testing

[Wir in Phase 2 ausgefüllt: `gitignore_boundary.py` + `stall_watchdog.py`,
Score je Modul, Survivors mit Begründung.]

## Veröffentlichung

[Wird in Phase 5 ausgefüllt: PR, Merge-Commit, integrierte Finalgates,
annotierter Tag, GitHub-Release-ID, Readback. Kein PyPI.]

## Betriebshinweis (dokumentierte Erkenntnis, kein Defekt)

Die gesamte Diagnose lief mit AKTIVER Microsoft-Defender-Echtzeitprüfung;
sie wurde erst nach Abschluss der Ursachenanalyse auf der
Entwicklungsmaschine deaktiviert. Die Transienz-Familie (gesperrte Replaces,
Handle-/Pfad-Sicht-Link-Count-Divergenz, blockierte Opens, minutenlange
Resolve-Ausfälle) ist das klassische Muster von Echtzeit-Filtertreibern auf
frisch erzeugten Dateien, verstärkt durch gleichzeitige intensive
mutmut-win-Läufe anderer Projekte auf derselben Maschine (IO/CPU-Konkurrenz
verlangsamt gestagte Suiten um ein Vielfaches). Der Stall-Watchdog macht
solche Phasen jetzt sichtbar (Stackdump statt Stille); die drei engen
Atomic-Retry-Punkte und der Publish-Once-Guard absorbieren die Folgen.
