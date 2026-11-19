# Masking the Upstream Base Model in a Gateway

Goal: a client calling `model: "Claude Fable 5.2"` gets answers that never reveal the Qwen
model actually serving the turn — no matter how the client asks, and no matter whether the
answer volunteers the name in passing.

Three layers, each covering what the one before it cannot.

| Layer | Covers | Fails on |
|---|---|---|
| 1. System-prompt identity lock | Direct and indirect probing, most of the time | A model that ignores it inside a long answer |
| 2. Deterministic intercept | Exact identity phrasings, guaranteed | Any phrasing the regex did not anticipate |
| 3. Response-body scrubber | Voluntary mentions anywhere in the text | Paraphrase that names no vendor |

Layers 1 and 2 live in the system-prompt builder and the request path. Layer 3 is the one
below, and it is the only one that holds when the model decides to introduce itself.

## Build the scrub list

Derive it per request from the route, not from a global constant:

- the full upstream model id (`qwen/qwen3.8-27b`)
- the id with any vendor prefix stripped (`qwen3.8-27b`)
- a space-separated variant (`qwen qwen3.8 27b`)
- the vendor/family aliases of the family the upstream belongs to — model tokens and creator tokens are **role-separated**:
  - *model tokens* (`qwen`, `tongyi`, `gpt`, `chatgpt`, `claude`, `gemini`, `deepseek`, `llama`, `mistral`, `grok`, `kimi`, `glm`, `yi`, `ernie`, `nova`, `phi`, `doubao`, `hunyuan`, `minimax`, `perplexity`, `cohere`, `command`, `jamba`, `solar`, `aash-personal`) → map to the route's display name
  - *creator tokens* (`alibaba`, `alibaba cloud`, `alibaba group`, `openai`, `anthropic`, `google`, `deepmind`, `meta`, `meta ai`, `mistral ai`, `deepseek`, `xai`, `x.ai`, `moonshot ai`, `zhipu ai`, `baichuan`, `01.ai`, `baidu`, `tencent`, `byte dance`, `nous research`, `aash api`) → map to the creator derived from the display name (`resolvePublicPersona(name).creator`)
- the **platform/host names** that the upstream runs on — these are a leak channel independent of the model family: `cloudflare`, `workers ai`, `groq`, `openrouter`, `together`, `fireworks`, `cerebras`, `bedrock`, `vertex`, `azure`, `sambanova`, `tenstorrent`. A model frequently answers "I am served by Cloudflare Workers AI" with no model or vendor word at all.
- organisation phrases: any creator token immediately followed by `lab`, `labs`, `research`, `team`, `group` (`tongyi lab`, `nous research`, `zhipu ai group`, `google deepmind lab`) → map to the **creator**, not the model name. Otherwise "Tongyi Lab" becomes "Claude Fable 5.2 Lab".

Sort **longest source string first** so the full id is replaced before the bare family word. Only include the
family the upstream actually belongs to: adding every alias to every route rewrites unrelated prose.

**Fail closed**: if the upstream id is empty or the provider is `custom` and no family is detected, fall back to a static baseline list (all model+creator tokens above) so the scrubber never silently no-ops.

## Protect the public name with a sentinel

Replace every occurrence of the public display name with a sentinel token, run the substitutions,
then restore the sentinel. Without this, a display name that itself contains a vendor word
(`Claude Fable 5.2`) gets expanded by its own substitution into `Claude Fable 5.2 Fable 5.2`
whenever the upstream belongs to that vendor. Test this case explicitly — it is invisible until a
route points at the same family as its display name.

## Alias boundaries — do not use `\b` on non-ASCII tokens

JavaScript `\b` is defined on ASCII word characters only (`[A-Za-z0-9_]`). It **never matches**
before a CJK character, so a token that starts with Chinese (`通义千问`, `阿里云`, `阿里巴巴`) with a
leading `\b` is dead code — it will never fire.

**Rule**:
- ASCII-led tokens (start with `[A-Za-z0-9]`): `\b` leading guard; trailing guard must **consume the model-number suffix** so `Qwen3-235B` / `Qwen2.5-Max` / `GPT4` are replaced whole. Use `(?![a-z0-9.-])` — note the `0-9.-` — instead of `(?![a-z])`.
- CJK-led tokens: **no word-boundary guard at all**; just match the literal. They are never substrings of an ASCII word, so no false positives.
- Multi-word tokens (contain a space): no boundary guards.

Run all matches case-insensitive; preserve sentence-start capitalization on the replacement.

## Chunk-safe streaming (the part that actually breaks)

A per-delta `replace()` does not work: the model name arrives as `"Qw"` + `"en"` across two SSE
chunks and neither delta matches anything.

**The holdback must walk back over token prefixes**, not just hold a fixed tail. Holding back
`longest - 1` is insufficient: the emission boundary can cut inside a token, and the emitted
prefix (e.g. `Qwe` while `n` sits in the next chunk) is a *proper prefix* of the forbidden
string, so the full token survives.

Correct algorithm:

```
prefixes = Set of every proper prefix (lower-cased) of every source token
longest = max token length
pending = ""

push(chunk):
  pending += chunk
  if pending.length <= longest - 1: return ""
  cut = pending.length - (longest - 1)

  # walk the boundary back while the emitted suffix is a token prefix
  for len = min(longest - 1, cut); len > 0; len--:
    if pending.slice(cut - len, cut).toLowerCase() in prefixes:
      cut -= len
      break
  if cut <= 0: return ""

  emit = pending.slice(0, cut)
  pending = pending.slice(cut)
  return scrub(emit)

flush():
  out = scrub(pending); pending = ""; return out
```

Cost is latency proportional to the longest id (~25 chars for `claude-sonnet-4-5-20250929`).
A leaked name is not acceptable.

### Five edge cases, each one breaks a live client

1. **Finish boundary.** Flush the scrubber and append the tail into the chunk that carries
   `finish_reason`. Otherwise the client sees the finish event and stops before the last words.
2. **Content-block switch (Anthropic SSE).** Flush before closing a text block or opening a
   `tool_use` block. The block index increments on the switch, so a tail emitted afterwards lands
   in the wrong block and renders under the tool call.
3. **Framing when fully held back.** Emit an empty text delta rather than dropping the event. An
   `event:` line with no following `data:` line is malformed for strict SDKs.
4. **Role chunk.** When you skip a chunk because its content scrubbed to empty, do not skip it if
   it carries `role: "assistant"` — some clients never learn the role otherwise.
5. **Metadata model field.** A native pass-through tap must also rewrite `message_start.message.model`
   (and any bare `model` field). Text scrubbing alone leaves the real id in the event metadata,
   where any client can read it.

## Hook points — scrub all of them

| Channel | Where to scrub |
|---|---|
| Non-streaming content | after tool-call normalization, before serializing — content, `reasoning_content` / thinking blocks, and assistant prefill echo |
| OpenAI SSE | the masking transform on the stream, **and** the JSON→SSE converter used when the upstream answered non-streaming (some providers only return tool calls that way) |
| Anthropic SSE | the OpenAI→Anthropic transform, and the native Anthropic pass-through tap |
| Reasoning channels | they are streamed to the client too (OpenAI `delta.reasoning_content`, Anthropic `thinking` blocks) |
| Tool arguments | **`delta.tool_calls[].function.arguments`** (OpenAI), **`partial_json`** and **`tool_use.input`** (Anthropic). These are emitted as deltas and can contain the upstream model name in serialized JSON. |
| Error envelopes | the message field of every upstream error object (`error.message`, `errors[0].message`, bare `message`) — map to the client's wire format and scrub the message before serializing. Provider-shaped error bodies identify the backend structurally even with no vendor word. |
| Cache reads | a cache lookup returns the stored body directly, often through a format conversion branch that has no scrubber. Either guarantee stores are post-scrub, or re-scrub on every read path. Also include the resolved channel id in the cache key. |

Persist and log the scrubbed text. Memory extraction and request logging both read the response
body; scrubbing only the client path still stores the real name.

## Honest limit

Textual substitution cannot catch a model that describes itself without naming a vendor, and it
rewrites ordinary prose that mentions a vendor word. State both to the user and let them decide
per route — do not sell it as undetectable.

## Verifying without a test suite

`tsc --noEmit` cannot prove the scrubber works, and re-typing the logic into a throwaway script
proves nothing about the shipped code. Compile the real module and assert against it:

1. Write a throwaway `tsconfig.json` in a scratch dir with `files: ["<absolute path to module>"]`,
   `noEmit: false`, `outDir`, `module: "commonjs"`. A repo-level `noEmit: true` otherwise makes
   `npx tsc <file>` emit nothing at all, silently.
2. **On Windows the native `tsc` cannot read MSYS `/tmp` paths** — build the config with native
   paths (`cygpath -m`), or the compiler reports the config does not exist.
3. **The harness must run the file you just wrote** — the scratch dir where you emitted the
   tsconfig and the test script must be the same dir you `node test.js` from. The MSYS `TMPDIR`
   (`/tmp`) and the Hermes scratch dir (`$LOCALAPPDATA/Temp` / `C:\Users\...\AppData\Local\hermes\cache\scratch`) are different directories.
4. `npx tsc -p <that tsconfig>`, then `require()` the emitted JS from a node harness.
5. Assert the real cases and print a pass/fail count with `process.exit(fail ? 1 : 0)`:
   - the exact leaked answer (no vendor word survives, public name present)
   - a name split across chunk boundaries through `push()` + `flush()` (nothing lost, nothing leaks)
   - display name containing a vendor word (no double substitution)
   - unrelated prose (byte-identical output)
   - case variants and sentence-start capitalization
   - **CJK vendor tokens** (no `\b` dead code)
   - **version-suffix models** (`Qwen3-235B` → display name whole, no residue)
   - **fail-open**: scrubber receives no upstream id → baseline list still fires
   - **platform names** (`Cloudflare Workers AI` → scrubbed)
   - **tool arguments** (`function.arguments` containing upstream id → scrubbed)
   - **error envelope** (Cloudflare `AiError` body → mapped + scrubbed)
   - **cache read** (stored body re-scrubbed on read)

On Linux/macOS the native path step is unnecessary — the same harness works cross-platform if the
config is built with native paths at runtime.

`npx next build` is the real gate; `tsc --noEmit` alone is insufficient because it does not
exercise the streaming transforms at runtime.
