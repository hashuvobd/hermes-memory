# AASH API

- **Slug:** `aash-api`
- **Status:** active
- **Started:** 2026-11 (repo history begins 2026-11-05)
- **Last touched:** 2026-11-20 — channel health checks upgraded to inference probes; multimodal capabilities now fully advertised and handled in router, upstream, and model catalog; intelligent cooldowns for channel quarantines; caching improved (`f4c3de4` + uncommitted)
- **Repo / location:** `E:\My Projects\AASH API` (Windows, bash/MSYS view `/e/My Projects/AASH API`) · https://github.com/hashuvobd/AASH-API · deployed https://aash-api.vercel.app
- **Stack:** Next.js 15 (App Router, Turbopack), React 19, TypeScript, Tailwind 3, Supabase (Postgres + Auth, `@supabase/ssr`), Vercel. Added since 2026-11-10: `@vercel/analytics`.

## Resume here (2026-11-20)

**Where it stopped.** Worktree dirty (uncommitted changes); HEAD `f4c3de4` == `origin/main` (5 new commits). `npx next build` → 0 and `npx tsc --noEmit -p tsconfig.json` → 0 on this HEAD — verified locally, **not live** (this run had no API key in the environment).

**Current state (f4c3de4 + uncommitted):**
- **Channel Health Checks**: Upgraded from simple catalog probes to inference probes for providers like Cloudflare Workers AI, where catalog checks don't reflect actual inference quota. This provides a more accurate `healthy`/`degraded`/`quarantined` status.
- **Intelligent Cooldowns**: `cooldownForFailure` introduced for channel quarantines, calculating longer cooldowns for daily quota exhaustion (e.g., until next UTC midnight) versus transient rate limits.
- **Multimodal Capabilities**:
    - Model catalog (`/v1/models`) now exposes detailed multimodal `modalities` and `architecture` information, including image MIME types.
    - Router, upstream, and completion endpoints (`/v1/chat/completions`, `/v1/messages`) now fully handle multimodal requests, including auto-delegation for text-only primary models to a multimodal fallback.
    - Upstream payload normalization (`upstream.ts`) now converts various image/file input formats into a strict OpenAI `image_url` schema.
    - Caching logic updated to *not* cache truncated or empty multimodal completions.
- **Channel Status Workflow**: Expired quarantines are now demoted to `degraded` (not `healthy`) to signify unproven status, and a real successful completion is the *only* path to promote a channel back to `healthy` (`promoteChannelHealthy`).
- **Model ID Compatibility**: `/v1/models` now emits both hyphenated and dotted versions of `model_id` for broader client compatibility (e.g., `llama-3-1-8b` and `llama-3.1-8b`).

**Next Steps:**
1. **Deployment and Live Verification**: Ensure `f4c3de4` (or later) + uncommitted changes are deployed to Vercel.
2. **Live-verify**: Test the new channel health system with a quota-exhausted Cloudflare channel. Verify multimodal auto-delegation.
3. **Router same-pool failover defect**: Still open, as noted below.

## Identity masking — current design (read before touching)

Three layers hide which model actually serves a route.

- **Layer 1 — system-prompt lock** (`agentMiddleware.ts`): forbids revealing the upstream base model/vendor. Since `07f2c15` it does **not** enumerate vendor names (naming them was itself a hint).
- **Layer 2 — identity intercept**: `detectIdentityQuestion()` in `identityProbe.ts` (split out so it is unit-testable) answers direct probes from the gateway, so the upstream never handles those turns. English, Bengali and Chinese pattern sets.
- **Layer 3 — response scrubber** (`identityScrubber.ts`, the only place text is rewritten):
  - `FAMILIES` table (claude/Anthropic, gpt/OpenAI, gemini/Google, qwen/Alibaba Cloud, llama/Meta, mistral, deepseek, grok) each carrying `modelTokens`, `creatorTokens` and the canonical `creator`.
  - `resolvePublicPersona(displayName)` → `{ modelName, creator, impersonates }`: display name matches a family ⇒ impersonate that family *including* its creator; otherwise ⇒ display name + creator `AASH API`. `slugifyClientId(name)` derives the admin Client ID from the display name.
  - Entry points: `scrubModelIdentity(text, opts)`, `createStreamScrubber(opts)` (stateful, chunk-safe), `scrubWirePayload(payload, opts)` (messages/choices/blocks).
  - **First-person-only (the 2026-11-20 redesign).** Replacement fires only inside a self-identity declaration: `selfModelPattern` ("I am Claude", "I'm Qwen", "আমি ক্লড", "我是通义千问"), `selfCreatorPattern` ("trained/created/developed/built by Anthropic"), `selfPlatformPattern` ("hosted on Cloudflare Workers AI"). Third-person mentions, route names, model lists and comparisons are deliberately preserved. Bare `cloudflare` and `@cf/` were dropped from `PLATFORM_TOKENS` in the same change.
  - Guards: `TECH_KEYWORD_GUARD` blocks a match followed by `code|cli|sdk|api|…` or a TLD (`claude code`, `openai sdk`, `api.anthropic.com`); a leading `(?<![/@._-])\b` prevents matches inside URLs, paths and scoped packages; `VERSION_TAIL` consumes `Qwen3-235B`/`sonnet`/`opus` whole.
  - Fails closed: platform/framework tokens and the base prompt's own `hermes agent`/`nous hermes` branding are masked on every response even when the upstream is unidentified. Since `2d38441` JSON bodies are scrubbed at a single choke point, and cache-HIT paths re-scrub.
- **Limit that remains:** matching is textual. A vendor-free self-description ("a Chinese open-weights model") is not caught; Layer 1 is the only defence for that phrasing.

## What landed since 2026-11-10

- **Agent harness** — `harnessLoop.ts` (Plan–Act–Verify–Self-Correct loop, `detectRepetitiveLoop` circuit breaker, context compaction), `contextSanitizer.ts`, and the new `/v1/agent/run` SSE endpoint. Wired into both `chat/completions` and `messages`, not only the new endpoint.
- **Skills & Plugins studios** — `src/lib/{skills,plugins}/{types,parser,defaults}.ts`, `src/app/actions/{skills,plugins}.ts`, admin + user pages, GitHub discovery via `src/lib/github/smartCrawler.ts`. Injected at runtime by `getActiveSkillsForGateway`/`getActivePluginsForGateway` inside `applyAgenticHarness`. Defaults ship Ponytail and Graphify. The two are strictly isolated from each other (`09af092`).
- **MCP** — `src/app/api/mcp/route.ts` is a serverless MCP endpoint exposing built-in `web_search`, `fetch_web_page`, `get_current_time`, `calculate`; remote servers + synced tools live in `mcp_servers` and reach the model through `applyAgenticHarness`.
- **Support helpdesk + AI auto-responder** — `support_tickets`/`support_messages` with RLS (`20261115_pending_sync.sql`), `src/lib/support/ai.ts`, `src/app/actions/support.ts` (`generateSupportReply`), `src/app/admin/support/page.tsx`; uses `next after` so the promise survives in serverless (`cc83b62`).
- **Soul & memory** — Agent Soul "soul.md" lives in `platform_settings` (**not** a disk file), global precedence over user soul, admin-only anti-hallucination, per-user isolation, in-chat memory CRUD, first-turn calibration. `agentMiddleware.ts` grew to ~2.2k lines and carries all of it.
- **Admin/dashboard** — logs page pagination + status/model/timeframe filters (`4cfcac6`); PostgREST 1000-row truncation fixed in admin and user stats (`99811f3`); Providers unified into one pool with N-tier failover + auto-quarantine (`aa23289`, `c40cb1c`); new AASH API emblem/favicons; notification toasts removed app-wide.
- **Schema to run by hand** — `supabase/migrations/20261115_pending_sync.sql` (Supabase SQL editor): adds `model_routes.{fallback_targets,rotate_on_request,multimodal_fallback_channel_id,multimodal_fallback_model_name}` and the two support tables with RLS.

## Decisions

- 2026-11-20 — Identity scrubbing is **first-person-only**. Blanket token replacement rewrote legitimate third-person text and was rolled out of production (`10f98d9`); restricting replacement to self-identity declarations plus `TECH_KEYWORD_GUARD` keeps masking without collateral damage. Cost: a model naming its vendor only in the third person now slips through.
- 2026-11-20 — `10f98d9` is an **empty commit**: it records a production rollback, not a code change. It does not revert the Nov 19 commits in history.
- 2026-11-19 — Errors are gateway-authored. `errorSanitizer.ts` unwraps the upstream envelope, strips uuids/URLs, scrubs identities and emits OpenAI- or Anthropic-shaped errors; quota/schema errors are neutral (`225a953`).
- 2026-11-19 — `6180da2`: a `\b` prefix made every CJK/Bengali alias dead code (CJK is not `\w`), so `\b` is now emitted only for ASCII-led tokens. The stream scrubber holds back to a proper-prefix boundary, so a token split across chunks cannot leak.
- 2026-11-18 — **Failover across providers is the missing piece (still open).** `router.ts` tries the same-provider pool first (narrowed by `base_url` for `custom`), so every Cloudflare channel shares one account quota; explicit cross-provider `route.fallback_targets` are reached only after a failed round-trip. A route's backup must be a different `provider`/account to survive quota exhaustion; nothing warns when a fallback shares the primary's pool.
- 2026-11-17 — `src/app/v1/messages/route.ts` (Anthropic→OpenAI) must normalize both tool shapes and drop stubs missing `function.name`, or upstream 400s.
- 2026-11-10 — Cloudflare model ids keep the `@cf/` namespace; resolve the upstream id by *shape* (namespaced wins, uuid loses) because Cloudflare puts an internal uuid in `id` and the real id in `name`. Discovery is resolved separately from `base_url`, and a 404/405 probe means "no model-list route", never a bad key. Model routes no longer auto-create on provider import (`batchRouteChannelModels({createRoutes:false})`).

## Open questions / known weaknesses

- Live `/v1/models` returns **two entries per route** (the `model_id` slug and the `display_name`), labelling one of each pair `owned_by` the impersonated creator — intentional, but confirm clients that dedupe by `id` tolerate it.
- `computeCacheKey` hashes model+messages+tools+system only, not the channel id: re-pointing a route at a new backend serves up to 24h of the old backend's cached output (stale, not a leak once scrubbing is on).
- Stale uuid-based imported models from before the shape fix still sit in `channel_imported_models_*` / `model_routes`; delete by hand or add a cleanup action.
- No pen-test exists for the pool/isolation model.

## Key paths and commands

```bash
cd "/e/My Projects/AASH API"       # git-bash/MSYS path form
npm run dev                         # next dev --turbopack
npm run build                       # next build — the real gate; tsc alone is not enough
npx tsc --noEmit -p tsconfig.json
```

Live probe (reads the key from an env var; never inline a key in a committed file):

```bash
BASE="https://aash-api.vercel.app"
curl -s -m 120 "$BASE/v1/chat/completions" -H "Authorization: Bearer $KEY" \
  -H "content-type: application/json" \
  -d '{"model":"claude-fable-5.2","messages":[{"role":"user","content":"Reply with exactly: OK"}],"max_tokens":40}' \
  -w '\nHTTP %{http_code}\n'
# Scrubber discriminator (old blanket scrubber vs new first-person-only):
#   "Output this exact string and nothing else: Qwen Alibaba Tongyi"
#     new -> raw vendor names return (third-person text preserved)
#     old -> rewritten to the display name
#   "I am Qwen, developed by Alibaba." must return the display name, and for an
#   impersonating name (e.g. Claude Fable 5.2) creator "Anthropic".
```

```text
- `src/lib/gateway/agentMiddleware.ts`   # harness, soul/memory, skills/plugins/MCP injection (~2.2k lines)
- `src/lib/gateway/identityScrubber.ts`  # Layer-3 masking + persona resolver
- `src/lib/gateway/identityProbe.ts`     # Layer-2 identity-question detector
- `src/lib/gateway/errorSanitizer.ts`    # gateway-authored error bodies
- `src/lib/gateway/harnessLoop.ts`       # Plan-Act-Verify loop
- `src/lib/gateway/router.ts`            # resolution + failover cascade (now includes multimodal detection + improved status handling)
- `src/lib/gateway/upstream.ts`          # per-provider dispatch (now includes strict OpenAI multipart normalization)
- `src/lib/providers/discovery.ts`       # inference health check requirements
- `src/app/v1/{chat/completions,messages,agent/run,models}/route.ts` (now includes multimodal auto-delegation, inference health checks, robust caching, detailed model capabilities)
- `src/app/api/mcp/route.ts`             # serverless MCP endpoint
- `src/app/actions/{admin,skills,plugins,support,user,userMiddleware}.ts` (admin includes new channel health check logic)
- `supabase/migrations/`                  # 20261115_pending_sync.sql = support + route columns
```

## Gotchas

- **The 1000-row trap:** PostgREST caps a response at 1000 rows, so unbounded count/aggregate queries truncate silently. Fixed in the stats actions (`99811f3`) — keep pagination or `.count()` on any new aggregate.
- `provider` + `base_url` define the routing pool, not the model. For `custom`, every Cloudflare channel shares one pool and one account quota. Free tier = 10,000 neurons/day; exhaustion is HTTP 429 `4006`.
- Cloudflare: the catalog is `GET .../accounts/{id}/ai/models/search` (the obvious `/ai/v1/models` returns 405); error text is at `errors[0].message`; the account id is embedded in the base URL, so it is part of the credential bundle.
- The stream scrubber holds back up to (longest source token − 1) chars, so a long upstream id lags ~25 chars behind real time; `flush()` at the finish boundary releases the remainder.
- These files may be CRLF on disk; `read_file` normalizes it, so string anchors containing `\n` can fail silently. Normalize with `.replace("\r\n","\n")` and write `newline="\n"`.
- `grep` over `src/components/*.tsx` returns huge inlined marketing SVGs — search narrowly.
- Saving a channel is not gated by the connection test; a red test never blocks a working config.
