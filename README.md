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