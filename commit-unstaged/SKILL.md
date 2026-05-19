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
  - Model the presentation of the plan on the output of `git rebase -i`. Show the ordered list of commit messages and let me pick any which I'd like to revise. This may be either rewording a commit's message in situ or merging/breaking up commits.
2. Second, once you've received by approval on the proposed commits, run the `git add`, `git commit`, etc commands necessary to enact the series of commits.
