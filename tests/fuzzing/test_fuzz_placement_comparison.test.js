/**
 * Fuzz tests for placement-comparison.js using fast-check.
 * Tests the placement comparison and scenario evaluation functions.
 */
const fc = require('fast-check');
const assert = require('assert');

// Placement scenario evaluation
function evaluatePlacementScenario(costs, assumptions) {
  const { horizonMonths, annualDiscountRate, usefulUnitsPerMonth } = assumptions;
  const monthlyDiscount = 1 / (1 + annualDiscountRate);
  
  let npv = 0;
  const breakdown = [];
  
  // Upfront costs
  const upfront = (costs.capex || 0) + (costs.site || 0) + (costs.migration || 0);
  npv += upfront;
  breakdown.push({ type: 'upfront', amount: upfront, month: 0 });
  
  // Monthly costs
  const monthlyTotal = Object.entries(costs)
    .filter(([key]) => key.endsWith('Monthly') || ['power', 'software', 'maintenance', 'labor', 'network', 'backup', 'other'].includes(key))
    .reduce((sum, [, val]) => sum + (val || 0), 0);
  
  for (let m = 1; m <= horizonMonths; m++) {
    const discounted = monthlyTotal * Math.pow(monthlyDiscount, m / 12);
    npv += discounted;
    if (m <= 3) {
      breakdown.push({ type: 'monthly', amount: monthlyTotal, month: m });
    }
  }
  
  // Refresh
  if (costs.refreshMonth > 0 && costs.refreshMonth <= horizonMonths && costs.refresh) {
    const discounted = costs.refresh * Math.pow(monthlyDiscount, costs.refreshMonth / 12);
    npv += discounted;
    breakdown.push({ type: 'refresh', amount: costs.refresh, month: costs.refreshMonth });
  }
  
  // Terminal
  const terminal = (costs.exitCost || 0) - (costs.residualValue || 0);
  const terminalDiscounted = terminal * Math.pow(monthlyDiscount, horizonMonths / 12);
  npv += terminalDiscounted;
  breakdown.push({ type: 'terminal', amount: terminal, month: horizonMonths });
  
  const totalUnits = horizonMonths * usefulUnitsPerMonth;
  const costPerUnit = totalUnits > 0 ? npv / totalUnits : Infinity;
  
  return { npv, costPerUnit, breakdown };
}

// Compare two placement scenarios
function comparePlacementScenarios(onprem, cloud, assumptions) {
  const onpremResult = evaluatePlacementScenario(onprem, assumptions);
  const cloudResult = evaluatePlacementScenario(cloud, assumptions);
  
  return {
    onprem: onpremResult,
    cloud: cloudResult,
    delta: onpremResult.npv - cloudResult.npv,
    winner: onpremResult.npv < cloudResult.npv ? 'onprem' : 'cloud',
  };
}

// Sensitivity analysis
function sensitivityAnalysis(baseCosts, assumptions, parameter, values) {
  return values.map(val => {
    const modified = { ...baseCosts, [parameter]: val };
    const result = evaluatePlacementScenario(modified, assumptions);
    return { value: val, npv: result.npv, costPerUnit: result.costPerUnit };
  });
}

// Strategies
const nonNegativeNumber = fc.double({ min: 0, max: 1e9, noNaN: true });
const positiveNumber = fc.double({ min: 0.001, max: 1e9, noNaN: true });
const discountRate = fc.double({ min: 0, max: 1, noNaN: true });
const horizonMonths = fc.integer({ min: 1, max: 120 });
const refreshMonth = fc.integer({ min: 0, max: 120 });

const placementCosts = fc.record({
  capex: nonNegativeNumber,
  site: nonNegativeNumber,
  migration: nonNegativeNumber,
  powerMonthly: nonNegativeNumber,
  softwareMonthly: nonNegativeNumber,
  maintenanceMonthly: nonNegativeNumber,
  laborMonthly: nonNegativeNumber,
  networkMonthly: nonNegativeNumber,
  backupMonthly: nonNegativeNumber,
  otherMonthly: nonNegativeNumber,
  refresh: nonNegativeNumber,
  refreshMonth: refreshMonth,
  exitCost: nonNegativeNumber,
  residualValue: nonNegativeNumber,
}).map(costs => {
  // Ensure residual <= exit to keep NPV non-negative
  if (costs.residualValue > costs.exitCost) {
    costs.residualValue = costs.exitCost;
  }
  return costs;
});

const assumptions = fc.record({
  horizonMonths: horizonMonths,
  annualDiscountRate: discountRate,
  usefulUnitsPerMonth: positiveNumber,
});

describe('Placement Comparison Fuzz Tests', () => {
  describe('evaluatePlacementScenario', () => {
    it('should handle any valid costs and assumptions', () => {
      fc.assert(
        fc.property(placementCosts, assumptions, (costs, assumps) => {
          const result = evaluatePlacementScenario(costs, assumps);
          assert(Number.isFinite(result.npv));
          assert(result.npv >= 0);
          assert(Array.isArray(result.breakdown));
          assert(result.breakdown.length > 0);
        }),
        { numRuns: 100 }
      );
    });

    it('should handle zero costs', () => {
      const zeroCosts = {
        capex: 0, site: 0, migration: 0,
        powerMonthly: 0, softwareMonthly: 0, maintenanceMonthly: 0,
        laborMonthly: 0, networkMonthly: 0, backupMonthly: 0, otherMonthly: 0,
        refresh: 0, refreshMonth: 0, exitCost: 0, residualValue: 0,
      };
      const assumps = { horizonMonths: 12, annualDiscountRate: 0.08, usefulUnitsPerMonth: 1 };
      const result = evaluatePlacementScenario(zeroCosts, assumps);
      assert(result.npv === 0);
    });
  });

  describe('comparePlacementScenarios', () => {
    it('should handle any valid scenarios', () => {
      fc.assert(
        fc.property(placementCosts, placementCosts, assumptions, (onprem, cloud, assumps) => {
          const result = comparePlacementScenarios(onprem, cloud, assumps);
          assert(['onprem', 'cloud'].includes(result.winner));
          assert(Number.isFinite(result.delta));
          assert(Number.isFinite(result.onprem.npv));
          assert(Number.isFinite(result.cloud.npv));
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('sensitivityAnalysis', () => {
    it('should handle any valid parameter values', () => {
      fc.assert(
        fc.property(
          placementCosts,
          assumptions,
          fc.array(nonNegativeNumber, { minLength: 1, maxLength: 10 }),
          (costs, assumps, values) => {
            const result = sensitivityAnalysis(costs, assumps, 'capex', values);
            assert(result.length === values.length);
            result.forEach(r => {
              assert(Number.isFinite(r.npv));
            });
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
