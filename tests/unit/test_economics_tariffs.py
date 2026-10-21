"""Unit tests for dcc.economics.tariffs module."""

import unittest
from decimal import Decimal
from typing import Any

from dcc.economics.tariffs import (
    DemandCharge,
    DemandChargeResult,
    FixedCharge,
    FixedChargeResult,
    TariffCalculationResult,
    TariffSpec,
    Tier,
    TieredChargeResult,
    TieredRate,
    TOUChargeResult,
    TOUPeriod,
    calculate_demand_charges,
    calculate_fixed_charges,
    calculate_tariff,
    calculate_tiered_charges,
    calculate_tou_charges,
    create_flat_rate_tariff,
    create_simple_tou_tariff,
    create_tiered_tariff,
)


def _empty_spec(**overrides: Any) -> TariffSpec:
    """Build a fully-populated TariffSpec, overriding individual sections.

    TariffSpec has no defaults: all eight fields (schema_version, currency,
    timezone, billing_period and the four charge collections) are required,
    so tests must supply every one of them.
    """
    fields: dict[str, Any] = {
        "schema_version": "tariff.v1",
        "currency": "USD",
        "timezone": "America/New_York",
        "billing_period": "monthly",
        "tou_periods": (),
        "demand_charges": (),
        "tiered_rates": (),
        "fixed_charges": (),
    }
    fields.update(overrides)
    return TariffSpec(**fields)


class TestTOUPeriod(unittest.TestCase):
    def test_creation(self):
        p = TOUPeriod(
            name="peak",
            days_of_week=(1, 2, 3, 4, 5),
            start_time="12:00",
            end_time="18:00",
            rate_per_kwh=Decimal("0.25"),
        )
        self.assertEqual(p.name, "peak")
        self.assertEqual(p.rate_per_kwh, Decimal("0.25"))

    def test_from_dict(self):
        data = {
            "name": "peak",
            "days_of_week": [1, 2, 3, 4, 5],
            "start_time": "12:00",
            "end_time": "18:00",
            "rate_per_kwh": "0.25",
        }
        p = TOUPeriod.from_dict(data)
        self.assertEqual(p.name, "peak")
        # from_dict normalizes days_of_week to a tuple of ints
        self.assertEqual(p.days_of_week, (1, 2, 3, 4, 5))
        self.assertEqual(p.rate_per_kwh, Decimal("0.25"))


class TestDemandCharge(unittest.TestCase):
    def test_creation(self):
        # billing_demand_basis is required: the tariff schema records how billing
        # demand is determined (e.g. "peak_kw_monthly"), and a demand charge for
        # which this is unknown cannot be applied to a consumption profile.
        d = DemandCharge(
            name="peak_demand",
            rate_per_kw=Decimal("15.00"),
            billing_demand_basis="peak_kw_monthly",
        )
        self.assertEqual(d.name, "peak_demand")
        self.assertEqual(d.billing_demand_basis, "peak_kw_monthly")

    def test_from_dict_defaults_basis(self):
        # The schema allows omitting billing_demand_basis; from_dict defaults it
        # to "peak_kw_monthly" rather than failing on older tariff specs.
        d = DemandCharge.from_dict({"name": "peak_demand", "rate_per_kw": "15.00"})
        self.assertEqual(d.billing_demand_basis, "peak_kw_monthly")


class TestTier(unittest.TestCase):
    def test_creation(self):
        # The tier bound is named upper_limit_kwh (units are part of the name).
        t = Tier(
            upper_limit_kwh=Decimal(1000),
            rate_per_kwh=Decimal("0.10"),
        )
        self.assertEqual(t.upper_limit_kwh, Decimal(1000))

    def test_unlimited_tier(self):
        # None means "no upper bound"; the last tier of a tiered rate must use it.
        t = Tier(upper_limit_kwh=None, rate_per_kwh=Decimal("0.06"))
        self.assertIsNone(t.upper_limit_kwh)


class TestTieredRate(unittest.TestCase):
    def test_creation(self):
        r = TieredRate(
            name="energy_tiers",
            tiers=(Tier(upper_limit_kwh=Decimal(1000), rate_per_kwh=Decimal("0.10")),),
        )
        self.assertEqual(r.name, "energy_tiers")
        # tiers is stored as a tuple, so the structure is immutable/hashable.
        self.assertIsInstance(r.tiers, tuple)
        self.assertEqual(len(r.tiers), 1)


class TestFixedCharge(unittest.TestCase):
    def test_creation(self):
        f = FixedCharge(
            name="service_fee",
            amount=Decimal("50.00"),
            frequency="monthly",
        )
        self.assertEqual(f.name, "service_fee")


class TestTariffSpec(unittest.TestCase):
    def test_creation(self):
        t = _empty_spec(timezone="America/New_York")
        self.assertEqual(t.currency, "USD")
        self.assertEqual(t.schema_version, "tariff.v1")
        self.assertEqual(t.billing_period, "monthly")

    def test_from_dict_defaults(self):
        # from_dict fills schema defaults, so a sparse spec is usable.
        t = TariffSpec.from_dict({})
        self.assertEqual(t.schema_version, "tariff.v1")
        self.assertEqual(t.tou_periods, ())


class TestTOUChargeResult(unittest.TestCase):
    def test_creation(self):
        r = TOUChargeResult(
            period_name="peak",
            energy_kwh=Decimal(1000),
            rate_per_kwh=Decimal("0.25"),
            charge=Decimal("250.00"),
        )
        self.assertEqual(r.period_name, "peak")
        self.assertEqual(r.charge, Decimal("250.00"))


class TestDemandChargeResult(unittest.TestCase):
    def test_creation(self):
        r = DemandChargeResult(
            charge_name="peak_demand",
            billing_demand_kw=Decimal(100),
            rate_per_kw=Decimal("15.00"),
            charge=Decimal("1500.00"),
        )
        self.assertEqual(r.charge_name, "peak_demand")
        self.assertEqual(r.charge, Decimal("1500.00"))


class TestTieredChargeResult(unittest.TestCase):
    def test_creation(self):
        r = TieredChargeResult(
            rate_name="energy_tiers",
            total_energy_kwh=Decimal(1000),
            charge=Decimal("100.00"),
        )
        self.assertEqual(r.rate_name, "energy_tiers")
        # tier_breakdown defaults to an empty list (per-result breakdown).
        self.assertEqual(r.tier_breakdown, [])


class TestFixedChargeResult(unittest.TestCase):
    def test_creation(self):
        r = FixedChargeResult(
            charge_name="service_fee",
            amount=Decimal("50.00"),
            frequency="monthly",
        )
        self.assertEqual(r.charge_name, "service_fee")
        self.assertEqual(r.amount, Decimal("50.00"))


class TestTariffCalculationResult(unittest.TestCase):
    def test_creation(self):
        r = TariffCalculationResult(
            total_energy_charges=Decimal("250.00"),
            total_demand_charges=Decimal("1500.00"),
            total_fixed_charges=Decimal("50.00"),
            total=Decimal("1800.00"),
            energy_kwh=Decimal(1000),
            peak_demand_kw=Decimal(100),
            tou_charges=[],
            demand_charges=[],
            tiered_charges=[],
            fixed_charges=[],
            currency="USD",
            billing_period="monthly",
        )
        self.assertEqual(r.total, Decimal("1800.00"))
        self.assertEqual(r.currency, "USD")


class TestCalculateTouCharges(unittest.TestCase):
    def test_calculate(self):
        # calculate_tou_charges is keyword-only and takes energy BY PERIOD
        # (a name -> kWh mapping), not a single total.
        periods = [
            TOUPeriod(
                name="peak",
                days_of_week=(1, 2, 3, 4, 5),
                start_time="12:00",
                end_time="18:00",
                rate_per_kwh=Decimal("0.25"),
            ),
        ]
        result = calculate_tou_charges(
            tou_periods=periods,
            energy_by_period={"peak": Decimal(1000)},
        )
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], TOUChargeResult)
        self.assertEqual(result[0].charge, Decimal("250.00"))

    def test_period_with_no_energy_is_skipped(self):
        periods = [
            TOUPeriod(
                name="peak",
                days_of_week=(1, 2, 3, 4, 5),
                start_time="12:00",
                end_time="18:00",
                rate_per_kwh=Decimal("0.25"),
            ),
        ]
        self.assertEqual(
            calculate_tou_charges(tou_periods=periods, energy_by_period={}), []
        )


class TestCalculateDemandCharges(unittest.TestCase):
    def test_calculate(self):
        charges = [
            DemandCharge(
                name="peak",
                rate_per_kw=Decimal("15.00"),
                billing_demand_basis="peak_kw_monthly",
            )
        ]
        result = calculate_demand_charges(
            demand_charges=charges,
            billing_demand_kw=Decimal(100),
        )
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], DemandChargeResult)
        self.assertEqual(result[0].charge, Decimal("1500.00"))


class TestCalculateTieredCharges(unittest.TestCase):
    def test_calculate(self):
        tiers = TieredRate(
            name="test",
            tiers=(Tier(upper_limit_kwh=None, rate_per_kwh=Decimal("0.10")),),
        )
        result = calculate_tiered_charges(
            tiered_rates=[tiers],
            total_energy_kwh=Decimal(1000),
        )
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], TieredChargeResult)
        self.assertEqual(result[0].charge, Decimal("100.00"))

    def test_tier_breakdown(self):
        # 1500 kWh into a 1000 kWh tier at 0.10 plus an unlimited tier at 0.05
        rate = TieredRate(
            name="test",
            tiers=(
                Tier(upper_limit_kwh=Decimal(1000), rate_per_kwh=Decimal("0.10")),
                Tier(upper_limit_kwh=None, rate_per_kwh=Decimal("0.05")),
            ),
        )
        result = calculate_tiered_charges(
            tiered_rates=[rate], total_energy_kwh=Decimal(1500)
        )
        self.assertEqual(result[0].charge, Decimal("125.00"))
        self.assertEqual(len(result[0].tier_breakdown), 2)


class TestCalculateFixedCharges(unittest.TestCase):
    def test_calculate(self):
        # The second argument is the BILLING PERIOD ("monthly"/"quarterly"/"annual"),
        # not a month count: the function scales each charge to the period.
        charges = [FixedCharge(name="fee", amount=Decimal(50), frequency="monthly")]
        result = calculate_fixed_charges(fixed_charges=charges, billing_period="annual")
        self.assertIsInstance(result, list)
        self.assertIsInstance(result[0], FixedChargeResult)
        self.assertEqual(result[0].amount, Decimal(600))

    def test_defaults_to_monthly(self):
        charges = [FixedCharge(name="fee", amount=Decimal(50), frequency="monthly")]
        result = calculate_fixed_charges(fixed_charges=charges)
        self.assertEqual(result[0].amount, Decimal(50))


class TestCalculateTariff(unittest.TestCase):
    def test_calculate(self):
        spec = _empty_spec(
            tou_periods=(
                TOUPeriod(
                    name="peak",
                    days_of_week=(1, 2, 3, 4, 5),
                    start_time="12:00",
                    end_time="18:00",
                    rate_per_kwh=Decimal("0.25"),
                ),
            ),
            demand_charges=(
                DemandCharge(
                    name="peak_demand",
                    rate_per_kw=Decimal("15.00"),
                    billing_demand_basis="peak_kw_monthly",
                ),
            ),
            fixed_charges=(
                FixedCharge(
                    name="service_fee", amount=Decimal(50), frequency="monthly"
                ),
            ),
        )
        # calculate_tariff is keyword-only and needs peak_demand_kw as well as energy.
        result = calculate_tariff(
            spec=spec,
            energy_kwh=Decimal(1000),
            peak_demand_kw=Decimal(100),
        )
        self.assertIsInstance(result, TariffCalculationResult)
        self.assertEqual(result.total, Decimal("1800.00"))

    def test_empty_spec_totals_zero(self):
        result = calculate_tariff(
            spec=_empty_spec(), energy_kwh=Decimal(0), peak_demand_kw=Decimal(0)
        )
        self.assertEqual(result.total, Decimal(0))


class TestCreateSimpleTouTariff(unittest.TestCase):
    def test_create(self):
        t = create_simple_tou_tariff(
            currency="USD",
            timezone="America/New_York",
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
        )
        self.assertIsInstance(t, TariffSpec)
        self.assertEqual(t.currency, "USD")
        self.assertIn("peak", [p.name for p in t.tou_periods])
        self.assertIn("off_peak", [p.name for p in t.tou_periods])


class TestCreateTieredTariff(unittest.TestCase):
    def test_create(self):
        # create_tiered_tariff takes tier DICTS (schema keys upper_limit_kwh /
        # rate_per_kwh) rather than parallel threshold/rate lists; the last tier
        # must be unlimited (None) for the resulting spec to validate.
        t = create_tiered_tariff(
            currency="USD",
            timezone="America/New_York",
            tiers=[
                {"upper_limit_kwh": "1000", "rate_per_kwh": "0.10"},
                {"upper_limit_kwh": None, "rate_per_kwh": "0.08"},
            ],
        )
        self.assertIsInstance(t, TariffSpec)
        self.assertEqual(len(t.tiered_rates), 1)
        self.assertEqual(len(t.tiered_rates[0].tiers), 2)


class TestCreateFlatRateTariff(unittest.TestCase):
    def test_create(self):
        # create_flat_rate_tariff names its rate parameter rate_per_kwh.
        t = create_flat_rate_tariff(
            currency="USD",
            timezone="America/New_York",
            rate_per_kwh=Decimal("0.10"),
        )
        self.assertIsInstance(t, TariffSpec)
        # A flat rate is modelled as one tiered rate with a single unlimited tier.
        self.assertEqual(t.tiered_rates[0].tiers[0].upper_limit_kwh, None)

    def test_charges_flat_rate(self):
        t = create_flat_rate_tariff(rate_per_kwh=Decimal("0.10"))
        result = calculate_tariff(
            spec=t, energy_kwh=Decimal(1000), peak_demand_kw=Decimal(0)
        )
        self.assertEqual(result.total, Decimal("100.00"))


if __name__ == "__main__":
    unittest.main()
