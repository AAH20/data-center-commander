/**
 * k6 Spike Test — Data Center Commander API
 *
 * Simulates sudden traffic spikes (e.g., dashboard refresh storms,
 * monitoring agents polling simultaneously).
 *
 * Usage:
 *   k6 run tests/performance/k6/spike-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, TENANT_ID, buildUrl, getHeaders } from './shared.js';

export const options = {
  stages: [
    { duration: '30s', target: 5 },    // Baseline
    { duration: '10s', target: 100 },  // Sudden spike
    { duration: '1m', target: 100 },   // Hold at peak
    { duration: '10s', target: 5 },    // Drop back
    { duration: '1m', target: 5 },     // Recovery
    { duration: '10s', target: 150 },  // Second spike
    { duration: '1m', target: 150 },   // Hold
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000', 'p(99)<4000'],
    http_req_failed: ['rate<0.08'],
  },
};

const headers = getHeaders();

export default function () {
  // Simulate dashboard refresh storm
  let res = http.get(buildUrl('/v2/overview'), { headers });
  check(res, { 'overview status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/analytics', { window_days: 7 }), { headers });
  check(res, { 'analytics status is 200': (r) => r.status === 200 });

  res = http.get(buildUrl('/v2/assets'), { headers });
  check(res, { 'assets status is 200': (r) => r.status === 200 });

  res = http.get(`${BASE_URL}/healthz`, { headers });
  check(res, { 'healthz status is 200': (r) => r.status === 200 });

  sleep(0.2);
}
