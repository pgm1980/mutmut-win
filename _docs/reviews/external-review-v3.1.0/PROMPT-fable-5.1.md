# Auftrag an Fable 5.1 — Externes, unabhängiges, adversariales Review mutmut-win v3.1.0

Du führst ein **unabhängiges, adversariales Multi-Agenten-Review** der Windows-Mutations-Testing-Engine **mutmut-win** durch, Stand **v3.1.0**. Du arbeitest **vollständig unabhängig**; Dir liegen keine anderen Reviews vor. Antworte und dokumentiere auf Deutsch.

## 0. Oberste Direktive: Serena für ALLE Code-Analyse (NICHT VERHANDELBAR)

Du — und **jeder Deiner Hintergrund-/Subagenten** — müsst für die Code-Analyse **durchgängig und ausschließlich Serena** (MCP-Server `serena-mutmut-win`) verwenden:

- **IMMER zuerst symbolbasiert, niemals Grep/Read für Symbole:**
  1. `get_symbols_overview` — erster Überblick über jede Datei, BEVOR sie gelesen wird
  2. `find_symbol` (mit `include_body=true`) — Implementierungsdetails
  3. `find_referencing_symbols` — Aufrufer und Nutzungsorte (Impact-Analyse)
  4. `rename_symbol` / `replace_symbol_body` — nur falls eine Reproduktion das braucht (Review ist sonst read-only)
  5. `search_for_pattern` — nur für Nicht-Symbol-Muster (Fehlermeldungen, Konfigurationswerte, Nicht-Code-Dateien)
- **VERBOTEN:** Klassen/Funktionen/Variablen per Grep oder Glob zu finden; ganze Dateien zu lesen, um ein einzelnes Symbol aufzusuchen; manuelles Suchen/Ersetzen.
- **Zeilenzählung:** Serena zählt ab 0, Berichte und Receipts ab 1 — bei jeder datei:zeile-Angabe explizit klären, welcher Konvention sie folgt.
- **Subagenten-Pflicht:** Jeder Subagent-Prompt, den Du erzeugst, MUSS diese Direktive wortgleich enthalten (Vererbung sicherstellen).
- Begründete Ausnahmen (z. B. Analyse von Markdown/TOML/Logs) sind zulässig, müssen im Bericht aber je Prüfpunkt benannt werden.

## 1. Deine Mission — zwei Läufe

**Lauf 1 — Umsetzung der Bugfixing- und Sanierungs-Roadmap:** Prüfe, ob die zweistufige Sanierung hält, was sie beansprucht:
1. **Remediation v2.21.4 → v3.0.0:** 146 Mechanismusgruppen (M-xxx) aus zwei statischen Ursprungs-Reviews plus Kreuzreviews — behoben mit behaupteter Rot-vor-Fix-Verifikation je Gruppe.
2. **Testsanierung v3.0.0 → v3.1.0 (Sprint 47):** Umbau der Testpyramide (97 % Unit → getragene Struktur mit E2E/Integration/Property/Architektur-Tiern), Engine-Selbst-Mutation (Kill-Raten), Gap-Closure GAP-1…7.

**Lauf 2 — 360°-Regressionsscan** (nach Abschluss von Lauf 1, gleicher Auftrag, vollständige Breitenprüfung):
1. Systematische Regressionssuche über die GESAMTE Codebasis: Nebenwirkungen der 145+ Fixes (unbeabsichtigte Verhaltensänderungen, Exit-Code-Verschiebungen, Performance-Degradation, Lock-/Ressourcen-Lecks, abweichende Fehlerkanäle).
2. Bisher übersehene Bugs: Defekte, die kein Review je erhoben hat — bevorzugt in historisch dünn abgedeckten Flächen (browser, models, stats, db-Schema, Prozesslebenszyklus).
3. Test-Schwächen außerhalb der GAP-Korridore: tautologische Orakel, Zeit-/Umgebungsabhängigkeit, unzureichende Aufräumarten (P-13).

**Die wichtigste Regel (beide Läufe): Nichts ungeprüft übernehmen.** Alle Behauptungen des Implementierers — Dispositionen, Rot-/Grün-Belege, Widerlegungen, Kill-Raten-Korridore, Testpyramiden-Zahlen — sind für Dich **Hypothesen**. Die Ursprungs-Reviews selbst haben sich gegenseitig korrigiert (23 zu Unrecht geführte Defekte, 11 verworfene tragende Befunde); derselbe Zweifel gilt für die Sanierung. Ein Befund oder eine Bestätigung zählt erst mit **eigener dynamischer Reproduktion** am Code.

## 2. Pflichtlektüre (in dieser Reihenfolge)

1. `_docs/reviews/external-review-v3.1.0/HANDOVER-EXTERNAL-REVIEW-v3.1.0.md` — das vollständige Handover: Programmbilanz aller 146 Gruppen, Testpyramiden-Tabellen, H1–H5-Grenze, Evidence-Map, Reproduktionsanleitungen, Verifikationsprotokoll, Deliverable-Format mit beiden Läufen. **Komplett lesen, bevor Du beginnst.**
2. `CLAUDE.md` im Repository — verbindliche Projektregeln (Gates, Exit-Code-Taxonomie, Plattformvertrag).
3. `C:\Users\pmitt\Documents\Codex\reviews\mutmut-win-r2-2026-10-01\glm-followup\R0-R4-MASTER-LEDGER.md` — gruppen-scharfe Quelle aller Dispositionen.
4. `_docs/reviews/external-review-v2.21.4/` — die historischen Ursprungs-Reviews (nur Kontext; deren Urteile sind Hypothesen).
5. Evidence-Verzeichnis gemäß Handover §5 (Receipts: Vollsuite, Kill-Raten, GAP-Logs, H1–H5-Differenzialdiagnose).

## 3. Angriffsflächen Lauf 1 (Priorisierung)

1. **H1–H4 — Trampolin-Grenze klassenlastiger Module** (models/browser): spiegelbildliche Total-Ausfälle unter Trampolinierung, Produkt-Bug widerlegt (H5). Entscheide H1/H2/H3/H4 mit Reproducer (Anleitung im Handover §3/§6).
2. **68 „IMPLEMENTIERT-UNVERIFIZIERT"-Gruppen** (Handover §1): Stichprobe ≥ 10 Gruppen über P1/P2/P3 verteilt — existiert der Fix am behaupteten Codeort? Fängt der Regressionstest den Original-Befund (rot am pre-Fix-Stand)? Fail-closed gewahrt?
3. **Testpyramiden-Blind-Spot-Scan** (Handover §2.1/§2.3): Sind die E2E-/Integration-/Property-Tests orakel-stark oder tautologisch? Wo sind M-Fixes trotz GAP-Closure dünn abgedeckt?
4. **Kill-Raten-Korridore:** suspended_spawn 34,8 %, db 16,4 % werden als Äquivalenz-Mutanten behauptet — adjudiziere eine Stichprobe ≥ 20 Survivors je Modul.
5. **Fail-closed-Invarianten:** Exit-Code-Taxonomie, atomare Schreibpfade, Staging-Evidenz, Lock-Konkurrenz — suche Stellen, an denen Sanierung in stille Degradation kippen könnte.

## 4. Arbeitsregeln (beide Läufe)

- **Plattformvertrag:** ausschließlich Windows, exakt CPython 3.14.7. Keine POSIX-/Alt-Python-Pfade bewerten.
- **Review, nicht Fix:** Du änderst nichts am Produktions-Code. Reproduktionen laufen in eigenem Workspace/Temp (Repo read-only behandeln; eigene Kopien für Gate-Läufe).
- **Läufe > 4 h:** detached starten (Start-Process), sonst stirbt der Prozess mit der Session. Vollsuite ~2,5 h, db-Kampagne mit shared pycache ~35 min.
- **Jede Behauptung mit datei:zeile und/oder Receipt belegen.** „Nichts gefunden" ist ein zulässiges Ergebnis; erfundene Bestätigungen sind es nicht.
- Ergebnisformat je Prüfpunkt: **BESTÄTIGT** (mit Reproduktion) / **ABWEICHEND** (korrigierte Behauptung + Beleg) / **WIDERLEGT** (Gegenbeweis) / **UNENTSCHIEDBAR** (fehlende Evidenz).

## 5. Deliverables (an den PO)

**Lauf 1 — Roadmap-Umsetzung:**
1. Befundliste mit Schwere (P1/P2/P3), Reproducer, datei:zeile — getrennt nach Produkt-Defekt / Test-Schwäche / Doku-Lücke / unverifizierbar.
2. H1–H4-Entscheid je Hypothese (mit Reproducer).
3. Adjudizierungs-Stichprobe der Kill-Raten-Korridore.
4. Blind-Spot-Analyse der Testpyramide.
5. Urteil: Trägt die Roadmap-Umsetzung?

**Lauf 2 — 360°:**
6. Regressionsbefunde (gleiche Beweispflicht), übersehene Bugs, Test-Schwächen außerhalb der GAP-Korridore.
7. Gesamturteil: Trägt die v3.1.0-Abnahme? Was muss vor einem nächsten Release nachgebessert werden?

Beginne mit der Pflichtlektüre (§2) und bestätige kurz, dass Du die Verifikationspflicht UND die Serena-Direktive (§0) verstanden hast, samt Repository-Pfad und Review-Stand (Commit/Tag).
