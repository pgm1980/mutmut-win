---
name: pr-review
description: Use when reviewing a pull request or before creating one — orchestrates multiple specialized review agents for comments, tests, error handling, types, code quality, and simplification.
license: Apache-2.0
---

# Comprehensive PR Review

Run a comprehensive pull request review using multiple specialized agents, each focusing on a different aspect of code quality.

## Review Workflow

### 1. Determine Review Scope

- Check git status and `git diff --name-only` to identify changed files
- Check if PR already exists: `gh pr view`
- Determine which review aspects to run (default: all applicable)

### 2. Available Review Aspects

| Aspect | Agent Prompt | Focus |
|--------|-------------|-------|
| **comments** | [comment-analyzer-prompt.md](references/comment-analyzer-prompt.md) | Comment accuracy and maintainability |
| **tests** | [pr-test-analyzer-prompt.md](references/pr-test-analyzer-prompt.md) | Test coverage quality and completeness |
| **errors** | [silent-failure-hunter-prompt.md](references/silent-failure-hunter-prompt.md) | Silent failures and error handling |
| **types** | [type-design-analyzer-prompt.md](references/type-design-analyzer-prompt.md) | Type design and invariants |
| **code** | [code-reviewer-prompt.md](references/code-reviewer-prompt.md) | Project guidelines and bug detection |
| **simplify** | [code-simplifier-prompt.md](references/code-simplifier-prompt.md) | Code clarity and maintainability |

### 3. Determine Applicable Reviews

Based on changes:
- **Always applicable**: code-reviewer (general quality)
- **If test files changed**: pr-test-analyzer
- **If comments/docs added**: comment-analyzer
- **If error handling changed**: silent-failure-hunter
- **If types added/modified**: type-design-analyzer
- **After passing review**: code-simplifier (polish and refine)

### 4. Launch Review Agents

For each applicable review aspect:
1. Read the corresponding prompt file from `references/`
2. Dispatch via the Agent tool with `subagent_type: general-purpose`, providing the prompt content plus the specific review context (changed files, PR description, etc.)

**Sequential approach** (default — easier to understand and act on):
- Each report is complete before next
- Good for interactive review

**Parallel approach** (when user requests speed):
- Launch all agents simultaneously via multiple Agent tool calls
- Faster for comprehensive review

### 5. Aggregate Results

After agents complete, summarize:

```markdown
# PR Review Summary

## Critical Issues (X found)
- [agent-name]: Issue description [file:line]

## Important Issues (X found)
- [agent-name]: Issue description [file:line]

## Suggestions (X found)
- [agent-name]: Suggestion [file:line]

## Strengths
- What's well-done in this PR

## Recommended Action
1. Fix critical issues first
2. Address important issues
3. Consider suggestions
4. Re-run review after fixes
```

## Tips

- **Run early**: Before creating PR, not after
- **Focus on changes**: Agents analyze git diff by default
- **Address critical first**: Fix high-priority issues before lower priority
- **Re-run after fixes**: Verify issues are resolved
- **Use specific reviews**: Target specific aspects when you know the concern

## Workflow Integration

**Before committing:**
1. Write code
2. Run code and errors reviews
3. Fix any critical issues
4. Commit

**Before creating PR:**
1. Stage all changes
2. Run all applicable reviews
3. Address all critical and important issues
4. Run specific reviews again to verify
5. Create PR

**After PR feedback:**
1. Make requested changes
2. Run targeted reviews based on feedback
3. Verify issues are resolved
4. Push updates
