# AASH API

- **Slug:** `aash-api`
- **Status:** active
- **Started:** 2026-11 (repo history begins 2026-11-05)
- **Last touched:** 2026-11-17 (discovery + uuid fix + import without auto-routes; Anthropic→OpenAI tool-translation 400 fix); 2026-11-18 (model identity masking, then strict response-level identity scrubbing + auto-derived client IDs — commit `e2a9e8f`)
- **Repo / location:** `/home/shuvo/Projects/AASH-API` · https://github.com/hashuvobd/AASH-API
- **Stack:** Next.js 15 (App Router, Turbopack), React 19, TypeScript, Tailwind 3, Supabase (Postgres + Auth, server actions via `@supabase/ssr`), Vercel

## Goal

A commercial multi-provider AI gateway (aashapi.com): one API key and one monthly allowance in front of 50+ models. Speaks both OpenAI (`/v1/chat/completions`, `/v1/responses`) and Anthropic (`/v1/messages`) protocols so coding tools can point at it unchanged. Admin dashboard manages upstream provider keys, model routes, fallbacks and pricing.

## Current state

- Public marketing site, docs, model catalog, ranking, status page, dashboard (keys, usage, billing, logs) and admin panel all build and ship from this repo.
- Gateway routing works: `src/lib/gateway/{router,upstream,auth,caching,accounting,cors}.ts`. Upstream dispatch is a per-provider switch; `custom` channels post to `base_url + /chat/completions`.
- Provider channels live in Supabase `provider_channels` (name, provider, base_url, api_key, priority, weight, status, quarantine columns). Providers: google, anthropic, openai, groq, deepseek, openrouter, custom.
- Admin → Providers modal does live credential test + model discovery, bulk publish to routes, per-model live probe, row ping/health. Model routes support multi-model fallback cascades, drag-and-drop priority, round-robin combo mode, multimodal auto-delegation.
- 2026-11-10: Cloudflare Workers AI works as a `custom` channel end to end — discovery hits its real catalog endpoint (see Gotchas), ids resolve to `@cf/...`, and models are classified by `task`.
- 2026-11-10: model import refuses opaque uuid ids and reports the skip count, after a first attempt published Cloudflare's internal uuids as upstream model names.
- 2026-11-10: **model routes no longer auto-create on provider import**. `batchRouteChannelModels` now takes `{createRoutes: false}` — the provider modal only records models in its catalog (`channel_imported_models_*`); the Models & Routing page's "Import All Discovered Models" is the explicit place to create live routes.
- **2026-11-10 (later):** Admin UI polish batch — status badge redesign across all admin pages (Providers, Models, Logs, Keys, Usage, Billing), filter/table alignment fixes on Logs page, dropdown menu positioning fixed to trigger on scroll, "9Router" branding removed from Models page, checkbox alignment fixes. Commits `345c200`–`c863e36`. Build passes, typecheck clean.

## Decisions

- 2026-11-10 — Discovery is resolved separately from `base_url` (`src/lib/providers/discovery.ts`) instead of appending `/models` everywhere, because vendors scope catalogs to sibling paths (Cloudflare) and a single hardcoded probe produced false credential failures.
- 2026-11-10 — 404/405 from a discovery probe is treated as "no model list route", never as a bad key: HTTP routing/method resolution runs before auth, so the credential was never examined. Such channels are not quarantined.
- 2026-11-10 — Cloudflare model ids keep the `@cf/` namespace; never strip or re-prefix them, they are the routing key on both `/ai/v1` and `/ai/run`.
- 2026-11-10 — Resolve the upstream id by SHAPE (namespaced `@...`/`vendor/model` wins, uuid-shaped loses), not by field name: Cloudflare puts an internal uuid in `id` and the real id in `name`, and the previous `m.id || m.name` silently stored the uuid (`5007 No such model`).
- 2026-11-17 — Fixed Anthropic→OpenAI tool translation 400 in `src/app/v1/messages/route.ts`: the mapper re-read Anthropic field names (`t.name`, `t.input_schema`) on OpenAI-shaped `enhancedTools` (MCP tools from `applyAgenticHarness`), emitting nameless `function` stubs that upstream OpenAI validators reject with `missing field 'function.name'`. The mapper now normalizes both Anthropic (`{name, input_schema}`) and OpenAI (`{type: "function", function: {name}}`) shapes and drops any stub still missing `function.name` before forwarding.
- 2026-11-18 — Model identity masking in `src/lib/gateway/agentMiddleware.ts`: added a hard "AASH IDENTITY LOCK" directive forbidding any revelation of upstream base model/vendor (Qwen, GPT, Claude, Anthropic, Gemini, DeepSeek, Llama, Mistral…) and a deterministic intercept that answers identity probes ("what is your name", "who made you", "are you Qwen", etc.) from the gateway itself as the routed public model, so the upstream model never handles those turns. Applies to both `/v1/chat/completions` and `/v1/messages`.

- 2026-11-18 — **Strict identity scrubbing (layer 3)** in the new `src/lib/gateway/identityScrubber.ts`. The system-prompt lock and the identity-question intercept only cover direct probes; a base model can still volunteer its real name inside an unrelated long answer. Every response body is now rewritten before it leaves the gateway: `scrubModelIdentity()` replaces the upstream model id plus its vendor/family aliases (Qwen/Alibaba/Tongyi, GPT/OpenAI, Claude/Anthropic, Gemini/Google, DeepSeek, Llama/Meta, Mistral) with `resolved.route.display_name`, and `createStreamScrubber()` does the same for SSE deltas with a holdback buffer as long as the longest forbidden string, so an identity split across chunks ("Qw"+"en") cannot leak. A protect-sentinel prevents double substitution when the public name itself contains a vendor word ("Claude" in "Claude Fable 5.2"). Wired into both non-streaming paths and all four stream transforms (`createAnthropicTransformStream`, `createNativeAnthropicTapStream`, `createOpenAIMaskStream`, `convertCompletionToSSEStream`); the native Anthropic tap also rewrites `message_start.message.model`.
- 2026-11-18 — **Client ID auto-derivation** in `src/app/admin/models/page.tsx`. The "Virtual Model Identifier (Client ID)" field now follows the Display Name through `slugifyClientId()` while `clientIdTouched` is false; typing in the field makes it an explicit override and clearing it re-syncs. Suggestion clicks derive from the suggestion's display name instead of its raw upstream id — that mismatch is what produced stray ids like `-cf-qwen-qwen3.8-27b`. Quick-route and new-route open in sync mode; editing an existing route preserves its stored id. Dots are kept in slugs to match the existing `gemini-2.5-flash` convention.

## Open questions

- Stale rows: channels imported before the uuid fix still hold uuid entries in `channel_imported_models_*` (platform_settings) and `model_routes`. They need deleting by hand, or a cleanup action.
- Whether Cloudflare's `result[].name` is always `@cf/`-prefixed for every account (normaliser handles both shapes, but only a real fetch confirms it). **Confirmed 2026-11-10:** 73 accessible / 39 eligible, names prefixed `@cf/`.
- Whether per-account Cloudflare "frontier models need paid billing" should surface as a separate tier tag rather than the generic free-tier tag.

## Next steps

1. Re-run Test Connection, delete the old uuid-based imported models, then Publish Selected — model tests should return 200ms-range latencies instead of `5007`.
2. Consider a first-class `cloudflare` provider option (auto-filled base URL from account id) instead of the `custom` dropdown, if more CF-specific behaviour appears.
3. Remaining manual-model path: when a provider has no discovery route the modal shows amber, but there is still no "add model id by hand" control — the only way in is discovery.

## Key paths and commands

```bash
cd /home/shuvo/Projects/AASH-API
npm run dev          # next dev --turbopack
npm run build        # next build (used as the typecheck gate; tsc --noEmit also clean)
npx tsc --noEmit -p tsconfig.json
```

```
src/app/actions/admin.ts          # all admin server actions (channel CRUD, discovery, health, tests)
src/lib/providers/discovery.ts    # discovery resolver: base_url → catalog request + normalisation
src/lib/gateway/upstream.ts       # per-provider upstream dispatch
src/app/admin/providers/page.tsx  # Add/Edit Provider modal + test/discovery UI
supabase/migrations/              # schema; 20261106_admin_gateway.sql holds the gateway tables
```

## Gotchas

- `testChannelConnection` and `pingChannel` (in `admin.ts`) both perform discovery; changing one without the other leaves the health check lying. They now share the resolver — keep it that way.
- Cloudflare: `GET {base}/ai/v1/models` → 405/`7001`, `GET {base}/ai/v1` → 404/`7003`, catalog is `GET .../accounts/{id}/ai/models/search` (array under `result`, total in `result_info.total_count`, classify by `task.name`). Cloudflare error text is at `errors[0].message`, not `error.message`.
- Cloudflare account id is embedded in the base URL path, so it is part of the credential bundle, not a global setting.
- Cloudflare search entries carry an internal **uuid in `id`** and the invocable id in `name` (`@cf/...`). Storing `id` gives `5007 No such model <uuid> or task` on every call — the exact failure that surfaced after the first discovery fix.
- `read_file`/grep over `src/components/*.tsx` returns huge minified marketing SVGs — search narrowly or you burn the context window.
- Saving a channel is not gated by the connection test, so a red test never blocks a working config.
- Identity scrubbing is textual, not semantic: a base model that describes itself without naming a vendor ("a large language model built by a Chinese team") still gets through. Matching is case-insensitive with word boundaries for single-word aliases, so "Meta"/"Google" appearing as ordinary prose also become the display name — that is the intended cost of strictness.
- The stream scrubber holds back up to (longest forbidden string − 1) chars, so a route pointing at a long upstream id (e.g. `claude-sonnet-4-5-20250929`, 26 chars) lags ~25 chars behind real time. `flush()` at the finish boundary and at stream end releases the remainder.