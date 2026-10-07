#!/usr/bin/env bash
# The access ladder, from a host that can reach the service (a VM on the VPC):
#   no token -> 401, unlisted caller -> 403, reader -> read tool only, admin -> all.
# Env: URL (service url), plus optionally AS_SA (a service account you may impersonate).
# Locally: URL=http://localhost:8080 with MCP_ALLOW_ANONYMOUS=true skips the ladder.
set -euo pipefail

: "${URL:?}"
H=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')
LIST='{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
call() { curl -s "$@" | sed -n 's/^data: //p;/^{/p'; }

echo "no token  -> $(code -X POST "$URL/mcp" "${H[@]}" -d "$LIST") (want 401)"

if [ -n "${AS_SA:-}" ]; then
  token=$(gcloud auth print-identity-token --impersonate-service-account="$AS_SA" --audiences="$URL")
  echo "as $AS_SA -> $(code -X POST "$URL/mcp" "${H[@]}" -H "Authorization: Bearer $token" -d "$LIST")"
  call -X POST "$URL/mcp" "${H[@]}" -H "Authorization: Bearer $token" -d "$LIST" |
    python3 -c 'import json,sys; print("tools:", [t["name"] for t in json.load(sys.stdin)["result"]["tools"]])'
fi
