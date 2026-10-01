# mutmut-win — Project Memory

> Last refresh: 2026-10-01.

## Sanierung v2.21.4 → **Programmziel: v3.0.0** (Sprints 43–47, R0–R4)

- **Versionseinordnung (Auftraggeber-Entscheidung):** Die vollstaendig sanierte Version
  (alle 146 Defektgruppen behoben) wird **mutmut-win 3.0.0** (Major-Bump). Signal an
  die Kunden: grundlegend anderes Korrektheitslevel, alle Kinderkrankheiten behoben.
  Das Programmziel lebt oberhalb der Sprint-Zielversion (aktuell v2.21.5) und wird
  erst mit der Releasefreigabe wirksam (Lifecycle in `.sprint/state.md`).
- **Auslöser:** Review-Abschlussbericht (23.09.2026) mit 146 Defektgruppen (9 high,
  56 medium, 81 low) gegen v2.21.4/`4d7f950`; Handover `HANDOVER_GLM-5.3.md`
  (ungetrackt, liegt im Review-Workspace `C:/claude_codex/mutmut-win-astra`).
- **Grundregel:** Jede Gruppe M-xxx wird vor jedem Fix mit Serena verifiziert
  (Symbole, Aufrufer, Widerlegungskriterien) und durch einen vorher rot laufenden
  Regressionstest belegt. Keine Vertragsvariante (P-08) ohne Nutzerentscheidung.
- **Sprint 43 (R0) abgeschlossen** auf `fix/v2.21.5-remediation-r0` (Issue #141):
  Baseline aller Gates protokolliert; Testinfrastruktur Q-01–Q-04
  (`tests/unit/atomic_fault_util.py`, `windows_fs_util.py`, `guard_plugin_util.py`,
  `process_tree_util.py` + conftest-Fixtures) mit 27 Eigentests; Q-05-Matrix im
  Sprint-43-Backlog; 51 AP-Issues #141–#191 + 5 Milestones; Semgrep-Gate pass
  (ein adjudiziertes Finding für den Q-01-Harness-Import, Commit e1f1217);
  pip-audit clean. Historie: der dokumentierte R0-Volllauf war fehlgeschlagen,
  es wurden nur gezielte Nachtests geführt (AR-27 dokumentiert die Lücke).
- **Sprint 44 (R1) abgeschlossen:** AP-00b bis AP-08b — **18 eindeutige M-IDs**
  (M-140, M-142, M-145, M-008, M-143, M-034, M-002, M-031, M-003, M-001, M-006,
  M-007, M-005, M-114, M-009, M-144, M-004, M-139 — 9 P1 plus 9 Begleiter inkl.
  M-114). Phasengate: Vollsuite 2731/43/1 (der cicd-Export-Flake lag nicht unter
  der P-17-Ausnahme — als Lücke geführt, AR-27), Semgrep-Gate PASS, pip-audit
  clean. P-08 (R1): M-008=A, M-003=A, M-144 S2=A.
- **Sprint 45 (R2, administrative Vorwelle + Nachbesserung):** AP-09 bis AP-32
  inkl. AP-29b auf `fix/v2.21.5-remediation-r1` bis `a385a63` gemergt. Das
  adversariale Astra-Review (2026-10-01, `ASTRA_REVIEW_R1_R2.md`) fällte
  **„nicht abnahmefähig"**: 37 Findings → **AR-01 bis AR-27** (6 P1/19 P2/2 P3),
  zehn P-08-Entscheidungen getroffen (Astra, `P08_ENTSCHEIDUNGEN_R2_ASTRA.md`),
  u. a. **M-042-Korrektur**: `e9bfbee` dokumentierte BC-132 (dekorierte Klassen),
  die Originalkarte M-042/BC-085 (len/isinstance-Bindung + Argumentschnitt) ist
  wieder geöffnet und wird umgesetzt. **Eindeutige Zählung (AR-25):** R2 umfasst
  85 eindeutige M-IDs: 75 IMPLEMENTED + M-101 (Stufe 1) + M-102 (Docstring) +
  8 vollständig P-08-blockiert; die zehn P-08-Fragen sind keine zusaetzlichen
  disjunkten Gruppen. Nachbesserung läuft auf `fix/v2.21.5-remediation-r2`
  (Arbeitsmatrix: `reviews/mutmut-win-r2-2026-10-01/glm-followup/ARBEITSMATRIX.md`).
- **Parallelisierung (Auftraggeber-Freigabe):** Ab R2 duerfen Subagenten parallel
  an mehreren Arbeitspaketen arbeiten (Worktree-Isolation, P-12). Der Nutzer hat
  ein hohes Tokenlimit und kann bei Ueberschreitung ohne Kontextverlust wechseln.

## Stehende Regeln (aus Sprint 42 und früher, weiterhin verbindlich)

- Lifecycle-Vertrag: `.sprint/state.md` hat 16 Frontmatter-Felder inkl.
  `phase`/Provenance; Branch-Muster `fix/vX.Y.Z-…` oder `codex/vX.Y.Z`; der
  LIVE-Block und das aktive Sprint-Backlog (genau 9 einheitliche Checkboxen,
  NOT_EXECUTED-Klauseln, RELEASE_SEQUENCE) sind wortgenau getestet
  (`tests/unit/test_release_supply_chain.py`). `tests_passed`/`semgrep_passed`/
  `housekeeping_done` bleiben `false`, solange `phase: in_progress` (bis zum
  Version-Bump auf das Release-Ziel).
- Berichtsdateien (ASTRA_*, CLAUDE_*, HANDOVER_*, OVERLAP_*, Review-Abschluss*)
  niemals committen und nicht im Checkout liegen lassen (CRLF verletzt den
  Checkout-Vertrag); sie leben im Review-Workspace `mutmut-win-astra`.
- Gate-Umgebungen: `UV_PROJECT_ENVIRONMENT` und `HYPOTHESIS_STORAGE_DIRECTORY`
  extern setzen; für Vollsuiten zusätzlich `--group build` synchronisieren
  (hatchling wird von Supply-Chain-Tests benötigt).
- Engine-Self-Mutation: gezielte Gates mit Contract-Tests als einzigem
  `--tests-dir` (Matrix im Sprint-43-Backlog).
- pytest-Vollsuiten laufen serial >45 min: nur als Hintergrundprozess mit Log in
  einem externen Verzeichnis starten; Toolbox-Timeouts töten den Elternprozess
  und verwaisten Worker. Niemals Python-Prozesse nach Namen killen, während ein
  Baseline-Lauf läuft.
