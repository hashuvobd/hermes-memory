---
name: llm-provider-integration
description: "Use when wiring or debugging a provider in an LLM gateway."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [providers, gateway, openai-compatible, verification, debugging, cloudflare]
---

# Wiring Providers Into an LLM Gateway

## When to Use

- Adding a provider key, preset, or route to an LLM gateway, router, or aggregator (the user's own app, LiteLLM, one-api, Portkey, Hermes' provider pool).
- A "connection test failed", "credential verification failed", 401/404/405, or an empty model picker for a provider that works in curl.
- Writing the provider-adapter layer: discovery, health probe, model catalog, auth headers.

## Step 0 — establish whose code owns the failing test

A provider-key modal can belong to the user's own product, a third-party gateway, or the agent app you happen to be running in. **Ask or confirm before reading source.** Digging through the host app's repo produces confident advice about a codebase the user does not own, and they will have to correct you. One question — "is this your gateway or the app's dashboard?" — costs nothing.

## Step 1 — probe provider-vs-gateway out of the way first

Hit the provider directly with curl before blaming either side. **Probe unauthenticated first**: on most edge gateways method/route resolution runs *before* auth, so the response still separates the cases:

| Response | Means |
|---|---|
| route/not-found error (404, `could not route`) | URL path is wrong — fix the base URL |
| method-not-supported (405) | Route missing/verb wrong — **the host is reachable**, so this is not a credential or network fault |
| auth error (401/403, missing-header codes) | Route exists, credentials or scopes are the issue |
| 200 | Discovery works; look at the payload shape next |

An unauthenticated probe is still diagnostic, so you never need the user's key to make progress.

## Step 2 — treat discovery, inference, and auth as three separate capabilities

Every OpenAI-compatible provider must answer two different questions, and many answer only one:

- **Discovery**: `GET {base}/models` — optional. The OpenAI-compat spec does not require it.
- **Inference**: `POST {base}/chat/completions` — the thing that actually matters.
- **Auth**: proven only by a request that got past routing.

A verifier built on discovery alone will reject providers that only support inference. That is the single most common false failure when adding a non-OpenAI vendor.

## Step 3 — the discovery URL is not always `base_url + /models`

Keep `base_url` inference-only in the provider record and make `discovery_url` a separate optional field. Vendors that scope endpoints by account id (path-embedded account/project ids) commonly put discovery on a **sibling** path one level up from the inference prefix. See `references/cloudflare-workers-ai.md` for a verified example.

Implement it as **one resolver** — `{provider, baseUrl, apiKey} → {kind, url, headers}` — that every caller goes through. A gateway grows several verification paths (the admin "test connection" button, the row-level ping, the background health check), and if each one hardcodes `{base}/models`, fixing one leaves the others quarantining a perfectly healthy channel. Before declaring the fix done, grep the repo for every site that builds a `/models` URL and confirm none is left.

## Step 4 — fall back to a real completion as the health probe

When a provider has no discovery endpoint, verify with `POST {base}/chat/completions`, `max_tokens: 1`, cheapest known model. One call proves token validity, model access, and streaming-free plumbing. Use `scripts/probe_provider.sh` to run discovery + root + completion probes in one pass.

## Step 5 — classify before recommending

Before suggesting any fix, say which of these it is:

1. **Path bug** — 404/405/route error. The key was never examined.
2. **Auth/scope** — 401/403 or a vendor auth code. Fix the token, not the URL.
3. **No discovery** — 405/7001-style verb error, or 200 with an empty list. Provider is fine; the gateway needs a static catalog or a completion-based probe.
4. **Shim mismatch** — provider serves only a subset of OpenAI surface (chat yes; models/tools/json-mode no).

## Pitfalls

- **Never tell the user to rotate or re-scope a key on evidence produced before auth was checked.** A 405 arrives without ever reading the Authorization header; rotating burns a credential for nothing and hides the real bug.
- **A method error is not an outage.** 405 means reachable-and-wrong-path. Do not report it as blocked, rate-limited, or a WAF problem.
- **Don't confuse the compat shim with the vendor's native API.** Chat may work on `/v1/...` while JSON mode, tool calling, reranking, or binary output exist only on the native run path with a different body shape. State which surface you are recommending.
- **Respect model-id namespaces.** `@cf/...`, `openai/...`, `anthropic/...` prefixes are part of the id; stripping or re-normalising them breaks routing.
- **Derive a client-facing model id from the display name, never by slugifying the upstream id.** Slugifying `@cf/qwen/qwen3.8-27b` produces `-cf-qwen-qwen3.8-27b` — the namespace separator turns into a stray leading hyphen and the id stops tracking what the admin actually sees on screen. Slugify the display name, keep dots (they match conventions like `gemini-2.5-flash`), and let manual typing in the field become an explicit override of the derivation. Reset that override flag when the form opens for a new route and set it when editing an existing one, so a stored id is never silently rewritten underneath a live client.
- **Check whether the failure blocks saving.** Verification-only failures usually leave the provider usable if the model is set explicitly; say so instead of presenting the modal error as fatal.
- **A failed probe is not proof the token is bad** — say what the test did and did not exercise.
- **Read the provider's error envelope before stringifying it.** OpenAI uses `error.message`, Cloudflare uses `errors[0].{code,message}`, and many proxies use a bare `message`. Parse all three, or the real cause is buried in a JSON blob.
- **Never let a missing discovery route quarantine a working channel.** Health checks that fail on 404/405 will take a perfectly good provider out of rotation; treat "no model list" as reachable, and verify with a 1-token completion instead.
- **Route creation must be opt-in, not automatic.** A provider key modal that imports models should only record them in that provider's catalog (`channel_imported_models_*` or equivalent). Client-facing routes (`model_routes`, virtual aliases) are only created when the caller explicitly requests them — e.g. the Models & Routing page's "Import All Discovered Models" action. Auto-creating routes on import pollutes the routing table with unvetted entries and conflates catalog management with route management.
- **Terminology matters: "Import" ≠ "Publish".** Use "Import" / "Imported" for recording models into a provider's local catalog, and "Create Route" / "Route" for making a model addressable by clients. Mixing them ("Publish Selected" when only importing) hides the fact that no route was created and misleads the admin about system state.
- **Normalize tool shapes before forwarding — never assume one tool format.** A gateway handler translating Anthropic tools to OpenAI tools receives `enhancedTools` that mixes client-sent Anthropic-shaped tools (`{name, description, input_schema}`) with MCP/OpenAI-shaped tools (`{type: "function", function: {name}}`) injected by the agentic harness. Mapping Anthropic field names (`t.name`, `t.input_schema`) over OpenAI-shaped entries yields `function.name: undefined`, which `JSON.stringify` drops entirely, and upstream OpenAI validators reject the nameless stub with `missing field 'function.name'`. Pass OpenAI-shaped entries through unchanged, convert Anthropic-shaped ones, and drop any entry still missing `function.name` before the upstream request. Verify with `tsc --noEmit`, then against the real function rather than a re-typed copy: compile the module on its own — a throwaway `tsconfig.json` whose `files` holds the absolute path, `noEmit: false`, an `outDir` — and run node assertions over both tool shapes plus nameless stubs; confirm every forwarded entry carries `function.name` and nothing null or nameless survives.

- **Mask upstream base model identity — never let the provider's model answer "who are you?"** An upstream base model (Qwen, GPT, Claude, Gemini, DeepSeek, Llama, Mistral…) answers identity questions with its own name instead of the routed public model name. Layers 1 and 2 fix that: a hard identity-lock directive in the gateway system prompt, plus a deterministic intercept that answers identity probes ("what is your name", "who made you", "are you Qwen") from the gateway itself so the upstream never handles those turns. Apply to both OpenAI (`/v1/chat/completions`) and Anthropic (`/v1/messages`), streaming and non-streaming.
- **The prompt lock and intercept only cover direct probes — add a third, deterministic layer that rewrites the response body.** A base model will volunteer its real name inside an otherwise unrelated long answer ("I'm Qwen, developed by Alibaba Group"), which no amount of prompt phrasing reliably stops. Scrub every response before it leaves the gateway: replace the upstream model id plus its vendor/family aliases with the route's display name. This must be chunk-safe for streams — see `references/identity-masking.md` for the holdback-buffer technique, the public-name sentinel, and the five stream edge cases that each break a live client.
- **Verify masking live on both wire formats with three probe shapes, not one.** A direct question ("what's your name"), a third-party framing ("are you Qwen?"), and a long unrelated prompt that gives the model room to introduce itself unprompted. The third is the only one that proves the response scrubber — the first two are already answered by the intercept and will pass even with layer 3 missing entirely. Check the streamed reasoning channel too, not just the final text.
- **Persist and log the scrubbed text, not the raw.** Cloud memory extraction and request logs both run off the response body; wiring the scrubber into the client path only still writes the real model name into the memory store and log table.
- **State the limit of textual masking instead of promising total secrecy.** Substitution cannot catch a model that paraphrases itself without naming a vendor ("a large language model built by a Chinese team"), and it *will* rewrite ordinary prose that mentions a vendor word ("Meta", "Google") on a route belonging to that family. That is the accepted cost of strictness — say so, and let the user decide per route.
- **Read a patched region back before moving on in a large route file.** In a 60–180 KB CRLF handler, a fuzzy block replacement can re-indent the block or swallow the closing brace of the enclosing `else if`, and the resulting diff still looks plausible. Re-read 10–30 lines around every edit or trust `tsc --noEmit` / `next build` to catch it before the next edit lands on corrupted structure. When a block resists two patch attempts, switch to an exact-string replacement from Python (`open(..., newline="")`, match the literal bytes that are actually there) instead of patching a third time — and never assume uniform line endings, because a region rewritten with `\n` inside an otherwise-CRLF file silently breaks every later `\r\n` match.

## References

- `references/cloudflare-workers-ai.md` — Workers AI endpoint map, error codes, and the discovery/inference split.
- `scripts/probe_provider.sh` — run the three probes against any base URL.
- `references/identity-masking.md` — three-layer identity masking: scrub-list construction, public-name sentinel, chunk-safe stream scrubber, hook points per wire format, and the verify-without-a-test-suite harness.
