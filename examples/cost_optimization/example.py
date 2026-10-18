"""Example usage of the Data Center Commander cost optimization engine."""

from dcc.cost_optimization import (
    CloudCostAnalyzer,
    CloudProvider,
    CostOptimizationEngine,
    InstanceType,
    PricingModel,
    Workload,
)


def create_sample_catalog():
    """Create a sample instance catalog for AWS."""
    return [
        InstanceType(
            name="t3.small",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=2.0,
            storage_gb=20,
            on_demand_hourly=0.0208,
            reserved_1yr_hourly=0.0131,
            reserved_3yr_hourly=0.0082,
            spot_hourly=0.0062,
        ),
        InstanceType(
            name="t3.medium",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=4.0,
            storage_gb=40,
            on_demand_hourly=0.0416,
            reserved_1yr_hourly=0.0262,
            reserved_3yr_hourly=0.0164,
            spot_hourly=0.0125,
        ),
        InstanceType(
            name="m5.large",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=8.0,
            storage_gb=50,
            on_demand_hourly=0.096,
            reserved_1yr_hourly=0.060,
            reserved_3yr_hourly=0.038,
            spot_hourly=0.029,
        ),
        InstanceType(
            name="m5.xlarge",
            provider=CloudProvider.AWS,
            vcpus=4,
            memory_gb=16.0,
            storage_gb=100,
            on_demand_hourly=0.192,
            reserved_1yr_hourly=0.120,
            reserved_3yr_hourly=0.076,
            spot_hourly=0.058,
        ),
        InstanceType(
            name="m5.2xlarge",
            provider=CloudProvider.AWS,
            vcpus=8,
            memory_gb=32.0,
            storage_gb=200,
            on_demand_hourly=0.384,
            reserved_1yr_hourly=0.240,
            reserved_3yr_hourly=0.152,
            spot_hourly=0.115,
        ),
        InstanceType(
            name="m6i.large",
            provider=CloudProvider.AWS,
            vcpus=2,
            memory_gb=8.0,
            storage_gb=50,
            on_demand_hourly=0.086,
            reserved_1yr_hourly=0.054,
            reserved_3yr_hourly=0.034,
            spot_hourly=0.026,
        ),
        InstanceType(
            name="m6i.xlarge",
            provider=CloudProvider.AWS,
            vcpus=4,
            memory_gb=16.0,
            storage_gb=100,
            on_demand_hourly=0.172,
            reserved_1yr_hourly=0.108,
            reserved_3yr_hourly=0.068,
            spot_hourly=0.052,
        ),
    ]


def create_sample_workloads(catalog):
    """Create sample workloads for demonstration."""
    instances = {it.name: it for it in catalog}

    return [
        # Production web servers — well utilized
        Workload(
            workload_id="web-001",
            name="web-server-1",
            instance_type=instances["m5.xlarge"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-east-1",
            environment="production",
            team="engineering",
            application="web",
            cpu_utilization_avg=0.55,
            cpu_utilization_p95=0.75,
            memory_utilization_avg=0.65,
            memory_utilization_p95=0.80,
        ),
        Workload(
            workload_id="web-002",
            name="web-server-2",
            instance_type=instances["m5.xlarge"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-east-1",
            environment="production",
            team="engineering",
            application="web",
            cpu_utilization_avg=0.50,
            cpu_utilization_p95=0.70,
            memory_utilization_avg=0.60,
            memory_utilization_p95=0.75,
        ),
        # Over-provisioned staging server
        Workload(
            workload_id="staging-001",
            name="staging-app",
            instance_type=instances["m5.2xlarge"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-east-1",
            environment="staging",
            team="engineering",
            application="staging",
            cpu_utilization_avg=0.12,
            cpu_utilization_p95=0.25,
            memory_utilization_avg=0.18,
            memory_utilization_p95=0.30,
        ),
        # Dev server — very underutilized
        Workload(
            workload_id="dev-001",
            name="dev-box",
            instance_type=instances["m5.xlarge"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-east-1",
            environment="dev",
            team="engineering",
            application="dev",
            cpu_utilization_avg=0.08,
            cpu_utilization_p95=0.15,
            memory_utilization_avg=0.12,
            memory_utilization_p95=0.20,
        ),
        # Batch processing — good spot candidate
        Workload(
            workload_id="batch-001",
            name="batch-processor",
            instance_type=instances["m5.xlarge"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-east-1",
            environment="production",
            team="data",
            application="batch",
            cpu_utilization_avg=0.45,
            cpu_utilization_p95=0.65,
            memory_utilization_avg=0.50,
            memory_utilization_p95=0.70,
            uptime_hours_monthly=400,
        ),
        # CI runner — good spot candidate
        Workload(
            workload_id="ci-001",
            name="ci-runner",
            instance_type=instances["m5.large"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-east-1",
            environment="dev",
            team="engineering",
            application="ci",
            cpu_utilization_avg=0.30,
            cpu_utilization_p95=0.55,
            memory_utilization_avg=0.35,
            memory_utilization_p95=0.50,
            uptime_hours_monthly=300,
        ),
        # Database — reserved instance candidate
        Workload(
            workload_id="db-001",
            name="primary-db",
            instance_type=instances["m5.2xlarge"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-east-1",
            environment="production",
            team="data",
            application="database",
            cpu_utilization_avg=0.60,
            cpu_utilization_p95=0.80,
            memory_utilization_avg=0.70,
            memory_utilization_p95=0.85,
        ),
        # Old generation server — modernization candidate
        Workload(
            workload_id="legacy-001",
            name="legacy-app",
            instance_type=instances["m5.xlarge"],
            pricing_model=PricingModel.ON_DEMAND,
            region="us-west-2",
            environment="production",
            team="engineering",
            application="legacy",
            cpu_utilization_avg=0.40,
            cpu_utilization_p95=0.60,
            memory_utilization_avg=0.50,
            memory_utilization_p95=0.65,
        ),
    ]


def main():
    """Run the cost optimization engine and display results."""
    print("=" * 70)
    print("  Data Center Commander — Cost Optimization Engine")
    print("=" * 70)

    catalog = create_sample_catalog()
    workloads = create_sample_workloads(catalog)

    # Run full optimization
    engine = CostOptimizationEngine(catalog)
    report = engine.run(workloads)

    # Display results
    print(f"\n📊 Report generated: {report.generated_at}")
    print(f"   Total workloads: {report.total_workloads}")
    print(f"   Total monthly cost: ${report.total_monthly_cost:,.2f}")
    print(f"   Total potential annual savings: ${report.total_potential_savings:,.2f}")
    print(f"   Savings percentage: {report.savings_percent:.1f}%")

    # Cost breakdown
    if report.cost_breakdown:
        cb = report.cost_breakdown
        print(f"\n📈 Cost Breakdown:")
        print(f"   By provider: {cb.by_provider}")
        print(f"   By region: {cb.by_region}")
        print(f"   By team: {cb.by_team}")
        print(f"   By environment: {cb.by_environment}")
        print(f"   By pricing model: {cb.by_pricing_model}")

    # Rightsizing recommendations
    if report.rightsizing_recommendations:
        print(f"\n🔧 Rightsizing Recommendations ({len(report.rightsizing_recommendations)}):")
        for i, rec in enumerate(report.rightsizing_recommendations[:5], 1):
            print(f"   {i}. {rec.workload_name}: {rec.current_instance.name} → "
                  f"{rec.recommended_instance.name}")
            print(f"      Savings: ${rec.monthly_savings:.2f}/mo ({rec.savings_percent:.0f}%) "
                  f"| Risk: {rec.risk_level.value} | Action: {rec.action}")
            print(f"      Reason: {rec.reason}")

    # Reserved instance plans
    if report.reserved_instance_plans:
        print(f"\n📋 Reserved Instance Plans ({len(report.reserved_instance_plans)}):")
        for i, plan in enumerate(report.reserved_instance_plans[:5], 1):
            print(f"   {i}. {plan.quantity}x {plan.instance_type.name} "
                  f"({plan.term_months}mo, {plan.payment_option})")
            print(f"      Savings: ${plan.monthly_savings:.2f}/mo ({plan.savings_percent:.0f}%) "
                  f"| Break-even: {plan.break_even_months:.1f}mo "
                  f"| Risk: {plan.risk_level.value}")

    # Spot instance strategies
    if report.spot_strategies:
        print(f"\n⚡ Spot Instance Strategies ({len(report.spot_strategies)}):")
        for i, strategy in enumerate(report.spot_strategies[:5], 1):
            print(f"   {i}. {strategy.workload_name}: {strategy.current_instance.name} → "
                  f"{strategy.recommended_instance.name}")
            print(f"      Savings: ${strategy.monthly_savings:.2f}/mo ({strategy.savings_percent:.0f}%) "
                  f"| Interruption risk: {strategy.interruption_risk.value} "
                  f"({strategy.interruption_probability:.0%})")

    # Risk summary
    print(f"\n⚠️  Risk Summary:")
    for level, count in report.risk_summary.items():
        print(f"   {level}: {count}")

    # Quick wins
    if report.quick_wins:
        print(f"\n✅ Quick Wins:")
        for i, win in enumerate(report.quick_wins, 1):
            print(f"   {i}. {win}")

    # Long-term recommendations
    if report.long_term_recommendations:
        print(f"\n🎯 Long-term Recommendations:")
        for i, rec in enumerate(report.long_term_recommendations, 1):
            print(f"   {i}. {rec}")

    print("\n" + "=" * 70)

    # Also demonstrate individual analyzers
    print("\n📊 Individual Analyzer Demos:")
    print("-" * 40)

    # Cloud cost analyzer
    analyzer = CloudCostAnalyzer()
    idle = analyzer.idle_workloads(workloads)
    print(f"   Idle workloads: {len(idle)}")
    for wl in idle:
        print(f"     - {wl.name} ({wl.workload_id})")

    under = analyzer.underutilized_workloads(workloads)
    print(f"   Underutilized workloads: {len(under)}")
    for wl in under:
        print(f"     - {wl.name} ({wl.workload_id})")

    over = analyzer.overutilized_workloads(workloads)
    print(f"   Overutilized workloads: {len(over)}")
    for wl in over:
        print(f"     - {wl.name} ({wl.workload_id})")

    top = analyzer.top_spenders(workloads, n=3)
    print(f"   Top 3 spenders:")
    for wl in top:
        print(f"     - {wl.name}: ${wl.monthly_cost:.2f}/mo")

    print("\n✅ Cost optimization analysis complete!")


if __name__ == "__main__":
    main()
