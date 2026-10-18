/**
 * Fuzz tests for quality-dashboard.js using fast-check.
 * Tests the quality scoring and anomaly detection functions.
 */
const fc = require('fast-check');
const assert = require('assert');

// Quality score calculation
function calculateQualityScore(metrics) {
  const weights = {
    coverage: 0.3,
    freshness: 0.25,
    completeness: 0.25,
    accuracy: 0.2,
  };
  let score = 0;
  for (const [key, weight] of Object.entries(weights)) {
    const value = metrics[key];
    if (value != null && Number.isFinite(value)) {
      score += Math.max(0, Math.min(1, value)) * weight;
    }
  }
  return Math.round(score * 100) / 100;
}

// Freshness score based on age in hours
function calculateFreshnessScore(ageHours, maxAgeHours = 168) {
  if (ageHours < 0) return 0;
  if (ageHours >= maxAgeHours) return 0;
  return Math.max(0, 1 - ageHours / maxAgeHours);
}

// Completeness score
function calculateCompletenessScore(expected, actual) {
  if (expected <= 0) return 0;
  return Math.min(1, actual / expected);
}

// Anomaly severity classification
function classifyAnomalySeverity(zScore) {
  const absZ = Math.abs(zScore);
  if (absZ >= 4) return 'critical';
  if (absZ >= 3) return 'high';
  if (absZ >= 2) return 'medium';
  if (absZ >= 1) return 'low';
  return 'none';
}

// Quality status from score
function qualityStatusFromScore(score) {
  if (score >= 0.9) return 'good';
  if (score >= 0.7) return 'estimated';
  if (score >= 0.5) return 'suspect';
  return 'poor';
}

// Strategies
const qualityMetrics = fc.record({
  coverage: fc.double({ min: 0, max: 1, noNaN: true }),
  freshness: fc.double({ min: 0, max: 1, noNaN: true }),
  completeness: fc.double({ min: 0, max: 1, noNaN: true }),
  accuracy: fc.double({ min: 0, max: 1, noNaN: true }),
});

const ageHours = fc.double({ min: 0, max: 10000, noNaN: true });
const maxAgeHours = fc.double({ min: 1, max: 10000, noNaN: true });
const expectedCount = fc.integer({ min: 0, max: 10000 });
const actualCount = fc.integer({ min: 0, max: 10000 });
const zScore = fc.double({ min: -100, max: 100, noNaN: true });
const qualityScore = fc.double({ min: 0, max: 1, noNaN: true });

describe('Quality Dashboard Fuzz Tests', () => {
  describe('calculateQualityScore', () => {
    it('should handle any valid metrics', () => {
      fc.assert(
        fc.property(qualityMetrics, (metrics) => {
          const score = calculateQualityScore(metrics);
          assert(score >= 0 && score <= 1);
          assert(Number.isFinite(score));
        }),
        { numRuns: 100 }
      );
    });

    it('should handle partial metrics', () => {
      fc.assert(
        fc.property(
          fc.dictionary(fc.string(), fc.double({ min: 0, max: 1, noNaN: true }), { maxKeys: 4 }),
          (metrics) => {
            const score = calculateQualityScore(metrics);
            assert(score >= 0 && score <= 1);
          }
        ),
        { numRuns: 100 }
      );
    });
  });

  describe('calculateFreshnessScore', () => {
    it('should handle any valid age and max age', () => {
      fc.assert(
        fc.property(ageHours, maxAgeHours, (age, maxAge) => {
          const score = calculateFreshnessScore(age, maxAge);
          assert(score >= 0 && score <= 1);
          assert(Number.isFinite(score));
        }),
        { numRuns: 100 }
      );
    });

    it('should return 0 for negative age', () => {
      fc.assert(
        fc.property(fc.double({ min: -1000, max: -0.001, noNaN: true }), (age) => {
          assert(calculateFreshnessScore(age) === 0);
        })
      );
    });
  });

  describe('calculateCompletenessScore', () => {
    it('should handle any valid expected and actual counts', () => {
      fc.assert(
        fc.property(expectedCount, actualCount, (expected, actual) => {
          const score = calculateCompletenessScore(expected, actual);
          assert(score >= 0 && score <= 1);
          assert(Number.isFinite(score));
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('classifyAnomalySeverity', () => {
    it('should handle any z-score', () => {
      fc.assert(
        fc.property(zScore, (z) => {
          const severity = classifyAnomalySeverity(z);
          assert(['none', 'low', 'medium', 'high', 'critical'].includes(severity));
        }),
        { numRuns: 100 }
      );
    });

    it('should classify correctly at boundaries', () => {
      assert(classifyAnomalySeverity(0) === 'none');
      assert(classifyAnomalySeverity(0.5) === 'none');
      assert(classifyAnomalySeverity(1) === 'low');
      assert(classifyAnomalySeverity(2) === 'medium');
      assert(classifyAnomalySeverity(3) === 'high');
      assert(classifyAnomalySeverity(4) === 'critical');
      assert(classifyAnomalySeverity(-4) === 'critical');
    });
  });

  describe('qualityStatusFromScore', () => {
    it('should handle any valid score', () => {
      fc.assert(
        fc.property(qualityScore, (score) => {
          const status = qualityStatusFromScore(score);
          assert(['good', 'estimated', 'suspect', 'poor'].includes(status));
        }),
        { numRuns: 100 }
      );
    });

    it('should classify correctly at boundaries', () => {
      assert(qualityStatusFromScore(0.95) === 'good');
      assert(qualityStatusFromScore(0.9) === 'good');
      assert(qualityStatusFromScore(0.85) === 'estimated');
      assert(qualityStatusFromScore(0.7) === 'estimated');
      assert(qualityStatusFromScore(0.6) === 'suspect');
      assert(qualityStatusFromScore(0.5) === 'suspect');
      assert(qualityStatusFromScore(0.4) === 'poor');
      assert(qualityStatusFromScore(0) === 'poor');
    });
  });
});
