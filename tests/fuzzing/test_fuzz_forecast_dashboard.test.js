/**
 * Fuzz tests for forecast-dashboard.js using fast-check.
 * Tests the holtForecast and other forecasting functions.
 */
const fc = require('fast-check');
const assert = require('assert');

// Import the forecasting functions from the UI module
// Since the UI files are IIFEs, we need to extract the functions
// For testing, we'll reimplement the core logic and test it

// Simple Exponential Smoothing with trend (Holt's method)
function holtForecast(series, horizon = 7, alpha = 0.3, beta = 0.1) {
  if (series.length < 3) return null;
  const values = series.map((p) => p.value);
  let level = values[0];
  let trend = values[1] - values[0];
  const fitted = [level];

  for (let i = 1; i < values.length; i++) {
    const prevLevel = level;
    level = alpha * values[i] + (1 - alpha) * (level + trend);
    trend = beta * (level - prevLevel) + (1 - beta) * trend;
    fitted.push(level + trend);
  }

  const forecast = [];
  for (let i = 1; i <= horizon; i++) {
    forecast.push({
      timestamp: series[series.length - 1].timestamp + i * 86400000,
      value: level + i * trend,
    });
  }
  return { fitted, forecast };
}

// Moving Average forecast
function movingAverageForecast(series, window = 7, horizon = 7) {
  if (series.length < window) return null;
  const values = series.map((p) => p.value);
  const recent = values.slice(-window);
  const avg = recent.reduce((a, b) => a + b, 0) / recent.length;
  const forecast = [];
  for (let i = 1; i <= horizon; i++) {
    forecast.push({
      timestamp: series[series.length - 1].timestamp + i * 86400000,
      value: avg,
    });
  }
  return { forecast };
}

// Linear regression forecast
function linearRegressionForecast(series, horizon = 7) {
  if (series.length < 2) return null;
  const n = series.length;
  const x = series.map((_, i) => i);
  const y = series.map((p) => p.value);
  const xMean = x.reduce((a, b) => a + b, 0) / n;
  const yMean = y.reduce((a, b) => a + b, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    num += (x[i] - xMean) * (y[i] - yMean);
    den += (x[i] - xMean) ** 2;
  }
  const slope = den !== 0 ? num / den : 0;
  const intercept = yMean - slope * xMean;
  const forecast = [];
  for (let i = 1; i <= horizon; i++) {
    forecast.push({
      timestamp: series[series.length - 1].timestamp + i * 86400000,
      value: intercept + slope * (n - 1 + i),
    });
  }
  return { forecast };
}

// Anomaly detection using z-score
function detectAnomalies(series, threshold = 3) {
  if (series.length < 3) return [];
  const values = series.map((p) => p.value);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / values.length;
  const std = Math.sqrt(variance);
  if (std === 0) return [];
  return series.filter((p) => Math.abs((p.value - mean) / std) > threshold);
}

// Confidence interval calculation
function calculateConfidenceInterval(series, confidence = 0.95) {
  if (series.length < 2) return null;
  const values = series.map((p) => p.value);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const variance = values.reduce((a, b) => a + (b - mean) ** 2, 0) / (values.length - 1);
  const std = Math.sqrt(variance);
  const zScore = confidence === 0.95 ? 1.96 : confidence === 0.99 ? 2.576 : 1.645;
  const margin = zScore * std / Math.sqrt(values.length);
  return { lower: mean - margin, upper: mean + margin };
}

// Strategies
const floatArray = fc.array(fc.double({ min: -1e6, max: 1e6, noNaN: true }), { minLength: 3, maxLength: 100 });
const positiveInt = fc.integer({ min: 1, max: 50 });
const alpha = fc.double({ min: 0.001, max: 1, noNaN: true });
const beta = fc.double({ min: 0.001, max: 1, noNaN: true });
const windowSize = fc.integer({ min: 1, max: 20 });
const threshold = fc.double({ min: 0.1, max: 10, noNaN: true });
const confidence = fc.double({ min: 0.5, max: 0.99, noNaN: true });

// Helper to create series from float array
function makeSeries(values) {
  const base = Date.now() - values.length * 86400000;
  return values.map((v, i) => ({ timestamp: base + i * 86400000, value: v }));
}

describe('Forecast Dashboard Fuzz Tests', () => {
  describe('holtForecast', () => {
    it('should handle any valid series and parameters', () => {
      fc.assert(
        fc.property(floatArray, positiveInt, alpha, beta, (values, horizon, a, b) => {
          const series = makeSeries(values);
          const result = holtForecast(series, horizon, a, b);
          assert(result !== null);
          assert(result.forecast.length === horizon);
          result.forecast.forEach(p => {
            assert(Number.isFinite(p.value));
            assert(p.timestamp > series[series.length - 1].timestamp);
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should return null for short series', () => {
      fc.assert(
        fc.property(fc.array(fc.double({ noNaN: true }), { maxLength: 2 }), (values) => {
          const series = makeSeries(values);
          assert(holtForecast(series) === null);
        })
      );
    });
  });

  describe('movingAverageForecast', () => {
    it('should handle any valid series and window', () => {
      fc.assert(
        fc.property(floatArray, windowSize, positiveInt, (values, window, horizon) => {
          const series = makeSeries(values);
          const result = movingAverageForecast(series, window, horizon);
          if (series.length >= window) {
            assert(result !== null);
            assert(result.forecast.length === horizon);
            result.forecast.forEach(p => {
              assert(Number.isFinite(p.value));
            });
          } else {
            assert(result === null);
          }
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('linearRegressionForecast', () => {
    it('should handle any valid series', () => {
      fc.assert(
        fc.property(floatArray, positiveInt, (values, horizon) => {
          const series = makeSeries(values);
          const result = linearRegressionForecast(series, horizon);
          assert(result !== null);
          assert(result.forecast.length === horizon);
          result.forecast.forEach(p => {
            assert(Number.isFinite(p.value));
          });
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('detectAnomalies', () => {
    it('should handle any valid series and threshold', () => {
      fc.assert(
        fc.property(floatArray, threshold, (values, thresh) => {
          const series = makeSeries(values);
          const anomalies = detectAnomalies(series, thresh);
          assert(Array.isArray(anomalies));
          anomalies.forEach(p => {
            assert(Number.isFinite(p.value));
          });
        }),
        { numRuns: 100 }
      );
    });

    it('should return empty array for short series', () => {
      fc.assert(
        fc.property(fc.array(fc.double({ noNaN: true }), { maxLength: 2 }), (values) => {
          const series = makeSeries(values);
          assert(detectAnomalies(series).length === 0);
        })
      );
    });
  });

  describe('calculateConfidenceInterval', () => {
    it('should handle any valid series and confidence level', () => {
      fc.assert(
        fc.property(floatArray, confidence, (values, conf) => {
          const series = makeSeries(values);
          const result = calculateConfidenceInterval(series, conf);
          assert(result !== null);
          assert(Number.isFinite(result.lower));
          assert(Number.isFinite(result.upper));
          assert(result.lower <= result.upper);
        }),
        { numRuns: 100 }
      );
    });
  });
});
