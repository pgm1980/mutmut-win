# Sprint 46 Backlog

| | |
|---|---|
| **Ziel** | v3.0.0 |
| **Baseline** | Sprint 45 (R2-Nachbesserung) abgeschlossen auf `main` (`ee34729`); Abnahmeinstrument ist das R0-R4-Master-Ledger (146 Gruppen, glm-followup) |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v3.0.0-remediation-r3` |
| **Start** | 2026-10-02 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot.

## Auslöser

Phase R3 des Remediation-Programms v2.21.4 → 3.0.0 (GitHub-Issues
#177–#190, Gruppen M-068 bis M-146) nach dem Abschluss von R0/R1/R2 und
dem v2.21.5-Release. 43 Gruppen mit Rot-Beweis vor jedem Fix; eine Gruppe
(M-097) per dokumentierter Entscheidung deferred, vier Gruppen nach
Gegenbeweis widerlegt und gepinnt. Abschluss per Release 3.0.0 (AP-47) mit
dokumentierter Abweichung für die abgebrochene Modul-Gate-Kampagne.

## Arbeitsumfang (R3-Welle AP-33 bis AP-46 + Release AP-47)

- [x] Staging-Topologie und Stream-Kopie: AP-33 (M-078, M-082, M-083 streamend/Readonly-Cleanup), AP-37 (M-084, M-086, M-087 Walk-Helfer/Link-Abwehr/NTFS-Faltung), AP-38 (M-085, M-089 Verzeichnis-Erwartungen/Meta-Invalidierung)
- [x] Executor- und Prozess-Ressourcenlebenszyklus: AP-34 (M-090, M-091, M-092), AP-35 (M-093 RunLock-Fehlertaxonomie), AP-39 (M-104, M-108 Ctrl-C-Abschluss/stdout)
- [x] Forced-Fail-Nachweis und Testinventar-Parität: AP-40 (M-105, M-106), AP-41 (M-107, M-109 inkl. M-130-Fix-Beweismechanik)
- [x] Browser-Diff: AP-42 (M-117, M-118, M-119, M-119 generationsbasiert, begrenzt, nach App-Ende sicher)
- [x] Metadaten-Modelle: AP-43 (M-121 normalisierte Digests, M-122 Score-Doku, M-123 overflow-feste Zahlen)
- [x] Basis-Scan und Stats-Cache: AP-44 (M-124, M-125, M-126 Registrierung/Dedup/Diagnose), AP-45 (M-132–M-136 robuster Lader), AP-46-Zahlen (M-137, M-138, M-141)
- [x] Mutation-surface-Doku und widerlegte Gruppen: AP-46 (M-127, M-128, M-129, M-131, M-142–M-146); widerlegt/gepinnt: M-085, M-138 (Refutation) u. a.; deferred: M-097 (dokumentiert offen)
- [x] Modul-Gate-Kampagne (AP-47, nach Auftraggeberentscheidung abgebrochen und als dokumentierte Abweichung freigegeben): 3 PASS (output_capture 57,3 %, suspended_spawn 34,8 %, trampoline 66,7 % + Adjudizierung ~93,6 %), 2 BLOCKED (models/browser: Trampolin-Grenze klassenlastiger Module, Produkt-Bug widerlegt), db-Teilevidenz 288/2.622 (24,3 % Kill), Rest NOT_EXECUTED — Matrix AR27-GATE-MATRIX.md §7
- [x] Release 3.0.0: Release-Vollsuite 3.668/1/44 mit Root-Cause-Fix `ea0069c` [M-112-fix] (PEP 758) und gezielter Grün-Nachführung (88 passed); Testspezifikation `_docs/testmanagement/test_specification.md`; Merge PR #197 (`99db317`, Baum byte-identisch zu `d291ee5`), annotierter Tag `v3.0.0`, GitHub-Release, Issues #177–#191 mit Receipts geschlossen, Sprint-Housekeeping
