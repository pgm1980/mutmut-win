# TDD Cheat Sheet

Quick reference for the Red-Green-Refactor cycle.

## The Cycle

```
RED    → Write ONE failing test (one behavior, clear name, real code)
       → Run it → Confirm it FAILS for the expected reason
GREEN  → Write MINIMAL code to pass
       → Run it → Confirm ALL tests pass
REFACTOR → Clean up (names, duplication, helpers)
       → Run it → Confirm ALL tests still pass
REPEAT → Next behavior → next failing test
```

## Decision Guide

| Situation | Action |
|-----------|--------|
| New feature | RED: Write test for first behavior |
| Bug report | RED: Write test reproducing the bug |
| Refactoring | Ensure tests exist first, then refactor under green |
| Test passes immediately | Wrong test — fix it or delete it |
| Test errors (not fails) | Fix the error, re-run until it fails correctly |
| Code written before test | Delete code, start with RED |
| Test too hard to write | Design is too complex — simplify the interface |
| Must mock everything | Code too coupled — use dependency injection |
| "Just this once" | No. Delete code. Start over. |

## Bug Fix Pattern

```
1. RED:    Write test that reproduces the bug
2. VERIFY: Run → test FAILS (proves bug exists)
3. GREEN:  Fix the bug (minimal change)
4. VERIFY: Run → test PASSES (proves fix works)
5. VERIFY: Run → revert fix → test FAILS again (proves test catches the bug)
6. RESTORE fix, run full suite
```

## Test Quality Checklist

- [ ] One behavior per test
- [ ] Name describes the behavior, not the implementation
- [ ] Uses real code (mocks only when unavoidable)
- [ ] Watched it fail before writing production code
- [ ] Failed for the expected reason (not typo/error)
- [ ] Minimal production code to pass

## Red Flags

Any of these → stop and restart with TDD:
- "Should pass now" (run it)
- "I'll test after" (test first)
- "Too simple to test" (30 seconds to write)
- "Keep as reference" (delete means delete)
- Test passes on first run (wrong test)
