---
name: project-memory
description: "Use when work touches a named project; keep its file."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [projects, memory, notes, continuity]
---

# Project Memory

Per-project notes live outside the agent's bounded memory, one markdown file each, in a git-synced repo. Use this whenever the user mentions a project by name or starts work that clearly belongs to one.

## When to Use

- The user names a project ("the parser", "my Shopify app") or asks to resume earlier work.
- You are about to make an architectural decision, or one was just rejected for a reason.
- A session ends with state a future session would need: what works, what's blocked, what's next.
- The user asks what we were doing on something.

Skip it for one-off questions and anything with no continuing thread.

## Where

```
~/hermes-memory/projects/INDEX.md      # the table of projects
~/hermes-memory/projects/<slug>.md     # one file per project
~/hermes-memory/projects/_TEMPLATE.md  # structure for a new file
```

On Windows that is `C:\Users\<user>\hermes-memory\projects\`. The same paths appear on any machine after `git clone` plus `python sync.py --restore`.

## Read path (start of work)

1. Read `INDEX.md`. It is short by design.
2. If the project is listed, read only that project's file before acting.
3. If it is not listed, say so, then offer to create it from `_TEMPLATE.md`.

Do not read every project file. The index exists so that loading stays cheap.

## Write path (end of meaningful work)

Update the project file when any of these is true:

- a decision was made, or an approach was rejected for a reason worth keeping
- state changed: something now works, or broke in a new way
- a new next step or blocker appeared
- a gotcha cost real time

Rules:

- Edit the section that changed. Rewrite `Current state` rather than appending a log.
- Append decisions as one dated line each, with the reason. Never a narrative.
- Bump `Last touched` and the index row in the same edit.
- Keep the file under roughly 150 lines. When it grows, cut resolved detail; git history keeps it.
- Never write secrets, tokens or passwords. Name where the secret lives instead.

## Creating a project

Copy `_TEMPLATE.md` to `<slug>.md`, fill Goal and Stack, add a row to `INDEX.md`, then commit. Slug is lowercase and hyphens, and never changes afterwards.

## Syncing

```bash
cd ~/hermes-memory && python sync.py
```

Mirrors Hermes memory and skills, commits, pushes. Project files are already inside the repo, so a plain `git add -A && git commit && git push` covers them when sync.py is not wanted.

## Boundaries

- This is not the agent's memory tool. Do not copy project detail into `MEMORY.md`; that budget is for facts that apply to every session.
- Ordinary conversation does not belong here. Only what a future session would need to resume the work.
