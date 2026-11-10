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
- **Check whether the failure blocks saving.** Verification-only failures usually leave the provider usable if the model is set explicitly; say so instead of presenting the modal error as fatal.
- **A failed probe is not proof the token is bad** — say what the test did and did not exercise.
- **Read the provider's error envelope before stringifying it.** OpenAI uses `error.message`, Cloudflare uses `errors[0].{code,message}`, and many proxies use a bare `message`. Parse all three, or the real cause is buried in a JSON blob.
- **Never let a missing discovery route quarantine a working channel.** Health checks that fail on 404/405 will take a perfectly good provider out of rotation; treat "no model list" as reachable, and verify with a 1-token completion instead.

## References

- `references/cloudflare-workers-ai.md` — Workers AI endpoint map, error codes, and the discovery/inference split.
- `scripts/probe_provider.sh` — run the three probes against any base URL.
