# PROMPT an GPT-6 Astra — P-08-Entscheidungen R2 (mutmut-win 3.0.0-Sanierung)

> **Verwendung:** Diese Message erst übergeben, wenn der R2-Stand vollständig committet UND gepusht ist.
> **Status: AUSGEFÜLLT UND ÜBERGABEBEREIT (01.10.2026).** Der Abschnitt „Aktueller Stand" enthält die finalen Fakten (R2 abgeschlossen, gepusht).

---

## Kontext für die Entscheidung

Du bist die abschließende Review-Instanz („Astra") des Mutations-Testing-Ports **mutmut-win** (Windows-nativen Builds, CPython 3.14.7 ausschließlich). Das Projekt wird von v2.21.4 auf **3.0.0** saniert (146 Defektgruppen, Roadmap `HANDOVER_GLM-5.3.md`). R0 und R1 sind abgeschlossen und gemergt; R2 ist bis auf die unten stehenden Entscheidungen umgesetzt. Nach dem R1-Vorbild (Deine bindenden Entscheidungen M-008=A, M-003=A, M-144 Stufe 2=A, dokumentiert in `P08_ENTSCHEIDUNGEN_M-008_M-003_M-144.md`) brauchst Du jetzt die zehn offenen R2-Verhaltens- und Vertragsänderungen (Prinzip P-08): Keine Variante wird ohne Deine dokumentierte Entscheidung implementiert.

**Entscheidungsregel des Projekts (P-07/P-08):** Fixes dürfen Ergebnisse nur konservativ verschieben (fail-closed). Vertragsänderungen brauchen eine ausdrückliche Entscheidung; die abgelehnte Variante erhält den dokumentierten Status „per Entscheidung zurückgestellt" oder den in der Karte genannten Minimalfix. Der PO hat delegiert: Du triffst die fachliche Wahl; er nimmt sie ab.

## Aktueller Stand — FINAL (01.10.2026, R2 abgeschlossen)

- Integrationsbranch: `fix/v2.21.5-remediation-r1`, HEAD `a385a63` (docs(memory): record R2 completion), **gepusht nach `origin/fix/v2.21.5-remediation-r1`** (github.com/pgm1980/mutmut-win).
- R2 umgesetzt: **Alle 25 Arbeitspakete** (AP-09 bis AP-32 inkl. AP-29b) gemergt — 76 nicht-blockierte Gruppen vollständig implementiert. Finale Vollsuite: **3360 passed / 43 skipped / 2 failed** (beide Failures sind die bekannten Version-Governance-Präexistenten: Ziel 3.0.0 vs. Paketversion 2.21.x — der Bump erfolgt release-gebündelt). Kanonisches Semgrep-Gate: **PASS** (28 adjudizierte Findings, 0 unerwartet). ruff / mypy strict / lint-imports sauber.
- Diese Nachricht blockieren: die 10 P-08-Gruppen selbst (M-016, M-022, M-023, M-036, M-041, M-058, M-061, M-064/M-101 Stufe 2, M-102) — alle als blockiert in ihren Issues dokumentiert; die zugehörigen APs sind mit ihren Geschwistergruppen gemergt und geschlossen.
- Bekannte offene Punkte (nicht P-08): **Issue #192** (P1 — gezielte Mutation-Gate-Infrastruktur liefert Falschverdikte/Abbrüche, vier Belege; muss vor dem konsolidierten Mutation-Phasengate gefixt werden; dokumentierte NOT_EXECUTED-Gates: AP-14, AP-20/M-035, AP-23, AP-17), zwei Version-Governance-Tests (erwarten den 3.0.0-Bump), M-042-Dokumentationsroute wartet auf Deine Bestätigung (Frage 10).
- Detailkarten mit vollständiger Analyse je Gruppe: `HANDOVER_GLM-5.3.md` (Zeilenangaben je Gruppe unten).
- Empfehlungsdokument der orchestrierenden Instanz: `P08_ENTSCHEIDUNGEN_R2_OFFEN.md`.

## AUFGABE 1 (vor den Entscheidungen): Unabhängiges adversariales Multi-Agenten-Review aller implementierten Bugfixes

**Bevor** Du die zehn P-08-Entscheidungen triffst, prüfe alle bisher in der Sanierung implementierten Bugfixes mit einem unabhängigen, adversarialen Multi-Agenten-Review. Jeder Reviewer-Agent arbeitet aus einer eigenen Linse, kennt die ursprünglichen Detailkarten (`HANDOVER_GLM-5.3.md`, Teil-B-Abschnitte je AP, Zeilenangaben in der AP-Übersichtstabelle des Handovers) und hat Lesezugriff auf den gepushten Branch (`origin/fix/v2.21.5-remediation-r1`, HEAD `a385a63`).

### Review-Linsen (je ein Agent)

1. **Korrektheit:** Stimmt die Logik? Randfälle? War der Regressionstest nachweislich rot vor dem Fix (TDD-Echtheit, Issue-Dokumentation)?
2. **Fail-closed & Verträge (P-07):** Verschiebt der Fix Ergebnisse ausschließlich konservativ? Exit-Codes, Meldungen, Kompatibilität, Mutanten-ID-Stabilität?
3. **Security & Supply-Chain:** Neue Angriffsflächen, Semgrep-Allowlist-Zuwächse gerechtfertigt, Abhängigkeitsfragen, Prozess-/Injection-Oberflächen?
4. **Performance & Robustheit:** Lastverhalten, Timeouts, Ressourcenlecks, Windows-Spezifika?
5. **Testqualität & Gate-Ehrlichkeit:** Töten die Tests die Mutanten wirklich? Wie sind die dokumentierten NOT_EXECUTED-Gates (AP-14, AP-20/M-035, AP-23, AP-17) und Issue #192 zu gewichten?
6. **Dokumentation & Vertragstreue:** README, Docstrings, Issues, Commit-Messages (Conventional Commits + [M-xxx])?

### Ausgabeformat

- **Je Fix (Gruppe M-xxx):** `GUTBEFUND` oder `SCHLECHTBEFUND` + 1–3 Sätze Begründung aus jeder beauftragten Linse + bei Schlechtbefund ein konkreter Nachbesserungsauftrag (Commit-Vorschlag oder Issue-Text).
- **Gesamturteil:** Tabelle Gruppe × Linse → Verdikt; Liste der Nachbesserungsaufträge nach Priorität.
- **Verknüpfung mit Aufgabe 2:** Schlechtbefunde bei P-08-relevanten Gruppen (z. B. M-041, M-016) fließen als Randbedingung in die Entscheidung; alle übrigen Schlechtbefunde werden als Issues für die Nachfolge-Session formuliert.

### R2 — vollständige Fix-Liste (76 Gruppen; Roadmap: HANDOVER Teil B, AP-Abschnitt je Zeile; Commits im Branch)

| AP (Roadmap-Abschnitt) | Gruppe | Fix in einem Satz | Commit |
|---|---|---|---|
| AP-09 (ab Z. 2105) | M-065 | WorkerEnvironmentError wird fatal statt stiller Verdikte | 276d78c |
| AP-09 | M-054 | Events werden vollständig gedrained, bevor tote Worker gefegt werden | 276d78c |
| AP-10 (Teil B, AP-Tabelle) | M-032 | git-ignorierte paths_to_mutate-Wurzeln werden über gemeinsame Walk-Quelle gestagt | 2af987b |
| AP-10 | M-033 | Verschwindene Preflight-Eingaben gelten als abwesend, nicht als Kollision | 27588ef |
| AP-10 | M-030 | Datei↔Verzeichnis-Typwechsel werden vor dem Materialisieren ausgeräumt | ab0af01 |
| AP-11 (ab Z. 2475) | M-060 | PEP-610-URL wird exakt einmal dekodiert | 687e66a |
| AP-12 (ab Z. 2616) | M-062 | „Nicht beobachtbar" wird von echter Drift getrennt (begrenzte Nachmessung) | 81d1475 |
| AP-12 | M-063 | MYPY_CACHE_DIR wird ins ephemere Runtime-Dir umgeleitet; Checker-Fail-safe | e29434d |
| AP-12 | M-101 (Stufe 1) | Watchdog-Abdeckung für Timing-Stats- und Abschluss-Fingerprint | ffcd8d9 |
| AP-13 (ab Z. 2893) | M-055 | Worker-Kappung bei Pool-Kollaps (Generation-Supervisor) | 790bd65 |
| AP-13 | M-110 | START-Vorserialisierung für den Workerstart | 790bd65 |
| AP-13 | M-111 | Teardown-Dokumentation des Supervisors | ec371db |
| AP-14 (ab Z. 3087) | M-056 | Mutantennamen werden plattformweit case-sensitiv aufgelöst | e3dc95a |
| AP-14 | M-113 | Doppelte Quellwurzeln werden bei der Namensauflösung dedupliziert | 5f50af5 |
| AP-14 | M-026 | show/apply/Browser-Lesen heilt Metadaten nie mehr | e9bb1d1 |
| AP-14 | M-115 | DB-only-Fallback owners werden per Modulidentität aufgelöst | c505cb1 |
| AP-14 | M-116 | Nicht-UTF-8-Staging-Dateien brechen den Fallback-Scan nicht mehr | 6869c7a |
| AP-14 | M-074 | apply meldet den aufgelösten Mutanten statt des Glob-Musters | 81cb0d3 |
| AP-15 (ab Z. 3463) | M-057 | TUI-Subkommandos laufen im kill-on-close Job Object | 0005150 |
| AP-16 (ab Z. 3615) | M-021 | --since-commit Pfade projektrelativ über git --relative | 65c1be0 |
| AP-16 | M-024 | Inkrementeller Testausschluss kanonisiert projektrelativ | 68316e9 |
| AP-17 (ab Z. 3884) | M-073 | --dry-run --min-score wird als Optionskonflikt (Exit 2) abgelehnt | 813b823 |
| AP-17 | M-025 | treat-timeout-as-kill Gate-Score wird auf stderr ausgegeben | 02cf3a6 |
| AP-17 | M-076 | Exit-130-Vertrag auch bei Ctrl-C vor der Workerphase | 1eca143 |
| AP-17 | M-020 | --force-Cleanup räumt Readonly-Leaves (remove_staging_root mit onexc) | 0d89b2c |
| AP-17 | M-075 | export-cicd-stats fail-closed ohne mutants/ statt rohem OSError | c6b292c |
| AP-18 (ab Z. 4199) | M-027 | Config-Lesegrenze konsolidiert | 6053456 |
| AP-18 | M-079/M-080 | Strukturprüfung beider Config-Quellen | c8f7750 |
| AP-18 | M-078/M-028 | Falsche TOML-Typen werden abgelehnt | 6053456 |
| AP-18 | M-077 | Gemeinsame Validierungsgrenze beider Quellen | 354cf20 |
| AP-19 (ab Z. 4571) | M-029 | Quantifizierer-Kommas in setup.cfg-Regexlisten bleiben geschützt | 7d70124 |
| AP-19 | M-083 | Boolean/Float werden als mutation_profile abgelehnt | dd857a3 |
| AP-19 | M-082 | Leerer Pfad wird nie als Mutationswurzel geraten | f512a14 |
| AP-19 | M-072 | Tote max_stack_depth-Werte 0–3 werden mit Frame-Ursache abgelehnt | 7cb6de5 |
| AP-20 (ab Z. 4830) | M-088 | _copy_with_retry nutzt exakt max_attempts atomare Kopien | 1f2d988 |
| AP-20 | M-035 | uv-sources werden TOML-sicher mit Parser-Beweis entfernt | f6685e7 |
| AP-21 (Teil B, AP-Tabelle) | M-037 | CacheEnvironmentError als fatale Domänen-Ausnahme | 0f175bc |
| AP-21 | M-095 | Null-Link-Diagnose (st_nlink 0) | 0f175bc |
| AP-22 (ab Z. 5117) | M-093 | Interrupt-sichere Freigabe aller DB-Teillocks (ExitStack) | 5c93d9e |
| AP-23 (ab Z. 5266) | M-038 | Identitätsgebundener Klassenstack für do_not_mutate_patterns | 50eaf47 |
| AP-23 | M-042 | Dekorierte-Klassen-Sperre technisch dokumentiert (wartet auf Deine Bestätigung, Frage 10) | e9bfbee |
| AP-23 | M-043 | Token-Stream-Extent für Block-Pragmas | d63d2fc |
| AP-24 (ab Z. 5483) | M-040 | NFKC- und Mangling-korrekte kwargs-Schlüssel des Trampolin-Wrappers | 2e44689 |
| AP-24 | M-039 | Methoden-Trampoline binden Globalen zur Klassenerzeugungszeit | dabec0f |
| AP-24 | M-044 | Lambda-Generatoren ändern Funktionsidentität nicht mehr | c25f691 |
| AP-25 (ab Z. 5755) | M-045 | Oversized Integer-Inkrements rendern hexadezimal | e50b344 |
| AP-25 | M-098 | Wertgleiche Float/Imaginary-Inkrements werden verworfen | b6f2abe |
| AP-25 | M-046 | CRCR behält erforderliche Klammern | 71dd51c |
| AP-25 | M-048 | Unary-Mutationen werden gegen Match-Pattern-Grammatik gegatet | 6c9c3a4 |
| AP-25 | M-047 | Nackte Dezimal-Integer werden an Attributbasen geklammert | d2bf597 |
| AP-25 | M-049 | Wertgleiche String-Case-Mutanten werden verworfen | 03f07e1 |
| AP-26 (ab Z. 6138) | M-050 | chr()-Domain-Guard für Bereichsverschiebungen | 418e352 |
| AP-26 | M-100 | Lazy Kandidaten-Pipeline unter dem Cap (Eager-Orakel-Differential) | b6b67a0 |
| AP-26 | M-052 | (?#...)-Kommentarspannen werden nie mutiert (_scan_regex) | c7da90b |
| AP-26 | M-099 | Pattern-Argument wird positional oder per pattern= gebunden | 2a3fbc0 |
| AP-26 | M-051 | Statisch auflösbare re.VERBOSE-Flags sperren Kommentare | 1ca725b |
| AP-27 (ab Z. 6458) | M-053 | Namens-Konsistenz-Gate vor Dispatch | e22cdac |
| AP-27 | M-103 | Endliches Budget-Ceiling für Timeout-Multiplikatoren | 972082e |
| AP-27 | M-102 (Docstring) | Ehrlicher _apply_timeouts-Docstring (stdout-Zeile P-08-blockiert) | 972082e |
| AP-28 (ab Z. 6673) | M-059 | Leerzeilen-Toleranz in mypy-JSONL-Reports | 9549e01 |
| AP-28 | M-127 | Pydantic-Schema-Validierung aller Checker-Reports | 2b0e800 |
| AP-28 | M-128 | Job-Handle-Leak-Fenster vor geschütztem Launch geschlossen | 6b54127 |
| AP-29 (ab Z. 6880) | M-015 | Dreiwertiges Ladeergebnis; geerbte Regeln unter gestörter Ebene ausgesetzt | 8f747ae |
| AP-29 | M-014 | utf-8-sig-BOM-Behandlung wie Git | 2ccbc54 |
| AP-29b (ab Z. 7025) | M-017 | Gits Verzeichnismarker-Präzedenz innerhalb einer Ebene (Git-Orakel) | 3e03bb0 |
| AP-30 (ab Z. 7176) | M-018 | relative_files-Coverage wird akzeptiert | bec84e2 |
| AP-30 | M-019 | Coverage-Parallel-Konfigurationen werden vereinigt | bec84e2 |
| AP-30 | M-071 | Module-Docstring deckt den echten Datenpfad | bec84e2 |
| AP-31 (ab Z. 7368) | M-069 | Strukturelle Parent-Fehler werden nicht wiederholt | ea2b2e7 |
| AP-31 | M-012 | Idempotente Probe mit Retry-Leiter | 98f3241 |
| AP-31 | M-011 | Republikation des Guards nur bei Notwendigkeit | 482b54f |
| AP-32 (ab Z. 7578) | M-066 | Jeder Sibling-fd wird exakt einmal geschlossen | f126552 |
| AP-32 | M-067 | Sibling-Erschöpfungsdiagnose in der Fehlermeldung | 60874c6 |
| AP-32 | M-013 | Exklusiv-Zufallsvalidierung ohne Handle-Link-Zählung | 9f886a0 |
| AP-32 | M-010 | Sibling-Namensbudget + deterministischer Pfadlängen-Skip | 13e6ae9/d6c1d04 |

### R1 — kompakte Fix-Liste (18 Gruppen; Detail in den geschlossenen Issues #141–#151 und im R1-Phasengate)

| AP | Gruppen | Kurzfassung |
|---|---|---|
| AP-00b | M-140 | Belastbarer Grandchild-Containment-Test |
| AP-01 | M-142, M-145, M-008, M-143 | Phase-Guard-Proof-Lebenszyklus; Publikationsfehler wird suspicious |
| AP-02 | M-034, M-002, M-031 | Staging Retain-Policy mit kanonischen Schlüsseln |
| AP-03 | M-003 | Mutation-Surface-Autorität (Exit 1 bei unvollständiger Fläche) |
| AP-04 | M-001 | Gitignore Tracked-Override |
| AP-05 | M-006, M-007 | Import-Basis (Marker-Bump) |
| AP-06 | M-005 | Apply Compare-and-swap |
| AP-07 | M-009, M-144 | Prozessidentität |
| AP-08 | M-004 | Monotoner I/O-Zähler über den Prozessbaum |
| AP-08b | M-139 | IL-Integrationstest-Vorbedingung |

**Hinweise für das Review:** Issue #192 (vier belegte Falschverdikte gezielter Mutation-Gates) und die dokumentierten NOT_EXECUTED-Gates sind bei der Testqualitäts-Linse explizit zu bewerten. Die finale Vollsuite (3360 passed / 2 version-governance-bedingte Failures) und das kanonische Semgrep-Gate (PASS) stehen als Gesamtevidenz bereit.

---

## AUFGABE 2: Bitte entscheidende zehn Fragen

Antworte je Gruppe im Format **„M-xxx = <A|B|C|eigene Formulierung>"** plus 1–2 Sätze Begründung (für die Releasehistorie). Die Empfehlungen stammen von GLM-5.3 und sind als solche markiert — Du kannst abweichen.

---

### 1. M-061 · AP-11 · Gitignore-Grenze im Core-Fingerprint (Handover Z. 2555–2613)
**Problem:** Die Core-Hasher walken ohne Gitignore-Boundary; ignorierte Laufartefakte können Läufe fail-closed als „failed" beenden. Der symmetrische Fix hat im Flat-Layout (Self-Editable, Projektwurzel bleibt im Kind-sys.path) eine Aufweichung: Ein ignoriertes, in-place importierbares Top-Level-Modul wäre in keinem Digest mehr sichtbar (der kombinierte Digest bindet es heute bereits nicht).
- **A (Empfehlung GLM-5.3):** Boundary überall symmetrisch; README-Zusage „ignoriert = keine Basis" wird eingelöst; Restrisiko Flat-Layout dokumentiert + per Test festgeschrieben.
- **B:** Import-Roots, die im Kind auf sys.path bleiben, ohne Boundary walken — strenger, erhält aber zwei Wurzelklassen mit dauerhafter Asymmetrie.

### 2. M-064/M-101 Stufe 2 · AP-12 · Lazy Endabgleich der Ausführungsbasis (Z. 2616–2892)
**Problem:** Jeder erfolgreiche Lauf hasht die Umgebung fünfmal vollständig. Stufe 2 (Kurzschluss bei exakter Gleichheit mit der Startbasis, 5→4 Pässe) ändert den Vertrag: Änderungen nach Worker-Ende enden heute „failed"/deautorisiert, danach „completed" mit `execution_basis_complete=True`.
- **A (Empfehlung GLM-5.3):** Stufe 2 umsetzen — Verdikte unberührt (Worker beendet, Job geschlossen), CI/CD-Export prüft den Live-Stand erneut (`_stable_live_basis`); ADR/Docstring + README dokumentieren. Zusätzlich Stufe 1 (Watchdog-Abdeckung) + Benchmark.
- **B:** Stufe 2 zurückstellen (nur Stufe 1 + Benchmark); Performance-Befund bleibt teilweise offen.

### 3. M-058 · AP-15 · Browser-Retest „Modul" bei Paket-__init__ (Z. 3551–3613)
**Problem:** Bei Mutanten aus `__init__.py` selektiert `retest-module` den ganzen Paketbaum. Fix: exakte Namensliste. Darüber hinaus: Bei nicht zugeordneten Namen (DB-only) Aktion verweigern statt Muster raten (Verhaltensänderung).
- **A (Empfehlung GLM-5.3):** Verweigerung bei fehlender Zuordnung (fail-closed, markiert, getestet, README).
- **B:** Altes Muster mit Warnung (weniger strikt, rät weiter).

### 4. M-022 · AP-16 · --since-commit: Bereichssyntax (Z. 3643–3703)
**Problem:** Der Wert geht unvalidiert an `git diff` (Options-/Pathspec-Deutung möglich). Fix: Validierung per `git rev-parse --verify --end-of-options`, nur kanonische OID + `--`. Entscheidungspunkt: Bereichsausdrücke (`A..B`, `main...HEAD`) funktionieren heute undokumentiert und würden abgelehnt.
- **A (Empfehlung GLM-5.3):** Bereiche mit Exit 2 ablehnen (Breaking der undokumentierten Syntax; CHANGELOG + Hinweis auf `git merge-base`).
- **B:** `...`-Form über `git merge-base --end-of-options` zu einer OID auflösen (CI-freundlich; zweiter Prozessstart, mehr Aufwand).

### 5. M-023 · AP-16 · Positivfilter inkrementeller Ziele (Z. 3822–3881)
**Problem:** Nur Negativfilter gegen exakt konfigurierte `tests_dir`; geänderte Testdateien außerhalb davon (z. B. `tests/conftest.py` bei `tests_dir=['tests/unit/']`) werden Mutationsziele. Fix: Ziel nur unter `paths_to_mutate`. Verhaltensänderungen: Dateien außerhalb `paths_to_mutate` (scripts/, setup.py) fallen inkrementell weg (volllaufkonsistent); `--paths-to-mutate` + `--since-commit` wird Schnittmenge statt Ersetzung.
- **A (Empfehlung GLM-5.3):** Positivfilter (inkrementelles Universum nie größer als Volllauf; CHANGELOG).
- **B:** Minimalfix — nur tests_dir kanonisieren/erweitern (heuristisch, verfehlt `tests/factories.py` und scripts/).

### 6. M-036 · AP-22 · Lockdomäne der Cache-Datenbank (ADR, Z. 5197–5263)
**Problem:** DB-Lockschlüssel hängen an `tempfile.gettempdir()`; divergierende TEMP-Werte erlauben doppelten „exklusiven" Zugriff, `_recover_abandoned_run` beendet fremde Läufe. Drei Wege:
- **A (Empfehlung GLM-5.3):** Colocation im kanonischen DB-Elternverzeichnis — global pro DB, kein Temp-Fallback, Hardlink-DB fail-closed (`RunLockCorruptError`), Staging-/Basis-Excludes erweitert, ADR. (3 Hardlink-Vertragstests brechen bewusst; Lockdateien liegen sichtbar im DB-Verzeichnis.)
- **B:** Per-User Known-Folder (LocalAppData) — kleiner Eingriff, behebt nur divergierende TEMP desselben Benutzers, Cross-User bleibt getrennt.
- **C:** ProgramData maschinenweit — echte Globalität, aber ACL-/Squatting-Problematik, Security-Review, Aufwand L+.

### 7. M-041 · AP-24 · NFKC-Kodierung von Mutanten-IDs (identitätsändernd, Z. 5571–5632)
**Problem:** NFKC-äquivalente Namen (K vs. U+FF2B) kollidieren in den privaten Trampoline-Bindungen. Fix: Hex-Kodierung (`xq_`) für nicht-NFKC-normale Namen. Breite:
- **A (Empfehlung GLM-5.3):** **Alle** nicht-NFKC-normalen Namen bekommen neue IDs, auch ohne Kollision — deterministisch, kontextunabhängig; alte IDs verwaisen (Cache, dokumentiert; Anzeige hex-kodiert).
- **B:** Nur bei tatsächlicher NFKC-Kollision — IDs ändern sich durch fremde Funktionen im Modul (kontextabhängig; vom Review abgelehnt).

### 8. M-102 · AP-27 · Timeout-Modell: Diagnosezeile (Z. 6552–6608)
**Problem:** Der dokumentierte „selected test time"-Budgetzweig ist unerreichbar (`mapping_is_authoritative` nie True); jede Task erhält das Full-Suite-Budget. Pflicht ist nur die Docstring-Korrektur (kein P-08). Separat freigabepflichtig: eine stdout-Zeile je Lauf, wenn Fallback-Tasks mit Timingdaten existieren.
- **A (Empfehlung GLM-5.3):** Diagnosezeile freigeben (im JSON-Modus über den bestehenden stdout→stderr-Redirect; JSON-Kanal bleibt sauber).
- **B:** Nur Docstring; Zeile zurückstellen.

### 9. M-016 · AP-29b · Case-insensitives Gitignore-Matching + pathspec-Pin (Z. 7114–7172)
**Problem:** Ignore-Matching ist case-sensitiv, Git unter Windows nicht — ignorierte Bäume landen im Basis-Hash; Negationen verfehlen Treffer. Fix: ASCII-Faltung `(?ai)` über private pattern_factory. P-08-relevant zudem: pathspec-Pin `>=1.1.1,<2` → `<1.2` straffen (Abhängigkeitsvertrag, chore(deps)-Commit mit uv.lock-Beleg) und einmalig geänderter Baumdigest betroffener Projekte.
- **A (Empfehlung GLM-5.3):** ASCII-Faltung + Pin-Straffung mit Guard-Test (Windows-Produktvertrag; Git faltet per tolower nur ASCII).
- **B:** `core.ignorecase` per `git config --bool` lesen und nur dann falten (git-exakt; zusätzlicher Prozess je Lauf).
- **C:** Zurückstellen (Matching bleibt case-sensitiv, nur dokumentiert — Basis-Hash-Defekt bleibt).

### 10. M-042 · AP-23 · Bestätigung: Dokumentationsroute dekorierte Klasse (bereits umgesetzt)
Keine neue Optionenwahl: Der Subagent hat die gesperrte dekorierte Klasse **dokumentiert** (Commit `e9bfbee`, technische Begründung im README/mutation.py) statt das Verhalten zu ändern. Bitte kurz bestätigen: **Dokumentationsroute OK** oder Verhaltensänderung nachholen (dann spezifizieren).

---

## Bitte zusätzlich

1. **Reihenfolge-Empfehlung** falls knapp: welche der Entscheidungen priorär andere APs entblocken (M-061→AP-11-Rest, M-064/M-101→AP-12-Rest, M-058→AP-15-Rest, M-022/M-023→AP-16-Rest, M-036→AP-22-Rest, M-041→AP-24-Rest, M-102→AP-27-Rest, M-016→AP-29b).
2. Format Deiner Antwort: je Gruppe eine Zeile `M-xxx = X`, danach 1–2 Sätze Begründung. Die orchestrierende Instanz setzt die Entscheidungen um, dokumentiert sie in README/Releasehistorie und in den Issues, und hängt die abgelehnten Varianten mit Status „per Entscheidung zurückgestellt" an.

*Vollständige Analysen mit Tests, Alternativen und Risiken je Gruppe: `HANDOVER_GLM-5.3.md` an den oben genannten Zeilen; Empfehlungen mit Konsequenzabschätzung: `P08_ENTSCHEIDUNGEN_R2_OFFEN.md`.*
