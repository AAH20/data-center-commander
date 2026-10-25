/**
 * Shared utilities for k6 performance tests.
 * Base URL, tenant ID, and common request helpers.
 *
 * NOTE: this file is loaded by k6's JavaScript runtime, not by Node. That runtime
 * has no `URLSearchParams`, no `setTimeout` and no event loop, so the URL is built
 * with `encodeURIComponent` and sleeping is k6's blocking `sleep`. The previous
 * version used all three and threw `ReferenceError: URLSearchParams is not
 * defined` on the first request of every scenario that called `buildUrl` -- which
 * went unnoticed because nothing ever ran these scripts in CI.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';

export const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8790';
// The seeded demo tenant in dcc_demo_local. The old placeholder (00000000-...) owns
// no rows, so a load test against it measured empty responses.
export const TENANT_ID = __ENV.TENANT_ID || 'dcc00000-0000-4000-8000-000000000001';

export const DEFAULT_PARAMS = {
  tenant_id: TENANT_ID,
};

export function buildUrl(path, extraParams = {}) {
  const params = Object.assign({}, DEFAULT_PARAMS, extraParams);
  const query = Object.keys(params)
    .map((key) => `${encodeURIComponent(key)}=${encodeURIComponent(params[key])}`)
    .join('&');
  return `${BASE_URL}${path}?${query}`;
}

export function getHeaders() {
  return {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
}

export function get(path, extraParams = {}) {
  return http.get(buildUrl(path, extraParams), { headers: getHeaders() });
}

export function post(path, body) {
  return http.post(buildUrl(path), JSON.stringify(body), { headers: getHeaders() });
}

export function checkResponse(res, expectedStatus = 200) {
  return check(res, {
    [`status is ${expectedStatus}`]: (r) => r.status === expectedStatus,
    'response time < 2000ms': (r) => r.timings.duration < 2000,
  });
}

export { sleep };
