output "instance_ids" {
  description = "IDs of EC2 instances"
  value       = aws_instance.this[*].id
}

output "instance_public_ips" {
  description = "Public IPs of EC2 instances"
  value       = var.enable_elastic_ip ? aws_eip.this[*].public_ip : aws_instance.this[*].public_ip
}

output "instance_private_ips" {
  description = "Private IPs of EC2 instances"
  value       = aws_instance.this[*].private_ip
}

output "ami_id" {
  description = "AMI ID used for instances"
  value       = data.aws_ami.ubuntu.id
}
