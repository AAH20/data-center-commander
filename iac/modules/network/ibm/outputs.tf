output "vpc_id" {
  description = "ID of the VPC"
  value       = ibm_is_vpc.this.id
}

output "vpc_crn" {
  description = "CRN of the VPC"
  value       = ibm_is_vpc.this.crn
}

output "subnet_id" {
  description = "ID of the subnet"
  value       = ibm_is_subnet.this.id
}

output "subnet_crn" {
  description = "CRN of the subnet"
  value       = ibm_is_subnet.this.crn
}

output "security_group_id" {
  description = "ID of the security group"
  value       = ibm_is_security_group.this.id
}

output "public_gateway_id" {
  description = "ID of the public gateway"
  value       = var.enable_public_gateway ? ibm_is_public_gateway.this[0].id : null
}
