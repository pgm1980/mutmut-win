# Sprint 27 — Full Source Audit: Findings

**Projekt:** mutmut-win v2.5.1 (Audit-Basis: main @ 729a644)
**Datum:** 2026-06-11 (laufend, Stage-weise ergänzt)
**Modus:** analysis-only — keine Fixes, keine Quellcode-Änderungen
**Methodik:** Parallele read-only Subagenten je Modulgruppe; jeder S1/S2-Kandidat
in-process verifiziert (Operator/API direkt aufrufen, generierte Mutanten
`compile()`/`exec()`-geprüft). Hauptsession-Stichproben zusätzlich
(`_issues/audit_verify_a1.py`).

**Severity:** S1 = blockiert Läufe / invalider Code / Crash · S2 = verfälscht
Ergebnisse/Score/Semantik · S3 = Robustheit/Edge-Case · S4 = kosmetisch/Rauschen.

**Verifikations-Legende:** ✅✅ = Agent + Hauptsession bestätigt · ✅ = Agent
in-process bestätigt · 🔬 = begründete Hypothese (Code-Lektüre, kein Runtime-Beweis).

**Nicht Teil des Audits** (bereits extern reported, W4.11): BUG-1
(`operator_collection_neutralize` sole-genexp), BUG-2 (`_RUNNER_TIMEOUT = 300`).

---

## Executive Summary (Stand: Stage A1)

| Stage | Scope | Findings | S1 | S2 | S3 | S4 |
|-------|-------|----------|----|----|----|----|
| A1 | Mutations-Engine (node_mutation, mutation, trampoline, regex_mutation) | 41 | 11 | 5 | 9 | 16 |
| A2 | Process & Execution (executor, worker, job_object, timeout, loop_monitor, runner) | 54 (1 Dup) | 2 | 12 | 21 | 19 |
| A3 | Pipeline & Persistenz (orchestrator, stats, test_mapping, file_setup, db, config, models, code_coverage, type_checking, type_checker_filter) | 65 (~8 Dups) | 2 | 21 | 19 | 23 |
| A4 | UI & Querschnitt (cli, browser, mutant_diff, exceptions, constants, _state, __init__, __main__) | 41 (~12 Dups) | 1 | 10 | 18 | 12 |
| **Σ** | **alle 29 src-Module** | **201 raw / ~180 unique** | **15** | **~40** | **~60** | **~65** |

**Baselines:** Semgrep (`--config auto src/`): **0 Findings**. pip-audit:
**nicht erhoben** — SSL-Zertifikatsfehler Richtung pypi.org in dieser
Umgebung (CERTIFICATE_VERIFY_FAILED); bei Gelegenheit mit funktionierender
Zertifikatskette nachholen. Tests: 610 passed / 4 skipped (Sprintbeginn).

**Drei Wurzelmuster erklären die Mehrzahl der schweren Funde:**

1. **„Parenless Subexpression-Yield"** (NM-001…006 + bekannter BUG-1): Fünf
   Operatoren yielden Teilausdrücke ohne Klammern-/Kontext-Erhalt — Multi-line-
   Operanden stranden (SyntaxError) oder Präzedenz bindet um (stille
   Semantik-Verfälschung). Die generalisierte Form von Bug #68. **Ein**
   gemeinsamer Safe-Unwrap-Helper fixt alle fünf Operatoren + BUG-1.
2. **Wrapper-Codegen-Annahmen** (MT-001…003, MT-006): Der Trampolin-Wrapper
   hartkodiert `self`, kollidiert mit Parametern namens `args`/`kwargs` und
   bricht das Async-Generator-Protokoll — alles Clean-Run-Brecher bzw. stille
   Wertverfälschung auf legalem Python.
3. **Klassenkörper-Injektion** (MT-004, MT-005): Das Mutants-Dict im
   Klassenkörper wird in `enum.Enum` zum Member und crasht `NamedTuple` beim
   Import — verbreitete Patterns, Clean-Run-Brecher.

Dazu strukturell: Das Sicherheitsnetz gegen invalide Mutanten existiert, ist
aber wirkungslos verdrahtet (MT-007 — invalide Datei bleibt im Staging,
`InvalidGeneratedSyntaxException` ist toter Code).

---

## Stage A1 — Mutations-Engine

### A1-NM: node_mutation.py (608 Zeilen, alle 24 Operatoren + Helper geprüft)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A1-NM-001 | S1 | :544/:552 `operator_or_default` | #68-Guard prüft nur Operator-Whitespace, nicht Operanden: `x = (a +\n b or c)` → Mutant `x = a +\n b` → SyntaxError | ✅✅ |
| A1-NM-002 | S1 | :165 `operator_remove_unary_ops` | `yield node.expression` verwirft lpar/rpar der UnaryOp: `(not aaa\n == bbb)` → `aaa\n == bbb` → SyntaxError | ✅ |
| A1-NM-003 | S1 | :433 `operator_conditional_expression` | body/orelse-Yield verwirft IfExp-Klammern: multi-line body strandet → SyntaxError | ✅ |
| A1-NM-004 | S1 | :395 `operator_math_methods` | BUG-1-Geschwister: `abs(a\n - b)` → Strand; `round(i for i in y)` → bare genexp → SyntaxError | ✅✅ |
| A1-NM-005 | S1 | :514 `operator_collection_neutralize` | Zweiter unabhängiger Trigger neben BUG-1: multi-line erstes Argument strandet (`sorted(a\n or b)`) | ✅ |
| A1-NM-006 | S2 | :395 + :514 | Präzedenz-Verfälschung: `list(a or b)[0]` → `a or b[0]` kompiliert, testet aber umgebundene Expression | ✅✅ |
| A1-NM-007 | S3 | :26 `operator_number` | `1e400` (legal, = inf) → `repr(inf)`="inf" kein Float-Token → CSTValidationError bricht ganze Datei | ✅ |
| A1-NM-008 | S3 | :330 `operator_regex` | Triple-quoted Patterns falsch gesliced: Anchor-Mutationen entfallen still; Validierung prüft falschen String; latenter S1 bei Katalog-Erweiterung | ✅ |
| A1-NM-009 | S4 | :85 `operator_dict_arguments` | `dict(a=1, aXX=2)` → Mutant mit doppeltem Keyword → SyntaxError (pathologisch) | ✅ |
| A1-NM-010 | S4 | :504/:394 | Equivalent-by-construction: `list(sorted(xs))`→`sorted(xs)`, `abs(abs(x))`→`abs(x)` etc. — unkillbare Mutanten | ✅/🔬 |
| A1-NM-011 | S4 | :43 `operator_string` | Docstring-Heuristik quote-stil-basiert: single-quoted Docstrings mutiert (unkillbar), triple-quoted SQL/Templates nie mutiert | ✅ |
| A1-NM-012 | S4 | :365/:477 `operator_void_call_removal` | Exclusion-Lücke: `self.log.error(m)` wird entfernt (Logger-Instanzattribut = Standard-Pattern); `await g()` nie erfasst | ✅ |

**Coverage:** sauber: operator_lambda, operator_arg_removal, beide
string_methods_swaps, operator_keywords, operator_name, operator_swap_op,
operator_augmented_assignment, operator_assignment, operator_match,
operator_return_value, operator_raise_removal,
operator_comprehension_filter_removal (Note: nur ListComp/äußeres for —
Coverage-Lücke, kein Bug), Registry + Daten-Tabellen.

### A1-MT: mutation.py (542 Z.) + trampoline.py (91 Z.)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A1-MT-001 | S1 | mutation.py:401-419 | Wrapper hartkodiert `self`: Methoden ohne Param `self` (`__init_subclass__`, `__class_getitem__`, Metaclass `cls`/`mcs`) → NameError **im Clean Run** | ✅✅ |
| A1-MT-002 | S1 | mutation.py:390/:399 | Wrapper-Locals `args`/`kwargs` kollidieren mit gleichnamigen Parametern: stille Wertverfälschung (`(2,[1])` statt `(2,2)`) bzw. TypeError im Clean Run | ✅ |
| A1-MT-003 | S1 | mutation.py:386 | `args = args[1:]` bei Methoden: `def m(*args)` verliert ALLE Argumente (StarredElement entfernt) | ✅ |
| A1-MT-004 | S1 | trampoline.py:19 + mutation.py:314 | Mutants-Dict im Klassenkörper wird **Enum-Member**: `list(Color)` = `['RED', 'xǁColorǁdescribe__mutmut_mutants']` — bricht Iteration/len/Serialisierung im Clean Run | ✅✅ |
| A1-MT-005 | S1 | ebd. | `NamedTuple`-Klasse mit Methode: ClassVar-Annotation → TypeError beim Import der mutierten Datei → Run blockiert | ✅ |
| A1-MT-006 | S2 | mutation.py:424-434 | Async-Generator-Wrapper bricht Protokoll: `asend()`-Werte verschluckt, `athrow()` erreicht Generator-try/except nicht — im Clean Run | ✅ |
| A1-MT-007 | S2 | file_setup.py:449-476 + exceptions.py:67 | Sicherheitsnetz wirkungslos: invalide Mutanten-Datei wird VOR Validierung geschrieben und bei SyntaxError nicht ersetzt (stumm); `InvalidGeneratedSyntaxException` nirgends erzeugt (toter Code) | ✅ |
| A1-MT-008 | S2 | mutation.py:190-228 | PEP-695 Type-Param-Bounds werden mutiert (Bug-#70-Geschwister): py3.13+ lazy → unkillbar; py3.12 eager → Import-Crash-Risiko | ✅/🔬 |
| A1-MT-009 | S3 | mutation.py:228 | Dekorierte Klassen komplett geskippt: `@dataclass`-Methoden erhalten 0 Mutanten, still | ✅ |
| A1-MT-010 | S3 | mutation.py:231-248 | `typing.cast`-Aliase (`t.cast`, `from typing import cast as c`) nicht erkannt → Bug-#4-Äquivalente kehren zurück | ✅ |
| A1-MT-011 | S3 | trampoline.py:40 | Legaler Identifier mit `ǁ` (U+01C1): ValueError propagiert ungefangen → gesamter Run crasht | ✅ |
| A1-MT-012 | S3 | mutation.py:296/:356 | Top-Level-Redefinition (`def f` 2×): doppelte Mutanten-Namen → Fehlattribution, Key-Kollision | ✅ |
| A1-MT-013 | S3 | trampoline.py:86 | Stale `MUTANT_UNDER_TEST`-Suffix → KeyError im getesteten Code → falsches „killed" | ✅ |
| A1-MT-014 | S4 | mutation.py:72/:469/:22 | Phantom-Mutationen für nie materialisierbare Scopes; `Mutation.contained_by_top_level_function`-Typ faktisch falsch | ✅ |
| A1-MT-015 | S4 | mutation.py Wrapper | `inspect.isgeneratorfunction` → False für Wrapper (Introspektion degradiert) | ✅ |
| A1-MT-016 | S4 | Generierung | BOM (U+FEFF) wird verworfen (kompiliert, aber nicht byte-treu); CRLF dagegen sauber | ✅ |
| A1-MT-017 | S4 | operator_name × Imports | `from copy import deepcopy` → `from copy import copy` mutiert: garantierter NameError-Junk-Mutant | ✅ |
| A1-MT-018 | S4 | mutation.py:122 | `_skip_subtree_ids` id()-basiert: aktuell sicher (Nodes bleiben referenziert); latent bei Visitor-Wiederverwendung | 🔬 |

**Positiv verifiziert:** Dispatch-Kern (clean/aktiviert/isoliert/stats),
test_mapping-Roundtrips (Dunder/Trailing-Underscore), Lambda-Default-Skip
(#70), dekorierte Nested Functions, CRLF-Erhalt, match/walrus/type-alias/
async-Methoden/PEP-750-t-Strings.

### A1-RX: regex_mutation.py (167 Z.) + operator_regex-Einbettung

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A1-RX-001 | S1 | regex_mutation.py:161 | `{n+1}`-Mutation auf `a{4294967294}` → `re.compile` wirft **OverflowError** (kein `re.error`) → ungefangen, 0 Mutanten für ganze Datei | ✅✅ |
| A1-RX-002 | S2 | node_mutation.py:291 + regex_mutation.py:144 | Äquivalente by construction: `^`-Removal unter `re.match`/`fullmatch`, `$`-Removal unter `fullmatch` (erschöpfend äquivalenz-getestet, 1365 Inputs, 0 Diff) | ✅ |
| A1-RX-003 | S3 | node_mutation.py:321 | `Arg.keyword` ignoriert: `re.match(string="a+b", pattern=p)` mutiert den Haystack; echtes kwarg-Pattern nie mutiert | ✅ |
| A1-RX-004 | S3 | node_mutation.py:330 | Triple-quoted: nur 1 von 3 Quotes gestrippt → Anchor-Mutationen entfallen still, Validierung prüft falschen String (= NM-008, RX-Sicht) | ✅ |
| A1-RX-005 | S4 | regex_mutation.py:38 | `?` von Gruppen-Konstrukten als Quantifier behandelt: `(?:ab)+`→`(:ab)+` etc. — kompilierende, irreführende Noise-Mutanten | ✅ |
| A1-RX-006 | S4 | :40/:155 | Backslash-Paritäts-Blindheit: Quantifier/Anchors nach `\\\\` nie mutiert (False Negatives) | ✅ |
| A1-RX-007 | S4 | :91/:134 | Literale in Char-Classes fehlinterpretiert: `[{3}]`→`[{2}]`; `\\\\d`-Klassen-Swap flippt Literal | ✅ |
| A1-RX-008 | S4 | :61-77 | Cap-Starvation: feste Reihenfolge bei MAX=5 → quantifier-reiche Patterns testen Anchors/Klassen nie | ✅ |
| A1-RX-009 | S4 | :43 | Gültiger Quantifier `{,m}` nicht erkannt (False Negative) | ✅ |
| A1-RX-010 | S3 | :161 + node_mutation.py:336 | Validierung prüft Source-Escape-Form ohne Call-Flags: VERBOSE-Kommentar-Mutationen = Äquivalente; cooked/raw-Differenz latent | ✅/🔬 |
| A1-RX-011 | S4 | node_mutation.py:312 | Erkennungs-Heuristik: nur wörtliches `re.<fn>(<literal>)` — Aliase/compiled Patterns/Konstanten nie mutiert (dokumentierte Design-Grenze, hier als Coverage-Karte) | ✅ |

**Positiv:** Keine konstruierbare Literal-Zerstörung (Quotes/dangling
Backslash unmöglich); Crash-Sweep über exotische Patterns sauber; Caps +
No-op-Filter greifen. Test-Evidenz: Hypothesis-Alphabete ohne Komma →
`{n,m}`-Zweig property-untestbar; `operator_regex` ohne direkte Unit-Tests.

### Fix-Cluster-Empfehlung (für den späteren Fixing-Sprint)

| Cluster | Findings | Ein Fix |
|---------|----------|---------|
| F1 Safe-Unwrap-Helper (Genexp-Guard + Multiline-Guard + lpar/rpar-Transfer) | NM-001…006 + BUG-1 | ja — ein Helper, 5 Operatoren |
| F2 Wrapper-Codegen (first-param-Name statt `self`, kollisionsfreie Locals, *args-Methoden, async-gen passthrough) | MT-001, -002, -003, -006 | gemeinsame Codegen-Stelle |
| F3 Klassenkörper-Injektion → Modul-Level | MT-004, MT-005 | ja |
| F4 Sicherheitsnetz scharf schalten (validate→write-Reihenfolge, Warning, Exception nutzen) | MT-007, NM-007, MT-011, RX-001 (Blast-Radius) | ja — ein Guard-Pfad |
| F5 Skip-Lücken (TypeParam, cast-Aliase, Import-Kontext, Docstring-Position) | MT-008, MT-010, MT-017, NM-011 | verwandt |
| F6 Regex-Polish | RX-002…010, NM-008 | Modul-lokal |

---

## Stage A2 — Process & Execution

**Schlüssel-Erkenntnisse:** (1) Beide Abbruch-/Fehlerpfade des Pools enden in
Hängern — demonstriert. (2) Die Timeout-Architektur ist dreifach gebrochen:
`timeout_multiplier` wird im Worker als **absolute Sekunden** interpretiert
(flach 60 s je Task), die im Orchestrator berechneten per-Task-
`timeout_seconds` werden **nirgends gelesen**, `WallClockTimeout` ist toter
Code — von zwei Agenten unabhängig gefunden, Hauptsession-bestätigt.
(3) Die in Sprint 24 (#12) als geliefert geltende Worker-Restart-Logik
(max 3 Restarts/Backoff/Exhaustion) **existiert nicht im Code** — geliefert
wurde nur ein In-Worker-`except Exception` (Soft-Errors); product_backlog-AC
ist entsprechend zu korrigieren. (4) Der IL-Triple-Check degeneriert auf
Windows (Primärplattform!) zum Single-Check: `psutil.status()` ist dort
praktisch immer "running" (empirisch belegt), Output-Wachstum ist durch
Block-Buffering blind. (5) Die IlForensics — das v2.5-Explainability-Feature —
erreicht die DB nie: `save_result` wird ohne `forensics` aufgerufen
(Spalte bleibt immer NULL) — Hauptsession-bestätigt.

### A2-EW: executor.py (171 Z.) + worker.py (364 Z.)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A2-EW-001 | S1 | executor.py:144-170 | Shutdown schließt Queues nie (kein `cancel_join_thread`): nach Ctrl+C/Crash blockiert der Queue-Feeder beim Interpreter-Exit → mutmut-win hängt für immer; Job-Handle bleibt offen → Orphans überleben. Demonstriert (Watchdog musste os._exit erzwingen) | ✅ |
| A2-EW-002 | S1 | executor.py:128-142 | `get_events()` blockiert ohne Timeout/Liveness-Check: harter Worker-Tod (OS-Kill, AccessViolation, BaseException) → Event fehlt → Orchestrator hängt ewig. Sprint-24-Restart-Logik (#12: max-3/Backoff/Exhaustion) NICHT implementiert — nur In-Worker-except | ✅✅ |
| A2-EW-003 | S2 | worker.py:59-61 | ≡ A2-JT-003 (s. dort): `worker_timeout = max(60, timeout_multiplier)` — Multiplikator als absolute Sekunden | ✅✅ |
| A2-EW-004 | S2 | orchestrator.py:655-676 | Summary-Schwarzloch: Status „segfault"/„check was interrupted by user" (exit 2 = Collection-Error!)/„not checked" inkrementieren keinen Bucket, zählen aber in completed/Score-Nenner → Summen-Inkonsistenz, deflationierter Score | ✅ |
| A2-EW-005 | S2 | worker.py:131-143 | `@argfile`-Konvention erfordert pytest ≥ 8.2; eigener Floor erlaubt 6.2.5 im Zielprojekt → UsageError 4 → alle gemappten Tasks „suspicious" | ✅/🔬 |
| A2-EW-006 | S2/S3 | worker.py:140 | Argfile UTF-8 geschrieben, von pytest/argparse locale-gelesen (cp1252) → Mojibake bei Nicht-ASCII-Test-IDs → exit 4 | 🔬 |
| A2-EW-007 | S3 | worker.py:177-245 | Temp-Logfile-Leak auf Kill-Pfaden — 4 verwaiste `mutmut_out_*.log` im Repo als Beleg; kein Startup-Sweep | ✅ |
| A2-EW-008 | S3 | worker.py:343-344 | `_kill_proc_tree`-Early-Return wenn Parent schon tot → Kinder (xdist/Test-Spawns) verwaisen bis Run-Ende; Kinderliste einmalig erhoben (TOCTOU) | ✅ |
| A2-EW-009 | S3 | worker.py:292 | Konfiguriertes `infinite_loop_window_seconds`/poll erreicht ProcessMonitor nie (Defaults hartverdrahtet); Forensik behauptet konfigurierten Wert | ✅ |
| A2-EW-010 | S3 | loop_monitor.py:162 | ≡ A2-JT-001: running_ratio-Check auf Windows vakuum | ✅ |
| A2-EW-011 | S3 | worker.py:133-171 | Misconfig-Pfade (fehlendes mutants/, pytest nicht auf PATH) → stiller „Suspicious-Sturm" statt Fail-Fast | ✅ |
| A2-EW-012 | S3 | worker.py:71-75 | Recovery verbucht Ergebnis als mutant_name="unknown" → echtes Mutant bleibt „not checked", Geisterzeile in DB | ✅ |
| A2-EW-013 | S3 | timeout.py:114-144 | Latente Landminen im toten WallClockTimeout: Parent-only-Kill, SemLock-Deadlock bei Kill unter Lock, Completed+TimedOut-Doppelzählung | 🔬 |
| A2-EW-014 | S3 | worker.py:261-268 | `_read_last_lines` lädt komplettes Log via read_text → MemoryError bei Output-Runaway-Mutanten | ✅ |
| A2-EW-015 | S3 | config.py:268-284 | setup.cfg-Fallback verliert `infinite_loop_*` + `extra_paths` (still Defaults) | ✅ |
| A2-EW-016 | S3 | orchestrator.py:697-704 | Präfix-Kollision `_update_source_data`: „src.foo" matcht per startswith auch „src.foo_bar"-Mutanten | ✅ |
| A2-EW-017 | S4 | executor.py:144 | Docstring „graceful join first" — Code killt zuerst | ✅ |
| A2-EW-018 | S4 | executor.py:97-112 | Job-Assign erst nach proc.start() — Mikro-Orphan-Fenster | ✅ |
| A2-EW-019 | S4 | executor.py:132-139 | Event-Diskriminierung per Key-Sniffing statt Typ-Tag — bricht still bei Modell-Erweiterung | ✅ |
| A2-EW-020 | S4 | constants.py:14/22 | Doppelter Literal-Key `-24` im Dict; 0xC0000005-Kill → „suspicious" statt Kill; -11/-9 auf Windows unerreichbar | ✅ |
| A2-EW-021 | S4 | job_object.py | ≡ A2-JT-005 | ✅ |
| A2-EW-022 | S4 | loop_monitor.py:292 | shutdown-join 1 s kann auslaufen (daemon, harmlos); Erst-Child-Sample 0,0 % | ✅ |
| A2-EW-023 | S4 | mutants/mutmut-stats.json | Testsuite schreibt in produktiven Stats-Cache (Unit-Test-Residue `pkg.my_func__mutmut_1`) → reale Läufe mit leerem Mapping | ✅ |

### A2-JT: job_object.py (156 Z.) + timeout.py (145 Z.) + loop_monitor.py (401 Z.)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A2-JT-001 | S2 | loop_monitor.py:162/176 | `psutil.status()` auf Windows immer "running" (empirisch: stdin-blockierter Prozess → running) → running_ratio-Check trennscharf-los; Doku-Szenario „sleeping → timeout" unerfüllbar | ✅ |
| A2-JT-002 | S2 | loop_monitor.py:349 + worker.py:196 | Output-Check blind: Block-Buffering (~8 KB; gemessen: 5000 B geschrieben, st_size 0) + pytest schweigt während EINES langen Tests → Triple-Check kollabiert zu „CPU ≥ 70" → CPU-gebundene legitime Slow-Tests als IL „killed" (Score-Inflation, high confidence) | ✅/🔬 |
| A2-JT-003 | S2 | worker.py:59-61 + orchestrator.py:440-473 + timeout.py | Timeout-Architektur: Multiplikator als absolute Sekunden (flach 60 s); berechnete `timeout_seconds` nie gelesen (Grep: 0 Lesezugriffe); WallClockTimeout nie instanziiert (toter Code) | ✅✅ |
| A2-JT-004 | S2 | orchestrator.py:648 | IlForensics wird nie persistiert: `save_result(...)` ohne `forensics=event.forensics` — DB-Spalte immer NULL, Explainability-Versprechen faktisch tot | ✅✅ |
| A2-JT-005 | S3 | job_object.py:26 | windll ohne `use_last_error=True` → `get_last_error()` immer 0 → alle Job-Object-Fehlermeldungen melden „error 0" (empirisch: real 87, gemeldet 0) | ✅ |
| A2-JT-006 | S3 | job_object.py:92-156 | Keine argtypes/restype: HANDLE als c_int (latent; ctypes wirft statt trunkiert — verifiziert); Struct-Layouts korrekt | ✅/🔬 |
| A2-JT-007 | S3 | executor.py:97-114 | Assign-Race: uv-Trampoline-Launcher spawnt Interpreter-KIND (Parent 0 % CPU, Kind 96 % — empirisch); Job-Assign trifft nur Launcher; Orphan-Schutz hängt real am undokumentierten uv-eigenen Job | ✅/🔬 |
| A2-JT-008 | S3 | timeout.py gesamt | WallClockTimeout tot + 3 latente Defekte (Parent-only-Kill, Doppel-Event-Race, PID-Reuse); Monotonic-Handling selbst korrekt | ✅/🔬 |
| A2-JT-009 | S3 | loop_monitor.py:140-196 | Kein Mindest-Sample-Guard: 1 Sample mit cpu=99 → IL/high confidence (empirisch) | ✅ |
| A2-JT-010 | S3 | loop_monitor.py:161/176 + config.py:155 | `output_threshold=0` (ge=0 erlaubt) deaktiviert IL-Detection still (growth<0 nie wahr); zugehöriger Margin-Zweig unerreichbar | ✅ |
| A2-JT-011 | S3 | loop_monitor.py:299-316 | `run()` ohne Catch-All: unerwartete Exception killt Sampler still → systematisch timeout/low ohne Warnung | 🔬 |
| A2-JT-012 | S4 | loop_monitor.py:232 | `daemon = True` als Klassenattribut shadowt Thread-Property (funktioniert, `_daemonic` inkonsistent) | ✅ |
| A2-JT-013 | S4 | timeout.py:135 | Docstring behauptet CTRL_C_EVENT, Code sendet SIGTERM | ✅ |
| A2-JT-014 | S4 | worker.py:210-216 | Snapshot-Cutoff NACH Kill+Log-Read → effektives Fenster < konfiguriert; Free-Threading-Deque-Race theoretisch | ✅/🔬 |
| A2-JT-015 | S4 | loop_monitor.py:161/348 | stat-Fehler/Log-Schrumpfung → growth 0 = pro-IL-Bias (Klemm-Logik empirisch) | ✅ |
| A2-JT-016 | S4 | tests/ | Tests kodieren das auf Windows unmögliche „sleeping"-Szenario; running_ratio nie isoliert getestet — Suite kann JT-001 nicht entdecken | ✅ |
| A2-JT-017 | S4 | job_object.py:31 | PROCESS_ALL_ACCESS überprivilegiert (0x101 reicht) | 🔬 |
| A2-JT-018 | S4 | loop_monitor.py:359-389 | v2.5.1-Cache verifiziert korrekt + notwendig (CPU liegt komplett im Launcher-Kind); Residual: Erst-Sample 0,0 verwässert Mean nur bei window≈timeout | ✅ |

### A2-RN: runner.py (384 Z.)

*Prämissen-Korrektur: Stats-Run ist seit Rewrite ein Subprozess (kein
pytest.main in-process) — mehrere befürchtete In-Process-Risiken gegenstandslos.*

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A2-RN-001 | S2 | runner.py:74/143/222 | Alle 3 Runner-Phasen → DEVNULL: bei Exit ≠ 0 null pytest-Output für den User; Exit 2/4/5 nicht dekodiert — alle erhalten irreführendes „Fix tests before mutating" (eigenständiger BUG-2-Begleiter; Worker-Pfad nutzt längst Temp-File-Capture) | ✅ |
| A2-RN-002 | S2 | runner.py:269-277 | `extra_paths` (#69) fehlt im Runner-PYTHONPATH (nur Worker hat es): #69-Nutzer scheitern am Clean-Gate mit unsichtbarem ImportError | ✅✅ |
| A2-RN-003 | S2 | runner.py:153-164 | Stats-JSON wird nach fehlgeschlagenem Subprozess ungeprüft geladen → Stale-Mapping des Vorlaufs als frisch persistiert → falsche Testselektion | ✅/🔬 |
| A2-RN-004 | S2 | runner.py:136/322 | Stats-Plugin × pytest-xdist: Controller überschreibt Worker-JSON mit leerem Mapping → „no mappings" → Full-Suite-Fallback unter Einzeltest-kalibriertem Timeout → Massen-Timeout | 🔬 |
| A2-RN-005 | S3 | runner.py:85-106 | `collect_tests` in anderem Universum: Projekt-Root statt mutants/, ohne tests_dir/Timeout/RC-Check/env → Cache permanent wirkungslos („Found N new tests" jedes Mal), hängende Collection unbegrenzt, Exit 2 → stiller Stale-Cache | ✅ |
| A2-RN-006 | S3 | runner.py:228-233 | Forced-Fail beweist nur „≥1 Failure irgendwo"; Timeout wird explizit in Erfolg umgemünzt (`return 1 # trampoline works`); ohne `-x` läuft volle Suite (BUG-2-Treiber) | ✅ |
| A2-RN-007 | S4 | runner.py:148/151 | Vestigiales `os.environ`-Schreiben im Parent (Relikt der In-Process-Ära) | ✅ |
| A2-RN-008 | S4 | runner.py:345 + stats.py:181 | Akkurater Plugin-`stats_time` wird beim Re-Save mit Parent-`process_time()` ≈ 0 überschrieben; `_state.stats_time` toter Global | ✅ |
| A2-RN-009 | S4 | stats.py:168/149 | Stale Doku: „in-process"-Behauptungen + irreführender Re-Run-Print überleben den Subprozess-Rewrite | ✅ |
| A2-RN-010 | S4 | runner.py:289 | Env-Getter `_mutants_env` schreibt Dateien (sitecustomize.py); kein injizierbarer mutants-Pfad — Unit-Tests hinterlassen reale Artefakte im Repo (beobachtet) | ✅ |
| A2-RN-011 | S4 | runner.py:364-383 | sitecustomize-Blocker matcht sys.path exakt-string (kein normcase/realpath) → Case-/Symlink-Varianten schattieren mutants/src | ✅/🔬 |
| A2-RN-012 | S3 | runner.py:129 | `PY_IGNORE_IMPORTMISMATCH=1` nur im Stats-Run — Clean/Forced-Fail/Worker ungeschützt (inkonsistente Phasen) | 🔬 |
| A2-RN-013 | S3 | config.py:187-193 | Arg-Koerzierung: `'-m "not slow"'` → naives split() → kaputte Tokens; `pytest_add_cli_args_test_selection` akzeptiert Strings gar nicht (inkonsistent) | ✅ |

**Cross-Module-Beobachtungen (A2, für A3/A4-Verifikation vorgemerkt):**
Worker startet `["pytest", ...]` vom PATH, Runner `sys.executable -m pytest` —
Interpreter-Asymmetrie; `get_mutant_name` strippt nur `src.` → `source/`-Layout
bricht Mapping-Lookup dauerhaft; `_apply_timeouts`-Mean-Fallback strukturell zu
knapp für Full-Suite-Fallback-Tasks.

**Doku-Folge:** product_backlog-AC zu #12 („Max 3 Worker-Neustarts pro Slot mit
Backoff; Slot-Exhaustion sauber behandelt") ist durch A2-EW-002 widerlegt —
geliefert wurde nur der In-Worker-except. Korrektur bei Sprint-27-Abschluss.

---

## Stage A3 — Pipeline & Persistenz

**Schlüssel-Erkenntnisse:** (1) **Destruktiv**: Absolute `paths_to_mutate`
(CLI oder pyproject) überschreiben die Original-Quelldateien mit
Trampolin-Code — `Path("mutants") / <absolut>` verwirft den linken Operanden;
Hauptsession-bestätigt. (2) Die beiden „intelligenten" Pipeline-Features sind
**end-to-end funktionslos**: Type-Checker-Filter (Mutanten-Namen matchen nie —
`mutants.`-Präfix) und `mutate_only_covered_lines` (Coverage misst den
pytest-Subprozess prinzipbedingt nicht → still 0 Mutanten) — beide exakt in
der Lücke, die die E2E-Tests aussparen. (3) `compute_cicd_stats` kennt
`killed_by_infinite_loop` nicht → CI/CD-Score systematisch zu niedrig
(bestätigt: 33,3 % vs. 66,7 % auf gleicher Datenlage). (4) Im **Standard-
src/-Layout** matcht `_update_source_data` nie → `.meta`-Dateien bleiben
ergebnislos, `browse` zeigt nichts (bestätigt; der zugehörige Unit-Test
kodiert den falschen Vertrag). (5) `load_results` setzt das v2.5-Schema
voraus, ruft aber nie `create_db` → Upgrade-Crash auf Alt-Caches (bestätigt;
derselbe Lauf bewies live FD-006: Exception hält Connection offen →
WinError 32).

### A3-OS: orchestrator.py (748 Z.) + stats.py (377 Z.) + test_mapping.py (110 Z.)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A3-OS-001 | S1 | executor.py:128 | ≡ A2-EW-002 (Event-Loop-Hänger bei hartem Worker-Tod) — unabhängig bestätigt | ✅ |
| A3-OS-002 | S2 | stats.py:306-338 | `compute_cicd_stats` ohne `killed_by_infinite_loop`-Case: IL-Kills zählen in total, in keinen Bucket → CICD-Score 33,3 % wo results 66,7 % melden | ✅✅ |
| A3-OS-003 | S2 | orchestrator.py:592-603 | Type-Check-Kills nie in DB persistiert (einziger save_result-Call ist der Event-Loop) → results/CICD divergieren dauerhaft vom Run-Score | ✅ |
| A3-OS-004 | S2 | orchestrator.py:697-704 | src-Layout: norm_path behält `src.`, get_mutant_name strippt es → startswith matcht NIE → .meta ergebnislos, `browse` leer; Unit-Test kodiert falschen Vertrag | ✅✅ |
| A3-OS-005 | S2 | orchestrator.py:206-221 | Ctrl-C → regulärer Abschluss: voller Nenner, kein Abbruch-Marker, Exit 0 — CI kann Abbruch nicht erkennen | ✅ |
| A3-OS-006 | S2 | stats.py:179-191 | Fehlgeschlagene Stats-Collection überschreibt guten Cache mit leerem MutmutStats → Full-Suite-Fallback, Laufzeit explodiert still | ✅ |
| A3-OS-007 | S2 | stats.py:143-158 | Test-Löschung ohne neue Tests → Obsolete-Cleanup läuft nie → tote Node-IDs im Argfile → Exit 4 → „suspicious"-Flut | ✅/🔬 |
| A3-OS-008 | S2 | file_setup.py:416-444 | mtime-Fast-Path ignoriert covered_lines/Konfig-Wechsel → veraltetes Mutanten-Universum ohne Warnung | ✅ |
| A3-OS-009 | S2 | orchestrator.py:123-141 | Teilmengen-Lauf + Type-Checker: caught enthält ALLE Projekt-Mutanten → Subset-Score aufgebläht | ✅ |
| A3-OS-010 | S2 | orchestrator.py:163 | IndexError wenn Type-Checker alle Mutanten fängt (kein Leerheits-Check nach Step 1b) | ✅ |
| A3-OS-011 | S2 | orchestrator.py:293-312 | ≡ A3-CM-003 (Coverage-Leerlauf), Orchestrator-Sicht | 🔬 |
| A3-OS-012 | S2 | db.py:40-44 + file_setup.py:152-172 | Keine Epochen-Invalidierung: DB-Zeilen verschwundener Mutanten bleiben ewig (results über Vereinigungsmenge aller Läufe); mtime-only-Invalidierung übersieht Restores mit altem Timestamp; gelöschte Quellen → Orphans | ✅ |
| A3-OS-013 | S3 | orchestrator.py:185-216 | Kein Resume: Restart wiederholt alle Mutanten (upstream skippt erledigte) — nur Generierung gecacht | ✅ |
| A3-OS-014 | S3 | cli.py:219 + models.py:192 | `--output json` ohne Score (Property nicht serialisiert) — CI-Kanal blind | ✅ |
| A3-OS-015 | S3 | worker.py:144-148 | Leeres Mapping → Full-Suite-Fallback im Worker; Schätzung = Einzeltest-Mittel → Sortierung invers, upstream bucht „no tests" | ✅ |
| A3-OS-016 | S3 | worker.py:71-101 | ≡ A2-EW-012 („unknown"-DB-Zeilen) | ✅ |
| A3-OS-017 | S3 | test_mapping.py:31 + cli.py:375 | `tests-for-mutant` mit plausibler Eingabe → roher AssertionError (time-estimates fängt denselben Fall) | ✅ |
| A3-OS-018 | S3 | timeout.py | ≡ A2-JT-008 (toter Code; bei Nachrüstung Doppel-Event-Risiko) | ✅ |
| A3-OS-019 | S4 | models.py:189 | `type_check_caught` hat keinen Writer → 🧙-Spalte im Live-Progress immer 0 | ✅ |
| A3-OS-020 | S4 | orchestrator.py:435 | fnmatch case-insensitiv auf Windows → plattformdivergente Mutant-Filter | ✅ |
| A3-OS-021 | S4 | test_mapping.py:31 | Funktionsnamen mit literal `__mutmut_` → partition-first-match → falsches Mapping (rpartition wäre korrekt) | ✅ |
| A3-OS-022 | S4 | orchestrator.py:223-251 | dry_run ignoriert mutant_names/Type-Check/Coverage-Filter → Zahl ≠ Real-Lauf | ✅ |
| A3-OS-023 | S4 | runner.py:148 | ≡ A2-RN-007 | ✅ |
| A3-OS-024 | S4 | stats.py:149-256 | Toter Inkremental-Apparat: `tests`-Param ignoriert (Full-Re-Run trotz „for them"-Meldung), Doppel-Save, new_tests()/ids ohne Aufrufer | ✅ |
| A3-OS-025 | S4 | stats.py:65-69 | load_stats fängt nur FileNotFound/JSONDecode — PermissionError etc. crashen den Run | ✅ |
| A3-OS-026 | S4 | cli.py:223 | `--min-score` failt bei 0 Mutanten mit Score 0.0 (fail-closed, aber unkommuniziert; mit OS-011 failt Coverage+min-score derzeit immer) | ✅ |

### A3-FD: file_setup.py (486 Z.) + db.py (149 Z.)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A3-FD-001 | S2 | db.py:121-126 | `load_results` selektiert forensics-Spalte ohne create_db/Migration auf Lesepfad → OperationalError auf Prä-v2.5-Caches (results/browse/export nach Upgrade) | ✅✅ |
| A3-FD-002 | S2 | file_setup.py:218 | `also_copy`/`extra_paths` mit `..` schreiben AUSSERHALB von mutants/ (Sandbox-bestätigt: Datei außerhalb erzeugt) — und `..` ist der #69-Kern-Use-Case (Siblings!) | ✅ |
| A3-FD-003 | S2 | file_setup.py:144-164 | Kein Deletion-Sync: gelöschte/umbenannte Quellen bleiben als Geister in mutants/ + DB → Score mischt Epochen, Tests laufen gegen gelöschte Module grün | ✅ |
| A3-FD-004 | S3 | file_setup.py:167-172 | mtime-Regression (Restore mit altem Timestamp) → stumm veralteter Staging-Stand (Sandbox-bestätigt) | ✅ |
| A3-FD-005 | S3 | file_setup.py:184-206 | `also_copy=["."]` nestet mutants/mutants (inkl. .git!) — Skip-Set kleiner als bei copy_src_dir, Guard greift nicht (`Path(".").name == ""`) | ✅ |
| A3-FD-006 | S3 | db.py:64/100/124 | Connections nie geschlossen (`with sqlite3.connect` committet nur): Exception hält Connection → DB gelockt (WinError 32) — live im Hauptsession-Check beobachtet | ✅✅ |
| A3-FD-007 | S3 | db.py:67-71 | Migrations-Race: paralleles create_db → „duplicate column" OperationalError (interleaved bestätigt) | ✅ |
| A3-FD-008 | S3 | file_setup.py:258-262 | pyproject-Sanitiser übersieht `[tool.uv.sources.<pkg>]`-Subtables → „Distribution not found"-Fehler bleibt für diese Syntax | ✅ |
| A3-FD-009 | S3 | cli.py:154-158 | `--force`: rmtree(ignore_errors=True) + unkonditionales „Removed mutants/" → Teil-Löschung als Clean Slate verkauft (≡ A3-CM-023) | ✅ |
| A3-FD-010 | S3 | models.py:139-176 + file_setup.py:420 | Korrupte .meta (non-atomarer save, Crash in Step 8) → JSONDecodeError ungefangen → alle Folge-Läufe blockiert bis manuellem Löschen (≡ A3-CM-009, dort bestätigt) | ✅ |
| A3-FD-011 | S3 | db.py:100-105 | Lone Surrogates crashen save_result (UnicodeEncodeError, Upsert verloren) — aktuell unerreichbar (errors="replace" im einzigen Producer), latente Falle | ✅ |
| A3-FD-012 | S4 | db.py:98 | create_db bei jedem save_result (2 Connections + CREATE + PRAGMA pro Mutant) — Hot-Loop-Overhead | ✅ |
| A3-FD-013 | S4 | file_setup.py:209-219 | „also copying X"-Log VOR Guards: meldet nie-kopierte/geskippte Pfade als kopiert | ✅ |
| A3-FD-014 | S4 | worker.py:160-165 | Absolute extra_paths: Worker legt ECHTEN Pfad auf PYTHONPATH (mutants/-Join verworfen), Copy-Seite relativiert — Real-vs-Staging-Mischimporte | ✅ |
| A3-FD-015 | S4 | file_setup.py:136-146 | Voll-Projekt-Kopie mit 9-Namen-Skip-Liste: data/, models/, *.pt, node_modules, .env (Secrets!) werden mitkopiert — GB-Risiko bei ML-Projekten | ✅ |

*FD-Positivbefunde:* `.pth`/sitecustomize-Mechanik schreibt NICHTS ins venv
(User-Umgebung nach Abbruch nicht vergiftet — explizit geprüft);
do_not_mutate-fnmatch ist auf Windows separator-/case-tolerant; DB-Roundtrip
exotischer Daten (NUL, ǁ, Emoji, 1 MB, forensics-dict) sauber; ein Commit
pro Mutant = crash-sicher.

### A3-CM: config.py (341 Z.) + models.py (210 Z.) + code_coverage.py (66 Z.) + type_checking.py (117 Z.) + type_checker_filter.py (139 Z.)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A3-CM-001 | **S1** | config.py:80 + orchestrator.py:306 + file_setup.py:449 | **Absolute paths_to_mutate überschreiben Original-Quellen mit Trampolin-Code** (`Path("mutants")/<abs>` == `<abs>`; .meta landet neben Quelle); Guard existiert nur für also_copy | ✅✅ |
| A3-CM-002 | S2 | type_checking.py:96 + orchestrator.py:581 | Type-Checker-Filter funktional tot: Checker-Pfade → `mutants.src.foo.…`, Task-Namen → `foo.…` — matchen nie; Phantom-caught zählen zusätzlich in Score; null Test-Abdeckung | ✅ |
| A3-CM-003 | S2 | code_coverage.py:35 + runner.py:178 | `mutate_only_covered_lines` tot: Coverage.collect() im Parent, pytest im Subprozess ohne Brücke → lines()=None → 0 Mutanten, „No mutants generated." ohne Ursache | ✅ |
| A3-CM-004 | S2 | cli.py:163-200 | CLI-Overrides via model_copy umgehen ALLE Pydantic-Constraints: `--max-children 0` (→ 0 Worker → Hänger), `--timeout-multiplier -1` akzeptiert | ✅ |
| A3-CM-005 | S2 | config.py:329 | Typos in [tool.mutmut] still verschluckt (extra="ignore"): `paths_to_mutat` → Default-Guess mutiert unbemerkt falschen Baum; Hyphen/Underscore-Duplikat: letzter gewinnt | ✅ |
| A3-CM-006 | S2 | cli.py:184-197 | `--since-commit`: git-returncode nie geprüft → ungültige Ref = „nichts geändert" + Exit 0 (falscher CI-Erfolg); Test-/gelöschte Dateien werden Mutationsziele | ✅ |
| A3-CM-007 | S2 | orchestrator.py:697 | ≡ A2-EW-016 (startswith ohne Trennzeichen: src.foo matcht src.foo_bar) | ✅ |
| A3-CM-008 | S2 | type_checking.py:38-54 | `mypy.exe`/`.venv\Scripts\mypy.exe` nicht als mypy erkannt (exakte Listen-Mitgliedschaft) → JSON-Lines im Falsch-Zweig → JSONDecodeError → Lauf-Abbruch; auf Windows die Norm | ✅ |
| A3-CM-009 | S2 | models.py:139-176 | Korrupte/abgeschnittene .meta crasht nächsten Lauf (load fängt nur FileNotFound; save nicht atomar) — bestätigt mit %TEMP%-Experiment | ✅ |
| A3-CM-010 | S3 | type_checking.py:33-35 | run_type_checker: kein timeout (Hänger), returncode ungeprüft (Crash → still 0 gefiltert), encoding strict (UnicodeDecodeError) | ✅/🔬 |
| A3-CM-011 | S3 | type_checking.py:57-72 | parse_pyright_report filtert Severity nicht: Warnings zählen als Type-Errors (nach CM-002-Fix → Überfilterung) | ✅ |
| A3-CM-012 | S3 | orchestrator.py:592 | ≡ A3-OS-003 | ✅ |
| A3-CM-013 | S3 | code_coverage.py:15/47 | Coverage-Pfad-Keying ohne normcase/resolve; Re-Run misst Trampolin-Zeilen statt Originalzeilen (derzeit durch CM-003 maskiert) | 🔬 |
| A3-CM-014 | S3 | config.py:250 | Malformierte/Nicht-UTF-8 setup.cfg → roher Traceback statt ConfigError | 🔬 |
| A3-CM-015 | S4 | config.py:205 | fnmatch-Semantik: `*` kreuzt Separatoren; POSIX-divergent; .pyw nie mutiert | ✅ |
| A3-CM-016 | S4 | config.py:179-193 | Koerzierungs-Asymmetrie: Einzel-String nur bei 2 von 5 Listenfeldern akzeptiert | ✅ |
| A3-CM-017 | S4 | cli.py:175 | Override-Semantik inkonsistent: --do-not-mutate ergänzt, andere ersetzen; nur eines dokumentiert | ✅ |
| A3-CM-018 | S4 | config.py:39-70 | guess-Heuristik: lib-Vorrang (JS-lib/ kapert Guess); Fallback „src/" unkommuniziert | ✅ |
| A3-CM-019 | S4 | models.py:189 | ≡ A3-OS-019 | ✅ |
| A3-CM-020 | S4 | code_coverage.py | Keine Type-Hints/Docstrings (Projektstandard verletzt); Typ-Lügen in Signaturen; _unload_modules_not_in vestigial | ✅ |
| A3-CM-021 | S4 | models.py:23 | MutationTask-Docstring-Beispiel entspricht nicht realem Namensformat | ✅ |
| A3-CM-022 | S4 | models.py | Validator-Lücken: mutant_name ohne min_length, kein validate_assignment, Zähler ohne ge=0, status freier String | ✅ |
| A3-CM-023 | S4 | cli.py:151 | ≡ A3-FD-009 | ✅ |
| A3-CM-024 | S4 | type_checking.py:43 | Nackte `Exception` mit komplettem stdout im Message-Text statt spezifischer Exception | ✅ |

---

## Stage A4 — UI & Querschnitt

**Schlüssel-Erkenntnisse:** (1) **`apply` beschädigt Quellcode**: Bei
namensgleichen Methoden über Klassen hinweg (`__init__`, `get`, …) patcht es
die ERSTE gefundene Funktion statt der richtigen (Klassenname wird verworfen
— mutant_diff.py:209/218, Sandbox- + Code-bestätigt); zusätzlich ohne Backup,
nicht atomar, ohne Staleness-Check, und es flippt LF→CRLF für die ganze
Datei. (2) **Das Forensics-Rendering existiert nicht**: Kein einziger
Zugriff auf `forensics` in cli.py/browser.py (Grep-bestätigt) — der
Sprint-26-AC „results-command renders forensics" war nie erfüllt; zusammen
mit A2-JT-004 (Spalte immer NULL) ist die IL-Explainability doppelt tot.
(3) Der TUI-Browser kennt den v2.5-Status `killed_by_infinite_loop` nicht
(kein Emoji, keine Spalte, falscher Filter, „Unknown status"). (4) `--debug`
ist ein totes Flag; `--output json` ist nicht parsebar (Diagnose-Prints auf
stdout). (5) Querschnitt: erster Stats-Trampolin-Hit importiert die komplette
CLI-Kette (~1,4 s gemessen) in den User-Testprozess; Emoji-Ausgabe crasht
auf cp1252-Pipes ohne PYTHONUTF8; Exit-Codes 33/34 haben keinen Producer
(Mutanten ohne Tests laufen die Vollsuite statt „no tests"); 6 tote
Exception-Klassen; Konstanten-Drift (MUTANT_UNDER_TEST 3× definiert).

### A4-UI: cli.py (454 Z.) + browser.py (423 Z.) + mutant_diff.py (226 Z.)

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A4-UI-001 | **S1** | mutant_diff.py:209/218 | **apply patcht falsche Funktion**: Klassenname verworfen, `find_top_level_function_or_method` nimmt ersten Namens-Treffer → B.greet-Mutant landet in A.greet (Sandbox-Repro); bei `__init__`-Mutanten praktisch jede Codebase betroffen; show ist NICHT betroffen | ✅✅ |
| A4-UI-002 | S2 | mutant_diff.py:225 | apply flippt LF→CRLF für gesamte Datei (text-mode read + write ohne newline="") → Git-Diff-Rauschen | ✅ |
| A4-UI-003 | S2 | mutant_diff.py:225 | apply ohne Backup, nicht atomar, ohne Staleness-Check (überschreibt ggf. neueren Code mit altem Mutanten-Stand) | ✅ |
| A4-UI-004 | S2 | cli.py:303 + browser.py | Forensics-Rendering existiert nirgends (Grep: 0 Zugriffe in UI-Schicht) — README + Sprint-26-AC behaupten es; AC-Status in Backlogs falsch | ✅✅ |
| A4-UI-005 | S2 | cli.py:65/172 | `--debug` totes Flag (0 Lesezugriffe auf config.debug); run-except-Exception verschluckt Tracebacks genau dort, wo debug helfen müsste | ✅ |
| A4-UI-006 | S2 | cli.py:219 + orchestrator | `--output json`: stdout enthält Step-Header/Warnungen/Summary VOR dem JSON → json.loads(stdout) schlägt fehl (CliRunner-bestätigt); „text" ist No-op-Choice | ✅ |
| A4-UI-007 | S2 | browser.py:47-93 | TUI-Diff ist Ganzdatei-Diff (Trampolin + ALLE Mutanten, identisch je Mutant; 8-Zeilen-Modul → 79-Zeilen-Diff); DB-Fallback zeigt immer „mutant not found" (sucht qualifizierten Namen, Datei enthält nur lokale) — korrektes mutant_diff.get_diff_for_mutant ungenutzt | ✅ |
| A4-UI-008 | S2 | browser.py:29-44/260/303 | `killed_by_infinite_loop` fehlt komplett: kein Emoji (→„?"), keine Spalte (Zeilensumme ≠ Total), Filter zeigt IL-Kills als offen, match → „Unknown status (exit_code=38)" — fürs v2.5-Headline-Feature | ✅ |
| A4-UI-009 | S3 | cli.py:255-289 | results-Schwarzloch: segfault/interrupted/not-checked in keiner Zeile, aber in Total+Nenner (bestätigt: Buckets 5 von 8, Score ohne Hinweis) | ✅ |
| A4-UI-010 | S3 | browser.py:369-375 | Aktionen crashen bei leerer Tabelle: cursor_row=0 (nie None — Guard toter Code) → get_row_at(0) → RowDoesNotExist | ✅/🔬 |
| A4-UI-011 | S3 | cli.py:160/312/335 | Korrupte pyproject/.meta → rohe Tracebacks in run/show/apply/browse (ConfigError/JSONDecodeError ungefangen, CliRunner-bestätigt) | ✅ |
| A4-UI-012 | S3 | cli.py + orchestrator:415 | mutant_names-Matching inkonsistent über 5 Commands (run: exakt+Glob; show/apply/time-estimates: nur exakt; tests-for-mutant: bedingt) — nirgends dokumentiert | ✅ |
| A4-UI-013 | S3 | cli.py:247/437/358 | Exit-Code-/Stream-Inkonsistenz: leere DB → results exit 0, export-cicd exit 1, time-estimates exit 0; tests-for-mutant: Tippfehler nicht von „ungetestet" unterscheidbar | ✅ |
| A4-UI-014 | S4 | mutant_diff.py:177 | show-Diff: Hunk-Header immer @@ -1,N (funktionsrelativ), from/to-Label identisch → nicht patch-fähig | ✅ |
| A4-UI-015 | S4 | cli.py:283 | „Suspicious:1" ohne Leerzeichen (Alignment-Bruch) | ✅ |
| A4-UI-016 | S4 | cli.py:64 | `--no-progress` unterdrückt auch die End-Summary → leiser Lauf endet ohne jedes Ergebnis | ✅ |

**Flag-Wiring-Matrix (Kern):** verdrahtet: max-children, paths-to-mutate,
tests-dir, min-score, since-commit, dry-run, do-not-mutate, force,
treat-timeout-as-kill (run↔results konsistent inkl. IL — verifiziert),
**--no-infinite-loop-detection + --infinite-loop-cpu-threshold (end-to-end
sauber — Worker liest exakt diese Keys; Positivbefund)**. Halb: output
(UI-006), no-progress (UI-016), extra-paths-to-copy (Runner fehlt ≡
A2-RN-002), timeout-multiplier (als absolute Sekunden ≡ A2-JT-003),
window/poll-IL-Felder (≡ A2-EW-009). Tot: **--debug** (UI-005).

### A4-QX: Kleinst-Module + Querschnitts-Sweeps

| ID | Sev | Ort | Kurzbeschreibung | Verif. |
|----|-----|-----|------------------|--------|
| A4-QX-001 | S2 | __main__.py:3 | Erster Stats-Trampolin-Hit importiert komplette CLI-Kette (click+textual+rich+orchestrator) in den User-Testprozess: **~1,4 s gemessen**; Textual-Importfehler würde Stats/fail-Modus crashen | ✅ |
| A4-QX-003 | S2 | orchestrator.py:719 + cli.py | Emoji-Ausgabe (🎉⏰🌀) auf umgeleitetem stdout ohne UTF-8-Mode → UnicodeEncodeError (cp1252 strict) → Lauf bricht ab; Dev-Env maskiert via PYTHONUTF8=1 | ✅/🔬 |
| A4-QX-005 | S3 | exceptions.py:52 | `BadTestExecutionCommandsException` tot: Docstring verspricht Raise bei pytest Exit 4 — kein Producer; Exit 4 fällt still in „suspicious" | ✅ |
| A4-QX-006 | S3 | exceptions.py:12-46 | 6 tote Exception-Klassen (InvalidConfigValueError, WorkerError, WorkerCrashError, WorkerInitError, MutationError, MutationParseError); cli fängt `Exception` statt `MutmutWinError` | ✅ |
| A4-QX-007 | S3 | constants.py:16/53 + worker.py:144 | Exit 33 („no tests") + 34 (skipped) ohne Producer: Mutanten ohne Tests laufen die VOLLE Suite statt 33 → massiver Laufzeitverlust vs. mutmut-Design (≡ OS-015-Wurzel) | ✅ |
| A4-QX-008 | S3 | worker.py:123 vs runner.py:245 | Interpreter-Asymmetrie: Worker startet bare `"pytest"` vom PATH, Runner `sys.executable -m pytest` → nicht aktiviertes venv = Exit-35-Flut trotz grünem Clean-Gate | ✅ |
| A4-QX-017 | S4 | __main__.py:8 + _state.py | `_reset_globals` deckt `_cached_max_stack_depth` nicht ab (Tests resetten manuell) | ✅ |
| A4-QX-018 | S4 | config.py:114 + __main__.py:42 | `max_stack_depth` ohne ge=-1: Wert 0 verwirft ALLE Stats-Hits → jeder Mutant läuft Vollsuite | ✅ |
| A4-QX-019 | S4 | 5 Module | Konstanten-Drift: MUTANT_UNDER_TEST 3× definiert + hardcoded; EXIT_CODE_INFINITE_LOOP 2×; Worker nutzt Literale 35/36/38 | ✅ |
| A4-QX-020 | S4 | __main__.py:57 | Per-Hit-Import in record_trampoline_hit (Hot Path) | ✅ |
| A4-QX-023 | S4 | cli.py:214 + type_checking.py | run fängt Exception → Einzeiler, Traceback auch mit --debug weg; type_checking raised nackte `Exception` | ✅ |
| A4-QX-025 | S4 | constants.py:12 | Exit 2 vermengt User-Interrupt mit pytest-Collection-Errors: Import-brechende Mutanten (eigentlich Kills) → „interrupted" → Summary-Schwarzloch | ✅ |

*(QX-002/004/009-016/021/022/024 sind Quersicht-Bestätigungen bereits
gelisteter Findings — im QX-Agent-Report mit Exit-Code-Matrix dokumentiert.)*

**Exit-Code-Matrix (Kernaussagen):** Exit 33/34 ohne Producer; Exit 2 =
Interrupt UND Collection-Error (Kills als „interrupted" verschluckt);
-11/-9-Segfault-Mapping auf Windows unerreichbar (echte Windows-Crashes
0xC0000005 → „suspicious"); Exit 4 (stale Argfiles, bad args) → still
„suspicious"; CLI-Prozess-Exit 0 auch bei git-Fehler unter --since-commit.
**Encoding-Sweep:** alle Datei-I/O-Stellen haben explizites utf-8; Risiken
nur an Rändern (Argfile-Leseseite, Emoji-stdout, Fremd-Output ohne
errors=). **Except-Sweep:** kein bare except; breite Catches an 3 Stellen
mit Risiko (cli.py:214, worker.py:229-OSError→35-Flut, models.py:144).
**Positiv:** Trampolin-Import-Vertrag vollständig (beide Codegen-Namen
exportiert, lazy — normale Mutant-Läufe importieren mutmut_win nicht);
`python -m mutmut_win` ohne Doppel-Ausführung; #72-Versions-Fix korrekt;
`_reset_globals` für _state vollständig; set.add threadsicher (160k/160k).

---

## Gesamtfazit & konsolidierte Fix-Cluster

### Die 15 S1-Findings auf einen Blick

| # | ID | Ein-Satz-Diagnose |
|---|----|--------------------|
| 1 | A3-CM-001 | Absolute `paths_to_mutate` überschreiben Original-Quellen mit Trampolin-Code (destruktiv) |
| 2 | A4-UI-001 | `apply` patcht bei klassen-übergreifender Namensgleichheit die falsche Funktion (stille Quell-Beschädigung) |
| 3 | A2-EW-001 | Ctrl+C/Crash → Interpreter-Exit-Hang (Queues nie geschlossen) + Orphan-Überleben |
| 4 | A2-EW-002 | Harter Worker-Tod → Event-Loop hängt ewig; Sprint-24-Restart-Logik existiert nicht |
| 5 | A1-MT-001 | Trampolin-Wrapper hartkodiert `self` → NameError im Clean Run (`__init_subclass__`, Metaclass) |
| 6 | A1-MT-002 | Wrapper-Locals kollidieren mit Parametern `args`/`kwargs` → stille Wertverfälschung im Clean Run |
| 7 | A1-MT-003 | `def m(*args)`-Methoden verlieren ALLE Argumente |
| 8 | A1-MT-004 | Mutants-Dict wird Enum-Member → bricht jede Enum-Klasse mit Methode im Clean Run |
| 9 | A1-MT-005 | NamedTuple mit Methode → TypeError beim Import der mutierten Datei |
| 10 | A1-NM-001 | or_default: multi-line Operanden → SyntaxError-Mutant (Guard prüft falsche Ebene) |
| 11 | A1-NM-002 | remove_unary_ops: multi-line → SyntaxError-Mutant |
| 12 | A1-NM-003 | conditional_expression: multi-line body → SyntaxError-Mutant |
| 13 | A1-NM-004 | math_methods: genexp/multi-line → SyntaxError-Mutant (BUG-1-Geschwister) |
| 14 | A1-NM-005 | collection_neutralize: zweiter Trigger (multi-line) neben bekanntem BUG-1 |
| 15 | A1-RX-001 | Regex-`{n+1}` → OverflowError statt re.error → 0 Mutanten für ganze Datei |

### Strategische Diagnose

1. **Drei v2.x-Vorzeige-Features sind in Produktion (teil-)funktionslos**:
   IL-Forensik (nie persistiert + nie gerendert + Triple-Check auf Windows
   degeneriert), Type-Checker-Filter (Namens-Mismatch, matcht nie),
   Coverage-guided Mutation (misst Subprozess nicht, 0 Mutanten). Gemeinsame
   Ursache: **End-to-End-Lücke in der Testpyramide** — Unit-Tests prüfen
   Bausteine, E2E-Tests nur Mutanten-Generierung; kein Test fährt die
   Features durch die echte Pipeline.
2. **Timeout-Architektur dreifach gebrochen** (Multiplikator als absolute
   Sekunden, per-Task-Budgets nie gelesen, Monitor toter Code) — von drei
   Agenten unabhängig gefunden.
3. **Die Bug-#68/BUG-1-Klasse ist ein Wurzelmuster** in 5 Operatoren plus
   Codegen — ein gemeinsamer Safe-Unwrap-/Guard-Helper + das scharf
   geschaltete ast.parse-Sicherheitsnetz (MT-007) eliminieren die ganze
   Klasse strukturell.
4. **Abbruch-/Fehlerpfade sind die schwächste Zone**: beide Hänger (EW-001/
   002), Ctrl-C-als-Erfolg (OS-005), Stats-Cache-Zerstörung (OS-006),
   Stale-Argfiles (OS-007), Meta-Korruption blockt Folge-Läufe (CM-009).

### Konsolidierte Fix-Cluster (Empfehlung für Fixing-Sprints 28+)

| Cluster | Findings (Kern) | Charakter |
|---------|-----------------|-----------|
| **C1 Quell-Schutz (SOFORT)** | CM-001, UI-001, UI-002, UI-003 | klein, isoliert, destruktiv-verhindernd |
| **C2 Codegen-Korrektheit** | MT-001…006, NM-001…006 + BUG-1, NM-007/009, MT-007-Sicherheitsnetz, RX-001 | Engine; ein Helper + Wrapper-Rewrite + Guard-Pfad |
| **C3 Pool-Robustheit** | EW-001, EW-002, EW-007/008, JT-005, QX-008 | Shutdown/Liveness/Tree-Kill |
| **C4 Timeout-Architektur** | JT-003 (≡EW-003/QX-002), EW-009, BUG-2 (extern), RN-005b | Worker liest task.timeout_seconds; clean_run_timeout-Config |
| **C5 IL-Detection ehrlich machen** | JT-001/002/004, EW-009/010, UI-004/008, OS-002, JT-009/010/011 | Persistenz + Rendering + Windows-Realismus + Schwellen-Guards |
| **C6 Tote Features reaktivieren oder deaktivieren** | CM-002/003 (+OS-011), CM-008/010/011, OS-003/009/010 | Type-Check + Coverage end-to-end |
| **C7 Score-/Status-Integrität** | EW-004, OS-002/005/012, UI-009, QX-025, EW-020, OS-014/026 | Buckets, Nenner, Epochen, JSON |
| **C8 Pipeline-Hygiene** | OS-006/007/008, FD-001…011, CM-004/005/006/009, RN-001/002/003 | Cache/DB/Config/Diagnose |
| **C9 UX/Konsistenz** | UI-005/006/007/010…016, QX-001/003/005/006/007/017…025, RN-006…013, Rest-S4 | Sammelposten |

### Audit-Coverage-Nachweis

Alle 29 Module unter `src/mutmut_win/` wurden von mindestens einem Agenten
vollständig gelesen und bewertet; jeder Agent lieferte eine
Symbol-Coverage-Tabelle; die Hauptsession hat 12 Top-Findings unabhängig
nachverifiziert (alle bestätigt: 6× A1, 4× A2/A3-Greps+Reads, 2× A4) und
die Baselines erhoben. Verifikations-Skripte: `_issues/audit_verify_a1.py`,
`_issues/audit_verify_a3.py`, `_issues/audit_verify_a3b.py` (gitignored).

*Sprint 27 abgeschlossen 2026-06-11. Fixing beginnt erst nach
User-Priorisierung (analysis-only-Mandat).*
