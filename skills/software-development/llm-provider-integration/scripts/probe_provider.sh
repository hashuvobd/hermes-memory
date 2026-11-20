#!/usr/bin/env bash
# Three-probe diagnostic for an OpenAI-compatible provider.
# Run unauthenticated first: method/route resolution usually precedes auth, so the
# result still tells you path-bug vs auth-bug without touching the user's key.
#
#   ./probe_provider.sh https://api.example.com/v1
#   ./probe_provider.sh https://api.example.com/v1 "$API_KEY" "@cf/meta/llama-3.2-3b-instruct"
#
# Always pass MODEL for a provider whose catalog is free/unmetered while inference bills a
# quota (Cloudflare Workers AI, most free tiers): a 200 on discovery during a full quota
# outage is the single most misleading signal in provider debugging.
#
# Exit codes: 0 = at least one surface worked, 1 = every probe failed.
set -uo pipefail

BASE="${1:?usage: probe_provider.sh BASE_URL [API_KEY] [MODEL]}"
KEY="${2:-}"
MODEL="${3:-}"
BASE="${BASE%/}"

AUTH=()
[ -n "$KEY" ] && AUTH=(-H "Authorization: Bearer $KEY")

# probe sets LAST_CODE; each endpoint is hit exactly once so a probe never burns quota twice.
LAST_CODE=""
probe() { # label, curl args...  -> returns 0 on HTTP 200
  local label="$1"; shift
  local body code
  body=$(mktemp)
  code=$(curl -sS -o "$body" -w '%{http_code}' --max-time 20 "$@" 2>&1) || code="000"
  LAST_CODE="$code"
  printf '== %s -> HTTP %s\n' "$label" "$code"
  head -c 600 "$body"; echo; rm -f "$body"
  [ "$code" = "200" ]
}

infer_payload() { printf '{"model":"%s","messages":[{"role":"user","content":"ping"}],"max_tokens":1,"temperature":0,"stream":false}' "$1"; }

surface_ok=1
probe "discovery  GET  {base}/models" "${AUTH[@]}" "$BASE/models" || true
DISC_CODE="$LAST_CODE"

probe "root       GET  {base}" "${AUTH[@]}" "$BASE" || true

if [ -n "$MODEL" ]; then
  probe "inference  POST {base}/chat/completions" "${AUTH[@]}" \
    -H 'Content-Type: application/json' \
    -d "$(infer_payload "$MODEL")" \
    "$BASE/chat/completions" || true
  INF_CODE="$LAST_CODE"
  [ "$INF_CODE" = "200" ] && surface_ok=0
  [ "$DISC_CODE" = "200" ] && surface_ok=0
else
  INF_CODE=""
  [ "$DISC_CODE" = "200" ] && surface_ok=0
  echo "!! no MODEL given — inference probe skipped; that is the only probe that proves the token"
  echo "   works AND that the account is entitled to generate. Pass one before calling a channel healthy."
fi

echo
echo "VERDICT"
case "${DISC_CODE}:${INF_CODE}" in
  200:200)           echo "  healthy — catalog and inference both answered" ;;
  200:429|200:402)   echo "  QUOTA WALL — catalog reachable, account cannot generate."
                     echo "  A discovery-only health check reports this as healthy. Do not clear the channel"
                     echo "  on a short timer: hold it to the provider's reset boundary (00:00 UTC for Workers AI)." ;;
  200:410)           echo "  MODEL GONE (410) — key is fine, the model id is retired. Fix the route's upstream id." ;;
  200:401|200:403)   echo "  catalog public, inference needs entitlement — scope or plan, not a URL fix." ;;
  404:*|405:*)       echo "  no catalog surface — 404/405 means reachable-but-wrong-path. Judge on the inference column." ;;
  *)                 echo "  discovery=$DISC_CODE inference=${INF_CODE:-n/a} — see references/health-and-quarantine.md" ;;
esac

echo
exit $surface_ok
