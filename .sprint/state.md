---
current_sprint: "31"
sprint_goal: "v2.9.0 Feature Truth & Score Integrity — tote Features (Type-Check-Filter, Coverage) ehrlich reaktivieren oder abschalten; Score-Pipeline lückenlos (Buckets, Exit-Code-Map, Ctrl-C-Abbruch, Orphans, JSON-Kanal)."
branch: "feature/v2.9.0-score-integrity"
started_at: "2026-06-11"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: true
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State (Sprint 31 opened 2026-06-11)

## Current Focus
Sprint 31 — **v2.9.0 Feature Truth & Score Integrity** — geplant,
Implementierung noch nicht gestartet (wartet auf „Go"). Basis: Audit-Cluster
**C6 + C7**. Die beiden tot beworbenen Features (Type-Check-Filter auf drei
Ebenen gebrochen, Coverage ohne Subprozess-Brücke) werden ehrlich, die
Score-Pipeline wird lückenlos. Issues #91–#97 angelegt. Branch
`feature/v2.9.0-score-integrity`.

## Sprint 31 Backlog (33 SP — Must 26, Should 7)
1. **#91 (Must, 5 SP):** Status-Wahrheit — Exit-Code-Map (−24-Dublette,
   0xC0000005, Exit-2-Entscheid per CoT ≥3), vollständige Summary-Buckets +
   Catch-All + Summen-Invariante, generisches results-Rendering.
2. **#92 (Must, 5 SP):** type_checking.py härten — Basename-Erkennung
   (mypy.exe/uv run mypy — heute Lauf-ABBRUCH auf Windows), timeout/
   returncode/encoding, pyright-Severity-Filter. Context7 PFLICHT.
3. **#93 (Must, 8 SP):** Type-Check end-to-end — kanonisches Matching
   (CM-002: matcht heute NIE), Task-Schnittmenge (OS-009), DB-Persistenz
   (OS-003), Leerheits-Guard (OS-010), E2E mit echtem mypy. NACH #91+#92.
4. **#94 (Must, 3 SP):** Ctrl-C-Ehrlichkeit — was_interrupted + unchecked,
   Exit 130, Gate-Skip.
5. **#95 (Must, 5 SP):** Coverage timeboxed Spike → Entscheid-CoT ≥8 →
   Einbau ODER ehrliche Deaktivierung. Kernfrage Zeilen-Referenzsystem.
   Context7 für coverage-API.
6. **#96 (Should, 5 SP):** DB-Orphans — Design-CoT ≥8, Tendenz
   Purge-bei-Voll-Lauf mit Subset-Guard (destruktiv → Tests zuerst).
7. **#97 (Should, 2 SP):** CI-Kanal — score im JSON (additiv),
   0-Mutanten-Gate-Kommunikation. ZULETZT (finale Modellform).

Scope-Ventil: #96/#97 → Sprint 32 bei Blowup; #95 weicht bei Timebox-Riss
auf den Deaktivierungs-Pfad aus.

## Planungs-Erkenntnisse (12-Schritt-CoT)
- Map zuerst: constants.status_by_exit_code ist das Fundament aller
  Downstream-Konsumenten — Korrekturen danach wären Doppelarbeit.
- Exit-2-Default: `2 → killed` (Worker-Ctrl-C strukturell vom
  Orchestrator-Pfad getrennt; Collection-Error = beobachtbare
  Verhaltensänderung); Forensik via last_output statt neuem Status.
- Score-Korrekturen (Phantom-caught weg, Segfault/Collection-Kills rein)
  im Changelog als „score corrections" ausweisen — CI-Gates können kippen.
- summary.type_check_caught ist heute verwaist (caught fließt in killed).
- Alle C6/C7-Befunde am v2.8.0-Stand re-verifiziert (Planungsphase).

## Out of scope (Roadmap unverändert)
C8+C9 (Sprint 32 / v2.10.0) inkl. 3 vorgemerkter Pipeline-Hygiene-Punkte
und OS-012-mtime-Teil; Mutation-Gate deferred bis C8; pip-audit (SSL).
