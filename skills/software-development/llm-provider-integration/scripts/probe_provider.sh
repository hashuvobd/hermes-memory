#!/usr/bin/env bash
# Three-probe diagnostic for an OpenAI-compatible provider.
# Run unauthenticated first: method/route resolution usually precedes auth, so the
# result still tells you path-bug vs auth-bug without touching the user's key.
#
#   ./probe_provider.sh https://api.example.com/v1
#   ./probe_provider.sh https://api.example.com/v1 "$API_KEY" "@cf/meta/llama-3.1-8b-instruct"
#
# Exit codes: 0 = at least one surface worked, 1 = every probe failed.
set -uo pipefail

BASE="${1:?usage: probe_provider.sh BASE_URL [API_KEY] [MODEL]}"
KEY="${2:-}"
MODEL="${3:-}"
BASE="${BASE%/}"

AUTH=()
[ -n "$KEY" ] && AUTH=(-H "Authorization: Bearer $KEY")

probe() { # label, curl args...
  local label="$1"; shift
  local body code
  body=$(mktemp)
  code=$(curl -sS -o "$body" -w '%{http_code}' --max-time 20 "$@" 2>&1) || code="000"
  printf '== %s -> HTTP %s\n' "$label" "$code"
  head -c 600 "$body"; echo; rm -f "$body"
  [ "$code" = "200" ] && return 0 || return 1
}

ok=1
probe "discovery  GET  {base}/models"       "${AUTH[@]}" "$BASE/models"       && ok=0
probe "root       GET  {base}"              "${AUTH[@]}" "$BASE"              || true

if [ -n "$MODEL" ]; then
  probe "inference  POST {base}/chat/completions" "${AUTH[@]}" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":1}" \
    "$BASE/chat/completions" && ok=0
else
  echo "!! no MODEL given — inference probe skipped; that is the only probe that proves a token works"
fi

echo
exit $ok
