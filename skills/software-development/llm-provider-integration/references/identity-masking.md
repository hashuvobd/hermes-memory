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
- the vendor/family aliases of the family the upstream belongs to — `qwen|tongyi|alibaba|alibaba cloud`,
  `gpt|chatgpt|openai`, `claude|anthropic`, `gemini|google|deepmind`, `deepseek`, `llama|meta`, `mistral`

Sort **longest first** so the full id is replaced before the bare family word. Only include the
family the upstream actually belongs to: adding every alias to every route rewrites unrelated prose.

## Protect the public name with a sentinel

Replace every occurrence of the public display name with a sentinel token, run the substitutions,
then restore the sentinel. Without this, a display name that itself contains a vendor word
(`Claude Fable 5.2`) gets expanded by its own substitution into `Claude Fable 5.2 Fable 5.2`
whenever the upstream belongs to that vendor. Test this case explicitly — it is invisible until a
route points at the same family as its display name.

Match single-word aliases with `\b` boundaries and multi-word ones without; run case-insensitive;
preserve sentence-start capitalization on the replacement.

## Chunk-safe streaming (the part that actually breaks)

A per-delta `replace()` does not work: the model name arrives as `"Qw"` + `"en"` across two SSE
chunks and neither delta matches anything.

Use a stateful scrubber:

```
holdback = (longest forbidden string length) - 1

push(chunk):
  pending += chunk
  if len(pending) <= holdback: return ""          # nothing safe to emit yet
  emit   = pending[:len(pending) - holdback]
  pending = pending[-holdback:]
  return scrub(emit)

flush():
  out = scrub(pending); pending = ""; return out
```

Holding back the tail guarantees no forbidden string can straddle an emit boundary. Cost is
latency proportional to the longest id: a route on `claude-sonnet-4-5-20250929` lags ~25 chars
behind real time. That is acceptable; a leaked name is not.

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

## Hook points

Scrub all of them, not just the obvious one:

- **Non-streaming**: after tool-call normalization, before serializing the response — content,
  `reasoning_content` / thinking blocks, and assistant prefill echo.
- **OpenAI SSE**: the masking transform on the stream, **and** the JSON→SSE converter used when the
  upstream answered non-streaming (some providers only return tool calls that way).
- **Anthropic SSE**: the OpenAI→Anthropic transform, and the native Anthropic pass-through tap.
- **Reasoning channels**: they are streamed to the client too.

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
2. `npx tsc -p <that tsconfig>`, then `require()` the emitted JS from a node harness.
3. Assert the real cases and print a pass/fail count with `process.exit(fail ? 1 : 0)`:
   - the exact leaked answer (no vendor word survives, public name present)
   - a name split across chunk boundaries through `push()` + `flush()` (nothing lost, nothing leaks)
   - display name containing a vendor word (no double substitution)
   - unrelated prose (byte-identical output)
   - case variants and sentence-start capitalization

On Windows the native `tsc` cannot read MSYS `/tmp` paths — build the config with native paths
(`cygpath -m`), or the compiler reports the config does not exist.
