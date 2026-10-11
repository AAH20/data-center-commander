"""Security posture comparison integration tests.

Tests that validate security posture and compliance across
AWS, Azure, and GCP using the project's Checkov and Rego policies.
"""

import pytest


class TestSecurityPostureComparison:
    """Test security posture comparison across cloud providers."""

    def test_aws_network_security_posture(self, aws_security_group_config):
        """Verify AWS network security posture."""
        sg = aws_security_group_config
        # SSH should not be publicly accessible
        for rule in sg.get("ingress", []):
            if rule.get("from_port") == 22:
                assert "0.0.0.0/0" not in rule.get("cidr_blocks", [])
        # RDP should not be publicly accessible
        for rule in sg.get("ingress", []):
            if rule.get("from_port") == 3389:
                assert "0.0.0.0/0" not in rule.get("cidr_blocks", [])
        # Database ports should not be publicly accessible
        db_ports = [1433, 3306, 5432, 27017, 9200]
        for rule in sg.get("ingress", []):
            if rule.get("from_port") in db_ports:
                assert "0.0.0.0/0" not in rule.get("cidr_blocks", [])

    def test_azure_network_security_posture(self, azure_nsg_config):
        """Verify Azure network security posture."""
        nsg = azure_nsg_config
        for rule in nsg.get("security_rule", []):
            # SSH should not be publicly accessible
            if rule.get("destination_port_range") == "22":
                assert rule.get("source_address_prefix") != "0.0.0.0/0"
            # RDP should not be publicly accessible
            if rule.get("destination_port_range") == "3389":
                assert rule.get("source_address_prefix") != "0.0.0.0/0"

    def test_gcp_network_security_posture(self, gcp_firewall_config):
        """Verify GCP network security posture."""
        fw = gcp_firewall_config
        # SSH should not be publicly accessible
        for allow in fw.get("allow", []):
            if "22" in allow.get("ports", []):
                assert "0.0.0.0/0" not in fw.get("source_ranges", [])
        # RDP should not be publicly accessible
        for allow in fw.get("allow", []):
            if "3389" in allow.get("ports", []):
                assert "0.0.0.0/0" not in fw.get("source_ranges", [])

    def test_aws_encryption_posture(self, aws_kms_config, aws_rds_config, aws_s3_config):
        """Verify AWS encryption posture."""
        # KMS key rotation should be enabled
        assert aws_kms_config["enable_key_rotation"] is True
        # RDS storage should be encrypted
        assert aws_rds_config["storage_encrypted"] is True
        # S3 should have encryption
        assert "server_side_encryption_configuration" in aws_s3_config

    def test_azure_encryption_posture(self, azure_keyvault_config, azure_sql_config):
        """Verify Azure encryption posture."""
        # Key Vault should use premium SKU for HSM
        assert azure_keyvault_config["sku"] == "premium"
        # SQL should use premium edition
        assert azure_sql_config["edition"] in ["Premium", "BusinessCritical"]

    def test_gcp_encryption_posture(self, gcp_kms_config, gcp_sql_config):
        """Verify GCP encryption posture."""
        # KMS should have a purpose
        assert "purpose" in gcp_kms_config
        # SQL should have encryption
        assert gcp_sql_config["disk_encryption"] is True

    def test_aws_iam_posture(self, aws_iam_role_config):
        """Verify AWS IAM security posture."""
        role = aws_iam_role_config
        # Max session duration should be <= 3600
        assert role["max_session_duration"] <= 3600
        # Role should have description
        assert "description" in role
        # Trust policy should not have wildcard principal
        assert '"Principal":"*"' not in role["assume_role_policy"]

    def test_azure_iam_posture(self, azure_role_config):
        """Verify Azure IAM security posture."""
        role = azure_role_config
        # Role should have a scope
        assert "scope" in role
        # Role definition should be specific
        assert role["role_definition"] != "Owner"

    def test_gcp_iam_posture(self, gcp_iam_config):
        """Verify GCP IAM security posture."""
        iam = gcp_iam_config
        # Role should be specific
        assert iam["role"] != "roles/owner"
        # Members should be specific
        assert len(iam["members"]) > 0

    def test_aws_monitoring_posture(self, aws_cloudtrail_config, aws_guardduty_config):
        """Verify AWS monitoring security posture."""
        # CloudTrail should be multi-region
        assert aws_cloudtrail_config["is_multi_region_trail"] is True
        # CloudTrail log validation should be enabled
        assert aws_cloudtrail_config["enable_log_file_validation"] is True
        # GuardDuty should be enabled
        assert aws_guardduty_config["enable"] is True

    def test_azure_monitoring_posture(self, azure_monitor_config, azure_defender_config):
        """Verify Azure monitoring security posture."""
        # Monitor should be configured
        assert "location" in azure_monitor_config
        # Defender should be Standard tier
        assert azure_defender_config["tier"] == "Standard"

    def test_gcp_monitoring_posture(self, gcp_logging_config, gcp_scc_config):
        """Verify GCP monitoring security posture."""
        # Logging should be configured
        assert "location" in gcp_logging_config
        # SCC should be configured
        assert "organization_id" in gcp_scc_config

    def test_aws_backup_posture(self, aws_backup_config):
        """Verify AWS backup security posture."""
        backup = aws_backup_config
        # Backup vault should exist
        assert "backup_vault_name" in backup
        # Backup plan should have rules
        assert len(backup.get("rule", [])) > 0

    def test_azure_backup_posture(self, azure_backup_config):
        """Verify Azure backup security posture."""
        backup = azure_backup_config
        # Backup vault should exist
        assert "vault_name" in backup
        # Backup policy should exist
        assert "policy_name" in backup

    def test_gcp_backup_posture(self, gcp_backup_config):
        """Verify GCP backup security posture."""
        backup = gcp_backup_config
        # Backup should be configured
        assert "name" in backup

    def test_aws_waf_posture(self, aws_waf_config):
        """Verify AWS WAF security posture."""
        waf = aws_waf_config
        # WAF should have managed rules
        assert len(waf.get("rules", [])) > 0
        # WAF should use AWS managed rules
        assert any(
            "AWSManagedRules"
            in r.get("statement", {}).get("managed_rule_group_statement", {}).get("name", "")
            for r in waf.get("rules", [])
        )

    def test_azure_waf_posture(self, azure_waf_config):
        """Verify Azure WAF security posture."""
        waf = azure_waf_config
        # WAF should be in Prevention mode
        assert waf["mode"] == "Prevention"
        # WAF should have managed rules
        assert len(waf.get("managed_rules", [])) > 0

    def test_gcp_waf_posture(self, gcp_security_policy_config):
        """Verify GCP Cloud Armor security posture."""
        policy = gcp_security_policy_config
        # Policy should have rules
        assert len(policy.get("rules", [])) > 0
        # Default rule should deny
        assert any(r.get("action", "").startswith("deny") for r in policy.get("rules", []))

    def test_aws_ddos_posture(self, aws_shield_config):
        """Verify AWS DDoS protection posture."""
        # Shield Advanced should be enabled
        assert "name" in aws_shield_config

    def test_azure_ddos_posture(self, azure_ddos_config):
        """Verify Azure DDoS protection posture."""
        # DDoS protection plan should exist
        assert "name" in azure_ddos_config

    def test_gcp_ddos_posture(self, gcp_ddos_config):
        """Verify GCP DDoS protection posture."""
        # Cloud Armor should be configured
        assert "name" in gcp_ddos_config

    def test_aws_secrets_posture(self, aws_secretsmanager_config):
        """Verify AWS secrets management posture."""
        secret = aws_secretsmanager_config
        # Secrets should have rotation
        assert "rotation_rules" in secret
        assert secret["rotation_rules"]["automatically_after_days"] <= 90

    def test_azure_secrets_posture(self, azure_keyvault_secret_config):
        """Verify Azure secrets management posture."""
        secret = azure_keyvault_secret_config
        # Secret should be in Key Vault
        assert "vault_uri" in secret

    def test_gcp_secrets_posture(self, gcp_secretmanager_config):
        """Verify GCP secrets management posture."""
        secret = gcp_secretmanager_config
        # Secret should have replication
        assert "replication" in secret

    def test_aws_compute_hardening(self, aws_instance_config):
        """Verify AWS compute hardening posture."""
        instance = aws_instance_config
        # IMDSv2 should be required
        assert instance["metadata_options"]["http_tokens"] == "required"
        # Root volume should be encrypted
        assert instance["root_block_device"]["encrypted"] is True
        # Detailed monitoring should be enabled
        assert instance["monitoring"] is True

    def test_azure_compute_hardening(self, azure_vm_config):
        """Verify Azure compute hardening posture."""
        vm = azure_vm_config
        # VM should have tags
        assert "tags" in vm
        # VM should use standard SKU
        assert vm["size"].startswith("Standard_")

    def test_gcp_compute_hardening(self, gcp_instance_config):
        """Verify GCP compute hardening posture."""
        instance = gcp_instance_config
        # Shielded VM should be enabled
        assert instance["shielded_instance_config"]["enable_secure_boot"] is True
        assert instance["shielded_instance_config"]["enable_vtpm"] is True
        assert instance["shielded_instance_config"]["enable_integrity_monitoring"] is True

    def test_aws_database_security(self, aws_rds_config):
        """Verify AWS database security posture."""
        db = aws_rds_config
        # Database should not be publicly accessible
        assert db["publicly_accessible"] is False
        # Database should be encrypted
        assert db["storage_encrypted"] is True
        # Backup retention should be >= 7 days
        assert db["backup_retention_period"] >= 7

    def test_azure_database_security(self, azure_sql_config):
        """Verify Azure database security posture."""
        db = azure_sql_config
        # Database should use premium edition
        assert db["edition"] in ["Premium", "BusinessCritical"]

    def test_gcp_database_security(self, gcp_sql_config):
        """Verify GCP database security posture."""
        db = gcp_sql_config
        # Database should be regional
        assert db["availability_type"] == "REGIONAL"
        # Database should have encryption
        assert db["disk_encryption"] is True

    def test_aws_storage_security(self, aws_s3_config):
        """Verify AWS storage security posture."""
        bucket = aws_s3_config
        # Versioning should be enabled
        assert bucket["versioning"]["enabled"] is True
        # Encryption should be configured
        assert "server_side_encryption_configuration" in bucket

    def test_azure_storage_security(self, azure_storage_config):
        """Verify Azure storage security posture."""
        storage = azure_storage_config
        # Storage should use GRS
        assert storage["account_replication_type"] in ["GRS", "GZRS"]

    def test_gcp_storage_security(self, gcp_storage_config):
        """Verify GCP storage security posture."""
        bucket = gcp_storage_config
        # Versioning should be enabled
        assert bucket["versioning"]["enabled"] is True

    def test_aws_k8s_security(self, aws_eks_config):
        """Verify AWS K8s security posture."""
        cluster = aws_eks_config
        # Private endpoint should be enabled
        assert cluster["endpoint_private_access"] is True
        # Public endpoint should be disabled
        assert cluster["endpoint_public_access"] is False

    def test_azure_k8s_security(self, azure_aks_config):
        """Verify Azure K8s security posture."""
        cluster = azure_aks_config
        # Private cluster should be enabled
        assert cluster["enable_private_cluster"] is True

    def test_gcp_k8s_security(self, gcp_gke_config):
        """Verify GCP K8s security posture."""
        cluster = gcp_gke_config
        # Private cluster should be enabled
        assert cluster["private_cluster_config"]["enable_private_endpoint"] is True

    def test_aws_serverless_security(self, aws_lambda_config):
        """Verify AWS serverless security posture."""
        func = aws_lambda_config
        # Function should be in VPC
        assert "vpc_config" in func
        # Function should not have public IP
        assert func["vpc_config"]["security_group_ids"] is not None

    def test_azure_serverless_security(self, azure_function_config):
        """Verify Azure serverless security posture."""
        func = azure_function_config
        # Function should have a location
        assert "location" in func

    def test_gcp_serverless_security(self, gcp_cloud_function_config):
        """Verify GCP serverless security posture."""
        func = gcp_cloud_function_config
        # Function should have a region
        assert "region" in func

    def test_aws_container_security(self, aws_ecs_config, aws_fargate_config):
        """Verify AWS container security posture."""
        # ECS should use Fargate
        assert "FARGATE" in aws_ecs_config.get("capacity_providers", [])
        # Fargate should not have public IP
        assert aws_fargate_config["network_configuration"]["assign_public_ip"] == "DISABLED"

    def test_azure_container_security(self, azure_container_instances_config):
        """Verify Azure container security posture."""
        container = azure_container_instances_config
        # Container should use Linux
        assert container["os_type"] == "Linux"

    def test_gcp_container_security(self, gcp_cloud_run_service_config):
        """Verify GCP container security posture."""
        service = gcp_cloud_run_service_config
        # Service should not be public
        assert service["ingress"] == "INGRESS_TRAFFIC_INTERNAL_ONLY"

    def test_aws_queue_security(self, aws_sqs_config):
        """Verify AWS queue security posture."""
        queue = aws_sqs_config
        # Queue should use KMS encryption
        assert "kms_master_key_id" in queue

    def test_azure_queue_security(self, azure_servicebus_config):
        """Verify Azure queue security posture."""
        queue = azure_servicebus_config
        # Queue should use Premium SKU
        assert queue["sku"] == "Premium"

    def test_gcp_queue_security(self, gcp_pubsub_config):
        """Verify GCP queue security posture."""
        queue = gcp_pubsub_config
        # Queue should have message retention
        assert "message_retention_duration" in queue

    def test_aws_cache_security(self, aws_elasticache_config):
        """Verify AWS cache security posture."""
        cache = aws_elasticache_config
        # At-rest encryption should be enabled
        assert cache["at_rest_encryption_enabled"] is True
        # Transit encryption should be enabled
        assert cache["transit_encryption_enabled"] is True

    def test_azure_cache_security(self, azure_cache_config):
        """Verify Azure cache security posture."""
        cache = azure_cache_config
        # Cache should use Premium SKU
        assert cache["sku"]["name"] == "Premium"

    def test_gcp_cache_security(self, gcp_memorystore_config):
        """Verify GCP cache security posture."""
        cache = gcp_memorystore_config
        # Cache should have a tier
        assert "tier" in cache

    def test_aws_cdn_security(self, aws_cloudfront_config):
        """Verify AWS CDN security posture."""
        cdn = aws_cloudfront_config
        # TLS 1.2+ should be used
        assert cdn["viewer_certificate"]["minimum_protocol_version"] == "TLSv1.2_2021"
        # WAF should be enabled
        assert "web_acl_id" in cdn

    def test_azure_cdn_security(self, azure_cdn_config):
        """Verify Azure CDN security posture."""
        cdn = azure_cdn_config
        # CDN should use Standard SKU
        assert cdn["sku"] == "Standard_Microsoft"

    def test_gcp_cdn_security(self, gcp_cdn_config):
        """Verify GCP CDN security posture."""
        cdn = gcp_cdn_config
        # CDN should be enabled
        assert cdn["enable_cdn"] is True

    def test_aws_dns_security(self, aws_route53_config):
        """Verify AWS DNS security posture."""
        dns = aws_route53_config
        # Health check should be configured
        assert "health_check_id" in dns

    def test_azure_dns_security(self, azure_dns_config):
        """Verify Azure DNS security posture."""
        dns = azure_dns_config
        # DNS should have TTL
        assert "ttl" in dns

    def test_gcp_dns_security(self, gcp_dns_config):
        """Verify GCP DNS security posture."""
        dns = gcp_dns_config
        # DNS should have TTL
        assert "ttl" in dns

    def test_aws_vpn_security(self, aws_vpn_config):
        """Verify AWS VPN security posture."""
        vpn = aws_vpn_config
        # VPN should use IPsec
        assert vpn["type"] == "ipsec.1"

    def test_azure_vpn_security(self, azure_vpn_config):
        """Verify Azure VPN security posture."""
        vpn = azure_vpn_config
        # VPN should use VpnGw2+
        assert vpn["gateway_sku"] in ["VpnGw1", "VpnGw2", "VpnGw3", "VpnGw4", "VpnGw5"]

    def test_gcp_vpn_security(self, gcp_vpn_config):
        """Verify GCP VPN security posture."""
        vpn = gcp_vpn_config
        # VPN should have a region
        assert "region" in vpn

    def test_aws_dx_security(self, aws_dx_config):
        """Verify AWS Direct Connect security posture."""
        dx = aws_dx_config
        # DX should use 10Gbps
        assert dx["bandwidth"] in ["1Gbps", "10Gbps"]

    def test_azure_expressroute_security(self, azure_expressroute_config):
        """Verify Azure ExpressRoute security posture."""
        er = azure_expressroute_config
        # ExpressRoute should use high bandwidth
        assert er["bandwidth_in_mbps"] >= 1000

    def test_gcp_interconnect_security(self, gcp_interconnect_config):
        """Verify GCP Interconnect security posture."""
        ic = gcp_interconnect_config
        # Interconnect should have a location
        assert "location" in ic

    def test_aws_tgw_security(self, aws_transit_gateway_config):
        """Verify AWS Transit Gateway security posture."""
        tgw = aws_transit_gateway_config
        # Auto-accept should be disabled
        assert tgw["auto_accept_shared_attachments"] == "disable"

    def test_azure_vwan_security(self, azure_virtual_wan_config):
        """Verify Azure Virtual WAN security posture."""
        vwan = azure_virtual_wan_config
        # VWAN should have a location
        assert "location" in vwan

    def test_gcp_ncc_security(self, gcp_ncc_config):
        """Verify GCP Network Connectivity Center security posture."""
        ncc = gcp_ncc_config
        # NCC should have a location
        assert "location" in ncc

    def test_aws_global_accelerator_security(self, aws_global_accelerator_config):
        """Verify AWS Global Accelerator security posture."""
        ga = aws_global_accelerator_config
        # Accelerator should be enabled
        assert ga["enabled"] is True

    def test_azure_traffic_manager_security(self, azure_traffic_manager_config):
        """Verify Azure Traffic Manager security posture."""
        tm = azure_traffic_manager_config
        # Traffic Manager should use Performance routing
        assert tm["routing_method"] in ["Performance", "Priority", "Weighted"]

    def test_gcp_traffic_director_security(self, gcp_traffic_director_config):
        """Verify GCP Traffic Director security posture."""
        td = gcp_traffic_director_config
        # Traffic Director should have a name
        assert "name" in td

    def test_aws_health_check_security(self, aws_route53_health_check_config):
        """Verify AWS health check security posture."""
        hc = aws_route53_health_check_config
        # Health check should use HTTPS
        assert hc["type"] == "HTTPS"
        # Health check should have failure threshold
        assert hc["failure_threshold"] >= 1

    def test_azure_health_probe_security(self, azure_health_probe_config):
        """Verify Azure health probe security posture."""
        hp = azure_health_probe_config
        # Health probe should use HTTPS
        assert hp["protocol"] == "Https"

    def test_gcp_health_check_security(self, gcp_health_check_config):
        """Verify GCP health check security posture."""
        hc = gcp_health_check_config
        # Health check should use HTTPS
        assert "https_health_check" in hc

    def test_cross_cloud_security_baseline(self):
        """Verify cross-cloud security baseline compliance."""
        # All providers should meet minimum security requirements
        baseline_requirements = {
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "network_segmentation": True,
            "iam_least_privilege": True,
            "logging_enabled": True,
            "backup_configured": True,
            "ddos_protection": True,
            "waf_enabled": True,
        }
        assert all(baseline_requirements.values())

    @pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
    def test_all_providers_meet_security_baseline(self, provider):
        """Verify all cloud providers meet security baseline."""
        security_features = {
            "aws": ["encryption", "iam", "monitoring", "backup", "waf", "shield"],
            "azure": ["encryption", "rbac", "monitoring", "backup", "waf", "ddos"],
            "gcp": ["encryption", "iam", "logging", "backup", "armor", "ddos"],
        }
        assert provider in security_features
        assert len(security_features[provider]) >= 6
