# Configuration, Toolsets & Voice

Edit with `hermes config edit` or `hermes config set section.key value`.
Full reference: https://hermes-agent.nousresearch.com/docs/user-guide/configuration

### Config Sections (most-used keys)

| Section | Key options |
|---------|-------------|
| `model` | `default`, `provider`, `base_url`, `api_key`, `context_length`, `aliases` |
| `agent` | `max_turns` (90), `tool_use_enforcement`, `service_tier`, `verify_on_stop` |
| `terminal` | `backend` (local/docker/ssh/modal/daytona/vercel_sandbox, or a plugin backend like singularity), `cwd`, `timeout` (180) |
| `compression` | `enabled`, `threshold` (0.50), `target_ratio` (0.20) |
| `display` | `skin`, `interface` (cli/tui), `language`, `show_reasoning`, `show_cost`, `pet` |
| `approvals` | `mode` (smart/manual/off), `timeout`, `cron_mode` |
| `stt` | `enabled`, `provider` (local/groq/openai/mistral/elevenlabs/deepinfra) |
| `tts` | `provider` (edge/elevenlabs/openai/minimax/mistral/neutts/gemini/piper/kittentts/deepinfra/xai) |
| `memory` | `memory_enabled`, `user_profile_enabled`, `provider`, `write_approval` |
| `security` | `redact_secrets`, `website_blocklist` |
| `browser` | `headed` (false), `engine` (auto/lightpanda), `executable_path` ("" = auto-detect Chromium), `user_data_dir` ("" = fresh ephemeral profile per session), `chromium_args` ([]), `command_timeout` (Chromium launch timeout floor), `cloud_provider`, `cdp_url`, `use_real_profile` |
| `delegation` | `model`, `provider`, `max_concurrent_children`, `max_iterations` (50), `max_spawn_depth` |
| `checkpoints` | `enabled`, `max_snapshots` (50) |
| `curator` | `enabled`, `consolidate` (false, opt-in aux-model consolidation), `interval_hours`, `stale_after_days` |

`hermes config check` reports sections missing from an older config.

### Toolsets

Enable/disable via `hermes tools` (interactive) or `hermes tools enable/disable NAME`.
Full enumeration: `TOOLSETS` dict in `toolsets.py` (`_HERMES_CORE_TOOLS` is the default bundle most platforms inherit).

| Toolset | What it provides |
|---------|-----------------|
| `web` / `search` | Web search + extraction / search-only subset |
| `browser` | `browser_exec` (Python CDP helpers), `browser_cdp`, `browser_dialog`, `browser_vault` — local Chromium, a cloud provider, or `/browser connect`. Disable this toolset to turn browsing off |
| `terminal` | Shell commands and process management |
| `file` | File read/write/search/patch |
| `code_execution` | Sandboxed Python execution |
| `coding` | Code-editing helpers (LSP-backed) |
| `computer_use` | Desktop GUI control (cua-driver) |
| `vision` | Image analysis |
| `image_gen` | Image generation and image-to-image editing |
| `video` / `video_gen` | Video analysis / video generation |
| `x_search` | X (Twitter) search (X OAuth or API key) |
| `tts` | Text-to-speech |
| `skills` | Skill browsing and management |
| `memory` | Persistent cross-session memory |
| `session_search` | Search past conversations |
| `context_engine` | Pluggable context-engine hooks |
| `project` | Named multi-folder workspace tools |
| `delegation` | Subagent task delegation |
| `cronjob` | Scheduled task management |
| `clarify` | Ask user clarifying questions |
| `todo` | In-session task planning |
| `kanban` | Multi-agent work-queue tools (gated to workers) |
| `debugging` | Extra introspection tools (off by default) |
| `safe` | Minimal low-risk toolset for locked-down sessions |
| `discord`, `discord_admin`, `feishu_doc`, `feishu_drive` | Service integrations (gated on their credentials). `homeassistant` (`ha_*` tools), `spotify` (`spotify_*` tools) and `yuanbao` (`yb_*` tools) are not built in: they come from the `homeassistant` / `spotify` / `yuanbao` catalog plugins (`hermes plugins install <name>`) |

Camofox is no longer built in: `hermes plugins install camofox` adds it as the `camofox` toolset with its own browser tools. Existing Camofox setups are migrated automatically on `hermes update`.

Tool changes take effect on `/reset` (new session) — never mid-conversation, to preserve prompt caching.

## Voice

### STT (Voice → Text)

Voice messages from messaging platforms are auto-transcribed.

```yaml
stt:
  enabled: true
  provider: local   # local (faster-whisper, free) | groq | openai | mistral | elevenlabs | deepinfra
  local:
    model: base     # tiny, base, small, medium, large-v3, turbo
```

Auto-detect priority: local faster-whisper (`python -c "import pm; pm.sync_venv(['stt-whisper'], explicit=True)"`) → Groq (`GROQ_API_KEY`, free tier) → OpenAI (`VOICE_TOOLS_OPENAI_KEY`) → Mistral Voxtral (`MISTRAL_API_KEY`).

### TTS (Text → Voice)

| Provider | Env var | Free? |
|----------|---------|-------|
| Edge TTS (default) | None | Yes |
| ElevenLabs | `ELEVENLABS_API_KEY` | Free tier |
| OpenAI | `VOICE_TOOLS_OPENAI_KEY` | Paid |
| MiniMax | `MINIMAX_API_KEY` | Paid |
| Mistral | `MISTRAL_API_KEY` | Paid |
| Gemini | `GOOGLE_API_KEY` | Free tier |
| NeuTTS / Piper / KittenTTS (local) | None | Free |

Voice commands: `/voice on` (voice-to-voice), `/voice tts` (always voice), `/voice off`.

### Chat-surface visibility + busy input (`display.*`)

Three independent knobs; users often ask for one and mean another:

| Key | Hides | Values |
|---|---|---|
| `display.show_reasoning` | model reasoning / "Thought" blocks | bool (desktop Settings → Chat → Reasoning Blocks; `/reasoning hide`) |
| `display.tool_progress` | tool rows (reads, greps, commands) | `off`/`new`/`all`/`verbose`/`log`; only `off` or `false` silences, a missing key means on |
| `display.busy_input_mode` | — behaviour: what Enter does mid-turn | `interrupt` (default), `queue` (next turn), `steer` (inject after next tool call); `/busy <mode>` |

"Answer-only" = `show_reasoning: false` + `tool_progress: off`. Approvals, failed calls and diffs stay visible regardless.

Pitfalls, all verified in source:

- `hermes config set display.tool_progress off` coerces `off` → boolean `false` and warns "not a recognized config key". The warning is cosmetic (the key registry lags the readers); `_load_tool_progress_mode()` and the desktop's `toolProgressVisible()` both handle a bool.
- A CLI `config set` on these keys is **not pushed** to the running desktop renderer — `change_watcher.py` broadcasts skins/pets/cron/sessions/skills but no `config.changed`. The gateway side reads through `load_user_config_effective()` (mtime-cached) so behaviour (`busy_input_mode`) applies to the next message; the renderer repaints only after it refetches config (app reload or session switch). Say this instead of claiming it is already live.
- Desktop sessions resolve `display.platforms.cli.show_reasoning` first, then the global key (that is what the app's own toggle writes); `tool_progress` is read globally only. Setting the global keys also replaces messaging-platform defaults — override under `display.platforms.<platform>` to keep Telegram/Discord chatty.
- Hiding reasoning hides output, not thinking. Cost/latency come from `agent.reasoning_effort` or provider `enable_thinking: false`.
