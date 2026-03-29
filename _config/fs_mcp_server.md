# FS MCP Server — Tool-Nutzungsrichtlinie

Vollstaendige Richtlinie fuer den Einsatz des FS MCP Servers in Softwareentwicklungsprojekten.
Referenziert aus der CLAUDE.md als oberste Direktive.

---

## Architektur

Der FS MCP Server exponiert **2 MCP Tools**:

| Tool | Zweck |
|------|-------|
| `service_catalog` | Tool-Discovery: Kategorien, Parameter-Schemas, EBNF-Grammatik, Use Cases |
| `execute_workflow` | Tool-Ausfuehrung: Einzeloperationen, Pipelines, Templates, Use Cases |

Dahinter stehen **138 Atomic Tools** in **25 Kategorien**, aufrufbar via `execute_workflow`.

**EBNF-Grammatik abrufbar via:** `service_catalog(detail: 'schema')`
**Alle Tools mit Parametern via:** `service_catalog(detail: 'full')`
**Use Cases via:** `service_catalog(detail: 'use-cases')`

---

## Tier 1: FS MCP ERSETZT Bash (VERBOTEN fuer Filesystem-Ops)

Bash darf **NICHT** fuer Filesystem-Operationen verwendet werden. Stattdessen MUSS der FS MCP Server genutzt werden.

| Bash (VERBOTEN) | FS MCP Ersatz | Vorteil |
|-----------------|---------------|---------|
| `cat` | `read_file` | Offset/Length, Encoding-Erkennung |
| `head -n N` | `head_file` | Effizient fuer grosse Dateien |
| `tail -n N` | `tail_file` | Effizient fuer Log-Dateien |
| `echo > file` / `cat <<EOF` | `write_file`, `safe_write` | Auto-Versioning, Crash-Safe |
| `cp`, `cp -r` | `copy_file`, `verified_copy`, `filtered_copy` | Hash-Verifikation, Pattern-Filter |
| `mv` | `move_file` | Audit-Trail |
| `rm`, `rm -rf` | `delete_file`, `secure_delete`, `batch_delete` | Sichere Loeschung, Batch-Modus |
| `mkdir -p` | `create_directory` | Audit-Trail |
| `find` | `search_files`, `find_by_date`, `find_by_size_range`, `find_recent`, `find_empty_dirs` | Datum, Groesse, Fuzzy |
| `grep`, `rg` (in Dateien) | `search_code`, `regex_extract` | Kontext-Zeilen, spezialisierte Extraktion |
| `diff` | `compare_files`, `word_diff`, `three_way_merge` | Word-Level, 3-Wege-Merge |
| `sha256sum`, `md5sum` | `get_hash`, `verify_hash`, `generate_checksum_file` | 5 Algorithmen, Manifest-Erzeugung |
| `tar`, `zip`, `7z` | `compress`, `extract` | 5 Formate, Zip-Slip-Schutz |
| `wc -l` | `count_lines_in_dir`, `text_statistics` | Woerter, Saetze, Durchschnitte |
| `sort` | `sort_lines` | In-Place, numerisch |
| `uniq` | `unique_lines` | Duplikat-Zaehlung |
| `sed` | `search_replace`, `delete_lines`, `insert_lines` | DryRun, Backreferences, Zeilenbereich |
| `tree` | `get_directory_tree` | Tiefenlimit, Filter |
| `du` | `storage_analysis` | Breakdown nach Extension/Groesse/Alter |
| `stat`, `file` | `get_file_info`, `analyze_content` | Encoding, BOM, Language, MIME |
| `base64` | `base64_encode`, `base64_decode` | Datei-zu-Datei |
| `ls` | `list_directory` | Pagination, Sortierung, Glob-Filter |

**Bash bleibt ERLAUBT fuer:**
- `git` (Versionskontrolle)
- `dotnet` (Build, Test, Run, Publish)
- `npm`, `cargo`, `python`, `pip` (Paketmanagement, Build)
- `docker` (Container-Management)
- `semgrep` (Security-Scanning)
- `dotnet stryker` (Mutation Testing)
- Andere Build/Test/Deploy-Befehle die KEINE Filesystem-Operationen sind

---

## Tier 2: FS MCP BEVORZUGT vor Built-In Tools

In folgenden Situationen MUSS der FS MCP Server statt der Claude Code Built-In Tools verwendet werden:

| Situation | Built-In (NICHT nutzen) | FS MCP (NUTZEN) |
|-----------|------------------------|-----------------|
| Multi-File Lesen | `Read` auf jede Datei einzeln | `read_multiple_files` (parallel) |
| Grosse Dateien (>1 MB) | `Read` (laedt alles in Kontext) | `head_file`, `tail_file`, `read_file` mit offset/length |
| Komplexe Dateisuche | `Glob` mit einfachem Pattern | `find_by_date`, `find_by_size_range`, `fuzzy_find`, `find_with_regex_name` |
| Multi-File Inhaltssuche | `Grep` ueber ganzes Projekt | `search_code` mit Kontext-Zeilen |
| Batch-Edits (>3 Dateien) | `Edit` auf jede Datei einzeln | Pipeline mit mehreren `edit_block`/`search_replace` Steps |
| Produktionsdateien schreiben | `Write` (kein Versioning) | `write_file` oder `safe_write` (Auto-Versioning, Crash-Safe) |
| Dateivergleich | Bash `diff` | `compare_files`, `word_diff` |
| Verzeichnisvergleich | Bash `diff -r` | `compare_directories` |
| Datei-Hashing | Bash `sha256sum` | `get_hash` (5 Algorithmen) |
| Encoding-Erkennung | Bash `file` | `analyze_content` (Encoding, BOM, Language, LOC) |

---

## Tier 3: Built-In Tools BLEIBEN (Workflow-Integration)

Diese Claude Code Built-In Tools DUERFEN weiterhin verwendet werden, weil sie in den Claude Code UI-Workflow integriert sind:

| Built-In | Wann erlaubt | Begruendung |
|----------|-------------|-------------|
| **Read** | Einzeldatei schnell lesen (<1 MB) | Zeigt Zeilennummern, integriert in Kontext-Fenster |
| **Edit** | Einzeldatei-Edit mit visuellem Diff | Claude Code UI zeigt Diff zur Genehmigung |
| **Glob** | Einfache `*.cs` / `**/*.json` Patterns | Schneller, kein Overhead |
| **Grep** | Schneller Check in 1-2 bekannten Dateien | Direkte Ergebnisse ohne Workflow-Overhead |

**WICHTIG:** Sobald eine Operation ueber das "schnelle Einzeldatei-Szenario" hinausgeht, MUSS der FS MCP Server verwendet werden.

---

## Tier 4: FS MCP EINZIGARTIG (kein Built-In Aequivalent)

Diese Faehigkeiten existieren NUR im FS MCP Server und MUESSEN aktiv genutzt werden:

| Faehigkeit | Tools | Wann nutzen |
|-----------|-------|-------------|
| **Multi-Step Pipelines** | `execute_workflow` mit `steps[]` | Wenn 2+ Operationen logisch zusammengehoeren |
| **Auto-Versioning** | Transparent auf allen Writes | Immer aktiv (Konfiguration) |
| **Auto-Audit** | Transparent auf allen Operationen | Immer aktiv (Konfiguration) |
| **File Tagging** | `tag_file`, `get_tags`, `search_by_tags` | Dateien kategorisieren, Status tracken |
| **Snapshots** | `create_snapshot`, `compare_snapshots` | Vor/Nach Aenderungen vergleichen |
| **Template Learning** | `saveAsTemplate` in Pipelines | Wiederkehrende Workflows speichern |
| **Use Cases** | `execute_workflow` mit `useCase` | Vordefinierte Workflows (40 verfuegbar) |
| **Structured Data** | INI, ENV, CSV, JSON flatten/unflatten | Konfigurationsdateien lesen/schreiben |
| **Security Scanning** | `sensitive_scan` | Vor Commits: API-Keys, Passwoerter pruefen |
| **Encoding-Management** | `batch_detect_encoding`, `analyze_content` | Encoding-Probleme erkennen und beheben |
| **Code Metrics** | `project_overview`, `text_statistics` | Projekt-Ueberblick, Datei-Statistiken |
| **Archive-Management** | 5 Formate, `list_archive`, `extract_single` | Deployment-Pakete, Backups |
| **Datei-Integritaet** | `generate_checksum_file`, `verify_hash` | Build-Artefakte verifizieren |
| **Duplikat-Erkennung** | `find_similar_files` | Speicherplatz optimieren, Redundanz finden |
| **Verzeichnis-Intelligenz** | `storage_analysis`, `find_empty_dirs`, `flatten_directory` | Projekt-Hygiene |

---

## Pipeline-Beispiele fuer Entwicklungs-Workflows

### Beispiel 1: Sichere Dateibearbeitung mit Snapshot

```json
{
  "steps": [
    {"id": "snap", "tool": "create_snapshot", "params": {"path": "$input.dir"}},
    {"id": "edit", "tool": "search_replace", "params": {"path": "$input.file", "pattern": "$input.old", "replacement": "$input.new"}},
    {"id": "verify", "tool": "compare_files", "params": {"pathA": "$input.file", "pathB": "$input.file"}}
  ]
}
```

### Beispiel 2: Projekt-Analyse

```json
{
  "steps": [
    {"id": "overview", "tool": "project_overview", "params": {"path": "$input.root"}},
    {"id": "size", "tool": "storage_analysis", "params": {"path": "$input.root"}},
    {"id": "scan", "tool": "sensitive_scan", "params": {"path": "$input.root"}},
    {"id": "dupes", "tool": "find_similar_files", "params": {"path": "$input.root"}}
  ]
}
```

### Beispiel 3: Pre-Commit Check

```json
{
  "steps": [
    {"id": "scan", "tool": "sensitive_scan", "params": {"path": "$input.root"}},
    {"id": "encoding", "tool": "batch_detect_encoding", "params": {"path": "$input.root"}},
    {"id": "empty", "tool": "find_empty_dirs", "params": {"path": "$input.root"}}
  ]
}
```

---

## Entscheidungsbaum

```
Ist es eine Filesystem-Operation?
  |
  +-- Nein (git, dotnet, npm, docker) --> Bash verwenden
  |
  +-- Ja
       |
       +-- Einzeldatei, schnell, <1 MB?
       |    |
       |    +-- Lesen --> Read (Built-In)
       |    +-- Editieren mit Diff --> Edit (Built-In)
       |    +-- Dateiname suchen (einfach) --> Glob (Built-In)
       |    +-- Inhalt suchen (1-2 Dateien) --> Grep (Built-In)
       |
       +-- Alles andere --> FS MCP Server (PFLICHT)
            |
            +-- Multi-File? --> Pipeline mit execute_workflow
            +-- Grosse Datei? --> head_file, tail_file, offset/length
            +-- Komplexe Suche? --> find_by_date, fuzzy_find, etc.
            +-- Batch-Operation? --> Pipeline oder Batch-Tools
            +-- Analyse/Metrics? --> project_overview, storage_analysis
            +-- Sicherheit? --> sensitive_scan, secure_delete
            +-- Strukturierte Daten? --> read_ini, write_env, csv_filter
            +-- Archiv? --> compress, extract, list_archive
```
