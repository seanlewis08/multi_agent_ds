# LLM Adapter Checklist

**Plan file:** `project_planning/LLM_Adapter_Implementation_Plan.md`  
**Primary implementation file:** `src/multi_agent_ds/adapters/llm/openai.py`  
**Resume phrase:** `Pick back up where I left off`

## How To Resume

When returning to this work, use a prompt like:

```text
Use agent teams for this task. Pick back up where I left off in project_planning/LLM_Adapter_Checklist.md and continue from the next unchecked item. Update the checklist and progress log as you go.
```

The current agent should:

1. read this checklist
2. read `project_planning/LLM_Adapter_Implementation_Plan.md`
3. inspect the current state of `src/multi_agent_ds/adapters/llm/openai.py`
4. continue from the next unchecked task

## Current Status

- Overall status: `not started`
- Current checkpoint: `Step 1 - Constructor and config wiring`
- Human review completed through: `none`
- Testing completed through: `none`

## Checkpoint Checklist

### Step 1: Constructor and Config Wiring

- [ ] Implement `OpenAIAdapter.__init__(settings)`
- [ ] Load `.env`
- [ ] Read `model`, `temperature`, and `max_tokens` from `settings["llm"]["providers"]["openai"]`
- [ ] Read `OPENAI_API_KEY`
- [ ] Instantiate the OpenAI client
- [ ] Fail clearly if config or API key is missing

Human review checkpoint:

- [ ] Confirm the constructor is still thin and adapter-only
- [ ] Confirm no workflow, agent, or file I/O logic leaked into the adapter

Testing checkpoint:

- [ ] Import smoke test passes
- [ ] Constructor smoke test passes with real settings

### Step 2: Retry Helper

- [ ] Add one private retry helper
- [ ] Retry only `RateLimitError`
- [ ] Retry only `APIConnectionError`
- [ ] Use small exponential backoff
- [ ] Stop after a small fixed number of attempts

Human review checkpoint:

- [ ] Confirm retry logic is narrow and not framework-like
- [ ] Confirm no new dependency was added for retries

Testing checkpoint:

- [ ] Mocked retry-path test covers retry then success
- [ ] Mocked retry-path test covers retry exhaustion

### Step 3: Shared Chat Request Path

- [ ] Add one private request path around `chat.completions.create`
- [ ] Support `messages`
- [ ] Support optional `tools`
- [ ] Support optional `response_format`
- [ ] Reuse the retry helper

Human review checkpoint:

- [ ] Confirm there is only one SDK request path
- [ ] Confirm the adapter is not split between multiple OpenAI API surfaces

Testing checkpoint:

- [ ] Mocked request-path test verifies expected request arguments

### Step 4: `chat(...)`

- [ ] Implement `chat(messages, tools=None)`
- [ ] Extract assistant text content
- [ ] Extract tool calls when present
- [ ] Extract usage when present
- [ ] Return a compact normalized dict

Human review checkpoint:

- [ ] Confirm the return shape is small and stable
- [ ] Confirm raw SDK objects are not becoming the public contract

Testing checkpoint:

- [ ] `chat()` smoke test passes
- [ ] Tool-calling shape is covered by a focused test or fixture

### Step 5: `structured_output(...)`

- [ ] Implement `structured_output(messages, schema)`
- [ ] Use JSON schema response formatting
- [ ] Parse returned text with `json.loads`
- [ ] Return parsed output plus usage

Human review checkpoint:

- [ ] Confirm structured output reuses the same SDK request path
- [ ] Confirm no second provider/request stack was introduced

Testing checkpoint:

- [ ] Structured-output smoke test passes
- [ ] Invalid JSON or parse-failure behavior is covered

### Step 6: Optional Export Cleanup

- [ ] Decide whether `adapters/llm/__init__.py` should export `OpenAIAdapter`
- [ ] If updated, keep the export minimal

Human review checkpoint:

- [ ] Confirm there is no premature provider abstraction

Testing checkpoint:

- [ ] Import path test passes for the chosen export shape

### Step 7: Final Validation and Commit Readiness

- [ ] Run all focused adapter tests
- [ ] Re-check the final adapter against `Sean_Plan.md`
- [ ] Re-check the final adapter against architecture boundaries
- [ ] Summarize remaining limitations, if any
- [ ] Ask: `Should I commit and push these changes?`

Human review checkpoint:

- [ ] Confirm the completed unit is reviewable on its own
- [ ] Confirm no unrelated worktree changes are being bundled

Testing checkpoint:

- [ ] Final focused validation is complete and recorded below

## Progress Log

Use this section to keep resumable notes while implementing.

### Entry Template

```text
Date:
Checkpoint:
Status:
Files touched:
Validation run:
Notes:
Next item:
```

### Initial Entry

```text
Date: 2026-04-15
Checkpoint: Planning only
Status: Checklist and implementation plan created
Files touched:
- project_planning/LLM_Adapter_Implementation_Plan.md
- project_planning/LLM_Adapter_Checklist.md
Validation run:
- documentation-only; no tests run
Notes:
- The target implementation remains Sean Step 1 in Sean_Plan.md.
- The intended adapter is a thin OpenAI wrapper in src/multi_agent_ds/adapters/llm/openai.py.
- The plan is to use one SDK path: chat.completions.create.
Next item:
- Step 1 - Constructor and config wiring
```
