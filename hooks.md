# Hook-Tracking-Protokoll

**Zweck:** Protokolliert ob die Hooks in `.claude/hooks/` korrekt feuern.
**Erstellt:** 2026-03-30
**Gilt ab:** Sprint 14 (v1.0.0 Entwicklung)

---

## Hook-Übersicht

| Hook | Trigger | Datei | Liest aus |
|------|---------|-------|----------|
| sprint-health | SessionStart | sprint-health.sh | .sprint/state.md YAML-Frontmatter |
| sprint-gate | PostToolUse (git commit) | sprint-gate.sh | housekeeping_done |
| sprint-state-save | PreCompact | sprint-state-save.sh | Gesamte state.md |
| post-compact-reminder | PostCompact | post-compact-reminder.sh | Sprint-Frontmatter |
| verify-after-agent | SubagentStop | verify-after-agent.sh | Ruff/mypy/pytest/Semgrep |
| statusline | Permanent | statusline.sh | current_sprint, housekeeping_done |
| sprint-housekeeping-reminder | Stop | sprint-housekeeping-reminder.sh | HK-Items |

---

## Hook-Findings (zu fixen nach Sprint 20)

| # | Hook | Finding | Severity |
|---|------|---------|----------|
| H-01 | sprint-gate.sh | Sucht Sprint Backlog mit `find . -maxdepth 4` statt in `_docs/sprint backlogs/` — **FIX PENDING** | HIGH |
| H-02 | sprint-gate.sh | Sprint Backlogs Sprint 1-13 nie erstellt — weil H-04 (Matcher-Bug) den Hook nie feuern ließ | HIGH (Folge von H-04) |
| H-03 | sprint-health.sh | ~~Feuert nicht~~ **GEFIXT**: Hook feuert korrekt! Output erscheint als `<system-reminder>` am Session-Start, nicht als Chat-Nachricht. War die ganze Zeit aktiv. | RESOLVED |
| H-04 | PostToolUse | **ROOT CAUSE**: Matcher ist REGEX, nicht Glob. `Bash(*git commit*)` = ungültiger Regex. Fix: Matcher `Bash` (Catch-All) + Commit-basierte Filterung im Skript via `.sprint/.last-gate-commit` Marker. **VERIFIZIERT: Gate-Marker wird geschrieben.** | FIXED + VERIFIED |
| H-05 | copy_also_copy | `tests/` Default kopiert .venv-Symlinks → WinError 1920 | HIGH |
| H-06 | Dogfooding | ~~Worker ModuleNotFoundError~~ GEFIXT (multiprocessing.Pool→sequential). Verbleibendes Problem: Dogfooding (mutmut-win auf sich selbst) ist ein Sonderfall — Trampoline wirkt nur auf Ziel-Projekt-Code, nicht auf mutmut-win's eigenen Code. Normaler Use Case funktioniert. | WONTFIX (by design) |
| H-07 | CLI | 10 neue CLI-Flags (3 Tiers): --paths-to-mutate, --min-score, --output json, --since-commit (USP!), --tests-dir, --no-progress, --debug, --dry-run, --timeout-multiplier, --do-not-mutate. ~165 LOC. | HIGH |

---

## Sprint 14: Regex-Mutationen

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | MANUELL getestet | Ja | Sprint 14 erkannt, Branch-Warning korrekt, HK-Items aufgelistet. Hook feuert NICHT automatisch bei SessionStart — muss untersucht werden |
| sprint-gate (git commit) | NEIN | — | Kein Output nach git commit sichtbar. Finding H-04 bestätigt |
| verify-after-agent (SubagentStop) | N/A | — | Kein Subagent in Sprint 14 verwendet |
| statusline | MANUELL getestet | Ja | `S14 [HK!] \| main \| 11mod` korrekt. Automatisch: unklar |
| sprint-housekeeping-reminder (Stop) | | | Wird bei Session-Ende geprüft |

## Sprint 15: Math-Methoden

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | | | |
| sprint-gate (git commit) | | | |
| verify-after-agent (SubagentStop) | | | |
| statusline | | | |

## Sprint 16: Return Value Replacement

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | | | |
| sprint-gate (git commit) | | | |
| verify-after-agent (SubagentStop) | | | |
| statusline | | | |

## Sprint 17: Conditional Expression

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | | | |
| sprint-gate (git commit) | | | |
| verify-after-agent (SubagentStop) | | | |
| statusline | | | |

## Sprint 18: Statement Removal

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | | | |
| sprint-gate (git commit) | | | |
| verify-after-agent (SubagentStop) | | | |
| statusline | | | |

## Sprint 19: Collection-Methoden

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | | | |
| sprint-gate (git commit) | | | |
| verify-after-agent (SubagentStop) | | | |
| statusline | | | |

## Sprint 20: or-Default

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | | | |
| sprint-gate (git commit) | | | |
| verify-after-agent (SubagentStop) | | | |
| statusline | | | |
| sprint-housekeeping-reminder (Stop) | | | Letzer Sprint — Session-End |
