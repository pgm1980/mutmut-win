# ADR: Layer Contracts v2 — Realignment der import-linter-Schichten

**Status:** Accepted (Sprint 29, 2026-06-11)
**Issue:** [#84](https://github.com/pgm1980/mutmut-win/issues/84)
**Entscheidungsverfahren:** Sequential-Thinking-Session (nextgen-cot), Optionenanalyse + Kanten-Verifikation; Audit-Grundlage `_docs/audit/sprint_27_audit_findings.md`.

## Kontext

`uv run lint-imports` war über mehrere Sprints rot, ohne dass es auffiel —
das Gate wurde in den Sprint-Abschlüssen 23–26 nachweislich nie ausgeführt
(Sprint-28-Befund: identische Verletzungen auf dem Sprint-Start-Stand
`015cf32`). Die deklarierte Schichtung
`cli|browser → orchestrator|runner|mutant_diff → domain → process`
hat der realen, gewollten Architektur nie entsprochen:

- `process.worker`/`process.executor` konsumieren die **Event-/Task-Modelle**
  (`models`) — das IST der IPC-Vertrag des Pools, kein Unfall.
- `orchestrator` treibt `runner` direkt; `stats` kapselt runner-gestützte
  Collection — die Anwendungsschicht kooperiert by design.
- `cli` startet den TUI-`browser` (browse-Command).
- `mutation` orchestriert `node_mutation` + `trampoline` — ein kohäsiver
  Engine-Verbund, kein Schichtverstoß.
- `|`-getrennte Module derselben Ebene sind bei import-linter **independent**
  (dürfen einander nicht importieren) — das war für diese Paare nie gewollt.

## Entscheidung

Realignment statt Code-Umbau oder Contract-Löschung: Der Contract beschreibt
die **beabsichtigte** Architektur mit fünf Bändern (oben → unten); `:`
markiert Geschwister, die einander absichtlich nutzen dürfen:

```
1  cli : browser                                        — UI-Paar
2  orchestrator : runner : stats : mutant_diff          — Anwendungs-/Koordinationsband
3  file_setup : mutation : node_mutation :              — Engine-Band (Codegen,
   regex_mutation : trampoline : test_mapping :           Persistenz, Analyse-Dienste)
   db : type_checking : type_checker_filter :
   code_coverage
4  process                                              — Infrastruktur (Pool/Worker/Jobs)
5  config : models : constants : exceptions : _state    — Shared Kernel (reine Daten/
                                                          Validierung/Tabellen)
```

**Shared-Kernel-Begründung (Band 5 unter `process`):** `models`,
`constants`, `exceptions`, `config`, `_state` sind verhaltensfreie
Datenstrukturen/Tabellen ohne Aufwärts-Importe. Domänenmodelle als unterste
Schicht sind orthodoxe Schichtenarchitektur — die alte Annahme „process ist
der Boden" scheiterte daran, dass ein Worker die Events, die er emittieren
muss, nicht sehen durfte.

## Was der Contract weiterhin verbietet (Werttest)

- Kernel-Module importieren NIE aufwärts (z. B. `models` → `orchestrator`).
- `process` erreicht weder Engine- noch Anwendungsband (kein Worker-Zugriff
  auf `mutation`/`file_setup`).
- Das Engine-Band ruft nie `orchestrator`/`runner`/`cli`.
- Nichts unterhalb von Band 1 importiert die UI.
- Querschüsse über Bandgrenzen (z. B. `db` → `runner`, `trampoline` →
  `process`) bleiben illegal.

`:`-Geschwister lockern NUR innerhalb kohäsiver Bänder; die vertikale
Ordnung bleibt vollständig erzwungen. Bewusster Trade-off: Importe
*innerhalb* eines Bandes sind unbeschränkt — verfilzt ein Band, wird es per
Folge-ADR gesplittet.

## Verworfene Optionen

- **(A) Code-Umbau auf den alten Contract** (models aus der process-Reichweite
  ziehen, orchestrator/runner entkoppeln): paketweiter Refactor ohne
  Verhaltensnutzen, weit jenseits von 3 SP, hohes Regressionsrisiko direkt
  nach einem 200-Findings-Audit.
- **(B) Contract löschen:** durch CLAUDE.md verboten und sachlich falsch —
  die vertikale Ordnung hat realen Schutzwert (s. o.).
- **TYPE_CHECKING-Importe ausnehmen** (`exclude_type_checking_imports`):
  unnötig (die einzige Typ-Kante `executor → config` zeigt ohnehin in den
  Kernel) und das strengere Gate ist vorzuziehen.

## Konsequenzen / Durchsetzung

- `[tool.importlinter]` in `pyproject.toml` trägt den neuen Contract.
- **Das Gate läuft jetzt wirklich:** `tests/test_architecture.py::
  test_import_linter_contracts_hold` führt `lint-imports` als Subprozess aus
  und schlägt mit dem Report fehl — jede `uv run pytest`-Ausführung erzwingt
  den Contract; ein vergessenes Sprint-Gate ist nicht mehr möglich.
- Nicht gelistete Module (`__init__`, `__main__`) sind Entry-Points außerhalb
  der Bänder.
