# Skill: Commit Confirmation

Use this skill at the end of any implementation task.

## Required Prompt

Before ending the turn, ask:

`Should I commit and push these changes?`

Do not assume consent from silence.

## If The User Says Yes

- inspect `git status`
- stage only the files for the completed unit of work
- create the commit with the detailed explanation format
- push the current branch
- report the commit subject and push result
- include a summary of each `git` command that was run, in order

## If The User Says No

- do not commit
- do not push
- summarize what is ready and what would be included in the next commit

## If The Worktree Is Mixed

- if unrelated local changes overlap with the same files, stop and ask before committing
- if unrelated changes are separable, leave them unstaged
