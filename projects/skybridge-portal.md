# Skybridge Portal

- **Slug:** `skybridge-portal`
- **Status:** active
- **Started:** 2026-10-25
- **Last touched:** 2026-11-18
- **Repo / location:** `E:\My Projects\Skybridge Portal` · https://github.com/hashuvobd/skybridge-portal-v2
- **Stack:** Next.js 16.4.6 (App Router, Turbopack) · React 19.3 · TypeScript · Tailwind v4 · Supabase (JS REST client) · Supabase Auth via @supabase/ssr · Prisma (seed/CLI only) · xlsx · jspdf · qrcode · html2canvas

## Goal

Internal operations desk for Sky Bridge Visa Consultancy: track Bangladesh → North Macedonia
employment migration candidates from intake through submission, work-permit approval and
deployment readiness, plus the partner agencies sourcing them. Used by head-office ops staff.
Done = staff run the pipeline off this instead of the Excel mother list.

## Current state

Live on real Supabase data and now behind auth. Seven views, permission-gated in `Navbar.tsx`:
Operations Desk (table ⇄ kanban toggle), Insights, Accounts, Partner Agencies, Lawyers, Activity
Logs, Team & Access. Built and wired: candidate CRUD with per-document uploads (photo, passport,
submission, PCC, approval, visa, flight, contact form), dual physical/scan passport and PCC flags,
custom date pickers, batch actions, XLSX export, Excel import, dossier generation, payments ledger,
lawyer assignment, and an activity log with an approve/reject flow.

Auth: Supabase Auth via `@supabase/ssr`, three system roles (ADMIN / EMPLOYEE / AGENT, AGENT pinned
to its own agency) plus **custom roles** — `CustomRole.permissions` holds keys from the 21-key
matrix in `src/lib/auth/permissions.ts` (`candidates.*`, `accounts.*`, `agencies.*`,
`dashboard.view`, `logs.*`, `team.*`); `hasPermission()` in `types.ts` gates UI and
`requirePermission()` / `requireRole()` / `requireOperationalWrite()` gate routes.
`/setup` + `/api/setup` creates the first admin, public only until one exists.

Dossier: `src/lib/dossierPdf.ts` is the single renderer. `/api/candidates/[id]/dossier` returns the
HTML print view (server-side `qrcode`); `downloadCandidateDossierPdf()` in the drawer/table produces
the PDF client-side (`jspdf` + `html2canvas`). Dual Office Copy / Agency Copy on one A4, watermark
seal from `blueSealBase64.ts`, QR pointing at `/verify/<id>`, 6-digit serial derived from `sl`.

Verification 2026-11-18 at `bde787f`: `npx tsc --noEmit` exits 0. No `npm run build` re-run this
session. Mock data fallbacks were removed — `dataService.ts` now throws on a dead DB instead of
serving samples (`da72ebc`).

**Committed 2026-11-18 as `bde787f`** (39 commits, 68 files since `f29cd3a`): Next.js 16.4.3 →
16.4.6, the auth/RBAC layer, dossier engine, lawyer and payment modules, activity logs, and the
Candidate/Agent schema growth (`status`, `visa*`, `flight*`, `pccInHand`/`pccScanReceived`,
`passportScanReceived`, per-document `*DocName`/`*DocData`, `approvedCountry`, `jobType`,
`lawyerId`, `requiredAmount`/`refundRequiredAmount`, `Agent.phase`; new `Payment`, `CustomRole`
and `Lawyer` models). Pushed: HEAD equals `origin/master`.

**Uncommitted:** untracked artifacts only — `.tmp-verify/`, `Blue-Seal-Sky-Bridge.png` (already
copied into `public/`), `agy-decode-run.log`.

## Decisions

- 2026-10-25 — Supabase Postgres via Prisma for the initial build.
- 2026-10-27 — Runtime data access moved off Prisma onto the Supabase JS REST client; Prisma kept for
  seed/CLI only. Reason: the generated client and native binaries hurt the standalone deploy target.
  Do not reintroduce `@prisma/client` into shared or client modules.
- 2026-10-27 — Deploy target is a VPS/cPanel-style host via `output: "standalone"` +
  `scripts/prepare-deploy.js` producing `deploy.zip`.
- 2026-11-10 — Auth is Supabase Auth, not hand-rolled. Reason: managed sessions beat password handling.
- 2026-11-10 — Role and `agentId` live in `app_metadata`, `user_metadata` is display only. Reason: a
  user cannot write `app_metadata`, so no client can promote itself.
- 2026-11-10 — The proxy refreshes cookies and redirects, nothing more; each route handler verifies
  the session. Reason: the proxy is not the authorization boundary.
- 2026-11-10 — Two Supabase clients: user-scoped for requests, service-role only for auth admin.
  Reason: keeps RLS meaningful and confines the key that bypasses it.
- 2026-11-18 — System roles replaced fixed role checks with a permission-key matrix plus custom
  roles, so ops can grant narrow access without a code change.
- 2026-11-18 — One dossier template (`dossierPdf.ts`) drives both the print route and the client
  PDF download, instead of separate print and download implementations.

## Open questions

- Deployment host for `deploy.zip` — which box, and is it still live? The zip carries `.env` with the
  service-role key.
- Are the new tables and columns (`Payment`, `CustomRole`, `Lawyer`, the `Candidate` document and
  visa/flight fields) actually applied to the live Supabase project? `prisma/schema.prisma` is
  documentation now — PostgREST is the runtime, so a missing column fails at request time.
- RLS is off on the original three tables and unaudited on the new ones. Which policies, and do they
  land before or after the `sb_publishable_` / `sb_secret_` key switch?
- `/verify/<id>` and `/api/candidates/<id>/dossier` render the full dossier — passport number and
  photo included — with no guard, and every printed dossier QR-codes the first. Should `/verify`
  become a redacted public view instead?
- Are the 21 agencies correct, or is the true partner list the 17 in the README?

## Next steps

Ordered worst-first. None of these were addressed by the `f29cd3a..bde787f` work.

1. **Requests still reach the database as the service role.** `dataService.ts:13` and
   `src/lib/supabase.ts` prefer `SUPABASE_SERVICE_ROLE_KEY`, so the layer under the guards bypasses
   RLS. Run request-path reads as the signed-in user, then write policies to match.
2. **Public unguarded dossier.** `src/app/api/candidates/[id]/dossier/route.ts` and
   `src/app/verify/[id]/route.ts` skip `requireUser()`; both return the full record. Decide the
   public contract, then redact or guard.
3. **PostgREST filter injection.** `dataService.ts:95,97` interpolate raw search into
   `query.or(`name.ilike.%${search}%,…`)` — a `,` or `)` rewrites the filter expression.
4. **Three dashboard metrics measure the wrong thing** (`dataService.ts:886–888`):
   `missingPassportsApproved` counts `!passportInHand` across every candidate without checking
   `approval`; `pendingOver30Days` is `submissionSlip && !approval` with no date comparison;
   `inReview` is just `submitted − approved`.
5. **Batch actions never recompute `stage`.** `batchUpdateCandidates` sets `stage` only for
   SUBMITTED/APPROVED; `MARK_PASSPORT_IN_HAND` and `MARK_PCC_RECEIVED` flip the flag and leave the
   stage stale, unlike the single-record path.
6. **`PATCH /api/candidates/[id]` has no schema.** POST screens with zod, PATCH passes the raw body
   to `updateCandidate`, so `sl`, `agentId`, `stage`, `lawyerId` are mass-assignable by anyone with
   write permission.
7. **Secret leak in the deploy artifact.** `prepare-deploy.js` copies `.env` into
   `.next/standalone` before zipping.
8. **Agency hygiene.** `resolveAgent`'s substring matching mints duplicate agencies on spreadsheet
   spelling drift; agency delete reassigns to an arbitrary different agency rather than Sky Bridge
   Direct Intake; `approvalCity` is written before approval, so Insights' city split over-counts.

Minor: `sl` uses `max+1` against a unique constraint (concurrent-create collision); `syncExcel.ts`
and `seed-from-excel.js` duplicate the `AGENT_MAPPING` table and drift independently.

## Key paths and commands

```bash
cd "/e/My Projects/Skybridge Portal"     # E:\My Projects\Skybridge Portal
npm run dev                              # localhost:3000
npx tsc --noEmit                         # typecheck — clean at bde787f
npm run build                            # prod build; output:standalone
node check-count.js                      # live row counts via Prisma (read-only)
node scripts/prepare-deploy.js           # builds deploy.zip — copies .env into the zip
```

Routes (24 route handlers): `api/auth/{login,logout,me}`,
`api/candidates` (+`[id]`, `[id]/dossier`, `batch`), `api/agents` (+`[id]`), `api/lawyers` (+`[id]`),
`api/payments` (+`[id]`), `api/roles` (+`[id]`), `api/users` (+`[id]`),
`api/activity-logs` (+`[id]/approve`), `api/dashboard/metrics`, `api/export`, `api/seed`,
`api/setup`, plus `verify/[id]`.

Auth module map: `src/lib/auth/{session,guards,types,permissions,audit,agency}.ts` (permissions →
types → guards → data), `src/lib/supabase/{server,admin}.ts` (user-scoped vs service-role),
`src/proxy.ts` (cookie refresh and redirect only), `src/app/{login,setup}/page.tsx`,
`src/app/api/{auth,setup,users,roles}/…`,
`src/components/{AuthShell,LoginForm,SetupForm,UserManagement}.tsx`.

Data flow: `src/app/page.tsx` holds all state → `src/components/*` (props down) → `src/app/api/*` →
`src/lib/dataService.ts` and `paymentService.ts` (the only files touching data) → Supabase REST.

## Gotchas

- **Next 16 is not the Next you know.** `AGENTS.md` warns the APIs/conventions differ from training
  data and to read `node_modules/next/dist/docs/` before writing code. `cacheComponents: true` and
  `partialPrefetching: true` are both enabled.
- **The service-role key is still reachable from the request path** (`dataService.ts:13`,
  `src/lib/supabase.ts:5`). The new admin client is the only intended holder; any other use is a bug,
  not a convenience.
- **Public unguarded dossier.** `/verify/<id>` and `/api/candidates/[id]/dossier` skip
  `requireUser()` and render the full record — passport number, photo, dates. Anyone with a
  candidate id (including the QR printed on every dossier) gets it.
- **Business rule is duplicated in ~4 places.** `approval ? (passportInHand && pccReceived ?
  DEPLOYMENT_READY : APPROVED) : submissionSlip ? SUBMITTED : INTAKE` lives in `createCandidate`,
  `updateCandidate` (twice — DB and mock path), and `batchUpdateCandidates`. Change one, change all.
- **Supabase connector is project-scoped.** Connected as label `supabase_noir-lavish`; can operate
  on `bombegnoifzrchgqdqwv` only. `LIST_ALL_PROJECTS` returns 403 — enumerating projects needs a
  Personal Access Token. SQL tool can write despite its read-only flag.
- **`AuditLog.id` has no database default.** Prisma's `@default(cuid())` is client-generated, so the
  column is `text NOT NULL` with no default. A PostgREST write must supply its own id or it fails as
  a NOT NULL violation — and the audit writer swallows errors, so the failure is silent. `Payment`,
  `CustomRole`, `Lawyer` and the rest of the schema behave the same way.
- **Supabase key deprecation (by end of 2026):** `anon` and `service_role` keys retire → `sb_publishable_...`
  (client-safe, RLS applies) and `sb_secret_...` (server-only, bypasses RLS). Factor into the RLS work.
- **git-bash path translation is off for native binaries.** `node /tmp/x.js` resolves to
  `E:\tmp\x.js`. Use forward-slash native paths or `$LOCALAPPDATA/Temp` for scratch files.
- Killing the dev server: `taskkill //PID` fails in git-bash (MSYS rewrites the switch). Use
  `cmd //c "taskkill /PID <pid> /T /F"`.
