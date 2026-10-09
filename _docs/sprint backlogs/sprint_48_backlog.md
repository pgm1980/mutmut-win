# Sprint 48 Backlog

| | |
|---|---|
| **Ziel** | v3.1.0 |
| **Baseline** | S3-NO-GO; Reviewtag `9426088634589d70bcbbbc49e4d382091c621056`, Ausgangs-HEAD `fef1b61358dd6f860dbc7d9ec353c5334905d02e` |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v3.1.0-s3-sanierung` |
| **Start** | 2026-10-09 |
| **Statusautorität** | `.sprint/state.md`, `../sanierung/s3/SANIERUNGSLEDGER.json` und die dort gebundenen terminalen Receipts |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot. Dieser Sanierungsauftrag behauptet keine Veröffentlichung.

- [ ] P1 S3-001: beliebige geerbte Testeingaben binden; strict/lax und unveränderter gesunder Reuse im echten CLI
- [ ] P1 S3-002: Spawn-Coveragepfad, konservative vollständige Population, fehlende Kinddaten, harter Abbruch und Moduswechsel
- [ ] P1 S3-003: endliche CPU-Arbeit, echte Endlosschleife, Cleanup/Forensik und konservative Legacy-Auswertung
- [ ] P2 S3-004 bis S3-015: mechanismusspezifisches Rot, kausaler Fix, Grün und gesunde Gegenkontrollen
- [ ] P2-Testkarten: wirksame produktionsnahe Orakel statt schwacher Surrogate
- [ ] P3 Produkt-, Test- und Dokumentkarten nach den finalen Einzelkriterien
- [ ] Alle 220 offenen Verifikationskarten: eigenes Urteil oder präzise verbleibende Grenze; keine unbelegte Fehlerannahme
- [ ] Integrierte Finalgates: vollständiges pytest mit Coverage, Ruff/Format, mypy strict, Importcontracts, kanonisches Semgrep, nativer Wrapper und vollständiger Dependency-Audit
- [ ] Mutationsevidenz aller geänderten Module, Survivor-Adjudizierung, finale Bilanz und Original-/Frozen-Integritätsnachweis

Der Sanierungsplan und die 270 Einzelkarten stehen im Ledger. Ein Einzelgrün
ist keine integrierte Abnahme. Originalcheckout, eingefrorene S3-Dokumente
und historische Release-Refs bleiben erhalten. Der PO hat am 2026-10-09 den
aktuellen 17-Felder-Lifecycle-Vertrag und die entsprechende Berichtigung
des AGENTS-Schemas ausdrücklich bestätigt.
