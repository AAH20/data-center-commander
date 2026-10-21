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
            monthly_fixed_cost=ZERO,
            annual_projected_cost=ZERO,
            currency="USD",
            generated_at=dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc),
            method="flat",
        )
        d = r.to_dict()
        self.assertIsInstance(d, dict)


class TestValidateTariffSpec(unittest.TestCase):
    def test_valid(self):
        # validate_tariff_spec parses a raw dict into a TariffSpec (it does not
        # type-check an existing TariffSpec and return a bool).
        result = validate_tariff_spec({
            "currency": "USD",
            "timezone": "America/New_York",
            "energy_rates": {"flat": "0.12"},
        })
        self.assertIsInstance(result, TariffSpec)
        self.assertEqual(result.currency, "USD")
        self.assertEqual(result.energy_rates["flat"], Decimal("0.12"))

    def test_rejects_non_dict(self):
        with self.assertRaises(ValueError):
            validate_tariff_spec(TariffSpec(currency="USD", timezone="America/New_York"))  # type: ignore[arg-type]


class TestForecastPrices(unittest.TestCase):
    def test_flat(self):
        t = build_flat_tariff(
            currency="USD",
            timezone="America/New_York",
            rate=Decimal("0.12"),
        )
        result = forecast_prices(t, daily_kwh=Decimal("1000"), days=30)
        self.assertIsInstance(result, ForecastResult)
        self.assertEqual(result.method, "flat")
        self.assertEqual(len(result.points), 30 * HOURS_PER_DAY)


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
            rates={"on_peak": Decimal("0.25"), "off_peak": Decimal("0.10")},
        )
        self.assertIsInstance(t, TariffSpec)
        self.assertEqual(t.energy_rates["on_peak"], Decimal("0.25"))
        self.assertEqual(t.energy_rates["off_peak"], Decimal("0.10"))


class TestBuildTieredTariff(unittest.TestCase):
    def test_build(self):
        # Tiers are expressed as N thresholds + N+1 rates (no (threshold, rate)
        # pairs, and no open-ended None threshold -- the final rate is implicit).
        t = build_tiered_tariff(
            currency="USD",
            timezone="America/New_York",
            tier_thresholds=[Decimal("1000")],
            tier_rates=[Decimal("0.10"), Decimal("0.08")],
        )
        self.assertIsInstance(t, TariffSpec)
        self.assertEqual(t.tier_thresholds, [Decimal("1000")])
        self.assertEqual(t.tier_rates, [Decimal("0.10"), Decimal("0.08")])


if __name__ == "__main__":
    unittest.main()
