# Review-Pipeline v3.1.0 — Unabhängig, Kreuz, Kreuz-Kreuz

**Stand:** 2026-10-07 · **Basis:** v3.1.0 (PR #199 / Tag folgt) · **Organisation:** PO
**Prinzip:** Zwei externe, adversariale Multi-Agenten-Reviews **unabhängig voneinander** (kein Team weiß vom anderen). Danach zwei Kreuzreviews und ein Kreuz-Kreuz-Review. Jede Stufe erhält nur die für sie bestimmten Dokumente.

## Stufenübersicht

| Stufe | Wer | Input | Prompt | Output |
|---|---|---|---|---|
| **S1a** | Fable 5.1 (Multi-Agenten) | Repo v3.1.0 + Evidence + Handover-MD | `PROMPT-fable-5.1.md` (inkl. Serena-Oberdirektive §0) | `REPORT-fable-s1.md` (Lauf 1: Roadmap-Umsetzung + Lauf 2: 360°-Regressionsscan) |
| **S1b** | GPT-6 Astra (Multi-Agenten) | Repo v3.1.0 + Evidence + Handover-MD | `PROMPT-gpt6-astra.md` (inkl. Serena-Oberdirektive §0) | `REPORT-gpt6-s1.md` (Lauf 1 + Lauf 2) |
| **S2a** | Fable 5.1 | `REPORT-gpt6-s1.md` + eigener S1a-Bericht | `PROMPT-cross-fable-on-gpt.md` (bei Start aus Vorlage §S2 erzeugen) | `CROSSREPORT-fable-on-gpt.md` |
| **S2b** | GPT-6 Astra | `REPORT-fable-s1.md` + eigener S1b-Bericht | `PROMPT-cross-gpt-on-fable.md` (Vorlage §S2) | `CROSSREPORT-gpt-on-fable.md` |
| **S3** | Drittes LLM (nicht Fable, nicht GPT-6) | beide S1-Berichte + beide Kreuzberichte | `PROMPT-crosscross.md` (Vorlage §S3) | `FINAL-VERDICT.md` |

**Serena-Oberdirektive (gilt für ALLE Stufen):** Jedes Review-Team und alle dessen Hintergrund-/Subagenten verwenden durchgängig und ausschließlich Serena (`serena-mutmut-win`) für Code-Analyse (get_symbols_overview → find_symbol → find_referencing_symbols); Grep/Read für Symbole ist verboten. Jede erzeugte Subagent-Prompt-Datei enthält die Direktive wortgleich.

## Ablaufregeln

1. **S1a und S1b starten zeitgleich, vollständig isoliert** (eigene Workspaces, keine Kenntnis des anderen Teams, keine gemeinsamen Dateien außer Repo+Evidence read-only).
2. S2 startet erst, wenn beide S1-Berichte vorliegen. Der Kreuzreviewer **verifiziert adversarial** den fremden Bericht am Code — derselbe Verifikationszwang wie in S1 (nichts ungeprüft übernehmen; dynamische Reproduktion).
3. S3 bewertet alle vier Dokumente: Widersprüche zwischen S1a/S1b, Qualität der Kreuzauflösungen, Restrisiken. S3 entscheidet Streitfälle nicht per Mehrheit, sondern per eigener Reproduktion.
4. **Änderungsverbot:** Kein Stadium dieser Pipeline ändert Produktions-Code. Findings gehen als belegte Vorschläge an den PO.
5. Alle Berichte in `_docs/reviews/external-review-v3.1.0/` ablegen; Repo-Commits nur über den PO.

## Vorlage §S2 — Kreuzreview-Prompt (Platzhalter <FREMD> / <EIGEN>)

```text
# Auftrag an <REVIEWER> — Kreuzreview: <FREMD>-Bericht über mutmut-win v3.1.0

Dir liegt der Erstbericht <FREMD_REPORT>.md eines anderen unabhängigen
Review-Teams vor, zusätzlich Dein eigener Erstbericht <EIGEN_REPORT>.md.

Deine Aufgabe: Prüfe JEDE Behauptung des fremden Berichts adversarial am
Code — dieselbe Verifikationspflicht wie im Erstreview (Reproduktion vor
Bewertung; BESTÄTIGT/ABWEICHEND/WIDERLEGT/UNENTSCHIEDBAR je Behauptung,
mit datei:zeile und Reproducer).

Schwerpunkte:
1. Technisch falsche Behauptungen (dynamisch widerlegbar?).
2. Überbewertete Schwere (ist der Pfad unter Windows/CPython 3.14.7 mit
   dokumentierter Konfiguration erreichbar? fängt eine vorgelagerte
   Prüfung ab?).
3. Vom fremden Team übersehene Defekte (aus Deinem eigenen S1-Bericht:
   welche Deiner Findings wurden nicht gefunden? warum?).
4. Übereinstimmende Findings beider Teams (Konsolidierung mit Belegen).

Liefer: CROSSREPORT-<fremd-gerichtet>.md mit je Behauptung: Urteil,
Beleg, korrigierte Schwere falls abweichend. Keine Fixes; Repo read-only.
Basis: HANDOVER-EXTERNAL-REVIEW-v3.1.0.md §7 (Verifikationsprotokoll).
```

## Vorlage §S3 — Kreuz-Kreuz-Review-Prompt

```text
# Auftrag an <DRITTES_LLM> — Kreuz-Kreuz-Review mutmut-win v3.1.0

Dir liegen vier Dokumente vor: die beiden unabhängigen Erstberichte
(REPORT-fable-s1.md, REPORT-gpt6-s1.md) und die beiden Kreuzberichte
(CROSSREPORT-fable-on-gpt.md, CROSSREPORT-gpt-on-fable.md).

Deine Aufgabe:
1. Widerspruchs-Analyse: Wo widersprechen sich die Erstberichte? Wer
   hatte recht (eigene Reproduktion entscheiden lassen, nicht Mehrheit)?
2. Kreuz-Qualität: Haben die Kreuzreviews die Behauptungen des fremden
   Berichts tatsächlich am Code verifiziert oder nur plausibilisiert?
   Zitate prüfen, Reproducer nachziehen (Stichprobe).
3. Restrisiko: Welche Flächen hat KEIN Team geprüft (Abdeckungsmatrix)?
4. Konsolidiertes Finalverdict je offener Frage (H1-H4, Kill-Raten-
   Korridore, 68 unverifizierte Gruppen, Testpyramide):
   BESTÄTIGT/WIDERLEGT/UNENTSCHIEDBAR mit Deinem eigenen Beleg.
5. Empfehlung an den PO: Nachbesserungs-Liste VOR einem nächsten
   Release, mit Priorität.

Basis: HANDOVER-EXTERNAL-REVIEW-v3.1.0.md. Keine Fixes; Repo read-only.
Liefer: FINAL-VERDICT.md.
```

## Verzeichnis dieses Pakets

| Datei | Zweck |
|---|---|
| `HANDOVER-EXTERNAL-REVIEW-v3.1.0.md` | Vollständiges Handover (Programmbilanz 146 Gruppen, Testpyramide, H1–H5, Evidence, Protokoll) |
| `PROMPT-fable-5.1.md` | Stufe S1a — unabhängiges Review |
| `PROMPT-gpt6-astra.md` | Stufe S1b — unabhängiges Review |
| `README-review-pipeline.md` | Diese Datei: 5-Stufen-Pipeline + Vorlagen für S2/S3 |
