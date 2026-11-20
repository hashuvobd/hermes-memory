# AASH API

- **Slug:** `aash-api`
- **Status:** active
- **Started:** 2026-11 (repo history begins 2026-11-05)
- **Last touched:** 2026-11-20 — Code Mode sandbox added (uncommitted): isolated V8 VM with fetch, aash.search/browserPreview/now, Buffer/URL; exposed via MCP `code_mode_execute` and intercepted in chat-completions; `codeModeService.ts` new; system prompt updated; security audit committed (`51e9f43`, == `origin/main`, uncommitted work in 8 files + 1 new)
- **Repo / location:** `E:\My Projects\AASH API` (Windows, bash/MSYS view `/e/My Projects/AASH API`) · https://github.com/hashuvobd/AASH-API · deployed https://aash-api.vercel.app
- **Stack:** Next.js 15 (App Router, Turbopack), React 19, TypeScript, Tailwind 3, Supabase (Postgres + Auth, `@supabase/ssr`), Vercel. Added since 2026-11-10: `@vercel/analytics`.

## Resume here (2026-11-20)

**Where it stopped.** HEAD `51e9f43` == `origin/main`, but the worktree is **dirty**: Code Mode work started ~21:39 and was never committed (8 modified files +203/−46, plus new `src/lib/gateway/codeModeService.ts`). `next build` exit 0 was verified on the *committed* HEAD only — the dirty tree is unbuilt and unverified.

**Code Mode (uncommitted, this is the next thing to finish).** `codeModeService.ts` (237 lines) runs model-written JS/TS in a `node:vm` context: 1–15 s timeout (default 8 s), console capture, a `fetch` wrapper allowing only `http(s):` with a 10 s abort, and `aash.{search,browserPreview,now,context}`. Wired in three places, mirroring the browser engine: the MCP `code_mode_execute` tool, `handleGatewayCodeModeToolCall` in `/v1/chat/completions` (forces a non-streaming upstream fetch when the tool set includes it, then re-issues the follow-up completion), and `executeMcpToolCall` step 2 in `agentMiddleware.ts`. System prompt section 4 was rewritten to advertise it. Five alias names (`code_mode`, `codemode`, `execute_code`, `run_code`) resolve to the same handler.
- **Not wired into `/v1/messages`** — Anthropic-protocol clients get the tool in their schema but no interception, so the call goes upstream instead of executing.
- Six page files (`admin/alerts`, `admin/{skills,plugins}`, `dashboard/{skills,plugins}`) only lose header badges — cosmetic, unrelated to Code Mode.

**Landed since `f4c3de4`:**
- **Server-side browser engine** (new `browserService.ts`): `executeBrowserPreview({url|html,width,height})` resolves a system Chrome/Edge binary from fixed Windows/macOS/Linux paths, runs `execFile --headless=new --no-sandbox --screenshot=… <url>` (15s timeout, no shell), returns a base64 PNG plus a 3 000-char DOM summary. Wired in three places: the MCP `browser_preview`/`browser_screenshot` tools, the chat-completions tool intercept (`isBrowserToolCall`), and `executeMcpToolCall` in `agentMiddleware.ts`. Admin MCP list synthesizes an "AASH Built-in Headless Browser Engine" row (`admin.ts:getMcpServers`).
- **Autonomous MCP tool interception** — the gateway executes tool calls itself; directives were softened (`a1ffb37`) so a model lacking browser access adapts instead of halting.
- **Tool function-name normalization** (`443cefa`→`893f745`, four commits): every name coerced to `^[a-zA-Z0-9_-]{1,64}$` and deduplicated (`_2`, `_3`) inside `normalizeUpstreamPayload`, with round-trip mapping to the caller's original names — rationale in Decisions.
- **`stream_options`** is deleted whenever `stream` is falsy, for all providers, not only Cloudflare (`d8b12bf`).
- **Multimodal cascade** (`5401510`): tool-result images are detected recursively and an upstream 400 from a text-only primary auto-cascades to the multimodal fallback. `router.ts` picks the fallback channel with `.neq("status","disabled")` instead of `.eq("status","healthy")`.
- **Identity attribution split** (`7c06abd`, plus a `gemma` family in `d8b12bf`): `detectFamilyLoose()`/`familyTokenPattern()` identify a family from a slug (`gemma-4-31b-it` → Google) for `owned_by` and persona; `detectFamily()`/`tokenPattern()` still build replacements, so `gemma-cli` is untouched. Scrubbing semantics unchanged.
- **Model catalogue** (both `/v1/models` at `src/app/v1` and `src/app/api/v1`): 60s in-process cache, `?limit`/`?offset`, 503 `catalog_unavailable` on a failed DB read, `Cache-Control: public, s-maxage=60, stale-while-revalidate=300`. Vision is advertised only when the multimodal fallback channel is enabled *and* its provider is in `VISION_CAPABLE_PROVIDERS` (openai/anthropic/google) or the upstream model is a known vision model.
- **Security audit committed** — `SECURITY-AUDIT-FINDINGS.txt`; see the audit section below.

**Next Steps:**
1. **Finish and commit Code Mode.** It is uncommitted and unverified by `next build`; `/v1/messages` interception is missing (see Resume here).
2. **None of the audit findings is fixed in code.** `save_soul`/`save_memory` on `/api/mcp` still pass `undefined` (`route.ts:403,422`), landing on the global keys at `agentMiddleware.ts:610`/`:997`. Code Mode widened the same unauthenticated surface: `code_mode_execute` on that endpoint now lets any caller run code with outbound `fetch` — a new SSRF/execution path that the 2026-11-20 audit did **not** cover (it audited `d8b12bf`, before this work).
3. Deploy `51e9f43` to Vercel (manual, dashboard) and live-verify: browser tool round-trip, tool-name normalization against a strict upstream, multimodal 400 cascade.
4. Router same-pool failover defect: still open.

## Security audit (2026-11-20) — committed, unfixed

`SECURITY-AUDIT-FINDINGS.txt` (in-repo, 423 lines) is a source-only audit of worktree `d8b12bf` (Cloudflare security-audit skill, `standard` profile). No target code was built, run or probed — that host has no OS-enforced sandbox. Full artifacts: `C:\Users\Shuvo\security-audit-skill\aash-api\run-1\`. **Re-verified against this repo during the project-memory pass; every finding still stands at `51e9f43`.**

Three CRITICAL, each independently sufficient for platform compromise:
1. `POST /api/mcp` performs **no authentication**; its `save_soul`/`save_memory` tools pass an undefined user id, which resolves to the PLATFORM-WIDE keys (`agentMiddleware.ts:610`, `:997`) that are concatenated into every user's system prompt.
2. `getAuthUser()` (`src/utils/supabase/server.ts:47`) falls back to an unverified cookie/session identity (its steps 2 and 3); the 12 consumers then query with the service-role client, so a forged cookie yields server-side identity for any user id.
3. `POST /api/auth/sync` (`:43-61`) discards the `setSession` result and sets `is_admin:true` from an email string taken from the **request body**; `profiles.email` has no unique constraint.

HIGH: admin authorization by unverified email; unauthenticated SSRF (`fetch_web_page`) with response exfiltration; any API-key holder can proxy into the gateway's own network; a headless browser launched from caller input with `--no-sandbox` and `file://` admitted. MEDIUM: unauthenticated writes into the gateway audit log with caller-supplied request bodies. LOW: intercepted requests never call `recordGatewayUsage`; query-string API keys plus a 14-char key prefix written to stdout.

`NEEDS-VALIDATION` items are environment facts, not code defects: Chrome presence in the runtime, egress policy, whether the platform strips inbound `x-forwarded-host`, any deployed non-prod `NODE_ENV`, out-of-migration unique index on `profiles.email`, model resistance to injected globals.

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
- **MCP** — `src/app/api/mcp/route.ts` is a serverless MCP endpoint exposing built-in `web_search`, `fetch_web_page`, `get_current_time`, `calculate`, `browser_preview`, `browser_screenshot`; remote servers + synced tools live in `mcp_servers` and reach the model through `applyAgenticHarness`. **No authentication on POST** — audit finding 1.
- **Support helpdesk + AI auto-responder** — `support_tickets`/`support_messages` with RLS (`20261115_pending_sync.sql`), `src/lib/support/ai.ts`, `src/app/actions/support.ts` (`generateSupportReply`), `src/app/admin/support/page.tsx`; uses `next after` so the promise survives in serverless (`cc83b62`).
- **Soul & memory** — Agent Soul "soul.md" lives in `platform_settings` (**not** a disk file), global precedence over user soul, admin-only anti-hallucination, per-user isolation, in-chat memory CRUD, first-turn calibration. `agentMiddleware.ts` grew to ~2.2k lines and carries all of it.
- **Admin/dashboard** — logs page pagination + status/model/timeframe filters (`4cfcac6`); PostgREST 1000-row truncation fixed in admin and user stats (`99811f3`); Providers unified into one pool with N-tier failover + auto-quarantine (`aa23289`, `c40cb1c`); new AASH API emblem/favicons; notification toasts removed app-wide.
- **Schema to run by hand** — `supabase/migrations/20261115_pending_sync.sql` (Supabase SQL editor): adds `model_routes.{fallback_targets,rotate_on_request,multimodal_fallback_channel_id,multimodal_fallback_model_name}` and the two support tables with RLS.

## Decisions

- 2026-11-20 — **Code Mode sandbox added (uncommitted).** `src/lib/gateway/codeModeService.ts` provides an isolated V8 execution environment for model-written code. Exposed as the MCP `code_mode_execute` tool and intercepted in `/v1/chat/completions`. **Not yet wired into `/v1/messages`** — the tool is advertised in the schema but no interception exists there, so Anthropic-protocol clients will forward the call upstream instead of executing locally.
- 2026-11-20 — Tool function names are normalized at exactly one choke point, `normalizeUpstreamPayload` (`upstream.ts`), for every provider: renamed to `^[a-zA-Z0-9_-]{1,64}$`, deduplicated, and re-mapped back to the caller's original names on the response. Fixing this per-endpoint had already produced four separate 400 reports (`443cefa`, `81bd6eb`, `893f745`).
- 2026-11-20 — The browser engine ships with `--no-sandbox` and admits `file://`, and the MCP endpoint that exposes it has no auth. Recorded as HIGH in the committed audit and **deliberately left unfixed** for now; do not treat it as reviewed-and-cleared.
- 2026-11-20 — Identity *attribution* and identity *scrubbing* now use different matchers (`detectFamilyLoose`/`familyTokenPattern` vs `detectFamily`/`tokenPattern`). One strict matcher for both meant every slugged name reported `owned_by: aash-api`; the split lets `gemma-4-31b-it` attribute to Google while `gemma-cli` stays unrewritten (`7c06abd`).
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
- No pen-test exists for the pool/isolation model. A source-only audit does exist now (`SECURITY-AUDIT-FINDINGS.txt`) but it was never executed against a running deployment.
- The audit's three CRITICAL findings are structural, not cosmetic: any unauthenticated caller can rewrite the platform-wide system prompt, forge identity via the auth cookie, or promote themselves to admin. Fixing the `/v1` surface without fixing these leaves the platform open.

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
- `src/lib/gateway/upstream.ts`          # per-provider dispatch, payload normalization, tool-name choke point
- `src/lib/gateway/browserService.ts`    # headless Chrome/Edge runner (audit finding 7)
- `src/lib/gateway/codeModeService.ts`    # V8 code-mode sandbox — uncommitted, no auth in front of it
- `src/lib/providers/discovery.ts`       # inference health check requirements
- `src/app/v1/{chat/completions,messages,agent/run,models}/route.ts` (multimodal auto-delegation, inference health checks, 60s catalogue cache, tool-call intercept)
- `src/app/api/mcp/route.ts`             # serverless MCP endpoint — POST has no auth (audit finding 1)
- `src/app/api/auth/sync/route.ts`       # admin promotion from a request-body email (audit finding 3)
- `src/utils/supabase/server.ts`         # getAuthUser() unverified cookie fallback (audit finding 2)
- `SECURITY-AUDIT-FINDINGS.txt`          # committed source-only audit, 2026-11-20 (unfixed)
- `supabase/migrations/`                  # 20261115_pending_sync.sql = support + route columns
```

## Gotchas

- **The 1000-row trap:** PostgREST caps a response at 1000 rows, so unbounded count/aggregate queries truncate silently. Fixed in the stats actions (`99811f3`) — keep pagination or `.count()` on any new aggregate.
- `provider` + `base_url` define the routing pool, not the model. For `custom`, every Cloudflare channel shares one pool and one account quota. Free tier = 10,000 neurons/day; exhaustion is HTTP 429 `4006`.
- Strict upstreams reject a tool name outside `^[a-zA-Z0-9_-]{1,64}$` and reject duplicate names. Both are handled in `normalizeUpstreamPayload`; never inject a raw caller name further down.
- `stream_options` with `stream:false` is a 400 on OpenAI, DeepSeek, Groq, Together and vLLM — stripped for all providers, not just Cloudflare.
- `/api/mcp` and its built-in tools (including the headless browser and the two soul/memory writers) require no credential. Anything added to `BUILTIN_TOOLS` is anonymously reachable until that is fixed.
- Cloudflare: the catalog is `GET .../accounts/{id}/ai/models/search` (the obvious `/ai/v1/models` returns 405); error text is at `errors[0].message`; the account id is embedded in the base URL, so it is part of the credential bundle.
- The stream scrubber holds back up to (longest source token − 1) chars, so a long upstream id lags ~25 chars behind real time; `flush()` at the finish boundary releases the remainder.
- These files may be CRLF on disk; `read_file` normalizes it, so string anchors containing `\n` can fail silently. Normalize with `.replace("\r\n","\n")` and write `newline="\n"`.
- `grep` over `src/components/*.tsx` returns huge inlined marketing SVGs — search narrowly.
- Saving a channel is not gated by the connection test; a red test never blocks a working config.
