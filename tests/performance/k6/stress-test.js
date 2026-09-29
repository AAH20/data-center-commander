/**
 * k6 Stress Test — Data Center Commander API
 *
 * Pushes the system beyond normal capacity to find breaking points.
 * Uses aggressive ramp-up to high VU counts.
 *
 * Usage:
 *   k6 run tests/performance/k6/stress-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TENANT_ID, buildUrl, getHeaders } from './shared.js';

export const options = {
  stages: [
    { duration: '2m', target: 50 },   // Ramp to 50 VUs
    { duration: '5m', target: 50 },   // Hold
    { duration: '2m', target: 100 },  // Ramp to 100 VUs
    { duration: '5m', target: 100 },  // Hold
    { duration: '2m', target: 200 },  // Ramp to 200 VUs
    { duration: '5m', target: 200 },  // Hold
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<3000', 'p(99)<5000'],
    http_req_failed: ['rate<0.10'],
  },
};

const headers = getHeaders();

export default function () {
  // Heavy endpoints under stress
  let res = http.get(buildUrl('/v1/analytics', { window_days: 90 }), { headers });
  check(res, { 'analytics status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v1/assets'), { headers });
  check(res, { 'assets status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v1/topology'), { headers });
  check(res, { 'topology status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v1/costs'), { headers });
  check(res, { 'costs status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v1/capacity'), { headers });
  check(res, { 'capacity status is 200': (r) => r.status === 200 });

  sleep(0.5);
}
