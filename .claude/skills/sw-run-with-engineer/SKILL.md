---
name: sw-run-with-engineer
description: Delegate implementation to a Sonnet 5 subagent acting as your engineer, then validate its work yourself. Use in the use-sw-development-workflow development loop, or whenever you (a stronger model, e.g. Opus or Fable) should direct and review rather than write the code.
argument-hint: "What should the engineer build?"
---

You are the tech lead. A subagent is your engineer. You do not write the implementation — you specify it, then verify it. In use-sw-development-workflow, for an API task you have already written the failing test and watched it fail (sw-test-driven-development); the engineer makes it pass. A UI task has no test for now: the engineer builds the behaviour and the UI's lint and build check it.

## 1. Specify

First gather just enough context yourself (read the key files, and the files that may be affected by the changes, locate the relevant code) to write precise instructions. Then write direct, unambiguous instructions for the engineer:

- Work on vertical features instead of layers
- Exact files/paths to change, and which to leave alone.
- The intended behaviour and any constraints (APIs and types to reuse).
- API task: the failing test, its path and name, the command that runs it, and the failing output you saw. The engineer makes it pass without editing it.
- UI task: the behaviour to build, and that it gets no tests. The UI's lint and build are its checks.
- The entries of the plan's Decisions section that touch the task.
- The conventions files the engineer must load: the rows of `.claude/conventions/README.md`, at the root of the repo that holds the code, whose paths or conditions match the change. Read them yourself as well. Do not learn conventions from the surrounding code. If the repo has no `.claude/conventions/`, name the CLAUDE.md sections that apply.
- Which commands prove the change: for API work the test command, then the project's format, lint and type-check commands; for UI work the lint and build commands (`next build` also type-checks). Find them in the repo's CLAUDE.md, then in the root files of the project that holds the code (`package.json` scripts, `pyproject.toml`, `Makefile`, pre-commit config).
- What to report back: files changed, commands run with their real output, questions it could not settle, and anything it could not do.

Give instructions, not options. If a design decision is open and the code, the plan or its Decisions answer it, decide it yourself. If none of them does, the decision is the developer's: ask before you delegate.

## 2. Delegate

Spawn the engineer with the Agent tool:

```
Agent({
  subagent_type: "general-purpose",
  model: "sonnet",
  run_in_background: false,
  description: "<3-5 word task>",
  prompt: "<your full instructions>"
})
```

The prompt always tells the engineer: "Use the Skill tool to load and follow sw-test-driven-development before implementing." For an API task it adds: "The failing test is already written: make it pass without editing it. If you believe the test is wrong, stop and say why." For a UI task it adds: "Write no tests: the UI has no test setup. Run the UI's lint and build and fix every failure." It always ends with: "When the instructions do not answer a question, do not guess: stop and report the question, the options you see and your recommendation. Never commit, stage or push. Never use SendMessage or ListAgents: a message you send goes out under my name."

Requirements: model `sonnet`, reasoning effort **medium** (state "Use medium reasoning effort." in the prompt), and `run_in_background: false` so you get the result before continuing. For independent parallel workstreams, spawn several engineers in one message; use `isolation: "worktree"` only if they would edit the same files.

Do not implement the task yourself while waiting. Continue an existing engineer with SendMessage rather than spawning a fresh one for follow-up work on the same task.

## 3. Validate

Never trust the engineer's report at face value. Independently verify:

- Read the actual diff / changed files — don't rely on the summary.
- API task: check that the failing test was not weakened: `git diff` on the test file shows no change you did not approve.
- Re-run the checks yourself, with the commands from step 1, and read the output: the test, the API suite and its checks for API work, lint and build for UI work. Never run a command the repo marks as unsafe.
- **Never relay a number from the report as your own finding.** Re-derive its counts, line numbers and inventories yourself before they reach the user. If the report contradicts a number you already stated, verify it now — deferring to a later reviewer is not validation. Give every count its unit ("9 call sites", not "9 sites"), because a count without its basis is unverified even when the arithmetic is right.
- Check the task was met in full: no silently skipped requirements, no scope creep, no stubbed or faked behaviour, no unrelated files touched.
- Check quality against the conventions files you named and the comments rule in sw-test-driven-development: no dead code, no swallowed errors.
- Answer each question in the report that the code, the plan or its Decisions answer, and send the answer to the same engineer with SendMessage. Every other question is the developer's: ask them with your recommendation and wait (use-sw-development-workflow's loop says how).

If something is wrong, send the engineer specific corrective instructions (via SendMessage) and validate again. Fix things yourself only when the remaining work is a trivial edit. When the engineer has failed the same correction twice, stop and ask the developer how to proceed, with your recommendation.

## 4. Report

In use-sw-development-workflow the ticked task in the plan is the report: skip this step until the workflow's summary. Otherwise tell the user what was built, what you verified and how (with real command output), and anything left undone. Faithfully report failures — never claim verification you did not perform.
