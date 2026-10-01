# Sprint 45 Backlog

| | |
|---|---|
| **Ziel** | v2.21.5 |
| **Baseline** | Sprint 44 (R1) abgeschlossen auf `fix/v2.21.5-remediation-r1`; R2-Vorwelle (AP-09 bis AP-32) gemergt bis `a385a63`; adversariales Astra-Review (2026-10-01) mit Gesamturteil „nicht abnahmefähig" |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v2.21.5-remediation-r2` |
| **Start** | 2026-09-28 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot.

## Auslöser

Phase R2 der Sanierung v2.21.4 (AP-09 bis AP-32) wurde programmatisch
gemergt; das unabhängige adversariale Review (ASTRA_REVIEW_R1_R2.md,
2026-10-01, Prüfstand `a385a63`) bestätigte 27 Folgeaufträge
(AR-01 bis AR-27: 6 P1, 19 P2, 2 P3) und traf die zehn P-08-Entscheidungen.
Dieser Sprint setzt die Nachbesserung und die P-08-Umsetzungen um; das
Programmziel 3.0.0 (Major) bleibt dokumentierte PO-Entscheidung oberhalb
der Sprint-Zielversion und wird erst mit der Releasefreigabe wirksam.

## Arbeitsumfang (R2-Nachbesserung + P-08)

- [ ] P1-Produkt: AR-01 (M-009 Rootidentität), AR-02 (M-001/M-032 verschachtelte Wurzeln), AR-03 (M-001 Gitlink), AR-17 (M-005 CAS-Race-Tests)
- [ ] Gate-Infrastruktur: AR-15 (#192-Diagnose/Fix + 17 Gruppen nachqualifizieren), AR-13 (Q-02 HANDLE), AR-09 (M-140), AR-27 (Phasengate-Matrix)
- [ ] P2-Produkt: AR-04 (M-001 Worktree-Cache), AR-05 (M-144 Popen-Barrieren), AR-06/AR-07 (M-005 CAS-Backup/Siblings), AR-08 (M-011 Retry-Leiter), AR-10 (M-006 Runtime-Präfix), AR-24 (M-076 Exit 130)
- [ ] P-08-Umsetzungen: M-022/M-023 (AP-16), M-036 (AP-22), M-016 (AP-29b), M-061 (AP-11), M-041 (AP-24), echte M-042 (AP-23), M-058 (AP-15), M-102 (AP-27); M-064/M-101 Stufe 2 per Entscheidung zurückgestellt, AR-12-Benchmark nachliefern
- [ ] Test-/Evidenzqualität: AR-16 (58 Gruppen-Receipts beschaffen/erzeugen), AR-18 (M-017 Git-Orakel echte Verzeichnisse), AR-19 (AP-16 Gate-Werte trennen)
- [ ] Dokumentation/Governance: AR-20/21/22/23 (README-Verträge), AR-25 (eindeutige Zählung), AR-26 (Sprint-/Releasezustand konsistent)
- [ ] Konsolidiertes Phasengate (P-16/P-18): Vollsuite, kanonisches Semgrep-Gate, gezielte Mutationsgates auf dem finalen Stand, Governance grün
- [ ] Abschlussbericht mit vollständig abgeglichener AR/P-08-Matrix, Gate-Receipts, verbleibenden Risiken und Abnahmeempfehlung

## Abgrenzungen

- R3 (AP-33 bis AP-46) und R4 (AP-47) sind nicht Teil dieses Sprints.
- Administrativ geschlossene Issues (#154–#176) werden über Folgekommentare
  an die tatsächliche Nachbesserung gebunden; keine stillen Wiedereröffnungen.
- Historische R0-/R1-Gate-Lücken werden transparent dokumentiert (AR-27),
  nicht rückwirkend als bestanden erklärt.
