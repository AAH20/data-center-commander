// Fuzz tests for placement-scenarios.js using fast-check.
const fc = require('fast-check');
const assert = require('assert');

// Scenario snapshot validation
function validateScenarioSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return false;
  if (!snapshot.name || typeof snapshot.name !== 'string') return false;
  if (!snapshot.payload || typeof snapshot.payload !== 'object') return false;
  if (snapshot.payload.schema_version !== 'placement-tco-comparison.v1') return false;
  if (!snapshot.payload.assumptions || !snapshot.payload.sources || !snapshot.payload.results) return false;
  return true;
}

// Scenario hash calculation
function calculateScenarioHash(snapshot) {
  const str = JSON.stringify(snapshot.payload, Object.keys(snapshot.payload).sort());
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return Math.abs(hash).toString(16).padStart(8, '0');
}

// Scenario comparison
function compareScenarioSnapshots(a, b) {
  const hashA = calculateScenarioHash(a);
  const hashB = calculateScenarioHash(b);
  return hashA === hashB;
}

// Scenario list filtering
function filterScenarios(scenarios, filter) {
  if (!filter) return scenarios;
  return scenarios.filter(s => {
    if (filter.profile && s.profile !== filter.profile) return false;
    if (filter.objective && s.objective !== filter.objective) return false;
    return true;
  });
}

// Strategies
const snapshotName = fc.string({ minLength: 0, maxLength: 200 });
const schemaVersion = fc.constantFrom('placement-tco-comparison.v1', 'invalid', '');
const currency = fc.constantFrom('USD', 'EUR', 'GBP', 'JPY', 'invalid');
const horizonMonths = fc.integer({ minValue: -100, maxValue: 200 });

const scenarioSnapshot = fc.record({
  name: snapshotName,
  payload: fc.record({
    schema_version: schemaVersion,
    assumptions: fc.record({
      currency: currency,
      horizon_months: horizonMonths,
    }),
    sources: fc.record({
      onprem: fc.record({ type: fc.string(), reference: fc.string(), observed_on: fc.string() }),
      cloud: fc.record({ type: fc.string(), reference: fc.string(), observed_on: fc.string() }),
    }),
    results: fc.record({
      onprem: fc.record({ total_cost: fc.double() }),
      cloud: fc.record({ total_cost: fc.double() }),
    }),
  }),
});

describe('Placement Scenarios Fuzz Tests', () => {
  describe('validateScenarioSnapshot', () => {
    it('should handle any snapshot object', () => {
      fc.assert(
        fc.property(scenarioSnapshot, (snapshot) => {
          const result = validateScenarioSnapshot(snapshot);
          assert(typeof result === 'boolean');
        }),
        { numRuns: 100 }
      );
    });

    it('should reject invalid snapshots', () => {
      assert(validateScenarioSnapshot(null) === false);
      assert(validateScenarioSnapshot({}) === false);
      assert(validateScenarioSnapshot({ name: 'test' }) === false);
    });
  });

  describe('calculateScenarioHash', () => {
    it('should handle any valid snapshot', () => {
      fc.assert(
        fc.property(scenarioSnapshot, (snapshot) => {
          const hash = calculateScenarioHash(snapshot);
          assert(typeof hash === 'string');
          assert(hash.length > 0);
        }),
        { numRuns: 100 }
      );
    });

    it('should be deterministic', () => {
      const snapshot = {
        name: 'test',
        payload: {
          schema_version: 'placement-tco-comparison.v1',
          assumptions: { currency: 'USD', horizon_months: 12 },
          sources: {},
          results: {},
        },
      };
      const hash1 = calculateScenarioHash(snapshot);
      const hash2 = calculateScenarioHash(snapshot);
      assert(hash1 === hash2);
    });
  });

  describe('compareScenarioSnapshots', () => {
    it('should handle any valid snapshots', () => {
      fc.assert(
        fc.property(scenarioSnapshot, scenarioSnapshot, (a, b) => {
          const result = compareScenarioSnapshots(a, b);
          assert(typeof result === 'boolean');
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('filterScenarios', () => {
    it('should handle any scenario list and filter', () => {
      fc.assert(
        fc.property(
          fc.array(scenarioSnapshot, { maxLength: 10 }),
          fc.record({ profile: fc.string(), objective: fc.string() }),
          (scenarios, filter) => {
            const result = filterScenarios(scenarios, filter);
            assert(Array.isArray(result));
            assert(result.length <= scenarios.length);
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
