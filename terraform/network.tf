resource "google_compute_network" "main" {
  name                    = "mcp-vpc"
  auto_create_subnetworks = false
  depends_on              = [google_project_service.services]
}

resource "google_compute_subnetwork" "run_egress" {
  name                     = "run-egress"
  region                   = var.region
  network                  = google_compute_network.main.id
  ip_cidr_range            = "10.10.0.0/24"
  private_ip_google_access = true
}

# ALL_TRAFFIC egress sends even public destinations through the VPC; Cloud NAT is
# what lets those packets leave it.
resource "google_compute_router" "main" {
  name    = "mcp-router"
  region  = var.region
  network = google_compute_network.main.id
}

resource "google_compute_router_nat" "main" {
  name                               = "mcp-nat"
  router                             = google_compute_router.main.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"
}

# Only for callers outside the VPC (Agent Runtime engines). Whether such a caller can
# reach an INTERNAL_ONLY service by its public hostname is unverified -- test it.
resource "google_compute_subnetwork" "psc" {
  count         = var.enable_psc_attachment ? 1 : 0
  name          = "psc-attachment"
  region        = var.region
  network       = google_compute_network.main.id
  ip_cidr_range = "10.10.1.0/24"
}

resource "google_compute_network_attachment" "engines" {
  count                 = var.enable_psc_attachment ? 1 : 0
  name                  = "engines"
  region                = var.region
  connection_preference = "ACCEPT_AUTOMATIC"
  subnetworks           = [google_compute_subnetwork.psc[0].id]
}
