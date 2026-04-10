# BUG REPORT 6: mutmut-win 2.0.0 — Worker-Hang ab ~Mutant 29/42

**Reporter:** Claude Code Agent (pgm1980/nextgen-cot-mcp-server)
**Date:** 2026-04-10
**Version:** mutmut-win 2.0.0 (git tag v2.0.0)
**Severity:** Major (Mutation-Run kann nicht abgeschlossen werden)
**Environment:** Windows 11 Pro 10.0.26200, Python 3.14.3, uv 0.11.6, 24 CPU-Cores

---

## Summary

mutmut-win 2.0.0 hängt reproduzierbar bei ~29/42 Mutanten wenn `identifiers.py` mutiert wird. Die Clean-Test-Suite und die Forced-Fail-Verification laufen korrekt durch. Das Mapping-System funktioniert (274 Mappings aus 912 Tests — grosser Fortschritt gegenüber v1.0.x). Aber der Worker-Pool hängt während der eigentlichen Mutation-Phase.

**Bewiesene Kernaussage:** Kein einzelner Mutant verursacht den Hang. Alle 42 Mutanten laufen sequentiell mit `timeout 30` in 5-13 Sekunden durch. Das Problem liegt im Worker-Management, nicht in den Tests oder Mutanten.

---

## Reproduktion

### Umgebung

```
OS:       Windows 11 Pro 10.0.26200
Python:   3.14.3
uv:       0.11.6
CPU:      24 Cores (AMD/Intel)
Projekt:  64 Source-Dateien, 915 Tests (unit + integration + property + benchmark)
```

### Minimaler Reproduktionsschritt

```bash
rm -rf mutants/ .mutmut-cache/
uv run mutmut-win run --paths-to-mutate src/nextgen_cot_mcp_server/infrastructure/identifiers.py --max-children 20
```

### Erwartetes Verhalten

42 Mutanten werden in ~10-30 Sekunden verarbeitet (42 Mutanten x ~7s / 20 Worker).

### Tatsächliches Verhalten

```
Running clean test suite…
Collecting test timing statistics…
Collected 274 test-to-mutant mappings across 912 tests.
Running forced-fail verification…
1/42  🎉 1  🫥 0  ⏰ 0  🤔 0  🙁 0  🔇 0  🧙 0
...
29/42  🎉 24  🫥 0  ⏰ 0  🤔 0  🙁 5  🔇 0  🧙 0
<--- HÄNGT HIER, kein weiterer Fortschritt, CPU-Last fällt auf ~5% --->
```

Der Prozess wird nie beendet. Kein Exit-Code, keine Fehlermeldung. Die CPU-Last fällt nach ~29 Mutanten von ~95% auf ~5%.

---

## Beweis: Kein Mutant verursacht den Hang

Alle 42 Mutanten wurden einzeln mit `timeout 30` getestet. Keiner hängt:

```bash
for i in $(seq 1 42); do
  PYTHONPATH="$(pwd)/mutants/src" \
  MUTANT_UNDER_TEST="nextgen_cot_mcp_server.infrastructure.identifiers.x_uuid7__mutmut_$i" \
  timeout 30 .venv/Scripts/python.exe -m pytest mutants/tests/ -m "not no_mutmut" -q --tb=no
done
```

### Ergebnisse (alle 42 Mutanten):

| Mutant | Ergebnis | Dauer | Killed? |
|--------|----------|-------|---------|
| 1 | 264 failed, 638 passed, 10 errors | 5.79s | Ja |
| 2 | 264 failed, 638 passed, 10 errors | 4.91s | Ja |
| 3 | 264 failed, 638 passed, 10 errors | 4.79s | Ja |
| 4 | 264 failed, 638 passed, 10 errors | 4.72s | Ja |
| 5 | 264 failed, 638 passed, 10 errors | 4.82s | Ja |
| 6 | 1 failed, 911 passed | 6.94s | Ja |
| 7 | 264 failed, 638 passed, 10 errors | 8.23s | Ja |
| 8 | 1 failed, 911 passed | 6.99s | Ja |
| 9 | 3 failed, 909 passed | 7.87s | Ja |
| 10 | 912 passed | 6.89s | **Nein** (survived) |
| 11 | 220 failed, 682 passed, 10 errors | 6.86s | Ja |
| 12 | 264 failed, 638 passed, 10 errors | 4.99s | Ja |
| 13 | 912 passed | 7.03s | **Nein** |
| 14 | 912 passed | 7.11s | **Nein** |
| 15 | 264 failed, 638 passed, 10 errors | 8.30s | Ja |
| 16-26 | (mixed) | 4.8-8.3s | Ja/Nein |
| 27 | 2 failed, 910 passed | 7.13s | Ja |
| 28 | 912 passed | 7.02s | **Nein** |
| 29 | 1 failed, 911 passed | 7.72s | Ja |
| 30 | 912 passed | 6.95s | **Nein** |
| 31-42 | (mixed) | 6.5-13.3s | Ja/Nein |

**Maximale Laufzeit eines einzelnen Mutanten: 13.26 Sekunden (Mutant 41).**
**Kein Mutant hängt oder überschreitet 30 Sekunden.**

---

## Beobachtetes Hang-Muster bei verschiedenen Worker-Konfigurationen

| Config | Fortschritt | Dann |
|--------|------------|------|
| `--max-children 4` | 29/42 | Hang |
| `--max-children 20` | 29/42 | Hang |
| `--max-children 1` | Forced-fail-Phase | Hang (kein Output nach "Running forced-fail verification…") |

Der Hang tritt bei verschiedenen Worker-Zahlen auf, immer ungefähr beim selben Mutanten (~29).

---

## Was funktioniert

1. **Clean-Test-Suite:** Bestanden (912 passed, 1 deselected via `-m "not no_mutmut"`)
2. **Test-to-Mutant-Mappings:** Korrekt (274 Mappings aus 912 Tests)
3. **Forced-Fail-Verification:** Manuelle Ausführung bestanden (kein Hang)
4. **Alle 42 Mutanten individuell:** Alle in 5-13s abgeschlossen
5. **Version 2.0.0:** Korrekt installiert und angezeigt

---

## Hypothese

Der Worker-Pool-Manager hat ein Deadlock- oder Race-Condition-Problem:
- Worker senden Ergebnisse via Queue an den Hauptprozess
- Ab ~29 Ergebnissen blockiert entweder die Queue (voll?) oder der Ergebnis-Consumer (missed Event?)
- Die verbleibenden Worker warten auf Bestätigung, der Hauptprozess wartet auf Ergebnisse

Das erklärt:
- Warum es bei ~29 hängt (nicht bei einem bestimmten Mutanten — die Queue-Kapazität ist erschöpft)
- Warum die CPU-Last auf 5% fällt (alle Worker idle, warten auf die Queue)
- Warum es mit 1 Worker auch hängt (forced-fail-Phase nutzt die gleiche Queue-Infrastruktur)

---

## Betroffenes Modul

```
Datei: src/nextgen_cot_mcp_server/infrastructure/identifiers.py
Funktion: uuid7() — 1 Funktion, ~30 LOC
Mutanten: 42
Tests: 8 Unit-Tests + 3 Property-Tests (hypothesis) = 11 direkt, 912 total
```

### Source-Code

```python
def uuid7() -> UUID:
    global _last_timestamp_ms
    timestamp_ms = max(time.time_ns() // 1_000_000, _last_timestamp_ms + 1)
    _last_timestamp_ms = timestamp_ms
    random_bytes = secrets.token_bytes(10)
    uuid_bytes = (
        timestamp_ms.to_bytes(6, "big")
        + bytes([0x70 | (random_bytes[0] & 0x0F), random_bytes[1]])
        + bytes([0x80 | (random_bytes[2] & 0x3F)])
        + random_bytes[3:10]
    )
    return UUID(bytes=uuid_bytes)
```

### Relevante Tests

- `tests/unit/test_identifiers.py` — 8 Tests (version check, monotonicity, uniqueness, timestamp)
- `tests/property/test_uuid7_properties.py` — 3 hypothesis Tests (`max_examples=30, deadline=None`)
- `tests/conftest.py` — autouse Fixture das `_last_timestamp_ms` zwischen Tests zurücksetzt

### Relevante Konfiguration

```toml
# pyproject.toml
[tool.mutmut]
paths_to_mutate = ["src/nextgen_cot_mcp_server/"]
tests_dir = ["tests/"]
pytest_add_cli_args = ["-m", "not no_mutmut"]

[tool.pytest.ini_options]
testpaths = ["tests", "benchmarks"]
asyncio_mode = "auto"
```

---

## Vergleich mit funktionierendem Projekt

In einem anderen Python-Projekt (vergleichbares Setup: hatchling, src-Layout, uv, Python 3.14.3):
- 108 Mutanten, 1 Worker: **31 Sekunden**
- 108 Mutanten, 12 Worker: **7.5 Sekunden**
- Kein Hang, Ergebnis erscheint sofort

### Mögliche Unterschiede

| Faktor | Dieses Projekt | Funktionierendes Projekt |
|--------|---------------|-------------------------|
| Test-Anzahl | 915 | ~100-200 |
| hypothesis Tests | Ja (deadline=None) | Unklar |
| pytest-asyncio | Ja (asyncio_mode=auto) | Unklar |
| autouse Fixture (conftest.py) | Ja (global state reset) | Unklar |
| Integration Tests mit Real-DB | Ja (aiosqlite :memory:) | Unklar |
