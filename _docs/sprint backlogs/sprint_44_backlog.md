# Sprint 44 Backlog

| | |
|---|---|
| **Ziel** | v2.21.5 |
| **Baseline** | Sprint 43 (R0) auf `fix/v2.21.5-remediation-r0`, Commit `6ad89d4`; Codebasis identisch mit v2.21.4/`4d7f950` |
| **Scope** | Windows und exakt CPython 3.14.7 |
| **Branch** | `fix/v2.21.5-remediation-r1` |
| **Start** | 2026-09-24 |
| **Statusautorität** | `.sprint/state.md` sowie der unmittelbar vor Remote-Writes live geprüfte GitHub-Zustand |

<!-- RELEASE_SEQUENCE: version-bump -> final-gates -> merge-main -> integrated-final-gates -> reproducible-artifacts -> annotated-tag -> github-release -->

Eine billingbedingt nicht gestartete GitHub-CI wird als `NOT_EXECUTED`
behandelt: eine Evidenzlücke, weder PASS noch FAIL. Ausgeführte rote CI
bleibt sichtbar rot.

## Auslöser

Phase R1 der Sanierung v2.21.4: alle 9 P1-Gruppen, in der Reihenfolge
falsche/als korrekt ausgewiesene Ergebnisse (M-008, M-002, M-003, M-001),
stille Wiederverwendung auf unvollständiger Basis (M-006, M-007),
Datenverlust und Fremdwirkung (M-005, M-009), zuletzt M-004. Die beiden
fragilen Tests M-140 (AP-00b) und M-139 (AP-08b) werden vorgezogen.

## Arbeitsumfang (R1: AP-00b, AP-01 bis AP-08, AP-08b)

- [ ] AP-00b / M-140: Belastbarer Grandchild-Containment-Test (Job Object) mit PID-Synchronisation, Negativkontrolle und Sabotagenachweis (Issue #142; Serena-Verifikation: bestätigt)
- [ ] AP-01 / M-142, M-145, M-008, M-143: Phase-Guard-Proof-Lebenszyklus im Worker (Issue #143; wartet auf P-08-Entscheidung M-008)
- [ ] AP-02 / M-034, M-002, M-031: Staging-Retain-Policy und kanonische Mutationswurzeln inkl. Staging-Benchmark vorher/nachher (Issue #144)
- [ ] AP-03 / M-003: Degradierte Mutationsfläche sichtbar und gate-wirksam (Issue #145; wartet auf P-08-Entscheidung M-003)
- [ ] AP-04 / M-001: Getrackte Quellen gegen Gitignore-Pruning schützen (Issue #146)
- [ ] AP-05 / M-006, M-007: Vollständige effektive Importbasis (.venv im Projekt, ZIP-Unterpfade) (Issue #147)
- [ ] AP-06 / M-005, M-114: apply: Compare-and-swap-Publikation (Issue #148)
- [ ] AP-07 / M-009, M-144: Prozessidentität statt nackter PID (Issue #149; Stufe 1 entscheidungsfrei, Stufe 2 wartet auf P-08)
- [ ] AP-08 / M-004 + AP-08b / M-139: IL-Erkennung über monotonen I/O-Zähler; IL-Integrationstest-Vorbedingung (Issues #150, #151)

## Abgrenzungen

- AP-Branches zweigen von `fix/v2.21.5-remediation-r1` ab (AP-00/R0 ist noch nicht nach `main` gemergt — Nutzerfreigabe ausstehend); die Sprint-State referenziert den R1-Integrationsbranch.
- Jede Gruppe durchläuft das Pflichtprotokoll (Serena-Verifikation, Widerlegungskriterien, rot-vor-Fix-Regressionstest) vor jeder Codeänderung; Verifikationsergebnisse stehen in den AP-Issues.
