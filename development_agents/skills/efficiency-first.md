# Skill: Efficiency First

Use this skill whenever you are about to add or rewrite code.

## Default Heuristics

- Choose the smallest change that solves the problem cleanly.
- Reuse existing functions, registries, and config before adding new helpers.
- Prefer pandas, NumPy, sklearn, and SQL-native operations over Python loops.
- Avoid repeated dataframe scans, repeated conversions, and avoidable copies.
- Avoid adding abstraction layers unless they remove real duplication or complexity.
- Avoid new dependencies unless the current stack cannot solve the problem reasonably.

## Blocking Checks

Stop and simplify if the change would:

- add a helper that only wraps one call site without reducing complexity
- create a parallel code path instead of extending the existing one
- perform row-wise dataframe work where vectorized logic is available
- hardcode values already present in settings or registries
- add a dependency for convenience rather than necessity

## Output Standard

The final implementation should feel like the obvious next step in the current architecture, not a sidecar subsystem.
