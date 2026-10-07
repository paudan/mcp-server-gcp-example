# Keyless auth for the deploy workflow: GitHub's OIDC token is exchanged for a
# short-lived credential of the deploy service account. No JSON keys anywhere.
resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  depends_on                = [google_project_service.services]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }
  # Without a condition any GitHub repository could impersonate the deploy account.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account" "deploy" {
  account_id   = "mcp-deploy"
  display_name = "CI deploy runner"
}

resource "google_service_account_iam_member" "deploy_wif" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# What deploy-server.yml needs, step by step. Add a role here when the workflow
# gains a step that needs one (a missing role shows up as a 403 in that step).
resource "google_project_iam_member" "deploy_roles" {
  for_each = toset([
    "roles/artifactregistry.writer", # push the image
    "roles/run.developer",           # gcloud run deploy / update-traffic
    "roles/agentregistry.editor",    # create/update the registry entry
    "roles/iap.admin",               # set the registry entry's IAP policy
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# `gcloud run deploy` acts as the service's runtime account.
resource "google_service_account_iam_member" "deploy_acts_as_runtime" {
  service_account_id = google_service_account.mcp.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}
