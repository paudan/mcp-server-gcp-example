resource "google_project_service" "services" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "compute.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudtrace.googleapis.com",
    "agentregistry.googleapis.com",
    "iap.googleapis.com",
  ])
  service            = each.value
  disable_on_destroy = false
}
