# Hook Inspection Log

**Zweck:** Protokolliert ob die Hooks in `.claude/hooks/` korrekt feuern und ihre Tasks ausführen.
**Erstellt:** 2026-03-30

---

## SessionStart Hook (`sprint-health.sh`)

| Zeitpunkt | Sprint | Gefeuert? | Frontmatter erkannt? | Ausgabe korrekt? | Notizen |
|-----------|--------|-----------|---------------------|------------------|---------|
| Sprint 8 Start | 8 | ✅ Ja | ✅ Ja | ✅ Ja | Sprint 8 korrekt erkannt, Branch-Warnung (main → erwartet feature branch), HK-Items aufgelistet |

## PostToolUse Hook (`sprint-gate.sh` — Matcher: git commit)

| Zeitpunkt | Sprint | Gefeuert? | Gate aktiv? | Blocker erkannt? | Notizen |
|-----------|--------|-----------|------------|------------------|---------|
| Sprint 8 Commit (file_setup) | 8 | ✅ Ja | ✅ Ja (housekeeping_done=false) | ✅ 4 Blocker: MEMORY.md, 32 Issues, Backlog, Semgrep | Korrekt — Gate warnt vor Housekeeping |
| Sprint 9 Commit (test_mapping) | 9 | ✅ Ja | ✅ Ja | ✅ 4 Blocker identisch | Gate feuert konsistent bei jedem Commit |
| Sprint 10 Commit (mutant_diff) | 10 | ✅ Ja | ✅ Ja | ✅ 4 Blocker identisch | Gate konsistent über alle 3 Sprints |
| Sprint 11 Commit (in-process stats) | 11 | ✅ Ja | ✅ Ja | ✅ Blocker erkannt | Konsistent |
| Sprint 12 Commit (completeness) | 12 | ✅ Ja | ✅ Ja | ✅ Blocker erkannt | Konsistent über alle Sprints |

## SubagentStop Hook (`verify-after-agent.sh`)

| Zeitpunkt | Sprint | Gefeuert? | Ruff OK? | mypy OK? | Tests OK? | Semgrep OK? | Notizen |
|-----------|--------|-----------|----------|----------|-----------|-------------|---------|
| Sprint 8 file_setup Agent | 8 | ✅ Ja (implicit — Agent tool returned) | ✅ Ruff 0 | ⚠️ 27 pre-existing | ✅ 308 passed | ⏭️ Nicht geprüft | Hook feuert, verify-after-agent prüft "." statt "src/" |
| Sprint 9 test_mapping Agent | 9 | ✅ Ja | ✅ Ruff 0 | ⚠️ pre-existing | ✅ 350 passed | ⏭️ Nicht geprüft | Konsistent |
| Sprint 10 mutant_diff Agent | 10 | ✅ Ja | ✅ Ruff 0 | ⚠️ pre-existing | ✅ 368 passed | ⏭️ Nicht geprüft | Konsistent |

## StatusLine Hook (`statusline.sh`)

| Zeitpunkt | Sprint | Ausgabe | Korrekt? | Notizen |
|-----------|--------|---------|----------|---------|
| Sprint 8 Start | 8 | `S8 [HK!] \| main \| 7mod` | ✅ Ja | Sprint, HK-Flag, Branch, Uncommitted korrekt |

## PreCompact Hook (`sprint-state-save.sh`)

| Zeitpunkt | Sprint | Gefeuert? | Context gespeichert? | Notizen |
|-----------|--------|-----------|---------------------|---------|
| (wird bei Komprimierung protokolliert) | | | | |

## PostCompact Hook (`post-compact-reminder.sh`)

| Zeitpunkt | Sprint | Gefeuert? | Reminders ausgegeben? | Sprint-State korrekt? | Notizen |
|-----------|--------|-----------|----------------------|----------------------|---------|
| (wird bei Komprimierung protokolliert) | | | | | |

## Stop Hook (`sprint-housekeeping-reminder.sh`)

| Zeitpunkt | Sprint | Gefeuert? | Uncommitted gewarnt? | HK-Items gewarnt? | Notizen |
|-----------|--------|-----------|---------------------|-------------------|---------|
| (wird bei Session-Ende protokolliert) | | | | | |
