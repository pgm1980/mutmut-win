# mutmut-win — Project Memory

> Last refresh: 2026-09-28.

## Sanierung v2.21.4 → **Ziel: v3.0.0** (Sprints 43–47, R0–R4)

- **Versionseinordnung (Auftraggeber-Entscheidung):** Die vollstaendig sanierte Version
  (alle 146 Defektgruppen behoben) wird **mutmut-win 3.0.0** (Major-Bump). Signal an
  die Kunden: grundlegend anderes Korrektheitslevel, alle Kinderkrankheiten behoben.
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
  pip-audit clean.
- **Sprint 44 (R1) läuft:** AP-00b bis AP-08b — alle 9 P1-Gruppen + 6 begleitende
  P2/P3-Gruppen umgesetzt (M-140, M-142, M-145, M-008, M-143, M-034, M-002, M-031,
  M-003, M-001, M-006, M-007, M-005, M-114, M-009, M-144, M-004, M-139).
  P-17 ist fuer beide fragilen Tests erloschen. Semgrep-Gate PASS (25 Findings,
  0 unerwartet), pip-audit clean. Finale Vollsuite laeuft.
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
