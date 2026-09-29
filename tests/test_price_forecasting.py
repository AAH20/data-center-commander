"""Tests for energy price forecasting from tariff structures."""
import datetime as dt
import unittest
from decimal import Decimal

from dcc.forecasting.price import (
    TariffSpec,
    build_flat_tariff,
    build_tiered_tariff,
    build_tou_tariff,
    forecast_prices,
    validate_tariff_spec,
)


class ValidateTariffSpecTests(unittest.TestCase):
    def test_valid_flat_spec(self):
        spec = {
            "currency": "USD",
            "timezone": "America/New_York",
            "energy_rates": {"flat": "0.12"},
            "demand_rate": "15.00",
            "fixed_monthly_charge": "50.00",
            "source_ref": "utility-tariff-2026",
            "version": "1",
        }
        result = validate_tariff_spec(spec)
        self.assertEqual(result.currency, "USD")
        self.assertEqual(result.timezone, "America/New_York")
        self.assertEqual(result.energy_rates["flat"], Decimal("0.12"))
        self.assertEqual(result.demand_rate, Decimal("15.00"))
        self.assertEqual(result.fixed_monthly_charge, Decimal("50.00"))
        self.assertEqual(result.source_ref, "utility-tariff-2026")

    def test_valid_tou_spec(self):
        spec = {
            "currency": "EUR",
            "timezone": "Europe/Berlin",
            "energy_rates": {"on_peak": "0.25", "off_peak": "0.08", "shoulder": "0.15"},
            "tou_schedule": {"0": "off_peak", "6": "shoulder", "12": "on_peak", "18": "shoulder", "22": "off_peak"},
        }
        result = validate_tariff_spec(spec)
        self.assertEqual(result.currency, "EUR")
        self.assertEqual(result.tou_schedule[0], "off_peak")
        self.assertEqual(result.tou_schedule[12], "on_peak")

    def test_valid_tiered_spec(self):
        spec = {
            "currency": "GBP",
            "timezone": "Europe/London",
            "energy_rates": {"tiered": "0.10"},
            "tier_thresholds": ["500", "1000"],
            "tier_rates": ["0.10", "0.12", "0.15"],
        }
        result = validate_tariff_spec(spec)
        self.assertEqual(len(result.tier_thresholds), 2)
        self.assertEqual(len(result.tier_rates), 3)
        self.assertEqual(result.tier_thresholds[0], Decimal("500"))
        self.assertEqual(result.tier_rates[2], Decimal("0.15"))

    def test_rejects_invalid_currency(self):
        with self.assertRaises(ValueError):
            validate_tariff_spec({"currency": "US", "timezone": "UTC", "energy_rates": {"flat": "0.1"}})

    def test_rejects_empty_energy_rates(self):
        with self.assertRaises(ValueError):
            validate_tariff_spec({"currency": "USD", "timezone": "UTC", "energy_rates": {}})

    def test_rejects_negative_rate(self):
        with self.assertRaises(ValueError):
            validate_tariff_spec({"currency": "USD", "timezone": "UTC", "energy_rates": {"flat": "-0.1"}})

    def test_rejects_mismatched_tiers(self):
        spec = {
            "currency": "USD",
            "timezone": "UTC",
            "energy_rates": {"tiered": "0.10"},
            "tier_thresholds": ["500"],
            "tier_rates": ["0.10", "0.12", "0.15"],
        }
        with self.assertRaises(ValueError):
            validate_tariff_spec(spec)

    def test_rejects_non_increasing_thresholds(self):
        spec = {
            "currency": "USD",
            "timezone": "UTC",
            "energy_rates": {"tiered": "0.10"},
            "tier_thresholds": ["1000", "500"],
            "tier_rates": ["0.10", "0.12", "0.15"],
        }
        with self.assertRaises(ValueError):
            validate_tariff_spec(spec)

    def test_rejects_invalid_tou_hour(self):
        spec = {
            "currency": "USD",
            "timezone": "UTC",
            "energy_rates": {"flat": "0.1"},
            "tou_schedule": {"25": "on_peak"},
        }
        with self.assertRaises(ValueError):
            validate_tariff_spec(spec)

    def test_rejects_valid_to_before_valid_from(self):
        spec = {
            "currency": "USD",
            "timezone": "UTC",
            "energy_rates": {"flat": "0.1"},
            "valid_from": "2026-06-01T00:00:00Z",
            "valid_to": "2026-01-01T00:00:00Z",
        }
        with self.assertRaises(ValueError):
            validate_tariff_spec(spec)

    def test_rejects_boolean_rate(self):
        with self.assertRaises(ValueError):
            validate_tariff_spec({"currency": "USD", "timezone": "UTC", "energy_rates": {"flat": True}})

    def test_rejects_non_dict_spec(self):
        with self.assertRaises(ValueError):
            validate_tariff_spec("not a dict")


class BuildTariffTests(unittest.TestCase):
    def test_build_flat_tariff(self):
        t = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        self.assertEqual(t.energy_rates["flat"], Decimal("0.12"))
        self.assertIsNone(t.demand_rate)
        self.assertEqual(t.fixed_monthly_charge, Decimal("0"))

    def test_build_tou_tariff(self):
        t = build_tou_tariff(
            currency="USD",
            timezone="UTC",
            rates={"on_peak": "0.25", "off_peak": "0.08"},
        )
        self.assertEqual(t.energy_rates["on_peak"], Decimal("0.25"))
        self.assertEqual(t.energy_rates["off_peak"], Decimal("0.08"))

    def test_build_tiered_tariff(self):
        t = build_tiered_tariff(
            currency="USD",
            timezone="UTC",
            tier_thresholds=["500", "1000"],
            tier_rates=["0.10", "0.12", "0.15"],
        )
        self.assertEqual(len(t.tier_thresholds), 2)
        self.assertEqual(len(t.tier_rates), 3)

    def test_build_flat_rejects_negative_rate(self):
        with self.assertRaises(ValueError):
            build_flat_tariff(currency="USD", timezone="UTC", rate="-0.1")


class ForecastPricesTests(unittest.TestCase):
    def test_flat_rate_forecast(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        result = forecast_prices(tariff, daily_kwh="1000", days=1)
        self.assertEqual(len(result.points), 24)
        self.assertEqual(result.currency, "USD")
        self.assertEqual(result.method, "flat")
        # All points should have the same rate
        rates = {p.energy_rate for p in result.points}
        self.assertEqual(len(rates), 1)
        self.assertEqual(result.peak_rate, Decimal("0.12"))
        self.assertEqual(result.off_peak_rate, Decimal("0.12"))

    def test_tou_forecast_has_different_rates(self):
        tariff = build_tou_tariff(
            currency="USD",
            timezone="UTC",
            rates={"on_peak": "0.25", "off_peak": "0.08", "shoulder": "0.15"},
        )
        result = forecast_prices(tariff, daily_kwh="1000", days=1)
        self.assertEqual(result.method, "tou")
        rates = {p.energy_rate for p in result.points}
        self.assertGreater(len(rates), 1)
        self.assertEqual(result.peak_rate, Decimal("0.25"))
        self.assertEqual(result.off_peak_rate, Decimal("0.08"))

    def test_tiered_forecast(self):
        tariff = build_tiered_tariff(
            currency="USD",
            timezone="UTC",
            tier_thresholds=["100"],
            tier_rates=["0.10", "0.15"],
        )
        result = forecast_prices(tariff, daily_kwh="1000", days=1)
        self.assertEqual(result.method, "tiered")
        # With 1000 kWh/day and threshold at 100, most hours should be in tier 2
        tier2_points = [p for p in result.points if p.energy_rate == Decimal("0.15")]
        self.assertGreater(len(tier2_points), 0)

    def test_forecast_with_demand_charges(self):
        tariff = build_flat_tariff(
            currency="USD",
            timezone="UTC",
            rate="0.12",
            demand_rate="15.00",
        )
        result = forecast_prices(
            tariff, daily_kwh="1000", days=30, include_demand=True, peak_demand_kw="500"
        )
        # Demand cost = 15 * 500 = 7500/month
        # For 30 days = 1 month, so demand cost should be 7500
        self.assertIn("Demand charges included", " ".join(result.notes))

    def test_forecast_rejects_demand_without_rate(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        with self.assertRaises(ValueError):
            forecast_prices(tariff, daily_kwh="1000", days=1, include_demand=True)

    def test_forecast_rejects_demand_without_peak_kw(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12", demand_rate="15")
        with self.assertRaises(ValueError):
            forecast_prices(tariff, daily_kwh="1000", days=1, include_demand=True)

    def test_forecast_rejects_zero_daily_kwh(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        with self.assertRaises(ValueError):
            forecast_prices(tariff, daily_kwh="0", days=1)

    def test_forecast_rejects_invalid_days(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        with self.assertRaises(ValueError):
            forecast_prices(tariff, daily_kwh="1000", days=0)
        with self.assertRaises(ValueError):
            forecast_prices(tariff, daily_kwh="1000", days=366)

    def test_forecast_with_fixed_monthly_charge(self):
        tariff = build_flat_tariff(
            currency="USD", timezone="UTC", rate="0.12", fixed_monthly_charge="50"
        )
        result = forecast_prices(tariff, daily_kwh="1000", days=30)
        self.assertEqual(result.monthly_fixed_cost, Decimal("50"))
        self.assertIn("Fixed monthly charge", " ".join(result.notes))

    def test_forecast_annual_projection(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        result = forecast_prices(tariff, daily_kwh="1000", days=30)
        # 1000 kWh/day * 0.12 = 120/day * 30 = 3600 for 30 days
        # Annual = 3600 * (365/30) = 43800
        self.assertGreater(result.annual_projected_cost, Decimal("40000"))

    def test_forecast_point_structure(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        result = forecast_prices(tariff, daily_kwh="1000", days=1)
        point = result.points[0]
        self.assertIsInstance(point.timestamp, dt.datetime)
        self.assertIsInstance(point.energy_rate, Decimal)
        self.assertIsInstance(point.estimated_cost, Decimal)
        self.assertEqual(point.currency, "USD")

    def test_forecast_to_dict(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        result = forecast_prices(tariff, daily_kwh="1000", days=1)
        d = result.to_dict()
        self.assertIn("tariff", d)
        self.assertIn("points", d)
        self.assertIn("total_cost", d)
        self.assertIn("currency", d)
        self.assertEqual(d["currency"], "USD")

    def test_forecast_with_custom_start(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        start = dt.datetime(2026, 6, 15, 0, 0, 0, tzinfo=dt.timezone.utc)
        result = forecast_prices(tariff, daily_kwh="1000", days=1, start=start)
        self.assertEqual(result.points[0].timestamp, start)

    def test_forecast_with_tou_schedule(self):
        spec = {
            "currency": "USD",
            "timezone": "America/New_York",
            "energy_rates": {"on_peak": "0.30", "off_peak": "0.05", "shoulder": "0.15"},
            "tou_schedule": {
                "0": "off_peak", "1": "off_peak", "2": "off_peak", "3": "off_peak",
                "4": "off_peak", "5": "off_peak", "6": "shoulder", "7": "shoulder",
                "8": "shoulder", "9": "shoulder", "10": "shoulder", "11": "shoulder",
                "12": "on_peak", "13": "on_peak", "14": "on_peak", "15": "on_peak",
                "16": "on_peak", "17": "on_peak", "18": "shoulder", "19": "shoulder",
                "20": "shoulder", "21": "shoulder", "22": "off_peak", "23": "off_peak",
            },
        }
        tariff = validate_tariff_spec(spec)
        result = forecast_prices(tariff, daily_kwh="1000", days=1)
        # Check that hour 0 is off_peak and hour 12 is on_peak
        self.assertEqual(result.points[0].period, "off_peak")
        self.assertEqual(result.points[12].period, "on_peak")
        self.assertEqual(result.points[0].energy_rate, Decimal("0.05"))
        self.assertEqual(result.points[12].energy_rate, Decimal("0.30"))

    def test_forecast_total_energy_conservation(self):
        """Total energy should approximately equal daily_kwh * days."""
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        result = forecast_prices(tariff, daily_kwh="1000", days=1)
        # The load curve multipliers should average to 1.0
        self.assertAlmostEqual(float(result.total_energy_kwh), 1000.0, delta=50.0)

    def test_forecast_with_validity_window(self):
        spec = {
            "currency": "USD",
            "timezone": "UTC",
            "energy_rates": {"flat": "0.12"},
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": "2026-12-31T23:59:59Z",
        }
        tariff = validate_tariff_spec(spec)
        self.assertIsNotNone(tariff.valid_from)
        self.assertIsNotNone(tariff.valid_to)

    def test_tariff_to_dict(self):
        tariff = build_flat_tariff(currency="USD", timezone="UTC", rate="0.12")
        d = tariff.to_dict()
        self.assertEqual(d["currency"], "USD")
        self.assertEqual(d["energy_rates"]["flat"], "0.12")
        self.assertIn("version", d)


if __name__ == "__main__":
    unittest.main()
