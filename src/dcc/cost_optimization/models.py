"""Data models for the cost optimization engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CloudProvider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"


class PricingModel(str, Enum):
    ON_DEMAND = "on_demand"
    RESERVED_1YR = "reserved_1yr"
    RESERVED_3YR = "reserved_3yr"
    SPOT = "spot"
    SAVINGS_PLAN_1YR = "savings_plan_1yr"
    SAVINGS_PLAN_3YR = "savings_plan_3yr"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class InstanceType:
    """A cloud instance type with pricing information."""

    name: str
    provider: CloudProvider
    vcpus: int
    memory_gb: float
    storage_gb: int
    on_demand_hourly: float
    reserved_1yr_hourly: float
    reserved_3yr_hourly: float
    spot_hourly: float
    region: str = "us-east-1"
    gpu_count: int = 0
    gpu_model: Optional[str] = None
    network_tier: str = "standard"  # standard, enhanced, premium

    @property
    def on_demand_monthly(self) -> float:
        return self.on_demand_hourly * 730

    @property
    def reserved_1yr_monthly(self) -> float:
        return self.reserved_1yr_hourly * 730

    @property
    def reserved_3yr_monthly(self) -> float:
        return self.reserved_3yr_hourly * 730

    @property
    def spot_monthly(self) -> float:
        return self.spot_hourly * 730

    @property
    def vcpu_to_memory_ratio(self) -> float:
        return self.vcpus / self.memory_gb if self.memory_gb > 0 else 0


@dataclass
class Workload:
    """A running workload / instance with utilization metrics."""

    workload_id: str
    name: str
    instance_type: InstanceType
    pricing_model: PricingModel
    region: str
    # Utilization metrics (0.0 – 1.0)
    cpu_utilization_avg: float = 0.0
    cpu_utilization_p95: float = 0.0
    memory_utilization_avg: float = 0.0
    memory_utilization_p95: float = 0.0
    network_in_mbps_avg: float = 0.0
    network_out_mbps_avg: float = 0.0
    disk_iops_avg: float = 0.0
    # Metadata
    environment: str = "production"  # production, staging, dev, test
    team: str = "unassigned"
    application: str = "unknown"
    tags: dict[str, str] = field(default_factory=dict)
    uptime_hours_monthly: float = 730.0
    # Cost
    monthly_cost: float = 0.0

    def __post_init__(self) -> None:
        if self.monthly_cost == 0.0:
            self.monthly_cost = self._compute_monthly_cost()

    def _compute_monthly_cost(self) -> float:
        hourly = {
            PricingModel.ON_DEMAND: self.instance_type.on_demand_hourly,
            PricingModel.RESERVED_1YR: self.instance_type.reserved_1yr_hourly,
            PricingModel.RESERVED_3YR: self.instance_type.reserved_3yr_hourly,
            PricingModel.SPOT: self.instance_type.spot_hourly,
            PricingModel.SAVINGS_PLAN_1YR: self.instance_type.reserved_1yr_hourly,
            PricingModel.SAVINGS_PLAN_3YR: self.instance_type.reserved_3yr_hourly,
        }
        return hourly[self.pricing_model] * self.uptime_hours_monthly


@dataclass
class CostBreakdown:
    """Aggregated cost breakdown for a set of workloads."""

    total_monthly: float = 0.0
    by_provider: dict[str, float] = field(default_factory=dict)
    by_region: dict[str, float] = field(default_factory=dict)
    by_team: dict[str, float] = field(default_factory=dict)
    by_environment: dict[str, float] = field(default_factory=dict)
    by_pricing_model: dict[str, float] = field(default_factory=dict)
    by_instance_family: dict[str, float] = field(default_factory=dict)
    compute_monthly: float = 0.0
    storage_monthly: float = 0.0
    network_monthly: float = 0.0
    other_monthly: float = 0.0
    workload_count: int = 0


@dataclass
class RightsizingRecommendation:
    """A recommendation to resize a workload."""

    workload_id: str
    workload_name: str
    current_instance: InstanceType
    recommended_instance: InstanceType
    current_monthly_cost: float
    recommended_monthly_cost: float
    monthly_savings: float
    annual_savings: float
    savings_percent: float
    reason: str
    risk_level: RiskLevel
    confidence: float  # 0.0 – 1.0
    action: str  # "downsize", "upsizing", "family_change"
    estimated_downtime_minutes: float = 0.0


@dataclass
class ReservedInstancePlan:
    """A plan for purchasing reserved instances."""

    instance_type: InstanceType
    provider: CloudProvider
    term_months: int  # 12 or 36
    payment_option: str  # "all_upfront", "partial_upfront", "no_upfront"
    quantity: int
    hourly_rate: float
    total_upfront: float
    total_effective_monthly: float
    on_demand_equivalent_monthly: float
    monthly_savings: float
    annual_savings: float
    savings_percent: float
    break_even_months: float
    risk_level: RiskLevel


@dataclass
class SpotInstanceStrategy:
    """A strategy for using spot instances."""

    workload_id: str
    workload_name: str
    current_instance: InstanceType
    recommended_instance: InstanceType
    current_monthly_cost: float
    spot_monthly_cost: float
    monthly_savings: float
    annual_savings: float
    savings_percent: float
    interruption_risk: RiskLevel
    interruption_probability: float  # 0.0 – 1.0
    recommended_max_bid: float
    diversification_recommendation: str
    fallback_strategy: str
    risk_level: RiskLevel


@dataclass
class OptimizationReport:
    """Complete cost optimization report."""

    generated_at: str = ""
    total_workloads: int = 0
    total_monthly_cost: float = 0.0
    total_potential_savings: float = 0.0
    savings_percent: float = 0.0
    cost_breakdown: Optional[CostBreakdown] = None
    rightsizing_recommendations: list[RightsizingRecommendation] = field(default_factory=list)
    reserved_instance_plans: list[ReservedInstancePlan] = field(default_factory=list)
    spot_strategies: list[SpotInstanceStrategy] = field(default_factory=list)
    risk_summary: dict[str, int] = field(default_factory=dict)
    quick_wins: list[str] = field(default_factory=list)
    long_term_recommendations: list[str] = field(default_factory=list)
