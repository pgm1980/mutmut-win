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

Arbeitsstand 2026-10-09: Die Kandidatenledger mit Rot-/Grün-/Rücknahmebelegen
werden fortlaufend je Karte gebunden. Drei integrierte Zwischenstände wurden
mit 224, 317 und 183 bestandenen Regressionstests (im zweiten Lauf ein
dokumentierter Skip) sowie jeweils Ruff, Format, mypy und import-linter
geprüft. Die vier Statikgates bestehen auch nach Integration der kanonischen
Laufzeitnamen, der zusätzlichen Inhaltsgegenlesung und des Clean-Typfilter-Fixes.
Das ist noch keine finale Abnahme. Jeder Beleg behält seinen eigenen
Source-/Test-/Lockstand.

Die Laufzeitnamensprüfung S3-007 hat 12 erfolgreiche CLI-Arme und einen
weiterhin zu qualifizierenden Exportarm am früheren Kandidaten. S3-016 besteht
seine vier echten Clean-Kontrollen; die gezielte Quellrücknahme reproduziert
zwei Fehler. Die Inhaltsgegenlesung für S3-001 besteht 60 gezielte Kontrollen
und die erweiterte Auswahl mit insgesamt 173 PASS und drei Skips; Benchmark und integrierte
Reuse-/Export-Wiederholung folgen. S3-020/030 werden nach ihrer terminalen
isolierten Abnahme integriert.

Alle 220 unverifizierten Karten besitzen individuelle aktuelle Prüfaufträge
und präzise Grenzen in getrennten Registern (95 P2, 125 P3). Statische
Gegenbeobachtungen werden nicht zu dynamischen Fehler- oder Widerlegungsbelegen.
Die sporadischen Basisfehler früherer Läufe bleiben sichtbar; ihre genaue
historische Ursache wird nicht aus dem neuen Hashfix abgeleitet. Der rohe
Dependency-Audit bleibt FAIL. Eine konkrete Semgrep-/Lock-Upgradeoption wird
isoliert für eine PO-Entscheidung über den verbindlichen Pin vorbereitet.

Die vom PO bestätigte Lifecycle-Korrektur gilt identisch für AGENTS.md und
CLAUDE.md: Der ausführbare Vertrag mit 17 Feldern bleibt erhalten. Kein
Sprint-Abschlussflag wird aus diesen Zwischenständen abgeleitet.
