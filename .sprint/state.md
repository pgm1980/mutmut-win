---
current_sprint: "8"
sprint_goal: "File Setup Pipeline (copy_src, write_mutants, setup_paths)"
branch: "feature/24-file-setup-pipeline"
started_at: "2026-03-30"
housekeeping_done: false
memory_updated: false
github_issues_closed: false
sprint_backlog_written: false
semgrep_passed: false
tests_passed: false
documentation_updated: false
---

# Sprint State

## Current Focus
- Sprint 8: File Setup Pipeline — the critical missing piece that enables end-to-end mutation testing

## Sprint Plan (v0.2.0)

### Sprint 8: File Setup Pipeline (Tier 1 Critical)
- [ ] `file_setup.py`: walk_source_files, copy_src_dir, setup_source_paths, write_all_mutants_to_file
- [ ] Orchestrator integration: use file_setup in _generate_mutants
- Issues: #24, #25, #26, #27, #28

### Sprint 9: Test Mapping + Stats (Tier 2 High)
- [ ] `test_mapping.py`: mangled_name_from_mutant_name, tests_for_mutant_names
- [ ] `stats.py`: load_stats, save_stats, collect_or_load_stats
- [ ] Type-checker filter wiring in orchestrator
- Issues: #29, #30, #31, #32, #33

### Sprint 10: CLI show/apply + E2E Validation (Tier 3)
- [ ] `mutant_diff.py`: find_mutant, get_diff_for_mutant, apply_mutant
- [ ] Live progress display
- [ ] End-to-end validation: full pipeline on reference projects
- Issues: #34, #35, #36, #37, #38
