locals {
  # The in-app role lists take bare identities: an email for a service account,
  # `principal://...` for an agent identity -- not the IAM `serviceAccount:` form.
  strip_prefix = { for m in concat(var.reader_identities, var.admin_identities) :
  m => replace(m, "serviceAccount:", "") }
}

resource "google_service_account" "mcp" {
  account_id   = "catalog-mcp"
  display_name = "catalog-mcp runtime"
}

resource "google_project_iam_member" "mcp_trace" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.mcp.email}"
}

resource "google_cloud_run_v2_service" "mcp" {
  name     = "catalog-mcp"
  location = var.region

  # Where a request may come from. IAM below decides who; this decides from where.
  ingress = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = google_service_account.mcp.email

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    vpc_access {
      # The server's own *.run.app name resolves to a public IP. Under the default
      # PRIVATE_RANGES_ONLY that never enters the VPC and INTERNAL_ONLY rejects it, so
      # every *caller* needs ALL_TRAFFIC. Set here for a caller deployed from this
      # module; the server itself calls nothing internal.
      egress = "ALL_TRAFFIC"
      network_interfaces {
        network    = google_compute_network.main.id
        subnetwork = google_compute_subnetwork.run_egress.id
      }
    }

    containers {
      # Placeholder: CI owns the image from the first deploy on.
      image = "us-docker.pkg.dev/cloudrun/container/hello"
      ports {
        container_port = 8080
      }
      env {
        name  = "MCP_HOST"
        value = "0.0.0.0"
      }
      env {
        name  = "MCP_READER_IDENTITIES"
        value = join(",", [for m in var.reader_identities : local.strip_prefix[m]])
      }
      env {
        name  = "MCP_ADMIN_IDENTITIES"
        value = join(",", [for m in var.admin_identities : local.strip_prefix[m]])
      }
    }
  }

  lifecycle {
    # `gcloud run deploy` changes the image and stamps client metadata.
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [google_project_service.services]
}

# Cloud Run IAM admits a caller; the app then checks its role.
resource "google_cloud_run_v2_service_iam_member" "invokers" {
  for_each = toset(concat(var.reader_identities, var.admin_identities))
  name     = google_cloud_run_v2_service.mcp.name
  location = var.region
  role     = "roles/run.invoker"
  member   = each.value
}
