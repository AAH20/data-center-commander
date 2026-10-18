output "instance_ids" {
  description = "List of EC2 instance IDs"
  value       = aws_instance.this[*].id
}

output "instance_public_ips" {
  description = "List of public IPs"
  value       = aws_instance.this[*].public_ip
}

output "instance_private_ips" {
  description = "List of private IPs"
  value       = aws_instance.this[*].private_ip
}

output "elastic_ips" {
  description = "List of Elastic IPs"
  value       = var.assign_elastic_ip ? aws_eip.this[*].public_ip : []
}
