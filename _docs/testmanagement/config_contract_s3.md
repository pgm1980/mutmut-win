# GAP-1: Konfigurationsvertrag nach S3-038

Diese Korrektur präzisiert die GAP-1-Zuordnung im eingefrorenen
`HANDOVER-EXTERNAL-REVIEW-v3.1.0.md:81`. Der historische Bericht und seine
Receipts bleiben unverändert. Maßgeblich ist die finale Karte S3-038
(Quellclaims L1-F11/G-14, Register R-0314/R-0336): eine Dokumentabweichung,
kein zusätzlicher bewiesener Produktfehler.

| Eingabe | Produktverhalten | Orakel |
|---|---|---|
| Unbekannter Schlüssel in `[tool.mutmut]` | Warnung auf stderr, Schlüssel ignoriert; bei ähnlicher Schreibweise mit Vorschlag | Warnung nennt den Schlüssel; CLI-Lauf darf bei ansonsten gültiger Konfiguration erfolgreich sein |
| Unbekannte lokale Option in `setup.cfg` `[mutmut]` | Warnung auf stderr, Option ignoriert | Warnung nennt die ignorierte Option |
| Ungültiger Wert einer bekannten Option | `InvalidConfigValueError`, CLI-Exit 2 vor Staging | Diagnose und fehlendes `mutants/` |
| Gültige bekannte Optionen | Validierte Konfiguration, keine Warnung über unbekannte Schlüssel | Gesunde Kontrolle und tatsächlicher erfolgreicher Lauf |

`load_config` und `_load_setup_cfg` unterscheiden Warnungen von der gemeinsamen
Wertprüfung `_validate_config_mapping`. „Config fail-closed“ gilt daher nicht
pauschal für unbekannte Schlüssel. Pydantics Ignorieren unbekannter Felder
bedeutet nicht, dass der Loader sie stillschweigend annimmt.

Der echte CLI-Fall in `tests/e2e/test_config_fail_closed_e2e.py` prüft nun
ausdrücklich die Warnung auf stderr und führt die Kampagne mit sowie ohne
unbekannten Schlüssel aus. Er ersetzt keinen vollständigen Vertragstest aller
Konfigurationsfelder. Der vorhandene Unit-Backstop
`TestConfigTypoWarning.test_unknown_key_warns_with_a_suggestion` prüft zusätzlich
die Tippfehlerkorrektur. Entfernen nur der TOML-Warnausgabe muss beide
Warnorakel rot machen; ein erfolgreicher Kampagnenlauf allein belegt keine
Warnung. Der gesunde Gegenarm prüft den stderr-Kanal ebenfalls.

Historische GAP-1-Fallzahlen und frühere rote Receipts sind keine aktuelle
Abnahme. Frische Source-/Test-/Lock-gebundene Rot-, Grün- und Sabotagebelege
stehen im S3-Sanierungsledger. Integrierte Finalgates und Mutationsevidenz
werden dort getrennt von diesen gezielten Konfigurationsprüfungen geführt.
