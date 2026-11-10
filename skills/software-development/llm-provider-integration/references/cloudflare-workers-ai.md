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
{ "success": true, "result": [ { "name": "@cf/meta/llama-3.1-8b-instruct",
    "task": { "id": "…", "name": "Text Generation" },
    "properties": [ { "property_id": "context_window", … } ] } ],
  "result_info": { "page": 1, "per_page": 200, "total_count": 87 } }
```

- The array is under **`result`**, not `data`/`models` — an OpenAI-shaped parser finds nothing and reports "0 models".
- Page until `result_info.total_count` is collected; `per_page` is honoured but has a server-side ceiling, so never assume one page is the whole catalog.
- `task.name` is the only reliable classifier: `Text Generation` → chat, `Text Embeddings` → embedding, others image/audio. Only text generation should auto-enable as a chat route.
- Prefer the **default** shape over `format=openrouter` when you also need `task` and `properties`; the marketplace shape drops the classification you need for tier tags.

## Error envelopes (all JSON with `success: false`)

| Code | Message / trigger | Meaning |
|---|---|---|
| `7001` | `GET not supported for requested URI` (405) | Route exists for another verb only. Fires **before auth** — proves nothing about the token. |
| `7003` | `Could not route to ...` (404) | Path does not exist at all. |
| `9106` | `Missing X-Auth-Key, X-Auth-Email or Authorization headers` (400) | Route is valid; credential missing/not sent. |

## Practical consequences

- `GET .../ai/v1/models` → 405/7001. `GET .../ai/v1` → 404/7003. Neither is a models list; do not build a Cloudflare preset that probes there.
- Account id is embedded in the path, so a different account means a different base URL — treat it as part of the credential bundle, not a global setting.
- The `/ai/v1` shim covers chat/embeddings/responses only. JSON mode, structured outputs, reranking and raw binary output live on `/ai/run`, whose body is flat (`{"messages": [...], "stream": true}`) with the model in the URL rather than a `model` field.
- AI Gateway's `/ai/v1` has the same missing-catalog gap, so switching to AI Gateway does not fix a discovery-based verifier.
- Verified live: the search route with a bogus bearer answers `400`/`9106 Authentication failed`, while `/ai/v1/models` answers `405`/`7001` regardless of the token. So 7001 = wrong path (fix the URL), 9106 = right path, bad credential (fix the token). Never report the first as an auth problem.
- Cloudflare error text lives at `errors[0].message` (with `errors[0].code`), not `error.message` — a generic `JSON.stringify(body)` fallback dumps the whole envelope into the UI and hides the code.