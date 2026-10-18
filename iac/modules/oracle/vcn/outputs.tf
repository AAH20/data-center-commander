output "vcn_id" {
  description = "ID of the created VCN"
  value       = oci_core_vcn.this.id
}

output "vcn_name" {
  description = "Display name of the created VCN"
  value       = oci_core_vcn.this.display_name
}

output "subnet_ids" {
  description = "Map of subnet names to IDs"
  value       = { for k, v in oci_core_subnet.this : k => v.id }
}

output "internet_gateway_id" {
  description = "ID of the internet gateway (if created)"
  value       = var.create_internet_gateway ? oci_core_internet_gateway.this[0].id : null
}

output "route_table_id" {
  description = "ID of the route table (if created)"
  value       = var.create_route_table ? oci_core_route_table.this[0].id : null
}

output "security_list_id" {
  description = "ID of the security list (if created)"
  value       = var.create_security_list ? oci_core_security_list.this[0].id : null
}
