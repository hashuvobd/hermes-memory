# Memory: Limits, Backends, and Moving It Between Machines

## What memory actually is

- Two plain files: `$HERMES_HOME/memories/MEMORY.md` (agent notes) and
  `USER.md` (user profile). Not a database, not an account record.
- Rendered into the system prompt as a **frozen snapshot at session start**.
  An entry saved mid-session is visible to the *next* session, never to the
  running one. Tool responses show live state, the prompt does not.
- Character limits are `memory.memory_char_limit` and
  `memory.user_char_limit` (defaults 2200 / 1375, about 2.75 chars per token).
  Raising them is free and local: `hermes config set memory.memory_char_limit 5000`.
  Say plainly that the new value applies from the next session.
- Over-limit writes are **refused, not truncated**, and the refusal shows the
  current entries. The fix is one batched call that removes or shortens stale
  entries and adds the new one together; limits are checked on the final result.
- No `read` action and no auto-compact. Disable with `memory.memory_enabled: false`.
  `hermes memory reset` erases both files; memory is per-profile, under
  `~/.hermes/profiles/<name>/memories/`.
- `hermes memory` (setup/status/off/reset) manages **external providers only**
  (honcho, mem0, supermemory, hindsight, byterover, retaindb, openviking,
  holographic). Built-in memory is always active alongside them.

## Two traps worth checking first when "it didn't remember"

- The model claimed a save without calling the memory tool. Read the file on
  disk to confirm. Small or weak-tool-calling models do this often.
- `write_approval: true` staged the write; it never reached the file until
  `/memory approve all`.

## Nothing about memory syncs through the user's account

A Nous Portal / provider login covers model access and billing, not storage.
When the user asks "does my memory follow me to a new device?" the honest answer
is no by default, then offer one of these three routes.

1. **Git repo of `memories/` + `skills/`** (plus any agent-owned notes dirs).
   Small, versioned, reviewable. Restore = clone, then reverse-copy.
2. **`hermes backup` / `hermes import`** — zip and restore the whole Hermes home,
   settings included. One command each way, manual cadence, all-or-nothing.
3. **An external memory provider** — server-side, so it follows the user with no
   copying. Costs a third-party account and key, hosted tiers may be paid, and it
   changes how memory behaves rather than just where it lives.

Never sync `.env`, `auth.json`, `sessions/`, `state.db`, or browser data.

## Sync script pattern (validated end to end)

- Mirror with copy-if-newer (mtime or size differs) and delete files in the
  destination that no longer exist in the source, so deletions propagate.
  Skip `*.lock`. Stock Windows git-bash has no `rsync` — do the mirror in Python
  (`shutil.copy2` + a wanted-set sweep) rather than depending on rsync.
- Commit only when `git diff --cached --quiet` exits non-zero; `git add -A`
  covers the repo's own non-mirrored directories (project files, docs).
- Add a `.gitignore` for `__pycache__/` and `*.pyc` before the first commit.
- Verify the push from the remote side, not from local exit codes:
  `gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1 --jq '[.tree[].path]'`.
- Schedule it with a **script-only cron job** (`no_agent=True`): a wrapper inside
  `$HERMES_HOME/scripts/` that runs the repo's sync with `sys.executable` and
  prints a one-line summary **only when something was pushed**. Empty stdout is a
  silent tick; a non-zero exit becomes an error alert. Daily at a fixed local hour
  is the right cadence; pass `timezone` when the user names a zone.
- A recovery README in the repo pays for itself: clone, restore, re-copy the cron
  scripts, recreate the jobs. Cron jobs and `$HERMES_HOME/scripts/` are **not**
  inside `memories/` or `skills/`, so they do not travel on their own.

## Per-project notes ride along

When the user wants continuity per project rather than only agent memory, the same
repo carries a `projects/` tree (`INDEX.md`, `_TEMPLATE.md`, one `<slug>.md` each)
plus a `repos.json` registry of tracked repos and their recorded baselines. That
layer has its own workflow and its own monitor script — load the `project-memory`
skill before touching it. Two consequences for the sync itself: project files are
already inside the repo, so a plain `git add -A && git commit && git push` covers
them; and a script the sync depends on should be kept as a copy under the repo's
`scripts/` so a restore on a new machine has the source, not just the installed copy.
