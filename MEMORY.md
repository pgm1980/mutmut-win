# mutmut-win — Project Memory

> Last refresh: 2026-10-07 (v3.1.0 released).

## Testsanierung v3.0.0 → **Programmziel: v3.1.0** (Sprint 47, Issue #198, PR #199) — ABGESCHLOSSEN

- **Ziel erreicht:** Testpyramide von 97 % Unit auf getragene Struktur
  (E2E 0→~27 Fälle, Integration ~15→~45, Property 0→60 @given, Architektur 35→87);
  Vollsuite Finalstand **3861 passed / 0 failed / 45 skipped / 1 xfailed** in 2:25:02
  (Run 4, `c0492c7`; Runs 5/6 = Release-Härtung, Receipts im Evidence-Verzeichnis).
- **Engine-Ökonomie:** M-149/M-149b shared pycache (Phasen + Worker, ~50×);
  db-Kampagne 2.989 Mutanten ~35 min; Isolation bewiesen (simple_lib 14/14 killed).
- **Kill-Raten-Korridore:** trampoline 66,7 % (93,6 % adjudiziert),
  suspended_spawn 34,8 %, db 16,4 % — Äquivalenzmutanten dokumentiert.
- **GAP-1..7 (26 Fälle):** Config-Fail-Closed, Atomic-Crash, Mutation-Operator,
  Staging-Drift, Browser-Diff, Lock-Konkurrenz, Interrupt (AttachConsole-Hilfsprozess:
  CTRL_C_EVENT von konsolenlosem Runner ist ein No-Op — Engine-Vertrag
  AR-24/M-076 E2E bestätigt: exit 130 + Status interrupted + Recovery).
- **Release-Härtung 2026-10-07:** repo-weite Ruff-Schuld (11 Funde) + 4 Format-Dateien,
  PEP758/Semgrep-Parser-Konflikt (except-Split), pyjwt-14×PYSEC adjudiziert
  UNREACHABLE (ignore-vuln in ci.yml, Override-Variante widerlegt),
  Governance-String-Kollision. Semgrep-Allowlist 31→43 (`bd45065`).
- **Externes Review vorbereitet:** `_docs/reviews/external-review-v3.1.0/`
  (Handover-MD mit 146-Gruppen-Bilanz + Testpyramide, Prompts Fable 5.1 /
  GPT-6 Astra mit Serena-Oberdirektive + Zwei-Läufe-Struktur
  [Roadmap-Umsetzung + 360°-Regressionsscan], 5-Stufen-Pipeline-README).
  Ursprungs-Reviews archiviert in `_docs/reviews/external-review-v2.21.4/`.
- **Offen:** H1–H4 Trampolin-Grenze (externes Review), Issue #193
  (Generation-Fingerprint ohne Engine-Version).

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
- **R2-Nachbesserung nahezu abgeschlossen (2026-10-02, HEAD `4a6e9a4`):** alle
  27 AR-Auftraege + 9 P-08-Umsetzungen verifiziert; **Vollsuite PASS** (erstmalig
  seit R0 vollstaendig auf dem Endstand: 3583/14/44 + Re-Run 105/9 — die 14 Falls
  waren Venv-Luecken: `[dev]`-Extras fehlten, pytest-asyncio/-benchmark), **Semgrep
  PASS** (31 adjudizierte Findings, Re-Record nach M-041/M-036/M-144,
  Pinning-Test 28→31), Governance 79/79. Trampoline-Gate 66,7 % + vollstaendige
  Survivor-Adjudizierung (~93,6 % Korridor, 5 Gruppen requalifiziert).
  **Config-Gate abgebrochen** (Nutzerentscheid: pathologische Mutanten-Region
  mit Stunden-Budgets + Issue #195; Teilevidenz 194k/146s bei 48 % archiviert).
- **Neue Engine-Issues:** **#194** Forced-Fail-/Kollektions-Hang bei
  `test_duplicate_definitions_220.py` im tests-dir (3×-Repro, CPU-Loop in
  `pathlib.__hash__`/`source_to_code`; blockiert Multi-Datei-Adjudizierung,
  Single-File-Gates unbeeinflusst — Synergie mit AP-41/#185 in R3). **#195**
  Verdict-Cache wird ueber Laeufe hinweg nicht wiederverwendet
  (`tests_fingerprint` instabil bei identischen Eingaben) — Absturz/Neustart
  vernichtet alle Verdikte.
- **v2.21.5 RELEASED (2026-10-02):** Kandidat `b47209c` (Tree `ee302345`),
  integriert als `9e3bec8` (Merge PR #196, Baum byte-identisch), annotierter
  Tag `v2.21.5`, GitHub-Release mit vollständiger Gate-Evidenz. Integrierte
  Vollsuite 3599/0/43 (pytest 9.0.3 lock-exakt); ruff/format/mypy-strict/
  import-linter grün auf Kandidat UND Integration; kanonisches Semgrep-Gate
  PASS (31 adjudizierte Findings); pip-audit sauber bis auf dokumentierte
  pyjwt-Dev-Abweichung (mcp-Deckelung); Wheel/sdist reproduzierbar gebaut.
  Gate-Infrastruktur-Regel: Regex-/Node-Gate-Receipts laufen über den
  Release-Body nach (regex-Wiederholung + Cross-File-Adjudizierung offen;
  config dokumentiert abgebrochen).
- **v3.0.0 RELEASED (2026-10-05):** Kandidat `d291ee5` (Tree `5457315e`),
  integriert als `99db317` (Merge PR #197, Baum byte-identisch), annotierter
  Tag `v3.0.0`, GitHub-Release mit Gate-Evidenz. R3-Welle: 43 Gruppen
  implementiert und rot/grün verifiziert (38 Fixes, 4 nach Gegenbeweis
  widerlegt/gepinnt, M-097 deferred); Testspezifikation in
  `_docs/testmanagement/test_specification.md`. Release-Vollsuite 3.668/1/44 —
  Root Cause des Fails: PEP-758-Multi-Except aus `95341e11` (M-112); Fix
  `ea0069c` [M-112-fix] plus gezielter Grün-Nachweis (88 passed).
  Modul-Gate-Kampagne nach Auftraggeberentscheidung abgebrochen und als
  dokumentierte Abweichung freigegeben (AR27-GATE-MATRIX.md §7): 3 PASS,
  2 BLOCKED (models/browser — Trampolin-Grenze klassenlastiger Module,
  Produkt-Bug durch Spiegelvergleich widerlegt), db-Teilevidenz 288/2.622
  (24,3 % Kill), Rest NOT_EXECUTED. Offen: #193, #194, #195; Übergabe an
  externen adversarialen Multi-Agenten-Review (GPT-6 Astra / Fable 5.1)
  mit Prüfaufträgen H1-H4 und E-A bis E-F.
- **Betriebsregel für Gate-Läufe (harte Lehre 2026-10-02):** Während ein
  Mutation-Gate läuft, darf sich im Worktree **nichts** ändern — weder Commits
  noch Dateien. Der Fingerprint- und der Staging-Integritätswächter invalidieren
  sonst den Lauf (zwei Läufe verloren: node_mutation Fingerprint-Abbruch,
  regex_mutation Staging-Selbstinvalidierung nach 5 h). Gates, die parallel zu
  Repo-Arbeit laufen sollen, gehören in einen SEPARATEN Worktree (z. B.
  `mutmut-win-gate2`), dessen Checkout eingefroren bleibt.
- **Master-Ledger (neues Abnahme-Instrument):** `R0-R4-MASTER-LEDGER.md` — alle
  **146 Gruppen** (R1=18, R2=85, R3=43; Handover-Zahlen 15/56/81 waren
  ungenau) aus 5 autoritativen Quellen; dreistufig: **35 verifiziert /
  68 implementiert-unverifiziert / 43 offen**. AR-16-Klarstellung: Issue-Kommentare
  enthaelten NULL receipt-artige Belege (75 Kommentare geprueft) — Modul-Gates
  sind die einzige Receipt-Quelle. **3.0.0 erst bei 146/146 verifiziert.**
- **Reihenfolge zur 3.0.0 (Auftraggeber):** Gates abschließen → v2.21.5-Release →
  R3-Sprint nach `R3-SPRINT-PLAN.md` (4 Wellen; AP-34 zuerst/XL; Receipt-Pflicht
  ab Tag 1; #194-Loesung in AP-41) → **vollstaendiges externe Astra-Review gegen
  die Roadmap** → R4/AP-47 → 3.0.0.

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
