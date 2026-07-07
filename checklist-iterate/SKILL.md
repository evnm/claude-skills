---
name: checklist-iterate
description: Works through a categorized markdown checklist file of open tasks — scopes each item, decides whether to execute directly or split across parallel subagents, confirms the plan with you, executes, and keeps the checklist file updated with progress notes as it goes. Re-run after appending new tasks to continue the loop. Use when the user has a checklist/task-list file (headings grouping `- [ ]` items) they want worked through iteratively.
---

You are working through a checklist file: a markdown document with
`##`/`###` headings grouping tasks by area (e.g. a screen, a subsystem),
each task a `- [ ]` (open) or `- [x]` (done) line. This skill runs the same
read → scope → plan → confirm → execute → update loop every time it's
invoked, so the checklist file accumulates a durable, append-only history of
what was done and why — future runs (and future readers) rely on that
history, so never rewrite or second-guess it.

Example of the shape you're reading:

```markdown
## Diagnosis screen

- [x] Replace the header with "Diagnosis"
  - Eyebrow label in `OnboardingDiagnose.tsx` changed to match the pattern
    used elsewhere.
- [ ] Add subtext explaining what to enter
```

## Step 0 — Locate the checklist file

If the user passed a path (as a skill argument or in their message), use it.
If not, ask which file — don't guess a path.

## Step 1 — Read and parse

Read the full file. Identify every `- [ ]` (open) item, grouped by its
enclosing heading.

Skip every `- [x]` item entirely — never re-do, re-verify, or edit its
existing notes unless the user explicitly asks you to revisit that specific
item.

If there are zero open items, tell the user the checklist is fully checked
off and stop. Don't invent work to do.

## Step 2 — Scope each open item

For each open item, do just enough investigation (grep/read, not
implementation) to know which files/areas it touches and roughly how much
work it is. Read the actual current code — checklist items are often
written without full knowledge of the codebase, so an item may turn out to
already be satisfied, already partially done, or bigger/smaller than it
reads.

Note overlaps: two items that touch the same file(s) belong in the same
unit of work and must never be split across parallel agents — concurrent
edits to one file will race or conflict.

## Step 3 — Decide direct execution vs. subagents

Default to doing the work yourself, directly, in this session. Most
checklists are small enough (a handful of items, each touching a couple of
files) that spawning subagents adds coordination overhead without saving
real time.

Only propose parallel subagents when the open items:
- number enough that serial execution would be slow going,
- split cleanly into disjoint file/area groups (per Step 2's overlap
  check), and
- each represent a substantial, independent chunk of work — not a
  one-line copy or config edit.

When subagents are warranted, define one group per disjoint area. Each
group's prompt must be self-contained: the specific checklist items it
owns (quoted verbatim), the file paths already identified in Step 2, and an
explicit instruction to *report back* what it changed and how it verified
it. Subagents must not edit the checklist file themselves — see Step 5 for
why.

## Step 4 — Present the plan and get confirmation

Show the grouping (a direct-execution task list, or the subagent groups)
and the reasoning behind it. Get explicit confirmation before doing any
work — use AskUserQuestion when there's a real choice to present (e.g.
direct vs. subagents, or an alternative grouping), or a plain-text summary
otherwise, but either way wait for the user's go-ahead.

Take redirection seriously: if the user reshapes the groups or picks a
different approach, replan Step 3 around their shape rather than arguing
for your original split.

## Step 5 — Execute

**Direct case:** work through items in a sensible order, verifying each as
you finish it (typecheck, relevant tests, or the project's `verify` skill
if one exists).

**Subagent case:** launch the confirmed groups in parallel — one message,
multiple Agent tool calls. Wait for their reports.

**Only this top-level session writes to the checklist file, regardless of
who did the work.** After each item (or group) is verified complete,
immediately edit the checklist file: flip `- [ ]` to `- [x]` and add one
short indented bullet underneath summarizing what changed and where. Do
this incrementally as work lands, not all at once at the end, so progress
survives an interruption and a partially-complete pass still leaves an
accurate record.

If an item turns out to already be satisfied by existing code, still check
it off, with a note explaining why no change was needed — don't leave it
open just because there was no diff.

## Step 6 — Verify and report

Run the project's standard verification (typecheck + test suite, or its
`verify` skill) once all items in this pass are done.

Summarize what changed, item by item, referencing the files touched. Flag
anything you deliberately skipped or deferred and why.

Don't commit the changes unless the user explicitly asks.

## Step 7 — The loop continues

The user may append new `- [ ]` items — under existing or new headings — to
the same file later and re-invoke this skill. Each re-run repeats Steps 1–6
against whatever is newly open. Never re-litigate, redo, or edit the notes
on already-checked items from a prior run.
