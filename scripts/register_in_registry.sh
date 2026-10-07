#!/usr/bin/env bash
# Create or update the server's Agent Registry entry from a generated toolspec.
# Env: PROJECT, REGION, TOOLSPEC (path), SERVICE (default catalog-mcp),
#      DISPLAY_NAME (default catalog-mcp -- clients look it up by exact match).
set -euo pipefail

: "${PROJECT:?}" "${REGION:?}" "${TOOLSPEC:?}"
SERVICE="${SERVICE:-catalog-mcp}"
DISPLAY_NAME="${DISPLAY_NAME:-catalog-mcp}"

url=$(gcloud run services describe "$SERVICE" \
  --project "$PROJECT" --region "$REGION" --format='value(status.url)')

if gcloud alpha agent-registry services describe "$SERVICE" \
    --project "$PROJECT" --location "$REGION" >/dev/null 2>&1; then
  action=update
else
  action=create
fi

# Register <url>/mcp, not the bare URL: the client uses the registered path verbatim.
gcloud alpha agent-registry services "$action" "$SERVICE" \
  --project "$PROJECT" \
  --location "$REGION" \
  --display-name="$DISPLAY_NAME" \
  --description="Example notes catalog MCP server" \
  --mcp-server-spec-type=tool-spec \
  --mcp-server-spec-content="$(cat "$TOOLSPEC")" \
  --interfaces="url=$url/mcp,protocolBinding=jsonrpc"
