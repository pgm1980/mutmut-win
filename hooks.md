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

## Sprint 14: Regex-Mutationen

| Hook | Gefeuert? | Output korrekt? | Notizen |
|------|-----------|------------------|---------|
| sprint-health (SessionStart) | | | |
| sprint-gate (git commit) | | | |
| verify-after-agent (SubagentStop) | | | |
| statusline | | | |
| sprint-housekeeping-reminder (Stop) | | | |

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
