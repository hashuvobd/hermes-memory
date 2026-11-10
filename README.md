# hermes-memory

Private mirror of Hermes Agent memory and skills, so a new machine can pick up the same agent.

## What's here

- `memories/MEMORY.md` — the agent's own notes
- `memories/USER.md` — the user profile
- `skills/` — installed skills (markdown, load on demand)

No credentials, no `.env`, no sessions, no browser data. Memory and skills only.

## Pull changes up from this machine

```bash
cd ~/hermes-memory
python sync.py
```

Mirrors `~/AppData/Local/hermes/memories` and `.../skills` into the repo, commits, pushes.
`--no-push` commits locally only.

## Put them onto a new machine

After installing Hermes and signing in:

```bash
git clone https://github.com/hashuvobd/hermes-memory.git
cd hermes-memory
python sync.py --restore
```

That copies memory and skills into the local Hermes home (`%LOCALAPPDATA%\hermes` on Windows,
`~/.hermes` on Linux/macOS). Start a new Hermes session afterwards: memory is loaded at session start,
so an already-running session will not see it.

## Project memory

`projects/` holds one markdown file per project, an index (`INDEX.md`), a template, and `repos.json`,
which maps each project to its local repo and the commit sha its file was last written for.

Two rules keep it current:

1. After any `git push` on a project, its file gets updated before moving on.
2. An hour of quiet after work triggers the same update: work that was never committed, or a decision
   taken in conversation.

Rule 2 runs as a scheduled monitor job (`project-memory-sync`, every 30 minutes). The check itself is a
script with no model call, and the agent only wakes when a tracked repo has commits newer than its
recorded baseline and its last commit is at least 60 minutes old.

To rebuild the job on a new machine:

```bash
cp scripts/project_memory_monitor.py ~/.hermes/scripts/     # %LOCALAPPDATA%\hermes\scripts on Windows
```

Then ask Hermes: create a cron job every 30 minutes, monitor `project_memory_monitor.py`, skill
`project-memory`, prompt as documented in that skill.