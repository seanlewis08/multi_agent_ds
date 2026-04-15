---
name: "Commit Rhythm"
description: Choose commit boundaries and split work into reviewable units. Use when deciding whether a task should produce one commit or several, especially across investigations, refactors, implementation slices, verification milestones, or mixed diffs.
---

# Commit Rhythm

Use this skill when a task should produce regular commits during implementation.

## Rules

- Split work into completed units, not arbitrary time intervals.
- Prefer one commit per coherent implementation slice.
- If a task naturally divides into investigation, implementation, and verification, commit only after implementation plus the relevant verification for that slice.
- If a unit turns out larger than expected, break it into smaller reviewable commits.
- If the entire task is one obvious small change, one commit is enough.

## Heuristics For A Commit Boundary

Commit when:

- a behavior change is complete
- a test or verification slice is complete
- a documentation slice that changes developer behavior is complete

Do not commit when:

- the code compiles only because of a temporary workaround
- you still expect to immediately rewrite the same change
- the diff mixes separate concerns that would be easier to review apart
