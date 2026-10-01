---
name: sw-grill-me
description: Use when sw-brainstorming leaves open questions, when a design or plan needs its decisions confirmed with the developer before coding, when the user wants to stress-test a plan or design, or when the user mentions "grill me".
---

Interview me relentlessly about every aspect of this plan until we reach a shared understanding. Walk down each branch of the design tree, resolving dependencies between decisions one-by-one. For each question, provide your recommended answer.

Ask the questions one at a time.

If a question can be answered by exploring the codebase, explore the codebase instead.

## In use-sw-development-workflow

- Start from the open-questions list sw-brainstorming produced. Ask first the questions whose answers change
  other questions.
- An answer can open a follow-up question. Ask it next, before you move on.
- Record each answer as `- <question> → <the developer's answer>`, for the plan's Decisions section. Use the
  developer's words. When they accept your recommendation, write the recommendation.
- An answer that changes the agreed design: say what changes in the design, get a yes, then continue.
- Stop when the list is empty and no follow-up question is open. Hand back to use-sw-development-workflow, which
  saves the plan.
