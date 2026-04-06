import http from "k6/http";
import { check, sleep } from "k6";

// Load balancer IPs for all 3 regions
const LB_IPS = [
  "http://10.0.1.11", // EU
  "http://10.0.2.11", // US
  "http://10.0.3.11", // APAC
];

export const options = {
  vus: 50,
  duration: "2m",
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const lb = LB_IPS[Math.floor(Math.random() * LB_IPS.length)];

  const payload = JSON.stringify({
    origin: "Dublin",
    destination: "Cork",
    start_time: new Date(Date.now() + 3600000).toISOString(),
  });

  const params = {
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${__ENV.AUTH_TOKEN || "test-token"}`,
    },
  };

  const res = http.post(`${lb}/journeys`, payload, params);

  check(res, {
    "status is 200 or 201": (r) => r.status === 200 || r.status === 201,
    "response time < 500ms": (r) => r.timings.duration < 500,
  });

  sleep(1);
}
