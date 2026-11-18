# Projects

One file per project, named `<slug>.md`. This index is the entry point: read it first, then open only the file you need.

| Project | Slug | Status | Last touched |
|---|---|---|---|
| Skybridge Portal | `skybridge-portal` | active | 2026-11-18 |
| AASH API | `aash-api` | active | 2026-11-10 |

## Conventions

- **Slug**: lowercase, hyphens, stable forever. Renaming a project keeps its slug.
- **Status**: `active`, `paused`, `shipped`, `abandoned`.
- **Last touched**: `YYYY-MM-DD`, updated whenever the file changes.
- Read the index at the start of any work session that mentions a project, then load only the matching file.
- Keep each file under ~150 lines. Cut resolved detail; the git history in this repo holds the rest.
- **`repos.json`** maps each slug to its local repo path and the commit sha its project file was last written for. That baseline is what decides when an update is due: the scheduled check fires when a repo has commits newer than its baseline and its last commit is at least an hour old. Advance the baseline whenever you update a file.
- Never store API keys, passwords or tokens here. Reference where the secret lives instead.