# S3-Sanierungsplan

Ausgangspunkt ist der versiegelte S3-Auftrag mit 270 finalen Karten.
`SANIERUNGSLEDGER.json` führt jede ID getrennt nach Produkt, Test,
Dokumentation oder offener Verifikation. Maßgeblich sind die finalen Karten,
nicht historische Prioritäten oder frühere Gate-PASS-Meldungen.

1. Vorbestand sichern: Branch/HEAD, Dirty-/Ignore-Inventar, Source und Lock,
   Prozesse sowie vorhandene Receipts. Vollständiges S3-Manifest und
   geschütztes Endinventar verifizieren. Implementierung nur in isolierten Worktrees.
2. S3-001 bis S3-003 zuerst: Rot gegen unveränderte Quelle, Fix,
   isolierte Rücknahme des kausalen Quellpatches, Grün, gesunde Gegenarme
   und echte CLI-/Run-/Scorebindung. Alle Produktionsaufrufer prüfen.
3. P2-Produkte S3-004 bis S3-015, danach P2-Testkarten bearbeiten.
   Parallelität nur bei unabhängigen Mechanismen und separaten Edit-Worktrees.
4. P3-Karten und offene Verifikationsaufträge bearbeiten. Ein offener Claim
   erhält erst nach eigener Prüfung ein Fehlerurteil; fehlende Feldinputs
   bleiben als konkrete Evidenzgrenze sichtbar.
5. Änderungen integrieren, Source-/Test-/Lockstand einfrieren und alle
   vorgeschriebenen Finalgates selbst ausführen. Mutation auf allen
   geänderten Modulen mit Population, Aktivierungsnachweis und mindestens
   20 Survivor-Prüfungen je Modul, sofern so viele Survivor existieren.
6. Einzelbilanz aus terminalen Receipts, präzise Restgrenzen und ehrliche
   Abnahmeentscheidung erstellen. Original und eingefrorene Übergabe
   abschließend gegen die gesicherten Inventare prüfen.

Alle 21 Arbeitsregeln aus `ASTRA-SANIERUNGSAUFTRAG.md` gelten. Receipts
enthalten Kommando, CWD, exakte Runtime, Start/Ende/Exit sowie Source-,
Test- und Lockhashes. Kandidaten-/Finalgates erhalten jeweils frische
externe uv-Umgebungen; Hypothesis, pytest, Coverage und Werkzeugcaches
liegen außerhalb der Checkouts.

Klärungen erfolgen über Sol, Thread `01a11c92-5bd7-7290-ba30-84ef23c1c1d6`.
Anfragen nennen diese Implementierungssession
`01a11fac-70d2-7880-8a58-8db2ac2df94e`, S3-IDs, genaue Normstelle und
eigene Interpretation. Antworten werden im Ledger gebunden. Sie sind
keine Ersatzabnahme der Implementierung.

Arbeitsstand 2026-10-09: Auf ausdrückliche PO-Anweisung nach Abschluss der
drei vorhandenen Agentenaufträge und der begonnenen Hauptsession-Integration
pausiert. Verbindlicher Fortsetzungscheckpoint: `PO-PAUSE.md`; maschinenlesbar
`SANIERUNGSLEDGER.json` mit allen 270 S3-IDs und eigenständiger Evidenzbindung.

Die Kandidaten aller 50 konkreten Karten sind integriert. Für die 220 zunächst
unverifizierten Karten bleiben individuelle Prüfaufträge und Grenzen erhalten
(95 P2, 125 P3). Statische Beobachtungen begründen kein pauschales Fehlerurteil.

Eigene Prüfung des Code-/Test-/Lockstands c373982: 80 ausgewählte Vertragstests,
Ruff, Format, mypy strict, import-linter, kanonisches Semgrep, nativer
Release-Wrapper und vollständiger Environment-Audit PASS. Der Audit umfasst
130 Windows-Abhängigkeiten inklusive pip und packaging ohne gemeldete
Schwachstellen oder Skips. Semgrep 1.180.0/PyJWT 2.15.1 sind ausdrücklich vom
PO genehmigt und integriert; CI prüft jetzt zusätzlich die frische volle
Lock-Umgebung. Historische rote Belege bleiben unverändert nachvollziehbar.

S3-001: Inhaltshash-Gegenkontrollen und begrenzter Vorher-/Nachher-Benchmark
abgeschlossen; höhere Laufzeitkosten ausdrücklich dokumentiert. S3-016:
positive Clean-Phasen-/Token-/Exitbeobachtung und identisch gebundener
Rot-/Grünvergleich liegen vor. S3-020/030 sind integriert. Der abschließende
CLI-/Reuse-/Exportumfang samt eigener Source-/Test-/Lockbindung steht in
`PO-PAUSE.md` und im verlinkten terminalen Agentenledger.

AGENTS.md und CLAUDE.md enthalten beide den vom PO bestätigten ausführbaren
17-Felder-Lifecyclevertrag und den genehmigten Semgrep-Pin. Der Reviewer hat
seine begonnenen Gegenprüfungen abgeschlossen und pausiert. Seine Antworten
erteilen keine Releasefreigabe.

Die vollständige integrierte pytest-Suite mit Coverage und die tatsächliche
Mutation des geänderten Produktionscodes bleiben NOT_EXECUTED am finalen
integrierten Stand. Historische Basis-/Exportfehler werden nicht rückwirkend
dem neuen Hashfix zugeschrieben. Weiterhin NO-GO; keine Sprint-Abschlussflags.
Keine neuen Aufgaben oder Kampagnen bis zur ausdrücklichen Wiederaufnahme.
