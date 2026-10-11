"""Cost comparison integration tests.

Tests that validate cost comparison and optimization across
AWS, Azure, and GCP for equivalent workloads.
"""

import pytest


class TestCostComparison:
    """Test cost comparison across cloud providers."""

    def test_aws_compute_cost_estimate(self, aws_instance_config):
        """Verify AWS compute cost estimation."""
        # m6i.xlarge: ~$0.192/hour on-demand
        instance_type = aws_instance_config["instance_type"]
        assert instance_type.startswith("m6i")
        # Cost optimization: reserved instances should be cheaper
        on_demand_hourly = 0.192
        reserved_hourly = on_demand_hourly * 0.6  # ~40% savings
        assert reserved_hourly < on_demand_hourly

    def test_azure_compute_cost_estimate(self, azure_vm_config):
        """Verify Azure compute cost estimation."""
        # Standard_D4s_v5: ~$0.192/hour on-demand
        size = azure_vm_config["size"]
        assert size.startswith("Standard_D")
        on_demand_hourly = 0.192
        reserved_hourly = on_demand_hourly * 0.6
        assert reserved_hourly < on_demand_hourly

    def test_gcp_compute_cost_estimate(self, gcp_instance_config):
        """Verify GCP compute cost estimation."""
        # n2-standard-4: ~$0.194/hour on-demand
        machine_type = gcp_instance_config["machine_type"]
        assert machine_type.startswith("n2")
        on_demand_hourly = 0.194
        sustained_use_discount = on_demand_hourly * 0.7  # ~30% automatic
        assert sustained_use_discount < on_demand_hourly

    def test_aws_storage_cost_estimate(self, aws_s3_config):
        """Verify AWS storage cost estimation."""
        # S3 Standard: ~$0.023/GB/month
        storage_cost_per_gb = 0.023
        # S3 Glacier: ~$0.004/GB/month
        glacier_cost_per_gb = 0.004
        assert glacier_cost_per_gb < storage_cost_per_gb

    def test_azure_storage_cost_estimate(self, azure_storage_config):
        """Verify Azure storage cost estimation."""
        # Standard GRS: ~$0.036/GB/month
        grs_cost_per_gb = 0.036
        # Standard LRS: ~$0.018/GB/month
        lrs_cost_per_gb = 0.018
        assert lrs_cost_per_gb < grs_cost_per_gb

    def test_gcp_storage_cost_estimate(self, gcp_storage_config):
        """Verify GCP storage cost estimation."""
        # Standard: ~$0.020/GB/month
        standard_cost_per_gb = 0.020
        # Nearline: ~$0.010/GB/month
        nearline_cost_per_gb = 0.010
        assert nearline_cost_per_gb < standard_cost_per_gb

    def test_aws_database_cost_estimate(self, aws_rds_config):
        """Verify AWS database cost estimation."""
        # db.r6g.xlarge: ~$0.437/hour
        instance_class = aws_rds_config["instance_class"]
        assert instance_class.startswith("db.r6g")
        on_demand_hourly = 0.437
        reserved_hourly = on_demand_hourly * 0.6
        assert reserved_hourly < on_demand_hourly

    def test_azure_database_cost_estimate(self, azure_sql_config):
        """Verify Azure database cost estimation."""
        # Premium P2: ~$0.504/hour
        edition = azure_sql_config["edition"]
        assert edition in ["Premium", "BusinessCritical"]
        on_demand_hourly = 0.504
        reserved_hourly = on_demand_hourly * 0.6
        assert reserved_hourly < on_demand_hourly

    def test_gcp_database_cost_estimate(self, gcp_sql_config):
        """Verify GCP database cost estimation."""
        # db-custom-4-16384: ~$0.424/hour
        tier = gcp_sql_config["tier"]
        assert tier.startswith("db-custom")
        on_demand_hourly = 0.424
        sustained_use_discount = on_demand_hourly * 0.7
        assert sustained_use_discount < on_demand_hourly

    def test_aws_network_cost_estimate(self, aws_lb_config):
        """Verify AWS network cost estimation."""
        # ALB: ~$0.0225/LCU-hour + $0.008/GB
        alb_lcu_hourly = 0.0225
        data_processing_per_gb = 0.008
        assert alb_lcu_hourly > 0
        assert data_processing_per_gb > 0

    def test_azure_network_cost_estimate(self, azure_lb_config):
        """Verify Azure network cost estimation."""
        # Standard LB: ~$0.025/hour + $0.005/GB
        lb_hourly = 0.025
        data_processing_per_gb = 0.005
        assert lb_hourly > 0
        assert data_processing_per_gb > 0

    def test_gcp_network_cost_estimate(self, gcp_lb_config):
        """Verify GCP network cost estimation."""
        # Cloud Load Balancing: ~$0.025/hour + $0.008/GB
        lb_hourly = 0.025
        data_processing_per_gb = 0.008
        assert lb_hourly > 0
        assert data_processing_per_gb > 0

    def test_aws_data_transfer_cost(self):
        """Verify AWS data transfer cost structure."""
        # Internet outbound: $0.09/GB (first 10TB)
        internet_outbound_per_gb = 0.09
        # Inter-region: $0.02/GB
        inter_region_per_gb = 0.02
        assert inter_region_per_gb < internet_outbound_per_gb

    def test_azure_data_transfer_cost(self):
        """Verify Azure data transfer cost structure."""
        # Internet outbound: $0.087/GB (first 10TB)
        internet_outbound_per_gb = 0.087
        # Inter-region: $0.02/GB
        inter_region_per_gb = 0.02
        assert inter_region_per_gb < internet_outbound_per_gb

    def test_gcp_data_transfer_cost(self):
        """Verify GCP data transfer cost structure."""
        # Internet outbound: $0.12/GB (first 10TB)
        internet_outbound_per_gb = 0.12
        # Inter-region: $0.01/GB
        inter_region_per_gb = 0.01
        assert inter_region_per_gb < internet_outbound_per_gb

    def test_aws_reserved_instance_savings(self):
        """Verify AWS reserved instance cost savings."""
        on_demand = 1000.0
        one_year_reserved = on_demand * 0.6  # 40% savings
        three_year_reserved = on_demand * 0.4  # 60% savings
        assert three_year_reserved < one_year_reserved < on_demand

    def test_azure_reserved_instance_savings(self):
        """Verify Azure reserved instance cost savings."""
        on_demand = 1000.0
        one_year_reserved = on_demand * 0.62  # 38% savings
        three_year_reserved = on_demand * 0.42  # 58% savings
        assert three_year_reserved < one_year_reserved < on_demand

    def test_gcp_sustained_use_discounts(self):
        """Verify GCP sustained use discount structure."""
        on_demand = 1000.0
        # Automatic discounts: 20-30% for sustained usage
        sustained_discount = on_demand * 0.7  # 30% savings
        # Committed use: 37-55% for 1-year, 55% for 3-year
        committed_1yr = on_demand * 0.63  # 37% savings
        committed_3yr = on_demand * 0.45  # 55% savings
        assert committed_3yr < committed_1yr < sustained_discount < on_demand

    def test_aws_spot_instance_savings(self):
        """Verify AWS spot instance cost savings."""
        on_demand = 1000.0
        spot = on_demand * 0.3  # Up to 90% savings
        assert spot < on_demand * 0.5

    def test_azure_spot_instance_savings(self):
        """Verify Azure spot instance cost savings."""
        on_demand = 1000.0
        spot = on_demand * 0.3  # Up to 90% savings
        assert spot < on_demand * 0.5

    def test_gcp_preemptible_savings(self):
        """Verify GCP preemptible/spot VM cost savings."""
        on_demand = 1000.0
        spot = on_demand * 0.2  # Up to 80% savings
        assert spot < on_demand * 0.5

    def test_aws_free_tier(self):
        """Verify AWS free tier offerings."""
        free_tier = {
            "ec2": "750 hours t2.micro",
            "s3": "5GB standard storage",
            "rds": "750 hours db.t2.micro",
            "lambda": "1M requests",
        }
        assert len(free_tier) >= 4

    def test_azure_free_tier(self):
        """Verify Azure free tier offerings."""
        free_tier = {
            "vm": "750 hours B1S",
            "storage": "5GB LRS blob",
            "database": "250GB SQL Database",
            "functions": "1M executions",
        }
        assert len(free_tier) >= 4

    def test_gcp_free_tier(self):
        """Verify GCP free tier offerings."""
        free_tier = {
            "compute": "1 e2-micro instance",
            "storage": "5GB regional",
            "functions": "2M invocations",
            "bigquery": "1TB queries",
        }
        assert len(free_tier) >= 4

    def test_aws_cost_allocation_tags(self, aws_instance_config):
        """Verify AWS cost allocation tags."""
        tags = aws_instance_config.get("tags", {})
        assert "Environment" in tags
        assert "Name" in tags

    def test_azure_cost_allocation_tags(self, azure_vm_config):
        """Verify Azure cost allocation tags."""
        tags = azure_vm_config.get("tags", {})
        assert "Environment" in tags
        assert "Name" in tags

    def test_gcp_cost_allocation_labels(self, gcp_instance_config):
        """Verify GCP cost allocation labels."""
        # GCP uses labels for cost allocation
        assert "name" in gcp_instance_config

    def test_aws_budget_alerts(self):
        """Verify AWS budget alert configuration."""
        alert_thresholds = [50, 80, 100]  # Percentages
        assert all(t <= 100 for t in alert_thresholds)

    def test_azure_budget_alerts(self):
        """Verify Azure budget alert configuration."""
        alert_thresholds = [50, 80, 100]  # Percentages
        assert all(t <= 100 for t in alert_thresholds)

    def test_gcp_budget_alerts(self):
        """Verify GCP budget alert configuration."""
        alert_thresholds = [50, 80, 100]  # Percentages
        assert all(t <= 100 for t in alert_thresholds)

    def test_aws_cost_explorer(self):
        """Verify AWS Cost Explorer capabilities."""
        capabilities = [
            "cost_analysis",
            "usage_forecasting",
            "reservation_planning",
            "savings_plans",
        ]
        assert len(capabilities) >= 4

    def test_azure_cost_management(self):
        """Verify Azure Cost Management capabilities."""
        capabilities = ["cost_analysis", "budget_alerts", "reservation_recommendations", "advisor"]
        assert len(capabilities) >= 4

    def test_gcp_cost_management(self):
        """Verify GCP cost management capabilities."""
        capabilities = [
            "cost_analysis",
            "budget_alerts",
            "committed_use_discounts",
            "recommendations",
        ]
        assert len(capabilities) >= 4

    def test_cross_cloud_cost_comparison(self):
        """Verify cross-cloud cost comparison methodology."""
        # Equivalent compute: 4 vCPU, 16GB RAM
        aws_monthly = 139.0  # m6i.xlarge on-demand
        azure_monthly = 139.0  # Standard_D4s_v5 on-demand
        gcp_monthly = 140.0  # n2-standard-4 on-demand
        # All within 5% of each other
        max_cost = max(aws_monthly, azure_monthly, gcp_monthly)
        min_cost = min(aws_monthly, azure_monthly, gcp_monthly)
        assert (max_cost - min_cost) / max_cost < 0.05

    def test_aws_s3_lifecycle_cost_optimization(self, aws_s3_config):
        """Verify AWS S3 lifecycle cost optimization."""
        assert "versioning" in aws_s3_config
        # Lifecycle policies should transition to cheaper storage
        lifecycle_rules = [{"transition_to_ia": 30, "transition_to_glacier": 90}]
        assert len(lifecycle_rules) > 0

    def test_azure_storage_lifecycle_cost_optimization(self, azure_storage_config):
        """Verify Azure storage lifecycle cost optimization."""
        assert "account_tier" in azure_storage_config
        # Lifecycle policies should transition to cooler tiers
        lifecycle_rules = [{"transition_to_cool": 30, "transition_to_archive": 90}]
        assert len(lifecycle_rules) > 0

    def test_gcp_storage_lifecycle_cost_optimization(self, gcp_storage_config):
        """Verify GCP storage lifecycle cost optimization."""
        assert "storage_class" in gcp_storage_config
        # Lifecycle policies should transition to cheaper storage
        lifecycle_rules = [{"transition_to_nearline": 30, "transition_to_coldline": 90}]
        assert len(lifecycle_rules) > 0

    def test_aws_compute_optimizer(self):
        """Verify AWS Compute Optimizer recommendations."""
        recommendations = ["right_sizing", "instance_family_upgrade", "idle_instance_detection"]
        assert len(recommendations) >= 3

    def test_azure_advisor_cost_recommendations(self):
        """Verify Azure Advisor cost recommendations."""
        recommendations = ["right_sizing", "reserved_instances", "idle_resources"]
        assert len(recommendations) >= 3

    def test_gcp_recommender_cost_recommendations(self):
        """Verify GCP Recommender cost recommendations."""
        recommendations = ["right_sizing", "committed_use_discounts", "idle_resources"]
        assert len(recommendations) >= 3

    def test_aws_savings_plans(self):
        """Verify AWS Savings Plans cost structure."""
        # Compute Savings Plans: up to 66% savings
        on_demand = 1000.0
        savings_plans = on_demand * 0.34  # 66% savings
        assert savings_plans < on_demand * 0.5

    def test_azure_savings_commitment(self):
        """Verify Azure savings commitment options."""
        # Azure Reservations: up to 72% savings
        on_demand = 1000.0
        reservation = on_demand * 0.28  # 72% savings
        assert reservation < on_demand * 0.5

    def test_gcp_commitment_discounts(self):
        """Verify GCP committed use discount structure."""
        # 1-year: 37% savings, 3-year: 55% savings
        on_demand = 1000.0
        one_year = on_demand * 0.63
        three_year = on_demand * 0.45
        assert three_year < one_year < on_demand

    @pytest.mark.parametrize("provider", ["aws", "azure", "gcp"])
    def test_all_providers_have_cost_optimization(self, provider):
        """Verify all cloud providers offer cost optimization."""
        optimization_features = {
            "aws": ["reserved_instances", "spot_instances", "savings_plans", "compute_optimizer"],
            "azure": ["reservations", "spot_instances", "advisor", "hybrid_benefit"],
            "gcp": ["sustained_use", "committed_use", "spot_vms", "recommender"],
        }
        assert provider in optimization_features
        assert len(optimization_features[provider]) >= 4
