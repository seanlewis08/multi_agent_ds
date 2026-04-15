# Skill: Commit Explanations

Use this skill whenever writing a commit message body.

## Required Content

Every commit body should explain:

- what changed in concrete terms
- why this unit exists
- how the change fits the repository architecture or plan
- what was verified
- what remains uncertain, if anything

## Standard

- Be specific about files, behavior, or interfaces.
- Prefer explanation over changelog repetition.
- Mention validation explicitly, even if the answer is "not run".
- Keep the body detailed enough for future review without becoming a dump of every edit.

## Avoid

- vague subjects like `updates` or `fix stuff`
- bodies that only restate the subject
- claiming validation that was not run
- bundling multiple unrelated rationales into one explanation
