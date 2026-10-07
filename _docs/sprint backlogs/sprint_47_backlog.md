# Sprint 47 Backlog

| | |
|---|---|
| **Ziel** | v3.1.0 |
| **Baseline** | Sprint 46 (R3-Welle + Release 3.0.0) abgeschlossen auf `main` (`b0c8a10`); Freigabe der Testspezifikation v2 und Test-Sanierungsroadmap durch PO am 2026-10-06 (mit vier Auflagen, siehe Testspezifikation §13.1) |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v3.1.0-testsanierung` |
| **Start** | 2026-10-06 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot.

## Auslöser

PO-Diskussion 2026-10-05/06 über die Wiederholungsmuster schwerer Produktbugs
(v1, v1.9, 2.20.1, 2.21.4 — jeweils erst durch externe adversariale
Multi-Agenten-Reviews gefunden). Diagnose: Testpyramide mit 97 % Unit-Schwergewicht
(52,9 % gemockt), 0 % echten E2E-Tests, quantifizierter Testblindheit über
Modul-Gate-Kill-Raten (suspended_spawn 34,8 %, db 24,3 %). Sanierung der
Testpyramide nach Testspezifikation v2 mit Enabler-TDD-Prinzip und
Kill-Rate-Abnahme.

## Arbeitsumfang (Wellen W0 bis W5)

- [x] W0 Enabler-TDD: #194 (Forced-Fail-Liveness, TM-10), #195 (Cross-Run-Verdikt-Cache, TM-09), M-097 (load_current_run/load_results-Refactor) — rot/grün; Pflicht-Gegenprobe Cache-Invalidierung
- [x] W1 E2E-Rückgrat: test_full_run.py, test_error_paths.py gegen e2e_projects; test_class_heavy_projects.py mit xfail(strict=True)-Dokumentation der Trampolin-Grenze (TM-01/06/08/11); Campaign-E2E mit Resume
- [x] W2 Windows-FS- und Prozesskorridore: junctions/hardlinks/sharing-violation/readonly/normcase; Jobhandle/Pipe/Runtime-Root über echten Prozessbaum; Ctrl-C je Phase (TM-02/03/04)
- [x] W3 Property-Ausbau: strategies.py plus mindestens 60 neue @given-Tests (Serialisierung, Fingerprint-Stabilität, Pfade, Stat-Ergebnisse, Timeout-Modell)
- [x] W4 Architekturverträge: CLI-Exit-Code-Tabelle, JSON-Export-Schema, Konfigurations-Schema fail-closed, Schreibpfad-Vertrag mit dokumentierter M-130-Ausnahme
- [x] W5 Wheel-Install-Grenze (TM-12) und Kill-Rate-Kampagnen: suspended_spawn verpflichtend (≥ 80 %), db nachrangig als detached Overnight-Kampagne
- [x] Querschnitt je Welle: Fallinventar nach Zählregeln, echte Laufbelege, offene Grenzen, Produktfehler als neue M-IDs mit rot/grün-Receipts; keine Löschung bestehender Tests
- [x] Gesamtabnahme: Szenario-Matrix TM-01 bis TM-12 vollständig, Pilot-Kill-Raten, Vollsuite grün auf Finalstand
- [x] Release 3.1.0 nach gewohntem Muster (PR, annotierter Tag, GitHub-Release, Housekeeping, Vollsuite-Receipt) und Übergabe-Basis für das externe Review (H1–H4, E-A bis E-F)
