#!/usr/bin/env bash
# Bind the conditional roles/iap.egressor policy (terraform output mcp_iap_policy) to the
# server's Agent Registry entry. Env: PROJECT, REGION, POLICY_JSON, DISPLAY_NAME.
set -euo pipefail

: "${PROJECT:?}" "${REGION:?}" "${POLICY_JSON:?}"
DISPLAY_NAME="${DISPLAY_NAME:-catalog-mcp}"

policy_file=$(mktemp)
trap 'rm -f "$policy_file"' EXIT
printf '%s' "$POLICY_JSON" > "$policy_file"

server=$(gcloud alpha agent-registry mcp-servers list \
  --project "$PROJECT" --location "$REGION" \
  --filter="displayName=$DISPLAY_NAME" --format='value(name)')
if [ -z "$server" ]; then
  echo "no MCP server named $DISPLAY_NAME in the registry" >&2
  exit 1
fi

# The id is the last path segment of the entry's resource name.
gcloud beta iap web set-iam-policy "$policy_file" \
  --project "$PROJECT" --region "$REGION" \
  --resource-type=agent-registry \
  --mcp-server="${server##*/}"
