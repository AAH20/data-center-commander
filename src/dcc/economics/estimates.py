"""Bottom-up cost estimation engine for new data center deployments.

Builds cost estimates from first principles by decomposing a deployment
specification into component-level quantities, applying unit costs from
the price engine, and rolling up lifecycle cash flows.

The estimation pipeline:
1. DeploymentSpec — capacity, redundancy, geography, and design parameters
2. Component sizing — electrical, mechanical, IT, network, civil quantities
3. Quantity takeoff — derived from design rules and industry ratios
4. Unit cost application — from PriceEngine or explicit overrides
5. Lifecycle calculation — escalation, recurrence, discounting via budget engine
6. Low/base/high bounds — from unit cost ranges and contingency

All calculations are deterministic, tenant-scoped, and read-only.
No I/O, no network, no persistence — callers persist results.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Optional

from .prices import PriceEngine, PriceRecord, PriceQuery, PriceStatus
from .unit import equivalent_annual_cost, cost_per_kw_year, cost_per_rack_year, cost_per_m2_year


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ZERO = Decimal("0")
ONE = Decimal("1")
MONTHS_PER_YEAR = 12

# Default design ratios (industry benchmarks, overridable)
DEFAULT_IT_LOAD_PER_RACK_KW = Decimal("8")          # kW per rack (IT load)
DEFAULT_POWER_DENSITY_KW_PER_M2 = Decimal("1.5")    # IT kW per m² white space
DEFAULT_PUE = Decimal("1.45")                        # Power Usage Effectiveness
DEFAULT_COOLING_KW_PER_IT_KW = Decimal("0.45")       # Cooling capacity per IT kW
DEFAULT_ELECTRICAL_OVERHEAD = Decimal("0.25")       # 25% electrical overhead
DEFAULT_MECHANICAL_OVERHEAD = Decimal("0.15")        # 15% mechanical overhead
DEFAULT_CIVIL_COST_PER_M2 = Decimal("800")           # USD/m² for shell
DEFAULT_DESIGN_COST_PCT = Decimal("0.08")            # 8% of construction
DEFAULT_NETWORK_COST_PER_RACK = Decimal("5000")      # USD per rack
DEFAULT_SOFTWARE_COST_PER_KW = Decimal("50")         # USD per IT kW
DEFAULT_MAINTENANCE_PCT = Decimal("0.05")            # 5% of capex annually
DEFAULT_CONTINGENCY_PCT = Decimal("0.10")            # 10% contingency
DEFAULT_WASTE_FACTOR = Decimal("0.05")               # 5% construction waste
DEFAULT_ESCALATION_PCT = Decimal("0.03")             # 3% annual escalation
DEFAULT_DISCOUNT_RATE = Decimal("0.08")              # 8% discount rate
DEFAULT_USEFUL_LIFE_YEARS = 15                       # 15-year facility life
DEFAULT_REFRESH_YEARS = 5                            # 5-year IT refresh cycle


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DeploymentType(str, Enum):
    """Type of data center deployment."""
    GREENFIELD = "greenfield"
    BROWNFIELD = "brownfield"
    EXPANSION = "expansion"
    EDGE = "edge"
    COLOCATION = "colocation"


class RedundancyLevel(str, Enum):
    """Electrical/mechanical redundancy level."""
    N = "N"
    N_PLUS_1 = "N+1"
    N_PLUS_2 = "N+2"
    TWO_N = "2N"
    TWO_N_PLUS_1 = "2N+1"


class TierLevel(str, Enum):
    """Uptime Institute tier level."""
    TIER_I = "Tier I"
    TIER_II = "Tier II"
    TIER_III = "Tier III"
    TIER_IV = "Tier IV"


class CostPhase(str, Enum):
    """Cost lifecycle phases matching estimate_line_items."""
    LAND = "land"
    DESIGN = "design"
    CIVIL = "civil"
    ELECTRICAL = "electrical"
    MECHANICAL = "mechanical"
    IT_EQUIPMENT = "it_equipment"
    NETWORK = "network"
    SOFTWARE = "software"
    LABOR = "labor"
    ENERGY = "energy"
    WATER = "water"
    CARBON = "carbon"
    MAINTENANCE = "maintenance"
    TAX = "tax"
    FINANCE = "finance"
    DECOMMISSIONING = "decommissioning"
    OTHER = "other"


class CostBehavior(str, Enum):
    """Cost behavior matching estimate_line_items."""
    ONE_TIME = "one_time"
    FIXED_RECURRING = "fixed_recurring"
    VARIABLE = "variable"
    STEP_FIXED = "step_fixed"
    CAPITALIZED = "capitalized"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DeploymentSpec:
    """Input specification for a new data center deployment.

    Attributes:
        name: Project name (1-120 chars).
        deployment_type: Greenfield, brownfield, expansion, etc.
        it_capacity_kw: Total IT load capacity in kW.
        rack_count: Number of racks (optional, derived from kW if omitted).
        white_space_m2: White space area in m² (optional, derived if omitted).
        geography: Geographic location for pricing (e.g., "US-East", "EG").
        currency: ISO 4217 currency code.
        redundancy: Electrical redundancy level.
        tier_level: Uptime Institute tier classification.
        pue: Power Usage Effectiveness assumption.
        horizon_months: Analysis horizon in months (1-600).
        discount_rate: Annual discount rate for NPV (0-1).
        contingency_pct: Contingency percentage (0-1).
        escalation_pct: Annual cost escalation rate (0-1).
        useful_life_years: Facility useful life in years.
        refresh_years: IT equipment refresh cycle in years.
        annual_it_energy_kwh: Annual IT energy consumption (optional).
        annual_useful_work: Annual useful work units (optional).
        design_overrides: Dict of design parameter overrides.
        price_overrides: Dict of explicit unit costs by item code.
        metadata: Additional caller-specific data.
    """

    name: str
    deployment_type: DeploymentType = DeploymentType.GREENFIELD
    it_capacity_kw: Decimal = ZERO
    rack_count: Optional[int] = None
    white_space_m2: Optional[Decimal] = None
    geography: str = "US-East"
    currency: str = "USD"
    redundancy: RedundancyLevel = RedundancyLevel.N_PLUS_1
    tier_level: TierLevel = TierLevel.TIER_III
    pue: Decimal = DEFAULT_PUE
    horizon_months: int = 180
    discount_rate: Decimal = DEFAULT_DISCOUNT_RATE
    contingency_pct: Decimal = DEFAULT_CONTINGENCY_PCT
    escalation_pct: Decimal = DEFAULT_ESCALATION_PCT
    useful_life_years: int = DEFAULT_USEFUL_LIFE_YEARS
    refresh_years: int = DEFAULT_REFRESH_YEARS
    annual_it_energy_kwh: Optional[Decimal] = None
    annual_useful_work: Optional[Decimal] = None
    design_overrides: dict[str, Any] = field(default_factory=dict)
    price_overrides: dict[str, Decimal] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (isinstance(self.name, str) and 1 <= len(self.name.strip()) <= 120):
            raise ValueError("name must contain 1-120 characters")
        if self.it_capacity_kw <= 0:
            raise ValueError("it_capacity_kw must be positive")
        if self.rack_count is not None and self.rack_count < 1:
            raise ValueError("rack_count must be at least 1")
        if self.white_space_m2 is not None and self.white_space_m2 <= 0:
            raise ValueError("white_space_m2 must be positive")
        if not (isinstance(self.horizon_months, int) and not isinstance(self.horizon_months, bool)
                and 1 <= self.horizon_months <= 600):
            raise ValueError("horizon_months must be an integer from 1 to 600")
        if self.discount_rate < 0 or self.discount_rate >= 1:
            raise ValueError("discount_rate must be in [0, 1)")
        if self.contingency_pct < 0 or self.contingency_pct > 1:
            raise ValueError("contingency_pct must be between 0 and 1")
        if self.escalation_pct < -1:
            raise ValueError("escalation_pct must be >= -1")
        if self.useful_life_years < 1:
            raise ValueError("useful_life_years must be positive")
        if self.refresh_years < 1:
            raise ValueError("refresh_years must be positive")
        if self.pue < 1:
            raise ValueError("pue must be >= 1")

    @property
    def effective_rack_count(self) -> int:
        """Derive rack count from IT capacity if not explicitly set."""
        if self.rack_count is not None:
            return self.rack_count
        return int(math.ceil(float(self.it_capacity_kw) / float(DEFAULT_IT_LOAD_PER_RACK_KW)))

    @property
    def effective_white_space_m2(self) -> Decimal:
        """Derive white space from IT capacity if not explicitly set."""
        if self.white_space_m2 is not None:
            return self.white_space_m2
        return self.it_capacity_kw / DEFAULT_POWER_DENSITY_KW_PER_M2

    @property
    def annual_it_energy(self) -> Decimal:
        """Annual IT energy in kWh (explicit or derived from capacity)."""
        if self.annual_it_energy_kwh is not None:
            return self.annual_it_energy_kwh
        # Assume 80% average utilization, 8760 hours
        return self.it_capacity_kw * Decimal("0.8") * Decimal("8760")

    @property
    def annual_facility_energy(self) -> Decimal:
        """Annual facility energy in kWh (IT energy × PUE)."""
        return self.annual_it_energy * self.pue


@dataclass
class ComponentQuantity:
    """A derived quantity for a cost component.

    Attributes:
        phase: Cost phase (electrical, mechanical, etc.).
        description: Human-readable description.
        quantity: Derived quantity value.
        quantity_unit: Unit of measure (kW, m², each, etc.).
        cost_behavior: One-time, recurring, etc.
        unit_cost_item_code: Item code for price lookup.
        unit_cost_override: Explicit unit cost (overrides price lookup).
        low_unit_cost: Low bound for unit cost.
        high_unit_cost: High bound for unit cost.
        waste_factor: Construction waste factor (0-1).
        recurrence_months: Recurrence period for recurring costs.
        start_month: Month when cost begins.
        escalation_pct: Annual escalation rate for this component.
        source: Description of how the quantity was derived.
    """

    phase: CostPhase
    description: str
    quantity: Decimal
    quantity_unit: str
    cost_behavior: CostBehavior
    unit_cost_item_code: str = ""
    unit_cost_override: Optional[Decimal] = None
    low_unit_cost: Optional[Decimal] = None
    high_unit_cost: Optional[Decimal] = None
    waste_factor: Decimal = ZERO
    recurrence_months: Optional[int] = None
    start_month: int = 0
    escalation_pct: Decimal = ZERO
    source: str = ""

    @property
    def is_lump_sum(self) -> bool:
        """True if this is a lump-sum USD quantity (quantity IS the cost)."""
        return self.quantity_unit == "USD"

    @property
    def effective_unit_cost(self) -> Decimal:
        """Resolve the effective unit cost (override or lookup).

        For lump-sum USD quantities, returns 1 (the quantity is the cost).
        """
        if self.is_lump_sum:
            return ONE
        if self.unit_cost_override is not None:
            return self.unit_cost_override
        return ZERO

    @property
    def extended_base(self) -> Decimal:
        """Extended base cost: quantity × (1 + waste) × unit_cost.

        For lump-sum USD quantities, returns the quantity directly.
        """
        if self.is_lump_sum:
            return self.quantity
        return self.quantity * (ONE + self.waste_factor) * self.effective_unit_cost

    @property
    def extended_low(self) -> Decimal:
        """Extended low cost using low unit cost bound."""
        if self.is_lump_sum:
            return self.quantity
        if self.low_unit_cost is not None:
            return self.quantity * (ONE + self.waste_factor) * self.low_unit_cost
        return self.extended_base

    @property
    def extended_high(self) -> Decimal:
        """Extended high cost using high unit cost bound."""
        if self.is_lump_sum:
            return self.quantity
        if self.high_unit_cost is not None:
            return self.quantity * (ONE + self.waste_factor) * self.high_unit_cost
        return self.extended_base


@dataclass
class EstimateLineItem:
    """A single estimate line item ready for persistence.

    Matches the estimate_line_items table structure.
    """

    line_no: int
    phase: str
    description: str
    quantity: Decimal
    quantity_unit: str
    waste_factor: Decimal
    base_unit_cost: Decimal
    low_unit_cost: Optional[Decimal]
    high_unit_cost: Optional[Decimal]
    currency: str
    pricing_status: str
    cost_behavior: str
    recurrence_months: Optional[int]
    start_month: int
    escalation_pct: Decimal
    extended_base: Decimal
    extended_low: Decimal
    extended_high: Decimal
    assumptions: dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseSubtotal:
    """Subtotal for a cost phase."""

    phase: str
    line_count: int
    total_base: Decimal
    total_low: Decimal
    total_high: Decimal
    total_pv_base: Decimal
    total_pv_low: Decimal
    total_pv_high: Decimal


@dataclass
class EstimateResult:
    """Complete bottom-up estimate result.

    Attributes:
        spec: The deployment specification used.
        line_items: List of estimate line items.
        phase_subtotals: Subtotals by phase.
        total_base: Total base case cost.
        total_low: Total low case cost.
        total_high: Total high case cost.
        total_pv_base: Total present value (base).
        total_pv_low: Total present value (low).
        total_pv_high: Total present value (high).
        first_period_cost: Cost in the first period.
        annual_energy_cost: Annual energy OPEX.
        annual_maintenance_cost: Annual maintenance OPEX.
        equivalent_annual_cost: EAC over the horizon.
        cost_per_kw_year: Normalized cost per kW-year.
        cost_per_rack_year: Normalized cost per rack-year.
        cost_per_m2_year: Normalized cost per m²-year.
        cost_per_kwh: Normalized cost per kWh.
        contingency_amount: Contingency reserve amount.
        currency: Currency code.
        calculation_version: Version of the calculation engine.
        execution_permitted: Always False (read-only).
    """

    spec: DeploymentSpec
    line_items: list[EstimateLineItem]
    phase_subtotals: list[PhaseSubtotal]
    total_base: Decimal
    total_low: Decimal
    total_high: Decimal
    total_pv_base: Decimal
    total_pv_low: Decimal
    total_pv_high: Decimal
    first_period_cost: Decimal
    annual_energy_cost: Decimal
    annual_maintenance_cost: Decimal
    equivalent_annual_cost: Decimal
    cost_per_kw_year: Optional[Decimal]
    cost_per_rack_year: Optional[Decimal]
    cost_per_m2_year: Optional[Decimal]
    cost_per_kwh: Optional[Decimal]
    contingency_amount: Decimal
    currency: str
    calculation_version: str = "1.0"
    execution_permitted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-safe dict."""
        return {
            "name": self.spec.name,
            "deployment_type": self.spec.deployment_type.value,
            "it_capacity_kw": float(self.spec.it_capacity_kw),
            "rack_count": self.spec.effective_rack_count,
            "white_space_m2": float(self.spec.effective_white_space_m2),
            "geography": self.spec.geography,
            "currency": self.currency,
            "redundancy": self.spec.redundancy.value,
            "tier_level": self.spec.tier_level.value,
            "pue": float(self.spec.pue),
            "horizon_months": self.spec.horizon_months,
            "discount_rate": float(self.spec.discount_rate),
            "contingency_pct": float(self.spec.contingency_pct),
            "escalation_pct": float(self.spec.escalation_pct),
            "total_base": float(self.total_base),
            "total_low": float(self.total_low),
            "total_high": float(self.total_high),
            "total_pv_base": float(self.total_pv_base),
            "total_pv_low": float(self.total_pv_low),
            "total_pv_high": float(self.total_pv_high),
            "first_period_cost": float(self.first_period_cost),
            "annual_energy_cost": float(self.annual_energy_cost),
            "annual_maintenance_cost": float(self.annual_maintenance_cost),
            "equivalent_annual_cost": float(self.equivalent_annual_cost),
            "cost_per_kw_year": float(self.cost_per_kw_year) if self.cost_per_kw_year else None,
            "cost_per_rack_year": float(self.cost_per_rack_year) if self.cost_per_rack_year else None,
            "cost_per_m2_year": float(self.cost_per_m2_year) if self.cost_per_m2_year else None,
            "cost_per_kwh": float(self.cost_per_kwh) if self.cost_per_kwh else None,
            "contingency_amount": float(self.contingency_amount),
            "line_count": len(self.line_items),
            "phase_subtotals": [
                {
                    "phase": ps.phase,
                    "line_count": ps.line_count,
                    "total_base": float(ps.total_base),
                    "total_low": float(ps.total_low),
                    "total_high": float(ps.total_high),
                    "total_pv_base": float(ps.total_pv_base),
                    "total_pv_low": float(ps.total_pv_low),
                    "total_pv_high": float(ps.total_pv_high),
                }
                for ps in self.phase_subtotals
            ],
            "calculation_version": self.calculation_version,
            "execution_permitted": self.execution_permitted,
        }


# ---------------------------------------------------------------------------
# Component sizing engine
# ---------------------------------------------------------------------------


class ComponentSizingEngine:
    """Derives component quantities from a deployment specification.

    Uses industry-standard ratios and design rules to size each cost
    component from the IT capacity, rack count, and white space area.
    """

    def __init__(self, spec: DeploymentSpec) -> None:
        self.spec = spec
        self._overrides = spec.design_overrides

    def _get_override(self, key: str, default: Decimal) -> Decimal:
        """Get a design parameter override or return the default."""
        if key in self._overrides:
            return Decimal(str(self._overrides[key]))
        return default

    def _get_price_override(self, item_code: str) -> Optional[Decimal]:
        """Get an explicit unit cost override for an item code."""
        return self.spec.price_overrides.get(item_code)

    def size_electrical(self) -> list[ComponentQuantity]:
        """Size electrical distribution and power train components."""
        it_kw = self.spec.it_capacity_kw
        pue = self.spec.pue
        facility_kw = it_kw * pue
        redundancy_factor = self._redundancy_factor()
        total_electrical_kw = facility_kw * (ONE + DEFAULT_ELECTRICAL_OVERHEAD) * redundancy_factor

        # Main switchgear
        switchgear_kw = total_electrical_kw
        # UPS capacity (N+1 means one extra module)
        ups_kw = it_kw * redundancy_factor
        # Power distribution units
        pdu_count = self.spec.effective_rack_count * 2  # Dual path
        # Generators (for Tier III/IV)
        generator_kw = total_electrical_kw if self.spec.tier_level in (
            TierLevel.TIER_III, TierLevel.TIER_IV
        ) else ZERO

        components = [
            ComponentQuantity(
                phase=CostPhase.ELECTRICAL,
                description="Main switchgear and distribution",
                quantity=switchgear_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="SWITCHGEAR-KW",
                unit_cost_override=self._get_price_override("SWITCHGEAR-KW"),
                low_unit_cost=Decimal("1800"),
                high_unit_cost=Decimal("3200"),
                source="facility_kw × (1 + electrical_overhead) × redundancy_factor",
            ),
            ComponentQuantity(
                phase=CostPhase.ELECTRICAL,
                description="UPS systems (N+1 redundant)",
                quantity=ups_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="UPS-KW",
                unit_cost_override=self._get_price_override("UPS-KW"),
                low_unit_cost=Decimal("400"),
                high_unit_cost=Decimal("800"),
                source="it_kw × redundancy_factor",
            ),
            ComponentQuantity(
                phase=CostPhase.ELECTRICAL,
                description="Power distribution units (dual path)",
                quantity=Decimal(pdu_count),
                quantity_unit="each",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="PDU-EACH",
                unit_cost_override=self._get_price_override("PDU-EACH"),
                low_unit_cost=Decimal("2000"),
                high_unit_cost=Decimal("5000"),
                source="rack_count × 2 (dual path)",
            ),
        ]
        if generator_kw > 0:
            components.append(ComponentQuantity(
                phase=CostPhase.ELECTRICAL,
                description="Standby generators",
                quantity=generator_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="GENERATOR-KW",
                unit_cost_override=self._get_price_override("GENERATOR-KW"),
                low_unit_cost=Decimal("600"),
                high_unit_cost=Decimal("1200"),
                source="total_electrical_kw (Tier III/IV only)",
            ))
        return components

    def size_mechanical(self) -> list[ComponentQuantity]:
        """Size cooling and heat rejection components."""
        it_kw = self.spec.it_capacity_kw
        cooling_kw = it_kw * DEFAULT_COOLING_KW_PER_IT_KW
        redundancy_factor = self._redundancy_factor()
        total_cooling_kw = cooling_kw * (ONE + DEFAULT_MECHANICAL_OVERHEAD) * redundancy_factor

        # Chillers
        chiller_kw = total_cooling_kw
        # Cooling towers
        cooling_tower_kw = total_cooling_kw * Decimal("1.2")
        # CRAH/CRAC units
        crah_count = max(1, int(math.ceil(float(it_kw) / 100)))

        return [
            ComponentQuantity(
                phase=CostPhase.MECHANICAL,
                description="Chiller plants",
                quantity=chiller_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="CHILLER-KW",
                unit_cost_override=self._get_price_override("CHILLER-KW"),
                low_unit_cost=Decimal("400"),
                high_unit_cost=Decimal("800"),
                source="it_kw × cooling_ratio × (1 + mech_overhead) × redundancy",
            ),
            ComponentQuantity(
                phase=CostPhase.MECHANICAL,
                description="Cooling towers and heat rejection",
                quantity=cooling_tower_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="COOLING-TOWER-KW",
                unit_cost_override=self._get_price_override("COOLING-TOWER-KW"),
                low_unit_cost=Decimal("200"),
                high_unit_cost=Decimal("500"),
                source="total_cooling_kw × 1.2",
            ),
            ComponentQuantity(
                phase=CostPhase.MECHANICAL,
                description="CRAH/CRAC units",
                quantity=Decimal(crah_count),
                quantity_unit="each",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="CRAH-EACH",
                unit_cost_override=self._get_price_override("CRAH-EACH"),
                low_unit_cost=Decimal("15000"),
                high_unit_cost=Decimal("35000"),
                source="ceil(it_kw / 100)",
            ),
        ]

    def size_civil(self) -> list[ComponentQuantity]:
        """Size civil and structural components."""
        white_space = self.spec.effective_white_space_m2
        # Total building area is ~2x white space (includes mechanical rooms, etc.)
        total_area = white_space * Decimal("2.0")
        civil_cost_per_m2 = self._get_override("civil_cost_per_m2", DEFAULT_CIVIL_COST_PER_M2)

        return [
            ComponentQuantity(
                phase=CostPhase.CIVIL,
                description="Building shell and structural works",
                quantity=total_area,
                quantity_unit="m²",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="CIVIL-M2",
                unit_cost_override=self._get_price_override("CIVIL-M2"),
                low_unit_cost=civil_cost_per_m2 * Decimal("0.7"),
                high_unit_cost=civil_cost_per_m2 * Decimal("1.5"),
                waste_factor=DEFAULT_WASTE_FACTOR,
                source="white_space_m2 × 2.0 (total building area)",
            ),
            ComponentQuantity(
                phase=CostPhase.CIVIL,
                description="Raised floor and containment",
                quantity=white_space,
                quantity_unit="m²",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="RAISED-FLOOR-M2",
                unit_cost_override=self._get_price_override("RAISED-FLOOR-M2"),
                low_unit_cost=Decimal("150"),
                high_unit_cost=Decimal("400"),
                waste_factor=DEFAULT_WASTE_FACTOR,
                source="white_space_m2",
            ),
        ]

    def size_it_equipment(self) -> list[ComponentQuantity]:
        """Size IT equipment components."""
        it_kw = self.spec.it_capacity_kw
        rack_count = self.spec.effective_rack_count

        return [
            ComponentQuantity(
                phase=CostPhase.IT_EQUIPMENT,
                description="Server hardware",
                quantity=it_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="SERVER-KW",
                unit_cost_override=self._get_price_override("SERVER-KW"),
                low_unit_cost=Decimal("800"),
                high_unit_cost=Decimal("2000"),
                source="it_capacity_kw",
            ),
            ComponentQuantity(
                phase=CostPhase.IT_EQUIPMENT,
                description="Storage systems",
                quantity=it_kw * Decimal("0.3"),
                quantity_unit="kW",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="STORAGE-KW",
                unit_cost_override=self._get_price_override("STORAGE-KW"),
                low_unit_cost=Decimal("400"),
                high_unit_cost=Decimal("1000"),
                source="it_kw × 0.3 (storage ratio)",
            ),
            ComponentQuantity(
                phase=CostPhase.IT_EQUIPMENT,
                description="Rack infrastructure (enclosures, PDUs, cabling)",
                quantity=Decimal(rack_count),
                quantity_unit="each",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="RACK-EACH",
                unit_cost_override=self._get_price_override("RACK-EACH"),
                low_unit_cost=Decimal("3000"),
                high_unit_cost=Decimal("8000"),
                source="rack_count",
            ),
        ]

    def size_network(self) -> list[ComponentQuantity]:
        """Size network and connectivity components."""
        rack_count = self.spec.effective_rack_count
        network_cost_per_rack = self._get_override(
            "network_cost_per_rack", DEFAULT_NETWORK_COST_PER_RACK
        )

        return [
            ComponentQuantity(
                phase=CostPhase.NETWORK,
                description="Network switches and routers",
                quantity=Decimal(rack_count),
                quantity_unit="each",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="NETWORK-RACK",
                unit_cost_override=self._get_price_override("NETWORK-RACK"),
                low_unit_cost=network_cost_per_rack * Decimal("0.6"),
                high_unit_cost=network_cost_per_rack * Decimal("1.5"),
                source="rack_count × network_cost_per_rack",
            ),
            ComponentQuantity(
                phase=CostPhase.NETWORK,
                description="Structured cabling and fiber",
                quantity=Decimal(rack_count),
                quantity_unit="each",
                cost_behavior=CostBehavior.CAPITALIZED,
                unit_cost_item_code="CABLING-RACK",
                unit_cost_override=self._get_price_override("CABLING-RACK"),
                low_unit_cost=Decimal("1000"),
                high_unit_cost=Decimal("3000"),
                source="rack_count",
            ),
        ]

    def size_design_and_other(self) -> list[ComponentQuantity]:
        """Size design, labor, and other soft costs."""
        it_kw = self.spec.it_capacity_kw
        white_space = self.spec.effective_white_space_m2
        total_area = white_space * Decimal("2.0")

        # Design costs as percentage of construction
        construction_cost = (
            it_kw * Decimal("2400")  # Electrical
            + it_kw * Decimal("1800")  # Mechanical
            + total_area * DEFAULT_CIVIL_COST_PER_M2  # Civil
        )
        design_cost = construction_cost * DEFAULT_DESIGN_COST_PCT

        return [
            ComponentQuantity(
                phase=CostPhase.DESIGN,
                description="Engineering and design services",
                quantity=design_cost,
                quantity_unit="USD",
                cost_behavior=CostBehavior.ONE_TIME,
                unit_cost_item_code="DESIGN-LUMP",
                unit_cost_override=self._get_price_override("DESIGN-LUMP"),
                source="construction_cost × design_pct",
            ),
            ComponentQuantity(
                phase=CostPhase.LABOR,
                description="Installation and commissioning labor",
                quantity=it_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.ONE_TIME,
                unit_cost_item_code="LABOR-KW",
                unit_cost_override=self._get_price_override("LABOR-KW"),
                low_unit_cost=Decimal("200"),
                high_unit_cost=Decimal("600"),
                source="it_kw × labor_rate",
            ),
            ComponentQuantity(
                phase=CostPhase.SOFTWARE,
                description="DCIM and management software licenses",
                quantity=it_kw,
                quantity_unit="kW",
                cost_behavior=CostBehavior.FIXED_RECURRING,
                unit_cost_item_code="SOFTWARE-KW",
                unit_cost_override=self._get_price_override("SOFTWARE-KW"),
                low_unit_cost=Decimal("30"),
                high_unit_cost=Decimal("100"),
                recurrence_months=12,
                escalation_pct=self.spec.escalation_pct,
                source="it_kw × software_rate, annual recurrence",
            ),
        ]

    def size_energy_opex(self) -> list[ComponentQuantity]:
        """Size recurring energy OPEX components."""
        annual_energy = self.spec.annual_facility_energy
        energy_rate = self._get_override("energy_rate_per_kwh", Decimal("0.12"))

        return [
            ComponentQuantity(
                phase=CostPhase.ENERGY,
                description="Annual electricity consumption",
                quantity=annual_energy,
                quantity_unit="kWh",
                cost_behavior=CostBehavior.VARIABLE,
                unit_cost_item_code="ENERGY-KWH",
                unit_cost_override=self._get_price_override("ENERGY-KWH"),
                low_unit_cost=energy_rate * Decimal("0.7"),
                high_unit_cost=energy_rate * Decimal("1.5"),
                recurrence_months=12,
                escalation_pct=self.spec.escalation_pct,
                source="annual_facility_energy × energy_rate, annual recurrence",
            ),
        ]

    def size_maintenance_opex(self) -> list[ComponentQuantity]:
        """Size recurring maintenance OPEX components."""
        it_kw = self.spec.it_capacity_kw
        maintenance_rate = self._get_override(
            "maintenance_pct", DEFAULT_MAINTENANCE_PCT
        )
        # Maintenance as % of IT equipment cost
        annual_maintenance = it_kw * Decimal("1200") * maintenance_rate

        return [
            ComponentQuantity(
                phase=CostPhase.MAINTENANCE,
                description="Preventive maintenance and support",
                quantity=annual_maintenance,
                quantity_unit="USD",
                cost_behavior=CostBehavior.FIXED_RECURRING,
                unit_cost_item_code="MAINT-ANNUAL",
                unit_cost_override=self._get_price_override("MAINT-ANNUAL"),
                recurrence_months=12,
                escalation_pct=self.spec.escalation_pct,
                source="it_kw × server_cost × maintenance_pct, annual",
            ),
        ]

    def size_refresh_capex(self) -> list[ComponentQuantity]:
        """Size IT refresh capital expenditure."""
        it_kw = self.spec.it_capacity_kw
        refresh_years = self.spec.refresh_years
        # Refresh cost = server cost / refresh cycle
        annual_refresh = it_kw * Decimal("1000") / Decimal(refresh_years)

        return [
            ComponentQuantity(
                phase=CostPhase.IT_EQUIPMENT,
                description="IT equipment refresh (amortized)",
                quantity=annual_refresh,
                quantity_unit="USD",
                cost_behavior=CostBehavior.FIXED_RECURRING,
                unit_cost_item_code="REFRESH-ANNUAL",
                unit_cost_override=self._get_price_override("REFRESH-ANNUAL"),
                recurrence_months=12,
                escalation_pct=self.spec.escalation_pct,
                source="it_kw × server_cost / refresh_years, annual",
            ),
        ]

    def _redundancy_factor(self) -> Decimal:
        """Compute the capacity multiplier for redundancy level."""
        factors = {
            RedundancyLevel.N: ONE,
            RedundancyLevel.N_PLUS_1: Decimal("1.2"),
            RedundancyLevel.N_PLUS_2: Decimal("1.4"),
            RedundancyLevel.TWO_N: Decimal("2.0"),
            RedundancyLevel.TWO_N_PLUS_1: Decimal("2.2"),
        }
        return factors.get(self.spec.redundancy, ONE)

    def size_all_components(self) -> list[ComponentQuantity]:
        """Run all sizing engines and return the complete component list."""
        components: list[ComponentQuantity] = []
        for method in (
            self.size_electrical,
            self.size_mechanical,
            self.size_civil,
            self.size_it_equipment,
            self.size_network,
            self.size_design_and_other,
            self.size_energy_opex,
            self.size_maintenance_opex,
            self.size_refresh_capex,
        ):
            result = method()
            # Filter out None values (conditional components)
            components.extend([c for c in result if c is not None])
        return components


# ---------------------------------------------------------------------------
# Estimate builder
# ---------------------------------------------------------------------------


class EstimateBuilder:
    """Builds estimate line items from sized components.

    Resolves unit costs from the price engine or explicit overrides,
    computes extended costs, and produces line items ready for persistence.
    """

    def __init__(
        self,
        spec: DeploymentSpec,
        price_engine: Optional[PriceEngine] = None,
    ) -> None:
        self.spec = spec
        self.price_engine = price_engine or PriceEngine()
        self.sizing = ComponentSizingEngine(spec)

    def _resolve_unit_cost(self, component: ComponentQuantity) -> tuple[Decimal, Optional[Decimal], Optional[Decimal]]:
        """Resolve unit cost from override, price engine, or default bounds.

        Returns (base, low, high) tuple.
        For lump-sum USD quantities, returns (1, None, None) since the quantity IS the cost.
        """
        # Lump-sum USD quantities: the quantity is the cost
        if component.is_lump_sum:
            return ONE, None, None

        # Explicit override takes highest priority
        if component.unit_cost_override is not None:
            base = component.unit_cost_override
            low = component.low_unit_cost
            high = component.high_unit_cost
            if low is None:
                low = base * Decimal("0.7")
            if high is None:
                high = base * Decimal("1.5")
            return base, low, high

        # Try price engine lookup
        if component.unit_cost_item_code:
            record = self.price_engine.get_current_price(
                component.unit_cost_item_code,
                geography=self.spec.geography,
            )
            if record is not None and record.normalized_unit_price is not None:
                base = record.normalized_unit_price
                low = component.low_unit_cost or base * Decimal("0.8")
                high = component.high_unit_cost or base * Decimal("1.2")
                return base, low, high

        # Fall back to default bounds
        if component.low_unit_cost is not None and component.high_unit_cost is not None:
            base = (component.low_unit_cost + component.high_unit_cost) / Decimal("2")
            return base, component.low_unit_cost, component.high_unit_cost

        # No pricing available — use zero (will be flagged as unpriced)
        return ZERO, None, None

    def build_line_items(self) -> list[EstimateLineItem]:
        """Build all estimate line items from sized components."""
        components = self.sizing.size_all_components()
        line_items: list[EstimateLineItem] = []

        for idx, component in enumerate(components, start=1):
            base, low, high = self._resolve_unit_cost(component)

            # Determine pricing status
            if component.unit_cost_override is not None:
                pricing_status = "sourced"
            elif component.unit_cost_item_code and self.price_engine.get_current_price(
                component.unit_cost_item_code, geography=self.spec.geography
            ) is not None:
                pricing_status = "sourced"
            elif base > 0:
                pricing_status = "allowance"
            else:
                pricing_status = "unpriced"

            # For lump-sum USD quantities, the quantity IS the cost
            if component.is_lump_sum:
                extended_base = component.quantity
                extended_low = component.quantity
                extended_high = component.quantity
            else:
                extended_base = component.quantity * (ONE + component.waste_factor) * base
                extended_low = (
                    component.quantity * (ONE + component.waste_factor) * low
                    if low is not None else extended_base
                )
                extended_high = (
                    component.quantity * (ONE + component.waste_factor) * high
                    if high is not None else extended_base
                )

            line_items.append(EstimateLineItem(
                line_no=idx * 10,
                phase=component.phase.value,
                description=component.description,
                quantity=component.quantity,
                quantity_unit=component.quantity_unit,
                waste_factor=component.waste_factor,
                base_unit_cost=base,
                low_unit_cost=low,
                high_unit_cost=high,
                currency=self.spec.currency,
                pricing_status=pricing_status,
                cost_behavior=component.cost_behavior.value,
                recurrence_months=component.recurrence_months,
                start_month=component.start_month,
                escalation_pct=component.escalation_pct or self.spec.escalation_pct,
                extended_base=extended_base,
                extended_low=extended_low,
                extended_high=extended_high,
                assumptions={
                    "source": component.source,
                    "deployment_type": self.spec.deployment_type.value,
                    "redundancy": self.spec.redundancy.value,
                    "tier_level": self.spec.tier_level.value,
                },
            ))

        return line_items


# ---------------------------------------------------------------------------
# Lifecycle cost calculator
# ---------------------------------------------------------------------------


class LifecycleCostCalculator:
    """Calculates lifecycle costs from estimate line items.

    Computes present values, phase subtotals, and unit economics
    using the same formulas as the estimate_cost_rollup view.
    """

    def __init__(self, spec: DeploymentSpec) -> None:
        self.spec = spec

    def calculate_pv(
        self,
        line_items: list[EstimateLineItem],
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate total present value for base, low, and high cases.

        Uses the same formula as estimate_cost_rollup:
        PV = Σ [extended × (1 + escalation)^(months/12) / (1 + discount)^(month/12)]
        """
        total_pv_base = ZERO
        total_pv_low = ZERO
        total_pv_high = ZERO

        for item in line_items:
            pv_base, pv_low, pv_high = self._line_pv(item)
            total_pv_base += pv_base
            total_pv_low += pv_low
            total_pv_high += pv_high

        return total_pv_base, total_pv_low, total_pv_high

    def _line_pv(self, item: EstimateLineItem) -> tuple[Decimal, Decimal, Decimal]:
        """Calculate present value for a single line item."""
        total_base = ZERO
        total_low = ZERO
        total_high = ZERO

        # Generate recurrence months
        if item.cost_behavior in ("fixed_recurring", "variable", "step_fixed"):
            if item.recurrence_months and item.recurrence_months > 0:
                recurrence = item.recurrence_months
            else:
                recurrence = self.spec.horizon_months + 1
        else:
            recurrence = self.spec.horizon_months + 1

        for month in range(item.start_month, self.spec.horizon_months, recurrence):
            # Escalation factor
            months_elapsed = month - item.start_month
            years = Decimal(months_elapsed) / Decimal(MONTHS_PER_YEAR)
            escalation_factor = (ONE + item.escalation_pct) ** years

            # Discount factor
            discount_years = Decimal(month) / Decimal(MONTHS_PER_YEAR)
            discount_factor = (ONE + self.spec.discount_rate) ** (-discount_years)

            total_base += item.extended_base * escalation_factor * discount_factor
            total_low += item.extended_low * escalation_factor * discount_factor
            total_high += item.extended_high * escalation_factor * discount_factor

        return total_base, total_low, total_high

    def calculate_phase_subtotals(
        self,
        line_items: list[EstimateLineItem],
    ) -> list[PhaseSubtotal]:
        """Calculate subtotals by cost phase."""
        phase_map: dict[str, PhaseSubtotal] = {}

        for item in line_items:
            if item.phase not in phase_map:
                phase_map[item.phase] = PhaseSubtotal(
                    phase=item.phase,
                    line_count=0,
                    total_base=Decimal("0"),
                    total_low=Decimal("0"),
                    total_high=Decimal("0"),
                    total_pv_base=Decimal("0"),
                    total_pv_low=Decimal("0"),
                    total_pv_high=Decimal("0"),
                )
            ps = phase_map[item.phase]
            ps.line_count += 1
            ps.total_base += item.extended_base
            ps.total_low += item.extended_low
            ps.total_high += item.extended_high

            pv_base, pv_low, pv_high = self._line_pv(item)
            ps.total_pv_base += pv_base
            ps.total_pv_low += pv_low
            ps.total_pv_high += pv_high

        return [phase_map[phase] for phase in sorted(phase_map.keys())]

    def calculate_first_period_cost(self, line_items: list[EstimateLineItem]) -> Decimal:
        """Calculate the cost in the first period (month 0)."""
        total = ZERO
        for item in line_items:
            if item.start_month == 0:
                total += item.extended_base
        return total

    def calculate_annual_opex(self, line_items: list[EstimateLineItem]) -> tuple[Decimal, Decimal]:
        """Calculate annual energy and maintenance OPEX."""
        energy_cost = ZERO
        maintenance_cost = ZERO
        for item in line_items:
            if item.phase == CostPhase.ENERGY.value:
                energy_cost = item.extended_base
            elif item.phase == CostPhase.MAINTENANCE.value:
                maintenance_cost = item.extended_base
        return energy_cost, maintenance_cost


# ---------------------------------------------------------------------------
# Main estimation engine
# ---------------------------------------------------------------------------


class BottomUpEstimator:
    """Main entry point for bottom-up cost estimation.

    Orchestrates the full estimation pipeline:
    1. Size components from deployment spec
    2. Build line items with resolved unit costs
    3. Calculate lifecycle present values
    4. Compute unit economics
    5. Return structured estimate result

    Example:
        spec = DeploymentSpec(
            name="New 2MW DC",
            it_capacity_kw=Decimal("2000"),
            geography="US-East",
        )
        estimator = BottomUpEstimator(spec)
        result = estimator.estimate()
        print(f"Total PV: {result.total_pv_base:,.2f} {result.currency}")
    """

    def __init__(
        self,
        spec: DeploymentSpec,
        price_engine: Optional[PriceEngine] = None,
    ) -> None:
        self.spec = spec
        self.builder = EstimateBuilder(spec, price_engine)
        self.calculator = LifecycleCostCalculator(spec)

    def estimate(self) -> EstimateResult:
        """Run the full bottom-up estimation and return the result."""
        # Build line items
        line_items = self.builder.build_line_items()

        # Calculate lifecycle costs
        total_pv_base, total_pv_low, total_pv_high = self.calculator.calculate_pv(line_items)
        phase_subtotals = self.calculator.calculate_phase_subtotals(line_items)
        first_period_cost = self.calculator.calculate_first_period_cost(line_items)
        annual_energy_cost, annual_maintenance_cost = self.calculator.calculate_annual_opex(line_items)

        # Calculate totals
        total_base = sum(item.extended_base for item in line_items)
        total_low = sum(item.extended_low for item in line_items)
        total_high = sum(item.extended_high for item in line_items)

        # Contingency
        contingency_amount = total_base * self.spec.contingency_pct

        # Equivalent annual cost
        horizon_years = Decimal(self.spec.horizon_months) / Decimal(MONTHS_PER_YEAR)
        eac = equivalent_annual_cost(
            float(total_pv_base),
            float(horizon_years),
            float(self.spec.discount_rate),
        )

        # Unit economics
        cost_per_kw = cost_per_kw_year(
            eac,
            float(self.spec.it_capacity_kw),
        )
        cost_per_rack = cost_per_rack_year(
            eac,
            float(self.spec.effective_rack_count),
        )
        cost_per_m2 = cost_per_m2_year(
            eac,
            float(self.spec.effective_white_space_m2),
        )
        cost_per_kwh = None
        if self.spec.annual_it_energy > 0:
            cost_per_kwh_val = eac / float(self.spec.annual_it_energy)
            cost_per_kwh = Decimal(str(cost_per_kwh_val))

        return EstimateResult(
            spec=self.spec,
            line_items=line_items,
            phase_subtotals=phase_subtotals,
            total_base=total_base,
            total_low=total_low,
            total_high=total_high,
            total_pv_base=total_pv_base,
            total_pv_low=total_pv_low,
            total_pv_high=total_pv_high,
            first_period_cost=first_period_cost,
            annual_energy_cost=annual_energy_cost,
            annual_maintenance_cost=annual_maintenance_cost,
            equivalent_annual_cost=Decimal(str(eac)),
            cost_per_kw_year=Decimal(str(cost_per_kw.value)) if cost_per_kw.value else None,
            cost_per_rack_year=Decimal(str(cost_per_rack.value)) if cost_per_rack.value else None,
            cost_per_m2_year=Decimal(str(cost_per_m2.value)) if cost_per_m2.value else None,
            cost_per_kwh=cost_per_kwh,
            contingency_amount=contingency_amount,
            currency=self.spec.currency,
        )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def estimate_deployment(
    *,
    name: str,
    it_capacity_kw: float | Decimal,
    geography: str = "US-East",
    currency: str = "USD",
    deployment_type: str = "greenfield",
    redundancy: str = "N+1",
    tier_level: str = "Tier III",
    pue: float | Decimal = 1.45,
    horizon_months: int = 180,
    discount_rate: float | Decimal = 0.08,
    contingency_pct: float | Decimal = 0.10,
    rack_count: Optional[int] = None,
    white_space_m2: Optional[float | Decimal] = None,
    price_engine: Optional[PriceEngine] = None,
    **kwargs: Any,
) -> EstimateResult:
    """Convenience function for quick bottom-up estimation.

    Creates a DeploymentSpec from keyword arguments and runs the estimator.
    Additional keyword arguments are passed to DeploymentSpec.

    Example:
        result = estimate_deployment(
            name="Edge DC 500kW",
            it_capacity_kw=500,
            geography="EU-West",
            redundancy="N+1",
        )
    """
    spec = DeploymentSpec(
        name=name,
        it_capacity_kw=Decimal(str(it_capacity_kw)),
        geography=geography,
        currency=currency,
        deployment_type=DeploymentType(deployment_type),
        redundancy=RedundancyLevel(redundancy),
        tier_level=TierLevel(tier_level),
        pue=Decimal(str(pue)),
        horizon_months=horizon_months,
        discount_rate=Decimal(str(discount_rate)),
        contingency_pct=Decimal(str(contingency_pct)),
        rack_count=rack_count,
        white_space_m2=Decimal(str(white_space_m2)) if white_space_m2 else None,
        **kwargs,
    )
    estimator = BottomUpEstimator(spec, price_engine)
    return estimator.estimate()


def quick_estimate(
    it_capacity_kw: float,
    geography: str = "US-East",
) -> dict[str, Any]:
    """Quick estimate with sensible defaults for rapid exploration.

    Returns a summary dict with key metrics.
    """
    result = estimate_deployment(
        name=f"Quick estimate {it_capacity_kw} kW",
        it_capacity_kw=it_capacity_kw,
        geography=geography,
    )
    return result.to_dict()
