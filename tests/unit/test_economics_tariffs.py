"""Unit tests for dcc.economics.tariffs module."""
import unittest
from decimal import Decimal

from dcc.economics.tariffs import (
    TOUPeriod,
    DemandCharge,
    Tier,
    TieredRate,
    FixedCharge,
    TariffSpec,
    TOUChargeResult,
    DemandChargeResult,
    TieredChargeResult,
    FixedChargeResult,
    TariffCalculationResult,
    calculate_tou_charges,
    calculate_demand_charges,
    calculate_tiered_charges,
    calculate_fixed_charges,
    calculate_tariff,
    create_simple_tou_tariff,
    create_tiered_tariff,
    create_flat_rate_tariff,
)


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


class TestDemandCharge(unittest.TestCase):
    def test_creation(self):
        d = DemandCharge(
            name="peak_demand",
            rate_per_kw=Decimal("15.00"),
        )
        self.assertEqual(d.name, "peak_demand")


class TestTier(unittest.TestCase):
    def test_creation(self):
        t = Tier(
            upper_limit=Decimal("1000"),
            rate_per_kwh=Decimal("0.10"),
        )
        self.assertEqual(t.upper_limit, Decimal("1000"))


class TestTieredRate(unittest.TestCase):
    def test_creation(self):
        r = TieredRate(
            name="energy_tiers",
            tiers=[Tier(upper_limit=Decimal("1000"), rate_per_kwh=Decimal("0.10"))],
        )
        self.assertEqual(r.name, "energy_tiers")


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
        t = TariffSpec(
            currency="USD",
            timezone="America/New_York",
        )
        self.assertEqual(t.currency, "USD")


class TestTOUChargeResult(unittest.TestCase):
    def test_creation(self):
        r = TOUChargeResult()
        self.assertIsNotNone(r)


class TestDemandChargeResult(unittest.TestCase):
    def test_creation(self):
        r = DemandChargeResult()
        self.assertIsNotNone(r)


class TestTieredChargeResult(unittest.TestCase):
    def test_creation(self):
        r = TieredChargeResult()
        self.assertIsNotNone(r)


class TestFixedChargeResult(unittest.TestCase):
    def test_creation(self):
        r = FixedChargeResult()
        self.assertIsNotNone(r)


class TestTariffCalculationResult(unittest.TestCase):
    def test_creation(self):
        r = TariffCalculationResult()
        self.assertIsNotNone(r)


class TestCalculateTouCharges(unittest.TestCase):
    def test_calculate(self):
        periods = [
            TOUPeriod(
                name="peak",
                days_of_week=(1, 2, 3, 4, 5),
                start_time="12:00",
                end_time="18:00",
                rate_per_kwh=Decimal("0.25"),
            ),
        ]
        result = calculate_tou_charges(periods, Decimal("1000"))
        self.assertIsInstance(result, TOUChargeResult)


class TestCalculateDemandCharges(unittest.TestCase):
    def test_calculate(self):
        charges = [DemandCharge(name="peak", rate_per_kw=Decimal("15.00"))]
        result = calculate_demand_charges(charges, Decimal("100"))
        self.assertIsInstance(result, DemandChargeResult)


class TestCalculateTieredCharges(unittest.TestCase):
    def test_calculate(self):
        tiers = TieredRate(
            name="test",
            tiers=[Tier(upper_limit=None, rate_per_kwh=Decimal("0.10"))],
        )
        result = calculate_tiered_charges([tiers], Decimal("1000"))
        self.assertIsInstance(result, TieredChargeResult)


class TestCalculateFixedCharges(unittest.TestCase):
    def test_calculate(self):
        charges = [FixedCharge(name="fee", amount=Decimal("50"), frequency="monthly")]
        result = calculate_fixed_charges(charges, months=12)
        self.assertIsInstance(result, FixedChargeResult)


class TestCalculateTariff(unittest.TestCase):
    def test_calculate(self):
        spec = TariffSpec(currency="USD", timezone="America/New_York")
        result = calculate_tariff(spec, Decimal("1000"))
        self.assertIsInstance(result, TariffCalculationResult)


class TestCreateSimpleTouTariff(unittest.TestCase):
    def test_create(self):
        t = create_simple_tou_tariff(
            currency="USD",
            timezone="America/New_York",
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
        )
        self.assertIsInstance(t, TariffSpec)


class TestCreateTieredTariff(unittest.TestCase):
    def test_create(self):
        t = create_tiered_tariff(
            currency="USD",
            timezone="America/New_York",
            tier_thresholds=[Decimal("1000")],
            tier_rates=[Decimal("0.10"), Decimal("0.08")],
        )
        self.assertIsInstance(t, TariffSpec)


class TestCreateFlatRateTariff(unittest.TestCase):
    def test_create(self):
        t = create_flat_rate_tariff(
            currency="USD",
            timezone="America/New_York",
            rate=Decimal("0.10"),
        )
        self.assertIsInstance(t, TariffSpec)


if __name__ == "__main__":
    unittest.main()
