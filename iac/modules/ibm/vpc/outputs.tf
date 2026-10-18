output "vpc_id" {
  description = "ID of the created VPC"
  value       = ibm_is_vpc.this.id
}

output "vpc_crn" {
  description = "CRN of the created VPC"
  value       = ibm_is_vpc.this.crn
}

output "vpc_name" {
  description = "Name of the created VPC"
  value       = ibm_is_vpc.this.name
}

output "subnet_ids" {
  description = "Map of subnet names to IDs"
  value       = { for k, v in ibm_is_subnet.this : k => v.id }
}

output "subnet_crns" {
  description = "Map of subnet names to CRNs"
  value       = { for k, v in ibm_is_subnet.this : k => v.crn }
}

output "public_gateway_ids" {
  description = "Map of public gateway names to IDs"
  value       = { for k, v in ibm_is_public_gateway.this : k => v.id }
}

output "security_group_id" {
  description = "ID of the security group (if created)"
  value       = var.create_security_group ? ibm_is_security_group.this[0].id : null
}

output "network_acl_id" {
  description = "ID of the network ACL (if created)"
  value       = var.create_network_acl ? ibm_is_network_acl.this[0].id : null
}

output "flow_log_id" {
  description = "ID of the flow log (if enabled)"
  value       = var.enable_flow_logs ? ibm_is_flow_log.this[0].id : null
}
