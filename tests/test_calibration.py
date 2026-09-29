"""Tests for forecast calibration engine."""
import math
import unittest

from dcc.forecasting.calibration import (
    ActualPoint,
    CalibrationMethod,
    CalibrationResult,
    ForecastPoint,
    MatchedPair,
    apply_bias_correction,
    apply_multiplicative_correction,
    calibrate_forecasts,
    compute_calibration_metrics,
    match_forecast_actual_pairs,
)


class MatchForecastActualPairsTests(unittest.TestCase):
    def test_exact_match(self):
        forecasts = [
            ForecastPoint(timestamp=1.0, value=10.0),
            ForecastPoint(timestamp=2.0, value=20.0),
            ForecastPoint(timestamp=3.0, value=30.0),
        ]
        actuals = [
            ActualPoint(timestamp=1.0, value=11.0),
            ActualPoint(timestamp=2.0, value=19.0),
            ActualPoint(timestamp=3.0, value=31.0),
        ]
        pairs = match_forecast_actual_pairs(forecasts, actuals)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs[0].forecast, 10.0)
        self.assertEqual(pairs[0].actual, 11.0)
        self.assertEqual(pairs[0].error, -1.0)
        self.assertEqual(pairs[1].error, 1.0)
        self.assertEqual(pairs[2].error, -1.0)

    def test_partial_match(self):
        forecasts = [
            ForecastPoint(timestamp=1.0, value=10.0),
            ForecastPoint(timestamp=2.0, value=20.0),
        ]
        actuals = [ActualPoint(timestamp=1.0, value=11.0)]
        pairs = match_forecast_actual_pairs(forecasts, actuals)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].timestamp, 1.0)

    def test_tolerance_match(self):
        forecasts = [ForecastPoint(timestamp=1.05, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=11.0)]
        pairs = match_forecast_actual_pairs(forecasts, actuals, tolerance=0.1)
        self.assertEqual(len(pairs), 1)
        pairs_strict = match_forecast_actual_pairs(forecasts, actuals, tolerance=0.01)
        self.assertEqual(len(pairs_strict), 0)

    def test_negative_tolerance_raises(self):
        with self.assertRaises(ValueError):
            match_forecast_actual_pairs([], [], tolerance=-1.0)

    def test_empty_inputs(self):
        pairs = match_forecast_actual_pairs([], [])
        self.assertEqual(pairs, [])

    def test_sorted_by_timestamp(self):
        forecasts = [
            ForecastPoint(timestamp=3.0, value=30.0),
            ForecastPoint(timestamp=1.0, value=10.0),
            ForecastPoint(timestamp=2.0, value=20.0),
        ]
        actuals = [
            ActualPoint(timestamp=1.0, value=11.0),
            ActualPoint(timestamp=2.0, value=19.0),
            ActualPoint(timestamp=3.0, value=31.0),
        ]
        pairs = match_forecast_actual_pairs(forecasts, actuals)
        self.assertEqual([p.timestamp for p in pairs], [1.0, 2.0, 3.0])


class ComputeCalibrationMetricsTests(unittest.TestCase):
    def test_empty_pairs(self):
        metrics = compute_calibration_metrics([])
        self.assertEqual(metrics["bias"], 0.0)
        self.assertEqual(metrics["mae"], 0.0)
        self.assertEqual(metrics["rmse"], 0.0)

    def test_known_values(self):
        pairs = [
            MatchedPair(timestamp=1.0, forecast=10.0, actual=12.0, error=-2.0),
            MatchedPair(timestamp=2.0, forecast=20.0, actual=18.0, error=2.0),
            MatchedPair(timestamp=3.0, forecast=30.0, actual=30.0, error=0.0),
        ]
        metrics = compute_calibration_metrics(pairs)
        self.assertAlmostEqual(metrics["bias"], 0.0)
        self.assertAlmostEqual(metrics["mae"], 4.0 / 3.0)
        self.assertAlmostEqual(metrics["rmse"], math.sqrt(8.0 / 3.0))

    def test_bias_positive_over_forecast(self):
        pairs = [
            MatchedPair(timestamp=1.0, forecast=15.0, actual=10.0, error=5.0),
            MatchedPair(timestamp=2.0, forecast=25.0, actual=20.0, error=5.0),
        ]
        metrics = compute_calibration_metrics(pairs)
        self.assertAlmostEqual(metrics["bias"], 5.0)

    def test_mape_skips_zero_actuals(self):
        pairs = [
            MatchedPair(timestamp=1.0, forecast=10.0, actual=0.0, error=10.0),
            MatchedPair(timestamp=2.0, forecast=20.0, actual=25.0, error=-5.0),
        ]
        metrics = compute_calibration_metrics(pairs)
        # Only the second pair counts: |25-20|/25 * 100 = 20%
        self.assertAlmostEqual(metrics["mape"], 20.0)

    def test_variance_ratio(self):
        pairs = [
            MatchedPair(timestamp=1.0, forecast=10.0, actual=10.0, error=0.0),
            MatchedPair(timestamp=2.0, forecast=20.0, actual=20.0, error=0.0),
            MatchedPair(timestamp=3.0, forecast=30.0, actual=30.0, error=0.0),
        ]
        metrics = compute_calibration_metrics(pairs)
        self.assertAlmostEqual(metrics["variance_ratio"], 1.0)


class ApplyBiasCorrectionTests(unittest.TestCase):
    def test_subtracts_bias(self):
        forecasts = [
            ForecastPoint(timestamp=1.0, value=10.0),
            ForecastPoint(timestamp=2.0, value=20.0),
        ]
        corrected = apply_bias_correction(forecasts, bias=2.0)
        self.assertEqual(corrected[0].value, 8.0)
        self.assertEqual(corrected[1].value, 18.0)

    def test_adjusts_intervals(self):
        forecasts = [
            ForecastPoint(timestamp=1.0, value=10.0, lower=8.0, upper=12.0),
        ]
        corrected = apply_bias_correction(forecasts, bias=1.0)
        self.assertEqual(corrected[0].lower, 7.0)
        self.assertEqual(corrected[0].upper, 11.0)

    def test_zero_bias_no_change(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        corrected = apply_bias_correction(forecasts, bias=0.0)
        self.assertEqual(corrected[0].value, 10.0)

    def test_preserves_timestamp(self):
        forecasts = [ForecastPoint(timestamp=42.0, value=10.0)]
        corrected = apply_bias_correction(forecasts, bias=1.0)
        self.assertEqual(corrected[0].timestamp, 42.0)


class ApplyMultiplicativeCorrectionTests(unittest.TestCase):
    def test_scales_values(self):
        forecasts = [
            ForecastPoint(timestamp=1.0, value=10.0),
            ForecastPoint(timestamp=2.0, value=20.0),
        ]
        corrected = apply_multiplicative_correction(forecasts, scale_factor=1.1)
        self.assertAlmostEqual(corrected[0].value, 11.0)
        self.assertAlmostEqual(corrected[1].value, 22.0)

    def test_scales_intervals(self):
        forecasts = [
            ForecastPoint(timestamp=1.0, value=10.0, lower=8.0, upper=12.0),
        ]
        corrected = apply_multiplicative_correction(forecasts, scale_factor=2.0)
        self.assertEqual(corrected[0].lower, 16.0)
        self.assertEqual(corrected[0].upper, 24.0)

    def test_zero_scale_raises(self):
        with self.assertRaises(ValueError):
            apply_multiplicative_correction([], scale_factor=0.0)

    def test_negative_scale_raises(self):
        with self.assertRaises(ValueError):
            apply_multiplicative_correction([], scale_factor=-1.0)


class CalibrateForecastsTests(unittest.TestCase):
    def _make_forecasts(self):
        return [
            ForecastPoint(timestamp=1.0, value=10.0),
            ForecastPoint(timestamp=2.0, value=20.0),
            ForecastPoint(timestamp=3.0, value=30.0),
            ForecastPoint(timestamp=4.0, value=40.0),
        ]

    def _make_actuals(self):
        return [
            ActualPoint(timestamp=1.0, value=12.0),
            ActualPoint(timestamp=2.0, value=22.0),
            ActualPoint(timestamp=3.0, value=32.0),
            ActualPoint(timestamp=4.0, value=42.0),
        ]

    def test_bias_correction(self):
        forecasts = self._make_forecasts()
        actuals = self._make_actuals()
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.BIAS)
        self.assertTrue(result.sufficient_data)
        self.assertEqual(result.sample_size, 4)
        # Bias = mean(forecast - actual) = mean(-2, -2, -2, -2) = -2
        self.assertAlmostEqual(result.bias, -2.0)
        # Corrected: subtract bias => 10-(-2)=12, 20-(-2)=22, etc.
        self.assertAlmostEqual(result.calibrated_forecasts[0].value, 12.0)
        self.assertAlmostEqual(result.calibrated_forecasts[1].value, 22.0)

    def test_multiplicative_correction(self):
        forecasts = self._make_forecasts()
        actuals = self._make_actuals()
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.MULTIPLICATIVE)
        self.assertTrue(result.sufficient_data)
        # scale = mean(actual) / mean(forecast) = 27 / 25 = 1.08
        self.assertAlmostEqual(result.scale_factor, 1.08)
        self.assertAlmostEqual(result.calibrated_forecasts[0].value, 10.0 * 1.08)

    def test_none_method_no_correction(self):
        forecasts = self._make_forecasts()
        actuals = self._make_actuals()
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.NONE)
        self.assertEqual(result.bias, 0.0)
        self.assertEqual(result.scale_factor, 1.0)
        self.assertEqual(result.calibrated_forecasts[0].value, 10.0)

    def test_insufficient_data(self):
        forecasts = self._make_forecasts()
        actuals = [ActualPoint(timestamp=1.0, value=12.0)]
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.BIAS, min_samples=3)
        self.assertFalse(result.sufficient_data)
        self.assertEqual(result.sample_size, 1)
        # No correction applied
        self.assertEqual(result.bias, 0.0)
        self.assertEqual(result.calibrated_forecasts[0].value, 10.0)

    def test_string_method(self):
        forecasts = self._make_forecasts()
        actuals = self._make_actuals()
        result = calibrate_forecasts(forecasts, actuals, method="bias")
        self.assertEqual(result.method, CalibrationMethod.BIAS)

    def test_invalid_method_raises(self):
        with self.assertRaises(ValueError):
            calibrate_forecasts([], [], method="invalid")

    def test_empty_inputs(self):
        result = calibrate_forecasts([], [])
        self.assertFalse(result.sufficient_data)
        self.assertEqual(result.sample_size, 0)
        self.assertEqual(result.calibrated_forecasts, [])

    def test_metrics_populated(self):
        forecasts = self._make_forecasts()
        actuals = self._make_actuals()
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.BIAS)
        self.assertIn("bias", result.metrics)
        self.assertIn("mae", result.metrics)
        self.assertIn("rmse", result.metrics)
        self.assertIn("mape", result.metrics)
        self.assertIn("smape", result.metrics)
        self.assertIn("variance_ratio", result.metrics)

    def test_pairs_populated(self):
        forecasts = self._make_forecasts()
        actuals = self._make_actuals()
        result = calibrate_forecasts(forecasts, actuals)
        self.assertEqual(len(result.pairs), 4)
        self.assertEqual(result.pairs[0].timestamp, 1.0)
        self.assertEqual(result.pairs[3].timestamp, 4.0)

    def test_tolerance_matching(self):
        forecasts = [ForecastPoint(timestamp=1.05, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=12.0)]
        result = calibrate_forecasts(forecasts, actuals, tolerance=0.1, min_samples=1)
        self.assertEqual(result.sample_size, 1)
        self.assertTrue(result.sufficient_data)


if __name__ == "__main__":
    unittest.main()
