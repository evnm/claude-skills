# claude-skills

A collection of personal [Claude Code](https://claude.ai/code) skills.

## Installation

Run `make install` to symlink each skill directory into
`~/.claude/skills/`.

## Skills

### checklist-iterate

Works through a categorized markdown checklist file (headings grouping
`- [ ]` tasks) one pass at a time: scopes the open items, proposes direct
execution or a parallel-subagent split, executes on confirmation, and keeps
the checklist updated with progress notes. Designed to be re-invoked as you
append new tasks to the same file.

### commit-unstaged

Reviews unstaged changes and untracked files, then proposes a coherent
sequence of self-contained commits with high-quality messages. Presents the
plan for confirmation before touching Git, so you can revise messages or
reorder commits before anything is written.

### recruiter-reply

Scans unread messages in a Gmail inbox for recruiter pitches and sends
templated replies in an interactive loop. See
[recruiter-reply/README.md](recruiter-reply/README.md) for setup
instructions.
