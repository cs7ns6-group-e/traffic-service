import http from "k6/http";
import { check, sleep } from "k6";

// Load balancer IPs for all 3 regions
const LB_IPS = [
  "http://10.0.1.11", // EU
  "http://10.0.2.11", // US
  "http://10.0.3.11", // APAC
];

export const options = {
  vus: 10,
  duration: "30s",
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  for (const lb of LB_IPS) {
    const res = http.get(`${lb}/health`);

    check(res, {
      "status is 200": (r) => r.status === 200,
      "response time < 500ms": (r) => r.timings.duration < 500,
    });
  }

  sleep(1);
}
