# Cloudflare Workers AI — endpoint map

Cloudflare is the clearest case of "OpenAI-compatible for inference, nothing else." Its inference prefix and its discovery endpoint are **siblings**, not nested.

## Endpoints

| Purpose | Request |
|---|---|
| Inference (OpenAI shim) | `POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1/chat/completions` |
| Embeddings (shim) | `POST .../accounts/{ACCOUNT_ID}/ai/v1/embeddings` |
| Responses (shim) | `POST .../accounts/{ACCOUNT_ID}/ai/v1/responses` |
| **Discovery** | `GET .../accounts/{ACCOUNT_ID}/ai/models/search` |
| Native run (full features) | `POST .../accounts/{ACCOUNT_ID}/ai/run/@cf/{model}` |

Auth: `Authorization: Bearer <API_TOKEN>` with **Workers AI: Read** (or Write). Global-key style `X-Auth-Email` + `X-Auth-Key` also accepted, listed as legacy.

`GET .../ai/models/search` query params: `search`, `task`, `page`, `per_page`, `include_deprecated`, `source`, and `format=openrouter` — the last one returns the catalog in marketplace shape, which is usually what an aggregator wants to store. Model ids come back namespaced `@cf/<vendor>/<model>`.

## Discovery payload

```
{ "success": true, "result": [ { "id": "f9f2250b-1048-4a52-9910-d0bf9f76…",
    "name": "@cf/meta/llama-3.1-8b-instruct",
    "task": { "id": "…", "name": "Text Generation" },
    "properties": [ { "property_id": "context_window", … } ] } ],
  "result_info": { "page": 1, "per_page": 200, "total_count": 87 } }
```

- **`id` is an internal uuid; `name` is the invocable `@cf/...` model id.** Storing `id` publishes routes that fail every inference with `5007 No such model <uuid> or task`. Pick the candidate that is namespaced (`@…` or `vendor/model`), reject uuid-shaped values, and never assume which field holds which — resolve it by shape, not by key.
- The array is under **`result`**, not `data`/`models` — an OpenAI-shaped parser finds nothing and reports "0 models".
- Page until `result_info.total_count` is collected; `per_page` is honoured but has a server-side ceiling, so never assume one page is the whole catalog.
- `task.name` is the only reliable classifier: `Text Generation` → chat, `Text Embeddings` → embedding, others image/audio. Only text generation should auto-enable as a chat route.
- Prefer the **default** shape over `format=openrouter` when you also need `task` and `properties`; the marketplace shape drops the classification you need for tier tags.

## Quota, deprecation, and why the catalog lies

The search endpoint and the inference endpoint draw on **different meters**, and this breaks any discovery-based health check:

- `GET .../ai/models/search` is free and unmetered — it answers `200` with the full catalog while the account can generate nothing at all.
- Inference bills **neurons** against a daily free allocation. When it is spent, every `POST .../chat/completions` answers `429` with `errors[0].code: 4006` and the text `you have used up your daily free allocation of 10,000 neurons`. `402` appears for billing walls.
- The allowance is **per account**, and the account id is embedded in the base URL — so two keys on two accounts are two quotas, while two keys on one account share one. A pool keyed on provider+base_url inherits that sharing.
- Reset boundary is **00:00 UTC**. A cooldown shorter than that guarantees quarantine/healthy flapping; hold the channel to the reset instead.
- What *does* reflect entitlement is `/ai/v1/models` answering `405`/`7001` regardless of token — which is why method errors must never be read as quota or auth signals.

Deprecation churn is high and fast. `.../ai/models/search` carries per-model deprecation properties; invoking a retired id answers `HTTP 410` with `errors[0].code: 5028` (`Model has been deprecated: <id> was deprecated on <date>`), and the sibling `@cf/qwen/...` family can rotate within days. Two consequences:

- Never hardcode a Workers AI probe model without checking it against the live catalog first — a same-day deprecation makes every probe fail on a cause unrelated to the credential.
- Treat `5028`/`410` as a **model-id** fault, not a key fault: fix the route's `upstream_model_name`, and do not quarantine the credential for a whole day over it.
- `5007` (`No such model <x> or task`) is the different fingerprint for a wrong id shape (uuid stored instead of the `@cf/...` name, or a stripped namespace) — that means the route is misconfigured, not the account.

## Error envelopes (all JSON with `success: false`)

| Code | Message / trigger | Meaning |
|---|---|---|
| `7001` | `GET not supported for requested URI` (405) | Route exists for another verb only. Fires **before auth** — proves nothing about the token. |
| `7003` | `Could not route to ...` (404) | Path does not exist at all. |
| `9106` | `Missing X-Auth-Key, X-Auth-Email or Authorization headers` (400) | Route is valid; credential missing/not sent. |
| `5007` | `No such model <x> or task` (400) | The model string is not a Workers AI id — usually the catalog's uuid got stored instead of the `@cf/...` name, or the id lost its `@cf/` prefix. |

## Practical consequences

- `GET .../ai/v1/models` → 405/7001. `GET .../ai/v1` → 404/7003. Neither is a models list; do not build a Cloudflare preset that probes there.
- Account id is embedded in the path, so a different account means a different base URL — treat it as part of the credential bundle, not a global setting.
- The `/ai/v1` shim covers chat/embeddings/responses only. JSON mode, structured outputs, reranking and raw binary output live on `/ai/run`, whose body is flat (`{"messages": [...], "stream": true}`) with the model in the URL rather than a `model` field.
- AI Gateway's `/ai/v1` has the same missing-catalog gap, so switching to AI Gateway does not fix a discovery-based verifier.
- Verified live: the search route with a bogus bearer answers `400`/`9106 Authentication failed`, while `/ai/v1/models` answers `405`/`7001` regardless of the token. So 7001 = wrong path (fix the URL), 9106 = right path, bad credential (fix the token). Never report the first as an auth problem.
- Cloudflare error text lives at `errors[0].message` (with `errors[0].code`), not `error.message` — a generic `JSON.stringify(body)` fallback dumps the whole envelope into the UI and hides the code.