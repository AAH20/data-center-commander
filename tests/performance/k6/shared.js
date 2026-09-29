/**
 * Shared utilities for k6 performance tests.
 * Base URL, tenant ID, and common request helpers.
 */

export const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8790';
export const TENANT_ID = __ENV.TENANT_ID || '00000000-0000-4000-8000-000000000001';

export const DEFAULT_PARAMS = {
  tenant_id: TENANT_ID,
};

export function buildUrl(path, extraParams = {}) {
  const params = new URLSearchParams({ ...DEFAULT_PARAMS, ...extraParams });
  return `${BASE_URL}${path}?${params.toString()}`;
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

export function sleep(seconds) {
  return new Promise((resolve) => setTimeout(resolve, seconds * 1000));
}
