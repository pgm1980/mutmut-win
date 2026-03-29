# Implementation Plan Template

Use this structure for `docs/plans/YYYY-MM-DD-<feature-name>.md`.

---

```markdown
# [Feature Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** [One sentence — what does this build?]

**Architecture:** [2-3 sentences — key approach and design decisions]

**Tech Stack:** [Key technologies, libraries, frameworks]

---

### Task 1: [Component Name]

**Files:**
- Create: `exact/path/to/new-file.ext`
- Modify: `exact/path/to/existing.ext:line-range`
- Test: `tests/exact/path/to/test-file.ext`

**Step 1: Write the failing test**

[Complete test code — not pseudocode]

**Step 2: Run test to verify it fails**

Run: `[exact test command]`
Expected: FAIL with "[expected error message]"

**Step 3: Write minimal implementation**

[Complete implementation code]

**Step 4: Run test to verify it passes**

Run: `[exact test command]`
Expected: PASS

**Step 5: Commit**

```bash
git add [specific files]
git commit -m "[type]: [description]"
```

---

### Task 2: [Next Component]

[Same structure as Task 1]

---

### Task N: Final Integration

**Step 1: Run full test suite**

Run: `[project test command]`
Expected: All tests pass

**Step 2: Verify integration**

[Manual or automated integration check]

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete [feature name]"
```
```

## Key Rules

- **Exact file paths** — never "the config file", always `src/config/app.ts`
- **Complete code** — never "add validation", always the actual code
- **Exact commands** — never "run tests", always `npm test -- --grep "auth"`
- **Expected output** — always state what success/failure looks like
- **One action per step** — 2-5 minutes each
- **TDD always** — test before implementation, every task
