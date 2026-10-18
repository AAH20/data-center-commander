"""Unit tests for dcc.forecasting.calibration module."""
import unittest

from dcc.forecasting.calibration import (
    CalibrationMethod,
    ForecastPoint,
    ActualPoint,
    MatchedPair,
    CalibrationResult,
    match_forecast_actual_pairs,
    compute_calibration_metrics,
    apply_bias_correction,
    apply_multiplicative_correction,
    calibrate_forecasts,
)


class TestCalibrationMethod(unittest.TestCase):
    def test_method_values(self):
        self.assertEqual(CalibrationMethod.NONE.value, "none")
        self.assertEqual(CalibrationMethod.BIAS.value, "bias")
        self.assertEqual(CalibrationMethod.MULTIPLICATIVE.value, "multiplicative")


class TestForecastPoint(unittest.TestCase):
    def test_creation(self):
        fp = ForecastPoint(timestamp=100.0, value=50.0)
        self.assertEqual(fp.timestamp, 100.0)
        self.assertEqual(fp.value, 50.0)


class TestActualPoint(unittest.TestCase):
    def test_creation(self):
        ap = ActualPoint(timestamp=100.0, value=48.0)
        self.assertEqual(ap.timestamp, 100.0)
        self.assertEqual(ap.value, 48.0)


class TestMatchedPair(unittest.TestCase):
    def test_creation(self):
        mp = MatchedPair(timestamp=100.0, forecast=50.0, actual=48.0, error=2.0)
        self.assertEqual(mp.timestamp, 100.0)
        self.assertEqual(mp.forecast, 50.0)
        self.assertEqual(mp.actual, 48.0)
        self.assertEqual(mp.error, 2.0)


class TestCalibrationResult(unittest.TestCase):
    def test_creation(self):
        cr = CalibrationResult(
            method=CalibrationMethod.BIAS,
            pairs=[],
            bias=0.0,
            scale_factor=1.0,
        )
        self.assertEqual(cr.method, CalibrationMethod.BIAS)
        self.assertEqual(cr.pairs, [])


class TestMatchForecastActualPairs(unittest.TestCase):
    def test_exact_match(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=9.0)]
        pairs = match_forecast_actual_pairs(forecasts, actuals)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].forecast, 10.0)
        self.assertEqual(pairs[0].actual, 9.0)

    def test_no_match(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=2.0, value=9.0)]
        pairs = match_forecast_actual_pairs(forecasts, actuals)
        self.assertEqual(len(pairs), 0)

    def test_with_tolerance(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.5, value=9.0)]
        pairs = match_forecast_actual_pairs(forecasts, actuals, tolerance=1.0)
        self.assertEqual(len(pairs), 1)

    def test_negative_tolerance(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=9.0)]
        with self.assertRaises(ValueError):
            match_forecast_actual_pairs(forecasts, actuals, tolerance=-1.0)


class TestComputeCalibrationMetrics(unittest.TestCase):
    def test_empty(self):
        metrics = compute_calibration_metrics([])
        self.assertEqual(metrics["bias"], 0.0)
        self.assertEqual(metrics["mae"], 0.0)

    def test_with_pairs(self):
        pairs = [MatchedPair(timestamp=1.0, forecast=10.0, actual=9.0, error=1.0)]
        metrics = compute_calibration_metrics(pairs)
        self.assertAlmostEqual(metrics["bias"], 1.0)
        self.assertAlmostEqual(metrics["mae"], 1.0)


class TestApplyBiasCorrection(unittest.TestCase):
    def test_correction(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        result = apply_bias_correction(forecasts, bias=2.0)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].value, 8.0)


class TestApplyMultiplicativeCorrection(unittest.TestCase):
    def test_correction(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        result = apply_multiplicative_correction(forecasts, scale_factor=0.9)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0].value, 9.0)


class TestCalibrateForecasts(unittest.TestCase):
    def test_calibrate(self):
        forecasts = [ForecastPoint(timestamp=1.0, value=10.0)]
        actuals = [ActualPoint(timestamp=1.0, value=9.0)]
        result = calibrate_forecasts(forecasts, actuals, method=CalibrationMethod.BIAS)
        self.assertIsInstance(result, CalibrationResult)


if __name__ == "__main__":
    unittest.main()
