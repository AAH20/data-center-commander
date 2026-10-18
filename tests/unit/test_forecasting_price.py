"""Unit tests for dcc.forecasting.price module."""
import unittest
import datetime as dt
from decimal import Decimal

from dcc.forecasting.price import (
    ZERO,
    ONE,
    HOURS_PER_DAY,
    DAYS_PER_MONTH,
    MONTHS_PER_YEAR,
    TOU_PERIODS,
    TariffSpec,
    PricePoint,
    ForecastResult,
    validate_tariff_spec,
    forecast_prices,
    build_flat_tariff,
    build_tou_tariff,
    build_tiered_tariff,
)


class TestConstants(unittest.TestCase):
    def test_zero(self):
        self.assertEqual(ZERO, Decimal("0"))

    def test_one(self):
        self.assertEqual(ONE, Decimal("1"))

    def test_hours_per_day(self):
        self.assertEqual(HOURS_PER_DAY, 24)

    def test_days_per_month(self):
        self.assertEqual(DAYS_PER_MONTH, 30)

    def test_months_per_year(self):
        self.assertEqual(MONTHS_PER_YEAR, 12)


class TestTouPeriods(unittest.TestCase):
    def test_periods(self):
        self.assertGreater(len(TOU_PERIODS), 0)
        names = [p[0] for p in TOU_PERIODS]
        self.assertIn("on_peak", names)


class TestTariffSpec(unittest.TestCase):
    def test_creation(self):
        t = TariffSpec(
            currency="USD",
            timezone="America/New_York",
        )
        self.assertEqual(t.currency, "USD")
        self.assertEqual(t.timezone, "America/New_York")

    def test_with_rates(self):
        t = TariffSpec(
            currency="USD",
            timezone="America/New_York",
            energy_rates={"peak": Decimal("0.25")},
        )
        self.assertEqual(t.energy_rates["peak"], Decimal("0.25"))

    def test_to_dict(self):
        t = TariffSpec(
            currency="USD",
            timezone="America/New_York",
        )
        d = t.to_dict()
        self.assertEqual(d["currency"], "USD")


class TestPricePoint(unittest.TestCase):
    def test_creation(self):
        pp = PricePoint(
            timestamp=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
            period="peak",
            energy_rate=Decimal("0.25"),
            demand_rate=None,
            estimated_cost=Decimal("10.00"),
            currency="USD",
        )
        self.assertEqual(pp.period, "peak")
        self.assertEqual(pp.energy_rate, Decimal("0.25"))

    def test_to_dict(self):
        pp = PricePoint(
            timestamp=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
            period="peak",
            energy_rate=Decimal("0.25"),
            demand_rate=None,
            estimated_cost=Decimal("10.00"),
            currency="USD",
        )
        d = pp.to_dict()
        self.assertEqual(d["period"], "peak")


class TestForecastResult(unittest.TestCase):
    def test_creation(self):
        t = TariffSpec(currency="USD", timezone="America/New_York")
        r = ForecastResult(
            tariff=t,
            points=[],
            total_energy_kwh=ZERO,
            total_cost=ZERO,
            average_rate=ZERO,
            peak_rate=ZERO,
            off_peak_rate=ZERO,
            monthly_fixed_cost=ZERO,
            annual_projected_cost=ZERO,
            currency="USD",
            generated_at=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
            method="flat",
        )
        self.assertEqual(r.currency, "USD")

    def test_to_dict(self):
        t = TariffSpec(currency="USD", timezone="America/New_York")
        r = ForecastResult(
            tariff=t,
            points=[],
            total_energy_kwh=ZERO,
            total_cost=ZERO,
            average_rate=ZERO,
            peak_rate=ZERO,
            off_peak_rate=ZERO,
            monthly_fixed_charge=ZERO,
            annual_projected_cost=ZERO,
            currency="USD",
            generated_at=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
            method="flat",
        )
        d = r.to_dict()
        self.assertIsInstance(d, dict)


class TestValidateTariffSpec(unittest.TestCase):
    def test_valid(self):
        t = TariffSpec(currency="USD", timezone="America/New_York")
        result = validate_tariff_spec(t)
        self.assertIsInstance(result, bool)


class TestForecastPrices(unittest.TestCase):
    def test_flat(self):
        t = TariffSpec(currency="USD", timezone="America/New_York")
        result = forecast_prices(t, energy_kwh=Decimal("1000"), days=30)
        self.assertIsInstance(result, ForecastResult)


class TestBuildFlatTariff(unittest.TestCase):
    def test_build(self):
        t = build_flat_tariff(
            currency="USD",
            timezone="America/New_York",
            rate=Decimal("0.10"),
        )
        self.assertIsInstance(t, TariffSpec)
        self.assertEqual(t.currency, "USD")


class TestBuildTouTariff(unittest.TestCase):
    def test_build(self):
        t = build_tou_tariff(
            currency="USD",
            timezone="America/New_York",
            peak_rate=Decimal("0.25"),
            off_peak_rate=Decimal("0.10"),
        )
        self.assertIsInstance(t, TariffSpec)


class TestBuildTieredTariff(unittest.TestCase):
    def test_build(self):
        t = build_tiered_tariff(
            currency="USD",
            timezone="America/New_York",
            tiers=[(Decimal("1000"), Decimal("0.10")), (None, Decimal("0.08"))],
        )
        self.assertIsInstance(t, TariffSpec)


if __name__ == "__main__":
    unittest.main()
