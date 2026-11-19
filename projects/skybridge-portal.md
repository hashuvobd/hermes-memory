# Skybridge Portal

- **Slug:** `skybridge-portal`
- **Status:** active
- **Started:** 2026-10-25
- **Last touched:** 2026-11-19
- **Repo / location:** `E:\My Projects\Skybridge Portal` · https://github.com/hashuvobd/skybridge-portal-v2
- **Stack:** Next.js 16.4.6 (App Router, Turbopack) · React 19.3 · TypeScript · Tailwind v4 · Supabase (JS REST client) · Supabase Auth via @supabase/ssr · Prisma (seed/CLI only) · xlsx · jspdf · qrcode · html2canvas · local disk under `public/uploads` for documents

## Goal

Internal operations desk for Sky Bridge Visa Consultancy: track Bangladesh → North Macedonia
employment migration candidates from intake through submission, work-permit approval and
deployment readiness, plus the partner agencies sourcing them. Used by head-office ops staff.
Done = staff run the pipeline off this instead of the Excel mother list.

## Current state

Live on real Supabase data, behind auth, at `7de5114` (clean tree, HEAD = `origin/master`). Seven
views, permission-gated in `Navbar.tsx`: Operations Desk (table ⇄ kanban), Insights, Accounts,
Partner Agencies, Lawyers, Activity Logs, Team and Access. Candidate CRUD with per-document uploads,
dual physical/scan passport and PCC flags, custom date pickers, batch actions, XLSX export, Excel
import, dossier generation, payments ledger, lawyer assignment, activity log with approve/reject.

Auth: Supabase Auth via `@supabase/ssr`; ADMIN / EMPLOYEE / AGENT (AGENT pinned to its agency) plus
custom roles — `CustomRole.permissions` holds keys from the 21-key matrix in
`src/lib/auth/permissions.ts`. `hasPermission()` gates UI; `requirePermission()` / `requireRole()` /
`requireOperationalWrite()` gate routes. `/setup` + `/api/setup` creates the first admin, public only
until one exists.

**Documents moved off Postgres onto disk (2026-11-19, `3d47edc`, `a625463`).**
`src/lib/documentStorage.ts` owns the layout: `saveCandidateDocumentToDisk()` decodes a base64 data
URL, writes `public/uploads/candidates/<6-digit sl>_<PASSPORT>/<NN_category>/<file>`, and returns
`/uploads/...`, which replaces the blob in the DB. Nine fixed categories (`01_profile_photo` …
`09_receipts`) plus a `candidate_info.json` per candidate. Wired into `createCandidate` and
`updateCandidate` (`dataService.ts`) and `createPayment` (`paymentService.ts`): any `*Data` field
still starting with `data:` is intercepted and swapped for a URL. Backfill is
`scripts/clean-supabase-base64.js`, with a near-twin `scripts/sync-candidate-documents.js`; it has
run — 212 candidate folders and 212 info JSONs exist, holding only 5 real documents.
`public/uploads/candidates/*` is gitignored.

Dossier: `src/lib/dossierPdf.ts` is still the single renderer — `/api/candidates/[id]/dossier` serves
the server-side HTML, `downloadCandidateDossierPdf()` builds the PDF client-side (`jspdf` plus
`html2canvas`), dual Office Copy / Agent Copy on one A4. `f995590` reworked the layout (balanced top
margin, aligned header meta, 5-column profile card, fixed-width short signature lines, Remarks
column) and added `parseDocStatusAndRemarks()`, which splits one free-text field into a controlled
Status (Law Firm / Office / Embassy / DHL / designated country) plus remarks. `7de5114` renamed the
second partition badge AGENCY COPY to AGENT COPY. QR is now black on white at 240px with
`errorCorrectionLevel: 'M'`; the client canvas exports PNG instead of JPEG 0.95.

Verification 2026-11-19 at `7de5114`: `npx tsc --noEmit` exits 0. No `npm run build` re-run.

## Decisions

- 2026-10-25 — Supabase Postgres via Prisma for the initial build.
- 2026-10-27 — Runtime data access moved off Prisma onto the Supabase JS REST client; Prisma kept for
  seed/CLI only. Reason: the generated client and native binaries hurt the standalone deploy target.
  Do not reintroduce `@prisma/client` into shared or client modules.
- 2026-10-27 — Deploy target is a VPS/cPanel-style host via `output: "standalone"` plus
  `scripts/prepare-deploy.js` producing `deploy.zip`.
- 2026-11-10 — Auth is Supabase Auth, not hand-rolled. Role and `agentId` live in `app_metadata`
  (client-unwritable), `user_metadata` is display only. The proxy refreshes cookies and redirects
  only — each route handler verifies the session. Two clients: user-scoped for requests,
  service-role for auth admin only.
- 2026-11-18 — System roles replaced fixed role checks with a permission-key matrix plus custom
  roles, so ops can grant narrow access without a code change.
- 2026-11-18 — One dossier template drives both the print route and the client PDF download.
- 2026-11-19 — Candidate documents and receipts moved from base64-in-Postgres to disk under
  `public/uploads`, with only the public URL kept in the DB. Reason: blobs bloated every candidate
  row and every list query.
- 2026-11-19 — Disk layout is one folder per candidate keyed `${sl}_${passportNumber}` with one
  numbered category subfolder each, so a file is findable by hand without the app.
- 2026-11-19 — Dossier canvas exports PNG, not JPEG 0.95. Reason: JPEG ringing on the QR code and
  hairline rules.
- 2026-11-19 — Document status split into a controlled Status plus free-text Remarks. Reason: one
  field was doing both jobs and overflowing the column.

## Open questions

- Every uploaded passport/PCC/receipt — and `candidate_info.json`, which carries name, passport
  number, agent and lawyer — now sits at an unauthenticated, guessable `/uploads/...` URL. Accept
  that, or move the tree behind an authed route?
- Did `clean-supabase-base64.js` finish against the live DB? Only 5 real documents exist on disk
  across 212 candidates; confirm no Candidate/Payment row still holds a `data:` URL and that no
  upload was dropped.
- Deployment host for `deploy.zip` — which box, and is it still live? The zip carries `.env` with the
  service-role key.
- Are the new tables and columns actually applied to the live Supabase project? `prisma/schema.prisma`
  is documentation now — PostgREST is the runtime, so a missing column fails at request time.
- RLS is off on the original three tables and unaudited on the new ones. Which policies, and do they
  land before or after the `sb_publishable_` / `sb_secret_` key switch?
- Are the 21 agencies correct, or is the true partner list the 17 in the README?

## Next steps

Worst-first. Items 5-7 predate `bde787f` and are still open.

1. **Documents are publicly fetchable.** `/uploads/candidates/<sl>_<passport>/...` is served straight
   from `public/` with no auth, and each folder's `candidate_info.json` leaks name, passport number,
   status, agent and lawyer. Move the tree out of `public/` behind an authed route handler, or accept
   it explicitly and stop writing `candidate_info.json`.
2. **Requests still reach the database as the service role.** `dataService.ts:13` and
   `src/lib/supabase.ts` prefer `SUPABASE_SERVICE_ROLE_KEY`, so the layer under the guards bypasses
   RLS. Run request-path reads as the signed-in user, then write policies to match.
3. **A redeploy can wipe uploaded documents.** `prepare-deploy.js` copies local `public/` into
   `.next/standalone` and tars it; anything uploaded on the host since the last local build is
   overwritten when the new zip is unpacked. Exclude `public/uploads` from the artifact and persist
   it outside the app directory.
4. **Public unguarded dossier.** `/verify/<id>` and `/api/candidates/[id]/dossier` skip
   `requireUser()`; both return the full record. Decide the public contract, then redact or guard.
5. **Unvalidated writes.** `PATCH /api/candidates/[id]` has no zod schema, so `sl`, `agentId`,
   `stage`, `lawyerId` are mass-assignable; `batchUpdateCandidates` never recomputes `stage` for
   MARK_PASSPORT_IN_HAND / MARK_PCC_RECEIVED; `dataService.ts:95,97` interpolate raw search into
   `query.or(...)`, so a `,` or `)` rewrites the filter expression.
6. **Three dashboard metrics measure the wrong thing** (`dataService.ts:886–888`):
   `missingPassportsApproved` ignores `approval`; `pendingOver30Days` has no date comparison;
   `inReview` is just `submitted − approved`.
7. **Agency hygiene and `max+1` serials.** `resolveAgent` substring matching mints duplicate agencies
   on spelling drift; agency delete reassigns to an arbitrary agency instead of Direct Intake;
   `approvalCity` is written before approval so the Insights city split over-counts; `sl` is
   `max+1` against a unique constraint.


## Key paths and commands

```bash
cd "/e/My Projects/Skybridge Portal"     # E:\My Projects\Skybridge Portal
npm run dev                              # localhost:3000
npx tsc --noEmit                         # typecheck — clean at 7de5114
npm run build                            # prod build; output:standalone
node check-count.js                      # live row counts via Prisma (read-only)
node scripts/clean-supabase-base64.js    # one-time backfill: base64 to disk, DB keeps URLs
node scripts/prepare-deploy.js           # builds deploy.zip — copies .env and public/ inside
```

24 route handlers under `src/app/api/` — `auth/{login,logout,me}`, `candidates` (+`[id]`,
`[id]/dossier`, `batch`), `agents`, `lawyers`, `payments`, `roles`, `users` (all +`[id]`),
`activity-logs` (+`[id]/approve`), `dashboard/metrics`, `export`, `seed`, `setup` — plus the page
route `verify/[id]`.

Auth map: `src/lib/auth/{session,guards,types,permissions,audit,agency}.ts`,
`src/lib/supabase/{server,admin}.ts` (user-scoped vs service-role), `src/proxy.ts` (cookie refresh and
redirect only), `src/components/{AuthShell,LoginForm,SetupForm,UserManagement}.tsx`.
Data flow: `src/app/page.tsx` holds all state → `src/components/*` (props down) → `src/app/api/*` →
`src/lib/dataService.ts` and `paymentService.ts` (the only files touching data) → Supabase REST.

## Gotchas

- **Uploads live inside `public/`, which is also the deploy artifact.** Gitignored but present in the
  working tree, so a local build plus `prepare-deploy.js` bakes whatever is on this machine into
  `deploy.zip`; server-side uploads are not the source of truth for a redeploy.
- **The upload tree is public PII.** Folders are keyed `${sl}_${passportNumber}` and each holds a
  `candidate_info.json` with name, passport number, status, agent and lawyer — all fetchable with no
  auth. Correcting a passport also routes later uploads to a new folder, stranding the old one.
- **`documentStorage.ts` writes before the DB insert** in `createCandidate`, so a rejected insert
  leaves orphan folders. `clean-supabase-base64.js` and `sync-candidate-documents.js` are
  copy-pasted twins (identical `DOCUMENT_MAPPING`) — the same drift hazard as `AGENT_MAPPING`.
- **Next 16 is not the Next you know.** `AGENTS.md` warns the APIs/conventions differ from training
  data and to read `node_modules/next/dist/docs/` first. `cacheComponents` and
  `partialPrefetching` are both on.
- **The service-role key is reachable from the request path** (`dataService.ts:13`,
  `src/lib/supabase.ts:5`). The admin client is the only intended holder; any other use is a bug.
- **The stage rule is duplicated in ~4 places** (`createCandidate`, `updateCandidate` twice,
  `batchUpdateCandidates`): approval plus both flags gives DEPLOYMENT_READY, else APPROVED, else a
  submission slip gives SUBMITTED, else INTAKE. Change one, change all.
- **`AuditLog.id` has no DB default** — Prisma's `@default(cuid())` is client-generated, so the
  column is `text NOT NULL` with no default; a PostgREST insert must supply its id or fail, and the
  audit writer swallows the error. `Payment`, `CustomRole`, `Lawyer` behave the same way.
- **Supabase connector is project-scoped.** Label `supabase_noir-lavish`; only `bombegnoifzrchgqdqwv`.
  `LIST_ALL_PROJECTS` returns 403 — that needs a Personal Access Token. The SQL tool writes despite
  its read-only flag. Keys retire by end of 2026: `anon` / `service_role` →
  `sb_publishable_...` (RLS applies) and `sb_secret_...` (bypasses RLS).
- **git-bash quirks.** Path translation is off for native binaries (`node /tmp/x.js` resolves to
  `E:\tmp\x.js`) — use forward-slash native paths or `$LOCALAPPDATA/Temp`. MSYS also rewrites
  `//PID`-style switches, so stopping the dev server needs `cmd //c`.
