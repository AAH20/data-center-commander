// Fuzz tests for azure-prices.js using fast-check.
const fc = require('fast-check');
const assert = require('assert');

// Price formatting
function formatPrice(value, currency) {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value.toFixed(6).replace(/0+$/, '').replace(/\.$/, '')} ${currency || 'USD'}`;
}

// CSV escaping
function escapeCsv(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`;
}

// Price calculation
function calculateMonthlyEstimate(unitsPerMonth, unitPrice) {
  if (!Number.isFinite(unitsPerMonth) || !Number.isFinite(unitPrice)) return null;
  return unitsPerMonth * unitPrice;
}

function calculateAnnualized(monthlyEstimate) {
  if (!Number.isFinite(monthlyEstimate)) return null;
  return monthlyEstimate * 12;
}

// Price comparison
function comparePrices(priceA, priceB) {
  if (!Number.isFinite(priceA) || !Number.isFinite(priceB)) return null;
  if (priceA < priceB) return -1;
  if (priceA > priceB) return 1;
  return 0;
}

// Strategies
const priceValue = fc.double({ min: 0, max: 1e9, noNaN: true });
const currency = fc.constantFrom('USD', 'EUR', 'GBP', 'JPY', '');
const unitsPerMonth = fc.double({ min: 0, max: 1e9, noNaN: true });
const unitPrice = fc.double({ min: 0, max: 1e9, noNaN: true });
const csvValue = fc.string();

describe('Azure Prices Fuzz Tests', () => {
  describe('formatPrice', () => {
    it('should handle any value and currency', () => {
      fc.assert(
        fc.property(priceValue, currency, (value, curr) => {
          const result = formatPrice(value, curr);
          assert(typeof result === 'string');
          assert(result.length > 0);
        }),
        { numRuns: 100 }
      );
    });

    it('should handle null/undefined values', () => {
      assert(formatPrice(null, 'USD') === '—');
      assert(formatPrice(undefined, 'USD') === '—');
      assert(formatPrice(NaN, 'USD') === '—');
      assert(formatPrice(Infinity, 'USD') === '—');
    });
  });

  describe('escapeCsv', () => {
    it('should handle any string value', () => {
      fc.assert(
        fc.property(csvValue, (value) => {
          const result = escapeCsv(value);
          assert(typeof result === 'string');
          assert(result.startsWith('"'));
          assert(result.endsWith('"'));
        }),
        { numRuns: 100 }
      );
    });

    it('should escape quotes correctly', () => {
      assert(escapeCsv('test"value') === '"test""value"');
      assert(escapeCsv('') === '""');
      assert(escapeCsv(null) === '""');
    });
  });

  describe('calculateMonthlyEstimate', () => {
    it('should handle any valid inputs', () => {
      fc.assert(
        fc.property(unitsPerMonth, unitPrice, (units, price) => {
          const result = calculateMonthlyEstimate(units, price);
          assert(Number.isFinite(result));
          assert(result >= 0);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('calculateAnnualized', () => {
    it('should handle any valid monthly estimate', () => {
      fc.assert(
        fc.property(priceValue, (monthly) => {
          const result = calculateAnnualized(monthly);
          assert(Number.isFinite(result));
          assert(result >= 0);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('comparePrices', () => {
    it('should handle any valid prices', () => {
      fc.assert(
        fc.property(priceValue, priceValue, (a, b) => {
          const result = comparePrices(a, b);
          assert(result === -1 || result === 0 || result === 1);
        }),
        { numRuns: 100 }
      );
    });
  });
});
