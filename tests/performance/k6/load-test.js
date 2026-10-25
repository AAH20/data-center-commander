/**
 * k6 Load Test — Data Center Commander API
 *
 * Simulates normal production traffic with a steady ramp-up
 * to a target VU count, holds, then ramps down.
 *
 * Usage:
 *   k6 run tests/performance/k6/load-test.js
 *   k6 run --env BASE_URL=http://localhost:8790 tests/performance/k6/load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TENANT_ID, buildUrl, getHeaders } from './shared.js';

export const options = {
  stages: [
    { duration: '1m', target: 10 },   // Ramp up to 10 VUs
    { duration: '3m', target: 10 },   // Hold at 10 VUs
    { duration: '1m', target: 20 },   // Ramp up to 20 VUs
    { duration: '3m', target: 20 },   // Hold at 20 VUs
    { duration: '1m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    http_req_failed: ['rate<0.05'],
    http_reqs: ['rate>10'],
  },
};

const params = { tenant_id: TENANT_ID };
const headers = getHeaders();

export default function () {
  // Health check
  let res = http.get(`${BASE_URL}/healthz`, { headers });
  check(res, { 'healthz status is 200': (r) => r.status === 200 });

  // Overview
  res = http.get(buildUrl('/v2/overview'), { headers });
  check(res, { 'overview status is 200': (r) => r.status === 200 });

  // Assets
  res = http.get(buildUrl('/v2/assets'), { headers });
  check(res, { 'assets status is 200': (r) => r.status === 200 });

  // Facilities
  res = http.get(buildUrl('/v2/facilities'), { headers });
  check(res, { 'facilities status is 200': (r) => r.status === 200 });

  // Workflows
  res = http.get(buildUrl('/v2/workflows'), { headers });
  check(res, { 'workflows status is 200': (r) => r.status === 200 });

  // Analytics
  res = http.get(buildUrl('/v2/analytics', { window_days: 30 }), { headers });
  check(res, { 'analytics status is 200': (r) => r.status === 200 });

  // Topology
  res = http.get(buildUrl('/v2/topology'), { headers });
  check(res, { 'topology status is 200': (r) => r.status === 200 });

  sleep(1);
}
