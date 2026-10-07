# HANDOVER — Externes adversariales Multi-Agenten-Review mutmut-win v3.1.0

**Datum:** 2026-10-07 · **Review-Stand:** v3.1.0 (Branch `fix/v3.1.0-testsanierung`, PR #199; Tag/Release folgen unmittelbar)
**Plattformvertrag:** ausschließlich Windows, exakt CPython 3.14.7 · **Repository:** `C:\claude_codex\mutmut-win` (GitHub pgm1980/mutmut-win)
**Adressaten:** Zwei unabhängige Review-Teams (Fable 5.1 bzw. GPT-6 Astra) — voneinander unabhängig, ohne Kenntnis voneinander. Danach Kreuzreviews (Fable-on-GPT, GPT-on-Fable) und ein Kreuz-Kreuz-Review durch ein drittes LLM.

---

## 0. Review-Auftrag in einem Satz

Prüfe adversarial, ob die Sanierung v2.21.4 → v3.1.0 (146 Mechanismusgruppen + Testsanierung Sprint 47) hält, was sie beansprucht — **vertraue keinem Claim ohne eigene dynamische Reproduktion am Code** (exakt dieselbe Verifikationspflicht, die der Implementierer hatte; siehe §7).

## 1. Ursprung und Programmbilanz R0–R4 (v2.21.4 → v3.0.0)

**Ursprungsauftrag (Kurzfassung):** Zwei unabhängige statische Reviews (Claude, Astra), zwei Kreuzreviews und ein Abschlussbericht erhoben gegen v2.21.4 (`4d7f950679e3f78d906b3b068e01a0ee5dcb5a4d`) **146 Mechanismusgruppen mit tragendem Defekt** (9 high/P1, 56 medium/P2, 81 low/P3, kein critical), geordnet in 51 Arbeitspakete und 5 Phasen (R0 Vorbereitung, R1 P1-Ergebnisintegrität, R2 P2, R3 P3, R4 Integration). Der Implementierer (GLM-5.3) hatte die Pflicht, jeden Befund vor dem Fix selbst am Code zu verifizieren (bestätigt / abweichend / widerlegt / nicht entscheidbar) und jeden Fix durch einen vorher roten Regressionstest zu belegen.

**Gesamtrechnung zum 3.0.0-Stand** (Quelle: `R0-R4-MASTER-LEDGER.md`, 325 Zeilen, gruppen-scharf):

| Status | Gruppen | Anzahl |
|---|---|---:|
| IMPLEMENTIERT, Receipt-Validierung offen | M-010, M-012, M-013, M-027, M-028, M-029, M-030, M-037, M-045, M-046, M-047, M-048, M-049, M-062, M-063, M-066, M-067, M-069, M-077, M-078, M-079, M-080, M-082, M-083, M-093, M-098, M-099 | 27 |
| IMPLEMENTIERT (keine dokumentierte Lücke) | M-114, M-139, M-021, M-024, M-039, M-040, M-044, M-055, M-057, M-059, M-060, M-064, M-071, M-088, M-111, M-116, M-127, M-128 | 18 |
| IMPLEMENTIERT, Requalifizierung lief | M-018, M-019, M-025, M-026, M-035, M-053, M-056, M-073, M-074, M-075, M-103, M-113, M-115 | 13 |
| IMPLEMENTIERT, Receipt fehlt (Issue-Mention ohne Beleg, 2026-10-02 validiert) | M-031, M-034, M-142, M-143, M-145, M-033, M-054, M-065, M-095, M-110 | 10 |
| R3 IMPLEMENTIERT+ROT/GRÜN VERIFIZIERT (`d122761`) | M-132 … M-138, M-141 | 8 |
| HISTORISCH QUALIFIZIERT (R1) | M-002, M-003, M-004, M-007, M-008 | 5 |
| REQUALIFIZIERT (Trampoline-Gate 66,7 % raw / ~93,6 % adjudiziert) | M-038, M-043, M-050, M-051, M-052 | 5 |
| R3 VERIFIZIERT (`02a3673`) | M-117, M-118, M-119, M-120 (browser) | 4 |
| ABGESCHLOSSEN (Doc/Test-only) | M-014, M-015, M-072 | 3 |
| R3 VERIFIZIERT (`21633c3`) | M-090, M-091, M-092 | 3 |
| R3 VERIFIZIERT (`48bb265`) | M-121, M-122, M-123 (models) | 3 |
| R3 VERIFIZIERT (`0538af7`) | M-124, M-125, M-126 | 3 |
| R3 VERIFIZIERT (`d549ca3`) | M-068, M-070 | 2 |
| R3 VERIFIZIERT (`afbc6cf`) | M-085, M-086 | 2 |
| R3 VERIFIZIERT (`97edbda`) | M-094, M-096 | 2 |
| R3 VERIFIZIERT (`9eb576e`) | M-104, M-108 | 2 |
| R3 VERIFIZIERT (`e9e650f`) | M-105, M-106 | 2 |
| NACHBESSERT+VERIFIZIERT (AR-01…AR-24, P-08-Entscheidungen) | M-001, M-005, M-006, M-009, M-011, M-016, M-017, M-020, M-022, M-023, M-032, M-036, M-041, M-042, M-058, M-061, M-076, M-100, M-102, M-140, M-144 (je 1) | 21 |
| BENCHMARK VORLIEGEND (`ec8bd4d`) | M-101 | 1 |
| R3 VERIFIZIERT (Einzelnachweise) | M-081, M-084, M-087, M-089, M-107, M-109, M-112, M-129, M-130, M-131, M-146 (je 1) | 11 |
| OFFEN (R3 nie begonnen; **in v3.1.0 nachgeholt**, siehe §2) | M-097 | 1 |
| **GESAMT** | | **146** |

**Dreistufige Bilanz 3.0.0:** VERIFIZIERT 77/146 (52 %) · IMPLEMENTIERT-UNVERIFIZIERT 68/146 (46 %) · OFFEN 1/146.
**Adnahmequote (nicht-OFFEN):** 145/146 = 99 %.

**Verifikationspflicht für das Review:** Die 68 „implementiert-unverifiziert"-Gruppen sind die primaire Angriffsfläche: Hier fehlt der Rot-vor-Fix-Beleg bzw. die Receipt-Validierung. Stichproben ziehen und prüfen, ob der Fix a) tatsächlich am beschriebenen Codeort wirkt, b) einen Regressionstest hat, der den Original-Befund wirklich fängt, c) fail-closed bleibt.

## 2. v3.1.0 — Testsanierung Sprint 47 (Issue #198, PR #199)

**Auslöser:** PO-Diagnose der Wiederholungsmuster schwerer Produktbugs (v1, v1.9, 2.20.1, 2.21.4 — jeweils erst durch externe adversariale Reviews gefunden): Testpyramide mit 97 % Unit-Schwergewicht, 52,9 % der Unit-Tests gemockt, 0 echte E2E-Tests, quantifizierte Testblindheit über Modul-Gate-Kill-Raten. Sanierung nach Testspezifikation v2 (`_docs/testmanagement/test_specification.md`) mit Enabler-TDD und Kill-Raten-Abnahme.

### 2.1 Testpyramide: vorher → nachher

| Tier | v2.21.4 (vorher) | v3.1.0 (nachher) | Belege |
|---|---|---|---|
| **E2E** (echte CLI-Läufe, echte Kampagnen) | **0** echte E2E | **~27 Fälle**: Full-Run über 6 Fixture-Projekte, Error-Paths mit Campaign-E2E (Kill→Restart→Resume), Config-Fail-Closed-Kette, Browser-Diff nach Kampagne (results/show/apply), Interrupt-Finalisierung (echtes Ctrl-C via Konsolen-Hilfsprozess), Wheel-Install-Grenze, Pycache-Korrektheit/-Integration | `tests/e2e/*`, Receipts gap1/gap4-7 |
| **Integration** | ~15 Fälle, FS/Prozess kaum abgedeckt | **~45 Fälle**: Windows-FS-Korridore ×10 (Junctions, Sharing-Violation, Readonly, Normcase, Long-Path, Surrogate), Prozesslebenszyklus ×3 (Tree-Kill, Runtime-Root, Pool-Collapse), Atomic-Crash-Recovery ×6, Mutation-Operator-Korrektheit ×5, Staging-Drift ×2, Lock-Konkurrenz ×2 | `tests/integration/*` |
| **Property** (@given/Hypothesis) | **0** | **60 Fälle** + wiederverwendbare `strategies.py`, Profile ci/default/nightly (Serialisierung, Fingerprint-Stabilität, Timeout-Modell, Pfad-Invarianten, Score-Arithmetik, Statistik) | `tests/unit/properties/*` |
| **Architektur-Verträge** | 35 | **87** (CLI-Exit-Code-Tabelle, JSON-Export-Schema, Config fail-closed, Write-Path AST-Scan über 41 Dateien, Basis-Diagnostics-Hash, Config-Source) | `tests/test_architecture.py`, `tests/unit/test_architecture_contracts.py` |
| **Unit** | ~3.400, 52,9 % gemockt | ~3.700 (bereinigt; **keine Löschungen** zur Ratio-Optik — Rule 4.13) | Vollsuite-Delta |
| **Vollsuite** | 3.583 passed / 14 venv-bedingte Fails (R2-Endstand) | **3861 passed / 0 failed / 45 skipped / 1 xfailed** in 2:25:02 (Run 4, `c0492c7`); Run 5/6 validieren die CI-Härting | Receipt-Logs (§5) |

### 2.2 Engine-Leistung und Korrektheit

| Thema | Ergebnis | Beleg |
|---|---|---|
| M-149 Shared pycache (Phasen) + M-149b (Worker-Forwarding) | db-Kampagne 2.989 Mutanten in ~35 min (vorher ~31 h geschätzt, **~50×**); Isolation bewiesen: simple_lib 14/14 killed mit geteilter pycache | `m149-benchmark.log`, `m149b-correctness.log` |
| Kill-Raten (Modul-Gates) | trampoline 66,7 % raw / 93,6 % adjudiziert · suspended_spawn 34,8 % · db 16,4 % — niedrige Raten als Äquivalenz-Mutanten-Korridore dokumentiert (Windows-API-/SQL-Boilerplate-Nähe) | `w5-killrate-*.log` |
| M-147 / Issue #195 | Cross-Run-Verdikt-Cache: kuratierte Env-Basis, pyc-Skip, timestamp-frei; Campaign-E2E beweist Wiederverwendung | Issue #195 (CLOSED) |
| M-148 / Issue #194 | Forced-Fail-Liveness mit Faulthandler-Frame-Diagnose vor Wall-Clock-Kill | Issue #194 (CLOSED) |
| M-097 (R3-offen) | Legacy-Fallback in einer Lesetransaktion nachgeholt | Commit `7d7caf7`-Serie |
| M-149b-Follow-up | Executor-Override-Seam gehärtet (Guard wie Runner-Injektion) — in Run 1 der Final-Vollsuite gefunden und gefixt | `3f0ee3e`, Run-1-Receipt |

### 2.3 Gap-Closure GAP-1…GAP-7 (26 neue Fälle)

Lücken, in denen M-Fixes nur Unit-Tests hatten, wurden mit echten Integrations-/E2E-Tests geschlossen:

| GAP | Thema | Abgedeckte M-Fixes | Fälle | Commit |
|---|---|---|---:|---|
| 1 | Config-Fail-Closed E2E (Exit 2 vor Staging, kein mutants/, type_check blockt Export, Gegenprobe) | M-032–M-045 | 5 | `065155a` |
| 2 | Atomic-Write Crash-Recovery (GANZ-oder-GANZ-Invariante, Kill mid-write, PermissionError) | M-005–M-067 | 6 | `065155a` |
| 3 | Mutation-Operator-Korrektheit (erwartete Mutanten-Namen, messbares Verhalten, do_not_mutate, max_stack_depth) | M-069–M-099 | 5 | `065155a` |
| 4 | Staging-Drift (Quelldatei ändert sich mid-Dispatch → definierter Status; No-Drift-Gegenprobe) | M-070–M-089 | 2 | `9cb0fe9` |
| 5 | Browser-Diff nach Kampagne (results/show/apply, 0-Survivor kein Crash) | M-117–M-120 | 4 | `9cb0fe9` |
| 6 | Workspace-Lock-Konkurrenz (zweiter Run abgewiesen, Lock-Release) | M-093/M-103/M-104 | 2 | `9cb0fe9` |
| 7 | Interrupt-Finalisierung (echtes Ctrl-C → Exit 130 + Status `interrupted` + Restart-Recovery) | M-105/M-106 | 2 | `9cb0fe9` |

**Wichtiger GAP-7-Befund (kein Produkt-Bug, aber testmethodisch relevant):** `CTRL_C_EVENT` von einem konsolenlosen Runner ist ein **stilles No-Op** — der Interrupt-Vertrag (AR-24/M-076) war bis v3.1.0 nie echt E2E-verifizierbar. Zustellung jetzt über Hilfsprozess (AttachConsole + GenerateConsoleCtrlEvent). Der Engine-Vertrag selbst hält (Exit 130, Status interrupted, Recovery).

### 2.4 Release-Härtung (CI-rot → grün, 2026-10-07 Abend)

| Blockade | Root Cause | Auflösung | Commit |
|---|---|---|---|
| CI Quality gates rot (11 Ruff-Funde) | W1–W5-Dateien hatten repo-weite Lint-Schuld (F841/ARG001/RUF002/RUF003/TC003), die dateiscopierte lokale Gates nicht sahen | alle Funde behoben + repo-weites Lokal-Gating etabliert | `ca3126d` |
| PEP758-Konflikt | Ruff 0.15.8 formatiert Tuple-Except zu `except A, B:` — der gepinnte Semgrep-1.175-Parser kann das nicht lesen (Governance-Test existiert genau dafür) | except-Klauseln gesplittet (verhaltensidentisch) | `ca3126d` |
| Dependency-Audit rot | pyjwt 2.13.0 (transitiv über semgrep==1.175.0, `~=2.13.0`) mit 14 PYSEC-Advisories | Adjudiziert UNREACHABLE (pyjwt = semgrep-Cloud-Telemetrie; Gate läuft `--oss-only --metrics off` offline); 14 `--ignore-vuln` mit Begründung in ci.yml; Override-Variante getestet (Gate PASS mit 2.15.1) aber von pip-audit-Resolver abgelehnt | `ca3126d` |
| Governance-String-Kollision | Adjudizierungs-Kommentar enthielt verbotenes Literal `semgrep scan` | Kommentar umformuliert | `5f168d7` |

## 3. H1–H5: Trampolin-Grenze klassenlastiger Module (HAUPTANGRIFFSFLÄCHE)

**Symptom:** Trampoliniertes `mutmut_win/models.py` bricht `tests/unit/test_file_setup.py` vollständig (136/140 FAILED), trampoliniertes `browser.py` bricht `test_browser_diff.py` (20/20 FAILED). Ohne Trampolin laufen exakt dieselben Tests spiegelbildlich grün (H5-Refutation 2026-10-05, Worktree `9592ab7`). Verlangsamung ~68×.

| Hypothese | Stand | Prüf-Anleitung |
|---|---|---|
| **H1** Trampolin-Generator kann pydantic/Textual-Klassen grundsätzlich nicht verarbeiten | OFFEN | models.py isoliert trampolinieren gegen kleine dedizierte Testdatei; generierten Code in `mutants/` inspizieren: Klassen-Body erhalten? Dispatch um Methoden? |
| **H2** M-121/M-123-Wechselspiel brach models.py unter Trampolin | OFFEN | models.py auf pre-R3-Stand reverten, Gate wiederholen |
| **H3** M-117–M-120-Wechselspiel brach browser.py | OFFEN | browser.py pre-R3, Gate wiederholen |
| **H4** Tests-dir-Wahl ungeeignet (Staging-Pipeline-Tests statt models-Tests) | OFFEN | dedizierte test_models_*.py als Gate-tests-dir |
| **H5** Produkt-Bug in R3-Änderungen | **WIDERLEGT** (Vorher-Nachher, spiegelbildlich) | — |

**Differenzialdiagnose-Quelle:** `BLOCKED-GATES-MODELS-BROWSER.md` (Evidence-Verzeichnis).

**Kill-Raten-Korridore (Adjudizierungs-Aufforderung):** suspended_spawn 34,8 % und db 16,4 % werden als Äquivalenz-Mutanten-Korridore behauptet. Stichprobe ≥ 20 Survivors je Modul ziehen und unabhängig adjudizieren: Existenzfähiger Verhaltens-Test überhaupt möglich?

## 4. Offene Issues

| Issue | Thema | Status |
|---|---|---|
| #193 | Generation-Fingerprint ohne Engine-Version (Q-60) | offen (Konzept) |
| #198 | Testsanierung v3.1.0 | wird mit Release geschlossen |
| H1–H4 | Trampolin-Grenze | dieses Review |

## 5. Evidence-Map

| Was | Wo |
|---|---|
| Vollsuite-Receipts (Run 1–6) | `C:\Users\pmitt\Documents\Codex\reviews\mutmut-win-r2-2026-10-01\glm-followup\evidence\vollsuite-final-v3.1.0*.log` |
| GAP-Receipts | `…\evidence\gap1-config.log`, `gap2-atomic.log`, `gap3-mutation.log`, `gap4-7-all.log` |
| Kill-Raten, M-149-Belege | `…\evidence\w5-killrate-*.log`, `m149*.log` |
| Master-Ledger (146 Gruppen, gruppen-scharf) | `…\glm-followup\R0-R4-MASTER-LEDGER.md` |
| Gate-Matrix (E-A–F) | `…\glm-followup\AR27-GATE-MATRIX.md` |
| H1–H5-Differenzialdiagnose | `…\glm-followup\BLOCKED-GATES-MODELS-BROWSER.md` |
| Ursprungs-Reviews (Claude/Astra, historisch) | `_docs/reviews/external-review-v2.21.4/` |
| Testspezifikation v2 + Roadmap W0–W5 | `_docs/testmanagement/` |
| CI-Runs PR #199 | GitHub Actions, Runs 37631722193 (rot), 37658348083 (rot), Follow-up (grün erwartet) |

## 6. Wie reproduziere ich selber?

```powershell
# Vollsuite (~2,5 h)
$py = "$env:TEMP\opencode\testsanierung-venv\Scripts\python.exe"   # oder frisches uv sync
& $py -m pytest tests -q --tb=short -p no:cacheprovider

# Gates
uv run --no-sync ruff check . && uv run --no-sync ruff format --check .
uv run --no-sync mypy --no-incremental --cache-dir=nul src/ scripts/
uv run --no-sync lint-imports --no-cache
# Semgrep-Gate (benötigt venv mit semgrep 1.175.0 auf PATH + UV_PROJECT_ENVIRONMENT)
python -I scripts/semgrep_release_gate.py

# Modul-Gate (Kill-Rate) — Beispiel trampoline (~10 min)
uv run --no-sync mutmut-win run --paths-to-mutate src/mutmut_win/trampoline.py --no-progress

# H1-Reproduktion models (BLOCKED-Korridor)
uv run --no-sync mutmut-win run --paths-to-mutate src/mutmut_win/models.py --tests-dir tests/unit/test_file_setup.py --no-progress
```

## 7. Verifikationsprotokoll für DIESES Review (Verpflichtend)

Dieses Review ist adversarial: **Jeder Claim in diesem Dokument ist eine Hypothese.** Gilt ohne Ausnahme:

1. **Nichts ungeprüft übernehmen** — auch nicht die Rot-/Grün-Belege, Dispositionen oder Widerlegungen des Implementierers. Reviews waren die Quelle der ursprünglichen 146 Befunde UND Quelle von Fehlbehauptungen (23 zu Unrecht geführte Defekte im ersten Claude-Bericht; 11 tragende Befunde von Astras Kreuzreview verworfen).
2. **Dynamisch reproduzieren vor Bewerten.** Statisch bleibt Hypothese. Ein Befund gilt erst mit Reproduktion (Test, Gate-Lauf, gezielter Mutation-Versuch).
3. **Rot-Beweis prüfen:** Hat der Regressionstest einer Stichprobe von M-Gruppen den Original-Befund wirklich gefangen (am pre-Fix-Stand rot aus dem richtigen Grund)? Stichprobe: ≥ 10 Gruppen je P1/P2/P3-Quintile, vorzugsment aus der Kategorie „IMPLEMENTIERT-UNVERIFIZIERT" (68 Gruppen).
4. **Fail-closed prüfen:** Findet das Review Stellen, wo Sanierung in stille Degradation kippen könnte (Exit-Code-Verschiebung, Fehlerkanal, half-state)?
5. **Testpyramide angreifen:** Sind die E2E/Integration/Property-Tests wirklich orakel-stark (unabhängiges Orakel) oder tautologisch zum Produktions-Code? Blind-Spot-Scan der GAP-1…7-Tests.
6. **H1–H4 entscheiden** (§3) — mit Reproducer.
7. **Kill-Raten adjudizieren** (§3, Stichprobe).
8. **Ergebnisformat je Prüfpunkt:** BESTÄTIGT (mit Reproduktion) / ABWEICHEND (korrigierte Behauptung + Beleg) / WIDERLEGT (Gegenbeweis datei:zeile) / UNENTSCHIEDBAR (fehlende Evidenz). Niemanden-gefunden ist ein zulässiges und wertvolles Ergebnis; erfundene Bestätigungen sind es nicht.

## 8. Erwartete Deliverables

Das Review besteht aus **zwei Läufen** (Reihenfolge verbindlich):

**Lauf 1 — Umsetzung der Bugfixing- und Sanierungs-Roadmap** (Fokus §§1–3):
1. Befundliste mit Schwere (P1/P2/P3), Reproducer und datei:zeile — getrennt nach: Produkt-Defekt / Test-Schwäche / Doku-Lücke / unverifizierbar.
2. H1–H4-Entscheid je Hypothese.
3. Adjudizierungs-Stichprobe der Kill-Raten-Korridore (≥ 20 Survivors je Modul).
4. Blind-Spot-Analyse der Testpyramide (§2.1): Welche M-Fixes sind trotz GAP-Closure dünn abgedeckt?
5. Urteil: Ist die Roadmap-Umsetzung (146 Gruppen + Sprint 47) belastbar dokumentiert und technisch tragfähig?

**Lauf 2 — 360°-Regressionsscan** (nach Abschluss von Lauf 1, gleicher Auftrag):
1. Systematische Regressionssuche über die GESAMTE Codebasis: Haben die 145+ Fixes Nebenwirkungen erzeugt (Verhaltensänderungen jenseits der behaupteten, Exit-Code-Verschiebungen, Performance-Degradation, Lock-/Ressourcen-Lecks, abweichende Fehlerkanäle)?
2. Bisher übersehene Bugs: Defekte, die KEIN Review (weder Ursprungs- noch Kreuzreviews noch Sanierung) je erhoben hat — bevorzugt in Flächen mit historisch dünner Abdeckung (browser, models, stats, db-Schema, Prozesslebenszyklus).
3. Test-Schwächen außerhalb der GAP-Korridore: tautologische Orakel, Zeit-/Umgebungsabhängigkeit, unzureichende Aufräumarten (P-13).
4. Je Lauf-2-Befund dieselbe Beweispflicht wie in Lauf 1 (Reproducer, datei:zeile, Schwere).

**Gesamturteil:** Ist die v3.1.0-Abnahme tragfähig? Welche Fixes müssen VOR einem nächsten Release nachgebessert werden?
