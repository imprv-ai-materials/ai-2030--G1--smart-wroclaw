---
name: sw-code-review
description: Use after the development loop of use-sw-development-workflow, or when the developer asks for a review of the changes on this branch. Dispatches a separate reviewer agent, revalidates its Blocker and High findings against the code, presents them with a recommended fix, and asks the developer to fix them now or save them as review remarks.
---

# Code Review

A separate agent reviews the changes in a fresh context. You check its serious findings against the code, present
the confirmed ones with a recommended fix, and the developer decides what happens to them.

**Core principle:** the reviewer finds, you verify, the developer decides. A finding nobody verified never reaches
the developer as a Blocker or High.

Read-only: nothing in this skill edits code or tests. The only file it changes is the plan.

## 1. Gather inputs

- **The plan** and its `Base:` commit. For a review outside use-sw-development-workflow, Base is the merge-base with
  the branch this one was cut from. Ask the developer when you are not sure which branch that is. Never assume
  `main`.
- **The review package.** Run from the repo root:

  ```bash
  BASE=<the plan's Base>
  PKG=$(mktemp -t sw-review-XXXXXX.md)
  { git log --oneline $BASE..HEAD; git status --short; git diff --stat $BASE; git diff -U10 $BASE;
    git ls-files --others --exclude-standard | while read -r f; do echo "=== new file: $f"; cat "$f"; done; } > "$PKG"
  ```

  `git diff $BASE` compares Base with the working tree, so it covers the developer's commits since Base and the
  uncommitted changes. New files are not in it until they are tracked, so the last line adds them.

## 2. Dispatch the reviewer

Read [reviewer-prompt.md](reviewer-prompt.md), fill its placeholders and spawn the reviewer:

```
Agent({
  subagent_type: "general-purpose",
  model: "opus",
  run_in_background: false,
  description: "Review branch changes",
  prompt: "<reviewer-prompt.md with the placeholders filled>"
})
```

- Name the most capable available model explicitly. An omitted model inherits the session's.
- Hand it the package and the plan, never your session's history. Its fresh context is the point of the review.
- Wait for the report. Never end your turn while the reviewer is still running.

## 3. Revalidate Blocker and High

For each Blocker and High finding:

1. Read the cited lines and the code around them.
2. Follow the `Fails when:` scenario through the code to the wrong outcome. When it is cheap, prove it: run an
   existing test, or a throwaway script kept outside the repo (the scratchpad or `/tmp`). Never change the repo's
   files while revalidating.
3. Give a verdict with its reason: **confirmed**; **regraded** to another severity; or **dropped** as not a defect,
   citing the code or the test that shows it.
4. For each confirmed finding, write your recommended fix: what to change, where, and, for API code, the test that
   will reproduce the finding before the fix. UI code gets no tests for now: its fix is checked by lint and build.

Merge duplicates into one finding. Medium and Low findings are not revalidated.

## 4. Save Medium and Low

Add every Medium and Low finding to the plan's `## Review remarks` section at once, whatever the developer decides
next:

`- [ ] F<N> (<severity>, not revalidated) <path:line> <problem> · fix: <the reviewer's fix>`

## 5. Present and ask

One message:

```
Review of <plan path> (Base <short hash>): <n> findings.

Confirmed:
F1 Blocker  <path:line>  <problem>
   Fails when: <inputs or state> → <wrong outcome>
   Fix: <recommended fix> · test: <test that reproduces it>

Regraded or dropped:
F3 High → Medium: <reason>
F4 dropped: <reason>

Medium and Low: <n>, saved to Review remarks as not revalidated.

Fix the confirmed findings now in the development loop, or save them as review remarks for later?
```

With no confirmed findings, say so, skip the question and go to step 6.

## 6. Record the decision

- **Fix now:** append each confirmed finding to the plan's Tasks, numbered after the last task:
  `- [ ] <N>. Fix F<N>: <problem> · files: <paths> · tests: <test that reproduces it>`, or `tests: none (UI)` for a
  finding in UI code.
  use-sw-development-workflow runs the loop on them.
- **Save:** add each confirmed finding to Review remarks:
  `- [ ] F<N> (<severity>, confirmed) <path:line> <problem> · fails when: <scenario> · fix: <recommended fix>`.
- **The developer names some findings to fix:** those become tasks, the rest are saved.

Then set the plan's `Review:` line to `Review: YYYY-MM-DD, <n> findings; fixing: <F-ids or none>; saved: <F-ids or none>`.

## Red Flags

| Thought | Reality |
|---------|---------|
| "The reviewer marked it Blocker, so it is one" | Revalidate it against the code. The reviewer's label is a claim. |
| "I read the diff myself, the reviewer is redundant" | Same author, same blind spots. The reviewer is the only fresh context. |
| "The fix is obvious, I'll apply it while revalidating" | The developer decides first. Revalidation never edits code. |
| "Medium and Low don't matter, skip them" | They go to Review remarks. A finding with no entry is lost. |
| "Review again after the fix loop" | Each API fix is proven by a test that failed before it and passes after; each UI fix by lint, build and the lead's read of the diff. |
