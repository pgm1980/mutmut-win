# Agent Prompt Template

Use this structure when dispatching focused subagents for parallel work.

## Template

```markdown
## Scope
[One specific problem domain — test file, subsystem, or bug]

## Context
[Error messages, test names, relevant file paths — everything the agent needs to understand the problem without asking questions]

## Goal
[Clear, measurable objective: "Make these 3 tests pass" or "Fix the race condition in X"]

## Constraints
- Do NOT modify files outside [scope]
- Do NOT refactor unrelated code
- Do NOT increase timeouts as a fix — find root cause
- [Any other boundaries]

## Expected Output
Return a summary containing:
1. **Root cause** — what was actually broken
2. **Changes made** — files and lines modified
3. **Verification** — test results after fix
```

## Fill-in Example

```markdown
## Scope
Fix the 3 failing tests in src/agents/agent-tool-abort.test.ts

## Context
Failing tests:
1. "should abort tool with partial output capture" - expects 'interrupted at' in message
2. "should handle mixed completed and aborted tools" - fast tool aborted instead of completed
3. "should properly track pendingToolCount" - expects 3 results but gets 0

Error output:
  FAIL  src/agents/agent-tool-abort.test.ts
  ● should abort tool with partial output capture
    expect(received).toContain(expected)
    Expected: "interrupted at"
    Received: ""

## Goal
All 3 tests in agent-tool-abort.test.ts pass

## Constraints
- Do NOT modify other test files
- Do NOT just increase timeouts — find the real timing issue
- Production code changes OK if the bug is there

## Expected Output
1. Root cause of each failure
2. Files and lines changed
3. Full test output showing all 3 pass
```

## Key Principles

- **Self-contained:** Agent should not need to ask questions
- **Focused:** One problem domain per agent
- **Measurable:** Clear pass/fail criteria
- **Bounded:** Explicit constraints prevent scope creep
