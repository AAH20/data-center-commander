output "enabled_policies" {
  description = "Map of enabled organization policy constraint names to their resource IDs"
  value = merge(
    var.disable_serial_port ? { "compute.disableSerialPortAccess" = google_org_policy_policy.disable_serial_port[0].id } : {},
    var.require_os_login ? { "compute.requireOsLogin" = google_org_policy_policy.require_os_login[0].id } : {},
    var.restrict_vm_external_ips ? { "compute.vmExternalIpAccess" = google_org_policy_policy.restrict_vm_external_ips[0].id } : {},
    var.enforce_uniform_bucket_level_access ? { "storage.uniformBucketLevelAccess" = google_org_policy_policy.uniform_bucket_level_access[0].id } : {},
    var.restrict_public_ip_cloudsql ? { "sql.restrictPublicIp" = google_org_policy_policy.restrict_public_ip_cloudsql[0].id } : {},
    var.disable_sa_key_creation ? { "iam.disableServiceAccountKeyCreation" = google_org_policy_policy.disable_sa_key_creation[0].id } : {},
    var.disable_sa_key_upload ? { "iam.disableServiceAccountKeyUpload" = google_org_policy_policy.disable_sa_key_upload[0].id } : {},
    var.require_vpc_flow_logs ? { "compute.requireVpcFlowLogs" = google_org_policy_policy.require_vpc_flow_logs[0].id } : {},
    var.restrict_vpc_peering ? { "compute.restrictVpcPeering" = google_org_policy_policy.restrict_vpc_peering[0].id } : {},
    var.restrict_vpn_peer_ips ? { "compute.restrictVpnPeerIPs" = google_org_policy_policy.restrict_vpn_peer_ips[0].id } : {},
    var.disable_default_network ? { "compute.skipDefaultNetworkCreation" = google_org_policy_policy.disable_default_network[0].id } : {},
    var.require_shielded_vms ? { "compute.requireShieldedVm" = google_org_policy_policy.require_shielded_vms[0].id } : {},
    var.restrict_cloud_nat ? { "compute.restrictCloudNAT" = google_org_policy_policy.restrict_cloud_nat[0].id } : {},
    var.restrict_lb_creation ? { "compute.restrictLoadBalancerCreation" = google_org_policy_policy.restrict_lb_creation[0].id } : {},
    var.restrict_shared_vpc ? { "compute.restrictSharedVpcProjects" = google_org_policy_policy.restrict_shared_vpc[0].id } : {},
    var.restrict_xpn_project_creation ? { "compute.restrictXpnProjectCreation" = google_org_policy_policy.restrict_xpn_project_creation[0].id } : {},
    { for k, v in google_org_policy_custom_constraint.custom : k => v.id }
  )
}
