variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "europe-west4"
}

variable "github_repository" {
  type        = string
  description = "owner/name of the repository whose workflow may deploy (WIF attribute condition)."
}

variable "reader_identities" {
  type        = list(string)
  description = "IAM members (serviceAccount:... or principal://...) that get the reader role and run.invoker."
  default     = []
}

variable "admin_identities" {
  type        = list(string)
  description = "IAM members that get the admin role and run.invoker."
  default     = []
}

variable "enable_psc_attachment" {
  type        = bool
  description = "Create a network attachment for callers that have no VPC of their own (Agent Runtime engines)."
  default     = false
}
