# Sprint 33 Backlog — v2.11.0 „Maintenance 1: Runtime & Self-Run"

**Sprint-Ziel:** Erster bedarfsgetriebener Maintenance-Sprint nach dem
Audit-Zyklus. Leitmotiv: die drei S2-Blocker zwischen dem Projekt und
breitem Dogfooding beseitigen — das Timeout-Modell bekommt einen
gemessenen Startup-Sockel (DOG-001), ungemappte Mutanten laufen nicht
mehr die Vollsuite (QX-007), und die Trampolin-Importkette wird
entkoppelt (QX-001), womit der Architektur-Skip im Build-Artefakt
fällt. Messbare Erfolgsgröße: **Dogfooding-Pilot BRUTTO ≥ 80 %**
(Sprint 32: 24,2 % brutto / 85,5 % über bewertbare).

**Basis:** Maintenance-Backlog (Product Backlog) — Auswahl nach
Schaden/Nutzen, KEIN Abarbeitungs-Versprechen für den Pool-Rest
(20 Einträge bleiben dokumentiert liegen).

**Branch:** `feature/v2.11.0-maintenance-1` · **Release:** v2.11.0
(nur auf explizites User-„Release")

**Planungs-CoT:** 10 Schritte — Leitmotiv-Findung (Runtime & Self-Run),
Design-Richtungen je S2 (gemessener Sockel via clean_wall−Σdurations;
Stats-vorhanden-Unterscheidung für no-tests; Kernel-Modulzug mit
BWC-Re-Export), Risiken (Hänger-Budget, Score-Verschiebungen,
Codegen-Pins), Scope-Ventil.

---

## Ausgewählte Items

| # | Issue | Typ | Titel | Quelle | SP | Priorität | Reihenfolge | Status |
|---|-------|-----|-------|--------|----|-----------|-------------|--------|
| 1 | [#105](https://github.com/pgm1980/mutmut-win/issues/105) | Bug | DOG-001: additiver Startup-Sockel im Timeout-Modell (gemessen, geclamps, transparent) | Dogfooding S2 | 5 | Must | 1 | 🔲 |
| 2 | [#106](https://github.com/pgm1980/mutmut-win/issues/106) | Bug | QX-007: `no tests`-Producer — ungemappte Mutanten laufen heute die Vollsuite | Audit S3 (Laufzeit-Kern) | 5 | Must | 2 | 🔲 |
| 3 | [#110](https://github.com/pgm1980/mutmut-win/issues/110) | Bug | Hygiene-Kleinkram: QX-017/018 (max_stack_depth-Falle!), QX-019-Rest, DOG-002 | Audit/Dogfooding S4 | 3 | Should | 3 (QX-018 gehört laufzeitlich zu #105/#106) | 🔲 |
| — | — | Gate | **Dogfooding-Re-Run (Zwischengate): brutto ≥ 80 % erwartet** | — | — | 4 | 🔲 |
| 4 | [#107](https://github.com/pgm1980/mutmut-win/issues/107) | Bug | QX-001(+QX-020): Trampolin-Importkette → Kernel-Modul; Architektur-Skip fliegt | Audit S2 + Sprint-32-Marker | 8 | Must | 5 | 🔲 |
| 5 | [#108](https://github.com/pgm1980/mutmut-win/issues/108) | Bug | UI-007: Browser-Diff = `show`-Diff (Single Source); DB-Fallback-Namensform | Audit S2 | 5 | Should | 6 | 🔲 |
| 6 | [#109](https://github.com/pgm1980/mutmut-win/issues/109) | Bug | Browser/CLI-Robustheit: UI-010/011/013/016 | Audit S3/S4 | 5 | Should | 7 | 🔲 |
| — | — | Gate | Abschluss-Dogfooding (gleicher Pilot, Vergleichbarkeit) + Score-Doku | — | — | 8 | 🔲 |

**Gesamt geplant:** 31 SP (Must 18, Should 13)

**Scope-Ventil:** #108/#109/#110 rutschen bei Blowup zurück in den Pool.
v2.11.0 ist mit #105–#107 + Re-Run-Beleg release-fähig.

---

## Sprint-Strategie

- **Maintenance-Disziplin:** Auswahl nach Schaden/Nutzen; der Pool-Rest
  (20 Einträge) wird NICHT versprochen. Nach v2.11.0: erneute Auswahl
  oder bewusster Stopp.
- **Messbarkeit wie im Audit-Modus:** Das Dogfooding-Zwischengate nach
  #105+#106 macht den Sprint-Erfolg VOR dem größten Item (#107) sichtbar;
  der Abschluss-Lauf dokumentiert den Endstand (gleicher Pilot für
  Vergleichbarkeit: code_coverage.py + type_checking.py).
- **Design-CoTs (CLAUDE.md):** #105 ≥ 8 (Sockel-Quelle clean_wall −
  Σdurations vs. Konstante; Clamp-Grenzen; Hänger-Worst-Case-Rechnung
  vor/nach), #107 ≥ 8 (Band-Platzierung laut ADR-Contract,
  Codegen-Importzeile, BWC-Re-Export, Importzeit-Test < 100 ms).
- **#106-Designkern:** `tests=[]` ist heute doppeldeutig — Vollsuite-
  Fallback bleibt für „keine Stats vorhanden" (seit #99 laut), echtes
  `no tests` (exit 33, nie dispatcht, direkt persistiert à la #93) nur
  bei „Mapping vorhanden, Mutant leer". Drei-Kanal-Test erweitert.
- **Score-Verschiebungen kommunizieren** (Changelog): no_tests
  verlässt den Nenner; zufällige Vollsuite-Kills entfallen.
- **#107-Beweisziel:** Der QX-001-Skip-Marker in test_architecture.py
  wird ENTFERNT — das Layer-Gate gilt wieder überall, auch im Artefakt.

---

## Task Breakdown

### Item 1: #105 Startup-Sockel (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 1.1 | **Design-CoT (≥ 8):** Sockel-Quelle (gemessen: clean_wall − Σdurations), Clamp, Transparenz-Ausweis, Hänger-Worst-Case vor/nach | 🔲 |
| 1.2 | Failing Tests: Budget = Sockel + estimated×mult (Floor bleibt Untergrenze); Sockel aus Messwerten; Clamp-Grenzen; Summary weist Sockel aus | 🔲 |
| 1.3 | Implementierung (Orchestrator misst clean_wall bereits; Stats liefern Σdurations) | 🔲 |
| 1.4 | Gates | 🔲 |

### Item 2: #106 no-tests-Producer (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 2.1 | Failing Tests: Mapping vorhanden + Mutant leer → exit 33 persistiert, NICHT dispatcht; kein Mapping → Vollsuite-Fallback bleibt (laut); Drei-Kanal-Konsistenz mit no_tests | 🔲 |
| 2.2 | Orchestrator: Abzweig bei Test-Zuweisung (à la #93-Persistenz) | 🔲 |
| 2.3 | Gates | 🔲 |

### Item 3: #110 Hygiene-Kleinkram (3 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 3.1 | QX-018: `max_stack_depth` ge=-1 (0 verwarf ALLE Stats-Hits → Vollsuite je Mutant) | 🔲 |
| 3.2 | QX-017: `_reset_globals` deckt `_cached_max_stack_depth` | 🔲 |
| 3.3 | QX-019-Rest: MUTANT_UNDER_TEST-Konsolidierung (eine Quelle) | 🔲 |
| 3.4 | DOG-002: JT-018-Hint einmal pro LAUF statt pro Worker | 🔲 |
| 3.5 | Gates | 🔲 |

### Zwischengate: Dogfooding-Re-Run

| Task | Beschreibung | Status |
|------|-------------|--------|
| G.1 | Pilot-Re-Run (gleiche Module, --force) → brutto ≥ 80 % erwartet; Ergebnis dokumentiert | 🔲 |

### Item 4: #107 Trampolin-Entkopplung (8 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 4.1 | **Design-CoT (≥ 8):** Kernel-Modul (Band laut ADR), Codegen-Importzeile, BWC-Re-Export, bestehende Codegen-Test-Pins | 🔲 |
| 4.2 | Failing Tests: Importzeit-Pin (< 100 ms, ohne click/textual im Modulgraph); Codegen erzeugt neue Importzeile; Re-Export funktioniert | 🔲 |
| 4.3 | Implementierung + QX-020-Slice (kein Per-Hit-Import im Hot Path) | 🔲 |
| 4.4 | **Architektur-Skip-Marker ENTFERNEN** — Gate gilt wieder im Artefakt (In-Mutants-Verifikation) | 🔲 |
| 4.5 | Gates | 🔲 |

### Item 5: #108 Browser-Diff (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 5.1 | Failing Tests: Browser-Diff-Quelle == mutant_diff.get_diff_for_mutant (Unit auf Quelle, nicht Pixel); DB-Fallback findet lokale Namensform | 🔲 |
| 5.2 | Umbau auf Single Source | 🔲 |
| 5.3 | Gates | 🔲 |

### Item 6: #109 Robustheit (5 SP)

| Task | Beschreibung | Status |
|------|-------------|--------|
| 6.1 | UI-010: leere Tabelle crasht keine Aktionen | 🔲 |
| 6.2 | UI-011: ConfigError → saubere Meldung in show/apply/browse | 🔲 |
| 6.3 | UI-013: EINE Exit-Code-Konvention bei leerer DB (dokumentiert + getestet) | 🔲 |
| 6.4 | UI-016: End-Summary immer; --no-progress unterdrückt nur Live-Zeilen | 🔲 |
| 6.5 | Gates | 🔲 |

### Abschluss: Dogfooding + Doku

| Task | Beschreibung | Status |
|------|-------------|--------|
| A.1 | Abschluss-Pilot (gleiche Module) — Score dokumentiert; neue Funde → Pool | 🔲 |
| A.2 | Maintenance-Backlog aktualisieren (erledigte Einträge raus, neue rein) | 🔲 |

---

## Quality Gates Sprint-Ende

| Gate | Befehl | Erwartung |
|------|--------|-----------|
| Tests | `uv run pytest` | 821 + neue ≥ 840 passed |
| Linting | `uv run ruff check src/ tests/` | 0 Findings |
| Format | `uv run ruff format --check src/ tests/` | 0 zu formatieren |
| Type Check | `uv run mypy src/mutmut_win/` | keine NEUEN Errors (Baseline 20) |
| Security | `semgrep scan --config auto src/mutmut_win/ tests/` | 0 blocking |
| Architecture | lint-imports in-suite — **nach #107 OHNE Artefakt-Skip** | KEPT überall |
| Mutation | Dogfooding-Pilot | **brutto ≥ 80 %** + dokumentiert |

---

## Release v2.11.0 (nur auf explizites User-„Release")

| Task | Status |
|------|--------|
| pyproject.toml + uv.lock auf 2.11.0 (`uv lock --system-certs`) | 🔲 |
| Annotated Tag v2.11.0 | 🔲 |
| GitHub Release (Changelog: Runtime-Fixes, Pilot-Vorher/Nachher, Skip-Entfernung) | 🔲 |
| Auto-close #105–#110 via Merge | 🔲 |
| MEMORY.md + product_backlog.md update (Maintenance-Pool-Pflege) | 🔲 |
