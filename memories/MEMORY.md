Shuvo expects live data, not recall: when a fact may have moved (model releases, benchmarks, prices, software versions, current events), search the web and answer with dated sources instead of relying on training knowledge, which is about a generation behind on AI models. Say plainly when something was checked and when.
§
Project memory: one markdown file per project in ~/hermes-memory/projects (INDEX.md is the entry point), in the private repo hashuvobd/hermes-memory alongside memories/ and skills/. Procedure lives in the project-memory skill. Memory sync: `python sync.py` in ~/hermes-memory.
§
The memory repo has no inherited git identity; each clone carries its own local config (hashuvobd / hashuvobd@users.noreply.github.com). A fresh clone or a sync script will fail `git commit` with 'Author identity unknown' until `git config user.name/user.email` is set in that repo.
§
AASH API project at E:\My Projects\AASH API, git remote origin https://github.com/hashuvobd/AASH-API.git (branch main), deployed at https://aash-api.vercel.app
§
Gateway models via GET /v1/models: Claude Fable 5.2, AASH-Personal, Fast-Response; endpoints /v1/chat/completions (OpenAI) and /v1/messages (Anthropic)
§
API key aash_api_6fa669053aed790a0a9e61bd82904d6b8a059fd38cc5e137 available as env vars HERMES_CUSTOM_AASH_API_VERCEL_APP_API_KEY and ANTHROPIC_AUTH_TOKEN
§
Fix: src/app/v1/messages/route.ts — Anthropic→OpenAI tool translation drops nameless tool stubs missing function.name (fixes HTTP 400)
§
Fix: src/lib/gateway/agentMiddleware.ts — AASH IDENTITY LOCK directive + deterministic identity intercept masks upstream base model identity
§
Vercel CLI not installed locally (npx vercel times out); dev server not running on port 3000; shell is bash/git-bash not PowerShell