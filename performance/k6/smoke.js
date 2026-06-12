/**
 * k6 smoke test — nanotech.icu
 *
 * Endpoints: GET /  · GET /script.js  · GET /api/auth/me  · POST /api/chat-consent
 * SLOs: http_req_failed < 1% · p(95) < 1500ms · checks > 99%
 *
 * Run: k6 run [-e BASE_URL=https://nanotech.icu] performance/k6/smoke.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'https://nanotech.icu';

export const errorRate = new Rate('errors');

export const options = {
  vus: 2,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1500'],
    errors: ['rate<0.01'],
    checks: ['rate>0.99'],
  },
};

export default function () {
  // 1. Landing page
  let res = http.get(`${BASE_URL}/`, { tags: { endpoint: 'landing' } });
  errorRate.add(
    !check(res, {
      'landing status 200': (r) => r.status === 200,
      'landing is HTML': (r) => (r.headers['Content-Type'] || '').includes('text/html'),
    }),
  );

  // 2. Script bundle
  res = http.get(`${BASE_URL}/script.js`, { tags: { endpoint: 'script' } });
  errorRate.add(
    !check(res, {
      'script status 200': (r) => r.status === 200,
      'script is JS': (r) => (r.headers['Content-Type'] || '').includes('javascript'),
    }),
  );

  // 3. Unauthenticated /api/auth/me — must be 401
  res = http.get(`${BASE_URL}/api/auth/me`, { tags: { endpoint: 'auth_me' } });
  errorRate.add(
    !check(res, {
      'auth/me 401': (r) => r.status === 401,
    }),
  );

  // 4. Consent acknowledgement — must be 200
  const consentPayload = JSON.stringify({
    accepted_at: new Date().toISOString(),
    consent_version: 'k6-smoke',
    source: 'k6',
    path: '/',
    locale: 'en-US',
  });
  res = http.post(`${BASE_URL}/api/chat-consent`, consentPayload, {
    headers: { 'Content-Type': 'application/json' },
    tags: { endpoint: 'chat_consent' },
  });
  errorRate.add(
    !check(res, {
      'chat-consent 200': (r) => r.status === 200,
      'chat-consent ok=true': (r) => {
        try {
          return r.json('ok') === true;
        } catch (_e) {
          return false;
        }
      },
    }),
  );

  sleep(1);
}
