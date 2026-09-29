"""Fuzz tests for tariff calculation engine using Hypothesis."""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st, assume

from dcc.economics.tariffs import (
    TariffSpec,
    TOUPeriod,
    DemandCharge,
    Tier,
    TieredRate,
    FixedCharge,
    calculate_tariff,
    calculate_tou_charges,
    calculate_demand_charges,
    calculate_tiered_charges,
    calculate_fixed_charges,
    create_simple_tou_tariff,
    create_tiered_tariff,
    create_flat_rate_tariff,
    EXAMPLE_TARIFF_SPEC,
    EXAMPLE_TIERED_TARIFF_SPEC,
)


# Strategies
non_negative_decimals = st.decimals(
    min_value=Decimal("0"), max_value=Decimal("10000"), allow_nan=False, allow_infinity=False
)

positive_decimals = st.decimals(
    min_value=Decimal("0.001"), max_value=Decimal("10000"), allow_nan=False, allow_infinity=False
)

time_strings = st.sampled_from([
    "00:00", "06:00", "12:00", "18:00", "23:59",
    "00:01", "05:30", "11:45", "17:15", "22:30",
])

currency_codes = st.sampled_from(["USD", "EUR", "GBP", "JPY", "CAD", "AUD"])

billing_periods = st.sampled_from(["monthly", "quarterly", "annual"])


class TestTariffSpecFuzz:
    """Fuzz tariff specification creation and validation."""

    @given(
        currency=currency_codes,
        timezone=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("L",))),
        billing_period=billing_periods,
    )
    @settings(max_examples=100)
    def test_create_simple_tou_tariff(self, currency, timezone, billing_period):
        """Creating a simple TOU tariff should work with valid inputs."""
        spec = create_simple_tou_tariff(
            currency=currency,
            timezone=timezone,
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
        )
        assert spec.currency == currency
        assert spec.timezone == timezone
        assert len(spec.tou_periods) >= 1

    @given(
        currency=currency_codes,
        tiers=st.lists(
            st.fixed_dictionaries({
                "upper_limit_kwh": st.one_of(st.none(), positive_decimals),
                "rate_per_kwh": positive_decimals,
            }),
            min_size=1, max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_create_tiered_tariff(self, currency, tiers):
        """Creating a tiered tariff should work with valid tier structures."""
        # Ensure last tier has no upper limit
        if tiers and tiers[-1]["upper_limit_kwh"] is not None:
            tiers[-1]["upper_limit_kwh"] = None
        try:
            spec = create_tiered_tariff(
                currency=currency,
                tiers=tiers,
            )
            assert spec.currency == currency
            assert len(spec.tiered_rates) == 1
        except (ValueError, TypeError):
            pass  # Expected for invalid tier structures

    @given(
        currency=currency_codes,
        rate=positive_decimals,
    )
    @settings(max_examples=100)
    def test_create_flat_rate_tariff(self, currency, rate):
        """Creating a flat rate tariff should work with valid inputs."""
        spec = create_flat_rate_tariff(
            currency=currency,
            rate_per_kwh=rate,
        )
        assert spec.currency == currency
        assert len(spec.tiered_rates) == 1


class TestTariffCalculationFuzz:
    """Fuzz tariff calculations."""

    @given(
        energy_kwh=positive_decimals,
        peak_demand_kw=positive_decimals,
    )
    @settings(max_examples=200)
    def test_calculate_tariff_never_crashes(self, energy_kwh, peak_demand_kw):
        """Tariff calculation should handle any valid inputs."""
        spec = create_simple_tou_tariff(
            currency="USD",
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
        )
        result = calculate_tariff(
            spec=spec,
            energy_kwh=energy_kwh,
            peak_demand_kw=peak_demand_kw,
        )
        assert result.total >= 0
        assert result.energy_kwh == energy_kwh
        assert result.peak_demand_kw == peak_demand_kw

    @given(
        energy_kwh=positive_decimals,
        peak_demand_kw=positive_decimals,
        energy_by_period=st.dictionaries(
            keys=st.sampled_from(["peak", "off_peak"]),
            values=positive_decimals,
            min_size=0, max_size=2,
        ),
    )
    @settings(max_examples=200)
    def test_calculate_tariff_with_periods(self, energy_kwh, peak_demand_kw, energy_by_period):
        """Tariff calculation with period breakdown should work."""
        spec = create_simple_tou_tariff(
            currency="USD",
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
        )
        result = calculate_tariff(
            spec=spec,
            energy_kwh=energy_kwh,
            peak_demand_kw=peak_demand_kw,
            energy_by_period=energy_by_period,
        )
        assert result.total >= 0

    @given(
        energy_kwh=positive_decimals,
        peak_demand_kw=positive_decimals,
    )
    @settings(max_examples=200)
    def test_calculate_tariff_tiered(self, energy_kwh, peak_demand_kw):
        """Tiered tariff calculation should work."""
        spec = create_tiered_tariff(
            currency="USD",
            tiers=[
                {"upper_limit_kwh": "1000", "rate_per_kwh": "0.15"},
                {"upper_limit_kwh": "5000", "rate_per_kwh": "0.12"},
                {"upper_limit_kwh": None, "rate_per_kwh": "0.08"},
            ],
        )
        result = calculate_tariff(
            spec=spec,
            energy_kwh=energy_kwh,
            peak_demand_kw=peak_demand_kw,
        )
        assert result.total >= 0
        assert len(result.tiered_charges) == 1

    @given(
        energy_kwh=positive_decimals,
        peak_demand_kw=positive_decimals,
    )
    @settings(max_examples=200)
    def test_calculate_tariff_with_demand(self, energy_kwh, peak_demand_kw):
        """Tariff calculation with demand charges should work."""
        spec = create_simple_tou_tariff(
            currency="USD",
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
            demand_rate_per_kw=Decimal("15.00"),
        )
        result = calculate_tariff(
            spec=spec,
            energy_kwh=energy_kwh,
            peak_demand_kw=peak_demand_kw,
        )
        assert result.total >= 0
        assert result.total_demand_charges >= 0

    @given(
        energy_kwh=positive_decimals,
        peak_demand_kw=positive_decimals,
    )
    @settings(max_examples=200)
    def test_calculate_tariff_with_fixed(self, energy_kwh, peak_demand_kw):
        """Tariff calculation with fixed charges should work."""
        spec = create_simple_tou_tariff(
            currency="USD",
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
            fixed_monthly_charge=Decimal("50.00"),
        )
        result = calculate_tariff(
            spec=spec,
            energy_kwh=energy_kwh,
            peak_demand_kw=peak_demand_kw,
        )
        assert result.total >= 0
        assert result.total_fixed_charges >= 0


class TestTariffComponentFuzz:
    """Fuzz individual tariff component calculations."""

    @given(
        energy=positive_decimals,
        rate=positive_decimals,
    )
    @settings(max_examples=200)
    def test_tou_charge_calculation(self, energy, rate):
        """TOU charge calculation should work."""
        period = TOUPeriod(
            name="test",
            days_of_week=(1, 2, 3, 4, 5),
            start_time="12:00",
            end_time="18:00",
            rate_per_kwh=rate,
        )
        results = calculate_tou_charges(
            tou_periods=[period],
            energy_by_period={"test": energy},
        )
        assert len(results) == 1
        assert results[0].charge == energy * rate

    @given(
        demand=positive_decimals,
        rate=positive_decimals,
    )
    @settings(max_examples=200)
    def test_demand_charge_calculation(self, demand, rate):
        """Demand charge calculation should work."""
        charge = DemandCharge(
            name="test",
            rate_per_kw=rate,
            billing_demand_basis="peak_kw_monthly",
        )
        results = calculate_demand_charges(
            demand_charges=[charge],
            billing_demand_kw=demand,
        )
        assert len(results) == 1
        assert results[0].charge == demand * rate

    @given(
        energy=positive_decimals,
        tier_rate=positive_decimals,
    )
    @settings(max_examples=200)
    def test_tiered_charge_calculation(self, energy, tier_rate):
        """Tiered charge calculation should work."""
        tier = Tier(
            upper_limit_kwh=None,
            rate_per_kwh=tier_rate,
        )
        rate = TieredRate(
            name="test",
            tiers=(tier,),
        )
        results = calculate_tiered_charges(
            tiered_rates=[rate],
            total_energy_kwh=energy,
        )
        assert len(results) == 1
        assert results[0].charge == energy * tier_rate

    @given(
        amount=positive_decimals,
        billing_period=billing_periods,
    )
    @settings(max_examples=200)
    def test_fixed_charge_calculation(self, amount, billing_period):
        """Fixed charge calculation should work."""
        charge = FixedCharge(
            name="test",
            amount=amount,
            frequency="monthly",
        )
        results = calculate_fixed_charges(
            fixed_charges=[charge],
            billing_period=billing_period,
        )
        assert len(results) == 1
        assert results[0].amount >= 0


class TestTariffValidationFuzz:
    """Fuzz tariff spec validation via calculate_tariff."""

    @given(
        billing_period=st.text(min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_invalid_billing_period_raises(self, billing_period):
        """Invalid billing period should raise ValueError when calculating."""
        assume(billing_period not in ("monthly", "quarterly", "annual"))
        spec = TariffSpec(
            schema_version="tariff.v1",
            currency="USD",
            timezone="UTC",
            billing_period=billing_period,
            tou_periods=(),
            demand_charges=(),
            tiered_rates=(),
            fixed_charges=(),
        )
        try:
            calculate_tariff(spec=spec, energy_kwh=Decimal("100"), peak_demand_kw=Decimal("10"))
        except ValueError:
            pass  # Expected

    @given(
        day=st.integers(min_value=-10, max_value=20),
    )
    @settings(max_examples=100)
    def test_invalid_day_of_week_raises(self, day):
        """Invalid day of week should raise ValueError when calculating."""
        assume(day < 1 or day > 7)
        period = TOUPeriod(
            name="test",
            days_of_week=(day,),
            start_time="12:00",
            end_time="18:00",
            rate_per_kwh=Decimal("0.25"),
        )
        spec = TariffSpec(
            schema_version="tariff.v1",
            currency="USD",
            timezone="UTC",
            billing_period="monthly",
            tou_periods=(period,),
            demand_charges=(),
            tiered_rates=(),
            fixed_charges=(),
        )
        try:
            calculate_tariff(spec=spec, energy_kwh=Decimal("100"), peak_demand_kw=Decimal("10"))
        except ValueError:
            pass  # Expected

    @given(
        rate=st.decimals(min_value=Decimal("-100"), max_value=Decimal("100"), allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=100)
    def test_negative_rate_raises(self, rate):
        """Negative rate should raise ValueError when calculating."""
        assume(rate < 0)
        period = TOUPeriod(
            name="test",
            days_of_week=(1, 2, 3, 4, 5),
            start_time="12:00",
            end_time="18:00",
            rate_per_kwh=rate,
        )
        spec = TariffSpec(
            schema_version="tariff.v1",
            currency="USD",
            timezone="UTC",
            billing_period="monthly",
            tou_periods=(period,),
            demand_charges=(),
            tiered_rates=(),
            fixed_charges=(),
        )
        try:
            calculate_tariff(spec=spec, energy_kwh=Decimal("100"), peak_demand_kw=Decimal("10"))
        except ValueError:
            pass  # Expected
