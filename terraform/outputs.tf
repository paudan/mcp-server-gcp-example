output "service_url" {
  value = google_cloud_run_v2_service.mcp.uri
}

output "deploy_service_account" {
  value = google_service_account.deploy.email
}

output "wif_provider" {
  value = google_iam_workload_identity_pool_provider.github.name
}

output "network_attachment" {
  description = "Pass to callers that have no VPC of their own; empty unless enable_psc_attachment."
  value       = try(google_compute_network_attachment.engines[0].id, "")
}

# `gcloud beta iap web set-iam-policy` reads this (version 3: conditional bindings);
# scripts/bind_iap_policy.sh applies it once the registry entry exists.
output "mcp_iap_policy" {
  value = jsonencode({ version = 3, bindings = local.iap_bindings })
}
