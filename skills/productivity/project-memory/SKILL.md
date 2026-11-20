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

## Triggers: when the file must be updated

Two standing rules from the user:

1. **After every push.** The moment work on a project ends in a `git push`, update that project's file before moving on: rewrite `Current state`, add dated decision lines, refresh `Next steps`, bump `Last touched`, update the index row, advance `recorded_sha` in `repos.json`, then push this repo. Do not wait to be asked.
2. **One hour of quiet.** If a project saw work (commits, or a session that changed its direction) and then an hour passes with no further activity, flush the update. This is the case a push does not cover: work that was never committed, or a decision made in conversation.

The scheduled job `project-memory-sync` covers rule 2 automatically: every 30 minutes a script checks each tracked repo, stays silent unless a repo has commits newer than its `recorded_sha` and its last commit is at least 60 minutes old, and only then wakes an agent to write the file. When it wakes you, the monitor output names the project slugs and the registry holds the paths and baselines.

## Where

```
~/hermes-memory/projects/INDEX.md      # the table of projects
~/hermes-memory/projects/<slug>.md     # one file per project
~/hermes-memory/projects/_TEMPLATE.md  # structure for a new file
```

On Windows that is `C:\Users\<user>\hermes-memory\projects\`. The same paths appear on any machine after `git clone` plus `python sync.py --restore`.

## Registry on more than one machine

One `repos.json` is shared through the memory repo, so a machine-local `path`
written on one host (a Windows drive path, a different home directory) silently
disables the monitor on the other: the path does not exist, the entry is skipped,
and nothing warns. Use a per-host override so one registry serves every machine:

```json
{
  "path": "<default clone path for this project>",
  "paths": {
    "<this-host>": "/home/shuvo/Projects/skybridge-portal"
  },
  "remote": "https://github.com/...",
  "recorded_sha": "..."
}
```

- `path` is the fallback default, used when the hostname is not in `paths`.
- `paths[socket.gethostname()]` is checked first; the monitor resolves it before
  falling back to `path`.
- When registering a project, fill both keys if you know the other machine's
  hostname and clone location. Never repoint `path` at the machine you happen to
  be on when another host already relies on it.

## Read path (start of work)

1. Read `INDEX.md`. It is short by design.
2. If the project is listed, read only that project's file before acting.
3. If it is not listed, say so, then offer to create it from `_TEMPLATE.md`.

Do not read every project file. The index exists so that loading stays cheap.

## Gathering the evidence (repo-backed projects)

Write the file from the repo, not from recall and not by asking the user what they did. For each
registered repo, from its local path:

1. `git status --short` and `git log --oneline <recorded_sha>..HEAD` — committed work since the
   recorded baseline, plus whatever is sitting uncommitted.
2. `git diff --stat` and `git diff --stat <recorded_sha>..HEAD` — size and shape of the change.
3. `git rev-parse --short HEAD @{u}` with `git log --oneline @{u}..HEAD` — whether HEAD is pushed. An
   unpushed commit is ordinary state to record, not a mistake to fix silently.
4. For a large or unfamiliar diff, read entry points rather than every file: the route or handler
   list, the new module's exports, and `package.json` for added dependencies.
5. **Before writing "X works", find X's call sites** (`grep -rn <symbol> src/`, `search_files`). A
   layer that exists but is never invoked changes nothing at runtime, and recording it as done hides
   the real next step. State which it is: built, wired, or both.

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
- Edit with targeted patches, one section at a time. A whole-file rewrite is refused after a
  paginated read, and per-section patches keep the diff reviewable.
- Never write secrets, tokens or passwords. Name where the secret lives instead.

## Creating a project

1. Copy `_TEMPLATE.md` to `<slug>.md`; fill Goal, Stack and Repo / location.
2. Add a row to `INDEX.md`.
3. If the project has a git repo, register it in `repos.json` as
   `{path, remote, recorded_sha, recorded_sha_date, file}`, with `recorded_sha`
   set to the newest commit visible here (local HEAD included), not to upstream.
   **The scheduled check only sees registered repos** —
   an unregistered project never gets an automatic update however much work it
   sees. If the repo is not cloned on this machine, either clone it or leave the
   entry out and tell the user the automatic rule will not fire for it yet.
4. Slug is lowercase and hyphens, and never changes afterwards. Commit.

## Testing the automatic update

Run `scripts/verify_project_memory_monitor.py` rather than hand-testing: it
builds a throwaway repo with backdated commits, asserts the monitor fires, that a
repeated idle tick produces byte-identical output, and that it goes silent once
`recorded_sha` advances to HEAD. It restores the registry on the way out.
Re-run it after every edit to the monitor.

To prove the positive path by hand without waiting out the quiet window, run the
monitor with the threshold forced to zero
(`PROJECT_MEMORY_QUIET_MINUTES=0 python3 "$HERMES_HOME/scripts/project_memory_monitor.py"`):
it must name every repo whose HEAD is ahead of its baseline, and two consecutive
runs must be byte-identical. If that prints nothing while a baseline is genuinely
behind, the path resolved to nothing on this host — check `paths` for this
hostname before concluding the repos are quiet.

Traps it exists to catch:

- **The baseline is the newest commit you can see, not the remote's.** A `recorded_sha` taken from
  `@{u}` alone re-fires while local HEAD is ahead of origin, so the gate reports work it just
  recorded as new. Take whichever of local HEAD and upstream is newer, both in the monitor and when
  advancing the baseline by hand.
- **Any value that changes between ticks re-wakes the agent every tick.** An
  elapsed duration ("quiet 70m"), a timestamp, or unsorted iteration in the
  output makes the gate useless and burns a model run per tick. Print what
  changed, never when or how long ago.
- **Git rejects relative dates in `GIT_COMMITTER_DATE`.** When backdating
  fixture commits, pass absolute ISO timestamps (`2026-11-10T07:00:00+00:00`);
  `"2 hours ago"` fails the commit silently and the fixture ends up empty.

## Syncing

```bash
cd ~/hermes-memory && python sync.py
```

Mirrors Hermes memory and skills, commits, pushes. Project files are already inside the repo, so a plain `git add -A && git commit && git push` covers them when sync.py is not wanted.

## Boundaries

- This is not the agent's memory tool. Do not copy project detail into `MEMORY.md`; that budget is for facts that apply to every session.
- Ordinary conversation does not belong here. Only what a future session would need to resume the work.
