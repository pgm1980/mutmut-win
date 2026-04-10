# Feature Request: Timeout-Diagnostics in mutmut-win

**Date:** 2026-04-10
**Version:** mutmut-win 2.0.2
**Reporter:** pgm1980/nextgen-cot-mcp-server

---

## Problem

Wenn ein Mutant den Timeout erreicht (default 60s), speichert mutmut-win nur:
- `status = "timeout"`
- `exit_code = 36`
- `duration = 60.0`

Es gibt keine Information **warum** der Timeout auftrat. Der Entwickler muss jeden Timeout-Mutanten manuell untersuchen.

## Konkretes Beispiel

In unserem Projekt haben 14 von 42 Mutanten auf `identifiers.py` den Timeout erreicht. Die Ursache war hypothesis-Tests mit `deadline=None` die bei bestimmten Mutationen (TypeError, gebrochene UUID-Struktur) in lange Shrinking-Phasen gehen.

Das herauszufinden erforderte:
1. Alle 42 Mutanten einzeln mit `MUTANT_UNDER_TEST=...` manuell laufen lassen
2. Die mutierten Source-Dateien in `mutants/src/` analysieren
3. Jede Mutation manuell mit dem Original vergleichen

## Vorgeschlagene Erweiterung

### 1. Letzte pytest-Ausgabe bei Timeout speichern

Wenn ein Worker den Timeout erreicht, die letzten N Zeilen der pytest-Ausgabe (stdout/stderr) in der Ergebnis-DB speichern:

```sql
ALTER TABLE mutant ADD COLUMN last_output TEXT;
```

Dann bei `mutmut-win results`:
```
Timeout mutants:
  x_uuid7__mutmut_22 (60.0s): TypeError: to_bytes() missing required argument: 'byteorder'
  x_uuid7__mutmut_27 (60.0s): FAILED test_uuid7_version_is_7 - assert 3 == 7
  x_uuid7__mutmut_42 (60.0s): TypeError: expected bytes, got NoneType
```

### 2. Mutation-Diff in der Ergebnis-DB speichern

Für jeden Mutanten die konkrete Code-Änderung speichern:

```sql
ALTER TABLE mutant ADD COLUMN mutation_diff TEXT;
```

```
  x_uuid7__mutmut_22: to_bytes(6, "big") → to_bytes(6, )
  x_uuid7__mutmut_27: 0x70 | (...) → 0x70 & (...)
```

### 3. `--timeout-detail` Flag

```bash
uv run mutmut-win results --timeout-detail
```

Zeigt für jeden Timeout-Mutanten:
- Die konkrete Mutation (Diff)
- Die letzte pytest-Zeile vor dem Kill
- Die gemappten Tests die liefen
- Empfehlung: "Consider adding `deadline=5000` to hypothesis tests" oder "Test does not detect this mutation within timeout"

### 4. Timeout-Kategorie unterscheiden

Nicht alle Timeouts sind gleich:
- **"Slow Kill"**: Test erkennt die Mutation, braucht aber >60s dafür → eigentlich ein Kill
- **"True Timeout"**: Test läuft endlos (Endlosschleife durch Mutation) → echter Timeout
- **"Flaky Timeout"**: Test schlägt manchmal schnell fehl, manchmal nicht → instabiler Test

Die Unterscheidung wäre möglich durch:
- Wenn der Prozess `FAILED` in stdout hatte bevor er gekillt wurde → "Slow Kill"
- Wenn der Prozess keine Ausgabe mehr produzierte → "True Timeout"
