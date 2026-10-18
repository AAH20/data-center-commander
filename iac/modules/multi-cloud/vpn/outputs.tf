output "aws_vpn_gateway_id" {
  description = "AWS VPN gateway ID"
  value       = var.aws_vpc_id != null ? aws_vpn_gateway.this[0].id : null
}

output "aws_vpn_connection_id" {
  description = "AWS VPN connection ID"
  value       = var.aws_vpc_id != null && var.gcp_network_id != null ? aws_vpn_connection.to_gcp[0].id : null
}

output "gcp_vpn_gateway_id" {
  description = "GCP VPN gateway ID"
  value       = var.gcp_network_id != null ? google_compute_ha_vpn_gateway.this[0].id : null
}

output "gcp_vpn_tunnel_id" {
  description = "GCP VPN tunnel ID"
  value       = var.aws_vpc_id != null && var.gcp_network_id != null ? google_compute_vpn_tunnel.to_aws[0].id : null
}

output "vpn_shared_key" {
  description = "VPN shared key"
  value       = local.shared_key
  sensitive   = true
}
