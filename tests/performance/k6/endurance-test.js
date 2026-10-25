/**
 * k6 Endurance Test — Data Center Commander API
 *
 * Sustained load over extended period to detect memory leaks,
 * connection pool exhaustion, and degradation over time.
 *
 * Usage:
 *   k6 run tests/performance/k6/endurance-test.js
 *   k6 run --env DURATION=30m tests/performance/k6/endurance-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TENANT_ID, buildUrl, getHeaders } from './shared.js';

const duration = __ENV.DURATION || '15m';
const targetVus = __ENV.VUS || 25;

export const options = {
  stages: [
    { duration: '2m', target: targetVus },   // Ramp up
    { duration: duration, target: targetVus }, // Sustained load
    { duration: '2m', target: 0 },            // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<4000'],
    http_req_failed: ['rate<0.05'],
    http_reqs: ['rate>5'],
  },
};

const headers = getHeaders();

export default function () {
  // Core endpoints under sustained load
  let res = http.get(buildUrl('/v2/overview'), { headers });
  check(res, { 'overview status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/assets'), { headers });
  check(res, { 'assets status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/facilities'), { headers });
  check(res, { 'facilities status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/workflows'), { headers });
  check(res, { 'workflows status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/analytics', { window_days: 30 }), { headers });
  check(res, { 'analytics status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/topology'), { headers });
  check(res, { 'topology status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/costs'), { headers });
  check(res, { 'costs status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/capacity'), { headers });
  check(res, { 'capacity status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/evidence'), { headers });
  check(res, { 'evidence status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/connectors'), { headers });
  check(res, { 'connectors status is 200': (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/healthz`, { headers });
  check(res, { 'healthz status is 200': (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/readyz`, { headers });
  check(res, { 'readyz status is 200': (r) => r.status === 200 });

  sleep(1);
}
