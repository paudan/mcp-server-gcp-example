# catalog-mcp: example MCP server on GCP

Companion code for [`../mcp-server-gcp.md`](../mcp-server-gcp.md). A deliberately tiny
notes catalog, wrapped in everything a production-like deployment needs: stateless
streamable HTTP, per-caller roles, a private Cloud Run service, Agent Registry
registration, a per-tool IAP policy and a keyless deploy workflow.

Nothing here is deployed by the tests or by reading it. Preview surfaces (`gcloud alpha`,
Agent Registry, Agent Gateway) were checked against `--help` output in October 2026.

## Layout

- `server/`
  - `app/auth.py`: ID-token verification for service accounts and agent identities, role lookup, 401/403 middleware.
  - `app/server.py`: the three tools, role-filtered `tools/list` and `tools/call`, `stateless_http=True`.
  - `scripts/generate_toolspec.py`: trims the tool list for Agent Registry and fails above 9,500 bytes.
  - `tests/`: auth, stateless, role and toolspec tests (no network, no credentials).
- `terraform/`: VPC, NAT, optional PSC attachment, Artifact Registry, workload identity federation, the Cloud Run service, and the IAP policy as an output. Applied by hand.
- `.github/`: one deploy workflow and the composite action it uses.
- `scripts/`: registry registration, IAP binding, and an access-ladder smoke test.
- `client/example_client.py`: registry lookup by display name, cached ID token, `tools/list`.

## Run it locally

```bash
cd server
uv sync
uv run pytest -q
MCP_ALLOW_ANONYMOUS=true uv run python -m app      # http://127.0.0.1:8080/mcp
```

In another shell:

```bash
curl -s -X POST http://127.0.0.1:8080/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

`MCP_ALLOW_ANONYMOUS=true` skips authentication and treats everyone as admin. Never set it on Cloud Run.

## Deploy order

1. `cp terraform/terraform.tfvars.example terraform/terraform.tfvars`, fill it in, then
   `terraform -chdir=terraform init && terraform -chdir=terraform apply`.
2. Store the outputs as GitHub secrets: `WIF_PROVIDER` (`wif_provider`),
   `WIF_SERVICE_ACCOUNT` (`deploy_service_account`), `GCP_PROJECT_ID`, `GCP_REGION`.
3. Push to `main` (or run the workflow). It tests, builds, deploys and registers the server.
4. Export the policy once the entry exists and keep it in the `POLICY_JSON` repository variable:
   `terraform -chdir=terraform output -raw mcp_iap_policy`. Re-run the workflow to bind it.
5. `URL=$(terraform -chdir=terraform output -raw service_url) scripts/smoke_test.sh` from a host on the VPC.

## Tear down

`terraform -chdir=terraform destroy`, then delete the registry entry:
`gcloud alpha agent-registry services delete catalog-mcp --location=$REGION`.
