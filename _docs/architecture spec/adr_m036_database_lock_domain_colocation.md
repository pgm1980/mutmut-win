# ADR: M-036 — Colocation der Datenbank-Lockdomäne im kanonischen DB-Elternverzeichnis

**Status:** Accepted (P-08/AP-22, 2026-10-01)
**Entscheidung:** P-08 M-036 = **A** (`P08_ENTSCHEIDUNGEN_R2_ASTRA.md`); Varianten B (Known-Folder/LocalAppData) und C (ProgramData/Kernel-Mutexe) per Entscheidung zurückgestellt.
**Basis:** `b190307` auf `fix/r2-followup-astra`; Repro `glm-followup/p08-036-repro.md`.

## Kontext

`_database_lock_root()` verankerte beide DB-Lockschlüssel (0-path, 1-file) unter
`tempfile.gettempdir()`. `gettempdir()` folgt `tempfile.tempdir` bzw. TMP/TEMP/TMP
der Prozessumgebung: Zwei Prozesse mit divergierenden effektiven TEMP-Wurzeln —
erreichbar über den öffentlichen Konstruktorparameter
`MutationOrchestrator(db_path=...)` — leiten zwei verschiedene Lock-Wurzeln ab
und erwerben beide den als exklusiv dokumentierten Datenbank-Lock für dieselbe
absolute DB-Datei (Repro: `second_acquire_succeeded: true`,
`same_lock_domain: false`). Folge war u. a. `_recover_abandoned_run` ohne
Eigner-/Lebendigkeitsprüfung auf die `running`-Zeile des noch lebenden anderen
Laufs. Der Docstring-Anspruch „process-independent" galt nur innerhalb einer
TEMP-Domäne.

Nur die Colocation-Variante beseitigt die Domänenspaltung ohne eine zweite
benutzer- oder maschinenweite Ablage: Eine Known-Folder-Wurzel (B) heilt nur
divergierende TEMP-Werte desselben Benutzers; ProgramData (C) brächte
Standard-ACLs, die fremden Benutzern nur Lesen auf fremd angelegten
Guard-Dateien erlauben (Squatting/DoS, explizite ACL-Verwaltung nötig);
benannte Kernel-Mutexe verlieren Owner-Diagnostik und Stale-Takeover.

## Entscheidung

1. **Kanonische Identität:** Beide DB-Lockschlüssel liegen im **kanonischen
   physischen Elternverzeichnis** der Datenbank
   (`.mutmut-win-db-0-path-<digest>.run.lock`,
   `.mutmut-win-db-1-file-<digest>.run.lock`). `_database_lock_root`,
   `_DATABASE_LOCK_DIRNAME` und der `tempfile`-Import entfallen. Es gibt
   **keinen Fallback** auf eine Temp-Wurzel: Wer die Datenbank nicht benennen
   kann, kann sie auch nicht sperren; wer das DB-Verzeichnis nicht öffnen
   darf, scheitert beim Lock-Erwerb (früher und mit klarerer Diagnose als
   vorher bei SQLite).
2. **Symlink-/Reparse-Prüfung vor Wegnormalisierung:** Jede existierende
   Komponente des *lexikalischen* DB-Elternpfads wird mit `lstat` geprüft,
   **bevor** `resolve(strict=True)` sie verfolgen könnte; ein Redirect
   (Symlink/Junction/Reparse) oder Nicht-Verzeichnis ist `RunLockError`. Eine
   Prüfung des bereits aufgelösten Pfads wäre wirkungslos, weil `resolve`
   dem Redirect bereits gefolgt wäre — deshalb die lexikalische Prüfung
   (Parität zu `db.validate_cache_path`, das an jedem Produktpfad vor der
   Lockableitung läuft und die Kette ebenfalls prüft).
3. **Beobachtbare DB-Identität:** Der 1-file-Schlüssel wird aus `lstat`
   (dev, inode) der existierenden DB gebildet. Existiert die Datei nicht,
   gibt es nur den 0-path-Schlüssel (Serialisierung der Ersteller vor der
   Existenz); nach `create_db` ergänzt `refresh_identity` den
   Identitätsschlüssel. Hardlink-DBs (`st_nlink != 1`) und Link-/Reparse-DBs
   werden **fail-closed als `RunLockCorruptError`** abgewiesen: Ein
   colokalisierter Schlüssel kann Aliasse in fremden Verzeichnissen nicht
   zur Konvergenz bringen — bewusste Vertragsänderung gegenüber der
   früheren Identitätskonvergenz.
4. **Nicht beobachtbare Linkzahl ist kein Beweis für eine sichere
   Einzeldatei:** `st_nlink == 0` (CPython-lstat-Fallback für ein nicht
   öffnenbares Regular File, vgl. M-095) bzw. die degenerierte Identität
   (0, 0) wird niemals als Identitätsschlüssel gehasht, sondern mit einer
   `RunLockCorruptError`-Meldung abgewiesen, die **nicht** „hardlink"
   behauptet (abgewiesen wurde eine unbeobachtbare Metadaten-Lesbarkeit,
   kein beobachteter Mehrfacheintrag).
5. **Lock-/Guard-Lebensdauer:** Guard-Dateien sind absichtlich persistent
   (stabiles Lock-Inode, `WorkspaceRunLock`-Protokoll unverändert); Owner-
   Records werden atomar publiziert und bei sauberer Freigabe entfernt.
   Colokalisiert sammeln sich `1-file-<digest>`-Guards bei API-Nutzern, die
   die DB wiederholt löschen/neu anlegen (neue Inode ⇒ neuer Digest), im
   DB-Verzeichnis statt unter `%TEMP%`. Bei der Default-DB räumt
   `run --force` das Verzeichnis mit auf. `run --force` entfernt `mutants/`
   und `.mutmut-cache/` weiterhin unter dem Workspace-Lock und **vor** dem
   DB-Lock (rmtree-Reihenfolge unverändert): Ein paralleler Leser mit
   gehaltenem DB-Lock im `.mutmut-cache/` lässt rmtree teilweise scheitern
   und läuft in den bestehenden fail-closed-Pfad „Could not fully remove
   … (files in use?)" — kein neues Verhalten, nur ein neuer Auslöser.
6. **Staging/Basis-Evidenz:** Alle Lock-/Guard-Pfade sind exakte Excludes in
   `_basis_excluded_paths` (Orchestrator): Guard-Bytes stehen unter
   OS-Byte-Range-Lock (zweites Handle desselben Prozesses liest sie nicht),
   Owner-Records ändern sich zwischen Beobachtungen (Basisdrift). Der
   0-path-Schlüssel ist deterministisch; der 1-file-Schlüssel wird je
   Aufruf neu berechnet (nach `create_db` existiert er). Die
   Namenswahl `.mutmut-win-db-*` trifft zwar die bestehenden
   Root-Filter (`file_setup._skip_automatic_root_file`,
   `stats._skip_context_file`), das ist aber **kein Ersatz** für die
   Excludes: Der Kontext-Filter greift nur im Projekt-Root, eine Custom-DB
   liegt aber typischerweise in einem gegangenen Unterverzeichnis.
   Kann die Lockdomäne nicht abgeleitet werden (Hardlink-DB, Redirect),
   degradieren die Excludes auf DB + Sidecars; die autoritative Abweisung
   erfolgt weiter über `validate_cache_path`/`DatabaseRunLocks`.
7. **ACL-Annahmen:** Es gibt keine neuen Annahmen über fremd verwaltete
   Verzeichnisse. Die Lockdomäne erbt exakt die ACLs des DB-Elternverzeichnisses:
   Wer die Datenbank anlegen/öffnen darf, darf dort auch die Lock-/Guard-Dateien
   anlegen und sperren; wer nicht, scheitert fail-closed. Keine
   ProgramData-Standard-ACLs, kein Squatting-Risiko in einem gemeinsamen
   Systemverzeichnis.
8. **Schichtung:** `run_lock` (Band 4) importiert weiterhin kein `db` (Band 3).
   Das validierte Anlegen des Elterndienstes ist als `db.ensure_cache_parent`
   extrahiert; der Orchestrator ruft es vor `DatabaseRunLocks` auf (frischer
   Workspace ohne `.mutmut-cache/`).

## Bewusste Vertragsänderungen

- `test_database_lock_domains_cover_canonical_path_and_hardlink_identity`,
  `test_absolute_database_uses_same_lock_domain_from_different_workspaces`,
  `test_database_lock_rejects_hardlink_alias_while_original_is_held` und
  `test_live_database_holder_excludes_hardlink_alias_across_processes`
  (Integration) sind als M-036-Vertragsänderung ersetzt: Hardlink-DBs werden
  abgewiesen statt konvergiert; die Temp-Unabhängigkeit ist neuer Test.
- `WorkspaceRunLock`-Protokoll, `run_lock_path_for_db` (cwd-gebundener
  Workspace-Lock), M-093 (ExitStack-Freigabe) und M-095 (Null-Link in db.py)
  bleiben unverändert grün.

## Offene Folgepunkte (cli-Seite, separater Merging-Agent)

- `cli._basis_excluded_paths` (apply/export) benötigt dieselben
  Lock-/Guard-Excludes.
- `cli.apply`/`cli.export_cicd_stats_cmd` ohne vorhandenes `.mutmut-cache/`:
  explizit festgelegtes Verhalten (bestehende Nutzer-Meldung vor dem DB-Lock
  vs. bewusstes `ensure_cache_parent` auch in Lesebefehlen) — nicht still auf
  `RunLockError` umstellen.
