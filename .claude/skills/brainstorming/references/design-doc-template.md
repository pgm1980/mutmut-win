# Design Document Template

Use this structure for `docs/plans/YYYY-MM-DD-<topic>-design.md`.

---

```markdown
# [Feature Name] Design

**Date:** YYYY-MM-DD
**Status:** Draft | Approved | Superseded

## Problem

What problem does this solve? Why does it matter?

- Who is affected?
- What happens without this?
- What triggered this work?

## Goals

What does success look like?

1. [Primary goal — measurable if possible]
2. [Secondary goal]
3. [Non-goal — explicitly out of scope]

## Approach

### Architecture

How does this fit into the existing system?

- Components involved
- Data flow
- Key interfaces

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| [e.g., Storage] | [e.g., SQLite] | [e.g., No server needed, sufficient for scale] |

### Alternatives Considered

**Option A: [Name]**
- Pros: ...
- Cons: ...
- Why rejected: ...

**Option B: [Name] (Chosen)**
- Pros: ...
- Cons: ...
- Why chosen: ...

## Implementation Outline

High-level tasks (details go in the implementation plan):

1. [Component/task]
2. [Component/task]
3. [Component/task]

## Testing Strategy

- Unit tests: [what to test]
- Integration tests: [what to test]
- Manual verification: [key scenarios]

## Open Questions

- [ ] [Unresolved question]
- [ ] [Decision needed from user]
```
