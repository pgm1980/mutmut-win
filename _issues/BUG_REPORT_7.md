# BUG REPORT 7: mutmut-win 2.0.3 — Timeout-Diagnostics fehlen

**Reporter:** pgm1980/nextgen-cot-mcp-server
**Date:** 2026-04-10
**Version:** mutmut-win 2.0.3 (git tag v2.0.3)
**Severity:** Minor (Feature fehlt, nicht Crash)

---

## Erwartung

Laut FEATURE_REQUEST_TIMEOUT_DIAGNOSTICS.md sollte v2.0.3 erweiterte Timeout-Informationen liefern:

1. **Letzte pytest-Ausgabe** bei Timeout (stdout/stderr vor dem Kill)
2. **Mutation-Diff** pro Mutant (welche Zeile wurde wie geändert)
3. **Timeout-Kategorie** (Slow Kill vs. True Timeout)

## Tatsächliches Verhalten

Das DB-Schema in `.mutmut-cache/mutmut-cache.db` ist unverändert:

```sql
-- v2.0.3 Schema (identisch mit v2.0.2)
CREATE TABLE mutant (
    mutant_name TEXT,
    status TEXT,
    exit_code INTEGER,
    duration REAL
);
```

Keine neuen Spalten (`last_output`, `mutation_diff`, `timeout_category`).

`uv run mutmut-win results` zeigt bei Timeout-Mutanten nur:

```
Timeout:   15
```

Keine Details welche Mutanten Timeouts hatten, warum, oder was die letzte Testausgabe war.

## Verifizierung

```bash
uv run python -c "
import sqlite3
conn = sqlite3.connect('.mutmut-cache/mutmut-cache.db')
cols = [c[1] for c in conn.execute('PRAGMA table_info(mutant)').fetchall()]
print('Columns:', cols)
# Output: ['mutant_name', 'status', 'exit_code', 'duration']
# Expected: + 'last_output', 'mutation_diff', 'timeout_category'
"
```

## Konkrete Auswirkung

15 von 42 Mutanten auf `identifiers.py` sind Timeouts. Ohne Diagnostics mussten wir diese manuell analysieren (alle 42 Mutanten einzeln mit `MUTANT_UNDER_TEST=...` und `timeout 30` laufen lassen, dann die mutierte Source-Datei durchlesen). Das hat ~30 Minuten gedauert.

Mit Diagnostics wäre das eine Sache von `uv run mutmut-win results --timeout-detail`.
