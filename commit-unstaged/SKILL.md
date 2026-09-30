---
name: commit-unstaged
description: Checks unstaged changes into Git as a sequence of commits with high quality commit messages. Use this whenever the user asks you to commit changes.
---

Read the unstaged changes (i.e. the output of `git diff`, plus the contents of any untracked files), think about code change(s) they represent, and then help me check the changes in to Git in a series of commits.

This interaction occurs in two parts:

1. First, based on your review of the changes, propose a series of commits.
  - Each commit should be self-contained and include a high quality commit message. A good commit message is one that conveys enough information for someone casually familiar with our codebase to understand it. Without being overly verbose, include any necessary context, a description of the problem or gap the commit addresses, and the solution the commit adds to the codebase.
  - When writing commit messages, adhere to the commit message guidelines in this repository's CLAUDE.md.
  - Collectively, the commits should be in a coherent order. We want to make it easy for code reviewers understand the broader change represented by a series of commits. Early commits might add independent components or tools that are then built upon by later commits, culminating in a "main" commit which uses those components/tools to solve the problem addressed by a pull request.
  - Model the presentation of the plan on the output of `git rebase -i`. Show the ordered list of commit messages.
  - Always print the full proposed commit sequence as plain text in your response — every commit's full message (title + body), not a summary or a truncated preview — BEFORE calling AskUserQuestion. The AskUserQuestion call itself is only for getting confirmation; its preview field is not a substitute for showing the plan in the actual message text, since the user should be able to read the full plan without opening/expanding anything.
  - The user must be able to read every proposed commit message without leaving the confirmation prompt. Text printed before a tool call can be hidden or collapsed in the UI (especially under terse output styles), so ALSO put the full proposed sequence (each commit's title and full body) in the `question` text or the `preview` field of the "Commit as proposed" option in AskUserQuestion. This applies regardless of output style: brevity rules never justify omitting or summarizing the commit messages.
  - Always end step 1 with the AskUserQuestion tool to get my explicit confirmation before committing anything — never proceed to step 2 based on plain-text approval alone, even for a single obvious commit. Offer at minimum "Commit as proposed" and "Revise message" (or similar) as options.
2. Second, once you've received by approval on the proposed commits, run the `git add`, `git commit`, etc commands necessary to enact the series of commits.
