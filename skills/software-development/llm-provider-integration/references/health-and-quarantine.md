# Channel health, quarantine, and recovery

Depth for the rules in SKILL.md Step 4 and the health pitfalls. Four questions a gateway must answer separately: *is it reachable*, *can it infer*, *should it be in rotation*, and *what clears the block*.

## 1. Health-verdict matrix

Read discovery and inference as two columns. The combination is the verdict; neither column alone is one.

| Discovery (`GET /models` or vendor search) | Inference (`POST /chat/completions`) | Verdict |
|---|---|---|
| 200 | 200 | healthy—and only now can the badge be green |
| 200 | 429 / 402 / quota code | **quota wall.** Reachable, credentialed, entitled to *nothing right now*. A discovery-only probe calls this healthy. |
| 200 | 4xx auth/scope | credential or scope problem; the catalog may be public while generations need a paid plan |
| 200 | 410 / "model deprecated" | key is fine, the *model id* is dead — do not touch the credential |
| 404 / 405 / method-not-supported | — | no catalog surface. Reachable; keep the channel, use a static catalog, verify by completion |
| network error / timeout | — | genuinely unreachable |

**Rule of thumb:** the badge may only be set green by a row whose inference column returned 2xx. Everything else is degraded or quarantined with the reason attached.

## 2. Channel states

Do not collapse these into a boolean. A binary healthy/unhealthy flag forces "expired cooldown" to be reported as one of two lies.

| State | Meaning | In rotation? |
|---|---|---|
| `healthy` | a real completion succeeded; nothing since contradicts it | yes, first |
| `degraded` | unproven — cooldown expired, or a failure was cleared without proof | yes, but ordered *after* every `healthy` key |
| `quarantined` | failed within its cooldown window | only as explicit last resort |
| `disabled` | operator intent; never rotate, never auto-promote | no |

Ordering inside a pool: healthy keys by priority, then degraded keys, then the quarantine last resort. `disabled` is always excluded — and no automatic path may write anything but `disabled` over it.

## 3. Transition rules

| Trigger | Transition | Never |
|---|---|---|
| Real 2xx completion on a non-healthy key | → `healthy`, clear `last_error` + `quarantined_until` | do this from a read path or a timer |
| 429 / 402 on the request path or a probe | → `quarantined` until `now + cooldown(class)` | use a fixed cooldown constant |
| Cooldown expires | → `degraded` (probation), `quarantined_until = null` | → `healthy`; nothing proved recovery |
| Manual re-enable by the operator | → `healthy` | treat an operator override as an inference proof — it is intent, not evidence |

A `disabled` channel must survive every automatic path untouched, including the promotion call.

## 4. Cooldown derivation

Classify from the HTTP status *and* the message text, both of which the quarantine call should receive.

| Class | Signals | Hold |
|---|---|---|
| Rate limit | `429` without quota wording, `rate limit`, `too many requests` | minutes (10 is a fine default) |
| Quota / billing wall | `402`, `insufficient_quota`, `quota exceeded/exhausted/reached`, `daily limit`, `billing hard limit`, `free tier`, vendor codes like Workers AI `4006`/`4007` | until the provider's reset boundary — 00:00 **UTC** for Workers AI and OpenAI-style cycles |
| Model gone | `410`, `5028`, `model has been deprecated`, `no such model` | short; the block is on the model id, so fixing the route matters more than waiting |

Clamp the computed hold to a floor (≥15 min) and a ceiling (≤24 h) so a clock skew or a reset-boundary bug cannot pin a channel out of rotation indefinitely.

Match on `\b4006\b`-style word boundaries, not substring: numeric vendor codes collide with random digits inside request ids and model names.

## 5. Probe-model selection

Probe failures must be attributable to the credential or the quota — never to an id the account cannot serve. Resolve in this order and report which one was used:

1. The route's own upstream model for that channel — the probe then measures exactly what clients consume.
2. An imported/known model recorded against that channel (`channel_imported_models_<id>` or equivalent).
3. A provider default, **confirmed present in the current catalog**.

Keep step 3 in one named constant. Providers retire cheap models without notice, and a retired id turns every probe into a `410` that looks like an outage. Vendor catalogs expose deprecation flags and dates — read them at probe-model selection time rather than caching an id forever.

Probe shape: `max_tokens` 1–4, `temperature: 0`, non-streaming, one short user message. You are asserting reachability and entitlement, not quality.

## 6. Hook points

Every one of these can set or clear a channel's state, so all of them must share the same verdict function:

- the request path (`/v1/chat/completions`, `/v1/messages`, …) — quarantine on 429/402, promote on 2xx (one line, fire-and-forget, never blocking the response);
- any per-model "test this model" action — real completion, per-key results, cascade across the pool;
- an admin row-level ping — real completion for providers where discovery cannot see inference;
- the model-list page — a *display* concern: aggregate honestly, so a pool with one quarantined key does not render a green provider row.

Grep for every site that writes `status` on the channel table before declaring a fix complete — a stale writer silently undoes the new logic.
