locals {
  # Agent Gateway policy: readers may reach only read-only tools; admins everything.
  # Conditions use IAP's MCP attributes. List tool names rather than relying on
  # isReadOnly alone -- a tool can be read-only and still admin-tier.
  read_tools = ["list_notes", "get_note"]

  reader_condition = join(" && ", [
    "api.getAttribute('iap.googleapis.com/mcp.tool.isReadOnly', false) == true",
    "api.getAttribute('iap.googleapis.com/mcp.toolName', '') in [${join(", ", [for t in local.read_tools : "'${t}'"])}]",
  ])

  iap_bindings = concat(
    length(var.reader_identities) == 0 ? [] : [{
      role    = "roles/iap.egressor"
      members = var.reader_identities
      condition = {
        title       = "Read-only MCP tools"
        description = "Query tools only"
        expression  = local.reader_condition
      }
    }],
    length(var.admin_identities) == 0 ? [] : [{
      role    = "roles/iap.egressor"
      members = var.admin_identities
    }],
  )
}
