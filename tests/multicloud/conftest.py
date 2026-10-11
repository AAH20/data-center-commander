"""Shared fixtures for multi-cloud integration tests."""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CLOUD_PROVIDERS = ["aws", "azure", "gcp"]


@pytest.fixture
def aws_vpc_config():
    return {"cidr_block": "10.0.0.0/16", "tags": {"Name": "prod-vpc", "Environment": "production"}}


@pytest.fixture
def azure_vnet_config():
    return {"address_space": ["10.0.0.0/16"], "location": "eastus", "tags": {"Name": "prod-vnet"}}


@pytest.fixture
def gcp_vpc_config():
    return {"name": "prod-vpc", "auto_create_subnetworks": False}


@pytest.fixture
def aws_security_group_config():
    return {
        "name": "prod-web-sg",
        "description": "Production web security group",
        "ingress": [
            {"from_port": 443, "to_port": 443, "protocol": "tcp", "cidr_blocks": ["0.0.0.0/0"]}
        ],
        "tags": {"Name": "prod-web-sg", "Environment": "production"},
    }


@pytest.fixture
def azure_nsg_config():
    return {
        "name": "prod-web-nsg",
        "location": "eastus",
        "security_rule": [
            {
                "name": "AllowHTTPS",
                "destination_port_range": "443",
                "source_address_prefix": "Internet",
            }
        ],
    }


@pytest.fixture
def gcp_firewall_config():
    return {
        "name": "prod-web-firewall",
        "network": "prod-vpc",
        "source_ranges": ["0.0.0.0/0"],
        "allow": [{"protocol": "tcp", "ports": ["443"]}],
    }


@pytest.fixture
def aws_rds_config():
    return {
        "identifier": "prod-db",
        "engine": "postgres",
        "instance_class": "db.r6g.xlarge",
        "storage_encrypted": True,
        "multi_az": True,
        "backup_retention_period": 30,
        "publicly_accessible": False,
        "tags": {"Name": "prod-db"},
    }


@pytest.fixture
def azure_sql_config():
    return {"name": "prod-sql", "location": "eastus", "edition": "Premium"}


@pytest.fixture
def gcp_sql_config():
    return {
        "name": "prod-db",
        "database_version": "POSTGRES_15",
        "region": "us-central1",
        "tier": "db-custom-4-16384",
        "availability_type": "REGIONAL",
        "disk_encryption": True,
    }


@pytest.fixture
def aws_s3_config():
    return {
        "bucket": "prod-data-bucket",
        "versioning": {"enabled": True},
        "server_side_encryption_configuration": {
            "rule": {"apply_server_side_encryption_by_default": {"sse_algorithm": "aws:kms"}}
        },
    }


@pytest.fixture
def azure_storage_config():
    return {"name": "proddatabucket", "account_tier": "Standard", "account_replication_type": "GRS"}


@pytest.fixture
def gcp_storage_config():
    return {
        "name": "prod-data-bucket",
        "location": "US-CENTRAL1",
        "storage_class": "STANDARD",
        "versioning": {"enabled": True},
    }


@pytest.fixture
def aws_instance_config():
    return {
        "instance_type": "m6i.xlarge",
        "monitoring": True,
        "metadata_options": {"http_tokens": "required"},
        "root_block_device": {"encrypted": True},
        "associate_public_ip_address": False,
        "tags": {"Name": "prod-app-1", "Environment": "production"},
    }


@pytest.fixture
def azure_vm_config():
    return {
        "name": "prod-app-1",
        "location": "eastus",
        "size": "Standard_D4s_v5",
        "tags": {"Name": "prod-app-1", "Environment": "production"},
    }


@pytest.fixture
def gcp_instance_config():
    return {
        "name": "prod-app-1",
        "machine_type": "n2-standard-4",
        "zone": "us-central1-a",
        "shielded_instance_config": {
            "enable_secure_boot": True,
            "enable_vtpm": True,
            "enable_integrity_monitoring": True,
        },
    }


@pytest.fixture
def aws_kms_config():
    return {"description": "Production encryption key", "enable_key_rotation": True}


@pytest.fixture
def azure_keyvault_config():
    return {"name": "prod-keyvault", "location": "eastus", "sku": "premium"}


@pytest.fixture
def gcp_kms_config():
    return {"name": "prod-key", "location": "us-central1", "purpose": "ENCRYPT_DECRYPT"}


@pytest.fixture
def aws_autoscaling_config():
    return {
        "min_size": 2,
        "max_size": 10,
        "desired_capacity": 4,
        "health_check_type": "ELB",
        "availability_zones": ["us-east-1a", "us-east-1b", "us-east-1c"],
    }


@pytest.fixture
def azure_vmss_config():
    return {
        "name": "prod-vmss",
        "location": "eastus",
        "sku": {"name": "Standard_D4s_v5", "capacity": 4},
    }


@pytest.fixture
def gcp_mig_config():
    return {
        "name": "prod-mig",
        "zone": "us-central1-a",
        "target_size": 4,
        "auto_healing_policies": [{"initial_delay_sec": 300}],
    }


@pytest.fixture
def aws_lb_config():
    return {
        "name": "prod-alb",
        "load_balancer_type": "application",
        "cross_zone_load_balancing": True,
    }


@pytest.fixture
def azure_lb_config():
    return {"name": "prod-lb", "location": "eastus", "sku": "Standard"}


@pytest.fixture
def gcp_lb_config():
    return {"name": "prod-lb", "region": "us-central1"}


@pytest.fixture
def aws_route53_config():
    return {
        "zone_id": "Z1234567890",
        "name": "app.example.com",
        "type": "A",
        "health_check_id": "abc123",
    }


@pytest.fixture
def azure_dns_config():
    return {"name": "app.example.com", "zone_name": "example.com", "ttl": 300}


@pytest.fixture
def gcp_dns_config():
    return {"name": "app.example.com.", "zone": "example-com", "type": "A", "ttl": 300}


@pytest.fixture
def aws_cloudfront_config():
    return {
        "enabled": True,
        "viewer_certificate": {"minimum_protocol_version": "TLSv1.2_2021"},
        "web_acl_id": "arn:aws:wafv2:us-east-1:123456789:global/webacl/prod/abc",
    }


@pytest.fixture
def azure_cdn_config():
    return {"name": "prod-cdn", "location": "eastus", "sku": "Standard_Microsoft"}


@pytest.fixture
def gcp_cdn_config():
    return {"name": "prod-cdn", "enable_cdn": True}


@pytest.fixture
def aws_backup_config():
    return {
        "backup_vault_name": "prod-backup-vault",
        "plan_name": "prod-backup-plan",
        "rule": [{"rule_name": "daily-backup"}],
    }


@pytest.fixture
def azure_backup_config():
    return {"vault_name": "prod-backup-vault", "policy_name": "prod-backup-policy"}


@pytest.fixture
def gcp_backup_config():
    return {"name": "prod-backup", "region": "us-central1"}


@pytest.fixture
def aws_guardduty_config():
    return {"enable": True}


@pytest.fixture
def azure_defender_config():
    return {"tier": "Standard", "extensions": [{"name": "Servers", "tier": "Standard"}]}


@pytest.fixture
def gcp_scc_config():
    return {"organization_id": "123456789", "location": "global"}


@pytest.fixture
def aws_cloudtrail_config():
    return {
        "name": "prod-trail",
        "is_multi_region_trail": True,
        "enable_log_file_validation": True,
        "s3_bucket_name": "prod-cloudtrail-logs",
    }


@pytest.fixture
def azure_monitor_config():
    return {"name": "prod-monitor", "location": "eastus"}


@pytest.fixture
def gcp_logging_config():
    return {"name": "prod-logging", "location": "us-central1"}


@pytest.fixture
def aws_config_recorder_config():
    return {"recording_group": {"all_supported": True, "include_global_resource_types": True}}


@pytest.fixture
def azure_policy_config():
    return {"name": "prod-policy", "mode": "Indexed"}


@pytest.fixture
def gcp_org_policy_config():
    return {"constraint": "constraints/compute.vmExternalIpAccess"}


@pytest.fixture
def aws_iam_role_config():
    return {
        "name": "prod-app-role",
        "assume_role_policy": json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "ec2.amazonaws.com"},
                        "Action": "sts:AssumeRole",
                    }
                ],
            }
        ),
        "max_session_duration": 3600,
        "description": "Production application role",
    }


@pytest.fixture
def azure_role_config():
    return {
        "name": "prod-app-role",
        "role_definition": "Contributor",
        "scope": "/subscriptions/123456789/resourceGroups/prod",
    }


@pytest.fixture
def gcp_iam_config():
    return {
        "role": "roles/compute.instanceAdmin",
        "members": ["serviceAccount:prod-app@project.iam.gserviceaccount.com"],
    }


@pytest.fixture
def aws_secretsmanager_config():
    return {
        "name": "prod/db/password",
        "description": "Production database password",
        "rotation_rules": {"automatically_after_days": 30},
    }


@pytest.fixture
def azure_keyvault_secret_config():
    return {"name": "db-password", "vault_uri": "https://prod-keyvault.vault.azure.net/"}


@pytest.fixture
def gcp_secretmanager_config():
    return {"name": "db-password", "replication": {"automatic": {}}}


@pytest.fixture
def aws_waf_config():
    return {
        "name": "prod-waf",
        "scope": "REGIONAL",
        "rules": [
            {
                "name": "AWSManagedRulesCommonRuleSet",
                "statement": {
                    "managed_rule_group_statement": {
                        "name": "AWSManagedRulesCommonRuleSet",
                        "vendor_name": "AWS",
                    }
                },
            }
        ],
    }


@pytest.fixture
def azure_waf_config():
    return {
        "name": "prod-waf",
        "mode": "Prevention",
        "managed_rules": [{"managed_rule_set": [{"type": "OWASP", "version": "3.2"}]}],
    }


@pytest.fixture
def gcp_security_policy_config():
    return {"name": "prod-security-policy", "rules": [{"action": "deny(403)", "priority": 1000}]}


@pytest.fixture
def aws_shield_config():
    return {"name": "prod-protection"}


@pytest.fixture
def azure_ddos_config():
    return {"name": "prod-ddos-plan", "location": "eastus"}


@pytest.fixture
def gcp_ddos_config():
    return {"name": "prod-ddos-policy", "edge_security_policy": True}


@pytest.fixture
def aws_vpn_config():
    return {"customer_gateway_id": "cgw-12345", "type": "ipsec.1"}


@pytest.fixture
def azure_vpn_config():
    return {"name": "prod-vpn", "location": "eastus", "gateway_sku": "VpnGw2"}


@pytest.fixture
def gcp_vpn_config():
    return {"name": "prod-vpn", "region": "us-central1"}


@pytest.fixture
def aws_dx_config():
    return {"name": "prod-dx", "bandwidth": "10Gbps", "location": "EqDC2"}


@pytest.fixture
def azure_expressroute_config():
    return {"name": "prod-expressroute", "location": "eastus", "bandwidth_in_mbps": 10000}


@pytest.fixture
def gcp_interconnect_config():
    return {"name": "prod-interconnect", "location": "us-central1"}


@pytest.fixture
def aws_transit_gateway_config():
    return {
        "description": "Production transit gateway",
        "auto_accept_shared_attachments": "disable",
    }


@pytest.fixture
def azure_virtual_wan_config():
    return {"name": "prod-vwan", "location": "eastus"}


@pytest.fixture
def gcp_ncc_config():
    return {"name": "prod-ncc", "location": "us-central1"}


@pytest.fixture
def aws_global_accelerator_config():
    return {"name": "prod-accelerator", "enabled": True}


@pytest.fixture
def azure_traffic_manager_config():
    return {"name": "prod-traffic-manager", "routing_method": "Performance"}


@pytest.fixture
def gcp_traffic_director_config():
    return {"name": "prod-traffic-director"}


@pytest.fixture
def aws_route53_health_check_config():
    return {
        "fqdn": "app.example.com",
        "port": 443,
        "type": "HTTPS",
        "resource_path": "/health",
        "request_interval": 30,
        "failure_threshold": 3,
    }


@pytest.fixture
def azure_health_probe_config():
    return {
        "name": "prod-health-probe",
        "protocol": "Https",
        "port": 443,
        "path": "/health",
        "interval_in_seconds": 30,
    }


@pytest.fixture
def gcp_health_check_config():
    return {
        "name": "prod-health-check",
        "check_interval_sec": 30,
        "healthy_threshold": 2,
        "unhealthy_threshold": 3,
        "https_health_check": {"port": 443, "request_path": "/health"},
    }


@pytest.fixture
def aws_s3_replication_config():
    return {
        "role": "arn:aws:iam::123456789:role/prod-replication",
        "rules": [{"id": "prod-replication", "status": "Enabled"}],
    }


@pytest.fixture
def azure_storage_replication_config():
    return {"account_tier": "Standard", "account_replication_type": "GRS"}


@pytest.fixture
def gcp_storage_replication_config():
    return {
        "location": "US",
        "custom_placement_config": {"data_locations": ["US-CENTRAL1", "US-EAST1"]},
    }


@pytest.fixture
def aws_dynamodb_global_table_config():
    return {
        "name": "prod-global-table",
        "replication_group": [{"region_name": "us-east-1"}, {"region_name": "us-west-2"}],
    }


@pytest.fixture
def azure_cosmos_config():
    return {"name": "prod-cosmos", "location": "eastus", "enable_multiple_write_locations": True}


@pytest.fixture
def gcp_firestore_config():
    return {"name": "prod-firestore", "location": "us-central1", "type": "FIRESTORE_NATIVE"}


@pytest.fixture
def aws_elasticache_config():
    return {
        "replication_group_id": "prod-cache",
        "node_type": "cache.r6g.xlarge",
        "num_cache_nodes": 2,
        "at_rest_encryption_enabled": True,
        "transit_encryption_enabled": True,
    }


@pytest.fixture
def azure_cache_config():
    return {
        "name": "prod-cache",
        "location": "eastus",
        "sku": {"name": "Premium", "family": "P", "capacity": 1},
    }


@pytest.fixture
def gcp_memorystore_config():
    return {
        "name": "prod-cache",
        "region": "us-central1",
        "tier": "BASIC",
        "replica_count": 1,
        "project_id": "prod-project",
    }


@pytest.fixture
def aws_lambda_config():
    return {
        "function_name": "prod-processor",
        "runtime": "python3.11",
        "memory_size": 512,
        "timeout": 30,
        "vpc_config": {"subnet_ids": ["subnet-123"], "security_group_ids": ["sg-123"]},
    }


@pytest.fixture
def azure_function_config():
    return {"name": "prod-processor", "location": "eastus", "runtime": "python", "version": "3.11"}


@pytest.fixture
def gcp_cloud_function_config():
    return {
        "name": "prod-processor",
        "region": "us-central1",
        "runtime": "python311",
        "memory": 512,
    }


@pytest.fixture
def aws_eks_config():
    return {
        "name": "prod-cluster",
        "version": "1.28",
        "endpoint_private_access": True,
        "endpoint_public_access": False,
    }


@pytest.fixture
def azure_aks_config():
    return {"name": "prod-cluster", "location": "eastus", "enable_private_cluster": True}


@pytest.fixture
def gcp_gke_config():
    return {
        "name": "prod-cluster",
        "location": "us-central1",
        "private_cluster_config": {"enable_private_endpoint": True},
    }


@pytest.fixture
def aws_sqs_config():
    return {"name": "prod-queue", "kms_master_key_id": "alias/prod-key"}


@pytest.fixture
def azure_servicebus_config():
    return {"name": "prod-queue", "location": "eastus", "sku": "Premium"}


@pytest.fixture
def gcp_pubsub_config():
    return {
        "name": "prod-queue",
        "message_retention_duration": "86400s",
        "project_id": "prod-project",
    }


@pytest.fixture
def aws_sns_config():
    return {"name": "prod-topic", "kms_master_key_id": "alias/prod-key"}


@pytest.fixture
def azure_eventgrid_config():
    return {"name": "prod-topic", "location": "eastus"}


@pytest.fixture
def gcp_pubsub_topic_config():
    return {"name": "prod-topic", "message_retention_duration": "86400s"}


@pytest.fixture
def aws_eventbridge_config():
    return {"name": "prod-event-bus"}


@pytest.fixture
def azure_eventhub_config():
    return {"name": "prod-event-hub", "location": "eastus", "partition_count": 4}


@pytest.fixture
def gcp_eventarc_config():
    return {"name": "prod-eventarc", "location": "us-central1"}


@pytest.fixture
def aws_step_functions_config():
    return {
        "name": "prod-state-machine",
        "definition": json.dumps(
            {"StartAt": "Process", "States": {"Process": {"Type": "Task", "End": True}}}
        ),
    }


@pytest.fixture
def azure_logic_app_config():
    return {"name": "prod-logic-app", "location": "eastus"}


@pytest.fixture
def gcp_workflows_config():
    return {"name": "prod-workflow", "region": "us-central1"}


@pytest.fixture
def aws_api_gateway_config():
    return {"name": "prod-api", "endpoint_configuration": {"types": ["REGIONAL"]}}


@pytest.fixture
def azure_api_management_config():
    return {"name": "prod-api", "location": "eastus", "sku": "Premium"}


@pytest.fixture
def gcp_api_gateway_config():
    return {"name": "prod-api", "region": "us-central1"}


@pytest.fixture
def aws_ecs_config():
    return {"name": "prod-cluster", "capacity_providers": ["FARGATE"]}


@pytest.fixture
def azure_container_instances_config():
    return {"name": "prod-container", "location": "eastus", "os_type": "Linux"}


@pytest.fixture
def gcp_cloud_run_config():
    return {"name": "prod-service", "region": "us-central1"}


@pytest.fixture
def aws_fargate_config():
    return {
        "cluster_name": "prod-cluster",
        "service_name": "prod-service",
        "launch_type": "FARGATE",
        "network_configuration": {"assign_public_ip": "DISABLED"},
    }


@pytest.fixture
def azure_container_apps_config():
    return {"name": "prod-container-app", "location": "eastus"}


@pytest.fixture
def gcp_cloud_run_service_config():
    return {
        "name": "prod-service",
        "region": "us-central1",
        "ingress": "INGRESS_TRAFFIC_INTERNAL_ONLY",
    }


@pytest.fixture
def aws_glue_config():
    return {"name": "prod-etl", "role": "arn:aws:iam::123456789:role/prod-glue-role"}


@pytest.fixture
def azure_data_factory_config():
    return {"name": "prod-adf", "location": "eastus"}


@pytest.fixture
def gcp_dataflow_config():
    return {"name": "prod-dataflow", "region": "us-central1"}


@pytest.fixture
def aws_athena_config():
    return {"name": "prod-athena", "encryption_option": "SSE_KMS"}


@pytest.fixture
def azure_synapse_config():
    return {"name": "prod-synapse", "location": "eastus"}


@pytest.fixture
def gcp_bigquery_config():
    return {"dataset_id": "prod_analytics", "location": "US"}


@pytest.fixture
def aws_redshift_config():
    return {
        "cluster_identifier": "prod-redshift",
        "node_type": "ra3.xlplus",
        "number_of_nodes": 3,
        "encrypted": True,
    }


@pytest.fixture
def azure_analytics_config():
    return {"name": "prod-analytics", "location": "eastus"}


@pytest.fixture
def gcp_bigtable_config():
    return {"name": "prod-bigtable", "location": "us-central1"}


@pytest.fixture
def aws_emr_config():
    return {"name": "prod-emr", "release_label": "emr-6.12.0", "applications": ["Spark", "Hadoop"]}


@pytest.fixture
def azure_hdinsight_config():
    return {"name": "prod-hdinsight", "location": "eastus", "cluster_type": "spark"}


@pytest.fixture
def gcp_dataproc_config():
    return {"name": "prod-dataproc", "region": "us-central1"}


@pytest.fixture
def aws_msk_config():
    return {
        "cluster_name": "prod-kafka",
        "number_of_broker_nodes": 3,
        "encryption_info": {
            "encryption_at_rest": {"kms_key_arn": "arn:aws:kms:us-east-1:123456789:key/abc"},
            "encryption_in_transit": {"client_broker": "TLS"},
        },
    }


@pytest.fixture
def azure_eventhub_cluster_config():
    return {"name": "prod-eventhub-cluster", "location": "eastus", "sku": "Dedicated"}


@pytest.fixture
def gcp_pubsub_lite_config():
    return {"name": "pubsub-lite", "region": "us-central1"}


@pytest.fixture
def aws_elasticbeanstalk_config():
    return {"application_name": "prod-app", "environment_name": "prod-env"}


@pytest.fixture
def azure_app_service_config():
    return {"name": "prod-app", "location": "eastus", "sku": "P1v2"}


@pytest.fixture
def gcp_app_engine_config():
    return {"service": "prod-app", "runtime": "python311"}


@pytest.fixture
def aws_workspaces_config():
    return {"directory_id": "d-1234567890", "bundle_id": "wsb-1234567890"}


@pytest.fixture
def azure_vdi_config():
    return {"name": "prod-vdi", "location": "eastus"}


@pytest.fixture
def gcp_workstations_config():
    return {"name": "prod-workstations", "region": "us-central1"}


@pytest.fixture
def aws_storage_gateway_config():
    return {"gateway_name": "prod-storage-gateway", "gateway_type": "FILE_S3"}


@pytest.fixture
def azure_file_sync_config():
    return {"name": "prod-file-sync", "location": "eastus"}


@pytest.fixture
def gcp_filestore_config():
    return {"name": "prod-filestore", "zone": "us-central1-a", "tier": "BASIC"}


@pytest.fixture
def aws_datasync_config():
    return {
        "source_location_arn": "arn:aws:datasync:us-east-1:123456789:location/loc-123",
        "destination_location_arn": "arn:aws:datasync:us-west-2:123456789:location/loc-456",
    }


@pytest.fixture
def azure_data_box_config():
    return {"name": "prod-data-box", "location": "eastus"}


@pytest.fixture
def gcp_transfer_service_config():
    return {"name": "prod-transfer", "region": "us-central1"}


@pytest.fixture
def aws_snowball_config():
    return {"job_type": "IMPORT", "device_type": "EDGE_SNOWBALL"}


@pytest.fixture
def azure_import_export_config():
    return {"name": "prod-import-export", "location": "eastus"}


@pytest.fixture
def gcp_storage_transfer_config():
    return {"name": "prod-transfer", "region": "us-central1"}


@pytest.fixture
def aws_outposts_config():
    return {"name": "prod-outpost", "site_id": "os-1234567890abcdef0"}


@pytest.fixture
def azure_stack_hci_config():
    return {"name": "prod-stack-hci", "location": "eastus"}


@pytest.fixture
def gcp_anthos_config():
    return {"name": "prod-anthos", "location": "us-central1"}


@pytest.fixture
def aws_local_zones_config():
    return {"zone_name": "us-east-1-bos-1a", "opt_in_status": "opted-in"}


@pytest.fixture
def azure_edge_zones_config():
    return {"name": "prod-edge-zone", "location": "eastus"}


@pytest.fixture
def gcp_edge_zones_config():
    return {"name": "prod-edge-zone", "region": "us-central1"}


@pytest.fixture
def aws_wavelength_config():
    return {"zone_name": "us-east-1-wl1-bos-wlz-1"}


@pytest.fixture
def azure_mobile_network_config():
    return {"name": "prod-mobile-network", "location": "eastus"}


@pytest.fixture
def gcp_distributed_cloud_config():
    return {"name": "prod-distributed-cloud", "region": "us-central1"}


@pytest.fixture
def aws_ground_station_config():
    return {"name": "prod-ground-station"}


@pytest.fixture
def azure_orbital_config():
    return {"name": "prod-orbital", "location": "eastus"}


@pytest.fixture
def gcp_satellite_config():
    return {"name": "prod-satellite", "region": "us-central1"}


@pytest.fixture
def aws_quantum_config():
    return {"name": "prod-quantum"}


@pytest.fixture
def azure_quantum_config():
    return {"name": "prod-quantum", "location": "eastus"}


@pytest.fixture
def gcp_quantum_config():
    return {"name": "prod-quantum", "region": "us-central1"}


@pytest.fixture
def aws_healthlake_config():
    return {"datastore_name": "prod-healthlake", "datastore_type_version": "R4"}


@pytest.fixture
def azure_healthcare_config():
    return {"name": "prod-healthcare", "location": "eastus"}


@pytest.fixture
def gcp_healthcare_api_config():
    return {"name": "prod-healthcare", "location": "us-central1"}


@pytest.fixture
def aws_forecast_config():
    return {"predictor_name": "prod-forecast"}


@pytest.fixture
def azure_machine_learning_config():
    return {"name": "prod-ml", "location": "eastus"}


@pytest.fixture
def gcp_vertex_ai_config():
    return {"name": "prod-vertex-ai", "region": "us-central1"}


@pytest.fixture
def aws_personalize_config():
    return {"dataset_group_name": "prod-personalize"}


@pytest.fixture
def azure_cognitive_services_config():
    return {"name": "prod-cognitive", "location": "eastus"}


@pytest.fixture
def gcp_ai_platform_config():
    return {"name": "prod-ai-platform", "region": "us-central1"}


@pytest.fixture
def aws_rekognition_config():
    return {"collection_id": "prod-rekognition"}


@pytest.fixture
def azure_vision_config():
    return {"name": "prod-vision", "location": "eastus"}


@pytest.fixture
def gcp_vision_api_config():
    return {"name": "prod-vision", "region": "us-central1"}


@pytest.fixture
def aws_transcribe_config():
    return {"transcription_job_name": "prod-transcribe"}


@pytest.fixture
def azure_speech_config():
    return {"name": "prod-speech", "location": "eastus"}


@pytest.fixture
def gcp_speech_api_config():
    return {"name": "prod-speech", "region": "us-central1"}


@pytest.fixture
def aws_translate_config():
    return {"translation_job_name": "prod-translate"}


@pytest.fixture
def azure_translator_config():
    return {"name": "prod-translator", "location": "eastus"}


@pytest.fixture
def gcp_translate_api_config():
    return {"name": "prod-translate", "region": "us-central1"}


@pytest.fixture
def aws_comprehend_config():
    return {"document_classifier_name": "prod-comprehend"}


@pytest.fixture
def azure_language_config():
    return {"name": "prod-language", "location": "eastus"}


@pytest.fixture
def gcp_natural_language_api_config():
    return {"name": "prod-nlp", "region": "us-central1"}


@pytest.fixture
def aws_textract_config():
    return {"document_name": "prod-textract"}


@pytest.fixture
def azure_form_recognizer_config():
    return {"name": "prod-form-recognizer", "location": "eastus"}


@pytest.fixture
def gcp_document_ai_config():
    return {"name": "prod-document-ai", "region": "us-central1"}


@pytest.fixture
def aws_polly_config():
    return {"voice_id": "Joanna"}


@pytest.fixture
def azure_text_to_speech_config():
    return {"name": "prod-tts", "location": "eastus"}


@pytest.fixture
def gcp_text_to_speech_api_config():
    return {"name": "prod-tts", "region": "us-central1"}


@pytest.fixture
def aws_lex_config():
    return {"bot_name": "prod-bot"}


@pytest.fixture
def azure_bot_service_config():
    return {"name": "prod-bot", "location": "eastus"}


@pytest.fixture
def gcp_dialogflow_config():
    return {"name": "prod-dialogflow", "region": "us-central1"}


@pytest.fixture
def aws_connect_config():
    return {"instance_alias": "prod-connect"}


@pytest.fixture
def azure_communication_services_config():
    return {"name": "prod-communication", "location": "eastus"}


@pytest.fixture
def gcp_contact_center_ai_config():
    return {"name": "prod-ccai", "region": "us-central1"}


@pytest.fixture
def aws_pinpoint_config():
    return {"application_name": "prod-pinpoint"}


@pytest.fixture
def azure_notification_hubs_config():
    return {"name": "prod-notification-hub", "location": "eastus"}


@pytest.fixture
def gcp_firebase_cloud_messaging_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_ses_config():
    return {"email_identity": "noreply@example.com"}


@pytest.fixture
def azure_email_communication_config():
    return {"name": "prod-email", "location": "eastus"}


@pytest.fixture
def gcp_sendgrid_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_chime_config():
    return {"app_instance_name": "prod-chime"}


@pytest.fixture
def azure_teams_config():
    return {"name": "prod-teams", "location": "eastus"}


@pytest.fixture
def gcp_meet_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_workdocs_config():
    return {"organization_id": "d-1234567890"}


@pytest.fixture
def azure_sharepoint_config():
    return {"name": "prod-sharepoint", "location": "eastus"}


@pytest.fixture
def gcp_drive_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_workmail_config():
    return {"organization_id": "m-1234567890abcdef0"}


@pytest.fixture
def azure_exchange_config():
    return {"name": "prod-exchange", "location": "eastus"}


@pytest.fixture
def gcp_gmail_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_quicksight_config():
    return {"account_name": "prod-quicksight"}


@pytest.fixture
def azure_powerbi_config():
    return {"name": "prod-powerbi", "location": "eastus"}


@pytest.fixture
def gcp_looker_config():
    return {"name": "prod-looker", "region": "us-central1"}


@pytest.fixture
def aws_grafana_config():
    return {"workspace_name": "prod-grafana"}


@pytest.fixture
def azure_dashboard_config():
    return {"name": "prod-dashboard", "location": "eastus"}


@pytest.fixture
def gcp_monitoring_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_xray_config():
    return {
        "sampling_rule": {
            "rule_name": "prod-sampling",
            "priority": 1000,
            "reservoir_size": 5,
            "fixed_rate": 0.1,
        }
    }


@pytest.fixture
def azure_application_insights_config():
    return {"name": "prod-app-insights", "location": "eastus"}


@pytest.fixture
def gcp_trace_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_cloudwatch_logs_config():
    return {"log_group_name": "/prod/application", "retention_in_days": 90}


@pytest.fixture
def azure_log_analytics_config():
    return {"name": "prod-log-analytics", "location": "eastus", "retention_in_days": 90}


@pytest.fixture
def gcp_cloud_logging_config():
    return {"project_id": "prod-project", "retention_days": 90}


@pytest.fixture
def aws_cloudwatch_alarm_config():
    return {
        "alarm_name": "prod-high-cpu",
        "metric_name": "CPUUtilization",
        "namespace": "AWS/EC2",
        "statistic": "Average",
        "period": 300,
        "evaluation_periods": 2,
        "threshold": 80,
        "comparison_operator": "GreaterThanThreshold",
        "alarm_actions": ["arn:aws:sns:us-east-1:123456789:prod-alerts"],
    }


@pytest.fixture
def azure_monitor_alert_config():
    return {
        "name": "prod-high-cpu",
        "location": "eastus",
        "severity": 2,
        "frequency": "PT5M",
        "window_size": "PT15M",
    }


@pytest.fixture
def gcp_monitoring_alert_config():
    return {
        "display_name": "prod-high-cpu",
        "comparison": "COMPARISON_GT",
        "threshold_value": 80,
        "duration": "300s",
    }


@pytest.fixture
def aws_ssm_config():
    return {
        "name": "prod-patch-baseline",
        "operating_system": "AMAZON_LINUX_2",
        "approval_rules": {
            "patch_rules": [
                {
                    "patch_filter_group": {
                        "patch_filters": [{"key": "PRODUCT", "values": ["AmazonLinux2"]}]
                    },
                    "approve_after_days": 7,
                }
            ]
        },
    }


@pytest.fixture
def azure_update_manager_config():
    return {"name": "prod-update-manager", "location": "eastus"}


@pytest.fixture
def gcp_os_config_config():
    return {"project_id": "prod-project", "zone": "us-central1-a"}


@pytest.fixture
def aws_inspector_config():
    return {
        "assessment_template_name": "prod-inspector",
        "rules_package_arns": ["arn:aws:inspector:us-east-1:123456789:rulespackage/0-9hgA516p"],
    }


@pytest.fixture
def azure_security_center_config():
    return {
        "tier": "Standard",
        "extensions": [
            {"name": "Servers", "tier": "Standard"},
            {"name": "Containers", "tier": "Standard"},
        ],
    }


@pytest.fixture
def gcp_security_health_analytics_config():
    return {"organization_id": "123456789"}


@pytest.fixture
def aws_macie_config():
    return {"status": "ENABLED"}


@pytest.fixture
def azure_purview_config():
    return {"name": "prod-purview", "location": "eastus"}


@pytest.fixture
def gcp_data_catalog_config():
    return {"name": "prod-data-catalog", "region": "us-central1"}


@pytest.fixture
def aws_detective_config():
    return {"enable": True}


@pytest.fixture
def azure_sentinel_config():
    return {"name": "prod-sentinel", "location": "eastus"}


@pytest.fixture
def gcp_chronicle_config():
    return {"name": "prod-chronicle", "region": "us-central1"}


@pytest.fixture
def aws_security_hub_config():
    return {
        "enable_default_standards": True,
        "standards": [
            {
                "standards_arn": "arn:aws:securityhub:us-east-1::standards/aws-foundational-security-best-practices/v/1.0.0"
            }
        ],
    }


@pytest.fixture
def azure_defender_for_cloud_config():
    return {
        "tier": "Standard",
        "extensions": [
            {"name": "Servers", "tier": "Standard"},
            {"name": "SqlServers", "tier": "Standard"},
            {"name": "Containers", "tier": "Standard"},
            {"name": "StorageAccounts", "tier": "Standard"},
        ],
    }


@pytest.fixture
def aws_artifact_config():
    return {"report_type": "SOC_2"}


@pytest.fixture
def azure_compliance_manager_config():
    return {"name": "prod-compliance", "location": "eastus"}


@pytest.fixture
def gcp_compliance_manager_config():
    return {"organization_id": "123456789"}


@pytest.fixture
def aws_license_manager_config():
    return {"license_configuration_name": "prod-license", "license_counting_type": "vCPU"}


@pytest.fixture
def azure_license_manager_config():
    return {"name": "prod-license", "location": "eastus"}


@pytest.fixture
def gcp_license_manager_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_service_catalog_config():
    return {"portfolio_name": "prod-portfolio", "product_name": "prod-product"}


@pytest.fixture
def azure_managed_applications_config():
    return {"name": "prod-managed-app", "location": "eastus"}


@pytest.fixture
def gcp_deployment_manager_config():
    return {"name": "prod-deployment", "region": "us-central1"}


@pytest.fixture
def aws_control_tower_config():
    return {"landing_zone_name": "prod-landing-zone"}


@pytest.fixture
def azure_landing_zone_config():
    return {"name": "prod-landing-zone", "location": "eastus"}


@pytest.fixture
def gcp_landing_zone_config():
    return {"organization_id": "123456789", "region": "us-central1"}


@pytest.fixture
def aws_organizations_config():
    return {"feature_set": "ALL"}


@pytest.fixture
def azure_management_groups_config():
    return {"name": "prod-management-group"}


@pytest.fixture
def gcp_resource_manager_config():
    return {"organization_id": "123456789"}


@pytest.fixture
def aws_ram_config():
    return {"resource_share_name": "prod-share"}


@pytest.fixture
def azure_resource_share_config():
    return {"name": "prod-share", "location": "eastus"}


@pytest.fixture
def gcp_resource_share_config():
    return {"name": "prod-share", "region": "us-central1"}


@pytest.fixture
def aws_config_aggregator_config():
    return {
        "aggregator_name": "prod-aggregator",
        "account_aggregation_sources": [{"account_ids": ["123456789012"], "all_aws_regions": True}],
    }


@pytest.fixture
def azure_policy_initiative_config():
    return {"name": "prod-initiative", "mode": "Indexed"}


@pytest.fixture
def aws_conformance_pack_config():
    return {
        "conformance_pack_name": "prod-conformance",
        "template_s3_uri": "s3://prod-templates/conformance.yaml",
    }


@pytest.fixture
def azure_blueprint_config():
    return {"name": "prod-blueprint", "location": "eastus"}


@pytest.fixture
def gcp_blueprint_config():
    return {"name": "prod-blueprint", "region": "us-central1"}


@pytest.fixture
def aws_security_token_config():
    return {
        "role_arn": "arn:aws:iam::123456789:role/prod-role",
        "role_session_name": "prod-session",
        "duration_seconds": 3600,
    }


@pytest.fixture
def azure_managed_identity_config():
    return {"name": "prod-identity", "location": "eastus"}


@pytest.fixture
def gcp_service_account_config():
    return {"account_id": "prod-sa", "display_name": "Production Service Account"}


@pytest.fixture
def aws_iam_access_analyzer_config():
    return {"analyzer_name": "prod-analyzer", "type": "ACCOUNT"}


@pytest.fixture
def azure_pim_config():
    return {"name": "prod-pim", "location": "eastus"}


@pytest.fixture
def gcp_privileged_access_manager_config():
    return {"organization_id": "123456789"}


@pytest.fixture
def aws_verified_permissions_config():
    return {"policy_store_name": "prod-permissions"}


@pytest.fixture
def azure_entra_id_config():
    return {"name": "prod-entra", "location": "eastus"}


@pytest.fixture
def gcp_identity_platform_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_cognito_config():
    return {
        "user_pool_name": "prod-user-pool",
        "mfa_configuration": "ON",
        "software_token_mfa_configuration": {"enabled": True},
    }


@pytest.fixture
def azure_ad_b2c_config():
    return {"name": "prod-b2c", "location": "eastus"}


@pytest.fixture
def gcp_identity_toolkit_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_directory_service_config():
    return {
        "name": "prod-directory",
        "size": "Large",
        "vpc_settings": {"vpc_id": "vpc-123", "subnet_ids": ["subnet-123", "subnet-456"]},
    }


@pytest.fixture
def azure_ad_domain_services_config():
    return {"name": "prod-domain", "location": "eastus"}


@pytest.fixture
def gcp_managed_microsoft_ad_config():
    return {"name": "prod-ad", "region": "us-central1"}


@pytest.fixture
def aws_secrets_manager_config():
    return {
        "name": "prod/secret",
        "description": "Production secret",
        "rotation_rules": {"automatically_after_days": 30},
    }


@pytest.fixture
def azure_key_vault_config():
    return {"name": "prod-keyvault", "location": "eastus", "sku": "premium"}


@pytest.fixture
def gcp_secret_manager_config():
    return {"name": "prod-secret", "replication": {"automatic": {}}}


@pytest.fixture
def aws_certificate_manager_config():
    return {"domain_name": "example.com", "validation_method": "DNS"}


@pytest.fixture
def azure_app_configuration_config():
    return {"name": "prod-app-config", "location": "eastus", "sku": "standard"}


@pytest.fixture
def gcp_runtime_config_config():
    return {"name": "prod-runtime-config", "region": "us-central1"}


@pytest.fixture
def aws_systems_manager_config():
    return {"name": "prod-ssm", "document_type": "Command"}


@pytest.fixture
def azure_automation_config():
    return {"name": "prod-automation", "location": "eastus"}


@pytest.fixture
def aws_maintenance_window_config():
    return {
        "name": "prod-maintenance",
        "schedule": "cron(0 0 ? * SUN *)",
        "duration": 4,
        "cutoff": 1,
    }


@pytest.fixture
def azure_maintenance_config():
    return {"name": "prod-maintenance", "location": "eastus"}


@pytest.fixture
def gcp_maintenance_policy_config():
    return {"project_id": "prod-project", "zone": "us-central1-a"}


@pytest.fixture
def aws_patch_manager_config():
    return {"name": "prod-patch", "baseline_id": "pb-1234567890abcdef0"}


@pytest.fixture
def azure_update_management_config():
    return {"name": "prod-update", "location": "eastus"}


@pytest.fixture
def gcp_os_patch_config():
    return {"project_id": "prod-project", "zone": "us-central1-a"}


@pytest.fixture
def aws_state_manager_config():
    return {"name": "prod-state", "document_type": "Association"}


@pytest.fixture
def azure_desired_state_config():
    return {"name": "prod-dsc", "location": "eastus"}


@pytest.fixture
def aws_distributed_map_config():
    return {"map_name": "prod-map"}


@pytest.fixture
def azure_cosmos_db_config():
    return {"name": "prod-cosmos", "location": "eastus", "enable_multiple_write_locations": True}


@pytest.fixture
def aws_location_service_config():
    return {"tracker_name": "prod-tracker"}


@pytest.fixture
def azure_maps_config():
    return {"name": "prod-maps", "location": "eastus"}


@pytest.fixture
def gcp_maps_platform_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_iot_core_config():
    return {"thing_name": "prod-thing", "thing_type_name": "prod-sensor"}


@pytest.fixture
def azure_iot_hub_config():
    return {"name": "prod-iot-hub", "location": "eastus", "sku": "S1"}


@pytest.fixture
def gcp_iot_core_config():
    return {"name": "prod-iot-core", "region": "us-central1"}


@pytest.fixture
def aws_1click_config():
    return {"project_name": "prod-1click"}


@pytest.fixture
def azure_sphere_config():
    return {"name": "prod-sphere", "location": "eastus"}


@pytest.fixture
def gcp_iot_edge_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_greengrass_config():
    return {"group_name": "prod-greengrass"}


@pytest.fixture
def azure_iot_edge_config():
    return {"name": "prod-iot-edge", "location": "eastus"}


@pytest.fixture
def gcp_edge_tpu_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_sagemaker_config():
    return {"notebook_instance_name": "prod-sagemaker", "instance_type": "ml.t3.medium"}


@pytest.fixture
def azure_machine_learning_workspace_config():
    return {"name": "prod-ml", "location": "eastus"}


@pytest.fixture
def gcp_ai_platform_notebook_config():
    return {"name": "prod-ai", "region": "us-central1"}


@pytest.fixture
def aws_bedrock_config():
    return {"model_id": "anthropic.claude-3-sonnet-20240229-v1:0"}


@pytest.fixture
def azure_openai_service_config():
    return {"name": "prod-openai", "location": "eastus"}


@pytest.fixture
def gcp_gemini_api_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_q_business_config():
    return {"application_name": "prod-q"}


@pytest.fixture
def azure_copilot_config():
    return {"name": "prod-copilot", "location": "eastus"}


@pytest.fixture
def gcp_bard_api_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_code_whisperer_config():
    return {"name": "prod-codewhisperer"}


@pytest.fixture
def azure_github_copilot_config():
    return {"name": "prod-copilot", "location": "eastus"}


@pytest.fixture
def gcp_codey_api_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_healthomics_config():
    return {"sequence_store_name": "prod-omics"}


@pytest.fixture
def azure_health_data_services_config():
    return {"name": "prod-health", "location": "eastus"}


@pytest.fixture
def aws_mainframe_modernization_config():
    return {"application_name": "prod-mainframe"}


@pytest.fixture
def azure_mainframe_rehosting_config():
    return {"name": "prod-mainframe", "location": "eastus"}


@pytest.fixture
def gcp_mainframe_migration_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_elastic_disaster_recovery_config():
    return {"source_server_id": "s-1234567890abcdef0"}


@pytest.fixture
def azure_site_recovery_config():
    return {"name": "prod-site-recovery", "location": "eastus"}


@pytest.fixture
def gcp_disaster_recovery_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_resilience_hub_config():
    return {"app_name": "prod-app"}


@pytest.fixture
def azure_recovery_services_vault_config():
    return {"name": "prod-recovery", "location": "eastus"}


@pytest.fixture
def gcp_backup_for_gke_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_fault_injection_simulator_config():
    return {"experiment_template_name": "prod-fis"}


@pytest.fixture
def azure_chaos_studio_config():
    return {"name": "prod-chaos", "location": "eastus"}


@pytest.fixture
def gcp_chaos_engineering_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_application_migration_service_config():
    return {"replication_server_instance_type": "t3.large"}


@pytest.fixture
def azure_migrate_config():
    return {"name": "prod-migrate", "location": "eastus"}


@pytest.fixture
def gcp_migrate_for_compute_engine_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_transfer_family_config():
    return {"server_id": "s-1234567890abcdef0"}


@pytest.fixture
def azure_data_share_config():
    return {"name": "prod-data-share", "location": "eastus"}


@pytest.fixture
def gcp_bigquery_data_transfer_service_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_data_exchange_config():
    return {"data_set_name": "prod-data-exchange"}


@pytest.fixture
def gcp_analytics_hub_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_clean_rooms_config():
    return {"collaboration_name": "prod-clean-rooms"}


@pytest.fixture
def azure_confidential_computing_config():
    return {"name": "prod-confidential", "location": "eastus"}


@pytest.fixture
def gcp_confidential_computing_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_private_5g_config():
    return {"network_name": "prod-private-5g"}


@pytest.fixture
def azure_private_5g_core_config():
    return {"name": "prod-private-5g", "location": "eastus"}


@pytest.fixture
def gcp_private_5g_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_drone_config():
    return {"name": "prod-drone"}


@pytest.fixture
def azure_drone_config():
    return {"name": "prod-drone", "location": "eastus"}


@pytest.fixture
def gcp_drone_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_robotics_config():
    return {"fleet_name": "prod-robotics"}


@pytest.fixture
def azure_robotics_config():
    return {"name": "prod-robotics", "location": "eastus"}


@pytest.fixture
def gcp_robotics_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_quantum_computing_config():
    return {"device_name": "prod-quantum"}


@pytest.fixture
def aws_blockchain_config():
    return {"network_name": "prod-blockchain"}


@pytest.fixture
def azure_blockchain_service_config():
    return {"name": "prod-blockchain", "location": "eastus"}


@pytest.fixture
def gcp_blockchain_node_engine_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_managed_blockchain_config():
    return {"network_name": "prod-blockchain"}


@pytest.fixture
def aws_ledger_config():
    return {"ledger_name": "prod-ledger"}


@pytest.fixture
def azure_ledger_config():
    return {"name": "prod-ledger", "location": "eastus"}


@pytest.fixture
def gcp_ledger_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_timestream_config():
    return {"database_name": "prod-timestream"}


@pytest.fixture
def azure_time_series_insights_config():
    return {"name": "prod-tsi", "location": "eastus"}


@pytest.fixture
def gcp_time_series_insights_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_managed_influxdb_config():
    return {"db_instance_name": "prod-influxdb"}


@pytest.fixture
def azure_influxdb_config():
    return {"name": "prod-influxdb", "location": "eastus"}


@pytest.fixture
def gcp_influxdb_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_keyspaces_config():
    return {"keyspace_name": "prod-keyspaces"}


@pytest.fixture
def aws_managed_redis_config():
    return {"replication_group_id": "prod-redis"}


@pytest.fixture
def aws_memorydb_config():
    return {"cluster_name": "prod-memorydb"}


@pytest.fixture
def aws_neptune_config():
    return {"db_cluster_identifier": "prod-neptune"}


@pytest.fixture
def aws_documentdb_config():
    return {"db_cluster_identifier": "prod-documentdb"}


@pytest.fixture
def aws_dynamodb_config():
    return {
        "table_name": "prod-table",
        "billing_mode": "PAY_PER_REQUEST",
        "point_in_time_recovery": {"enabled": True},
    }


@pytest.fixture
def aws_managed_grafana_config():
    return {"workspace_name": "prod-grafana"}


@pytest.fixture
def aws_managed_prometheus_config():
    return {"workspace_name": "prod-prometheus"}


@pytest.fixture
def aws_managed_service_config():
    return {"service_name": "prod-service"}


@pytest.fixture
def azure_managed_service_config():
    return {"name": "prod-service", "location": "eastus"}


@pytest.fixture
def gcp_managed_service_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_proton_config():
    return {"service_name": "prod-proton"}


@pytest.fixture
def azure_deployment_environments_config():
    return {"name": "prod-environments", "location": "eastus"}


@pytest.fixture
def gcp_cloud_deploy_config():
    return {"name": "prod-deploy", "region": "us-central1"}


@pytest.fixture
def aws_app_runner_config():
    return {"service_name": "prod-app-runner"}


@pytest.fixture
def aws_lightsail_config():
    return {"instance_name": "prod-lightsail"}


@pytest.fixture
def aws_elastic_container_service_config():
    return {"cluster_name": "prod-ecs"}


@pytest.fixture
def aws_elastic_kubernetes_service_config():
    return {"cluster_name": "prod-eks"}


@pytest.fixture
def azure_kubernetes_service_config():
    return {"name": "prod-aks", "location": "eastus"}


@pytest.fixture
def gcp_google_kubernetes_engine_config():
    return {"name": "prod-gke", "location": "us-central1"}


@pytest.fixture
def aws_batch_config():
    return {"compute_environment_name": "prod-batch"}


@pytest.fixture
def azure_batch_config():
    return {"name": "prod-batch", "location": "eastus"}


@pytest.fixture
def gcp_batch_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_parallel_cluster_config():
    return {"cluster_name": "prod-parallel"}


@pytest.fixture
def azure_cyclecloud_config():
    return {"name": "prod-cyclecloud", "location": "eastus"}


@pytest.fixture
def aws_mainframe_config():
    return {"name": "prod-mainframe"}


@pytest.fixture
def azure_mainframe_config():
    return {"name": "prod-mainframe", "location": "eastus"}


@pytest.fixture
def gcp_mainframe_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_elastic_beanstalk_config():
    return {"application_name": "prod-beanstalk"}


@pytest.fixture
def aws_kinesis_config():
    return {"stream_name": "prod-kinesis"}


@pytest.fixture
def azure_event_hubs_config():
    return {"name": "prod-event-hubs", "location": "eastus"}


@pytest.fixture
def aws_managed_kafka_config():
    return {"cluster_name": "prod-kafka"}


@pytest.fixture
def aws_data_pipeline_config():
    return {"pipeline_name": "prod-data-pipeline"}


@pytest.fixture
def aws_lake_formation_config():
    return {"database_name": "prod-lake"}


@pytest.fixture
def azure_data_lake_config():
    return {"name": "prod-data-lake", "location": "eastus"}


@pytest.fixture
def gcp_dataplex_config():
    return {"name": "prod-dataplex", "region": "us-central1"}


@pytest.fixture
def aws_data_brew_config():
    return {"job_name": "prod-databrew"}


@pytest.fixture
def gcp_dataprep_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def aws_lookout_config():
    return {"detector_name": "prod-lookout"}


@pytest.fixture
def azure_anomaly_detector_config():
    return {"name": "prod-anomaly-detector", "location": "eastus"}


@pytest.fixture
def aws_monitron_config():
    return {"project_name": "prod-monitron"}


@pytest.fixture
def aws_lookout_vision_config():
    return {"project_name": "prod-lookout-vision"}


@pytest.fixture
def azure_custom_vision_config():
    return {"name": "prod-custom-vision", "location": "eastus"}


@pytest.fixture
def aws_lookout_equipment_config():
    return {"project_name": "prod-lookout-equipment"}


@pytest.fixture
def aws_panorama_config():
    return {"device_name": "prod-panorama"}


@pytest.fixture
def azure_percept_config():
    return {"name": "prod-percept", "location": "eastus"}


@pytest.fixture
def aws_robomaker_config():
    return {"robot_application_name": "prod-robomaker"}


@pytest.fixture
def aws_omics_config():
    return {"sequence_store_name": "prod-omics"}


@pytest.fixture
def azure_genomics_config():
    return {"name": "prod-genomics", "location": "eastus"}


@pytest.fixture
def gcp_life_science_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def azure_computer_vision_config():
    return {"name": "prod-vision", "location": "eastus"}


@pytest.fixture
def azure_speech_services_config():
    return {"name": "prod-speech", "location": "eastus"}


@pytest.fixture
def gcp_speech_to_text_config():
    return {"name": "prod-speech", "region": "us-central1"}


@pytest.fixture
def azure_language_service_config():
    return {"name": "prod-language", "location": "eastus"}


@pytest.fixture
def gcp_text_to_speech_config():
    return {"name": "prod-tts", "region": "us-central1"}


@pytest.fixture
def azure_email_communication_services_config():
    return {"name": "prod-email", "location": "eastus"}


@pytest.fixture
def azure_power_bi_config():
    return {"name": "prod-power-bi", "location": "eastus"}


@pytest.fixture
def gcp_cloud_trace_config():
    return {"project_id": "prod-project"}


@pytest.fixture
def azure_maintenance_configuration_config():
    return {"name": "prod-maintenance", "location": "eastus"}


@pytest.fixture
def gcp_os_patch_management_config():
    return {"project_id": "prod-project", "zone": "us-central1-a"}


@pytest.fixture
def azure_desired_state_configuration_config():
    return {"name": "prod-dsc", "location": "eastus"}


@pytest.fixture
def gcp_os_config_manager_config():
    return {"project_id": "prod-project", "zone": "us-central1-a"}


@pytest.fixture
def azure_cache_for_redis_config():
    return {"name": "prod-cache", "location": "eastus"}


@pytest.fixture
def azure_service_bus_config():
    return {"name": "prod-service-bus", "location": "eastus", "sku": "Premium"}


@pytest.fixture
def azure_event_grid_config():
    return {"name": "prod-event-grid", "location": "eastus"}


@pytest.fixture
def gcp_analytics_config():
    return {"project_id": "prod-project"}
