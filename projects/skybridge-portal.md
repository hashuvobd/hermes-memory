# Skybridge Portal

- **Slug:** `skybridge-portal`
- **Status:** active
- **Started:** 2026-10-25
- **Last touched:** 2026-11-10
- **Repo / location:** `E:\My Projects\Skybridge Portal` · https://github.com/hashuvobd/skybridge-portal-v2
- **Stack:** Next.js 16.4.3 (App Router, Turbopack) · React 19.3 · TypeScript · Tailwind v4 · Supabase (JS REST client) · Supabase Auth via @supabase/ssr · Prisma (seed/CLI only) · xlsx

## Goal

Internal operations desk for Sky Bridge Visa Consultancy: track Bangladesh → North Macedonia
employment migration candidates from intake through submission, work-permit approval and
deployment readiness, plus the partner agencies sourcing them. Used by head-office ops staff.
Done = staff run the pipeline off this instead of the Excel mother list.

## Current state

Works and is live on real Supabase data (verified 2026-11-10: 208 candidates, 21 agencies,
22 approvals, 181 submitted, 2 deployment-ready). Four views: Operations Desk (table),
Pipeline Board (kanban), Insights (KPIs), Partner Agencies. All CRUD works: add/edit candidate,
inline milestone toggles, batch actions, agency CRUD with reassignment, XLSX export, WhatsApp
summary copy, Excel import.

Verification on 2026-11-10: `tsc --noEmit` clean, `npm run build` passes (10 routes, `/` static),
dev server 200, all API routes return real (non-dummy) data. `eslint` reports 32 errors / 22
warnings, all `no-explicit-any` + unused vars — `next build` does not gate on lint.

**Committed 2026-11-10 as `f29cd3a`:** the long-parked Supabase runtime migration (`dataService.ts`
Prisma → Supabase, `types.ts` decoupled from `@prisma/client`, `next.config.ts` and
`output: "standalone"`, `scripts/prepare-deploy.js`). Not yet pushed: master is ahead 1 of
origin/master.

**Uncommitted: the auth layer and role model.** Supabase Auth through `@supabase/ssr`. Role and agency
binding live in `app_metadata` (not user-writable), display name in `user_metadata`; a session without a
valid role is rejected outright. `src/proxy.ts` (Next 16's middleware) refreshes cookies and bounces
anonymous visitors to `/login`; authorization itself is per-route through `@/lib/auth/guards`.

Roles: **ADMIN** (everything, incl. Team & Access), **EMPLOYEE** (operations data, read/write), **AGENT**
(read-only, hard-scoped to its own agency). Every route now guards itself — candidate reads any
signed-in user with AGENT pinned to its own `agentId` regardless of query params; candidate writes and
agency creation ADMIN/EMPLOYEE; agency delete, seed and user administration ADMIN; metrics and export
ADMIN/EMPLOYEE. Two Supabase clients by design: a user-scoped cookie client for request paths, a
service-role client only for auth admin calls. First administrator via `/setup` + `/api/setup`, public
until one exists, permanently closed after. Accounts are created by admins at `/api/users` and the
Team & Access screen; deactivation is a 100-year Supabase ban, which kills both new logins and live
sessions. Auth events are written to `AuditLog` with a null `candidateId`.

Verified 2026-11-10 end to end against the live project using throwaway accounts: **45/45** role and
access checks plus **13/13** lifecycle checks (staff creation, AGENT promotion requires an agency,
deactivate/reactivate, delete, 8-attempt sign-in throttle, sign-out invalidating a replayed access
token, unknown-account 404). Every test account was deleted afterwards — `auth.users` back to 0 and the
portal back in its first-run state. `npm run build` clean, 17 routes, `/` still static.

Scripts: `scripts/auth-e2e.sh` (the suite, self-cleaning), `scripts/_auth-cleanup.mjs` (deletes
`auth-e2e-*` / `auth-verify-*` accounts). `deploy.zip` (65 MB) is gitignored.

## Decisions

- 2026-10-25 — Supabase Postgres via Prisma for the initial build.
- 2026-10-27 — Runtime data access moved off Prisma onto the Supabase JS REST client; Prisma left
  in place for seed/CLI only. Reason: Prisma's generated client and native binaries are painful in
  the standalone/VPS deploy target. `types.ts` was correspondingly decoupled from `@prisma/client`
  so the app ships without Prisma at all — do not reintroduce `@prisma/client` imports into shared
  or client modules.
- 2026-10-27 — Deploy target is a VPS/cPanel-style host via `output: "standalone"` +
  `scripts/prepare-deploy.js` producing `deploy.zip`.
- 2026-11-10 — Auth is Supabase Auth, not hand-rolled. Reason: a managed session store beats
  password handling in an internal ops tool.
- 2026-11-10 — Role and `agentId` live in `app_metadata`, `user_metadata` is display only. Reason: a
  user cannot write `app_metadata`, so no client can promote itself.
- 2026-11-10 — The proxy refreshes cookies and redirects, nothing more; each route handler verifies
  the session itself. Reason: the proxy is not the authorization boundary, and Next's docs say so.
- 2026-11-10 — Two Supabase clients split by purpose: user-scoped for requests, service-role only for
  auth admin. Reason: keeps RLS meaningful and confines the key that bypasses it.
- 2026-11-10 — The "two data layers" split was judged ugly but not a bug; parked deliberately.
  Prisma is dead weight at runtime but harmless.

## Open questions

- Deployment host for `deploy.zip` — which box, and is it still live?
- Was `deploy.zip` ever uploaded anywhere? It contains `.env` including the service-role key
  (see Gotchas).
- Has login, logout and first-admin setup been verified end to end against this Supabase project, and
  does `/api/setup` actually self-disable once an admin exists? — **Answered 2026-11-10: yes, both.**
- Which routes get guards, and once requests run as the signed-in user rather than the service role,
  which tables need RLS policies written? — **Guards: done. RLS policies: still open** (all 3 tables
  have RLS disabled and 0 policies, so nothing depends on it yet).
- Are the 21 agencies correct, or is the true partner list the 17 in the README?

## Next steps

Findings from the 2026-11-10 review, ordered worst-first. All still open.

1. **Requests still reach the database as the service role.** Access control now sits in the route
   handlers, but `dataService.ts:30` and `src/lib/supabase.ts` still prefer
   `SUPABASE_SERVICE_ROLE_KEY`, so the layer underneath runs with the key that bypasses RLS — and RLS is
   off on all three tables anyway. The next real hardening step is running request-path reads as the
   signed-in user and writing policies to match. Then commit the auth work and push `f29cd3a` —
   master is ahead 1 of origin/master.
2. **PostgREST filter injection.** `dataService.ts:103` interpolates raw search into
   `query.or(\`name.ilike.%${search}%,...\`)`. A `,` or `)` rewrites the filter expression. Real
   injection surface given the service-role key.
3. **Three dashboard metrics measure the wrong thing.** `missingPassportsApproved` increments on
   `!passportInHand` for *all* candidates, never checking `approval` (reads 19). `pendingOver30Days`
   is `submissionSlip && !approval` with no date comparison (reads 159, UI claims "over 30 days").
   `inReview` is just `submitted − approved`.
4. **Batch actions can never reach DEPLOYMENT_READY.** In `batchUpdateCandidates`, DB path sets
   `stage` explicitly per action; `MARK_PASSPORT_IN_HAND` / `MARK_PCC_RECEIVED` flip the boolean but
   leave stage alone, unlike the single-record path which recomputes.
5. **Inline edits leave a stale stage pill.** `page.tsx handleUpdateCandidate` optimistically merges
   client-side, then on success calls `fetchMetrics()` but not `fetchCandidates()`; the server
   recomputed `stage` and the row never sees it.
6. **Agency delete reassigns to a random agency.** Dialog promises "reassigned to Sky Bridge Direct
   Intake"; code takes any agent with a different id (`.neq('id', id).limit(1)`).
7. **`approvalCity` is written before approval**, so Insights' city breakdown counts non-approved
   files (Strumica shows 15 files / 13 approved). Both city selects also write it with no approval gate.
8. **Duplicate agencies from fuzzy matching.** Live data has `Sikder Trvl.` (6 files) *and*
   `Sikder trvl.` (1), `(Jhe) Fly Mig` alongside the mapped `Fly Migration Jhenaidah`, and
   `Shamoli` with 0 submissions. `resolveAgent`'s substring matching mints a new agency on every
   spreadsheet spelling drift. Also: Insights hardcodes "17 regional sourcing partners" and
   "21 Approvals Granted (Oct 2026)" as literal strings.
9. **`PATCH /api/candidates/[id]` has no validation** (POST uses zod). Raw body reaches
   `updateCandidate`, so `sl`, `agentId`, `stage` are mass-assignable by any caller.
10. **`/api/seed` is a public unauthenticated POST** pointing at a hardcoded
    `C:\Users\Shuvo\Downloads\_Completed Contact Form List_NM(7).xlsx` — can never work on the host,
    and re-imports/overwrites all records from whatever that file now contains.
11. **Secret leak in the deploy artifact.** `prepare-deploy.js` copies `.env` into
    `.next/standalone` before zipping, so `deploy.zip` carries the service-role key.

Minor: `sl` uses `max+1` against a unique constraint (concurrent-create collision); `AuditLog` is
written on every mutation but never displayed; `REJECTED` is in the enum and styled in the table
but no UI sets it and kanban omits the column; `contactForm` always `true`, unused; `.env` and
`.env.local` are byte-identical duplicates.

## Key paths and commands

```bash
cd "/e/My Projects/Skybridge Portal"     # E:\My Projects\Skybridge Portal
npm run dev                              # localhost:3000
npx tsc --noEmit                         # typecheck — currently clean
npm run build                            # prod build; output:standalone
node check-count.js                      # live row counts via Prisma (read-only)
node scripts/prepare-deploy.js           # builds deploy.zip — copies .env into the zip
```

Auth module map: `src/lib/auth/{session,guards,types,audit,agency}.ts` (session → guards → data),
`src/lib/supabase/{server,admin}.ts` (user-scoped vs service-role), `src/proxy.ts` (cookie refresh and
redirect only), `src/app/{login,setup}/page.tsx`, `src/app/api/{auth,setup,users}/…`,
`src/components/{AuthShell,LoginForm,SetupForm,UserManagement}.tsx`.

Data flow is one funnel: `src/app/page.tsx` holds all state → `src/components/*` (props down) →
`src/app/api/*` (8 thin routes) → `src/lib/dataService.ts` (the only file touching data, ~50% of it
duplicated DB-vs-mock logic) → Supabase REST.

## Gotchas

- **Next 16 is not the Next you know.** `AGENTS.md` warns the APIs/conventions differ from training
  data and to read `node_modules/next/dist/docs/` before writing code. `cacheComponents: true` and
  `partialPrefetching: true` are both enabled.
- **The service-role key is still reachable from the request path** (`dataService.ts:30`,
  `src/lib/supabase.ts`). The new admin client is the only intended holder; any other use is a bug,
  not a convenience.
- **Business rule is duplicated in ~4 places.** `approval ? (passportInHand && pccReceived ?
  DEPLOYMENT_READY : APPROVED) : submissionSlip ? SUBMITTED : INTAKE` lives in `createCandidate`,
  `updateCandidate` (twice — DB and mock path), and `batchUpdateCandidates`. Change one, change all.
- **Supabase connector is project-scoped.** Connected as label `supabase_noir-lavish`; can operate
  on `bombegnoifzrchgqdqwv` only. `LIST_ALL_PROJECTS` returns 403 — enumerating projects needs a
  Personal Access Token. SQL tool can write despite its read-only flag.
- **`AuditLog.id` has no database default.** It is a Prisma `@default(cuid())`, which the Prisma client
  generates — the column is `text NOT NULL` with no default. Any write through PostgREST must supply its
  own id or it fails as a NOT NULL violation, and the failure is easy to miss because the audit writer
  swallows errors by design. `cuid()` ids anywhere else in the schema behave the same way.
- **Supabase key deprecation (by end of 2026):** `anon` and `service_role` keys retire → `sb_publishable_...`
  (client-safe, RLS applies) and `sb_secret_...` (server-only, bypasses RLS). Factor into the RLS work.
- **git-bash path translation is off for native binaries.** `node /tmp/x.js` resolves to
  `E:\tmp\x.js`. Use forward-slash native paths or `$LOCALAPPDATA/Temp` for scratch files.
- Killing the dev server: `taskkill //PID` fails in git-bash (MSYS rewrites the switch). Use
  `cmd //c "taskkill /PID <pid> /T /F"`.
- `syncExcel.ts` + `seed-from-excel.js` share a duplicated `AGENT_MAPPING` table — they drift
  independently and both encode the Excel spelling variants that cause the duplicate agencies.
