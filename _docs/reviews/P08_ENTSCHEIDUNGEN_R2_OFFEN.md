# P-08 Entscheidungsvorlage R2 — offene Verhaltens-/Vertragsänderungen

**Stand:** 29.09.2026, erstellt während der Nachtphase (Autobetrieb).
**Zweck:** Die verbleibenden R2-Gruppen mit P-08-Relevanz benötigen Ihre dokumentierte Entscheidung, bevor die jeweiligen APs sie umsetzen (Prinzip P-08). Jede Karte: Problem → Optionen → Empfehlung (aus der Gegenprüfung des Handovers) → Konsequenzen.
**Format:** Bitte je Gruppe „A" / „B" / „C" ankreuzen oder abweichend formulieren. Die Empfehlung ist jeweils die im Handover tragfähig bewertete Variante.

---

## 1. M-061 · AP-11 · Core-Fingerprinting & Gitignore-Grenze im Flat-Layout

**Problem:** Die Core-Hasher (`_hash_project_import_core`, Editable-Kern) walken ohne Gitignore-Boundary; gitignorierte Laufartefakte können einen Lauf fail-closed als „failed" beenden. Der symmetrische Fix (Boundary überall) hat im Flat-Layout (Self-Editable, Projektwurzel bleibt im Kind-sys.path) eine Aufweichung: Ein ignoriertes, in-place importierbares Top-Level-Modul wäre danach in **keinem** Digest mehr sichtbar.

- **A (Empfehlung):** Symmetrische Boundary überall — README 545–549 („ignoriert = keine Basis") wird eingelöst; Restrisiko im Flat-Layout wird als akzeptiert dokumentiert und per Test festgeschrieben. Der kombinierte Digest bindet diese Dateien heute bereits nicht.
- **B:** Import-Roots, die im Kind auf sys.path bleiben, ohne Boundary weiterwalken — strenger fail-closed, erhält aber die Asymmetrie genau für diese Roots (zwei Klassen von Wurzeln, kompliziertere Verträge).

## 2. M-064/M-101 Stufe 2 · AP-12 · Lazy Endabgleich der Ausführungsbasis (5 → 4 Pässe)

**Problem:** Jeder erfolgreiche Lauf berechnet die Ausführungsbasis fünfmal vollständig (Prelude ×2, Schritt 3, Abschluss ×2). Stufe 2 (Kurzschluss bei exakter Gleichheit mit der Startbasis) ist eine Vertragsänderung: Ändert sich die Umgebung nach Worker-Ende während des ersten Abschlusspasses, endet der Lauf heute „failed"/deautorisiert, mit Stufe 2 „completed" mit `execution_basis_complete=True`.

- **A (Empfehlung):** Stufe 2 umsetzen — Verdikte sind unberührt (Worker beendet, Job geschlossen), der CI/CD-Export prüft den Live-Stand erneut (`_stable_live_basis`); Verhalten im ADR/Docstring + README dokumentiert. Zusätzlich Stufe 1 (Watchdog-Abdeckung für Schritt 3 + Abschluss) und Benchmark.
- **B:** Stufe 2 zurückstellen — nur Stufe 1 + Benchmark; Performance-Befund bleibt teilweise offen (Status „per Nutzerentscheidung zurückgestellt").

## 3. M-058 · AP-15 · Browser-Retest „Modul" bei Paket-__init__

**Problem:** `action_retest_module` leitet den Scope textuell ab; bei Mutanten aus `__init__.py` selektiert das Muster `pkg.*` den ganzen Paketbaum. Fix: exakte Namensliste für `__init__`-Dateien. Darüber hinaus (Verhaltensänderung): Für **nicht zugeordnete** Namen (DB-only/unmapped) wird die Aktion verweigert statt geraten.

- **A (Empfehlung):** Verweigerung bei fehlender Zuordnung (fail-closed; als Verhaltensänderung markiert, getestet, im README dokumentiert).
- **B:** Altes Muster mit Warnung bei fehlender Zuordnung (weniger strikt, rät weiter).

## 4. M-022 · AP-16 · --since-commit: Options-/Pathspec-Injektion und Bereichssyntax

**Problem:** Der Wert wird unvalidiert an `git diff` übergeben (Options- und Pathspec-Deutung möglich). Fix: Validierung per `git rev-parse --verify --end-of-options`, nur kanonische OID + `--` an `git diff`; ungültige Werte → Exit 2. Entscheidungspunkt: Bereichsausdrücke (`A..B`, `main...HEAD`), die heute undokumentiert funktionieren, werden von `rev-parse --verify` abgelehnt.

- **A (Empfehlung):** Bereiche bewusst mit Exit 2 ablehnen (Breaking Change der undokumentierten Syntax, CHANGELOG + Fehlerhinweis auf `git merge-base`).
- **B:** Die `...`-Form gezielt über `git merge-base --end-of-options A B` zu einer OID auflösen (unterstützt verbreitete CI-Nutzung; zweiter Prozessstart, mehr Aufwand).

## 5. M-023 · AP-16 · Positivfilter für inkrementelle Ziele

**Problem:** Der since-commit-Filter ist ein reiner Negativfilter gegen exakt konfigurierte `tests_dir`; geänderte Testdateien außerhalb davon (z. B. `tests/conftest.py` bei `tests_dir=['tests/unit/']`) werden Mutationsziele. Fix-Ansatz: Positivfilter — Ziel nur, wenn unter `paths_to_mutate`. Verhaltensänderungen: Dateien außerhalb `paths_to_mutate` (scripts/, setup.py) fallen inkrementell weg (volllaufkonsistent); `--paths-to-mutate` + `--since-commit` wird Schnittmenge statt Ersetzung.

- **A (Empfehlung):** Positivfilter wie beschrieben (inkrementelles Universum nie größer als Volllauf; CHANGELOG-Eintrag).
- **B:** Minimalfix — nur tests_dir-Ausschluss kanonisieren/erweitern (heuristic, verfehlt Hilfsmodule wie `tests/factories.py`, löst scripts/-Fall nicht).

## 6. M-036 · AP-22 · Lockdomäne der Cache-Datenbank (ADR erforderlich)

**Problem:** Die DB-Lockschlüssel hängen an `tempfile.gettempdir()` — zwei Prozesse mit divergierendem TEMP erwerben beide den „exklusiven" DB-Lock; `_recover_abandoned_run` beendet fremde Läufe. Fix-Richtung: Lockdomäne an das kanonische DB-Elternverzeichnis binden (Colocation). Vertragstests (3 Hardlink-Tests) brechen bewusst; Lockdateien liegen sichtbar im DB-Verzeichnis; schreibgeschützte DB-Verzeichnisse scheitern früher.

- **A (Empfehlung):** Colocation im kanonischen DB-Elternverzeichnis — global pro DB, kein Temp-Fallback, Hardlink-DB fail-closed (`RunLockCorruptError`), `_basis_excluded_paths` um Lock-/Guard-Pfade erweitert, ADR-Nachtrag.
- **B:** Per-User Known-Folder (LocalAppData) — kleiner Eingriff, behebt nur divergierende TEMP desselben Benutzers, verschiedene Benutzer bleiben getrennt, Docstring wird „per-user".
- **C:** ProgramData maschinenweit — echte Globalität, aber ACL-/Squatting-Problematik, Security-Review, Aufwand L+.

## 7. M-041 · AP-24 · NFKC-Kodierung von Mutanten-IDs (identitätsändernd)

**Problem:** NFKC-äquivalente Top-Level-Namen (K vs. Ｋ U+FF2B) kollidieren in den privaten Trampoline-Bindungen. Fix: vorhandene kollisionssichere Hex-Kodierung (`xq_`) zusätzlich wählen, wenn der Name nicht NFKC-normal ist. Entscheidbar ist die Breite:

- **A (Empfehlung):** **Alle** nicht-NFKC-normalen Namen erhalten neue xq-IDs, auch ohne Kollision — deterministisch und kontextunabhängig; alte IDs solcher Funktionen verwaisen (Cache, dokumentiert wie bei der Ordinal-Einführung; Anzeige hex-kodiert).
- **B:** Nur bei tatsächlicher NFKC-Kollision — IDs würden durch fremde Funktionen im selben Modul ändern (kontextabhängig, vom Review abgelehnt).

## 8. M-102 · AP-27 · Timeout-Modell: Diagnosezeile (Pflicht nur Docstring)

**Problem:** Der dokumentierte „selected test time"-Budgetzweig ist unerreichbar (`mapping_is_authoritative` ist nie True); jede Task erhält das Full-Suite-Budget. Pflichtfix ist reine Docstring-Korrektur (kein P-08). Separat freigabepflichtig: eine zusätzliche stdout-Zeile je Lauf („per-test budgets are inactive because the test mapping is not authoritative…"), wenn Fallback-Tasks mit Timingdaten existieren.

- **A (Empfehlung):** Diagnosezeile freigeben — geht im JSON-Modus über den bestehenden stdout→stderr-Redirect, JSON-Kanal bleibt sauber; bestehende Negativassertionen der Tests werden gezielt gewählt.
- **B:** Nur Docstring; Zeile zurückstellen (Status „per Nutzerentscheidung zurückgestellt").

## 9. M-016 · AP-29b · Case-insensitives Gitignore-Matching + pathspec-Pin

**Problem:** Das Ignore-Matching ist case-sensitiv, Git unter Windows (`core.ignorecase=true`) nicht — ignorierte Bäume landen im Basis-Hash; Negationsmuster verfehlen Treffer. Fix: ASCII-Faltung `(?ai)` über eine private pattern_factory. P-08-relevant sind außerdem die Straffung des pathspec-Pins (`>=1.1.1,<2` → `<1.2`, Abhängigkeitsvertrag, eigener chore(deps)-Commit mit uv.lock-Beleg) und der einmalig geänderte Baumdigest betroffener Projekte.

- **A (Empfehlung):** ASCII-Faltung `(?ai)` + Pin-Straffung auf `<1.2` mit Guard-Test (Windows-Produktvertrag; Git faltet per tolower nur ASCII, daher ASCII statt Unicode-Faltung).
- **B:** `core.ignorecase` per `git config --bool` lesen und nur dann falten — exakt git-konform, zusätzlicher Prozess/Config-Parsing pro Lauf.
- **C:** Zurückstellen — Matching bleibt case-sensitiv, Limitierung wird nur dokumentiert (Basis-Hash-Defekt bleibt bestehen).

---

## Zusätzlich zu bestätigen (keine neue Entscheidung, aber P-08-relevant)

- **M-042 · AP-23 (Abweichung von Upstream):** Der Subagent hat die gesperrte dekorierte Klasse **dokumentiert** (Commit `e9bfbee`, technische Begründung) statt das Verhalten zu ändern. Bitte bestätigen: Dokumentationsroute OK ☐ oder Verhaltensänderung gewünscht ☐.

## Abhängigkeit der Entscheidungen von ausstehenden APs

| Entscheidung | blockiert AP | Status des AP |
|---|---|---|
| M-061 | AP-11 (Teil) | AP-11 läuft (M-060 umgesetzt, M-061 wartet auf Entscheidung) |
| M-064/M-101 S2 | AP-12 (Teil) | AP-12 wartet auf AP-11 |
| M-058 | AP-15 (Teil) | wartet auf AP-14 |
| M-022/M-023 | AP-16 (M-021/M-024 nicht blockiert) | wartet auf AP-14 (cli.py-Mutex) |
| M-036 | AP-22 (M-093 nicht blockiert) | wartet auf AP-12 |
| M-041 | AP-24 (M-040/M-039/M-044 nicht blockiert) | wartet auf AP-23 |
| M-102 | AP-27 (M-053/M-103 nicht blockiert) | wartet auf AP-12 |
| M-016 | AP-29b (M-017-Redesign separat) | wartet auf AP-29 |

**Hinweis:** Nicht-blockierte Geschwistergruppen der jeweiligen APs werden unabhängig von diesen Entscheidungen umgesetzt; nur die P-08-Gruppen selbst warten.
