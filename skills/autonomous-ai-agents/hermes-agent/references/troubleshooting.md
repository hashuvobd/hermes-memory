# Troubleshooting

### Voice not working
1. Check `stt.enabled: true` in config.yaml
2. Verify provider: `python -c "import pm; pm.sync_venv(['stt-whisper'], explicit=True)"` or set API key
3. In gateway: `/restart`. In CLI: exit and relaunch.

### Tool not available
1. `hermes tools` — check if toolset is enabled for your platform
2. Some tools need env vars (check `.env`)
3. `/reset` after enabling tools

### Model/provider issues
1. `hermes doctor` — check config and dependencies
2. `hermes auth` — re-authenticate OAuth providers (or `hermes auth add <provider>`)
3. Check `.env` has the right API key
4. **GitHub Copilot** (`copilot` / `copilot-acp`) lives in the `github-copilot` labs plugin (`hermes plugins install github-copilot`); sign in with `hermes auth add copilot` — `gh` CLI logins are not read.

### Model switch refused: `use_session_mutation_model` (desktop picker)

`Model switch failed: JsonRpcGatewayError: use_session_mutation_model` in
`~/.hermes/logs/desktop.log` means the picker sent a bare
`config.set {key: 'model'}`. A model pick is session policy, not config: the
gateway accepts it only as the revision-fenced `session.mutate` operation, and
the desktop translator (`pickerModelMutation` in
`apps/desktop/src/api/canonical-protocol.ts`) is what rewrites it. That
translator splits the picker value `<model> --provider <id> [--session]` on
whitespace and demands exactly two flag tokens — so **a model NAME containing a
space makes it return null**, the pick falls through as raw `config.set`, and
the gateway refuses it. The `/model <name>` slash command parses the same way
and fails identically.

Diagnose before touching anything: read the log line, then feed the parser the
picker's real value.

```js
// inline pickerModelMutation in node -e
"Some Model --provider custom"          -> null      // broken
"Some Model --provider custom --session" -> null     // broken
"Some-Model --provider custom"          -> {model,provider}
```

Fixes, best first:

1. **No whitespace in model IDs** on the serving endpoint — rename, or expose
   hyphenated aliases. Fixes every surface with no rebuild; the only fix that
   survives updates.
2. Immediate workaround: `hermes config set model.default "<name>"`, then start
   a new session. Writes config.yaml directly and bypasses the picker; it does
   not retro-apply to the running session.
3. Patch the parser to `/^(.+?)\s+--provider\s+(\S+)(\s+--session)?$/` and
   rebuild the desktop bundle. Correct but local — re-applied after every
   update; report upstream as well.

Same-symptom neighbour: an OpenAI-compatible endpoint that publishes no model
metadata logs `Could not detect context length ... defaulting to 256,000 tokens
(probe-down)` in `agent.log`. Harmless when that number is right; pin it with
`model.context_length` when it is not.

### Changes not taking effect
- **Tools/skills:** `/reset` starts a new session with updated toolset
- **Config changes:** In gateway: `/restart`. In CLI: exit and relaunch.
- **Code changes:** Restart the CLI or gateway process

### web_extract shows a stale page (result caching)
`web_search`/`web_extract` cache results for 20 minutes (PR #94618) — a
repeat fetch of the same URL within the TTL is served from cache, which
can look like "my website changes aren't showing up."

Automatic carveouts (always fetched live, never cached):
- localhost / 127.0.0.1 / `*.local` / `*.localhost` / single-label LAN
  hostnames / private + link-local IP ranges (dev servers, hot-reload
  builds, chat-GUI artifact previews)
- URLs matched by `security.website_blocklist`
- failed responses and keyless-rescue-served responses

Developing a site tested over the PUBLIC internet (Vercel/Netlify
preview, ngrok/cloudflared tunnel, staging domain)? Public DNS isn't
auto-carved-out — list the host in config.yaml:

```yaml
web:
  cache_exempt_hosts:      # always fetched live; effective immediately
    - mysite.vercel.app
    - "*.ngrok-free.app"
    - mysite.dev           # suffix match: also covers preview.mysite.dev
```

Blunt instruments: `web.cache_ttl_minutes: 1` (min) or
`web.cache_enabled: false` disables both caches entirely.

### Skills not showing
1. `hermes skills list` — verify installed
2. `hermes skills config` — check platform enablement
3. Load explicitly: `hermes -s name` (or the skill's own `/<name>` slash command)

### Gateway issues
Check logs first:
```bash
grep -i "failed to send\|error" ~/.hermes/logs/gateway.log | tail -20
```

Common gateway problems:
- **Gateway dies on SSH logout**: Enable linger: `sudo loginctl enable-linger $USER`
- **Gateway dies on WSL2 close**: WSL2 requires `systemd=true` in `/etc/wsl.conf` for systemd services to work. Without it, gateway falls back to `nohup` (dies when session closes).
- **Gateway crash loop**: Reset the failed state: `systemctl --user reset-failed hermes-gateway`

### Platform-specific issues
- **Discord bot silent**: Must enable **Message Content Intent** in Bot → Privileged Gateway Intents.
- **Slack bot only works in DMs**: Must subscribe to `message.channels` event. Without it, the bot ignores public channels.
- **Windows-specific issues** (`Alt+Enter` newline, WinError 10106, UTF-8 BOM config, line endings): see `references/windows-quirks.md`.

### Auxiliary models not working
If `auxiliary` tasks (vision, compression, session_search) fail silently, the `auto` provider can't find a backend. Either set `OPENROUTER_API_KEY` or `GOOGLE_API_KEY`, or explicitly configure each auxiliary task's provider:
```bash
hermes config set auxiliary.vision.provider <your_provider>
hermes config set auxiliary.vision.model <model_name>
```

### "Reset permissions" / auto-approving everything
See `references/security-privacy.md` — wipe the "Always allow" stores, don't touch yolo mode.

