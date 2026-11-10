# AASH API

- **Slug:** `aash-api`
- **Status:** active
- **Started:** 2026-11 (repo history begins 2026-11-05)
- **Last touched:** 2026-11-10
- **Repo / location:** `/home/shuvo/Projects/AASH-API` · https://github.com/hashuvobd/AASH-API
- **Stack:** Next.js 15 (App Router, Turbopack), React 19, TypeScript, Tailwind 3, Supabase (Postgres + Auth, server actions via `@supabase/ssr`), Vercel

## Goal

A commercial multi-provider AI gateway (aashapi.com): one API key and one monthly allowance in front of 50+ models. Speaks both OpenAI (`/v1/chat/completions`, `/v1/responses`) and Anthropic (`/v1/messages`) protocols so coding tools can point at it unchanged. Admin dashboard manages upstream provider keys, model routes, fallbacks and pricing.

## Current state

- Public marketing site, docs, model catalog, ranking, status page, dashboard (keys, usage, billing, logs) and admin panel all build and ship from this repo.
- Gateway routing works: `src/lib/gateway/{router,upstream,auth,caching,accounting,cors}.ts`. Upstream dispatch is a per-provider switch; `custom` channels post to `base_url + /chat/completions`.
- Provider channels live in Supabase `provider_channels` (name, provider, base_url, api_key, priority, weight, status, quarantine columns). Providers: google, anthropic, openai, groq, deepseek, openrouter, custom.
- Admin → Providers modal does live credential test + model discovery, bulk publish to routes, per-model live probe, row ping/health. Model routes support multi-model fallback cascades, drag-and-drop priority, round-robin combo mode, multimodal auto-delegation.
- 2026-11-10: Cloudflare Workers AI can now be added as a `custom` channel — discovery resolves to its real catalog endpoint (see Gotchas) and imported `@cf/...` models are classified by `task`.

## Decisions

- 2026-11-10 — Discovery is resolved separately from `base_url` (`src/lib/providers/discovery.ts`) instead of appending `/models` everywhere, because vendors scope catalogs to sibling paths (Cloudflare) and a single hardcoded probe produced false credential failures.
- 2026-11-10 — 404/405 from a discovery probe is treated as "no model list route", never as a bad key: HTTP routing/method resolution runs before auth, so the credential was never examined. Such channels are not quarantined.
- 2026-11-10 — Cloudflare model ids keep the `@cf/` namespace; never strip or re-prefix them, they are the routing key on both `/ai/v1` and `/ai/run`.

## Open questions

- Whether Cloudflare's `result[].name` is always `@cf/`-prefixed for every account (normaliser handles both shapes, but only a real fetch confirms it).
- Whether per-account Cloudflare "frontier models need paid billing" should surface as a separate tier tag rather than the generic free-tier tag.

## Next steps

1. Run Test Connection with a real Cloudflare token, then Publish Selected — confirm the imported ids land as `@cf/...` and a model test returns 200.
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
- `read_file`/grep over `src/components/*.tsx` returns huge minified marketing SVGs — search narrowly or you burn the context window.
- Saving a channel is not gated by the connection test, so a red test never blocks a working config.