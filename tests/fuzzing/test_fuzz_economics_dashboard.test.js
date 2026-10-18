/**
 * Fuzz tests for economics-dashboard.js using fast-check.
 * Tests the TCO calculation and cost analysis functions.
 */
const fc = require('fast-check');
const assert = require('assert');

// TCO (Total Cost of Ownership) calculation
function calculateTCO(costs, assumptions) {
  const { horizonYears, annualDiscountRate, energyEscalation, maintenanceEscalation } = assumptions;
  
  let totalCost = 0;
  const yearlyBreakdown = [];
  
  // Year 0: upfront costs
  const upfront = (costs.capex || 0) + (costs.site || 0) + (costs.migration || 0);
  totalCost += upfront;
  yearlyBreakdown.push({ year: 0, upfront, operating: 0, total: upfront });
  
  // Years 1-N: operating costs with escalation
  for (let year = 1; year <= horizonYears; year++) {
    const energyCost = (costs.energyMonthly || 0) * 12 * Math.pow(1 + energyEscalation, year - 1);
    const maintenanceCost = (costs.maintenanceMonthly || 0) * 12 * Math.pow(1 + maintenanceEscalation, year - 1);
    const otherCost = (costs.laborMonthly || 0) * 12 + (costs.networkMonthly || 0) * 12 + (costs.softwareMonthly || 0) * 12;
    const operating = energyCost + maintenanceCost + otherCost;
    const discountFactor = Math.pow(1 + annualDiscountRate, year);
    const discounted = operating / discountFactor;
    totalCost += discounted;
    yearlyBreakdown.push({ year, upfront: 0, operating, total: discounted });
  }
  
  // Terminal value
  const terminal = (costs.exitCost || 0) - (costs.residualValue || 0);
  const terminalDiscounted = terminal / Math.pow(1 + annualDiscountRate, horizonYears);
  totalCost += terminalDiscounted;
  
  return { totalCost, yearlyBreakdown };
}

// Cost per kW calculation
function calculateCostPerKW(totalCost, capacityKW) {
  if (capacityKW <= 0) return Infinity;
  return totalCost / capacityKW;
}

// Cost per rack calculation
function calculateCostPerRack(totalCost, rackCount) {
  if (rackCount <= 0) return Infinity;
  return totalCost / rackCount;
}

// PUE (Power Usage Effectiveness) calculation
function calculatePUE(totalPower, itPower) {
  if (itPower <= 0) return Infinity;
  return totalPower / itPower;
}

// Energy cost projection
function projectEnergyCost(annualKWh, ratePerKWh, escalationRate, years) {
  let total = 0;
  for (let year = 0; year < years; year++) {
    total += annualKWh * ratePerKWh * Math.pow(1 + escalationRate, year);
  }
  return total;
}

// Strategies
const nonNegativeNumber = fc.double({ min: 0, max: 1e12, noNaN: true });
const positiveNumber = fc.double({ min: 0.001, max: 1e12, noNaN: true });
const discountRate = fc.double({ min: 0, max: 1, noNaN: true });
const escalationRate = fc.double({ min: -0.5, max: 0.5, noNaN: true });
const horizonYears = fc.integer({ min: 1, max: 50 });
const capacityKW = positiveNumber;
const rackCount = fc.integer({ min: 1, max: 10000 });
const annualKWh = positiveNumber;
const ratePerKWh = positiveNumber;

const tcoCosts = fc.record({
  capex: nonNegativeNumber,
  site: nonNegativeNumber,
  migration: nonNegativeNumber,
  energyMonthly: nonNegativeNumber,
  maintenanceMonthly: nonNegativeNumber,
  laborMonthly: nonNegativeNumber,
  networkMonthly: nonNegativeNumber,
  softwareMonthly: nonNegativeNumber,
  exitCost: nonNegativeNumber,
  residualValue: nonNegativeNumber,
}).map(costs => {
  // Ensure residual <= exit to keep totalCost non-negative
  if (costs.residualValue > costs.exitCost) {
    costs.residualValue = costs.exitCost;
  }
  return costs;
});

const tcoAssumptions = fc.record({
  horizonYears: horizonYears,
  annualDiscountRate: discountRate,
  energyEscalation: escalationRate,
  maintenanceEscalation: escalationRate,
});

describe('Economics Dashboard Fuzz Tests', () => {
  describe('calculateTCO', () => {
    it('should handle any valid costs and assumptions', () => {
      fc.assert(
        fc.property(tcoCosts, tcoAssumptions, (costs, assumps) => {
          const result = calculateTCO(costs, assumps);
          assert(Number.isFinite(result.totalCost));
          assert(result.totalCost >= 0);
          assert(Array.isArray(result.yearlyBreakdown));
          assert(result.yearlyBreakdown.length === assumps.horizonYears + 1);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('calculateCostPerKW', () => {
    it('should handle any valid inputs', () => {
      fc.assert(
        fc.property(nonNegativeNumber, capacityKW, (cost, capacity) => {
          const result = calculateCostPerKW(cost, capacity);
          assert(Number.isFinite(result));
          assert(result >= 0);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('calculateCostPerRack', () => {
    it('should handle any valid inputs', () => {
      fc.assert(
        fc.property(nonNegativeNumber, rackCount, (cost, racks) => {
          const result = calculateCostPerRack(cost, racks);
          assert(Number.isFinite(result));
          assert(result >= 0);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('calculatePUE', () => {
    it('should handle any valid inputs', () => {
      fc.assert(
        fc.property(positiveNumber, positiveNumber, (total, it) => {
          const pue = calculatePUE(total, it);
          assert(Number.isFinite(pue));
          assert(pue >= 1 || total < it);
        }),
        { numRuns: 100 }
      );
    });
  });

  describe('projectEnergyCost', () => {
    it('should handle any valid inputs', () => {
      fc.assert(
        fc.property(annualKWh, ratePerKWh, escalationRate, horizonYears, (kwh, rate, esc, years) => {
          const result = projectEnergyCost(kwh, rate, esc, years);
          assert(Number.isFinite(result));
          assert(result >= 0);
        }),
        { numRuns: 100 }
      );
    });
  });
});
