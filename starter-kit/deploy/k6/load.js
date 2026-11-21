// k6 load test skeleton (backlog F-011). Run: make load   (stack must be up)
// Paths: read path (dashboard) and decision-read path. Adjust to the real API.
import http from 'k6/http';
import { check, sleep } from 'k6';

const API = __ENV.API_URL || 'http://localhost:8101';

export const options = {
  scenarios: {
    dashboard_reads: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '60s', target: 50 },
        { duration: '30s', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],      // <1% errors (initial target; record the measured value)
    http_req_duration: ['p(95)<250'],    // initial target; record measured p50/p95/p99
  },
};

export default function () {
  const state = http.get(`${API}/api/state`);
  check(state, { 'state 200': (r) => r.status === 200 });
  const risks = http.get(`${API}/api/risks`);
  check(risks, { 'risks 200': (r) => r.status === 200 });
  sleep(1);
}
